from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OptimizationEvidenceClass(str, Enum):
    DEFAULT_PARAMETERS = "default_parameters"
    LOCAL_OPTIMIZATION_RESEARCH = "local_optimization_research"
    FULL_SEARCH_DIAGNOSTIC = "full_search_diagnostic"
    HISTORICAL_LEGACY_OPTIMIZATION = "historical_legacy_optimization"


EVIDENCE_RISK_ORDER = (
    OptimizationEvidenceClass.DEFAULT_PARAMETERS.value,
    OptimizationEvidenceClass.LOCAL_OPTIMIZATION_RESEARCH.value,
    OptimizationEvidenceClass.FULL_SEARCH_DIAGNOSTIC.value,
)


class OptimizationGovernanceError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}{': ' + detail if detail else ''}")


@dataclass(frozen=True)
class GovernedSelection:
    selected_parameters: dict[str, Any]
    selection_reason: str
    evidence_class: str
    default_passed: bool
    optimization_rescued: bool
    trial_count: int
    optimization_calls: int
    default_metrics: dict[str, Any]
    default_failure_reasons: tuple[str, ...]
    local_trials: tuple[dict[str, Any], ...]
    research_gain: dict[str, Any] | None
    parameter_neighborhood: tuple[dict[str, Any], ...]
    usable_for_candidate_selection: bool
    usable_for_promotion: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_parameters": self.selected_parameters,
            "selection_reason": self.selection_reason,
            "evidence_class": self.evidence_class,
            "default_passed": self.default_passed,
            "optimization_rescued": self.optimization_rescued,
            "trial_count": self.trial_count,
            "optimization_calls": self.optimization_calls,
            "default_metrics": self.default_metrics,
            "default_failure_reasons": list(self.default_failure_reasons),
            "local_trials": list(self.local_trials),
            "research_gain": self.research_gain,
            "parameter_neighborhood": list(self.parameter_neighborhood),
            "usable_for_candidate_selection": self.usable_for_candidate_selection,
            "usable_for_promotion": self.usable_for_promotion,
        }
