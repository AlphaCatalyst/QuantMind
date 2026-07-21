from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd


def semantic_audit(candidate_a: dict, candidate_b: dict, feature_contract: dict) -> dict:
    distance = feature_contract["distance_to_high_60"]
    return {
        "schema_version": "momentum-semantic-audit-v1",
        "candidate_a": {
            "candidate_lock_id": candidate_a["candidate_lock_id"],
            "historical_template_name": candidate_a["template_name"],
            "semantic_display_name": "medium-horizon momentum baseline deviation",
            "semantic_classification": "momentum_deviation_or_surprise",
            "semantic_mismatch": True,
            "reason": "current momentum minus its own trailing mean has no volatility denominator, beta residualization, or risk penalty and is not risk-adjusted",
            "momentum_60_10_definition": "adjusted_close[t-10] / adjusted_close[t-60] - 1",
            "rolling_mean_series": "the same symbol-level momentum_60_10 series, trailing 40 observations including t",
            "risk_adjustment_present": False,
        },
        "candidate_b": {
            "candidate_lock_id": candidate_b["candidate_lock_id"],
            "historical_template_name": candidate_b["template_name"],
            "semantic_display_name": "skip-recent momentum plus pullback reward",
            "semantic_classification": "momentum_plus_mean_reversion_or_anti_crowding_discount",
            "semantic_mismatch": True,
            "reason": "distance_to_high_60 is non-positive; subtracting 0.75 times it rewards stocks farther below their 60-session high",
            "distance_to_high_60_definition": distance["formula"],
            "distance_expected_range": "[-1, 0] for positive adjusted close, with 0 at the rolling high",
            "algebraic_equivalence": "momentum_60_10 + 0.75 * abs(distance_to_high_60)",
            "breakout_confirmation": False,
        },
        "historical_ids_unchanged": True,
    }


def daily_cross_section(signal: pd.DataFrame, matrix: pd.DataFrame) -> pd.DataFrame:
    merged = signal.merge(matrix[["symbol", "trade_date", "model_label", "raw_label"]],
                          on=["symbol", "trade_date"], how="inner", validate="one_to_one")
    rows = []
    for date, group in merged.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["pred", "model_label", "raw_label"]).copy()
        if len(valid) < 20 or valid["pred"].nunique() < 10:
            continue
        ranked = valid["pred"].rank(method="first")
        valid["quantile"] = pd.qcut(ranked, 10, labels=False) + 1
        quantiles = valid.groupby("quantile")["raw_label"].mean()
        rows.append({
            "trade_date": date,
            "ic": valid["pred"].corr(valid["model_label"]),
            "rankic": _spearman(valid["pred"], valid["model_label"]),
            "observable_mean_return": valid["raw_label"].mean(),
            "top_bottom_spread": quantiles.get(10, np.nan) - quantiles.get(1, np.nan),
            **{f"q{i}": quantiles.get(i, np.nan) for i in range(1, 11)},
        })
    return pd.DataFrame(rows)


def period_cross_metrics(daily: pd.DataFrame, start: str, end: str) -> dict:
    frame = daily[daily["trade_date"].between(start, end)].copy()
    def stats(column: str) -> tuple[float | None, float | None]:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.empty:
            return None, None
        std = values.std(ddof=0)
        return float(values.mean()), None if std == 0 else float(values.mean() / std)
    mean_ic, icir = stats("ic")
    mean_rankic, rankicir = stats("rankic")
    rank = frame["rankic"].dropna()
    weekly = frame.set_index("trade_date")["rankic"].resample("W-FRI").mean().dropna()
    monthly = frame.set_index("trade_date")["rankic"].resample("ME").mean().dropna()
    q = [float(frame[f"q{i}"].mean()) for i in range(1, 11)]
    cumulative = [float((1 + frame[f"q{i}"].dropna()).prod() - 1) for i in range(1, 11)]
    monotonicity = _spearman(pd.Series(q), pd.Series(range(1, 11)))
    return {
        "sessions": int(frame["trade_date"].nunique()), "mean_ic": mean_ic,
        "mean_rankic": mean_rankic, "icir": icir, "rankicir": rankicir,
        "rankic_positive_rate": None if rank.empty else float((rank > 0).mean()),
        "weekly_rankic": None if weekly.empty else float(weekly.mean()),
        "monthly_rankic": None if monthly.empty else float(monthly.mean()),
        "quantile_mean_returns": q, "quantile_cumulative_returns": cumulative,
        "q10_q1_spread": float(frame["top_bottom_spread"].mean()),
        "q10_observable_mean_spread": float((frame["q10"] - frame["observable_mean_return"]).mean()),
        "monotonicity": None if pd.isna(monotonicity) else float(monotonicity),
        "observable_mean_definition": "equal-weight next-period raw-label return across currently observable Fixed-100 members; diagnostic only, not an investable benchmark",
    }


def horizon_decay(signal: pd.DataFrame, normalized: pd.DataFrame, periods: dict[str, tuple[str, str]]) -> dict:
    price = normalized[["symbol", "trade_date", "adjusted_open", "adjusted_close"]].copy()
    price = price.sort_values(["symbol", "trade_date"])
    grouped = price.groupby("symbol", sort=False)
    for horizon in (1, 2, 3, 5, 10):
        entry = grouped["adjusted_open"].shift(-1)
        exit_price = grouped["adjusted_close"].shift(-horizon)
        price[f"return_t{horizon}"] = exit_price / entry - 1
    merged = signal.merge(price, on=["symbol", "trade_date"], how="inner")
    output = {}
    for period, (start, end) in periods.items():
        frame = merged[merged["trade_date"].between(start, end)]
        output[period] = {}
        for horizon in (1, 2, 3, 5, 10):
            column = f"return_t{horizon}"
            daily = frame.groupby("trade_date").apply(
                lambda g: _horizon_row(g, column), include_groups=False
            ).apply(pd.Series)
            output[period][f"T+{horizon}"] = {
                "mean_rankic": _finite_mean(daily.get("rankic")),
                "mean_top_bottom_spread": _finite_mean(daily.get("spread")),
            }
    return output


def _horizon_row(group: pd.DataFrame, column: str) -> dict:
    valid = group.dropna(subset=["pred", column]).copy()
    if len(valid) < 20:
        return {"rankic": np.nan, "spread": np.nan}
    valid["bucket"] = pd.qcut(valid["pred"].rank(method="first"), 10, labels=False)
    means = valid.groupby("bucket")[column].mean()
    return {"rankic": _spearman(valid["pred"], valid[column]),
            "spread": means.get(9, np.nan) - means.get(0, np.nan)}


def beta_and_contributions(result: dict, features: pd.DataFrame, benchmark: pd.DataFrame,
                           entity: str, period: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    equity = pd.DataFrame(result.get("equity_curve") or [])
    positions = pd.DataFrame(result.get("positions") or [])
    if equity.empty or positions.empty:
        raise ValueError("formal Qlib positions and NAV are required")
    equity["trade_date"] = pd.to_datetime(equity["date"])
    equity["strategy_return"] = pd.to_numeric(equity["value"], errors="coerce").pct_change()
    market = benchmark.copy(); market["trade_date"] = pd.to_datetime(market["trade_date"])
    market = market.sort_values("trade_date")
    market["market_return"] = pd.to_numeric(market["close"], errors="coerce").pct_change()
    positions["trade_date"] = pd.to_datetime(positions["date"])
    beta = features[["symbol", "trade_date", "style_beta_60", "mom_ret_1d"]].copy()
    beta["lagged_stock_beta"] = beta.sort_values(["symbol", "trade_date"]).groupby("symbol")["style_beta_60"].shift(1)
    pos = positions.merge(beta, on=["symbol", "trade_date"], how="left")
    pos["weight"] = pd.to_numeric(pos["weight"], errors="coerce")
    weighted = pos.groupby("trade_date").apply(
        lambda g: pd.Series({
            "weighted_average_stock_beta": np.average(g["lagged_stock_beta"].dropna(), weights=g.loc[g["lagged_stock_beta"].notna(), "weight"]) if g["lagged_stock_beta"].notna().any() else np.nan,
            "raw_stock_contribution": float((g["weight"] * g["mom_ret_1d"]).sum()),
        }), include_groups=False).reset_index()
    daily = equity[["trade_date", "strategy_return"]].merge(market[["trade_date", "market_return"]], on="trade_date", how="left").merge(weighted, on="trade_date", how="left")
    covariance = daily["strategy_return"].rolling(60, min_periods=20).cov(daily["market_return"])
    variance = daily["market_return"].rolling(60, min_periods=20).var(ddof=0)
    daily["portfolio_beta"] = (covariance / variance.where(variance.abs() > 1e-12)).shift(1)
    daily["market_component"] = daily["weighted_average_stock_beta"] * daily["market_return"]
    daily["residual_component"] = daily["strategy_return"] - daily["market_component"]
    daily.insert(0, "entity", entity); daily.insert(1, "period", period)
    pos["contribution"] = pos["weight"] * pos["mom_ret_1d"]
    stocks = pos.groupby("symbol")["contribution"].sum().reset_index()
    stocks.insert(0, "entity", entity); stocks.insert(1, "period", period)
    days = daily[["entity", "period", "trade_date", "strategy_return"]].copy()
    return daily, stocks, days


def holding_and_style(positions: pd.DataFrame, features: pd.DataFrame, signal: pd.DataFrame,
                      entity: str, period: str, style_columns: Iterable[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = positions.copy(); positions["trade_date"] = pd.to_datetime(positions["date"])
    dates = sorted(positions["trade_date"].unique())
    rebalances = set(dates[::5])
    pos = positions[positions["trade_date"].isin(rebalances)].merge(features, on=["symbol", "trade_date"], how="left")
    signal_pair = signal.merge(features, on=["symbol", "trade_date"], how="inner")
    styles, concentrations = [], []
    for date, group in pos.groupby("trade_date", sort=True):
        weights = pd.to_numeric(group["weight"], errors="coerce").fillna(0)
        total = weights.sum()
        weights = weights / total if total > 0 else weights
        universe = features[features["trade_date"] == date]
        score_day = signal_pair[signal_pair["trade_date"] == date]
        for column in style_columns:
            valid = pd.to_numeric(group[column], errors="coerce")
            selected = float(np.average(valid[valid.notna()], weights=weights[valid.notna()])) if valid.notna().any() else np.nan
            median = pd.to_numeric(universe[column], errors="coerce").median()
            corr = _spearman(score_day["pred"], score_day[column])
            styles.append({"entity": entity, "period": period, "trade_date": date,
                           "feature": column, "portfolio_weighted_exposure": selected,
                           "universe_median_exposure": median, "exposure_difference": selected - median,
                           "score_feature_spearman": corr})
        ordered = weights.sort_values(ascending=False)
        concentrations.append({"entity": entity, "period": period, "trade_date": date,
            "holdings": int((weights > 0).sum()), "effective_holdings": float(1 / (weights.pow(2).sum())) if weights.pow(2).sum() else 0.0,
            "top5_weight_share": float(ordered.head(5).sum()), "top10_weight_share": float(ordered.head(10).sum()),
            "single_stock_max_weight": float(ordered.max()), "sector_concentration": None,
            "sector_status": "not_computed_no_PIT_industry_contract"})
    return pd.DataFrame(styles), pd.DataFrame(concentrations)


def pair_correlations(signals: dict[str, pd.DataFrame], qlib: dict[tuple[str, str], dict]) -> dict:
    output = {}
    names = sorted(signals)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            merged = signals[left].merge(signals[right], on=["symbol", "trade_date"], suffixes=("_l", "_r"))
            implied = merged.assign(top_l=merged.groupby("trade_date")["pred_l"].rank(ascending=False) <= 20,
                                    top_r=merged.groupby("trade_date")["pred_r"].rank(ascending=False) <= 20)
            overlap = implied.groupby("trade_date").apply(lambda g: float((g.top_l & g.top_r).sum() / max(1, (g.top_l | g.top_r).sum())), include_groups=False).mean()
            periods = {}
            for period in ("2019-2024", "2025", "2026H1"):
                l = pd.DataFrame(qlib[(left, period)].get("equity_curve") or [])
                r = pd.DataFrame(qlib[(right, period)].get("equity_curve") or [])
                l["ret"] = l["value"].pct_change(); r["ret"] = r["value"].pct_change()
                pair = l[["date", "ret"]].merge(r[["date", "ret"]], on="date", suffixes=("_l", "_r"))
                monthly_l = pd.Series(l.ret.to_numpy(), index=pd.to_datetime(l.date)).resample("ME").apply(lambda x: (1+x.dropna()).prod()-1)
                monthly_r = pd.Series(r.ret.to_numpy(), index=pd.to_datetime(r.date)).resample("ME").apply(lambda x: (1+x.dropna()).prod()-1)
                periods[period] = {"daily_strategy_return_correlation": pair.ret_l.corr(pair.ret_r),
                                   "monthly_strategy_return_correlation": monthly_l.corr(monthly_r)}
            output[f"{left}::{right}"] = {"signal_correlation": _spearman(merged.pred_l, merged.pred_r),
                "signal_implied_top20_jaccard": float(overlap), "periods": periods}
    return output


def _finite_mean(values) -> float | None:
    if values is None:
        return None
    value = pd.to_numeric(values, errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _spearman(left: pd.Series, right: pd.Series) -> float:
    pair = pd.concat([pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")], axis=1).dropna()
    if len(pair) < 2:
        return np.nan
    return float(pair.iloc[:, 0].rank(method="average").corr(pair.iloc[:, 1].rank(method="average")))


def safe_float(value) -> float | None:
    return None if value is None or not math.isfinite(float(value)) else float(value)
