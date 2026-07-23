from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


LANES = {
    "trend_structure_lane": {
        "families": (
            "multi_horizon_trend", "pullback_continuation",
            "path_quality", "momentum_acceleration",
        ),
        "objective": "cross-horizon consistent and path-stable trend structures",
    },
    "trading_confirmation_lane": {
        "families": (
            "volume_price_confirmation", "liquidity_normalized_trend",
            "volatility_conditioned_trend",
        ),
        "objective": "volume, liquidity and volatility confirmation of price trend",
    },
    "recovery_relative_lane": {
        "families": (
            "drawdown_recovery", "residual_relative_strength",
            "cross_family_simple_hybrid",
        ),
        "objective": "trend recovery, residual strength and simple cross-family structure",
    },
}

TERMINAL_STATES = {
    "completed_with_survivors", "completed_no_lane_shortlist",
    "completed_no_validation_survivor", "completed_early_stop",
    "failed_nonrecoverable",
}
PROGRAM_STATES = TERMINAL_STATES | {
    "planned", "running_adaptive_research", "adaptive_research_complete",
    "union_shortlist_locked", "running_locked_validation",
    "paused_recoverable_error",
}


@dataclass(frozen=True)
class ProgramBudget:
    maximum_lanes: int = 3
    maximum_total_rounds: int = 24
    maximum_agent_calls: int = 24
    maximum_proposals: int = 72
    maximum_admissions: int = 48
    maximum_local_rescue_trials: int = 96
    maximum_adaptive_qlib_calls: int = 220
    maximum_validation_objects: int = 12
    maximum_validation_qlib_calls: int = 48
    maximum_report_qlib_calls: int = 20
    maximum_final_survivors: int = 5
    maximum_near_misses: int = 8
    maximum_lane_agent_calls: int = 9
    maximum_family_rounds: int = 4
    minimum_rounds_before_improvement_stop: int = 12
    minimum_agent_calls_before_improvement_stop: int = 12
    minimum_distinct_families_before_improvement_stop: int = 6
    minimum_lanes_with_completed_rounds: int = 3
    minimum_admissions_before_improvement_stop: int = 16

    def validate(self) -> None:
        frozen = ProgramBudget()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen Program bound")
        if self.maximum_lanes != 3:
            raise ValueError("formal Program requires exactly three pre-registered lanes")


@dataclass(frozen=True)
class AutonomousFactorResearchProgramSpecV1:
    orchestrator_revision: str = "1.0.0"
    program_name: str = "technical_factor_program_001"
    provider: str = "openai_codex_cli"
    model: str = "gpt-5.6-terra"
    runtime_mode: str = "store_required"
    provider_id: str = "tushare-pro-v1"
    universe: str = "Tushare Fixed-100"
    benchmark: str = "CSI300"
    feature_dataset_id: str = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"
    adaptive_research_period: tuple[str, str] = ("2019-01-02", "2020-12-31")
    locked_validation_period: tuple[str, str] = ("2021-01-04", "2024-12-31")
    contaminated_report_periods: tuple[str, ...] = ("2025", "2026H1")
    lanes: dict[str, dict[str, Any]] = field(default_factory=lambda: LANES)
    budgets: ProgramBudget = field(default_factory=ProgramBudget)
    hac_lag: int = 10
    fdr_q: float = 0.10
    predictive_claim: bool = False
    fresh_validation: bool = False
    frozen_test: bool = False
    usable_for_production: bool = False

    def validate(self) -> None:
        self.budgets.validate()
        if set(self.lanes) != set(LANES):
            raise ValueError("all three Lane Specs must be frozen together")
        if (self.provider, self.model, self.runtime_mode, self.provider_id) != (
            "openai_codex_cli", "gpt-5.6-terra", "store_required", "tushare-pro-v1"
        ):
            raise ValueError("formal Program provider/data contract mismatch")
        if self.hac_lag != 10 or self.fdr_q != .10:
            raise ValueError("HAC/FDR policy is frozen")
        if any((self.predictive_claim, self.fresh_validation, self.frozen_test, self.usable_for_production)):
            raise ValueError("retrospective Program cannot claim predictive or production evidence")

    def payload(self) -> dict[str, Any]:
        self.validate()
        stable = asdict(self)
        stable["schema_version"] = "autonomous-factor-research-program-spec-v1"
        return stable | {"program_spec_id": "afrp1_" + hash_payload(stable)}


def evidence_partitions() -> dict:
    rows = {
        "adaptive_research": (True, True, True, True, True, False),
        "locked_validation": (False, False, False, False, False, True),
        "contaminated_report": (False, False, False, False, False, False),
        "fresh_forward": (False, False, False, False, False, False),
    }
    fields = (
        "usable_by_agent", "usable_by_planner", "usable_by_failure_memory",
        "usable_for_parameter_selection", "usable_for_shortlist", "usable_for_registry",
    )
    return {
        "schema_version": "research-program-evidence-partition-v1",
        "provider_id": "tushare-pro-v1",
        "partitions": {
            name: {"evidence_partition": name} | dict(zip(fields, flags))
            for name, flags in rows.items()
        },
        "promotion_writes": 0,
    }


def empty_usage() -> dict[str, int]:
    return {
        "rounds": 0, "agent_calls": 0, "proposals": 0, "admissions": 0,
        "local_rescue_trials": 0, "adaptive_qlib_calls": 0,
        "validation_objects": 0, "validation_qlib_calls": 0,
        "report_qlib_calls": 0, "final_survivors": 0, "near_misses": 0,
        "locked_validation_reads": 0, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "tushare_calls": 0,
        "network_data_calls": 0, "promotion_writes": 0,
        "manual_intervention_count": 0, "manual_round_planning_count": 0,
        "manual_lane_switching_count": 0,
    }
