import json
from pathlib import Path

from backend.services.engine.factor_dsl import compile_template, execute_compiled, validate_values

from .artifact import publish_study, validate_study
from .eligibility import evaluate_eligibility, validation_candidate_order
from .enums import StudyStatus, TrialStatus
from .errors import OptimizationArtifactError
from .metrics import compute_mechanical_metrics
from .models import FactorOptimizationResult, FactorOptimizationTrial


def _safe_error_code(exc):
    name = type(exc).__name__.upper()
    return "TRIAL_" + "".join(char if char.isalnum() else "_" for char in name)[:80]


def execute_study(study, snapshot_contract, snapshot_root, factor_values_root, optimization_root):
    target = Path(optimization_root) / study.study_id
    if target.exists():
        return validate_study(study, snapshot_root, factor_values_root, optimization_root)
    trials = []
    failures = 0
    stopped = False
    for planned in study.trials:
        if stopped:
            trials.append(FactorOptimizationTrial(planned.trial_id, planned.ordinal, planned.parameters,
                                                  planned.factor_instance_id, TrialStatus.NOT_RUN, None, None, None,
                                                  False, ("failure_budget_stop",), None))
            continue
        try:
            compiled = compile_template(study.spec.template, snapshot_contract, planned.parameters)
            execution = execute_compiled(compiled, snapshot_root, factor_values_root)
            validation = validate_values(snapshot_root, factor_values_root, execution.factor_values_id)
            values_path = Path(factor_values_root) / execution.factor_values_id
            values_manifest = json.loads((values_path / "manifest.json").read_text())
            quality = validation["quality"]
            metrics = compute_mechanical_metrics(values_path, quality["warmup_periods"])
            status = TrialStatus.REPLAYED if execution.replayed else TrialStatus.SUCCEEDED
            eligible, reasons = evaluate_eligibility(status.value, metrics, study.spec.quality_gate, True)
            trials.append(FactorOptimizationTrial(planned.trial_id, planned.ordinal, planned.parameters,
                                                  compiled.factor_instance_id, status, execution.factor_values_id,
                                                  values_manifest["parquet_sha256"], metrics, eligible, reasons, None))
        except Exception as exc:
            failures += 1
            trials.append(FactorOptimizationTrial(planned.trial_id, planned.ordinal, planned.parameters,
                                                  planned.factor_instance_id, TrialStatus.FAILED, None, None, None,
                                                  False, ("execution_failed",), _safe_error_code(exc)))
            stopped = study.spec.budget.stop_on_first_error or failures > study.spec.budget.max_failed_trials
    success_count = sum(t.status in {TrialStatus.SUCCEEDED, TrialStatus.REPLAYED} for t in trials)
    if success_count == 0: status = StudyStatus.FAILED
    elif any(t.status in {TrialStatus.FAILED, TrialStatus.NOT_RUN} for t in trials): status = StudyStatus.PARTIAL
    else: status = StudyStatus.SUCCEEDED
    order = validation_candidate_order(trials)
    rid, manifest_hash, artifact_path = publish_study(study, trials, status, order, optimization_root)
    result = FactorOptimizationResult(study.study_id, rid, status, tuple(trials), order, manifest_hash,
                                      str(artifact_path), False)
    validated = validate_study(study, snapshot_root, factor_values_root, optimization_root)
    return FactorOptimizationResult(result.study_id, result.result_id, result.status, result.trials,
                                    result.validation_candidate_order, result.study_manifest_hash,
                                    result.artifact_path, False)
