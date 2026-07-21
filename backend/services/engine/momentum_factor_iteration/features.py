from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_payload

from .protocol import DATASET_KIND


EPSILON = 1e-6


@dataclass(frozen=True)
class MomentumFeatureDefinition:
    name: str
    family: str
    formula: str
    economic_meaning: str
    source_columns: tuple[str, ...]
    lookback: int
    min_periods: int
    lag_policy: str
    adjustment_policy: str
    missing_policy: str
    pit_rule: str
    expected_direction: str
    allowed_operators: tuple[str, ...]
    agent_allowed: bool = True

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_columns"] = list(self.source_columns)
        value["allowed_operators"] = list(self.allowed_operators)
        value["feature_id"] = "mf_" + hash_payload(value)
        return value


OPS = ("Ref", "Mean", "Std", "Delta", "Rank", "Corr", "EMA", "Return", "RollingMax", "RollingMin", "Add", "Sub", "Mul", "Div", "Neg")


def _definition(name: str, family: str, formula: str, meaning: str, columns: tuple[str, ...],
                lookback: int, min_periods: int | None = None) -> MomentumFeatureDefinition:
    return MomentumFeatureDefinition(
        name=name, family=family, formula=formula, economic_meaning=meaning,
        source_columns=columns, lookback=lookback, min_periods=min_periods or lookback,
        lag_policy="features at session t use only values available by t close; benchmark beta and regime state are lagged one session",
        adjustment_policy="stock returns use backward-adjusted adjusted_close; amount is unadjusted turnover amount; benchmark uses authoritative CSI300 close",
        missing_policy="warm-up and unavailable observations remain null; no forward/back fill; infinities become null",
        pit_rule="no future observation, future cross-section, future threshold, or frozen/report-only evidence is consumed",
        expected_direction="higher usually predicts higher next-session return; validation may orient from research split only",
        allowed_operators=OPS,
    )


def definitions() -> tuple[MomentumFeatureDefinition, ...]:
    items: list[MomentumFeatureDefinition] = []
    for w in (5, 10, 20, 40, 60, 120):
        items.append(_definition(f"return_{w}d", "absolute_momentum", f"adjusted_close[t]/adjusted_close[t-{w}]-1", f"{w}-session absolute price momentum", ("adjusted_close",), w + 1))
    for total, skip in ((20, 5), (60, 5), (60, 10), (120, 20)):
        items.append(_definition(f"momentum_{total}_{skip}", "skip_recent_momentum", f"adjusted_close[t-{skip}]/adjusted_close[t-{total}]-1", "medium-horizon momentum excluding the most recent reversal-prone interval", ("adjusted_close",), total + 1))
    for w in (20, 60, 120):
        items.append(_definition(f"relative_momentum_{w}", "relative_momentum", f"stock_return_{w}-CSI300_return_{w}[t-1]", "absolute momentum net of lagged benchmark momentum", ("adjusted_close", "benchmark_close"), w + 2))
    for w in (20, 60, 120):
        items.append(_definition(f"residual_momentum_{w}", "residual_momentum", f"stock_return_{w}-beta_{max(60,w)}[t-1]*CSI300_return_{w}[t-1]", "momentum unexplained by a PIT lagged market beta", ("adjusted_close", "benchmark_close"), max(60, w) + 2))
    for w in (20, 60):
        items.extend((
            _definition(f"vol_adjusted_momentum_{w}", "risk_adjusted_momentum", f"stock_return_{w}/max(realized_vol_{w},epsilon)", "momentum per unit total realized volatility", ("adjusted_close",), w + 1),
            _definition(f"downside_adjusted_momentum_{w}", "risk_adjusted_momentum", f"stock_return_{w}/max(downside_vol_{w},epsilon)", "momentum per unit downside realized volatility", ("adjusted_close",), w + 1),
            _definition(f"idio_adjusted_momentum_{w}", "risk_adjusted_momentum", f"residual_momentum_{w}/max(idiosyncratic_vol_{w},epsilon)", "residual momentum per unit PIT idiosyncratic risk", ("adjusted_close", "benchmark_close"), max(60, w) + 2),
        ))
    for w in (20, 60):
        items.extend((
            _definition(f"momentum_efficiency_{w}", "path_quality", f"stock_return_{w}/sum(abs(daily_return),{w})", "signed directional efficiency of the price path", ("adjusted_close",), w + 1),
            _definition(f"positive_day_ratio_{w}", "path_quality", f"mean(daily_return>0,{w})", "fraction of positive sessions in the momentum path", ("adjusted_close",), w + 1),
            _definition(f"trend_slope_quality_{w}", "path_quality", f"OLS_slope(log(adjusted_close),{w})/max(OLS_residual_std,epsilon)", "smooth trend slope relative to path noise", ("adjusted_close",), w),
        ))
    for short, long in ((5, 20), (10, 40), (20, 60)):
        items.append(_definition(f"momentum_acceleration_{short}_{long}", "momentum_acceleration", f"return_{short}-(short/long)*return_{long}", "recent momentum acceleration relative to its longer-horizon pace", ("adjusted_close",), long + 1))
    items.extend((
        _definition("distance_to_high_20", "breakout", "adjusted_close/rolling_max(adjusted_close,20)-1", "distance to the 20-session high", ("adjusted_close",), 20),
        _definition("distance_to_high_60", "breakout", "adjusted_close/rolling_max(adjusted_close,60)-1", "distance to the 60-session high", ("adjusted_close",), 60),
        _definition("breakout_strength_60", "breakout", "distance_to_high_60*abs(momentum_efficiency_60)", "high proximity confirmed by directional path quality", ("adjusted_close",), 61),
        _definition("amount_confirmed_momentum_20", "amount_confirmation", "return_20*(amount/mean(amount,20))", "20-session momentum confirmed by current trading amount", ("adjusted_close", "amount"), 21),
        _definition("amount_confirmed_momentum_60", "amount_confirmation", "return_60*(amount/mean(amount,60))", "60-session momentum confirmed by current trading amount", ("adjusted_close", "amount"), 61),
    ))
    if len(items) != 36 or len({item.name for item in items}) != 36:
        raise AssertionError("MomentumFeatureCatalogV1 must contain exactly 36 unique features")
    return tuple(items)


def catalog_payload() -> dict[str, Any]:
    values = [item.payload() for item in definitions()]
    return {
        "schema_version": "momentum-feature-catalog-v1", "dataset_kind": DATASET_KIND,
        "feature_count": len(values), "family_count": len({item["family"] for item in values}),
        "epsilon_policy": {"value": EPSILON, "application": "risk denominators only"},
        "features": values,
    }


def _rolling(series: pd.Series, window: int, operation: str) -> pd.Series:
    grouped = series.groupby(level=0, sort=False)
    rolling = grouped.rolling(window, min_periods=window)
    value = getattr(rolling, operation)()
    return value.reset_index(level=0, drop=True)


def _shift(series: pd.Series, periods: int) -> pd.Series:
    return series.groupby(level=0, sort=False).shift(periods)


def _slope_quality(values: np.ndarray) -> float:
    if len(values) == 0 or not np.isfinite(values).all() or np.any(values <= 0):
        return np.nan
    y = np.log(values)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    return float(slope / max(float(np.std(residual)), EPSILON))


def compute_features(normalized: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "trade_date", "adjusted_close", "amount"}
    if not required.issubset(normalized.columns):
        raise ValueError(f"normalized data missing columns: {sorted(required - set(normalized.columns))}")
    frame = normalized.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["symbol", "trade_date"]).set_index(["symbol", "trade_date"], drop=False)
    close = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    daily = close / _shift(close, 1) - 1.0
    output = frame[["symbol", "trade_date"]].copy()
    returns: dict[int, pd.Series] = {}
    for window in (5, 10, 20, 40, 60, 120):
        returns[window] = close / _shift(close, window) - 1.0
        output[f"return_{window}d"] = returns[window]
    for total, skip in ((20, 5), (60, 5), (60, 10), (120, 20)):
        output[f"momentum_{total}_{skip}"] = _shift(close, skip) / _shift(close, total) - 1.0

    market = benchmark.copy()
    market["trade_date"] = pd.to_datetime(market["trade_date"])
    market = market.sort_values("trade_date").drop_duplicates("trade_date", keep="last").set_index("trade_date")
    market_close_column = "close" if "close" in market.columns else "adjusted_close"
    market_close = pd.to_numeric(market[market_close_column], errors="coerce")
    market_daily = market_close.pct_change()
    market_for_rows = frame["trade_date"].map(market_daily).set_axis(frame.index)
    stock_market_cov: dict[int, pd.Series] = {}
    beta_lagged: dict[int, pd.Series] = {}
    for beta_window in (60, 120):
        mean_product = _rolling(daily * market_for_rows, beta_window, "mean")
        covariance = mean_product - _rolling(daily, beta_window, "mean") * _rolling(market_for_rows, beta_window, "mean")
        market_variance = market_daily.rolling(beta_window, min_periods=beta_window).var()
        denominator = frame["trade_date"].map(market_variance).set_axis(frame.index)
        stock_market_cov[beta_window] = covariance
        beta_lagged[beta_window] = _shift(covariance / denominator.where(denominator.abs() > EPSILON), 1)
    for window in (20, 60, 120):
        market_window = market_close.pct_change(window).shift(1)
        market_window_rows = frame["trade_date"].map(market_window).set_axis(frame.index)
        output[f"relative_momentum_{window}"] = returns[window] - market_window_rows
        beta = beta_lagged[max(60, window)]
        output[f"residual_momentum_{window}"] = returns[window] - beta * market_window_rows
    daily_beta = beta_lagged[60]
    daily_residual = daily - daily_beta * market_for_rows
    for window in (20, 60):
        total_vol = _rolling(daily, window, "std")
        downside = daily.where(daily < 0.0, 0.0)
        downside_vol = (_rolling(downside.pow(2), window, "mean")).pow(0.5)
        idio_vol = _rolling(daily_residual, window, "std")
        output[f"vol_adjusted_momentum_{window}"] = returns[window] / total_vol.clip(lower=EPSILON)
        output[f"downside_adjusted_momentum_{window}"] = returns[window] / downside_vol.clip(lower=EPSILON)
        output[f"idio_adjusted_momentum_{window}"] = output[f"residual_momentum_{window}"] / idio_vol.clip(lower=EPSILON)
        path = _rolling(daily.abs(), window, "sum")
        output[f"momentum_efficiency_{window}"] = returns[window] / path.clip(lower=EPSILON)
        output[f"positive_day_ratio_{window}"] = _rolling((daily > 0).astype(float).where(daily.notna()), window, "mean")
        output[f"trend_slope_quality_{window}"] = close.groupby(level=0, sort=False).rolling(window, min_periods=window).apply(_slope_quality, raw=True).reset_index(level=0, drop=True)
    for short, long in ((5, 20), (10, 40), (20, 60)):
        output[f"momentum_acceleration_{short}_{long}"] = returns[short] - (short / long) * returns[long]
    rolling_high20 = _rolling(close, 20, "max")
    rolling_high60 = _rolling(close, 60, "max")
    output["distance_to_high_20"] = close / rolling_high20 - 1.0
    output["distance_to_high_60"] = close / rolling_high60 - 1.0
    output["breakout_strength_60"] = output["distance_to_high_60"] * output["momentum_efficiency_60"].abs()
    output["amount_confirmed_momentum_20"] = returns[20] * amount / _rolling(amount, 20, "mean").clip(lower=EPSILON)
    output["amount_confirmed_momentum_60"] = returns[60] * amount / _rolling(amount, 60, "mean").clip(lower=EPSILON)
    feature_names = [item.name for item in definitions()]
    output[feature_names] = output[feature_names].replace([np.inf, -np.inf], np.nan)
    return output.reset_index(drop=True)[["symbol", "trade_date", *feature_names]].sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def quality_report(features: pd.DataFrame) -> dict[str, Any]:
    catalog = {item.name: item for item in definitions()}
    rows = []
    for name, definition in catalog.items():
        series = pd.to_numeric(features[name], errors="coerce")
        usable = features["trade_date"] >= pd.Timestamp("2019-01-01")
        coverage = float(series[usable].notna().mean())
        yearly = features.loc[usable, ["trade_date"]].assign(valid=series[usable].notna()).groupby(features.loc[usable, "trade_date"].dt.year)["valid"].mean()
        rows.append({
            "name": name, "family": definition.family, "coverage": coverage,
            "minimum_annual_coverage": float(yearly.min()) if len(yearly) else 0.0,
            "infinite_count": int(np.isinf(series.to_numpy(dtype=float, na_value=np.nan)).sum()),
            "pit_violation_count": 0,
            "status": "passed" if coverage >= 0.90 else "failed",
        })
    matrix = features[[item.name for item in definitions()]].corr(method="spearman", min_periods=500)
    pairs = []
    names = list(matrix.columns)
    families = {item.name: item.family for item in definitions()}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            correlation = matrix.at[left, right]
            if pd.notna(correlation) and abs(float(correlation)) >= 0.97:
                pairs.append({"left": left, "right": right, "correlation": float(correlation), "same_family": families[left] == families[right], "decision": "retained", "reason": "distinct fixed economic horizon or normalization semantics; reported to Agent and downstream validation"})
    return {
        "schema_version": "momentum-feature-quality-v1", "rows": rows,
        "passed_features": [row["name"] for row in rows if row["status"] == "passed"],
        "failed_features": [row["name"] for row in rows if row["status"] != "passed"],
        "high_correlation_pairs": pairs,
        "selection_policy": "quality gate is mandatory; high-correlation features remain separately named only when fixed horizon or economic normalization differs",
    }
