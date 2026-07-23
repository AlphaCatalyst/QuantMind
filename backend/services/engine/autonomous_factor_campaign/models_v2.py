from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


V2_TERMINAL_STATES = {
    "completed_with_holdout_survivors",
    "completed_no_discovery_shortlist",
    "completed_no_holdout_survivor",
    "completed_early_stop",
    "failed_nonrecoverable",
}
V2_STATES = V2_TERMINAL_STATES | {
    "planned", "running", "rounds_stopped", "memory_frozen",
    "shortlist_locked", "holdout_open", "registry_complete",
    "fresh_locks_complete", "paused_recoverable_error",
}


@dataclass(frozen=True)
class CampaignBudgetV2:
    maximum_rounds: int = 12
    maximum_agent_calls: int = 12
    maximum_proposals: int = 36
    maximum_admitted_templates: int = 24
    maximum_local_rescue_trials: int = 48
    maximum_discovery_qlib_calls: int = 100
    maximum_holdout_qlib_calls: int = 12
    maximum_report_qlib_calls: int = 12
    maximum_discovery_shortlist: int = 6
    maximum_final_candidate_locks: int = 3
    maximum_near_miss_reports: int = 6

    def validate(self) -> None:
        ceiling = CampaignBudgetV2()
        for name, maximum in asdict(ceiling).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen v2 campaign bound")
        if self.maximum_rounds < 1 or self.maximum_agent_calls < 1:
            raise ValueError("v2 campaign requires at least one round and Agent call")


@dataclass(frozen=True)
class AutonomousFactorCampaignSpecV2:
    orchestrator_revision: str = "2.0.1"
    campaign_name: str = "technical_factor_campaign_002"
    provider: str = "openai_codex_cli"
    model: str = "gpt-5.6-terra"
    runtime_mode: str = "store_required"
    provider_id: str = "tushare-pro-v1"
    universe: str = "Tushare Fixed-100"
    benchmark: str = "CSI300"
    feature_dataset_id: str = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"
    development_period: tuple[str, str] = ("2019-01-02", "2020-12-31")
    adaptive_discovery_period: tuple[str, str] = ("2021-01-04", "2022-12-30")
    locked_holdout_period: tuple[str, str] = ("2023-01-03", "2024-12-31")
    contaminated_report_periods: tuple[str, ...] = ("2025", "2026H1")
    budgets: CampaignBudgetV2 = field(default_factory=CampaignBudgetV2)
    predictive_claim: bool = False
    fresh_validation: bool = False
    frozen_test: bool = False
    usable_for_production: bool = False

    def payload(self) -> dict[str, Any]:
        self.validate()
        stable = asdict(self)
        stable["schema_version"] = "autonomous-factor-campaign-spec-v2"
        return stable | {"campaign_spec_id": "afc2_" + hash_payload(stable)}

    def validate(self) -> None:
        self.budgets.validate()
        if (self.provider, self.model, self.runtime_mode, self.provider_id) != (
            "openai_codex_cli", "gpt-5.6-terra", "store_required", "tushare-pro-v1"
        ):
            raise ValueError("formal v2 Agent/data authority contract mismatch")
        if any((self.predictive_claim, self.fresh_validation, self.frozen_test, self.usable_for_production)):
            raise ValueError("retrospective holdout cannot claim Fresh or production evidence")


def evidence_partitions() -> dict[str, Any]:
    rows = {
        "development": (True, True, True, True, True, False),
        "adaptive_discovery": (True, True, True, False, True, False),
        "locked_holdout": (False, False, False, False, False, True),
        "contaminated_report": (False, False, False, False, False, False),
        "fresh_forward": (False, False, False, False, False, False),
    }
    fields = (
        "usable_by_agent", "usable_by_planner", "usable_by_failure_memory",
        "usable_for_parameter_selection", "usable_for_shortlist", "usable_for_registry",
    )
    return {
        "schema_version": "campaign-evidence-partition-v1",
        "provider_id": "tushare-pro-v1",
        "partitions": {
            name: {"evidence_partition": name} | dict(zip(fields, values))
            for name, values in rows.items()
        },
        "promotion_writes": 0,
    }


def empty_budget_usage_v2() -> dict[str, int]:
    return {
        "rounds": 0, "agent_calls": 0, "proposals": 0, "admitted_templates": 0,
        "local_rescue_trials": 0, "discovery_qlib_calls": 0,
        "holdout_qlib_calls": 0, "report_qlib_calls": 0,
        "discovery_shortlist": 0, "final_candidate_locks": 0,
        "near_miss_reports": 0, "default_evaluations": 0,
        "development_locks": 0, "discovery_candidates": 0,
        "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
        "tushare_calls": 0, "network_data_calls": 0, "promotion_writes": 0,
        "locked_holdout_reads": 0,
    }
