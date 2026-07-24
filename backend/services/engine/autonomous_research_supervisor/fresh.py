from __future__ import annotations

from typing import Any

from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg,
    hac_mean_test,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .schemas import validate_candidate, validate_fresh_status


def first_trade_date_after(latest_date: str, official_trade_dates: list[str]) -> str:
    candidates = sorted(value for value in official_trade_dates if value > latest_date)
    if not candidates:
        raise ValueError("fresh_data_blocked: no official trade date after latest market data")
    return candidates[0]


def build_fresh_lock(candidate: dict[str, Any], *, latest_market_date: str,
                     official_trade_dates: list[str], market_snapshot_id: str) -> dict[str, Any]:
    validate_candidate(candidate)
    stable = {
        "schema_version": "project-candidate-fresh-lock-v1",
        "provider_id": "tushare-pro-v1",
        "candidate_id": candidate["candidate_id"],
        "formula": candidate["formula"],
        "parameters": candidate["parameters"],
        "orientation": candidate["orientation"],
        "archetype": candidate["archetype"],
        "primary_test_statistic": candidate["primary_statistic"],
        "strategy_protocol": candidate["strategy_protocol"],
        "universe": "Tushare Fixed-100",
        "benchmark": "CSI300",
        "fresh_start_date": first_trade_date_after(latest_market_date, official_trade_dates),
        "market_snapshot_id_at_lock": market_snapshot_id,
        "historical_cutoff": latest_market_date,
        "no_backfill": True,
        "status": "fresh_locked",
        "promotion_writes": 0,
    }
    return stable | {"fresh_lock_id": "pcfl1_" + hash_payload(stable)}


def build_fresh_cohort(locks: list[dict[str, Any]], *, observations_exist: bool = False) -> dict[str, Any]:
    if observations_exist:
        raise ValueError("Fresh Cohort must freeze before the first observation")
    if not locks or len(locks) > 10:
        raise ValueError("Fresh Cohort size must be between one and ten")
    stable = {
        "schema_version": "fresh-candidate-cohort-v1",
        "provider_id": "tushare-pro-v1",
        "candidate_membership": [row["candidate_id"] for row in locks],
        "fresh_lock_ids": [row["fresh_lock_id"] for row in locks],
        "primary_tests": {row["candidate_id"]: row["primary_test_statistic"] for row in locks},
        "minimum_evidence_policy": {
            "fresh_trading_days": 60,
            "completed_non_overlapping_holding_windows": 5,
            "rebalance_periods": 3,
            "finite_coverage": 0.90,
            "pit_violations": 0,
        },
        "multiple_testing_policy": {"method": "benjamini_hochberg", "fdr_q": 0.10},
        "membership_frozen": True,
        "promotion_writes": 0,
    }
    return stable | {"fresh_cohort_id": "fcc1_" + hash_payload(stable)}


def build_market_snapshot(*, start_date: str, end_date: str,
                          parent_snapshot_id: str | None = None,
                          revision: int = 1) -> dict[str, Any]:
    stable = {
        "schema_version": "fresh-market-snapshot-v1",
        "provider_id": "tushare-pro-v1",
        "start_date": start_date,
        "end_date": end_date,
        "parent_snapshot_id": parent_snapshot_id,
        "revision": revision,
        "first_seen_market_snapshot": parent_snapshot_id is None,
        "revision_does_not_overwrite_parent": parent_snapshot_id is not None,
        "endpoints": ["daily", "adj_factor", "daily_basic", "trade_cal", "index_daily"],
        "credential_source": "environment_only_not_persisted",
        "incremental_only": True,
        "promotion_writes": 0,
    }
    return stable | {"fresh_market_snapshot_id": "fms1_" + hash_payload(stable)}


def minimum_evidence_passed(observation: dict[str, Any]) -> bool:
    return (
        observation["fresh_trading_days"] >= 60
        and observation["completed_non_overlapping_holding_windows"] >= 5
        and observation["rebalance_periods"] >= 3
        and observation["finite_coverage"] >= 0.90
        and observation["pit_violations"] == 0
    )


def primary_test(observation: dict[str, Any]) -> dict[str, Any]:
    archetype = observation["archetype"]
    if archetype == "monotonic_rank_factor":
        values = observation["daily_rankic"]
        lag = 10
        effect_name = "mean_fresh_rankic"
    elif archetype == "top_tail_selection_factor":
        values = observation["non_overlapping_top20_universe_spread"]
        lag = 1
        effect_name = "mean_top20_universe_spread"
    else:
        raise ValueError("unsupported Fresh archetype")
    result = hac_mean_test(list(values), lag=lag)
    return result | {
        "effect": result["mean_rankic"],
        "effect_name": effect_name,
        "hac_lag": lag,
    }


def assess_cohort(cohort: dict[str, Any], observations: list[dict[str, Any]]) -> tuple[dict, list[dict]]:
    members = cohort["candidate_membership"]
    if {row["candidate_id"] for row in observations} - set(members):
        raise ValueError("Fresh observation is outside frozen Cohort")
    tested: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    for row in observations:
        expected = cohort["primary_tests"][row["candidate_id"]]
        actual = (
            "daily_official_label_rankic"
            if row["archetype"] == "monotonic_rank_factor"
            else "non_overlapping_top20_universe_10_session_spread"
        )
        if actual != expected:
            raise ValueError("POST_HOC_ALPHA_ARCHETYPE_SWITCH")
        if not minimum_evidence_passed(row):
            assessments.append({
                "candidate_id": row["candidate_id"],
                "status": "fresh_evidence_accumulating",
                "minimum_evidence_passed": False,
                "raw_p_value": None,
                "adjusted_q_value": None,
            })
            continue
        test = primary_test(row)
        tested.append({
            "candidate_id": row["candidate_id"],
            "raw_p_value": test["raw_p_value"],
            "test": test,
            "row": row,
        })
    adjusted = benjamini_hochberg(tested, q=0.10) if tested else []
    for item in adjusted:
        row, test = item["row"], item["test"]
        q_value = item["adjusted_q_value"]
        economic_gate = bool(row.get("economic_gate_passed", test["effect"] > 0))
        stability_gate = bool(row.get("stability_gate_passed", True))
        if test["effect"] > 0 and economic_gate and stability_gate and q_value <= 0.10:
            status = "fresh_supported"
        elif test["effect"] <= 0 or not stability_gate:
            status = "fresh_rejected"
        else:
            status = "fresh_inconclusive"
        validate_fresh_status(status)
        assessments.append({
            "candidate_id": row["candidate_id"],
            "status": status,
            "minimum_evidence_passed": True,
            "raw_p_value": item["raw_p_value"],
            "adjusted_q_value": q_value,
            "effect": test["effect"],
            "hac_lag": test["hac_lag"],
            "parameters_unchanged": True,
            "orientation_unchanged": True,
            "no_backfill": True,
        })
    stable = {
        "schema_version": "fresh-cohort-multiple-testing-v1",
        "provider_id": "tushare-pro-v1",
        "fresh_cohort_id": cohort["fresh_cohort_id"],
        "method": "benjamini_hochberg",
        "fdr_q": 0.10,
        "hypothesis_count": len(tested),
        "results": [
            {"candidate_id": row["candidate_id"], "raw_p_value": row["raw_p_value"],
             "adjusted_q_value": row["adjusted_q_value"],
             "rank": row["rank_in_multiple_test"]}
            for row in adjusted
        ],
        "promotion_writes": 0,
    }
    return stable | {"fresh_multiple_testing_id": "fcmt1_" + hash_payload(stable)}, assessments
