from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.autonomous_factor_campaign.artifact import KINDS
from backend.services.engine.rolling_blind_alpha_discovery.engine import (
    _blind_gate,
    _dsl_round_schedule,
    _mean_test,
    _rows,
    _window_set,
)
from backend.services.engine.rolling_blind_alpha_discovery.models import (
    RollingBlindBudgetV1,
    RollingBlindDiscoveryBatchSpecV1,
    empty_runtime_counts,
)


def _bundle(tmp_path: Path, count: int = 1134):
    calendar = tmp_path / "qlib" / "calendars"
    calendar.mkdir(parents=True)
    start = __import__("pandas").Timestamp("2022-01-04")
    dates = __import__("pandas").bdate_range(start, periods=count)
    (calendar / "day.txt").write_text(
        "\n".join(date.strftime("%Y-%m-%d") for date in dates) + "\n",
        encoding="utf-8",
    )
    return SimpleNamespace(qlib_view=tmp_path / "qlib")


def _window_rows(primary=0.01, excess=0.02, turnover=10.0, concentration=0.20):
    return [
        {
            "primary_metric": primary,
            "csi300_excess": excess,
            "turnover": turnover,
            "best_10_days_contribution": concentration,
        }
        for _ in range(12)
    ]


def test_window_set_uses_exact_non_overlapping_sixty_day_windows(tmp_path):
    value = _window_set(_bundle(tmp_path), RollingBlindDiscoveryBatchSpecV1())
    assert value["complete_window_count"] >= 12
    assert all(row["trading_day_count"] == 60 for row in value["windows"])
    assert all(
        left["end_date"] < right["start_date"]
        for left, right in zip(value["windows"], value["windows"][1:])
    )


def test_window_set_excludes_incomplete_tail(tmp_path):
    value = _window_set(_bundle(tmp_path, 1145), RollingBlindDiscoveryBatchSpecV1())
    assert value["tail_excluded"] is True
    assert value["tail_trading_day_count"] == 1145 % 60


def test_window_set_is_frozen_before_agent(tmp_path):
    value = _window_set(_bundle(tmp_path), RollingBlindDiscoveryBatchSpecV1())
    assert value["frozen_before_agent_calls"] is True
    assert value["agent_calls_before_freeze"] == 0
    assert value["boundaries_performance_selected"] is False


def test_spec_freezes_discovery_and_blind_partitions():
    spec = RollingBlindDiscoveryBatchSpecV1().payload(
        supervisor_id="arsv1_test", window_set_id="rbws1_test"
    )
    assert spec["discovery_period"] == ("2019-01-02", "2021-12-31")
    assert spec["blind_pool"] == ("2022-01-04", "2026-07-23")
    assert spec["blind_metrics_visible_to_agent"] is False
    assert spec["blind_metrics_visible_to_planner"] is False
    assert spec["fresh_metrics_visible"] is False


def test_spec_freezes_two_lanes_and_default_first():
    spec = RollingBlindDiscoveryBatchSpecV1().payload(
        supervisor_id="arsv1_test", window_set_id="rbws1_test"
    )
    assert set(spec["lanes"]) == {"dsl_lane", "fixed_model_lane"}
    assert (
        spec["lanes"]["dsl_lane"]["optimization_policy"]
        == "default_first_one_hop_local_rescue"
    )
    assert spec["lanes"]["fixed_model_lane"]["model"] == "existing_quantmind_lightgbm"


def test_budget_matches_batch_001_contract():
    budget = RollingBlindBudgetV1()
    assert budget.maximum_rounds == 24
    assert budget.maximum_agent_calls == 24
    assert budget.maximum_proposals == 72
    assert budget.maximum_admissions == 48
    assert budget.maximum_local_rescue_trials == 72
    assert budget.maximum_model_hypotheses == 6
    assert budget.maximum_qlib_calls == 300
    assert budget.maximum_blind_submissions == 20
    assert budget.maximum_final_survivors == 5


def test_budget_rejects_expansion():
    with pytest.raises(ValueError):
        RollingBlindBudgetV1(maximum_agent_calls=25).validate()


def test_round_schedule_has_minimum_coverage():
    schedule = _dsl_round_schedule()
    assert len(schedule) == 18
    assert len({lane for lane, _, _ in schedule}) == 3
    assert len({family for _, family, _ in schedule}) >= 8
    assert {archetype for _, _, archetype in schedule} == {
        "monotonic_rank_factor",
        "top_tail_selection_factor",
    }


def test_gate_accepts_complete_consistent_candidate():
    result = _blind_gate(_window_rows(), unchanged=True)
    assert result["passed"] is True
    assert result["primary_positive_window_rate"] == 1.0


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("primary_metric", -0.02, "primary_positive_rate"),
        ("csi300_excess", -0.01, "excess_positive_rate"),
        ("turnover", 31.0, "turnover"),
        ("best_10_days_contribution", 0.36, "concentration"),
    ],
)
def test_gate_rejects_failed_threshold(field, value, failure):
    rows = _window_rows()
    for row in rows:
        row[field] = value
    result = _blind_gate(rows, unchanged=True)
    assert result["passed"] is False
    assert failure in result["failed_gates"]


def test_gate_requires_twelve_windows():
    result = _blind_gate(_window_rows()[:11], unchanged=True)
    assert result["passed"] is False
    assert "minimum_windows" in result["failed_gates"]


def test_gate_rejects_post_lock_mutation():
    result = _blind_gate(_window_rows(), unchanged=False)
    assert result["passed"] is False
    assert "configuration_unchanged" in result["failed_gates"]


def test_gate_rejects_incomplete_window_metrics_without_crashing():
    rows = _window_rows()
    rows[0]["csi300_excess"] = None
    result = _blind_gate(rows, unchanged=True)
    assert result["passed"] is False
    assert result["checks"]["complete_metrics"] is False


def test_batch_rows_can_recover_legacy_children_from_lineage():
    batch_id = "rbdb1_parent"
    descriptor = SimpleNamespace(
        artifact_id="rbdb1_child",
        lineage=("rbdb1_response", batch_id),
    )
    repository = SimpleNamespace(
        store=SimpleNamespace(list_by_kind=lambda _: [descriptor]),
        identity=lambda _: {"record_type": "dsl_agent_round", "round_number": 1},
    )
    assert _rows(repository, "rolling_blind_discovery_batch", batch_id) == [
        {
            "record_type": "dsl_agent_round",
            "round_number": 1,
            "artifact_id": "rbdb1_child",
        }
    ]


def test_window_level_one_sided_test_positive():
    result = _mean_test([0.01 + index * 0.0001 for index in range(12)])
    assert result["observation_count"] == 12
    assert result["t_statistic"] > 0
    assert result["raw_p_value"] < 0.10


def test_zero_survivor_is_representable_without_lowering_gate():
    result = _blind_gate(_window_rows(primary=-0.01), unchanged=True)
    assert result["passed"] is False
    assert result["checks"]["minimum_windows"] is True


def test_runtime_replay_counts_are_zero():
    assert all(value == 0 for value in empty_runtime_counts().values())


def test_strategy_and_combined_optimization_are_disabled():
    spec = RollingBlindDiscoveryBatchSpecV1().payload(
        supervisor_id="arsv1_test", window_set_id="rbws1_test"
    )
    assert spec["strategy_optimization_calls"] == 0
    assert spec["combined_optimization_calls"] == 0
    assert spec["promotion_writes"] == 0


def test_required_artifact_kinds_are_registered():
    names = {
        "rolling_blind_window_set",
        "rolling_blind_discovery_batch",
        "rolling_blind_candidate_batch_lock",
        "rolling_blind_candidate_result",
        "rolling_blind_multiple_testing",
        "rolling_blind_search_exposure",
        "rolling_blind_alpha_survivor",
        "rolling_blind_submission_ledger",
        "rolling_blind_research_report",
    }
    assert names <= set(KINDS)
    assert names <= {kind.value for kind in ArtifactKind}


def test_runtime_source_has_no_blind_feedback_to_agent():
    from backend.services.engine.rolling_blind_alpha_discovery import engine

    source = inspect.getsource(engine._dsl_discovery)
    assert "window_result" not in source
    assert "blind_failures" not in source
    assert "fresh_model" not in source
    assert "normalized=normalized" in source
    assert '"parent_batch_id"' in source


def test_lock_contract_closes_agent_and_planner():
    from backend.services.engine.rolling_blind_alpha_discovery import engine

    source = inspect.getsource(engine._freeze_lock)
    assert '"agent_closed": True' in source
    assert '"planner_closed": True' in source
    assert '"blind_window_reads_before_publish": 0' in source


def test_blind_evaluator_never_early_stops_windows():
    from backend.services.engine.rolling_blind_alpha_discovery import engine

    source = inspect.getsource(engine._evaluate_blind)
    assert 'for window in windows["windows"]' in source
    assert '"early_stopped": False' in source


def test_survivor_contract_is_nonproduction():
    from backend.services.engine.rolling_blind_alpha_discovery import engine

    source = inspect.getsource(engine._finalize)
    assert '"status": "research_registered"' in source
    assert '"historical_pseudo_fresh": True' in source
    assert '"real_fresh_validated": False' in source
    assert '"production_eligible": False' in source


def test_fresh_lock_contract_is_no_backfill():
    from backend.services.engine.rolling_blind_alpha_discovery import engine

    source = inspect.getsource(engine._finalize)
    assert '"no_backfill": True' in source
    assert '"minimum_fresh_trading_days": 60' in source
