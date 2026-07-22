from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore

from .artifact import publish_artifact, validate_artifact
from .models import GovernedSelection, OptimizationEvidenceClass, OptimizationGovernanceError
from .policies import COMBINED_POLICY, FACTOR_POLICY, STRATEGY_POLICY


TASK_ID = "QM2-R1-006"
SOURCE_ABLATION_TASK = "QM2-R1-005"
SOURCE_CORRECTION_TASK = "QM2-R1-005F"
SOURCE_ASSESSMENT_ID = "poa1_15e9398eae7eb3dfadedf7391a8bb597e563050897f8adeaac5ca1f906c69f1a"
ALLOWED_MODES = ("default_first", "local_only", "full_search_diagnostic")
REQUIRED_CANDIDATE_METADATA = (
    "factor_optimization_policy_id", "strategy_optimization_policy_id",
    "combined_optimization_policy_id", "factor_optimization_mode",
    "strategy_optimization_mode", "factor_trial_count", "strategy_trial_count",
    "default_factor_passed", "default_strategy_passed", "optimization_rescued",
    "strategy_optimization_rescued", "full_search_diagnostic_used",
)


def require_agent_defaults(default_parameters: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(default_parameters, Mapping) or not default_parameters:
        raise OptimizationGovernanceError("AGENT_DEFAULT_PARAMETERS_MISSING")
    if any(not isinstance(name, str) or not name or value is None
           for name, value in default_parameters.items()):
        raise OptimizationGovernanceError("AGENT_DEFAULT_PARAMETERS_MISSING")
    return dict(default_parameters)


def local_factor_neighborhood(default_parameters: Mapping[str, Any] | None,
                              legal_values: Mapping[str, Sequence[Any]]) -> tuple[dict[str, Any], ...]:
    defaults = require_agent_defaults(default_parameters)
    if set(defaults) != set(legal_values):
        raise OptimizationGovernanceError("FACTOR_PARAMETER_DOMAIN_MISMATCH")
    rows: list[dict[str, Any]] = [defaults]
    for name in defaults:
        values = list(legal_values[name])
        if defaults[name] not in values:
            raise OptimizationGovernanceError("FACTOR_DEFAULT_PARAMETER_OUTSIDE_DOMAIN", name)
        index = values.index(defaults[name])
        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(values):
                rows.append({**defaults, name: values[neighbor]})
    unique: list[dict[str, Any]] = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    return tuple(unique[:FACTOR_POLICY.max_trials_per_template])


def _select_local(defaults: dict[str, Any], default_metrics: Mapping[str, Any],
                  failure_reasons: Iterable[str], local_trials: Sequence[Mapping[str, Any]],
                  neighborhood: Sequence[Mapping[str, Any]], *, strategy: bool) -> GovernedSelection:
    allowed = [dict(row) for row in neighborhood]
    supplied = [dict(row) for row in local_trials]
    for trial in supplied:
        parameters = trial.get("parameters")
        if not isinstance(parameters, dict) or parameters not in allowed:
            raise OptimizationGovernanceError("LOCAL_OPTIMIZATION_OUTSIDE_ONE_HOP_NEIGHBORHOOD")
    passing = [row for row in supplied if row.get("passed") is True]
    selected = passing[0] if passing else None
    chosen = dict(selected["parameters"]) if selected else defaults
    reason = ("strategy_local_optimization_rescued" if strategy else "local_optimization_rescued") \
        if selected else "local_optimization_did_not_rescue"
    return GovernedSelection(
        selected_parameters=chosen,
        selection_reason=reason,
        evidence_class=OptimizationEvidenceClass.LOCAL_OPTIMIZATION_RESEARCH.value,
        default_passed=False,
        optimization_rescued=selected is not None,
        trial_count=1 + len(supplied),
        optimization_calls=len(supplied),
        default_metrics=dict(default_metrics),
        default_failure_reasons=tuple(failure_reasons),
        local_trials=tuple(supplied),
        research_gain=dict(selected.get("research_gain", {})) if selected else None,
        parameter_neighborhood=tuple(allowed),
        usable_for_candidate_selection=True,
        usable_for_promotion=False,
    )


def evaluate_factor(*, agent_default_parameters: Mapping[str, Any] | None,
                    legal_values: Mapping[str, Sequence[Any]], default_passed: bool,
                    default_metrics: Mapping[str, Any], default_failure_reasons: Iterable[str] = (),
                    local_trials: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    defaults = require_agent_defaults(agent_default_parameters)
    neighborhood = local_factor_neighborhood(defaults, legal_values)
    if default_passed:
        if local_trials:
            raise OptimizationGovernanceError("DEFAULT_PARAMETERS_PASSED_SEARCH_FORBIDDEN")
        result = GovernedSelection(
            defaults, "default_parameters_passed", OptimizationEvidenceClass.DEFAULT_PARAMETERS.value,
            True, False, 1, 0, dict(default_metrics), (), (), None, neighborhood, True, False,
        )
    else:
        if len(local_trials) > FACTOR_POLICY.max_trials_per_template - 1:
            raise OptimizationGovernanceError("FACTOR_LOCAL_TRIAL_BUDGET_EXCEEDED")
        result = _select_local(defaults, default_metrics, default_failure_reasons,
                               local_trials, neighborhood, strategy=False)
    value = result.to_dict()
    value["optimization_rescued"] = result.optimization_rescued
    value["local_search_trial_count"] = len(result.local_trials)
    return value


def evaluate_strategy(*, default_passed: bool, default_metrics: Mapping[str, Any],
                      default_failure_reasons: Iterable[str] = (),
                      local_trials: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    defaults = STRATEGY_POLICY.default_parameters
    neighborhood = STRATEGY_POLICY.local_neighborhood
    if default_passed:
        if local_trials:
            raise OptimizationGovernanceError("DEFAULT_STRATEGY_PASSED_SEARCH_FORBIDDEN")
        result = GovernedSelection(
            defaults, "default_strategy_passed", OptimizationEvidenceClass.DEFAULT_PARAMETERS.value,
            True, False, 1, 0, dict(default_metrics), (), (), None, neighborhood, True, False,
        )
    else:
        if len(local_trials) > 6:
            raise OptimizationGovernanceError("STRATEGY_LOCAL_TRIAL_BUDGET_EXCEEDED")
        result = _select_local(defaults, default_metrics, default_failure_reasons,
                               local_trials, neighborhood, strategy=True)
    value = result.to_dict()
    value["strategy_optimization_rescued"] = result.optimization_rescued
    value["default_strategy_metrics"] = value.pop("default_metrics")
    value["selected_strategy_parameters"] = value.pop("selected_parameters")
    value["local_strategy_trials"] = value.pop("local_trials")
    selected = next((trial for trial in result.local_trials if trial.get("passed") is True), None)
    value["turnover_change"] = selected.get("turnover_change") if selected else None
    value["cost_change"] = selected.get("cost_change") if selected else None
    return value


def _validate_modes(factor_mode: str, strategy_mode: str,
                    allow_full_factor_search_diagnostic: bool,
                    allow_full_strategy_search_diagnostic: bool) -> None:
    if factor_mode not in ALLOWED_MODES or strategy_mode not in ALLOWED_MODES:
        raise OptimizationGovernanceError("OPTIMIZATION_MODE_INVALID")
    if factor_mode != "default_first" and strategy_mode != "default_first":
        raise OptimizationGovernanceError(COMBINED_POLICY.violation_error)
    if factor_mode == "full_search_diagnostic" and not allow_full_factor_search_diagnostic:
        raise OptimizationGovernanceError("FULL_FACTOR_SEARCH_DIAGNOSTIC_NOT_ALLOWED")
    if strategy_mode == "full_search_diagnostic" and not allow_full_strategy_search_diagnostic:
        raise OptimizationGovernanceError("FULL_STRATEGY_SEARCH_DIAGNOSTIC_NOT_ALLOWED")


def plan_governance(*, factor_mode: str = "default_first", strategy_mode: str = "default_first",
                    factor_optimizable_parameter_count: int = 1,
                    allow_full_factor_search_diagnostic: bool = False,
                    allow_full_strategy_search_diagnostic: bool = False,
                    default_factor_failed: bool = False,
                    default_strategy_failed: bool = False) -> dict[str, Any]:
    _validate_modes(factor_mode, strategy_mode, allow_full_factor_search_diagnostic,
                    allow_full_strategy_search_diagnostic)
    if factor_optimizable_parameter_count < 0:
        raise OptimizationGovernanceError("FACTOR_PARAMETER_COUNT_INVALID")
    local_factor_budget = min(7, 1 + 2 * factor_optimizable_parameter_count)
    factor_local = factor_mode == "local_only" or (factor_mode == "default_first" and default_factor_failed)
    strategy_local = strategy_mode == "local_only" or (
        strategy_mode == "default_first" and default_strategy_failed and not default_factor_failed
    )
    return {
        "schema_version": "optimization-governance-plan-v1",
        "task_id": TASK_ID,
        "factor_optimization_mode": factor_mode,
        "strategy_optimization_mode": strategy_mode,
        "default_factor_trial_planned": True,
        "local_factor_trials_planned": local_factor_budget if factor_local else 0,
        "full_factor_trials_planned": "diagnostic_only" if factor_mode == "full_search_diagnostic" else 0,
        "default_strategy_trial_planned": True,
        "local_strategy_trials_planned": 7 if strategy_local else 0,
        "full_strategy_trials_planned": 24 if strategy_mode == "full_search_diagnostic" else 0,
        "combined_optimization_allowed": False,
        "both_defaults_fail_resolution": (
            "factor_local_with_default_strategy_then_stop"
            if default_factor_failed and default_strategy_failed else None
        ),
        "full_search_usable_for_candidate_selection": False,
        "full_search_usable_for_promotion": False,
        "agent_calls": 0,
        "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "qlib_calls": 0,
        "network_calls": 0,
        "promotion_writes": 0,
    }


def validate_combination(*, factor_parameters_changed_from_default: bool,
                         strategy_parameters_changed_from_default: bool,
                         default_factor_failed: bool = False,
                         default_strategy_failed: bool = False) -> str:
    if factor_parameters_changed_from_default and strategy_parameters_changed_from_default:
        raise OptimizationGovernanceError(COMBINED_POLICY.violation_error)
    if factor_parameters_changed_from_default and not default_factor_failed:
        raise OptimizationGovernanceError("LOCAL_FACTOR_SEARCH_REQUIRES_DEFAULT_FAILURE")
    if strategy_parameters_changed_from_default and (not default_strategy_failed or default_factor_failed):
        raise OptimizationGovernanceError("LOCAL_STRATEGY_SEARCH_NOT_ALLOWED")
    if factor_parameters_changed_from_default:
        return "F1S0"
    if strategy_parameters_changed_from_default:
        return "F0S1"
    return "F0S0"


def build_search_budget(*, number_of_templates_considered: int, factor_trial_count: int,
                        strategy_trial_count: int, failed_factor_trials: int = 0,
                        failed_strategy_trials: int = 0) -> dict[str, int]:
    values = (number_of_templates_considered, factor_trial_count, strategy_trial_count,
              failed_factor_trials, failed_strategy_trials)
    if any(not isinstance(value, int) or value < 0 for value in values):
        raise OptimizationGovernanceError("SEARCH_BUDGET_INVALID")
    return {
        "number_of_templates_considered": number_of_templates_considered,
        "factor_trial_count": factor_trial_count,
        "strategy_trial_count": strategy_trial_count,
        "total_selection_count": factor_trial_count + strategy_trial_count,
        "effective_search_count": (factor_trial_count + strategy_trial_count
                                   + failed_factor_trials + failed_strategy_trials),
    }


def build_candidate_metadata(*, factor_mode: str, strategy_mode: str,
                             factor_trial_count: int, strategy_trial_count: int,
                             default_factor_passed: bool, default_strategy_passed: bool,
                             optimization_rescued: bool = False,
                             strategy_optimization_rescued: bool = False,
                             full_search_diagnostic_used: bool = False) -> dict[str, Any]:
    _validate_modes(factor_mode, strategy_mode, full_search_diagnostic_used,
                    full_search_diagnostic_used)
    value = {
        "factor_optimization_policy_id": FACTOR_POLICY.policy_id,
        "strategy_optimization_policy_id": STRATEGY_POLICY.policy_id,
        "combined_optimization_policy_id": COMBINED_POLICY.policy_id,
        "factor_optimization_mode": factor_mode,
        "strategy_optimization_mode": strategy_mode,
        "factor_trial_count": factor_trial_count,
        "strategy_trial_count": strategy_trial_count,
        "default_factor_passed": default_factor_passed,
        "default_strategy_passed": default_strategy_passed,
        "optimization_rescued": optimization_rescued,
        "strategy_optimization_rescued": strategy_optimization_rescued,
        "full_search_diagnostic_used": full_search_diagnostic_used,
    }
    return validate_candidate_lock_metadata(value)


def validate_candidate_lock_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    missing = [name for name in REQUIRED_CANDIDATE_METADATA if name not in metadata]
    if missing:
        raise OptimizationGovernanceError("CANDIDATE_OPTIMIZATION_METADATA_MISSING", ",".join(missing))
    if metadata.get("full_search_diagnostic_used"):
        raise OptimizationGovernanceError("FULL_SEARCH_DIAGNOSTIC_CANDIDATE_LOCK_FORBIDDEN")
    if metadata.get("promotion_candidate") or metadata.get("approved") or metadata.get("active") \
            or metadata.get("production"):
        raise OptimizationGovernanceError("OPTIMIZATION_GOVERNANCE_PROMOTION_FORBIDDEN")
    return dict(metadata)


def _identity(role: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "optimization-governance-v1",
        "task_id": TASK_ID,
        "artifact_role": role,
        "payload": dict(payload),
        "agent_calls": 0,
        "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "qlib_calls": 0,
        "network_calls": 0,
        "promotion_writes": 0,
        "predictive_claim": False,
        "usable_for_promotion": False,
    }


def _store(store_root: Path | None) -> FileSystemResearchArtifactStore:
    store = FileSystemResearchArtifactStore(resolve_config(store_root))
    store.validate_format()
    return store


def _find_decision(store: FileSystemResearchArtifactStore, root: Path):
    found = []
    for index, descriptor in enumerate(store.list_by_kind("optimization_governance_decision")):
        destination = root / str(index)
        store.materialize_artifact(descriptor.descriptor_id, destination)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("identity", {}).get("task_id") == TASK_ID:
            found.append(descriptor)
    if len(found) > 1:
        raise RuntimeError("multiple canonical optimization governance decisions")
    return found[0] if found else None


def _cold(store: FileSystemResearchArtifactStore, artifact_id: str, destination: Path) -> dict[str, Any]:
    descriptor = store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"optimization governance artifact missing: {artifact_id}")
    if destination.exists():
        shutil.rmtree(destination)
    store.materialize_artifact(descriptor.descriptor_id, destination)
    return validate_artifact(destination, artifact_id, descriptor.artifact_kind)


def execute_governance(*, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    work_root = Path(work_root)
    store = _store(store_root)
    if _find_decision(store, work_root / "lookup"):
        return replay_governance(work_root=work_root / "replay", store_root=store_root) | {"exact_existing": True}
    policies = (
        ("factor_optimization_policy", FACTOR_POLICY.to_dict()),
        ("strategy_optimization_policy", STRATEGY_POLICY.to_dict()),
        ("combined_optimization_policy", COMBINED_POLICY.to_dict()),
    )
    receipts, artifacts = [], []
    for kind, payload in policies:
        artifact = publish_artifact(work_root / "domain", kind, _identity(kind, payload), {"policy.json": payload})
        receipt = store.import_artifact(kind, Path(artifact["path"]), artifact["artifact_id"], lineage=())
        receipts.append({"artifact_id": artifact["artifact_id"], "descriptor_id": receipt.descriptor_id,
                         "new_blob_count": receipt.new_blob_count, "exact_existing": receipt.exact_existing})
        artifacts.append(artifact)
        _cold(store, artifact["artifact_id"], work_root / "cold" / artifact["artifact_id"])
    decision = {
        "schema_version": "optimization-governance-decision-v1",
        "source_ablation_task": SOURCE_ABLATION_TASK,
        "source_correction_task": SOURCE_CORRECTION_TASK,
        "source_ablation_assessment_id": SOURCE_ASSESSMENT_ID,
        "factor_decision": "default_first_optimize_only_on_failure",
        "strategy_decision": "default_first_optimize_only_on_failure",
        "combined_decision": "suspend_parameter_optimization",
        "factor_policy_id": artifacts[0]["artifact_id"],
        "strategy_policy_id": artifacts[1]["artifact_id"],
        "combined_policy_id": artifacts[2]["artifact_id"],
        "auto_applied": True,
        "effective_from_task": TASK_ID,
        "historical_artifacts_mutated": False,
        "candidate_status_mutated": False,
    }
    artifact = publish_artifact(work_root / "domain", "optimization_governance_decision",
        _identity("optimization_governance_decision", decision), {"decision.json": decision})
    lineage = tuple(item["artifact_id"] for item in artifacts)
    receipt = store.import_artifact(artifact["artifact_kind"], Path(artifact["path"]),
                                    artifact["artifact_id"], lineage=lineage)
    receipts.append({"artifact_id": artifact["artifact_id"], "descriptor_id": receipt.descriptor_id,
                     "new_blob_count": receipt.new_blob_count, "exact_existing": receipt.exact_existing})
    artifacts.append(artifact)
    _cold(store, artifact["artifact_id"], work_root / "cold" / artifact["artifact_id"])
    inventory = publish_inventory(store)
    integrity = scan_store_integrity(store)
    return {
        "status": "completed",
        "artifact_ids": [item["artifact_id"] for item in artifacts],
        "decision_id": artifact["artifact_id"],
        "receipts": receipts,
        "inventory_id": inventory.inventory_id,
        "store_integrity": integrity.status,
        "missing": len(integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs),
        "agent_calls": 0, "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0, "qlib_calls": 0,
        "network_calls": 0, "promotion_writes": 0,
    }


def replay_governance(*, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    work_root = Path(work_root)
    store = _store(store_root)
    decision = _find_decision(store, work_root / "lookup")
    if decision is None:
        raise RuntimeError("optimization governance decision not found")
    artifact_ids = [*decision.lineage, decision.artifact_id]
    recovered = [_cold(store, artifact_id, work_root / "cold" / artifact_id)
                 for artifact_id in artifact_ids]
    integrity = scan_store_integrity(store)
    return {
        "status": "valid", "decision_id": decision.artifact_id,
        "recovered_artifact_count": len(recovered), "artifact_ids": artifact_ids,
        "agent_calls": 0, "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0, "qlib_calls": 0,
        "network_calls": 0, "promotion_writes": 0,
        "new_artifacts": 0, "new_blobs": 0,
        "store_integrity": integrity.status,
        "missing": len(integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs),
    }
