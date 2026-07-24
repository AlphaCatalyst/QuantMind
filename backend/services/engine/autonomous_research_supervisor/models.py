from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


FRESH_STATES = {
    "fresh_locked",
    "fresh_evidence_accumulating",
    "fresh_supported",
    "fresh_rejected",
    "fresh_inconclusive",
    "fresh_data_blocked",
}


@dataclass(frozen=True)
class SupervisorBudget:
    maximum_research_cycles_per_run: int = 2
    maximum_feature_factory_runs_per_cycle: int = 1
    maximum_alpha_program_runs_per_cycle: int = 1
    maximum_agent_calls_per_cycle: int = 18
    maximum_proposals_per_cycle: int = 54
    maximum_admissions_per_cycle: int = 36
    maximum_qlib_calls_per_cycle: int = 240
    maximum_new_retrospective_candidates_per_cycle: int = 10
    maximum_active_fresh_candidates: int = 20
    maximum_fresh_cohort_size: int = 10

    def validate(self) -> None:
        frozen = SupervisorBudget()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen Supervisor bound")


@dataclass(frozen=True)
class AutonomousResearchSupervisorSpecV1:
    supervisor_name: str = "quantmind_autonomous_research_supervisor_001"
    provider_id: str = "tushare-pro-v1"
    evidence_semantics: str = "retrospective_research_only"
    global_fdr_q: float = 0.10
    minimum_fresh_evidence: dict[str, Any] = field(default_factory=lambda: {
        "fresh_trading_days": 60,
        "completed_non_overlapping_holding_windows": 5,
        "rebalance_periods": 3,
        "finite_coverage": 0.90,
        "pit_violations": 0,
    })
    budgets: SupervisorBudget = field(default_factory=SupervisorBudget)
    promotion_allowed: bool = False
    automatic_trading_allowed: bool = False

    def payload(self) -> dict[str, Any]:
        self.budgets.validate()
        if self.global_fdr_q != 0.10:
            raise ValueError("Supervisor FDR policy is frozen")
        if self.promotion_allowed or self.automatic_trading_allowed:
            raise ValueError("Supervisor cannot promote or trade")
        stable = asdict(self) | {
            "schema_version": "autonomous-research-supervisor-spec-v1",
            "credential_source": "environment_only_not_persisted",
            "no_backfill": True,
            "promotion_writes": 0,
        }
        return stable | {"supervisor_spec_id": "arsv1_" + hash_payload(stable)}


def runtime_counts() -> dict[str, int]:
    return {
        "research_cycles": 0,
        "feature_agent_calls": 0,
        "alpha_agent_calls": 0,
        "proposals": 0,
        "admissions": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "feature_writes": 0,
        "candidate_writes": 0,
        "fresh_lock_writes": 0,
        "fresh_observation_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
    }
