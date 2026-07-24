from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


ARCHETYPES = {
    "monotonic_rank_factor": {
        "primary_test_statistic": "daily_official_label_rankic",
        "hac_lag": 10,
    },
    "top_tail_selection_factor": {
        "primary_test_statistic": "non_overlapping_top20_universe_10_session_spread",
        "hac_lag": 1,
    },
}
LANES = {
    "trend_geometry_lane": {
        "families": ("multi_horizon_trend", "path_quality", "momentum_acceleration", "drawdown_recovery"),
    },
    "trading_confirmation_lane": {
        "families": ("volume_price_confirmation", "liquidity_normalized_trend", "volatility_conditioned_trend"),
    },
    "relative_asymmetric_lane": {
        "families": ("residual_relative_strength", "path_asymmetry", "cross_family_simple_hybrid"),
    },
}


@dataclass(frozen=True)
class AlphaProgramBudget:
    maximum_lanes: int = 3
    maximum_total_rounds: int = 18
    maximum_agent_calls: int = 18
    maximum_proposals: int = 54
    maximum_admissions: int = 36
    maximum_local_rescue_trials: int = 72
    maximum_adaptive_qlib_calls: int = 180
    maximum_union_shortlist: int = 12
    maximum_validation_qlib_calls: int = 48
    maximum_final_survivors: int = 5
    maximum_near_misses: int = 8
    minimum_rounds_before_improvement_stop: int = 12
    minimum_agent_calls_before_improvement_stop: int = 12
    minimum_distinct_families_before_improvement_stop: int = 7
    minimum_lanes_completed: int = 3
    minimum_admissions_before_improvement_stop: int = 18

    def validate(self) -> None:
        frozen = AlphaProgramBudget()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen Alpha Program bound")
        if self.maximum_lanes != 3:
            raise ValueError("formal Program requires three lanes")


@dataclass(frozen=True)
class AlphaArchetypeContractV1:
    allowed_archetypes: dict[str, dict[str, Any]] = field(default_factory=lambda: ARCHETYPES)
    post_hoc_switch_allowed: bool = False
    one_primary_archetype_per_proposal: bool = True
    global_fdr_q: float = .10

    def payload(self, feature_catalog_v2_id: str) -> dict:
        if self.allowed_archetypes != ARCHETYPES or self.post_hoc_switch_allowed or self.global_fdr_q != .10:
            raise ValueError("Alpha Archetype contract is frozen")
        stable = asdict(self) | {
            "schema_version": "alpha-archetype-contract-v1",
            "provider_id": "tushare-pro-v1",
            "feature_catalog_v2_id": feature_catalog_v2_id,
            "promotion_writes": 0,
        }
        return stable | {"archetype_contract_id": "aac1_" + hash_payload(stable)}


@dataclass(frozen=True)
class ArchetypeAwareAlphaProgramSpecV1:
    orchestrator_revision: str = "1.0.1"
    program_name: str = "technical_alpha_program_002"
    provider: str = "openai_codex_cli"
    model: str = "gpt-5.6-terra"
    runtime_mode: str = "store_required"
    provider_id: str = "tushare-pro-v1"
    universe: str = "Tushare Fixed-100"
    benchmark: str = "CSI300"
    feature_catalog_v2_id: str = ""
    adaptive_research_period: tuple[str, str] = ("2019-01-02", "2020-12-31")
    locked_validation_period: tuple[str, str] = ("2021-01-04", "2024-12-31")
    contaminated_report_periods: tuple[str, ...] = ("2025", "2026H1")
    lanes: dict[str, dict[str, Any]] = field(default_factory=lambda: LANES)
    budgets: AlphaProgramBudget = field(default_factory=AlphaProgramBudget)
    fdr_q: float = .10
    strategy_protocol: dict[str, Any] = field(default_factory=lambda: {
        "topk": 20, "n_drop": 5, "rebalance_interval": 10,
        "weighting": "equal_weight", "signal_lag": 1,
        "execution": "open", "benchmark": "CSI300",
    })
    predictive_claim: bool = False
    fresh_validation: bool = False
    usable_for_production: bool = False

    def payload(self) -> dict:
        self.budgets.validate()
        if not self.feature_catalog_v2_id:
            raise ValueError("frozen Technical Feature Catalog v2 is required")
        if self.lanes != LANES or self.fdr_q != .10:
            raise ValueError("Alpha Program lane/FDR contract is frozen")
        if any((self.predictive_claim, self.fresh_validation, self.usable_for_production)):
            raise ValueError("retrospective Program cannot claim production evidence")
        stable = asdict(self) | {"schema_version": "archetype-aware-alpha-program-spec-v1"}
        return stable | {"program_spec_id": "aap1_" + hash_payload(stable)}


def empty_usage() -> dict[str, int]:
    return {
        "rounds": 0, "agent_calls": 0, "proposals": 0, "admissions": 0,
        "local_rescue_trials": 0, "adaptive_qlib_calls": 0,
        "validation_objects": 0, "validation_qlib_calls": 0,
        "report_qlib_calls": 0, "final_survivors": 0,
        "locked_validation_reads": 0, "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
        "tushare_calls": 0, "network_data_calls": 0, "promotion_writes": 0,
        "manual_intervention_count": 0, "manual_alpha_round_planning_count": 0,
        "manual_archetype_switching_count": 0,
    }
