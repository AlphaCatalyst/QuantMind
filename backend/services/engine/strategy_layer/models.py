from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StrategySpec:
    schema_version: str
    name: str
    description: str
    unified_signal_id: str
    universe_id: str
    qlib_view_id: str
    start_date: str
    end_date: str
    selection: dict[str, Any]
    rebalance: dict[str, Any]
    weighting: dict[str, Any]
    execution: dict[str, Any]
    costs: dict[str, Any]
    benchmark: dict[str, Any]
    quality_gates: dict[str, Any]
    evidence_policy: dict[str, Any]
    data_authority: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
