from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.low_frequency_momentum.engine import _find_study, _source_matrix
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .artifact import KINDS, publish_artifact, validate_artifact
from .protocol import (
    COMPUTATION_REVISION, DECAY_HORIZONS, HORIZONS, PERIODS, REPORT_PERIODS, RESEARCH_PERIODS,
    SOURCE_FORMULA, SOURCE_SIGNAL_NAME, SOURCE_STUDY_ID, STYLE_COLUMNS,
    TASK_ID, TOP_NS,
)


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _store(bundle: AuthorityBundle, artifact: dict, kind: str, lineage: tuple[str, ...]) -> dict:
    field = KINDS[kind][0]
    artifact_id = artifact[field]
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), artifact_id, lineage=lineage)
    return {"artifact_kind": kind, "artifact_id": artifact_id,
            "descriptor_id": receipt.descriptor_id, "exact_existing": receipt.exact_existing,
            "new_blob_count": receipt.new_blob_count}


def _restore(bundle: AuthorityBundle, artifact_id: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"ARTIFACT_COMPLETENESS_FAILED:missing {artifact_id}")
    destination = Path(root) / descriptor.artifact_kind / artifact_id
    if destination.exists():
        shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    return validate_artifact(destination, artifact_id, descriptor.artifact_kind)


def _materialize(bundle: AuthorityBundle, artifact_id: str, root: Path) -> tuple[Path, dict]:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required source artifact missing: {artifact_id}")
    target = Path(root) / descriptor.artifact_kind / artifact_id
    if target.exists():
        shutil.rmtree(target)
    bundle.store.materialize_artifact(descriptor.descriptor_id, target)
    return target, json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]


def recover_source(bundle: AuthorityBundle, root: Path) -> tuple[dict, dict, pd.DataFrame, Path]:
    found = _find_study(bundle, root / "study-lookup")
    if found is None or found[0].artifact_id != SOURCE_STUDY_ID:
        raise RuntimeError("canonical R1-008 study identity mismatch")
    study_root, study = _materialize(bundle, SOURCE_STUDY_ID, root)
    matches = []
    for artifact_id in study["signal_artifact_ids"]:
        signal_root, identity = _materialize(bundle, artifact_id, root / "signals")
        if identity.get("name") == SOURCE_SIGNAL_NAME:
            matches.append((signal_root, identity | {"signal_artifact_id": artifact_id},
                            pd.read_parquet(signal_root / "signal_values.parquet")))
    if len(matches) != 1:
        raise RuntimeError("Signal D is missing or ambiguous")
    signal_root, identity, values = matches[0]
    if identity.get("canonical_formula") != SOURCE_FORMULA or identity.get("fixed_weights") != {
        "momentum_120_20": 0.5, "residual_momentum_60": 0.5,
    } or identity.get("orientation") != 1 or identity.get("signal_lag") != 1:
        raise RuntimeError("Signal D immutable definition mismatch")
    values["trade_date"] = pd.to_datetime(values["trade_date"])
    return study, identity, values.sort_values(["trade_date", "symbol"]), study_root


def diagnostic_spec(study: dict, signal: dict) -> dict[str, Any]:
    stable = {
        "schema_version": "momentum-tail-alpha-diagnostic-spec-v1",
        "computation_revision": COMPUTATION_REVISION,
        "task_id": TASK_ID, "research_type": "retrospective_tail_alpha_diagnostic",
        "provider_id": "tushare-pro-v1", "source_study_id": SOURCE_STUDY_ID,
        "source_signal_artifact_id": signal["signal_artifact_id"],
        "source_signal_spec_id": signal["signal_spec_id"], "signal_name": SOURCE_SIGNAL_NAME,
        "canonical_formula": SOURCE_FORMULA, "fixed_weights": signal["fixed_weights"],
        "orientation": 1, "signal_lag": 1, "periods": PERIODS,
        "horizons": list(HORIZONS), "decay_horizons": list(DECAY_HORIZONS),
        "top_n_baskets": list(TOP_NS), "top_n_holding_sessions": 10,
        "top_n_selection_allowed": False, "parameter_optimization_allowed": False,
        "candidate_lock_allowed": False, "registry_write_allowed": False,
        "promotion_allowed": False, "predictive_claim": False,
        "fresh_validation": False, "frozen_evidence": False,
    }
    stable["spec_id"] = "mtads1_" + hash_payload(stable)
    return stable


def _future_returns(normalized: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    frame = normalized[["symbol", "trade_date", "adjusted_close"]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["symbol", "trade_date"])
    close = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    for horizon in horizons:
        frame[f"return_{horizon}"] = frame.groupby("symbol")["adjusted_close"].shift(-horizon) / close - 1.0
    return frame.drop(columns="adjusted_close")


def style_matrix(normalized: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    frame = normalized[["symbol", "trade_date", "adjusted_close", "amount", "circ_mv"]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["symbol", "trade_date"])
    frame["stock_return"] = frame.groupby("symbol")["adjusted_close"].pct_change()
    market = benchmark.copy().sort_values("trade_date")
    market["trade_date"] = pd.to_datetime(market["trade_date"])
    close_name = "close" if "close" in market else "adjusted_close"
    market["market_return"] = pd.to_numeric(market[close_name], errors="coerce").pct_change()
    frame = frame.merge(market[["trade_date", "market_return"]], on="trade_date", how="left")
    grouped = frame.groupby("symbol", sort=False)
    for window in (20, 60):
        frame[f"volatility_{window}"] = grouped["stock_return"].transform(
            lambda value: value.rolling(window, min_periods=window).std(ddof=0))
        covariance = grouped.apply(
            lambda group: group["stock_return"].rolling(window, min_periods=window).cov(group["market_return"], ddof=0),
            include_groups=False,
        ).reset_index(level=0, drop=True).sort_index()
        market_variance = grouped["market_return"].transform(
            lambda value: value.rolling(window, min_periods=window).var(ddof=0))
        frame[f"style_beta_{window}"] = covariance / market_variance.where(market_variance > 0)
        residual = frame["stock_return"] - frame[f"style_beta_{window}"] * frame["market_return"]
        frame[f"style_idio_vol_{window}"] = residual.groupby(frame["symbol"]).transform(
            lambda value: value.rolling(window, min_periods=window).std(ddof=0))
    frame["amount_ratio_20"] = pd.to_numeric(frame["amount"], errors="coerce") / grouped["amount"].transform(
        lambda value: pd.to_numeric(value, errors="coerce").rolling(20, min_periods=20).mean())
    circ = pd.to_numeric(frame["circ_mv"], errors="coerce")
    frame["log_circ_mv"] = np.log(circ.where(circ > 0))
    return frame[["symbol", "trade_date", "log_circ_mv", "style_beta_20", "style_beta_60",
                  "style_idio_vol_20", "style_idio_vol_60", "volatility_20", "volatility_60",
                  "amount_ratio_20"]]


def analysis_frame(values: pd.DataFrame, matrix: pd.DataFrame, normalized: pd.DataFrame) -> pd.DataFrame:
    columns = ["symbol", "trade_date", "model_label", *[name for name in STYLE_COLUMNS if name in matrix],
               *[name for name in ("style_beta_20", "style_beta_60") if name in matrix]]
    frame = values.merge(matrix[columns], on=["symbol", "trade_date"], how="left", validate="one_to_one")
    frame = frame.merge(_future_returns(normalized, tuple(sorted(set(DECAY_HORIZONS)))),
                        on=["symbol", "trade_date"], how="left", validate="one_to_one")
    frame["rank"] = frame.groupby("trade_date")["factor_value"].rank(method="first")
    frame["decile"] = frame.groupby("trade_date")["rank"].transform(
        lambda value: pd.qcut(value, 10, labels=False, duplicates="drop") + 1
    )
    return frame


def _monotonicity(means: pd.Series, buckets: list[int]) -> float | None:
    selected = means.reindex(buckets).dropna()
    return None if len(selected) < 2 else _finite(pd.Series(selected.index).corr(selected.reset_index(drop=True), method="spearman"))


def quantile_and_tail(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict]]:
    quantile_rows, tail_rows, summaries = [], [], {}
    for period, bounds in PERIODS.items():
        source = frame[frame["trade_date"].between(*bounds)].copy()
        formal = source.dropna(subset=["factor_value", "model_label"])
        formal_daily_ic = formal.groupby("trade_date").apply(
            lambda g: g["factor_value"].corr(g["model_label"], method="spearman"),
            include_groups=False,
        ) if not formal.empty else pd.Series(dtype=float)
        formal_label_rankic = _finite(formal_daily_ic.mean())
        summaries[period] = {}
        for horizon in HORIZONS:
            column = f"return_{horizon}"
            daily = source.dropna(subset=["decile", column]).groupby(["trade_date", "decile"])[column].mean().unstack()
            means = daily.mean()
            for decile in range(1, 11):
                values = daily.get(decile, pd.Series(dtype=float)).dropna()
                quantile_rows.append({"period": period, "horizon": horizon, "decile": decile,
                    "mean_return": _finite(values.mean()), "cumulative_return": _finite((1 + values).prod() - 1),
                    "win_rate": _finite((values > 0).mean()), "date_count": int(len(values))})
            q10, q1 = daily.get(10, pd.Series(dtype=float)), daily.get(1, pd.Series(dtype=float))
            universe = source.groupby("trade_date")[column].mean()
            top_middle = daily.reindex(columns=[6, 7, 8, 9]).mean(axis=1)
            valid = source.dropna(subset=["factor_value", column])
            extreme = valid[valid["decile"].isin([1, 2, 9, 10])]
            extreme_ic = extreme.groupby("trade_date").apply(
                lambda g: g["factor_value"].corr(g[column], method="spearman"), include_groups=False
            ) if not extreme.empty else pd.Series(dtype=float)
            daily_ic = valid.groupby("trade_date").apply(
                lambda g: g["factor_value"].corr(g[column], method="spearman"), include_groups=False
            ) if not valid.empty else pd.Series(dtype=float)
            q10_universe = q10.subtract(universe, fill_value=np.nan)
            row = {
                "period": period, "horizon": horizon,
                "formal_label_rankic": formal_label_rankic,
                "forward_close_rankic": _finite(daily_ic.mean()),
                "mean_rankic": _finite(daily_ic.mean()),
                "q10_q1": _finite((q10 - q1).mean()), "q10_q5": _finite((q10 - daily.get(5, np.nan)).mean()),
                "q10_universe": _finite(q10_universe.mean()), "q9_q1": _finite((daily.get(9, np.nan) - q1).mean()),
                "top_tail_spread": _finite((q10 - top_middle).mean()),
                "top_tail_hit_rate": _finite((q10_universe > 0).mean()),
                "extreme_rank_ic": _finite(extreme_ic.mean()),
                "full_decile_monotonicity": _monotonicity(means, list(range(1, 11))),
                "top_half_monotonicity": _monotonicity(means, list(range(6, 11))),
                "top_three_decile_monotonicity": _monotonicity(means, [8, 9, 10]),
                "bottom_half_monotonicity": _monotonicity(means, list(range(1, 6))),
            }
            tail_rows.append(row); summaries[period][f"T+{horizon}"] = row
    return pd.DataFrame(quantile_rows), pd.DataFrame(tail_rows), summaries


def _benchmark_returns(benchmark: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    frame = benchmark.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    close_name = "close" if "close" in frame else "adjusted_close"
    close = pd.to_numeric(frame[close_name], errors="coerce")
    for horizon in horizons:
        frame[f"benchmark_{horizon}"] = close.shift(-horizon) / close - 1.0
    return frame[["trade_date", *[f"benchmark_{h}" for h in horizons]]]


def top_n_diagnostics(frame: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, holdings = [], []
    bench = _benchmark_returns(benchmark, (1, 10))
    for period, bounds in PERIODS.items():
        source = frame[frame["trade_date"].between(*bounds)].merge(bench, on="trade_date", how="left")
        dates = sorted(source["trade_date"].drop_duplicates())[::10]
        for top_n in TOP_NS:
            returns, benchmark_returns, overlaps, previous = [], [], [], set()
            for date in dates:
                day = source[source["trade_date"] == date].dropna(subset=["factor_value", "return_10"])
                selected = day.nlargest(top_n, "factor_value")
                current = set(selected["symbol"])
                if previous:
                    overlaps.append(len(current & previous) / max(1, len(current | previous)))
                previous = current
                basket_return = _finite(selected["return_10"].mean())
                if basket_return is not None:
                    returns.append(basket_return)
                    benchmark_returns.append(float(selected["benchmark_10"].iloc[0]))
                    for item in selected.itertuples():
                        holdings.append({"period": period, "top_n": top_n, "trade_date": date,
                                         "symbol": item.symbol, "forward_return": item.return_10,
                                         "contribution": item.return_10 / top_n})
            series = pd.Series(returns, dtype=float)
            nav = (1 + series).cumprod()
            drawdown = nav / nav.cummax() - 1 if not nav.empty else pd.Series(dtype=float)
            gross = _finite((1 + series).prod() - 1)
            benchmark_total = _finite((1 + pd.Series(benchmark_returns, dtype=float)).prod() - 1)
            rows.append({"period": period, "top_n": top_n, "holding_sessions": 10,
                         "gross_return": gross, "net_return": None,
                         "cost_status": "formal_trading_cost_unavailable_diagnostic_gross_only",
                         "csi300_return": benchmark_total,
                         "csi300_excess": None if gross is None or benchmark_total is None else gross - benchmark_total,
                         "maximum_drawdown": _finite(drawdown.min()),
                         "average_overlap": _finite(np.mean(overlaps)) if overlaps else None,
                         "rebalance_count": len(series), "diagnostic_only": True,
                         "not_strategy_optimization": True, "not_candidate_selection": True})
    return pd.DataFrame(rows), pd.DataFrame(holdings)


def monthly_2023(frame: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    source = frame[frame["trade_date"].between(*PERIODS["2023"])].copy()
    bench = _benchmark_returns(benchmark, (1,)).rename(columns={"benchmark_1": "csi300_return"})
    source = source.merge(bench, on="trade_date", how="left")
    rows = []
    for month, group in source.groupby(source["trade_date"].dt.to_period("M")):
        daily = []
        for date, day in group.groupby("trade_date"):
            valid = day.dropna(subset=["factor_value", "return_1", "decile"])
            if valid.empty:
                continue
            quantile = valid.groupby("decile")["return_1"].mean()
            daily.append({"forward_close_rankic": valid["factor_value"].corr(valid["return_1"], method="spearman"),
                          "formal_label_rankic": valid["factor_value"].corr(valid["model_label"], method="spearman"),
                          "q10": quantile.get(10), "q1": quantile.get(1),
                          "universe": valid["return_1"].mean(),
                          "top20": valid.nlargest(20, "factor_value")["return_1"].mean(),
                          "benchmark": valid["csi300_return"].iloc[0]})
        daily_frame = pd.DataFrame(daily)
        rows.append({"month": str(month),
                     "formal_label_rankic": _finite(daily_frame.formal_label_rankic.mean()),
                     "forward_close_rankic": _finite(daily_frame.forward_close_rankic.mean()),
                     "q10_return": _finite(daily_frame.q10.mean()),
                     "q10_q1": _finite((daily_frame.q10 - daily_frame.q1).mean()),
                     "q10_universe": _finite((daily_frame.q10 - daily_frame.universe).mean()),
                     "csi300_return": _finite(daily_frame.benchmark.mean()),
                     "signal_d_top20_return": _finite(daily_frame.top20.mean())})
    return pd.DataFrame(rows)


def stock_contributions(frame: pd.DataFrame, top_holdings: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    top20 = top_holdings[(top_holdings["period"] == "2023") & (top_holdings["top_n"] == 20)]
    for item in top20.itertuples():
        rows.append({"source": "top20_10day", "symbol": item.symbol, "contribution": item.contribution})
    source = frame[frame["trade_date"].between(*PERIODS["2023"])].dropna(subset=["decile", "return_1"])
    for label, decile in (("q10_daily", 10), ("q1_daily", 1)):
        selected = source[source["decile"] == decile].copy()
        counts = selected.groupby("trade_date")["symbol"].transform("count")
        selected["contribution"] = selected["return_1"] / counts
        rows.extend({"source": label, "symbol": item.symbol, "contribution": item.contribution}
                    for item in selected.itertuples())
    result = pd.DataFrame(rows).groupby(["source", "symbol"], as_index=False)["contribution"].sum()
    summary = {}
    for source_name, group in result.groupby("source"):
        ordered = group.sort_values("contribution", ascending=False)
        total = float(group["contribution"].sum())
        summary[source_name] = {
            "top_10_positive": ordered.head(10).to_dict("records"),
            "top_10_negative": ordered.tail(10).sort_values("contribution").to_dict("records"),
            "return_excluding_top_5": total - float(ordered.head(5)["contribution"].sum()),
            "return_excluding_bottom_5": total - float(ordered.tail(5)["contribution"].sum()),
            "total_additive_return": total,
        }
    return result, summary


def style_and_beta(frame: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    style_rows, beta_rows, summaries = [], [], {}
    bench = _benchmark_returns(benchmark, (1,))
    for period, bounds in PERIODS.items():
        source = frame[frame["trade_date"].between(*bounds)].merge(bench, on="trade_date", how="left")
        dates = sorted(source["trade_date"].drop_duplicates())[::10]
        selected_rows = []
        for date in dates:
            day = source[source["trade_date"] == date].dropna(subset=["factor_value"])
            top = day.nlargest(20, "factor_value")
            selected_rows.append(top)
            for column in STYLE_COLUMNS:
                if column not in day:
                    continue
                style_rows.append({"period": period, "trade_date": date, "feature": column,
                    "top20_weighted_mean": _finite(pd.to_numeric(top[column], errors="coerce").mean()),
                    "universe_median": _finite(pd.to_numeric(day[column], errors="coerce").median()),
                    "exposure_difference": _finite(pd.to_numeric(top[column], errors="coerce").mean() - pd.to_numeric(day[column], errors="coerce").median()),
                    "signal_feature_spearman": _finite(day["factor_value"].corr(pd.to_numeric(day[column], errors="coerce"), method="spearman"))})
            beta20 = _finite(pd.to_numeric(top.get("style_beta_20"), errors="coerce").mean())
            beta60 = _finite(pd.to_numeric(top.get("style_beta_60"), errors="coerce").mean())
            universe20 = _finite(pd.to_numeric(day.get("style_beta_20"), errors="coerce").median())
            universe60 = _finite(pd.to_numeric(day.get("style_beta_60"), errors="coerce").median())
            portfolio_return = _finite(pd.to_numeric(top["return_1"], errors="coerce").mean())
            market_return = _finite(top["benchmark_1"].iloc[0])
            component = None if beta60 is None or market_return is None else beta60 * market_return
            beta_rows.append({"period": period, "trade_date": date, "weighted_style_beta_20": beta20,
                              "weighted_style_beta_60": beta60, "universe_median_beta_20": universe20,
                              "universe_median_beta_60": universe60,
                              "beta_20_difference": None if beta20 is None or universe20 is None else beta20 - universe20,
                              "beta_60_difference": None if beta60 is None or universe60 is None else beta60 - universe60,
                              "top20_return": portfolio_return, "csi300_return": market_return,
                              "csi300_market_component": component,
                              "residual_return_diagnostic": None if portfolio_return is None or component is None else portfolio_return - component})
        beta_period = pd.DataFrame([row for row in beta_rows if row["period"] == period])
        summaries[period] = {column: _finite(beta_period[column].mean()) for column in beta_period.columns if column not in {"period", "trade_date"}}
    return pd.DataFrame(style_rows), pd.DataFrame(beta_rows), summaries


def component_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, bounds in PERIODS.items():
        source = frame[frame["trade_date"].between(*bounds)]
        for component in ("momentum_120_20", "residual_momentum_60"):
            daily = []
            for _, day in source.dropna(subset=[component, "model_label", "return_1"]).groupby("trade_date"):
                ranks = day[component].rank(method="first")
                top = day[ranks >= ranks.quantile(.9)]
                daily.append({
                    "formal_label_rankic": day[component].corr(day["model_label"], method="spearman"),
                    "forward_close_rankic": day[component].corr(day["return_1"], method="spearman"),
                    "top_tail_universe": top["return_1"].mean() - day["return_1"].mean(),
                })
            values = pd.DataFrame(daily, columns=(
                "formal_label_rankic", "forward_close_rankic", "top_tail_universe",
            ))
            rows.append({"period": period, "component": component,
                         "formal_label_rankic": _finite(values["formal_label_rankic"].mean()),
                         "forward_close_rankic": _finite(values["forward_close_rankic"].mean()),
                         "top_tail_universe": _finite(values["top_tail_universe"].mean()),
                         "date_count": len(values)})
    return pd.DataFrame(rows)


def stability_and_transition(frame: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    dates = sorted(frame[frame["trade_date"].between(PERIODS["2021"][0], PERIODS["2026H1"][1])]["trade_date"].drop_duplicates())
    pivot = frame.pivot(index="trade_date", columns="symbol", values="factor_value").reindex(dates)
    autocorrelation = {}
    for lag in (1, 5, 10, 20):
        values = [pivot.iloc[index].corr(pivot.iloc[index - lag], method="spearman") for index in range(lag, len(pivot))]
        autocorrelation[f"lag_{lag}"] = _finite(np.nanmean(values))
    rebalances = dates[::10]
    overlaps = {}
    for top_n in (10, 20, 30):
        sets = [set(pivot.loc[date].nlargest(top_n).dropna().index) for date in rebalances]
        overlaps[f"top{top_n}"] = _finite(np.mean([len(a & b) / max(1, len(a | b)) for a, b in zip(sets, sets[1:])]))
    rows = []
    for left, right in zip(rebalances, rebalances[1:]):
        before = frame[frame["trade_date"] == left][["symbol", "decile"]].rename(columns={"decile": "from_decile"})
        after = frame[frame["trade_date"] == right][["symbol", "decile"]].rename(columns={"decile": "to_decile"})
        moved = before.merge(after, on="symbol").dropna()
        moved["from_date"], moved["to_date"] = left, right
        rows.append(moved)
    transitions = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["symbol", "from_decile", "to_decile", "from_date", "to_date"])
    matrix = pd.crosstab(transitions["from_decile"], transitions["to_decile"], normalize="index") if not transitions.empty else pd.DataFrame()
    summary = {"score_autocorrelation": autocorrelation, "membership_overlap": overlaps,
               "q10_retention": _finite(matrix.loc[10, 10]) if 10 in matrix.index and 10 in matrix else None,
               "q10_to_q8_q9": _finite(matrix.loc[10, [c for c in (8, 9) if c in matrix]].sum()) if 10 in matrix.index else None,
               "q10_to_middle": _finite(matrix.loc[10, [c for c in range(3, 8) if c in matrix]].sum()) if 10 in matrix.index else None,
               "q10_to_q1_q2": _finite(matrix.loc[10, [c for c in (1, 2) if c in matrix]].sum()) if 10 in matrix.index else None}
    matrix_rows = matrix.stack().rename("transition_probability").reset_index()
    return summary, matrix_rows


def decay(frame: pd.DataFrame) -> dict:
    source = frame[frame["trade_date"].between(PERIODS["2021"][0], PERIODS["2024"][1])]
    output = {}
    for horizon in DECAY_HORIZONS:
        column = f"return_{horizon}"
        daily = []
        for _, day in source.dropna(subset=[column, "decile", "factor_value"]).groupby("trade_date"):
            means = day.groupby("decile")[column].mean()
            daily.append({"rankic": day["factor_value"].corr(day[column], method="spearman"),
                          "q10_q1": means.get(10) - means.get(1),
                          "q10_universe": means.get(10) - day[column].mean()})
        values = pd.DataFrame(daily)
        output[f"T+{horizon}"] = {name: _finite(values[name].mean()) for name in values}
        output[f"T+{horizon}"]["date_count"] = len(values)
    return output


def breadth_exposure(frame: pd.DataFrame, benchmark: pd.DataFrame, normalized: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    regimes, contract = build_regimes(normalized, benchmark)
    source = frame[frame["trade_date"].between(PERIODS["2021"][0], PERIODS["2026H1"][1])].merge(
        regimes[["trade_date", "breadth_regime"]], on="trade_date", how="left").merge(
        _benchmark_returns(benchmark, (1,)), on="trade_date", how="left")
    rows = []
    for state, group in source.groupby("breadth_regime"):
        daily = []
        for date, day in group.dropna(subset=["return_1", "factor_value", "decile"]).groupby("trade_date"):
            means = day.groupby("decile")["return_1"].mean()
            daily.append({"rankic": day["factor_value"].corr(day["return_1"], method="spearman"),
                          "q10_q1": means.get(10) - means.get(1),
                          "excess": day.nlargest(20, "factor_value")["return_1"].mean() - day["benchmark_1"].iloc[0]})
        values = pd.DataFrame(daily)
        nav = (1 + values["excess"]).cumprod() if not values.empty else pd.Series(dtype=float)
        dd = nav / nav.cummax() - 1 if not nav.empty else pd.Series(dtype=float)
        rows.append({"breadth_regime": state, "trading_days": len(values),
                     "rankic": _finite(values["rankic"].mean()), "q10_q1": _finite(values["q10_q1"].mean()),
                     "top20_csi300_excess": _finite((1 + values["excess"]).prod() - 1),
                     "maximum_drawdown": _finite(dd.min())})
    return pd.DataFrame(rows), contract


def _period_summary(tail: pd.DataFrame, topn: pd.DataFrame, period: str) -> dict:
    tail1 = tail[(tail["period"] == period) & (tail["horizon"] == 1)].iloc[0].to_dict()
    tail10 = tail[(tail["period"] == period) & (tail["horizon"] == 10)].iloc[0].to_dict()
    top20 = topn[(topn["period"] == period) & (topn["top_n"] == 20)].iloc[0].to_dict()
    return {"schema_version": "tail-alpha-retrospective-diagnostic-v1", "period": period,
            "retrospective_report_only": True, "not_used_for_selection": True,
            "not_fresh_validation": True, "rankic": tail1["formal_label_rankic"],
            "forward_close_rankic": tail1["forward_close_rankic"],
            "q10_q1": tail1["q10_q1"], "q10_universe": tail1["q10_universe"],
            "ten_day_tail": tail10, "top20_gross_diagnostic": top20}


def classify(tail: pd.DataFrame, topn: pd.DataFrame, breadth: pd.DataFrame) -> tuple[dict, dict]:
    annual = tail[(tail["period"].isin(RESEARCH_PERIODS)) & (tail["horizon"] == 1)]
    reports = tail[(tail["period"].isin(REPORT_PERIODS)) & (tail["horizon"] == 1)]
    top20 = topn[(topn["period"].isin(PERIODS)) & (topn["top_n"] == 20)]
    rank_positive = int((annual["formal_label_rankic"] > 0).sum())
    tail_positive = int((annual["q10_universe"] > 0).sum())
    top_positive = int((top20["csi300_excess"] > 0).sum())
    report_tail_positive = int((reports["q10_universe"] > 0).sum())
    robust_regime = bool(((breadth["q10_q1"] > 0) & (breadth["top20_csi300_excess"] > 0)).any())
    if rank_positive >= 3 and tail_positive >= 3 and top_positive >= 5:
        primary = "broad_monotonic_factor"
    elif tail_positive >= 3 and top_positive >= 4 and report_tail_positive >= 1:
        primary = "tail_selection_overlay"
    elif top_positive >= 4 and tail_positive < 3:
        primary = "defensive_relative_factor"
    elif robust_regime:
        primary = "regime_specific_factor"
    else:
        primary = "no_reliable_alpha"
    labels = []
    if rank_positive < 3 and tail_positive >= 3:
        labels.append("non_monotonic_tail_behavior")
    if top_positive >= 4 and tail_positive < 3:
        labels.append("benchmark_relative_defensive_exposure")
    if robust_regime and primary != "regime_specific_factor":
        labels.append("breadth_sensitive")
    labels = labels[:2]
    if primary == "tail_selection_overlay":
        decision = "build_momentum_selection_overlay"
    elif primary == "regime_specific_factor":
        decision = "retain_for_regime_specific_research"
    else:
        decision = "stop_signal_d_research"
    evidence = {"positive_rankic_research_years": rank_positive,
                "positive_q10_universe_research_years": tail_positive,
                "positive_top20_excess_periods": top_positive,
                "positive_report_tail_periods": report_tail_positive,
                "robust_breadth_regime_exists": robust_regime}
    return {"primary_classification": primary, "secondary_labels": labels, "evidence": evidence,
            "formal_rankic_gate_replaced": False}, {"decision": decision, "execute_decision": False,
            "candidate_lock_created": False, "registry_writes": 0, "promotion_writes": 0,
            "rationale": evidence}


def _find_existing(bundle: AuthorityBundle, root: Path) -> tuple[Any, dict] | None:
    found = []
    for index, descriptor in enumerate(bundle.store.list_by_kind("momentum_tail_alpha_diagnostic")):
        target = Path(root) / str(index)
        if target.exists():
            shutil.rmtree(target)
        bundle.store.materialize_artifact(descriptor.descriptor_id, target)
        identity = json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]
        if identity.get("task_id") == TASK_ID and identity.get("source_study_id") == SOURCE_STUDY_ID:
            found.append((descriptor, identity))
    if not found:
        return None
    latest_revision = max(int(item[1].get("computation_revision", 1)) for item in found)
    latest = [item for item in found if int(item[1].get("computation_revision", 1)) == latest_revision]
    if len(latest) > 1:
        raise RuntimeError("multiple canonical momentum tail-alpha diagnostics at latest computation revision")
    return latest[0]


def replay_diagnostic(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = load_authority_bundle(authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=Path(work_root) / "authority", store_root=store_root)
    found = _find_existing(bundle, Path(work_root) / "lookup")
    if found is None:
        raise RuntimeError("momentum tail-alpha diagnostic not found")
    descriptor, identity = found
    recovered = [_restore(bundle, artifact_id, Path(work_root) / "cold") for artifact_id in identity["artifact_ids"]]
    _restore(bundle, descriptor.artifact_id, Path(work_root) / "cold")
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "diagnostic_id": descriptor.artifact_id,
            "classification_id": identity["classification_id"],
            "recovered_artifact_count": len(recovered) + 1,
            "agent_calls": 0, "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0, "qlib_strategy_calls": 0, "network_calls": 0,
            "new_artifacts": 0, "new_blobs": 0, "registry_writes": 0, "promotion_writes": 0,
            "store_integrity": integrity.status, "missing": len(integrity.issues),
            "unreferenced": len(integrity.unreferenced_blobs)}


def execute_diagnostic(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = load_authority_bundle(authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=work_root / "authority", store_root=store_root)
    existing = _find_existing(bundle, work_root / "existing")
    if existing is not None and int(existing[1].get("computation_revision", 1)) == COMPUTATION_REVISION:
        return replay_diagnostic(repository_root=repository_root, work_root=work_root / "exact-replay", store_root=store_root) | {"exact_existing": True}
    study, signal, values, study_root = recover_source(bundle, work_root / "source-artifacts")
    matrix, _ = _source_matrix(bundle, work_root / "source-matrix")
    styles = style_matrix(bundle.normalized, bundle.benchmark)
    matrix = matrix.merge(styles, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    frame = analysis_frame(values, matrix, bundle.normalized)
    spec = diagnostic_spec(study, signal)
    quantiles, tail, tail_summary = quantile_and_tail(frame)
    topn, top_holdings = top_n_diagnostics(frame, bundle.benchmark)
    monthly = monthly_2023(frame, bundle.benchmark)
    contributions, contribution_summary = stock_contributions(frame, top_holdings)
    style, beta, beta_summary = style_and_beta(frame, bundle.benchmark)
    components = component_diagnostics(frame)
    stability, transition = stability_and_transition(frame)
    signal_decay = decay(frame)
    breadth, breadth_contract = breadth_exposure(frame, bundle.benchmark, bundle.normalized)
    report_2025 = _period_summary(tail, topn, "2025")
    report_2026 = _period_summary(tail, topn, "2026H1")
    classification, decision = classify(tail, topn, breadth)
    domain, cold = work_root / "domain", work_root / "cold"
    receipts, artifact_ids = [], []

    quantile_identity = {"schema_version": "momentum-quantile-return-report-v1", "provider_id": "tushare-pro-v1",
        "computation_revision": COMPUTATION_REVISION,
        "source_signal_artifact_id": signal["signal_artifact_id"], "source_study_id": SOURCE_STUDY_ID,
        "periods": PERIODS, "horizons": list(HORIZONS), "top_n_values": list(TOP_NS),
        "retrospective_report_only": True, "not_used_for_selection": True, "candidate_lock_created": False}
    quantile_artifact = publish_artifact(domain, "momentum_quantile_return_report", quantile_identity,
        {"quantile_returns.parquet": quantiles, "tail_metrics.parquet": tail,
         "top_n_diagnostics.parquet": topn, "monthly_2023.parquet": monthly,
         "stock_contributions.parquet": contributions, "contribution_summary.json": contribution_summary,
         "signal_decay.json": signal_decay, "report_2025.json": report_2025,
         "report_2026h1.json": report_2026, "tail_summary.json": tail_summary})
    receipts.append(_store(bundle, quantile_artifact, "momentum_quantile_return_report", (SOURCE_STUDY_ID, signal["signal_artifact_id"])))
    artifact_ids.append(quantile_artifact["quantile_report_id"]); _restore(bundle, artifact_ids[-1], cold)

    transition_identity = {"schema_version": "momentum-rank-transition-report-v1", "provider_id": "tushare-pro-v1",
        "computation_revision": COMPUTATION_REVISION,
        "source_signal_artifact_id": signal["signal_artifact_id"], "rebalance_interval": 10,
        "periods": PERIODS, "stability": stability, "parameter_change_allowed": False}
    transition_artifact = publish_artifact(domain, "momentum_rank_transition_report", transition_identity,
        {"rank_transition.parquet": transition, "score_stability.json": stability})
    receipts.append(_store(bundle, transition_artifact, "momentum_rank_transition_report", (SOURCE_STUDY_ID, signal["signal_artifact_id"])))
    artifact_ids.append(transition_artifact["transition_report_id"]); _restore(bundle, artifact_ids[-1], cold)

    style_identity = {"schema_version": "momentum-tail-style-exposure-v1", "provider_id": "tushare-pro-v1",
        "computation_revision": COMPUTATION_REVISION,
        "source_signal_artifact_id": signal["signal_artifact_id"], "style_columns": list(STYLE_COLUMNS),
        "periods": PERIODS, "beta_summary": beta_summary, "breadth_contract": breadth_contract,
        "sector_attribution_status": "not_computed_no_PIT_industry_contract"}
    style_artifact = publish_artifact(domain, "momentum_tail_style_exposure", style_identity,
        {"style_exposures.parquet": style, "beta_exposure.parquet": beta,
         "breadth_exposure.parquet": breadth, "component_diagnostics.parquet": components,
         "beta_summary.json": beta_summary})
    receipts.append(_store(bundle, style_artifact, "momentum_tail_style_exposure", (SOURCE_STUDY_ID, signal["signal_artifact_id"])))
    artifact_ids.append(style_artifact["style_exposure_id"]); _restore(bundle, artifact_ids[-1], cold)

    classification_identity = {"schema_version": "momentum-tail-signal-classification-v1", "provider_id": "tushare-pro-v1",
        "computation_revision": COMPUTATION_REVISION,
        "source_signal_artifact_id": signal["signal_artifact_id"],
        "primary_classification": classification["primary_classification"],
        "secondary_labels": classification["secondary_labels"], "research_decision": decision["decision"],
        "formal_rankic_gate_replaced": False, "candidate_lock_created": False,
        "registry_writes": 0, "promotion_writes": 0}
    classification_artifact = publish_artifact(domain, "momentum_tail_signal_classification", classification_identity,
        {"classification.json": classification, "decision.json": decision})
    receipts.append(_store(bundle, classification_artifact, "momentum_tail_signal_classification", tuple(artifact_ids)))
    artifact_ids.append(classification_artifact["classification_id"]); _restore(bundle, artifact_ids[-1], cold)

    counts = {"agent_calls": 0, "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
              "combined_optimization_calls": 0, "qlib_strategy_calls": 0, "network_calls": 0,
              "tushare_calls": 0, "candidate_locks": 0, "registry_writes": 0, "promotion_writes": 0}
    diagnostic_identity = {"schema_version": "momentum-tail-alpha-diagnostic-v1", "provider_id": "tushare-pro-v1",
        "computation_revision": COMPUTATION_REVISION,
        "task_id": TASK_ID, "source_study_id": SOURCE_STUDY_ID,
        "source_signal_artifact_id": signal["signal_artifact_id"], "source_signal_spec_id": signal["signal_spec_id"],
        "spec_id": spec["spec_id"], "artifact_ids": artifact_ids,
        "classification_id": classification_artifact["classification_id"],
        "primary_classification": classification["primary_classification"],
        "research_decision": decision["decision"], "execution_counts": counts,
        "predictive_claim": False, "fresh_validation": False, "frozen_evidence": False,
        "usable_for_promotion": False, "eligible_for_production": False}
    files = {"spec.json": spec, "quantile_returns.parquet": quantiles, "tail_metrics.parquet": tail,
        "top_n_diagnostics.parquet": topn, "monthly_2023.parquet": monthly,
        "stock_contributions.parquet": contributions, "style_exposures.parquet": style,
        "component_diagnostics.parquet": components,
        "rank_transition.parquet": transition, "signal_decay.json": signal_decay,
        "report_2025.json": report_2025, "report_2026h1.json": report_2026,
        "classification.json": classification, "decision.json": decision,
        "manifest_summary.json": {"source_artifact_ids": [SOURCE_STUDY_ID, signal["signal_artifact_id"]],
                                  "child_artifact_ids": artifact_ids}}
    diagnostic_artifact = publish_artifact(domain, "momentum_tail_alpha_diagnostic", diagnostic_identity, files)
    receipts.append(_store(bundle, diagnostic_artifact, "momentum_tail_alpha_diagnostic", tuple(artifact_ids) + (SOURCE_STUDY_ID, signal["signal_artifact_id"])))
    diagnostic_id = diagnostic_artifact["diagnostic_id"]; _restore(bundle, diagnostic_id, cold)
    inventory = publish_inventory(bundle.store); integrity = scan_store_integrity(bundle.store)
    return {"status": "completed", "diagnostic_id": diagnostic_id,
        "classification_id": classification_artifact["classification_id"],
        "source_signal_artifact_id": signal["signal_artifact_id"],
        "primary_classification": classification["primary_classification"],
        "secondary_labels": classification["secondary_labels"], "research_decision": decision["decision"],
        "artifact_ids": artifact_ids, "receipts": receipts, "execution_counts": counts,
        "inventory_id": inventory.inventory_id, "store_integrity": integrity.status,
        "missing": len(integrity.issues), "unreferenced": len(integrity.unreferenced_blobs)}
