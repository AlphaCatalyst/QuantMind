from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


EVIDENCE_CLASSES = {"research_diagnostic", "validation_evidence", "frozen_evidence", "approved"}
TRANSFORMS = {"raw", "cs_rank", "cs_zscore", "winsorized_cs_zscore"}
COMBINATIONS = {"single_factor", "fixed_weight_sum", "equal_weight"}


@dataclass(frozen=True)
class FactorSignalInput:
    template_id: str
    factor_instance_id: str
    factor_values_id: str
    source_artifact_kind: str
    source_artifact_id: str
    source_relative_path: str
    orientation: int
    values_are_oriented: bool
    dataset_id: str
    universe_id: str
    evidence_class: str
    canonicality: str


@dataclass(frozen=True)
class UnifiedSignalSpec:
    schema_version: str
    name: str
    description: str
    inputs: tuple[FactorSignalInput, ...]
    transformation: str
    combination: str
    weights: tuple[float, ...]
    missing_policy: str
    winsor_lower: float | None
    winsor_upper: float | None
    universe_id: str
    dataset_id: str
    start_date: str
    end_date: str
    data_authority: str
    predictive_claim: bool
    eligible_for_production: bool

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["inputs"] = [asdict(item) for item in self.inputs]
        value["weights"] = list(self.weights)
        return value
