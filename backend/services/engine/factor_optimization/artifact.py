import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.services.engine.factor_dsl.artifact import sha256_file, validate_values
from backend.services.engine.factor_dsl.canonical import canonical_json_bytes
from backend.services.engine.factor_dsl.identity import ENGINE_VERSION as DSL_ENGINE_VERSION

from .canonical import hash_payload, spec_payload
from .eligibility import evaluate_eligibility, validation_candidate_order
from .enums import StudyStatus, TrialStatus
from .errors import OptimizationArtifactError
from .identity import OPTIMIZATION_ENGINE_VERSION, result_id
from .metrics import compute_mechanical_metrics, metrics_payload
from .models import FactorOptimizationResult, FactorOptimizationTrial, MechanicalMetrics


ARTIFACT_SCHEMA_VERSION = "factor-optimization-artifact-v1"


def trial_payload(trial):
    return {"trial_id": trial.trial_id, "ordinal": trial.ordinal,
            "parameters": dict(sorted(trial.parameters.items())), "factor_instance_id": trial.factor_instance_id,
            "status": trial.status.value, "factor_values_id": trial.factor_values_id,
            "parquet_sha256": trial.parquet_sha256,
            "metrics": metrics_payload(trial.metrics) if trial.metrics else None,
            "eligible_for_validation": trial.eligible_for_validation,
            "ineligibility_reasons": list(trial.ineligibility_reasons), "error_code": trial.error_code}


def stable_manifest_payload(study, trials, status, order):
    counts = {name: sum(t.status.value == name for t in trials) for name in ("succeeded", "replayed", "failed", "not_run")}
    return {"schema_version": ARTIFACT_SCHEMA_VERSION, "study_id": study.study_id,
            "template_id": study.template_id, "snapshot_id": study.snapshot_id,
            "factor_dsl_engine_version": DSL_ENGINE_VERSION,
            "factor_optimization_engine_version": OPTIMIZATION_ENGINE_VERSION,
            "spec_sha256": hash_payload(spec_payload(study.spec)), "status": status.value,
            "trial_count": len(trials), **{f"{key}_count": value for key, value in counts.items()},
            "eligible_count": sum(t.eligible_for_validation for t in trials),
            "validation_candidate_order": list(order), "trial_ids": [t.trial_id for t in trials],
            "trial_result_summaries": [trial_payload(t) for t in trials]}


def publish_study(study, trials, status, order, output_root):
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    target = root / study.study_id
    if target.exists():
        raise OptimizationArtifactError("completed Study directory already exists; validate exact existing before publish")
    for stale in root.glob(f".{study.study_id}.staging-*"):
        if stale.is_dir(): shutil.rmtree(stale)
    staging = root / f".{study.study_id}.staging-{uuid.uuid4().hex}"; staging.mkdir()
    try:
        trials_dir = staging / "trials"; trials_dir.mkdir()
        spec_bytes = canonical_json_bytes(spec_payload(study.spec)) + b"\n"
        (staging / "spec.json").write_bytes(spec_bytes)
        for trial in trials:
            (trials_dir / f"{trial.trial_id}.json").write_bytes(canonical_json_bytes(trial_payload(trial)) + b"\n")
        stable = stable_manifest_payload(study, trials, status, order)
        manifest_hash = hash_payload(stable)
        rid = result_id(study.study_id, stable["trial_result_summaries"], order, manifest_hash)
        summary = {"schema_version": ARTIFACT_SCHEMA_VERSION, "study_id": study.study_id,
                   "result_id": rid, "status": status.value, "study_manifest_hash": manifest_hash,
                   "validation_candidate_order": list(order),
                   "counts": {key: stable[key] for key in ("trial_count", "succeeded_count", "replayed_count", "failed_count", "not_run_count", "eligible_count")},
                   "predictive_claim": False}
        (staging / "summary.json").write_bytes(canonical_json_bytes(summary) + b"\n")
        paths = [staging / "spec.json", staging / "summary.json", *sorted(trials_dir.glob("*.json"))]
        file_hashes = {str(path.relative_to(staging)): sha256_file(path) for path in paths}
        manifest = {**{key: value for key, value in stable.items() if key != "trial_result_summaries"},
                    "result_id": rid, "study_manifest_hash": manifest_hash,
                    "search_space": {name: dict(space.source) for name, space in sorted(study.spec.search_spaces.items())},
                    "budget": {"max_trials": study.spec.budget.max_trials, "max_failed_trials": study.spec.budget.max_failed_trials,
                               "stop_on_first_error": study.spec.budget.stop_on_first_error},
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "file_hashes": file_hashes}
        (staging / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
        os.replace(staging, target); staging = None
        return rid, manifest_hash, target
    finally:
        if staging is not None and staging.exists(): shutil.rmtree(staging)


def _trial_from_payload(payload):
    metrics = MechanicalMetrics(**payload["metrics"]) if payload["metrics"] is not None else None
    return FactorOptimizationTrial(payload["trial_id"], payload["ordinal"], payload["parameters"],
                                   payload["factor_instance_id"], TrialStatus(payload["status"]),
                                   payload["factor_values_id"], payload["parquet_sha256"], metrics,
                                   payload["eligible_for_validation"], tuple(payload["ineligibility_reasons"]),
                                   payload["error_code"])


def _study_status(trials):
    successful = sum(t.status in {TrialStatus.SUCCEEDED, TrialStatus.REPLAYED} for t in trials)
    if successful == 0:
        return StudyStatus.FAILED
    if any(t.status in {TrialStatus.FAILED, TrialStatus.NOT_RUN} for t in trials):
        return StudyStatus.PARTIAL
    return StudyStatus.SUCCEEDED


def validate_study(study, snapshot_root, factor_values_root, output_root):
    path = Path(output_root) / study.study_id
    try:
        manifest = json.loads((path / "manifest.json").read_text()); summary = json.loads((path / "summary.json").read_text())
        saved_spec = json.loads((path / "spec.json").read_text())
    except Exception as exc:
        raise OptimizationArtifactError("Study artifact files are unreadable") from exc
    if manifest.get("schema_version") != ARTIFACT_SCHEMA_VERSION or manifest.get("study_id") != study.study_id:
        raise OptimizationArtifactError("Study manifest schema/identity mismatch")
    if saved_spec != spec_payload(study.spec) or manifest.get("spec_sha256") != hash_payload(saved_spec):
        raise OptimizationArtifactError("Study spec content/hash mismatch")
    expected_files = {"spec.json", "summary.json", *{f"trials/{trial.trial_id}.json" for trial in study.trials}}
    if set(manifest.get("file_hashes", {})) != expected_files:
        raise OptimizationArtifactError("Study file inventory mismatch")
    for relative, expected_hash in manifest["file_hashes"].items():
        if sha256_file(path / relative) != expected_hash: raise OptimizationArtifactError("Study file hash mismatch")
    trials = []
    for planned in study.trials:
        payload = json.loads((path / "trials" / f"{planned.trial_id}.json").read_text())
        trial = _trial_from_payload(payload)
        if trial.trial_id != planned.trial_id or trial.factor_instance_id != planned.factor_instance_id or trial.parameters != planned.parameters:
            raise OptimizationArtifactError("Trial identity or parameter binding mismatch")
        if trial.status in {TrialStatus.SUCCEEDED, TrialStatus.REPLAYED}:
            if (trial.factor_values_id is None or trial.parquet_sha256 is None or trial.metrics is None or
                    trial.error_code is not None):
                raise OptimizationArtifactError("Successful Trial payload is incomplete or contradictory")
            validation = validate_values(snapshot_root, factor_values_root, trial.factor_values_id)
            values_manifest = json.loads((Path(factor_values_root) / trial.factor_values_id / "manifest.json").read_text())
            if (values_manifest["factor_template_id"] != study.template_id or
                    values_manifest["factor_instance_id"] != trial.factor_instance_id or
                    values_manifest["dataset_snapshot_id"] != study.snapshot_id or
                    values_manifest["bound_parameters"] != trial.parameters or
                    values_manifest["parquet_sha256"] != trial.parquet_sha256):
                raise OptimizationArtifactError("Trial Factor Values lineage mismatch")
            recomputed = compute_mechanical_metrics(Path(factor_values_root) / trial.factor_values_id, trial.metrics.warmup_periods)
            if recomputed != trial.metrics: raise OptimizationArtifactError("Trial mechanical metrics mismatch")
            eligible, reasons = evaluate_eligibility(trial.status.value, trial.metrics, study.spec.quality_gate, validation["status"] == "valid")
            if eligible != trial.eligible_for_validation or reasons != trial.ineligibility_reasons:
                raise OptimizationArtifactError("Trial eligibility mismatch")
        elif (trial.factor_values_id is not None or trial.parquet_sha256 is not None or trial.metrics is not None or
              trial.eligible_for_validation):
            raise OptimizationArtifactError("Unsuccessful Trial carries successful execution evidence")
        trials.append(trial)
    order = validation_candidate_order(trials)
    status = StudyStatus(manifest["status"])
    if status is not _study_status(trials):
        raise OptimizationArtifactError("Study status does not match Trial outcomes")
    stable = stable_manifest_payload(study, trials, status, order)
    stable_hash = hash_payload(stable)
    expected_result = result_id(study.study_id, stable["trial_result_summaries"], order, stable_hash)
    for key, value in stable.items():
        if key != "trial_result_summaries" and manifest.get(key) != value:
            raise OptimizationArtifactError("Study manifest stable summary mismatch")
    expected_search = {name: dict(space.source) for name, space in sorted(study.spec.search_spaces.items())}
    expected_budget = {"max_trials": study.spec.budget.max_trials,
                       "max_failed_trials": study.spec.budget.max_failed_trials,
                       "stop_on_first_error": study.spec.budget.stop_on_first_error}
    if manifest.get("search_space") != expected_search or manifest.get("budget") != expected_budget:
        raise OptimizationArtifactError("Study search space or budget mismatch")
    if order != tuple(manifest["validation_candidate_order"]) or stable_hash != manifest["study_manifest_hash"] or expected_result != manifest["result_id"]:
        raise OptimizationArtifactError("Study ordering or result identity mismatch")
    expected_counts = {key: stable[key] for key in ("trial_count", "succeeded_count", "replayed_count", "failed_count", "not_run_count", "eligible_count")}
    if (summary.get("result_id") != expected_result or summary.get("study_manifest_hash") != stable_hash or
            summary.get("validation_candidate_order") != list(order) or summary.get("counts") != expected_counts or
            summary.get("predictive_claim") is not False):
        raise OptimizationArtifactError("Study summary mismatch")
    return FactorOptimizationResult(study.study_id, expected_result, status, tuple(trials), order,
                                    stable_hash, str(path), True)
