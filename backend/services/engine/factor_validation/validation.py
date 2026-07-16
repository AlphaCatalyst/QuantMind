import json
import os
import shutil
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.services.engine.factor_dsl import execute_compiled
from backend.services.engine.factor_dsl.admission import snapshot_contract
from backend.services.engine.factor_dsl.compiler import compile_template
from backend.services.engine.factor_optimization import parse_optimization_spec, plan_study, validate_study

from .canonical import hash_payload, sha256_file, write_json
from .dataset import load_validation_labels, validate_validation_dataset
from .errors import ValidationArtifactError, ValidationSpecError
from .metrics import calculate_split_metrics, metrics_payload, selection_eligibility, train_orientation
from .models import ValidationTrialResult
from .parser import spec_payload


VALIDATION_ENGINE_VERSION = "factor-validation-engine-v1"


def load_optimization_lineage(study_ids, optimization_root, original_snapshot_root, original_values_root):
    contract = snapshot_contract(original_snapshot_root, "ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7")
    studies = []
    for study_id in study_ids:
        raw = json.loads((Path(optimization_root) / study_id / "spec.json").read_text())
        study = plan_study(parse_optimization_spec(raw), contract)
        if study.study_id != study_id: raise ValidationSpecError("Study ID does not match immutable spec")
        result = validate_study(study, original_snapshot_root, original_values_root, optimization_root)
        studies.append((study, result))
    return studies


def validate_spec_lineage(spec, dataset_root, optimization_root, original_snapshot_root, original_values_root):
    dataset = validate_validation_dataset(dataset_root, spec.validation_dataset_id)
    studies = load_optimization_lineage(spec.optimization_study_ids, optimization_root, original_snapshot_root, original_values_root)
    trials = [trial for study, _ in studies for trial in study.trials]
    if tuple(trial.trial_id for trial in trials) != spec.trial_ids:
        raise ValidationSpecError("Validation Spec must contain all 14 Study trials in immutable order")
    return {"status": "valid", "dataset": dataset, "studies": studies, "trials": trials}


def _metrics_for_dates(values, labels, start, end, orientation=1):
    subset = labels[(labels.trade_date >= start) & (labels.trade_date <= end)]
    return calculate_split_metrics(values, subset, orientation=orientation)


def _trial_payload(result):
    payload = dict(result.__dict__)
    for name in ("train_raw_metrics", "train_oriented_metrics", "validation_raw_metrics", "validation_oriented_metrics"):
        value = payload[name]; payload[name] = metrics_payload(value) if value is not None else None
    payload["parameters"] = dict(payload["parameters"]); payload["ineligibility_reasons"] = list(payload["ineligibility_reasons"])
    return payload


def _ordering(trials):
    eligible = [item for item in trials if item.eligible_for_selection]
    def key(item):
        metrics = item.validation_oriented_metrics
        return (-metrics.mean_rank_ic, -(metrics.rank_icir if metrics.rank_icir is not None else float("-inf")),
                -(metrics.mean_ic if metrics.mean_ic is not None else float("-inf")), -metrics.factor_finite_coverage, item.trial_id)
    return sorted(eligible, key=key)


def evaluate_validation(spec, *, dataset_root, snapshot_root, factor_values_root, validation_root,
                        optimization_root, original_snapshot_root, original_values_root):
    lineage = validate_spec_lineage(spec, dataset_root, optimization_root, original_snapshot_root, original_values_root)
    manifest = lineage["dataset"]["manifest"]
    contract = snapshot_contract(snapshot_root, manifest["feature_snapshot_id"])
    labels = load_validation_labels(dataset_root, spec.validation_dataset_id)
    labels["trade_date"] = pd.to_datetime(labels["trade_date"])
    split = manifest["splits"]
    results = []
    for study, _ in lineage["studies"]:
        for planned in study.trials:
            compiled = compile_template(study.spec.template, contract, planned.parameters)
            execution = execute_compiled(compiled, snapshot_root, factor_values_root)
            values = pd.read_parquet(Path(factor_values_root) / execution.factor_values_id / "values.parquet")
            train_raw = _metrics_for_dates(values, labels, split["train"]["effective_start"], split["train"]["effective_end"])
            orientation = train_orientation(train_raw)
            if orientation is None:
                train_oriented = valid_raw = valid_oriented = None
                eligible, reasons = False, ("train_orientation_unavailable",)
            else:
                train_oriented = _metrics_for_dates(values, labels, split["train"]["effective_start"], split["train"]["effective_end"], orientation)
                valid_raw = _metrics_for_dates(values, labels, split["validation"]["effective_start"], split["validation"]["effective_end"])
                valid_oriented = _metrics_for_dates(values, labels, split["validation"]["effective_start"], split["validation"]["effective_end"], orientation)
                eligible, reasons = selection_eligibility(train_oriented, valid_oriented, spec.minimum_requirements)
            results.append(ValidationTrialResult(study.study_id, planned.trial_id, study.template_id, planned.parameters,
                           compiled.factor_instance_id, execution.factor_values_id, execution.manifest["parquet_sha256"],
                           orientation, "train_mean_rank_ic", train_raw, train_oriented, valid_raw, valid_oriented,
                           eligible, reasons, None, False))
    ordered = _ordering(results)
    ranks = {item.trial_id: index + 1 for index, item in enumerate(ordered)}
    selected_ids = tuple(item.trial_id for item in ordered[:spec.candidate_selection["top_k"]])
    results = [replace(item, validation_rank=ranks.get(item.trial_id), selected_for_frozen=item.trial_id in selected_ids) for item in results]
    ordered = _ordering(results)
    stable = {"schema_version": "factor-validation-result-v1", "engine_version": VALIDATION_ENGINE_VERSION,
              "spec": spec_payload(spec), "validation_dataset_id": spec.validation_dataset_id,
              "feature_snapshot_id": manifest["feature_snapshot_id"], "trial_results": [_trial_payload(x) for x in results],
              "candidate_order": [x.trial_id for x in ordered], "selected_trial_ids": list(selected_ids),
              "development_diagnostic_used": False, "frozen_labels_accessed": False}
    result_id = "fvr_" + hash_payload(stable)
    selection_stable = {"schema_version": "factor-validation-selection-v1", "validation_result_id": result_id,
                        "validation_dataset_id": spec.validation_dataset_id, "selection_rule": "validation_predictive_order_v1",
                        "top_k": spec.candidate_selection["top_k"], "eligible_trial_ids": [x.trial_id for x in ordered],
                        "selected_trial_ids": list(selected_ids),
                        "candidates": [{"trial_id": x.trial_id, "factor_instance_id": x.factor_instance_id,
                                        "factor_values_id": x.factor_values_id, "orientation": x.orientation,
                                        "validation_rank": x.validation_rank} for x in ordered[:spec.candidate_selection["top_k"]]]}
    selection_id = "fvs_" + hash_payload(selection_stable)
    selection_stable["candidate_selection_id"] = selection_id
    target = Path(validation_root) / "results" / result_id
    selection_target = Path(validation_root) / "selections" / selection_id
    if target.exists():
        existing = json.loads((target / "manifest.json").read_text())
        return validate_validation_result(validation_root, result_id, existing["candidate_selection_id"])
    if selection_target.exists():
        raise ValidationArtifactError("Candidate Selection exists without its immutable Validation Result")
    staging = Path(validation_root) / "results" / f".{result_id}.staging-{uuid.uuid4().hex}"
    select_staging = Path(validation_root) / "selections" / f".{selection_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True); select_staging.mkdir(parents=True)
    try:
        write_json(staging / "spec.json", spec_payload(spec)); (staging / "trials").mkdir()
        for item in results: write_json(staging / "trials" / f"{item.trial_id}.json", _trial_payload(item))
        write_json(staging / "candidate_selection.json", selection_stable)
        file_hashes = {str(p.relative_to(staging)): sha256_file(p) for p in sorted(staging.rglob("*.json"))}
        write_json(staging / "manifest.json", {**stable, "validation_result_id": result_id,
                                               "candidate_selection_id": selection_id, "created_at": datetime.now(timezone.utc).isoformat(),
                                               "file_hashes": file_hashes})
        write_json(select_staging / "spec.json", spec_payload(spec)); write_json(select_staging / "selection.json", selection_stable)
        sel_hashes = {str(p.relative_to(select_staging)): sha256_file(p) for p in sorted(select_staging.glob("*.json"))}
        write_json(select_staging / "manifest.json", {**selection_stable, "created_at": datetime.now(timezone.utc).isoformat(), "file_hashes": sel_hashes})
        target.parent.mkdir(parents=True, exist_ok=True); selection_target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target); os.replace(select_staging, selection_target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
        if select_staging.exists(): shutil.rmtree(select_staging)
    return validate_validation_result(validation_root, result_id, selection_id)


def validate_validation_result(validation_root, result_id, selection_id):
    root, selection = Path(validation_root) / "results" / result_id, Path(validation_root) / "selections" / selection_id
    manifest = json.loads((root / "manifest.json").read_text()); selection_manifest = json.loads((selection / "manifest.json").read_text())
    if manifest["validation_result_id"] != result_id or manifest["candidate_selection_id"] != selection_id:
        raise ValidationArtifactError("validation result identity mismatch")
    for relative, digest in manifest["file_hashes"].items():
        if sha256_file(root / relative) != digest: raise ValidationArtifactError("validation result hash mismatch")
    for relative, digest in selection_manifest["file_hashes"].items():
        if sha256_file(selection / relative) != digest: raise ValidationArtifactError("candidate selection hash mismatch")
    stable = {key: manifest[key] for key in ("schema_version", "engine_version", "spec", "validation_dataset_id",
              "feature_snapshot_id", "trial_results", "candidate_order", "selected_trial_ids",
              "development_diagnostic_used", "frozen_labels_accessed")}
    if result_id != "fvr_" + hash_payload(stable):
        raise ValidationArtifactError("validation result content identity mismatch")
    selection_payload = json.loads((selection / "selection.json").read_text())
    selection_stable = {key: selection_payload[key] for key in ("schema_version", "validation_result_id",
                        "validation_dataset_id", "selection_rule", "top_k", "eligible_trial_ids",
                        "selected_trial_ids", "candidates")}
    if selection_id != "fvs_" + hash_payload(selection_stable) or selection_manifest.get("candidate_selection_id") != selection_id:
        raise ValidationArtifactError("Candidate Selection content identity mismatch")
    return {"status": "valid", "validation_result_id": result_id, "candidate_selection_id": selection_id,
            "result_path": str(root), "selection_path": str(selection), "manifest": manifest,
            "selection": selection_payload}
