from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyOptimizationSpec:
    schema_version: str
    name: str
    description: str
    unified_signal_ids: tuple[str, ...]
    universe_id: str
    qlib_view_id: str
    research_period: dict[str, str]
    retrospective_holdout_periods: dict[str, dict[str, str]]
    search_space: dict[str, tuple[int, ...]]
    budget: dict[str, int]
    execution_contract: dict[str, Any]
    benchmark_policy: dict[str, Any]
    eligibility: dict[str, Any]
    ordering: tuple[dict[str, str], ...]
    evidence_policy: dict[str, Any]
    data_authority: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["unified_signal_ids"] = list(self.unified_signal_ids)
        value["search_space"] = {key: list(items) for key, items in self.search_space.items()}
        value["ordering"] = list(self.ordering)
        return value


@dataclass(frozen=True)
class PlannedStrategyTrial:
    study_id: str
    unified_signal_id: str
    topk: int
    n_drop: int
    rebalance_interval: int
    strategy_spec_id: str
    qlib_result_id: str
    trial_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
