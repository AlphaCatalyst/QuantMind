import json
from pathlib import Path

from backend.services.engine.factor_validation import validate_frozen_result, validate_validation_result

from .canonical import sha256_file
from .errors import RegistryEvidenceError
from .models import RegistryEntry
from .status import derive_status


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise RegistryEvidenceError("research evidence JSON is unreadable") from exc


def _verify_hashes(root, manifest):
    for relative, digest in manifest.get("file_hashes", {}).items():
        path = Path(root) / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise RegistryEvidenceError("research evidence file hash mismatch")


def _metrics_summary(metrics):
    if metrics is None:
        return None
    keys = ("date_count_valid", "median_daily_observations", "mean_rank_ic", "rank_icir",
            "rank_ic_positive_rate", "factor_finite_coverage", "constant_output")
    return {key: metrics[key] for key in keys}


def _verify_correction(repository_root):
    root = Path(repository_root)
    correction_path = root / "docs/quantmind2/implementation/corrections/QM2-P0-006-evidence-correction-v1.json"
    run_path = root / "docs/quantmind2/implementation/runs/2026/2026-07/QM2-P0-006F-20260717T044608Z-8ad3e22/manifest.json"
    correction, run = _load(correction_path), _load(run_path)
    rels = run.get("relationships", [])
    if correction.get("effect") != "evidence_correction_only" or not any(
        rel.get("relationship_type") == "corrects" and
        rel.get("target_run_id") == correction.get("target_run_id") for rel in rels
    ):
        raise RegistryEvidenceError("QM2-P0-006F correction relationship is absent")
    return sha256_file(correction_path), sha256_file(run_path)


def build_entries_from_evidence(*, repository_root, optimization_root, validation_root,
                                validation_result_id, selection_id, frozen_result_id, policy):
    validation = validate_validation_result(validation_root, validation_result_id, selection_id)
    frozen = validate_frozen_result(validation_root, frozen_result_id)
    result_manifest = validation["manifest"]; selection = validation["selection"]
    frozen_manifest = frozen["manifest"]
    if frozen_manifest["candidate_selection_id"] != selection_id or frozen_manifest["selection_history_changed"] or frozen_manifest["reselection_permitted"]:
        raise RegistryEvidenceError("Frozen evidence does not preserve immutable Selection")
    correction_hash, correction_run_hash = _verify_correction(repository_root)
    selected = set(selection["selected_trial_ids"])
    frozen_by_trial = {item["trial_id"]: item for item in frozen_manifest["results"]}
    studies = {}
    original_trials = {}
    template_names = {}
    for study_id in result_manifest["spec"]["optimization_study_ids"]:
        root = Path(optimization_root) / study_id
        manifest, spec = _load(root / "manifest.json"), _load(root / "spec.json")
        _verify_hashes(root, manifest)
        if manifest.get("study_id") != study_id or manifest.get("status") != "succeeded":
            raise RegistryEvidenceError("Optimization Study identity/status mismatch")
        studies[study_id] = (root, manifest, spec)
        template_names[manifest["template_id"]] = spec["template"]["name"]
        for trial_id in manifest["trial_ids"]:
            original_trials[trial_id] = _load(root / "trials" / f"{trial_id}.json")
    entries = []
    for trial in result_manifest["trial_results"]:
        original = original_trials.get(trial["trial_id"])
        if not original or original["parameters"] != trial["parameters"]:
            raise RegistryEvidenceError("Optimization/Validation parameter lineage mismatch")
        study_root, study_manifest, _ = studies[trial["study_id"]]
        if study_manifest["template_id"] != trial["template_id"]:
            raise RegistryEvidenceError("Optimization/Validation Template lineage mismatch")
        frozen_item = frozen_by_trial.get(trial["trial_id"])
        if (trial["trial_id"] in selected) != (frozen_item is not None):
            raise RegistryEvidenceError("Selection/Frozen candidate set mismatch")
        if frozen_item and (frozen_item["factor_instance_id"] != trial["factor_instance_id"] or
                            frozen_item["factor_values_id"] != trial["factor_values_id"] or
                            frozen_item["orientation"] != trial["orientation"]):
            raise RegistryEvidenceError("Frozen lineage/orientation mismatch")
        validation_metrics = _metrics_summary(trial["validation_oriented_metrics"])
        frozen_metrics = _metrics_summary(frozen_item["frozen_metrics"]) if frozen_item else None
        status, reasons = derive_status(has_validation=True,
            validation_passed=trial["eligible_for_selection"], selected=trial["selected_for_frozen"],
            frozen_metrics=frozen_metrics, validation_metrics=validation_metrics, policy=policy)
        values_ids = tuple(dict.fromkeys((original["factor_values_id"], trial["factor_values_id"])))
        trial_path = Path(validation["result_path"]) / "trials" / f"{trial['trial_id']}.json"
        hashes = {
            "optimization_manifest": sha256_file(study_root / "manifest.json"),
            "optimization_trial": sha256_file(study_root / "trials" / f"{trial['trial_id']}.json"),
            "validation_manifest": sha256_file(Path(validation["result_path"]) / "manifest.json"),
            "validation_trial": sha256_file(trial_path),
            "selection_manifest": sha256_file(Path(validation["selection_path"]) / "manifest.json"),
            "correction_artifact": correction_hash,
            "correction_run_manifest": correction_run_hash,
        }
        if frozen_item:
            hashes["frozen_manifest"] = sha256_file(Path(frozen["path"]) / "manifest.json")
        entries.append(RegistryEntry(
            factor_instance_id=trial["factor_instance_id"], template_id=trial["template_id"],
            template_name=template_names[trial["template_id"]], parameter_values=dict(trial["parameters"]),
            dataset_snapshot_id=result_manifest["feature_snapshot_id"], factor_values_ids=values_ids,
            optimization_study_id=trial["study_id"], optimization_trial_id=trial["trial_id"],
            validation_dataset_id=result_manifest["validation_dataset_id"], validation_result_id=validation_result_id,
            candidate_selection_id=selection_id, frozen_result_id=frozen_result_id if frozen_item else None,
            orientation=trial["orientation"], status=status, status_reasons=reasons,
            validation_metrics_summary=validation_metrics, frozen_metrics_summary=frozen_metrics,
            evidence_hashes=dict(sorted(hashes.items())), family_id=trial["template_id"],
            created_from_protocols=("factor-optimization-artifact-v1", "factor-validation-result-v1",
                "qm2-frozen-2026-v1" if frozen_item else "factor-validation-selection-v1",
                "qm2-p0-006f-evidence-correction-v1"), redundancy_group=None))
    if len(entries) != 14 or len({entry.factor_instance_id for entry in entries}) != 14:
        raise RegistryEvidenceError("Registry requires exactly fourteen distinct real instances")
    return tuple(sorted(entries, key=lambda item: item.factor_instance_id))
