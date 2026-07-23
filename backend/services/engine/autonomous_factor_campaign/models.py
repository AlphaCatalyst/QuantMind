from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


TERMINAL_STATES = {
    "completed_with_candidates", "completed_no_candidate", "completed_early_stop",
    "failed_nonrecoverable",
}
CAMPAIGN_STATES = TERMINAL_STATES | {
    "planned", "running", "paused_recoverable_error", "paused_budget",
}
ROUND_THEMES = (
    "multi_horizon_trend", "path_quality", "momentum_acceleration",
    "pullback_continuation", "drawdown_recovery", "residual_relative_strength",
    "volatility_conditioned_trend", "volume_price_confirmation",
    "liquidity_normalized_trend", "cross_family_simple_hybrid",
)
FAILURE_TAXONOMY = (
    "invalid_dsl", "missing_feature", "pit_violation", "insufficient_coverage",
    "semantic_mismatch", "duplicate_structure", "duplicate_signal",
    "weak_predictive_signal", "negative_spread", "non_monotonic", "high_turnover",
    "cost_drag", "annual_instability", "benchmark_only_exposure",
    "return_concentration", "parameter_fragility", "regime_specific_only",
    "correlation_redundancy", "report_period_degradation",
)


@dataclass(frozen=True)
class CampaignBudget:
    maximum_rounds: int = 12
    maximum_agent_calls: int = 12
    maximum_proposals: int = 36
    maximum_admitted_templates: int = 24
    maximum_local_rescue_trials: int = 48
    maximum_formal_qlib_calls: int = 140
    maximum_candidate_locks: int = 5
    maximum_near_miss_reports: int = 5

    def validate(self) -> None:
        frozen = CampaignBudget()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen campaign bound")
        if self.maximum_rounds < 1 or self.maximum_agent_calls < 1:
            raise ValueError("campaign requires at least one round and Agent call")


@dataclass(frozen=True)
class AutonomousFactorCampaignSpecV1:
    orchestrator_revision: str = "1.0.6"
    campaign_name: str = "technical_factor_campaign_001"
    provider: str = "openai_codex_cli"
    model: str = "gpt-5.6-terra"
    runtime_mode: str = "store_required"
    provider_id: str = "tushare-pro-v1"
    universe: str = "Tushare Fixed-100"
    benchmark: str = "CSI300"
    feature_dataset_id: str = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"
    development_period: tuple[str, str] = ("2019-01-02", "2020-12-31")
    annual_selection_years: tuple[str, ...] = ("2021", "2022", "2023", "2024")
    report_periods: tuple[str, ...] = ("2025", "2026H1")
    budgets: CampaignBudget = field(default_factory=CampaignBudget)
    predictive_claim: bool = False
    fresh_validation: bool = False
    frozen_test: bool = False
    usable_for_production: bool = False

    def payload(self) -> dict[str, Any]:
        self.validate()
        stable = asdict(self)
        stable["schema_version"] = "autonomous-factor-campaign-spec-v1"
        return stable | {"campaign_spec_id": "afc1_" + hash_payload(stable)}

    def validate(self) -> None:
        self.budgets.validate()
        if self.provider != "openai_codex_cli" or self.model != "gpt-5.6-terra":
            raise ValueError("formal Agent provider/model contract mismatch")
        if self.runtime_mode != "store_required" or self.provider_id != "tushare-pro-v1":
            raise ValueError("authority/runtime contract mismatch")
        if any((self.predictive_claim, self.fresh_validation, self.frozen_test, self.usable_for_production)):
            raise ValueError("retrospective campaign cannot claim production or Fresh evidence")


def empty_budget_usage() -> dict[str, int]:
    return {
        "rounds": 0, "agent_calls": 0, "proposals": 0, "admitted_templates": 0,
        "local_rescue_trials": 0, "formal_qlib_calls": 0, "candidate_locks": 0,
        "near_miss_reports": 0, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "tushare_calls": 0,
        "network_data_calls": 0, "promotion_writes": 0,
        "default_evaluations": 0, "annual_evaluations": 0,
        "local_rescues": 0, "duplicate_rejections": 0,
        "cheap_screen_rejections": 0,
        "eligible_candidates": 0,
    }
