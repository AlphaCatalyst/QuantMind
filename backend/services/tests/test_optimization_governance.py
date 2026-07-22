from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.optimization_governance.artifact import ARTIFACT_FILES, validate_artifact
from backend.services.engine.optimization_governance.engine import (
    SOURCE_ABLATION_TASK, SOURCE_ASSESSMENT_ID, SOURCE_CORRECTION_TASK,
    build_candidate_metadata, build_search_budget, evaluate_factor, evaluate_strategy,
    execute_governance, local_factor_neighborhood, plan_governance, replay_governance,
    require_agent_defaults, validate_candidate_lock_metadata, validate_combination,
)
from backend.services.engine.optimization_governance.models import (
    EVIDENCE_RISK_ORDER, OptimizationEvidenceClass, OptimizationGovernanceError,
)
from backend.services.engine.optimization_governance.policies import (
    COMBINED_POLICY, FACTOR_POLICY, STRATEGY_POLICY,
)


def _error(code: str):
    return pytest.raises(OptimizationGovernanceError, match=code)


def _factor(passed: bool, trials=()):
    return evaluate_factor(agent_default_parameters={"window": 20},
        legal_values={"window": [10, 20, 40]}, default_passed=passed,
        default_metrics={"rankic": 0.02}, default_failure_reasons=("rankic",),
        local_trials=trials)


def _trial(parameters, passed=True):
    return {"parameters": parameters, "passed": passed, "research_gain": {"rankic": 0.01},
            "turnover_change": 0.1, "cost_change": 0.001}


def _store(root: Path):
    store = FileSystemResearchArtifactStore(resolve_config(root)); store.initialize(); return store


def test_agent_default_parameters_are_mandatory_and_never_inferred():
    for value in (None, {}, {"window": None}):
        with _error("AGENT_DEFAULT_PARAMETERS_MISSING"):
            require_agent_defaults(value)


def test_default_factor_is_evaluated_first_and_selected():
    result = _factor(True)
    assert result["selected_parameters"] == {"window": 20}
    assert result["selection_reason"] == "default_parameters_passed"


def test_passing_default_factor_has_one_trial_and_zero_optimization_calls():
    result = _factor(True)
    assert result["trial_count"] == 1 and result["optimization_calls"] == 0


def test_passing_default_factor_forbids_continuing_search():
    with _error("DEFAULT_PARAMETERS_PASSED_SEARCH_FORBIDDEN"):
        _factor(True, [_trial({"window": 10})])


def test_failed_default_factor_allows_one_hop_neighborhood():
    result = _factor(False, [_trial({"window": 10})])
    assert result["optimization_rescued"] is True
    assert result["selected_parameters"] == {"window": 10}


def test_factor_neighborhood_changes_one_parameter_at_a_time():
    rows = local_factor_neighborhood({"a": 2, "b": 5}, {"a": [1, 2, 3], "b": [4, 5, 6]})
    assert len(rows) == 5
    assert all(sum(row[k] != {"a": 2, "b": 5}[k] for k in row) <= 1 for row in rows)


def test_local_factor_trials_are_hard_capped_at_seven():
    rows = local_factor_neighborhood({"a": 2, "b": 5, "c": 8, "d": 11},
        {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9], "d": [10, 11, 12]})
    assert len(rows) == FACTOR_POLICY.max_trials_per_template == 7


def test_factor_trial_outside_one_hop_is_rejected():
    with _error("LOCAL_OPTIMIZATION_OUTSIDE_ONE_HOP_NEIGHBORHOOD"):
        _factor(False, [_trial({"window": 99})])


def test_factor_runtime_trial_budget_rejects_more_than_six_search_calls():
    with _error("FACTOR_LOCAL_TRIAL_BUDGET_EXCEEDED"):
        _factor(False, [_trial({"window": 10}, False) for _ in range(7)])


def test_full_factor_search_is_disabled_without_explicit_gate():
    with _error("FULL_FACTOR_SEARCH_DIAGNOSTIC_NOT_ALLOWED"):
        plan_governance(factor_mode="full_search_diagnostic")


def test_full_factor_search_is_diagnostic_only():
    result = plan_governance(factor_mode="full_search_diagnostic",
                             allow_full_factor_search_diagnostic=True)
    assert result["full_factor_trials_planned"] == "diagnostic_only"
    assert result["full_search_usable_for_candidate_selection"] is False
    assert result["full_search_usable_for_promotion"] is False


def test_default_strategy_is_canonical_and_evaluated_first():
    result = evaluate_strategy(default_passed=True, default_metrics={"sharpe": 1.0})
    assert result["selected_strategy_parameters"] == STRATEGY_POLICY.default_parameters
    assert result["trial_count"] == 1


def test_passing_default_strategy_forbids_search():
    with _error("DEFAULT_STRATEGY_PASSED_SEARCH_FORBIDDEN"):
        evaluate_strategy(default_passed=True, default_metrics={},
                          local_trials=[_trial(STRATEGY_POLICY.local_neighborhood[1])])


def test_failed_strategy_uses_exact_seven_configuration_neighborhood():
    assert len(STRATEGY_POLICY.local_neighborhood) == 7
    assert all(row["n_drop"] < row["topk"] for row in STRATEGY_POLICY.local_neighborhood)
    result = evaluate_strategy(default_passed=False, default_metrics={},
        default_failure_reasons=("gate",), local_trials=[_trial(STRATEGY_POLICY.local_neighborhood[1])])
    assert result["strategy_optimization_rescued"] is True


def test_strategy_local_trial_budget_rejects_more_than_six_search_calls():
    rows = [_trial(STRATEGY_POLICY.local_neighborhood[(i % 6) + 1], False) for i in range(7)]
    with _error("STRATEGY_LOCAL_TRIAL_BUDGET_EXCEEDED"):
        evaluate_strategy(default_passed=False, default_metrics={}, local_trials=rows)


def test_full_strategy_search_is_disabled_without_explicit_gate():
    with _error("FULL_STRATEGY_SEARCH_DIAGNOSTIC_NOT_ALLOWED"):
        plan_governance(strategy_mode="full_search_diagnostic")


def test_full_strategy_search_is_diagnostic_only():
    result = plan_governance(strategy_mode="full_search_diagnostic",
                             allow_full_strategy_search_diagnostic=True)
    assert result["full_strategy_trials_planned"] == 24
    assert result["full_search_usable_for_candidate_selection"] is False


@pytest.mark.parametrize("factor_changed,strategy_changed,factor_failed,strategy_failed,mode", [
    (False, False, False, False, "F0S0"),
    (True, False, True, False, "F1S0"),
    (False, True, False, True, "F0S1"),
])
def test_allowed_combinations(factor_changed, strategy_changed, factor_failed, strategy_failed, mode):
    assert validate_combination(factor_parameters_changed_from_default=factor_changed,
        strategy_parameters_changed_from_default=strategy_changed,
        default_factor_failed=factor_failed, default_strategy_failed=strategy_failed) == mode


@pytest.mark.parametrize("factor_mode,strategy_mode", [
    ("local_only", "local_only"),
    ("full_search_diagnostic", "full_search_diagnostic"),
])
def test_joint_search_modes_fail_during_plan(factor_mode, strategy_mode):
    with _error("COMBINED_PARAMETER_OPTIMIZATION_SUSPENDED"):
        plan_governance(factor_mode=factor_mode, strategy_mode=strategy_mode,
            allow_full_factor_search_diagnostic=True, allow_full_strategy_search_diagnostic=True)


def test_joint_changed_parameters_hard_fail():
    with _error("COMBINED_PARAMETER_OPTIMIZATION_SUSPENDED"):
        validate_combination(factor_parameters_changed_from_default=True,
            strategy_parameters_changed_from_default=True,
            default_factor_failed=True, default_strategy_failed=True)


def test_both_default_failures_search_factor_only_then_stop():
    result = plan_governance(default_factor_failed=True, default_strategy_failed=True,
                             factor_optimizable_parameter_count=2)
    assert result["local_factor_trials_planned"] == 5
    assert result["local_strategy_trials_planned"] == 0
    assert result["both_defaults_fail_resolution"] == "factor_local_with_default_strategy_then_stop"


def test_optimization_rescue_metadata_is_complete_and_research_only():
    result = _factor(False, [_trial({"window": 40})])
    assert result["optimization_rescued"] is True
    assert result["default_failure_reasons"] == ["rankic"]
    assert result["research_gain"] == {"rankic": 0.01}
    assert result["usable_for_promotion"] is False


def test_strategy_rescue_metadata_is_complete_and_research_only():
    result = evaluate_strategy(default_passed=False, default_metrics={"sharpe": 0.0},
        default_failure_reasons=("sharpe",), local_trials=[_trial(STRATEGY_POLICY.local_neighborhood[1])])
    assert result["strategy_optimization_rescued"] is True
    assert result["default_strategy_metrics"] == {"sharpe": 0.0}
    assert result["usable_for_promotion"] is False


def test_evidence_classes_and_risk_order_are_explicit():
    assert EVIDENCE_RISK_ORDER == ("default_parameters", "local_optimization_research",
                                   "full_search_diagnostic")
    assert OptimizationEvidenceClass.HISTORICAL_LEGACY_OPTIMIZATION.value == "historical_legacy_optimization"


def test_search_budget_counts_failed_trials_in_effective_count():
    result = build_search_budget(number_of_templates_considered=2, factor_trial_count=3,
        strategy_trial_count=1, failed_factor_trials=2, failed_strategy_trials=1)
    assert result["total_selection_count"] == 4
    assert result["effective_search_count"] == 7


def test_candidate_lock_requires_all_twelve_metadata_fields():
    metadata = build_candidate_metadata(factor_mode="default_first", strategy_mode="default_first",
        factor_trial_count=1, strategy_trial_count=1, default_factor_passed=True,
        default_strategy_passed=True)
    assert len(metadata) == 12
    del metadata["factor_trial_count"]
    with _error("CANDIDATE_OPTIMIZATION_METADATA_MISSING"):
        validate_candidate_lock_metadata(metadata)


def test_diagnostic_full_search_cannot_enter_candidate_lock():
    with _error("FULL_SEARCH_DIAGNOSTIC_CANDIDATE_LOCK_FORBIDDEN"):
        build_candidate_metadata(factor_mode="full_search_diagnostic", strategy_mode="default_first",
            factor_trial_count=3, strategy_trial_count=1, default_factor_passed=False,
            default_strategy_passed=True, full_search_diagnostic_used=True)


def test_registry_metadata_cannot_claim_promotion_state():
    metadata = build_candidate_metadata(factor_mode="default_first", strategy_mode="default_first",
        factor_trial_count=1, strategy_trial_count=1, default_factor_passed=True,
        default_strategy_passed=True)
    with _error("OPTIMIZATION_GOVERNANCE_PROMOTION_FORBIDDEN"):
        validate_candidate_lock_metadata({**metadata, "production": True})


def test_planner_exposes_all_seven_required_fields_and_zero_calls():
    result = plan_governance()
    required = {"default_factor_trial_planned", "local_factor_trials_planned",
        "full_factor_trials_planned", "default_strategy_trial_planned",
        "local_strategy_trials_planned", "full_strategy_trials_planned",
        "combined_optimization_allowed"}
    assert required.issubset(result)
    assert result["default_factor_trial_planned"] and result["default_strategy_trial_planned"]
    assert not result["combined_optimization_allowed"]
    assert all(result[name] == 0 for name in ("agent_calls", "factor_optimization_calls",
        "strategy_optimization_calls", "qlib_calls", "network_calls", "promotion_writes"))


def test_source_ablation_and_correction_are_bound_without_mutating_history():
    assert SOURCE_ABLATION_TASK == "QM2-R1-005"
    assert SOURCE_CORRECTION_TASK == "QM2-R1-005F"
    assert SOURCE_ASSESSMENT_ID.startswith("poa1_")


def test_all_four_artifact_kinds_are_registered():
    assert set(ARTIFACT_FILES) == {"optimization_governance_decision", "factor_optimization_policy",
        "strategy_optimization_policy", "combined_optimization_policy"}
    assert all(ArtifactKind(kind).value == kind for kind in ARTIFACT_FILES)


def test_policy_schemas_validate_runtime_payloads(repository_root: Path = Path(__file__).parents[3]):
    schemas = repository_root / "docs/quantmind2/implementation/schemas"
    for name, payload in (
        ("factor_optimization_policy_v2.schema.json", FACTOR_POLICY.to_dict()),
        ("strategy_optimization_policy_v2.schema.json", STRATEGY_POLICY.to_dict()),
        ("combined_optimization_policy_v1.schema.json", COMBINED_POLICY.to_dict()),
    ):
        Draft202012Validator(json.loads((schemas / name).read_text())).validate(payload)


def test_artifact_store_publication_cold_recovery_and_exact_replay(tmp_path: Path):
    store_root = tmp_path / "store"; _store(store_root)
    first = execute_governance(work_root=tmp_path / "execute", store_root=store_root)
    assert first["status"] == "completed" and len(first["artifact_ids"]) == 4
    assert first["store_integrity"] == "healthy" and first["missing"] == first["unreferenced"] == 0
    for artifact_id in first["artifact_ids"]:
        descriptor = _store(store_root).find_by_artifact_id(artifact_id)
        assert descriptor is not None
        destination = tmp_path / "manual-cold" / artifact_id
        _store(store_root).materialize_artifact(descriptor.descriptor_id, destination)
        assert validate_artifact(destination, artifact_id, descriptor.artifact_kind)["status"] == "valid"
    before = scan_store_integrity(_store(store_root))
    replay = replay_governance(work_root=tmp_path / "replay", store_root=store_root)
    after = scan_store_integrity(_store(store_root))
    assert replay["recovered_artifact_count"] == 4
    assert replay["new_artifacts"] == replay["new_blobs"] == 0
    assert all(replay[name] == 0 for name in ("agent_calls", "factor_optimization_calls",
        "strategy_optimization_calls", "qlib_calls", "network_calls", "promotion_writes"))
    assert (before.artifact_count, before.blob_count) == (after.artifact_count, after.blob_count)


def test_framework_decision_artifact_auto_applies_corrected_business_decision(tmp_path: Path):
    store_root = tmp_path / "store"; store = _store(store_root)
    result = execute_governance(work_root=tmp_path / "execute", store_root=store_root)
    descriptor = store.find_by_artifact_id(result["decision_id"])
    destination = tmp_path / "decision"
    store.materialize_artifact(descriptor.descriptor_id, destination)
    decision = json.loads((destination / "decision.json").read_text())
    assert decision["source_ablation_task"] == SOURCE_ABLATION_TASK
    assert decision["source_correction_task"] == SOURCE_CORRECTION_TASK
    assert decision["factor_decision"] == decision["strategy_decision"] == "default_first_optimize_only_on_failure"
    assert decision["combined_decision"] == "suspend_parameter_optimization"
    assert decision["auto_applied"] is True
    assert decision["historical_artifacts_mutated"] is decision["candidate_status_mutated"] is False
