from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from backend.services.engine.factor_dsl.models import SnapshotContract
from backend.services.engine.tushare_cutover.canonical import hash_payload


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    source_columns: tuple[str, ...]
    canonical_formula: str
    lookback: int
    min_periods: int
    ddof: int | None
    adjustment_semantics: str
    missing_policy: str = "propagate_no_fill"
    grouping: str = "symbol"
    sort_order: str = "symbol,trade_date ascending"
    pit_statement: str = "uses only the current and earlier trade dates"
    dtype: str = "float32"


DEFINITIONS = (
    FeatureDefinition("mom_ret_1d", ("adjusted_close",), "adjusted_close / lag(adjusted_close,1) - 1", 1, 2, None, "adjusted"),
    FeatureDefinition("mom_ret_5d", ("adjusted_close",), "adjusted_close / lag(adjusted_close,5) - 1", 5, 6, None, "adjusted"),
    FeatureDefinition("mom_ret_20d", ("adjusted_close",), "adjusted_close / lag(adjusted_close,20) - 1", 20, 21, None, "adjusted"),
    FeatureDefinition("mom_ret_60d", ("adjusted_close",), "adjusted_close / lag(adjusted_close,60) - 1", 60, 61, None, "adjusted"),
    FeatureDefinition("price_vs_ma_5", ("adjusted_close",), "adjusted_close / rolling_mean(adjusted_close,5) - 1", 5, 5, None, "adjusted"),
    FeatureDefinition("price_vs_ma_20", ("adjusted_close",), "adjusted_close / rolling_mean(adjusted_close,20) - 1", 20, 20, None, "adjusted"),
    FeatureDefinition("price_vs_ma_60", ("adjusted_close",), "adjusted_close / rolling_mean(adjusted_close,60) - 1", 60, 60, None, "adjusted"),
    FeatureDefinition("volatility_5d", ("adjusted_close",), "rolling_std(mom_ret_1d,5,ddof=0)", 5, 5, 0, "adjusted"),
    FeatureDefinition("volatility_20d", ("adjusted_close",), "rolling_std(mom_ret_1d,20,ddof=0)", 20, 20, 0, "adjusted"),
    FeatureDefinition("volatility_60d", ("adjusted_close",), "rolling_std(mom_ret_1d,60,ddof=0)", 60, 60, 0, "adjusted"),
    FeatureDefinition("downside_volatility_20d", ("adjusted_close",), "sqrt(rolling_mean(min(mom_ret_1d,0)^2,20))", 20, 20, 0, "adjusted"),
    FeatureDefinition("style_beta_20", ("adjusted_close", "CSI300.close"), "rolling_cov(mom_ret_1d,csi300_ret,20,ddof=0)/rolling_var(csi300_ret,20,ddof=0)", 20, 20, 0, "adjusted_and_csi300"),
    FeatureDefinition("style_beta_60", ("adjusted_close", "CSI300.close"), "rolling_cov(mom_ret_1d,csi300_ret,60,ddof=0)/rolling_var(csi300_ret,60,ddof=0)", 60, 60, 0, "adjusted_and_csi300"),
    FeatureDefinition("style_idio_vol_20", ("adjusted_close", "CSI300.close"), "rolling_std(mom_ret_1d-style_beta_20*csi300_ret,20,ddof=0)", 39, 20, 0, "adjusted_and_csi300"),
    FeatureDefinition("style_idio_vol_60", ("adjusted_close", "CSI300.close"), "rolling_std(mom_ret_1d-style_beta_60*csi300_ret,60,ddof=0)", 119, 60, 0, "adjusted_and_csi300"),
    FeatureDefinition("liq_volume_ratio_5", ("vol",), "vol/rolling_mean(vol,5)", 5, 5, None, "raw_volume"),
    FeatureDefinition("liq_volume_ratio_20", ("vol",), "vol/rolling_mean(vol,20)", 20, 20, None, "raw_volume"),
    FeatureDefinition("amount_ratio_5", ("amount",), "amount/rolling_mean(amount,5)", 5, 5, None, "raw_amount_thousand_cny"),
    FeatureDefinition("amount_ratio_20", ("amount",), "amount/rolling_mean(amount,20)", 20, 20, None, "raw_amount_thousand_cny"),
    FeatureDefinition("turnover_mean_5", ("turnover_rate",), "rolling_mean(turnover_rate,5)", 5, 5, None, "raw_daily_basic"),
    FeatureDefinition("turnover_mean_20", ("turnover_rate",), "rolling_mean(turnover_rate,20)", 20, 20, None, "raw_daily_basic"),
    FeatureDefinition("amihud_illiquidity_20", ("adjusted_close", "amount"), "rolling_mean(abs(mom_ret_1d)/(amount*1000),20)", 20, 20, None, "adjusted_return_raw_amount_cny"),
    FeatureDefinition("gap_return_1d", ("adjusted_open", "adjusted_close"), "adjusted_open/lag(adjusted_close,1)-1", 1, 2, None, "adjusted"),
    FeatureDefinition("intraday_range_1d", ("adjusted_high", "adjusted_low", "adjusted_open"), "(adjusted_high-adjusted_low)/adjusted_open", 1, 1, None, "adjusted"),
    FeatureDefinition("close_location_1d", ("adjusted_close", "adjusted_high", "adjusted_low"), "(adjusted_close-adjusted_low)/(adjusted_high-adjusted_low)", 1, 1, None, "adjusted"),
    FeatureDefinition("log_circ_mv", ("circ_mv",), "log(circ_mv)", 1, 1, None, "raw_daily_basic"),
)

LEGACY_REQUIRED = ("mom_ret_1d", "liq_volume_ratio_5", "style_beta_20", "style_idio_vol_20")


def _safe_div(left: pd.Series, right: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(right, errors="coerce")
    return pd.to_numeric(left, errors="coerce").div(denominator.where(denominator.abs() > 1e-12))


def _rolling(series: pd.Series, window: int, operation: str) -> pd.Series:
    grouped = series.groupby(series.index.get_level_values(0), sort=False)
    rolling = grouped.rolling(window, min_periods=window)
    value = getattr(rolling, operation)() if operation != "std" else rolling.std(ddof=0)
    return value.reset_index(level=0, drop=True)


def compute_feature_candidates(normalized: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    frame = normalized.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["symbol", "trade_date"], kind="mergesort").set_index(["symbol", "trade_date"])
    close = frame["adjusted_close"]
    returns = close.groupby(level=0, sort=False).pct_change(fill_method=None)
    market = benchmark.copy()
    market["trade_date"] = pd.to_datetime(market["trade_date"])
    market = market.sort_values("trade_date", kind="mergesort")
    market_return = market.set_index("trade_date")["close"].pct_change(fill_method=None)
    market_aligned = pd.Series(
        frame.index.get_level_values(1).map(market_return), index=frame.index, dtype="float64"
    )
    result = pd.DataFrame(index=frame.index)
    result["mom_ret_1d"] = returns
    for window in (5, 20, 60):
        result[f"mom_ret_{window}d"] = close.groupby(level=0, sort=False).pct_change(window, fill_method=None)
        result[f"price_vs_ma_{window}"] = _safe_div(close, _rolling(close, window, "mean")) - 1.0
        result[f"volatility_{window}d"] = _rolling(returns, window, "std")
    downside = returns.clip(upper=0).pow(2)
    result["downside_volatility_20d"] = _rolling(downside, 20, "mean").pow(0.5)
    for window in (20, 60):
        mean_stock = _rolling(returns, window, "mean")
        mean_market = _rolling(market_aligned, window, "mean")
        covariance = _rolling(returns * market_aligned, window, "mean") - mean_stock * mean_market
        variance = _rolling(market_aligned.pow(2), window, "mean") - mean_market.pow(2)
        beta = _safe_div(covariance, variance)
        result[f"style_beta_{window}"] = beta
        residual = returns - beta * market_aligned
        result[f"style_idio_vol_{window}"] = _rolling(residual, window, "std")
    for window in (5, 20):
        result[f"liq_volume_ratio_{window}"] = _safe_div(frame["vol"], _rolling(frame["vol"], window, "mean"))
        result[f"amount_ratio_{window}"] = _safe_div(frame["amount"], _rolling(frame["amount"], window, "mean"))
        result[f"turnover_mean_{window}"] = _rolling(frame["turnover_rate"], window, "mean")
    amihud = _safe_div(returns.abs(), frame["amount"] * 1000.0)
    result["amihud_illiquidity_20"] = _rolling(amihud, 20, "mean")
    prior_close = close.groupby(level=0, sort=False).shift(1)
    result["gap_return_1d"] = _safe_div(frame["adjusted_open"], prior_close) - 1.0
    result["intraday_range_1d"] = _safe_div(
        frame["adjusted_high"] - frame["adjusted_low"], frame["adjusted_open"]
    )
    result["close_location_1d"] = _safe_div(
        frame["adjusted_close"] - frame["adjusted_low"],
        frame["adjusted_high"] - frame["adjusted_low"],
    )
    result["log_circ_mv"] = np.log(frame["circ_mv"].where(frame["circ_mv"] > 0))
    result = result.replace([np.inf, -np.inf], np.nan).reset_index()
    return result.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)


def _max_missing_streak(series: pd.Series) -> int:
    missing = series.isna()
    if not missing.any():
        return 0
    groups = missing.ne(missing.shift()).cumsum()
    return int(missing.groupby(groups).sum().max())


def quality_and_selection(candidates: pd.DataFrame, maximum_features: int = 24) -> tuple[dict, tuple[str, ...]]:
    output = candidates[candidates["trade_date"].between("2019-01-02", "2026-06-23")].copy()
    names = [item.name for item in DEFINITIONS]
    quality: dict[str, dict] = {}
    for name in names:
        values = pd.to_numeric(output[name], errors="coerce")
        annual = {
            str(year): float(values[output["trade_date"].dt.year == year].notna().mean())
            for year in range(2019, 2027)
        }
        per_symbol = output.assign(_finite=values.notna()).groupby("symbol")["_finite"].mean()
        first = output.loc[values.notna(), "trade_date"].min()
        dispersion = output.assign(_value=values).groupby("trade_date")["_value"].std(ddof=0)
        quality[name] = {
            "finite_coverage": float(values.notna().mean()),
            "annual_coverage": annual,
            "minimum_symbol_coverage": float(per_symbol.min()),
            "maximum_missing_streak": int(output.assign(_value=values).sort_values(["symbol", "trade_date"]).groupby("symbol")["_value"].apply(_max_missing_streak).max()),
            "first_valid_date": None if pd.isna(first) else first.strftime("%Y-%m-%d"),
            "year_boundary_missingness": {
                str(year): float(values[(output["trade_date"].dt.year == year) & (output["trade_date"].dt.dayofyear <= 15)].isna().mean())
                for year in range(2019, 2027)
            },
            "mean_cross_sectional_dispersion": float(dispersion.mean()),
            "infinity_count": 0,
            "quality_passed": bool(
                values.notna().mean() >= 0.90
                and all(annual[str(year)] >= 0.85 for year in range(2021, 2025))
            ),
        }
    correlations = output[names].corr(method="spearman", min_periods=500)
    selected = list(LEGACY_REQUIRED)
    eligible = [name for name in names if quality[name]["quality_passed"] and name not in selected]
    while eligible and len(selected) < maximum_features:
        def key(name: str) -> tuple:
            maximum = max((abs(float(correlations.loc[name, prior])) for prior in selected if not pd.isna(correlations.loc[name, prior])), default=0.0)
            return (quality[name]["finite_coverage"], -maximum, -next(i for i, item in enumerate(names) if item == name), name)
        choice = max(eligible, key=key)
        selected.append(choice)
        eligible.remove(choice)
    selected = tuple(selected[:maximum_features])
    correlation_payload = {
        left: {right: None if pd.isna(correlations.loc[left, right]) else float(correlations.loc[left, right]) for right in names}
        for left in names
    }
    payload = {
        "schema_version": "tushare-feature-quality-v2",
        "feature_count_computed": len(names),
        "feature_limit": maximum_features,
        "selected_features": list(selected),
        "rejected_features": [name for name in names if name not in selected],
        "features": quality,
        "correlation_matrix": correlation_payload,
        "duplicate_key_count": int(output.duplicated(["symbol", "trade_date"]).sum()),
        "infinity_count": 0,
    }
    return payload, selected


def feature_contract(selected: tuple[str, ...]) -> dict:
    definitions = {item.name: item for item in DEFINITIONS}
    rows = []
    for name in selected:
        item = definitions[name]
        rows.append({
            "feature_name": item.name,
            "source_columns": list(item.source_columns),
            "canonical_formula": item.canonical_formula,
            "lookback": item.lookback,
            "min_periods": item.min_periods,
            "ddof": item.ddof,
            "grouping": item.grouping,
            "sort_order": item.sort_order,
            "adjustment_semantics": item.adjustment_semantics,
            "missing_policy": item.missing_policy,
            "warmup_requirement": item.lookback,
            "PIT_statement": item.pit_statement,
            "dtype": item.dtype,
        })
    stable = {
        "schema_version": "tushare-feature-catalog-v2",
        "provider_id": "tushare-pro-v1",
        "universe_scope": "fixed_100_only",
        "warmup_period": ["2018-09-03", "2018-12-31"],
        "output_period": ["2019-01-02", "2026-06-23"],
        "features": rows,
        "feature_count": len(rows),
        "network_calls": 0,
        "fill_policy": "no_forward_backward_or_zero_fill",
    }
    return stable | {"catalog_id": "tfc2_" + hash_payload(stable)}


def snapshot_contract(dataset_id: str, features: tuple[str, ...], date_count: int) -> SnapshotContract:
    roles = {"symbol": "key", "trade_date": "key"} | {name: "feature" for name in features}
    types = {"symbol": "string", "trade_date": "timestamp[ns]"} | {name: "float32" for name in features}
    return SnapshotContract(dataset_id, "tushare_feature_matrix_v2", roles, date_count, types)
