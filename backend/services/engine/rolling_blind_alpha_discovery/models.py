from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


@dataclass(frozen=True)
class RollingBlindBudgetV1:
    maximum_rounds: int = 24
    maximum_agent_calls: int = 24
    maximum_proposals: int = 72
    maximum_admissions: int = 48
    maximum_local_rescue_trials: int = 72
    maximum_model_hypotheses: int = 6
    maximum_qlib_calls: int = 300
    maximum_blind_submissions: int = 20
    maximum_final_survivors: int = 5
    minimum_rounds_before_improvement_stop: int = 18
    minimum_agent_calls_before_improvement_stop: int = 18
    minimum_distinct_families_before_improvement_stop: int = 8
    minimum_admissions_before_improvement_stop: int = 30

    def validate(self) -> None:
        frozen = RollingBlindBudgetV1()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
            if value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds the frozen Batch 001 budget")


@dataclass(frozen=True)
class RollingBlindDiscoveryBatchSpecV1:
    batch_name: str = "rolling_blind_discovery_batch_001"
    provider_id: str = "tushare-pro-v1"
    evidence_semantics: str = "historical_rolling_blind"
    discovery_period: tuple[str, str] = ("2019-01-02", "2021-12-31")
    blind_pool: tuple[str, str] = ("2022-01-04", "2026-07-23")
    window_trading_days: int = 60
    label_name: str = "technical_return_1d"
    feature_catalog_id: str = (
        "tfc3_b903c85e328d359181c18ce3444d458a41ee970be8b2f6b79eff83cc6d523aea"
    )
    model_spec_id: str = (
        "fcms1_27c7102a662731b28d5142166dacc398e82ca4c701870c6657bfd83cdcd7ad94"
    )
    strategy_protocol: dict[str, Any] = field(default_factory=lambda: {
        "topk": 20,
        "n_drop": 5,
        "rebalance_interval": 10,
        "weighting": "equal_weight",
        "signal_lag": 1,
        "execution": "open",
        "benchmark": "CSI300",
    })
    budgets: RollingBlindBudgetV1 = field(default_factory=RollingBlindBudgetV1)
    global_fdr_q: float = 0.10
    promotion_allowed: bool = False
    automatic_trading_allowed: bool = False

    def payload(self, *, supervisor_id: str, window_set_id: str) -> dict[str, Any]:
        self.budgets.validate()
        if self.global_fdr_q != 0.10:
            raise ValueError("Rolling Blind FDR is frozen at 10%")
        if self.promotion_allowed or self.automatic_trading_allowed:
            raise ValueError("Rolling Blind research cannot promote or trade")
        stable = asdict(self) | {
            "schema_version": "rolling-blind-discovery-batch-v1",
            "supervisor_id": supervisor_id,
            "rolling_blind_window_set_id": window_set_id,
            "lanes": {
                "dsl_lane": {
                    "structure_source": "Agent",
                    "optimization_policy": "default_first_one_hop_local_rescue",
                },
                "fixed_model_lane": {
                    "model": "existing_quantmind_lightgbm",
                    "configuration": "canonical_fixed_three_seed_equal_weight",
                    "feature_membership": "label_free_frozen_rule",
                },
            },
            "blind_metrics_visible_to_agent": False,
            "blind_metrics_visible_to_planner": False,
            "fresh_metrics_visible": False,
            "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0,
            "promotion_writes": 0,
        }
        return stable | {"rolling_blind_discovery_batch_id": "rbdb1_" + hash_payload(stable)}


def empty_runtime_counts() -> dict[str, int]:
    return {
        "rounds": 0,
        "agent_calls": 0,
        "proposals": 0,
        "admissions": 0,
        "rejected_structures": 0,
        "duplicate_structures": 0,
        "local_rescue_trials": 0,
        "model_hypotheses": 0,
        "model_training_calls": 0,
        "qlib_calls": 0,
        "blind_submissions": 0,
        "blind_window_evaluations": 0,
        "candidate_writes": 0,
        "survivor_writes": 0,
        "fresh_lock_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "manual_intervention_count": 0,
        "manual_round_planning_count": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
    }
