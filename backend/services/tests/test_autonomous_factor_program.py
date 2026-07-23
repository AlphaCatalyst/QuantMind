from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.services.engine.autonomous_factor_program.models import (
    LANES, AutonomousFactorResearchProgramSpecV1, evidence_partitions,
)
from backend.services.engine.autonomous_factor_program.orchestrator import (
    _can_improvement_stop, _process_round, _union_order,
)
from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg, hac_mean_test,
)


def test_all_three_lane_specs_freeze_before_agent():
    spec = AutonomousFactorResearchProgramSpecV1().payload()
    assert spec["program_spec_id"].startswith("afrp1_")
    assert set(spec["lanes"]) == set(LANES)
    assert spec["program_name"] == "technical_factor_program_001"


def test_program_partition_denies_late_evidence_to_research():
    rows = evidence_partitions()["partitions"]
    assert rows["adaptive_research"]["usable_by_agent"]
    for name in ("locked_validation", "contaminated_report", "fresh_forward"):
        assert not rows[name]["usable_by_agent"]
        assert not rows[name]["usable_by_planner"]
        assert not rows[name]["usable_by_failure_memory"]
    assert rows["locked_validation"]["usable_for_registry"]


def _state(rounds=0, calls=0, admissions=0, families=0, no_lock=0):
    names = [
        "multi_horizon_trend", "pullback_continuation", "path_quality",
        "volume_price_confirmation", "liquidity_normalized_trend",
        "drawdown_recovery",
    ][:families]
    lanes = {}
    for index, lane_id in enumerate(LANES):
        lanes[lane_id] = {
            "rounds": rounds // 3 + int(index < rounds % 3),
            "families_attempted": names[index::3],
            "consecutive_no_lock": no_lock // 3 + int(index < no_lock % 3),
            "lane_id": lane_id,
        }
    return {
        "budget_usage": {"rounds": rounds, "agent_calls": calls, "admissions": admissions},
        "lanes": lanes,
    }


def test_improvement_stop_is_forbidden_before_minimum_rounds():
    budget = AutonomousFactorResearchProgramSpecV1().payload()["budgets"]
    assert not _can_improvement_stop(_state(11, 11, 20, 6, 9), budget)


def test_improvement_stop_is_forbidden_before_all_lanes_run():
    budget = AutonomousFactorResearchProgramSpecV1().payload()["budgets"]
    state = _state(12, 12, 20, 6, 9)
    state["lanes"]["recovery_relative_lane"]["rounds"] = 0
    assert not _can_improvement_stop(state, budget)


def test_hac_positive_sequence_has_positive_statistic():
    result = hac_mean_test([.01, .02, .015, .005] * 20, lag=10)
    assert result["mean_rankic"] > 0
    assert result["t_statistic"] > 0
    assert 0 <= result["raw_p_value"] <= 1


def test_hac_empty_is_conservative():
    assert hac_mean_test([], lag=10)["raw_p_value"] == 1.0


def test_bh_is_monotone_and_fixed_at_ten_percent():
    rows = benjamini_hochberg([
        {"raw_p_value": .001}, {"raw_p_value": .02}, {"raw_p_value": .2},
    ], q=.10)
    assert rows[0]["adjusted_q_value"] <= rows[1]["adjusted_q_value"]
    assert all(row["fdr_threshold"] == .10 for row in rows)
    assert rows[0]["multiple_testing_passed"]
    assert not rows[-1]["multiple_testing_passed"]


def _union_row(lane, family, instance, values, rank=1):
    return {
        "lane_id": lane, "factor_family": family, "factor_instance_id": instance,
        "lane_rank": rank, "_values": values,
        "search_exposure": {"candidate_effective_search_count": 3},
    }


def test_union_prefers_lane_and_family_diversity():
    import pandas as pd
    values = pd.DataFrame({
        "symbol": ["a", "b", "a", "b"],
        "trade_date": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-02"]),
        "factor_value": [1., 2., 2., 1.],
    })
    inverse = values.copy()
    inverse["factor_value"] = [2., 1., 1., 2.]
    rows = [
        _union_row("a", "f1", "x", values),
        _union_row("b", "f2", "y", inverse),
    ]
    # Absolute correlation makes these global signal duplicates.
    assert len(_union_order(rows)) == 1


def test_invalid_agent_parameter_contract_closes_round_without_evaluation(monkeypatch):
    class Repository:
        def publish(self, kind, identity, files, lineage=()):
            if kind == "autonomous_factor_round":
                self.identity = identity
                return {"artifact_id": "afr1_rejected"}
            assert kind == "autonomous_factor_failure_memory"
            return {"artifact_id": "affm1_rejected"}

    repository = Repository()
    state = {
        "program_id": "afrp1_test",
        "budget_usage": {
            "proposals": 0, "admissions": 0, "adaptive_qlib_calls": 0,
            "local_rescue_trials": 0, "rounds": 0,
        },
        "known_fingerprints": [], "search_exposure_ids": [],
        "program_signal_refs": [], "lanes": {},
    }
    lane = {
        "lane_id": "trend_structure_lane", "proposals": 0, "admissions": 0,
        "adaptive_qlib_calls": 0, "local_rescue_trials": 0,
        "round_artifact_ids": [], "rounds": 0, "families_attempted": [],
        "candidate_refs": [], "consecutive_no_lock": 0,
        "agent_calls": 1, "memory": {},
    }
    state["lanes"][lane["lane_id"]] = lane

    class ContractFailure(Exception):
        detail = {
            "error_code": "parameter_declared_but_unused",
            "safe_summary": "unused parameter",
        }

    monkeypatch.setattr(
        "backend.services.engine.autonomous_factor_program.orchestrator.parse_decision",
        lambda *args, **kwargs: (_ for _ in ()).throw(ContractFailure()),
    )
    monkeypatch.setattr(
        "backend.services.engine.autonomous_factor_program.orchestrator.AgentContractError",
        ContractFailure,
    )
    monkeypatch.setattr(
        "backend.services.engine.autonomous_factor_program.orchestrator.update_memory",
        lambda memory, identity, usage: memory,
    )
    monkeypatch.setattr(
        "backend.services.engine.autonomous_factor_program.orchestrator._public",
        lambda value: value,
    )
    _process_round(
        state=state, lane=lane,
        plan={
            "round_number": 1, "theme": "multi_horizon_trend",
            "allowed_features": ["momentum_60_10"],
        },
        response_raw="{}", response_meta={
            "artifact_id": "response", "agent_provider": "test", "agent_model": "test",
        },
        repository=repository, evaluator=object(), contract=object(),
        work_root=Path("/tmp"),
        budget={"maximum_local_rescue_trials": 0},
    )
    assert repository.identity["failure_codes"] == ["parameter_declared_but_unused"]
    assert repository.identity["agent_contract_diagnostic"]["safe_summary"] == "unused parameter"
    assert state["budget_usage"]["rounds"] == 1
    assert lane["rounds"] == 1
    assert not lane["candidate_refs"]
