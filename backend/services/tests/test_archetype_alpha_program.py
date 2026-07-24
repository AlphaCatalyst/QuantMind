from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.archetype_alpha_program.evaluation import (
    daily_rankic, tail_observations,
)
from backend.services.engine.archetype_alpha_program.models import (
    ARCHETYPES, AlphaArchetypeContractV1, AlphaProgramBudget,
    ArchetypeAwareAlphaProgramSpecV1, empty_usage,
)
from backend.services.engine.archetype_alpha_program.orchestrator import (
    _normalize_and_admit,
)
from backend.services.engine.archetype_alpha_program.schemas import alpha_agent_schema
from backend.services.engine.autonomous_factor_program.statistics import benjamini_hochberg


def _template():
    return {
        "schema_version": "1.0.0", "name": "trend_rank",
        "description": "ranked trend", "dataset_kinds": ["legacy_feature_matrix_v1"],
        "parameters": [], "expression": {
            "type": "cs_rank", "operand": {"type": "feature", "name": "momentum_20"},
        }, "output": {"name": "trend_rank"},
    }


def _proposal(archetype="monotonic_rank_factor"):
    return {
        "proposal_id": "trend_rank", "lane_id": "trend_geometry_lane",
        "round_id": "r1", "factor_family": "multi_horizon_trend",
        "primary_archetype": archetype,
        "primary_hypothesis": "higher trend score has the preregistered relation",
        "primary_test_statistic": ARCHETYPES[archetype]["primary_test_statistic"],
        "expected_holding_horizon": "10 sessions",
        "template": _template(), "parameter_search": [],
        "rationale": "trend persistence", "expected_behavior": "higher is stronger",
        "novelty_claim": "simple test candidate", "risks": ["reversal"],
        "invalidation_conditions": ["unstable annual relation"],
    }


def test_archetype_contract_is_frozen_before_evaluation():
    payload = AlphaArchetypeContractV1().payload("tfc2_test")
    assert set(payload["allowed_archetypes"]) == {
        "monotonic_rank_factor", "top_tail_selection_factor",
    }
    assert payload["post_hoc_switch_allowed"] is False
    assert payload["global_fdr_q"] == .10


def test_program_spec_requires_catalog_and_exact_budgets():
    with pytest.raises(ValueError):
        ArchetypeAwareAlphaProgramSpecV1().payload()
    payload = ArchetypeAwareAlphaProgramSpecV1(feature_catalog_v2_id="tfc2_test").payload()
    assert payload["budgets"]["maximum_agent_calls"] == 18
    assert payload["strategy_protocol"]["rebalance_interval"] == 10


def test_program_budget_cannot_expand():
    with pytest.raises(ValueError):
        ArchetypeAwareAlphaProgramSpecV1(
            feature_catalog_v2_id="tfc2_test",
            budgets=AlphaProgramBudget(maximum_total_rounds=19),
        ).payload()


def test_archetype_missing_is_hard_failure():
    proposal = _proposal()
    proposal.pop("primary_archetype")
    with pytest.raises(ValueError, match="ALPHA_ARCHETYPE_MISSING"):
        _normalize_and_admit(
            proposal, round_number=1, family="multi_horizon_trend",
            lane_id="trend_geometry_lane", archetype="monotonic_rank_factor",
            allowed_features={"momentum_20"}, known_fingerprints=set(), index=0,
        )


def test_post_hoc_archetype_switch_is_hard_failure():
    with pytest.raises(ValueError, match="POST_HOC_ALPHA_ARCHETYPE_SWITCH"):
        _normalize_and_admit(
            _proposal("top_tail_selection_factor"), round_number=1,
            family="multi_horizon_trend", lane_id="trend_geometry_lane",
            archetype="monotonic_rank_factor", allowed_features={"momentum_20"},
            known_fingerprints=set(), index=0,
        )


def test_monotonic_primary_test_is_exact():
    result = _normalize_and_admit(
        _proposal(), round_number=1, family="multi_horizon_trend",
        lane_id="trend_geometry_lane", archetype="monotonic_rank_factor",
        allowed_features={"momentum_20"}, known_fingerprints=set(), index=0,
    )
    assert result["primary_test_statistic"] == "daily_official_label_rankic"
    assert result["primary_archetype"] == "monotonic_rank_factor"


def test_tail_primary_test_is_exact():
    result = _normalize_and_admit(
        _proposal("top_tail_selection_factor"), round_number=1,
        family="multi_horizon_trend", lane_id="trend_geometry_lane",
        archetype="top_tail_selection_factor", allowed_features={"momentum_20"},
        known_fingerprints=set(), index=0,
    )
    assert result["primary_test_statistic"] == "non_overlapping_top20_universe_10_session_spread"


def test_tail_observations_use_nonoverlapping_10_session_dates():
    dates = pd.bdate_range("2021-01-04", periods=45)
    symbols = [f"S{i:03d}" for i in range(100)]
    index = pd.MultiIndex.from_product([symbols, dates], names=["symbol", "trade_date"]).to_frame(index=False)
    index["trade_date"] = index["trade_date"].dt.strftime("%Y-%m-%d")
    index["adjusted_close"] = (
        np.tile(np.arange(45), 100) / 100 + np.repeat(np.arange(100), 45) / 10 + 10
    )
    values = index[["symbol", "trade_date"]].copy()
    values["factor_value"] = np.repeat(np.arange(100), 45)
    rows = tail_observations(values, index, 1, "2021-01-04", "2021-03-31")
    selected_dates = [row["trade_date"] for row in rows]
    positions = [dates.strftime("%Y-%m-%d").tolist().index(value) for value in selected_dates]
    assert all(right - left == 10 for left, right in zip(positions, positions[1:]))


def test_daily_rankic_is_primary_monotonic_observation():
    dates = pd.bdate_range("2021-01-04", periods=3).strftime("%Y-%m-%d")
    rows = pd.MultiIndex.from_product([[f"S{i:03d}" for i in range(100)], dates],
                                      names=["symbol", "trade_date"]).to_frame(index=False)
    rows["model_label"] = np.repeat(np.arange(100), 3)
    values = rows[["symbol", "trade_date"]].copy()
    values["factor_value"] = rows["model_label"]
    sample = daily_rankic(values, rows, 1, dates[0], dates[-1])
    assert sample == pytest.approx([1, 1, 1])


def test_bh_is_global_across_archetype_rows():
    rows = benjamini_hochberg([
        {"validation_id": "m", "raw_p_value": .01, "primary_archetype": "monotonic_rank_factor"},
        {"validation_id": "t", "raw_p_value": .08, "primary_archetype": "top_tail_selection_factor"},
    ], q=.10)
    assert {row["hypothesis_count"] for row in rows} == {2}
    assert rows[0]["adjusted_q_value"] == pytest.approx(.02)


@pytest.mark.parametrize("field", [
    "strategy_optimization_calls", "combined_optimization_calls",
    "tushare_calls", "network_data_calls", "promotion_writes",
    "manual_intervention_count", "manual_alpha_round_planning_count",
    "manual_archetype_switching_count",
])
def test_forbidden_usage_counters_start_at_zero(field):
    assert empty_usage()[field] == 0


def test_alpha_agent_schema_requires_archetype_before_evaluation():
    required = alpha_agent_schema()["properties"]["proposals"]["items"]["required"]
    assert "primary_archetype" in required
    assert "primary_test_statistic" in required
    assert "primary_hypothesis" in required


def test_source_contract_has_no_strategy_search_fields():
    rendered = str(alpha_agent_schema()).lower()
    assert "topk" not in rendered
    assert "n_drop" not in rendered
    assert "rebalance_interval" not in rendered
