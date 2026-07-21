from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def build_regimes(normalized: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    market = benchmark.copy()
    market["trade_date"] = pd.to_datetime(market["trade_date"])
    market = market.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    close_column = "close" if "close" in market.columns else "adjusted_close"
    close = pd.to_numeric(market[close_column], errors="coerce")
    market_return = close.pct_change()
    trend_return = close.pct_change(60).shift(1)
    trend_ma_gap = (close / close.rolling(120, min_periods=120).mean() - 1.0).shift(1)
    trend = np.select(
        [((trend_return > 0) & (trend_ma_gap > 0)), ((trend_return < 0) & (trend_ma_gap < 0))],
        ["bull", "bear"], default="sideways",
    ).astype(object)
    trend[pd.isna(trend_return) | pd.isna(trend_ma_gap)] = "unavailable"

    realized_vol = market_return.rolling(20, min_periods=20).std().shift(1)
    vol_low = realized_vol.expanding(min_periods=504).quantile(1 / 3).shift(1)
    vol_high = realized_vol.expanding(min_periods=504).quantile(2 / 3).shift(1)
    volatility = np.select([realized_vol < vol_low, realized_vol > vol_high], ["low", "high"], default="normal").astype(object)
    volatility[pd.isna(realized_vol) | pd.isna(vol_low) | pd.isna(vol_high)] = "unavailable"

    stock = normalized[["symbol", "trade_date", "adjusted_close"]].copy()
    stock["trade_date"] = pd.to_datetime(stock["trade_date"])
    stock = stock.sort_values(["symbol", "trade_date"])
    stock["ma20"] = stock.groupby("symbol", sort=False)["adjusted_close"].transform(lambda value: value.rolling(20, min_periods=20).mean())
    daily_breadth = stock.assign(above=stock["adjusted_close"] > stock["ma20"]).groupby("trade_date")["above"].mean()
    breadth_value = market["trade_date"].map(daily_breadth).shift(1)
    breadth_low = breadth_value.expanding(min_periods=504).quantile(1 / 3).shift(1)
    breadth_high = breadth_value.expanding(min_periods=504).quantile(2 / 3).shift(1)
    breadth = np.select([breadth_value < breadth_low, breadth_value > breadth_high], ["narrow", "broad"], default="neutral").astype(object)
    breadth[pd.isna(breadth_value) | pd.isna(breadth_low) | pd.isna(breadth_high)] = "unavailable"

    result = pd.DataFrame({
        "trade_date": market["trade_date"].to_numpy(), "trend_regime": trend,
        "volatility_regime": volatility, "breadth_regime": breadth,
        "lagged_trend_return_60": trend_return, "lagged_trend_ma_gap_120": trend_ma_gap,
        "lagged_realized_vol_20": realized_vol, "lagged_breadth_20": breadth_value,
    })
    contract = {
        "schema_version": "momentum-market-regime-v1",
        "usage": "diagnostic_only_not_agent_or_dsl_input",
        "trend": {"states": ["bull", "bear", "sideways"], "rule": "lagged CSI300 60-session return and lagged 120-session moving-average gap agree; otherwise sideways"},
        "volatility": {"states": ["low", "normal", "high"], "rule": "lagged 20-session CSI300 volatility against expanding past-only 1/3 and 2/3 quantiles", "minimum_history": 504},
        "breadth": {"states": ["broad", "neutral", "narrow"], "rule": "lagged share of Fixed-100 symbols above own 20-session average against expanding past-only 1/3 and 2/3 quantiles", "minimum_history": 504},
        "warmup_state": "unavailable",
        "pit_rule": "all state inputs and expanding thresholds are shifted at least one session; no future or evaluation-period calibration",
    }
    return result, contract


def regime_diagnostics(daily: pd.DataFrame, regimes: pd.DataFrame) -> dict[str, Any]:
    merged = daily.copy()
    merged["trade_date"] = pd.to_datetime(merged["trade_date"])
    merged = merged.merge(regimes[["trade_date", "trend_regime", "volatility_regime", "breadth_regime"]], on="trade_date", how="left")
    output: dict[str, Any] = {}
    for column in ("trend_regime", "volatility_regime", "breadth_regime"):
        metrics = {}
        for state, group in merged.groupby(column, dropna=False):
            label = str(state)
            metrics[label] = {
                "session_count": int(group["trade_date"].nunique()),
                "mean_rankic": _mean(group, "rankic"),
                "annualized_excess": _annualized(group, "strategy_return", "benchmark_return"),
                "positive_rankic_rate": _positive_rate(group, "rankic"),
            }
        output[column] = metrics
    return output


def _mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    value = pd.to_numeric(frame[column], errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _positive_rate(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return None if values.empty else float((values > 0).mean())


def _annualized(frame: pd.DataFrame, strategy: str, benchmark: str) -> float | None:
    if strategy not in frame or benchmark not in frame:
        return None
    values = (pd.to_numeric(frame[strategy], errors="coerce") - pd.to_numeric(frame[benchmark], errors="coerce")).dropna()
    if values.empty:
        return None
    return float(values.mean() * 252.0)
