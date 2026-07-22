from __future__ import annotations

import json

import pytest

from backend.services.engine.default_first_momentum_search.artifact import publish_artifact, validate_artifact
from backend.services.engine.default_first_momentum_search.engine import (
    _development_gate, candidate_ordering, local_rescue_eligible,
)
from backend.services.engine.default_first_momentum_search.protocol import (
    ANNUAL_PERIODS, BUDGET, DEVELOPMENT_PERIOD, GOVERNANCE_DECISION_ID, REPORT_PERIODS,
)
from backend.services.engine.optimization_governance.engine import (
    evaluate_factor, local_factor_neighborhood, validate_combination,
)
from backend.services.engine.optimization_governance.models import OptimizationGovernanceError


def metrics(rank_ic=.01, positive=.60, coverage=.95):
    return {"mean_rank_ic": rank_ic, "rank_ic_positive_rate": positive,
            "factor_finite_coverage": coverage}


def qlib(excess=.05, turnover=20.0):
    return {"net_excess_csi300": excess, "turnover": turnover, "max_drawdown": -.10}


def test_protocol_has_frozen_development_annual_and_report_boundaries():
    assert DEVELOPMENT_PERIOD == ("2019-01-02", "2020-12-31")
    assert tuple(ANNUAL_PERIODS) == ("2021", "2022", "2023", "2024")
    assert tuple(REPORT_PERIODS) == ("2025", "2026H1")
    assert BUDGET.max_total_agent_calls == 6 and BUDGET.max_total_templates == 12
    assert BUDGET.max_local_trials_per_template == 7
    assert GOVERNANCE_DECISION_ID.startswith("ogd1_7de0")


def test_default_pass_stops_search_and_requires_explicit_agent_defaults():
    result = evaluate_factor(agent_default_parameters={"weight": .5}, legal_values={"weight": [.25, .5, .75]},
                             default_passed=True, default_metrics=metrics())
    assert result["optimization_calls"] == 0
    assert result["selected_parameters"] == {"weight": .5}
    with pytest.raises(OptimizationGovernanceError, match="AGENT_DEFAULT_PARAMETERS_MISSING"):
        evaluate_factor(agent_default_parameters={}, legal_values={}, default_passed=True, default_metrics={})


def test_near_gate_controls_local_rescue_and_data_quality_is_hard_failure():
    assert local_rescue_eligible(metrics(rank_ic=-.001), {"top_bottom_return": -.01}, infinity_count=0)
    assert not local_rescue_eligible(metrics(rank_ic=-.01, positive=.40), {"top_bottom_return": -.01}, infinity_count=0)
    assert not local_rescue_eligible(metrics(rank_ic=.01), {"top_bottom_return": .01}, infinity_count=1)


def test_local_neighborhood_is_one_hop_and_capped_by_policy():
    rows = local_factor_neighborhood({"a": 2, "b": 5}, {"a": [1, 2, 3], "b": [4, 5, 6]})
    assert len(rows) == 5
    assert all(sum(row[name] != {"a": 2, "b": 5}[name] for name in row) <= 1 for row in rows)
    rows = local_factor_neighborhood({"a": 2, "b": 5, "c": 8},
                                     {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]})
    assert len(rows) == 7


def test_full_strategy_and_combined_optimization_are_not_admitted():
    with pytest.raises(OptimizationGovernanceError, match="COMBINED"):
        validate_combination(factor_parameters_changed_from_default=True,
                             strategy_parameters_changed_from_default=True,
                             default_factor_failed=True, default_strategy_failed=True)


def test_development_gate_requires_predictive_or_excess_evidence():
    passed, failures = _development_gate(metrics(), qlib(), {"top_bottom_return": -.01, "group_monotonicity": -.1}, 0)
    assert passed and not failures
    passed, failures = _development_gate(metrics(), qlib(excess=-.05),
                                         {"top_bottom_return": -.01, "group_monotonicity": -.1}, 0)
    assert not passed and "predictive_or_excess" in failures


def test_candidate_ordering_prefers_default_when_all_prior_keys_tie():
    summary = {"positive_rankic_year_count": 3, "positive_excess_year_count": 3,
        "median_rankic": .01, "worst_rankic": -.001, "median_excess": .05, "worst_excess": -.02,
        "median_return_without_best10": .1, "maximum_drawdown_abs": .2, "median_turnover": 20.0}
    default = {"summary": summary, "default_candidate_passed": True,
        "maximum_old_factor_correlation": .2, "ast_depth": 3, "factor_instance_id": "fi_a"}
    rescued = default | {"default_candidate_passed": False, "factor_instance_id": "fi_b"}
    assert sorted([rescued, default], key=candidate_ordering)[0] is default


def test_candidate_lock_completeness_and_research_only_boundary(tmp_path):
    identity = {"schema_version": "default-first-momentum-candidate-lock-v1", "provider_id": "tushare-pro-v1",
        "factor_template_id": "ft", "factor_instance_id": "fi", "template_name": "simple",
        "momentum_family": "consensus", "canonical_dsl": "x", "canonical_ast": {}, "input_features": ["momentum_20_5"],
        "agent_default_parameters": {"w": .5}, "selected_parameters": {"w": .5}, "optimization_mode": "default_first",
        "optimization_rescued": False, "development_metrics": {}, "annual_2021_2024_metrics": [], "orientation": 1,
        "factor_value_artifact_id": "fv", "unified_signal_id": "signal", "turnover": 1.0, "cost": 1.0,
        "concentration": .1, "old_factor_correlations": {}, "structural_fingerprint": "sf",
        "economic_hypothesis": "h", "status": "research_registered", "predictive_claim": False,
        "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0}
    artifact = publish_artifact(tmp_path, "default_first_momentum_candidate_lock", identity,
                                {"candidate.json": identity, "signal.parquet": b"signal"})
    assert validate_artifact(artifact["path"], artifact["candidate_lock_id"])["status"] == "valid"
    invalid = identity | {"status": "production"}
    with pytest.raises(ValueError, match="research-only"):
        publish_artifact(tmp_path / "invalid", "default_first_momentum_candidate_lock", invalid, {})


def test_report_is_explicitly_excluded_from_selection(tmp_path):
    identity = {"schema_version": "default-first-momentum-report-v1", "provider_id": "tushare-pro-v1",
        "candidate_lock_id": "lock", "period": "2025", "date_range": ["2025-01-02", "2025-12-30"],
        "metrics": {}, "qlib": {}, "regime_metrics": {}, "not_used_for_selection": True,
        "not_fresh_validation": True, "promotion_writes": 0}
    artifact = publish_artifact(tmp_path, "default_first_momentum_report", identity, {"report.json": identity})
    manifest = json.loads((__import__("pathlib").Path(artifact["path"]) / "manifest.json").read_text())
    assert manifest["identity"]["not_used_for_selection"] is True
