from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


R3_001_WINDOW_SET_ID = (
    "rbws1_4e8166c3a9d5699d39cac1a776165a311d1b2a6da85eb3c02187cd9405c16259"
)
FEATURE_CATALOG_ID = (
    "tfc3_b903c85e328d359181c18ce3444d458a41ee970be8b2f6b79eff83cc6d523aea"
)


@dataclass(frozen=True)
class CrossSectionalBatchBudgetV1:
    maximum_agent_calls: int = 18
    maximum_dsl_proposals: int = 54
    maximum_dsl_admissions: int = 30
    maximum_local_rescue_trials: int = 40
    fixed_ranking_model_hypotheses: int = 2
    maximum_rolling_evaluation_submissions: int = 12
    maximum_qlib_calls: int = 260
    maximum_survivors: int = 5

    def validate(self) -> None:
        expected = CrossSectionalBatchBudgetV1()
        if self != expected:
            raise ValueError("Batch 002 frozen budget changed")


@dataclass(frozen=True)
class CrossSectionalDiscoveryBatchSpecV1:
    batch_name: str = "rolling_blind_discovery_batch_002"
    provider_id: str = "tushare-pro-v1"
    evidence_semantics: str = "historical_rolling_evaluation"
    discovery_period: tuple[str, str] = ("2019-01-02", "2021-12-31")
    rolling_window_set_id: str = R3_001_WINDOW_SET_ID
    feature_catalog_id: str = FEATURE_CATALOG_ID
    budgets: CrossSectionalBatchBudgetV1 = field(
        default_factory=CrossSectionalBatchBudgetV1
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
    global_fdr_q: float = 0.10

    def payload(
        self,
        *,
        supervisor_id: str,
        residualization_id: str,
        ranking_model_spec_id: str,
        ranking_label_id: str,
    ) -> dict[str, Any]:
        self.budgets.validate()
        stable = asdict(self) | {
            "schema_version": "cross-sectional-alpha-discovery-batch-v1",
            "supervisor_id": supervisor_id,
            "cross_sectional_style_residualization_id": residualization_id,
            "ranking_model_spec_id": ranking_model_spec_id,
            "ranking_relevance_label_id": ranking_label_id,
            "rolling_evaluation_reads_before_lock": 0,
            "fresh_metric_reads": 0,
            "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0,
            "promotion_writes": 0,
            "automatic_batch_003_created": False,
        }
        return stable | {
            "rolling_blind_discovery_batch_id": "rbdb2_" + hash_payload(stable)
        }


def empty_counts() -> dict[str, int]:
    return {
        "agent_calls": 0,
        "proposals": 0,
        "admissions": 0,
        "rejected_structures": 0,
        "duplicate_structures": 0,
        "local_rescue_trials": 0,
        "model_hypotheses": 0,
        "model_training_calls": 0,
        "qlib_calls": 0,
        "rolling_submissions": 0,
        "rolling_window_evaluations": 0,
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
