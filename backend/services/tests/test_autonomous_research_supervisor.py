from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.engine.autonomous_research_supervisor import (
    AutonomousResearchSupervisorSpecV1,
    SupervisorBudget,
    assess_cohort,
    build_fresh_cohort,
    build_fresh_lock,
    build_market_snapshot,
    build_project_evidence_ledger,
    deduplicate_incremental_rows,
    first_trade_date_after,
    global_stop_decision,
)
from backend.services.engine.autonomous_research_supervisor.models import runtime_counts
from backend.services.engine.autonomous_research_supervisor.schemas import (
    validate_safe_payload,
    validate_candidate,
    validate_fresh_status,
)


def candidate(candidate_id="candidate-1", archetype="monotonic_rank_factor"):
    return {
        "candidate_id": candidate_id,
        "source_cycle_id": "cycle-1",
        "formula": "cs_rank(momentum_20)",
        "parameters": {"window": 20},
        "orientation": 1,
        "archetype": archetype,
        "primary_statistic": (
            "daily_official_label_rankic"
            if archetype == "monotonic_rank_factor"
            else "non_overlapping_top20_universe_10_session_spread"
        ),
        "historical_metrics": {"cross_year_stability": True},
        "search_exposure": {"effective_tests": 3},
        "multiple_testing_evidence": {"passed": True},
        "correlations": {"maximum": 0.5},
        "historical_date_max": "2026-07-23",
        "project_contamination_ledger_id": "peel1_test",
        "strategy_protocol": {"topk": 20, "rebalance_interval": 10},
        "status": "retrospective_candidate",
    }


def lock(value=None):
    return build_fresh_lock(
        value or candidate(),
        latest_market_date="2026-07-23",
        official_trade_dates=["2026-07-23", "2026-07-24", "2026-07-25"],
        market_snapshot_id="snapshot-at-lock",
    )


def observation(candidate_id, archetype, values, *, complete=True):
    row = {
        "candidate_id": candidate_id,
        "archetype": archetype,
        "fresh_trading_days": 60 if complete else 20,
        "completed_non_overlapping_holding_windows": 5 if complete else 2,
        "rebalance_periods": 3 if complete else 1,
        "finite_coverage": 0.95,
        "pit_violations": 0,
        "economic_gate_passed": True,
        "stability_gate_passed": True,
    }
    if archetype == "monotonic_rank_factor":
        row["daily_rankic"] = values
    else:
        row["non_overlapping_top20_universe_spread"] = values
    return row


def test_supervisor_spec_is_frozen_before_execution():
    payload = AutonomousResearchSupervisorSpecV1().payload()
    assert payload["supervisor_spec_id"].startswith("arsv1_")
    assert payload["budgets"]["maximum_research_cycles_per_run"] == 2
    assert payload["promotion_allowed"] is False


def test_supervisor_budget_cannot_expand():
    with pytest.raises(ValueError):
        AutonomousResearchSupervisorSpecV1(
            budgets=SupervisorBudget(maximum_agent_calls_per_cycle=19)
        ).payload()


def test_contamination_ledger_backfills_r1_and_r2_but_not_p0(tmp_path):
    root = tmp_path / "docs/quantmind2/implementation/runs/x"
    root.mkdir(parents=True)
    for index, task in enumerate(("QM2-R1-001", "QM2-R1-010", "QM2-R2-004", "QM2-P0-017")):
        target = root / str(index)
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps({
            "task": {"task_id": task},
            "run": {"implementation_run_id": f"run-{index}"},
            "artifacts": [],
        }))
    ledger = build_project_evidence_ledger(tmp_path)
    assert len(ledger["entries"]) == 3
    assert ledger["project_exposed_date_range"] == ["2019-01-02", "2026-07-23"]
    assert {row["evidence_semantics"] for row in ledger["entries"]} == {
        "retrospective_research_only"
    }
    r1_010 = next(row for row in ledger["entries"] if row["task_id"] == "QM2-R1-010")
    assert r1_010["r1_010_statistical_isolation"] is True
    assert r1_010["agent_visibility"] is False


def test_retrospective_candidate_cannot_claim_validation():
    validate_candidate(candidate())
    invalid = candidate()
    invalid["status"] = "validation_candidate"
    with pytest.raises(ValueError):
        validate_candidate(invalid)


def test_fresh_lock_starts_on_first_official_date_strictly_after_cutoff():
    value = lock()
    assert value["fresh_start_date"] == "2026-07-24"
    assert value["historical_cutoff"] == "2026-07-23"
    assert value["no_backfill"] is True
    assert value["formula"] == candidate()["formula"]


def test_no_trade_date_after_cutoff_is_data_blocked():
    with pytest.raises(ValueError, match="fresh_data_blocked"):
        first_trade_date_after("2026-07-23", ["2026-07-22", "2026-07-23"])


def test_cohort_freezes_membership_before_observation_and_caps_size():
    value = build_fresh_cohort([lock()])
    assert value["membership_frozen"] is True
    assert value["multiple_testing_policy"]["fdr_q"] == 0.10
    with pytest.raises(ValueError):
        build_fresh_cohort([lock()], observations_exist=True)
    with pytest.raises(ValueError):
        build_fresh_cohort([lock(candidate(f"c-{i}")) for i in range(11)])


def test_accumulating_status_precedes_minimum_evidence():
    cohort = build_fresh_cohort([lock()])
    multiple, assessments = assess_cohort(
        cohort,
        [observation("candidate-1", "monotonic_rank_factor", [0.01] * 20, complete=False)],
    )
    assert multiple["hypothesis_count"] == 0
    assert assessments[0]["status"] == "fresh_evidence_accumulating"


def test_monotonic_fresh_test_uses_hac10_and_can_support():
    cohort = build_fresh_cohort([lock()])
    _, assessments = assess_cohort(
        cohort,
        [observation("candidate-1", "monotonic_rank_factor", [0.02] * 60)],
    )
    assert assessments[0]["hac_lag"] == 10
    assert assessments[0]["status"] == "fresh_supported"


def test_tail_fresh_test_uses_hac1():
    tail = candidate("tail-1", "top_tail_selection_factor")
    cohort = build_fresh_cohort([lock(tail)])
    _, assessments = assess_cohort(
        cohort,
        [observation("tail-1", "top_tail_selection_factor", [0.01] * 6)],
    )
    assert assessments[0]["hac_lag"] == 1
    assert assessments[0]["status"] == "fresh_supported"


def test_fresh_rejected_and_inconclusive_states():
    c1, c2 = candidate("c1"), candidate("c2")
    cohort = build_fresh_cohort([lock(c1), lock(c2)])
    negative = observation("c1", "monotonic_rank_factor", [-0.01] * 60)
    weak = observation("c2", "monotonic_rank_factor", [0.002, 0.0] * 30)
    weak["economic_gate_passed"] = False
    multiple, assessments = assess_cohort(cohort, [negative, weak])
    statuses = {row["candidate_id"]: row["status"] for row in assessments}
    assert statuses["c1"] == "fresh_rejected"
    assert statuses["c2"] == "fresh_inconclusive"
    assert multiple["hypothesis_count"] == 2


def test_global_bh_applies_across_archetypes():
    mono = candidate("m")
    tail = candidate("t", "top_tail_selection_factor")
    cohort = build_fresh_cohort([lock(mono), lock(tail)])
    multiple, _ = assess_cohort(cohort, [
        observation("m", "monotonic_rank_factor", [0.02] * 60),
        observation("t", "top_tail_selection_factor", [0.01] * 6),
    ])
    assert multiple["hypothesis_count"] == 2
    assert {row["candidate_id"] for row in multiple["results"]} == {"m", "t"}


def test_fresh_observation_outside_frozen_cohort_is_rejected():
    cohort = build_fresh_cohort([lock()])
    with pytest.raises(ValueError, match="outside frozen Cohort"):
        assess_cohort(
            cohort,
            [observation("other", "monotonic_rank_factor", [0.01] * 60)],
        )


def test_post_hoc_fresh_archetype_switch_is_rejected():
    cohort = build_fresh_cohort([lock()])
    with pytest.raises(ValueError, match="POST_HOC_ALPHA_ARCHETYPE_SWITCH"):
        assess_cohort(
            cohort,
            [observation(
                "candidate-1",
                "top_tail_selection_factor",
                [0.01] * 6,
            )],
        )


def test_first_seen_snapshot_is_immutable_and_revision_has_new_identity():
    first = build_market_snapshot(start_date="2026-07-24", end_date="2026-07-24")
    revision = build_market_snapshot(
        start_date="2026-07-24",
        end_date="2026-07-24",
        parent_snapshot_id=first["fresh_market_snapshot_id"],
        revision=2,
    )
    assert first["first_seen_market_snapshot"] is True
    assert revision["revision_does_not_overwrite_parent"] is True
    assert revision["fresh_market_snapshot_id"] != first["fresh_market_snapshot_id"]


@pytest.mark.parametrize("status", [
    "fresh_locked", "fresh_evidence_accumulating", "fresh_supported",
    "fresh_rejected", "fresh_inconclusive", "fresh_data_blocked",
])
def test_all_fresh_states_are_explicit(status):
    validate_fresh_status(status)


def test_exact_replay_counters_cover_all_forbidden_side_effects():
    counts = runtime_counts()
    assert counts
    assert set(counts.values()) == {0}
    assert counts["promotion_writes"] == 0
    assert counts["tushare_calls"] == 0
    assert counts["qlib_calls"] == 0


def test_active_fresh_capacity_and_two_empty_cycles_stop_new_research():
    capacity = global_stop_decision(
        consecutive_cycles_without_new_feature=0,
        consecutive_cycles_without_candidate=0,
        novelty_exhausted=False,
        active_fresh_candidates=20,
    )
    empty = global_stop_decision(
        consecutive_cycles_without_new_feature=2,
        consecutive_cycles_without_candidate=2,
        novelty_exhausted=False,
        active_fresh_candidates=0,
    )
    assert capacity == {"stop": True, "reason": "active_fresh_capacity_reached"}
    assert empty == {"stop": True, "reason": "two_empty_research_cycles"}


def test_incremental_rows_are_deduplicated_without_history_download():
    rows = [
        {"ts_code": "000001.SZ", "trade_date": "20260724", "close": 10},
        {"ts_code": "000001.SZ", "trade_date": "20260724", "close": 11},
    ]
    result = deduplicate_incremental_rows(rows, ("ts_code", "trade_date"))
    assert result == [{"ts_code": "000001.SZ", "trade_date": "20260724", "close": 11}]


def test_credential_material_is_rejected_and_cli_has_no_token_argument():
    with pytest.raises(ValueError, match="credential"):
        validate_safe_payload({"tushare_token": "secret", "promotion_writes": 0})
    source = (
        Path(__file__).resolve().parents[3]
        / "tools/quantmind2/run_autonomous_research_supervisor.py"
    ).read_text(encoding="utf-8")
    assert "--token" not in source
    assert "token_hash" not in source
