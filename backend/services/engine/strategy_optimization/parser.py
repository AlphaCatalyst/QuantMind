from __future__ import annotations

from typing import Any, Mapping

from .errors import StrategyOptimizationError
from .models import StrategyOptimizationSpec

FIELDS = {
    "schema_version", "name", "description", "unified_signal_ids", "universe_id", "qlib_view_id",
    "research_period", "retrospective_holdout_periods", "search_space", "budget",
    "execution_contract", "benchmark_policy", "eligibility", "ordering", "evidence_policy",
    "data_authority",
}
TOPK = (10, 20, 30)
N_DROP = (0, 5, 10)
REBALANCE = (1, 5, 10)
FORMAL_CHAIN = ("QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange")


def _reject(condition: bool, message: str, code: str = "STRATEGY_OPTIMIZATION_INVALID") -> None:
    if condition:
        raise StrategyOptimizationError(message, code=code)


def parse_optimization_spec(value: Mapping[str, Any]) -> StrategyOptimizationSpec:
    _reject(set(value) != FIELDS, f"StrategyOptimizationSpec fields invalid: unknown={sorted(set(value)-FIELDS)} missing={sorted(FIELDS-set(value))}")
    _reject(value["schema_version"] != "1.0.0", "strategy optimization schema version is unsupported")
    _reject(value["data_authority"] != "tushare-pro-v1", "legacy authority forbidden", "LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    signals = tuple(value["unified_signal_ids"])
    _reject(len(signals) != 4 or len(set(signals)) != 4 or any(not str(x).startswith("usa_") for x in signals), "exactly four distinct Unified Signal IDs are required")
    _reject(value["research_period"] != {"start": "2019-01-02", "end": "2024-12-31"}, "research period is frozen")
    _reject(value["retrospective_holdout_periods"] != {
        "2025": {"start": "2025-01-02", "end": "2025-12-30"},
        "2026H1": {"start": "2026-01-05", "end": "2026-06-23"},
    }, "retrospective report periods are frozen")
    search = value["search_space"]
    _reject(set(search) != {"topk", "n_drop", "rebalance_interval"}, "only topk, n_drop and rebalance_interval may be searched")
    normalized_search = {key: tuple(int(x) for x in search[key]) for key in search}
    _reject(normalized_search != {"topk": TOPK, "n_drop": N_DROP, "rebalance_interval": REBALANCE}, "search space differs from the frozen v1 grid")
    _reject(value["budget"] != {"max_trials_per_signal": 24, "max_total_trials": 96}, "search budget is frozen")
    execution = dict(value["execution_contract"])
    expected_execution = {
        "weighting": "equal_weight", "signal_transform": "existing_unified_signal",
        "signal_lag_trade_dates": 1, "execution_price": "open", "cost_contract": "existing_formal_cn_exchange",
        "chain": list(FORMAL_CHAIN), "calendar": "qlib_trade_calendar",
    }
    _reject(execution != expected_execution, "fixed execution contract changed")
    benchmark = dict(value["benchmark_policy"])
    _reject(benchmark != {"selection_benchmark": "SH000300", "canonicality": "canonical", "fixed_100_usable_for_selection": False}, "canonical CSI300-only selection is required")
    _reject(dict(value["eligibility"]) != {
        "minimum_valid_years": 6, "minimum_average_holdings_ratio": 0.8,
        "require_finite_metrics": True, "allow_nav_fill": False,
    }, "eligibility gate is frozen")
    evidence = dict(value["evidence_policy"])
    expected_evidence = {
        "evidence_class": "retrospective_contaminated_strategy_parameter_diagnostic",
        "predictive_claim": False, "usable_for_research": True,
        "usable_for_parameter_selection": "research_only", "usable_for_promotion": False,
        "eligible_for_production": False,
    }
    _reject(evidence != expected_evidence, "research-only evidence policy changed")
    ordering = tuple(dict(item) for item in value["ordering"])
    expected_order = (
        {"field": "positive_excess_year_count", "direction": "desc"},
        {"field": "median_annual_net_excess", "direction": "desc"},
        {"field": "worst_annual_net_excess", "direction": "desc"},
        {"field": "sharpe_ratio", "direction": "desc"},
        {"field": "maximum_drawdown_abs", "direction": "asc"},
        {"field": "turnover", "direction": "asc"},
        {"field": "transaction_cost", "direction": "asc"},
        {"field": "trial_id", "direction": "asc"},
    )
    _reject(ordering != expected_order, "candidate ordering is frozen")
    return StrategyOptimizationSpec(
        **{**value, "unified_signal_ids": signals, "search_space": normalized_search,
           "ordering": ordering, "execution_contract": execution, "benchmark_policy": benchmark,
           "evidence_policy": evidence}
    )
