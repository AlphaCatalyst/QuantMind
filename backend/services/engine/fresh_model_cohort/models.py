from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


CANDIDATE_IDS = (
    "mhrmc1_6b1a97e5b5a19052387ac06c64c3d1cea998a502542479b47c535b1eb24527c3",
    "mhrmc1_83272b1d8093eccb6b3823d62fa618685c139497269bde5742006311ce856c23",
)
FRESH_LOCK_IDS = (
    "mhmfl1_59790b02d1ebcd6b8ed2a7d5e264d10a9060a3f91a0f52fd6c3ebdd6f3e5db17",
    "mhmfl1_1b78c7a94afc15505c852af9796b5b6b05e6ca68151eb11924a146e95bc0cdfc",
)
LABEL_ID = "trl1_38786d6192c987a887de52477ee2dfcca7f8a209ab5744ff70757339cb62cf3a"
MODEL_SPEC_ID = "fcms1_27c7102a662731b28d5142166dacc398e82ca4c701870c6657bfd83cdcd7ad94"
WALK_FORWARD_SPEC_ID = (
    "pwfs1_6a226e117f7eca56f380f1e7445bcb462dc7b7ffeedfe5d0e076b6d4a9c0a7d9"
)
PROJECT_EXPOSURE_DATE = "2026-07-23"
PRIOR_FIRST_SEEN_SNAPSHOT_ID = (
    "tims1_a59e3127abcdd187f352b4d268d765c73bfec480ac5fefd6c6c865ebe909168c"
)
SEEDS = (20260701, 20260702, 20260703)
ALLOWED_ENDPOINTS = ("daily", "adj_factor", "daily_basic", "trade_cal", "index_daily")
LEGAL_FRESH_STATES = (
    "fresh_locked",
    "fresh_evidence_accumulating",
    "fresh_supported",
    "fresh_rejected",
    "fresh_inconclusive",
    "fresh_data_blocked",
)

STRATEGY_PROTOCOL = {
    "topk": 20,
    "n_drop": 5,
    "rebalance_interval": 10,
    "weighting": "equal_weight",
    "signal_lag": 1,
    "execution": "open",
    "benchmark": "CSI300",
}
MINIMUM_EVIDENCE = {
    "fresh_trading_days": 60,
    "completed_holding_windows": 5,
    "rebalance_periods": 3,
    "monthly_retraining_events": 2,
    "coverage": 0.90,
    "pit_violations": 0,
}


@dataclass(frozen=True)
class ModelFreshCandidateCohortV1:
    candidate_membership: tuple[str, ...] = CANDIDATE_IDS
    fresh_lock_ids: tuple[str, ...] = FRESH_LOCK_IDS
    label_id: str = LABEL_ID
    model_spec_id: str = MODEL_SPEC_ID
    walk_forward_spec_id: str = WALK_FORWARD_SPEC_ID
    primary_statistic: str = "daily official-label RankIC"
    hac_lag: int = 10
    bh_fdr_q: float = 0.10
    monthly_retraining_rule: str = "first official trade date of each calendar month"
    project_exposure_date: str = PROJECT_EXPOSURE_DATE
    market_snapshot_id_at_lock: str = PRIOR_FIRST_SEEN_SNAPSHOT_ID
    no_backfill: bool = True

    def payload(self) -> dict[str, Any]:
        if self.candidate_membership != CANDIDATE_IDS:
            raise ValueError("MODEL_FRESH_COHORT_MEMBERSHIP_MISMATCH")
        if self.fresh_lock_ids != FRESH_LOCK_IDS:
            raise ValueError("MODEL_FRESH_COHORT_LOCK_MISMATCH")
        value = asdict(self)
        value |= {
            "schema_version": "model-fresh-candidate-cohort-v1",
            "provider_id": "tushare-pro-v1",
            "candidate_membership": list(self.candidate_membership),
            "fresh_lock_ids": list(self.fresh_lock_ids),
            "seed_ensemble": list(SEEDS),
            "minimum_evidence_policy": MINIMUM_EVIDENCE,
            "strategy_protocol": STRATEGY_PROTOCOL,
            "membership_frozen": True,
            "configuration_frozen": True,
            "published_before_fresh_market_read": True,
            "fresh_start_rule": (
                "first official A-share trade date strictly after project exposure date"
            ),
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        value["model_fresh_candidate_cohort_id"] = "mfcc1_" + hash_payload(value)
        return value


def minimum_evidence_passed(observation: dict[str, Any]) -> bool:
    return (
        observation.get("fresh_trading_days", 0) >= MINIMUM_EVIDENCE["fresh_trading_days"]
        and observation.get("completed_holding_windows", 0)
        >= MINIMUM_EVIDENCE["completed_holding_windows"]
        and observation.get("rebalance_periods", 0)
        >= MINIMUM_EVIDENCE["rebalance_periods"]
        and observation.get("monthly_retraining_events", 0)
        >= MINIMUM_EVIDENCE["monthly_retraining_events"]
        and observation.get("coverage", 0.0) >= MINIMUM_EVIDENCE["coverage"]
        and observation.get("pit_violations", 1) == 0
    )
