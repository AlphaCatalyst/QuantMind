from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


class QuantGPTContractError(ValueError):
    """Raised when a QuantGPT payload cannot satisfy the QuantMind contract."""


@dataclass(frozen=True)
class QuantGPTEvaluationRequest:
    expression: str
    universe: str
    start_date: str
    end_date: str
    n_groups: int = 5
    holding_period: int = 5
    neutralize_industry: bool = True
    neutralize_cap: bool = True


@dataclass(frozen=True)
class QuantGPTCandidateMetrics:
    score: float | None
    grade: str | None
    rank_ic_mean: float | None
    ic_ir: float | None
    turnover: float | None
    wq_fitness: float | None
    monotonicity_score: float | None
    anti_overfit_score: float | None
    coverage_days: int | None
    total_stock_count: int | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuantGPTEvaluation:
    task_id: str | None
    expression: str | None
    status: str
    metrics: QuantGPTCandidateMetrics | None
    params: dict[str, Any]
    report_url: str | None
    invalid_symbol_count: int = 0
    normalized_stock_factor_data: list[dict[str, Any]] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FactorValueRow:
    trade_date: date
    symbol: str
    factor_value: float


@dataclass(frozen=True)
class FactorValuesParseResult:
    expression: str | None
    universe: str | None
    start_date: str | None
    end_date: str | None
    rows: list[FactorValueRow]
    invalid_symbol_count: int
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromotionPolicy:
    min_abs_rank_ic: float = 0.015
    min_ic_ir: float = 0.15
    max_turnover: float = 0.35
    min_monotonicity_score: float = 0.6
    min_anti_overfit_score: float = 60.0
    min_coverage_days: int = 120
    max_existing_feature_corr: float = 0.85


@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    reasons: list[str]


@dataclass(frozen=True)
class FactorSignalConfig:
    tenant_id: str
    user_id: str
    run_id: str
    top_n: int = 20
    bottom_n: int = 0
    long_short: bool = False
    quantity: int = 100
    signal_source: str = "quantgpt_factor"
