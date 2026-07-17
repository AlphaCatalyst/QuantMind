from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Tuple


@dataclass(frozen=True)
class ResearchGoal:
    goal_id: str
    name: str
    objective: str
    dataset_kind: str
    allowed_features: Tuple[str, ...]
    allowed_operators: Tuple[str, ...]
    allowed_parameter_roles: Tuple[str, ...]
    maximum_templates: int
    maximum_trials: int
    maximum_iterations: int
    novelty_requirement: str
    constraints: Tuple[str, ...]


@dataclass(frozen=True)
class ResearchCampaignBudget:
    max_iterations: int = 3
    max_agent_calls: int = 4
    max_proposals_per_iteration: int = 4
    max_total_admitted_templates: int = 8
    max_total_trials: int = 64
    max_failed_proposals: int = 8
    max_failed_trials: int = 16
    max_agent_repair_attempts_per_call: int = 1

    def validate(self):
        hard = {"max_iterations": 3, "max_agent_calls": 4, "max_proposals_per_iteration": 4,
                "max_total_admitted_templates": 8, "max_total_trials": 64, "max_failed_proposals": 8,
                "max_failed_trials": 16, "max_agent_repair_attempts_per_call": 1}
        for name, maximum in hard.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
                raise ValueError(f"{name} exceeds the frozen campaign bound")
        if self.max_iterations < 1 or self.max_agent_calls < 1:
            raise ValueError("campaign requires at least one iteration and Agent call")


@dataclass(frozen=True)
class ResearchAgentRequest:
    goal: Mapping[str, Any]
    sanitized_memory: Mapping[str, Any]
    contract: Mapping[str, Any]


@dataclass(frozen=True)
class ResearchAgentResponse:
    raw_response: str
    provider_id: str
    model_id: str
    usage_summary: Optional[Mapping[str, Any]] = None


class ResearchAgent(Protocol):
    provider_id: str
    model_id: str

    def propose(self, request: ResearchAgentRequest) -> ResearchAgentResponse: ...


@dataclass(frozen=True)
class CampaignConfig:
    campaign_root: str
    snapshot_root: str
    snapshot_id: str
    validation_root: str
    validation_dataset_id: str
    registry_root: str
    registry_snapshot_id: str
    factor_values_root: str
    optimization_root: str
    existing_optimization_root: Optional[str] = None
    registry_output_root: Optional[str] = None
