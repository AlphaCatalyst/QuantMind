from __future__ import annotations

from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.evaluation import signal_similarity
from backend.services.engine.autonomous_factor_campaign.evaluation_v2 import _year_result
from backend.services.engine.autonomous_factor_program.statistics import hac_mean_test
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.tushare_agent_experiment.evaluation import factor_values


ADAPTIVE_YEARS = {
    "2019": ("2019-01-02", "2019-12-31"),
    "2020": ("2020-01-02", "2020-12-31"),
}
VALIDATION_YEARS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
}


def daily_rankic(values: pd.DataFrame, matrix: pd.DataFrame, orientation: int,
                 start: str, end: str) -> list[float]:
    selected = matrix.loc[
        matrix["trade_date"].between(start, end), ["symbol", "trade_date", "model_label"]
    ].merge(values, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    selected["factor_value"] *= orientation
    rows = []
    for _, group in selected.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["factor_value", "model_label"])
        if len(valid) >= 20 and valid["factor_value"].nunique() >= 5:
            value = valid["factor_value"].corr(valid["model_label"], method="spearman")
            if pd.notna(value):
                rows.append(float(value))
    return rows


def tail_observations(values: pd.DataFrame, normalized: pd.DataFrame, orientation: int,
                      start: str, end: str) -> list[dict[str, float]]:
    bars = normalized[["symbol", "trade_date", "adjusted_close"]].copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.strftime("%Y-%m-%d")
    bars = bars.sort_values(["symbol", "trade_date"])
    bars["future_10_session_gross_return"] = (
        bars.groupby("symbol")["adjusted_close"].shift(-10) / bars["adjusted_close"] - 1
    )
    merged = values.merge(
        bars[["symbol", "trade_date", "future_10_session_gross_return"]],
        on=["symbol", "trade_date"], how="left", validate="one_to_one",
    )
    merged = merged[merged["trade_date"].between(start, end)].copy()
    dates = sorted(merged["trade_date"].dropna().unique())[::10]
    rows = []
    for date in dates:
        group = merged[merged["trade_date"] == date].dropna(
            subset=["factor_value", "future_10_session_gross_return"]
        ).copy()
        if len(group) < 90:
            continue
        group["score"] = group["factor_value"] * orientation
        top20 = group.nlargest(20, "score")
        q10 = group.nlargest(max(1, int(np.ceil(len(group) * .10))), "score")
        universe = float(group["future_10_session_gross_return"].mean())
        top = float(top20["future_10_session_gross_return"].mean())
        rows.append({
            "trade_date": date, "top20_universe_spread": top - universe,
            "q10_universe_spread": float(q10["future_10_session_gross_return"].mean()) - universe,
            "top20_hit": float(top > universe), "top20_gross_return": top,
            "universe_gross_return": universe,
        })
    return rows


def _summary(annual: list[dict], archetype: str, maximum_existing_correlation: float,
             phase: str) -> dict:
    rankic = [row["metrics"].get("mean_rank_ic") for row in annual]
    excess = [row["qlib"].get("net_excess_csi300") for row in annual]
    turnover = [row["qlib"].get("turnover") for row in annual]
    concentration = [row["qlib"].get("best_10_days_contribution") for row in annual]
    tail_spread = [row["tail"]["top20_universe_spread_mean"] for row in annual]
    hit = [row["tail"]["top20_hit_rate"] for row in annual]
    def med(values):
        return None if not values or any(value is None for value in values) else float(median(values))
    common = {
        "coverage_passed": all((row["metrics"].get("factor_finite_coverage") or 0) >= .90 for row in annual),
        "infinity_passed": all(row["infinity_count"] == 0 for row in annual),
        "pit_passed": True,
        "positive_rankic_year_count": sum(value is not None and value > 0 for value in rankic),
        "median_annual_rankic": med(rankic), "worst_annual_rankic": None if None in rankic else min(rankic),
        "positive_csi300_excess_year_count": sum(value is not None and value > 0 for value in excess),
        "median_csi300_excess": med(excess), "worst_csi300_excess": None if None in excess else min(excess),
        "median_turnover": med(turnover), "median_best10_contribution": med(concentration),
        "positive_tail_spread_year_count": sum(value is not None and value > 0 for value in tail_spread),
        "median_tail_spread": med(tail_spread), "worst_tail_spread": None if None in tail_spread else min(tail_spread),
        "median_top20_hit_rate": med(hit),
        "maximum_existing_factor_correlation": maximum_existing_correlation,
    }
    if archetype == "monotonic_rank_factor":
        checks = {
            "coverage": common["coverage_passed"], "infinity": common["infinity_passed"], "pit": True,
            "positive_rankic_years": common["positive_rankic_year_count"] >= (1 if phase == "adaptive" else 3),
            "median_rankic": (common["median_annual_rankic"] or -999) >= .003,
            "worst_rankic": (common["worst_annual_rankic"] or -999) >= -.008,
            "turnover": (common["median_turnover"] or 999) <= 30,
            "concentration": (common["median_best10_contribution"] or 999) <= .35,
            "correlation": maximum_existing_correlation < .85,
        }
        if phase == "validation":
            checks |= {
                "positive_excess_years": common["positive_csi300_excess_year_count"] >= 3,
                "median_excess": (common["median_csi300_excess"] or -999) > 0,
                "worst_excess": (common["worst_csi300_excess"] or -999) > -.10,
            }
    else:
        checks = {
            "coverage": common["coverage_passed"], "infinity": common["infinity_passed"], "pit": True,
            "positive_tail_years": common["positive_tail_spread_year_count"] >= (1 if phase == "adaptive" else 3),
            "median_tail_spread": (common["median_tail_spread"] or -999) > 0,
            "worst_tail_spread": (common["worst_tail_spread"] or -999) > -.05,
            "top20_hit_rate": (common["median_top20_hit_rate"] or -999) >= (.50 if phase == "adaptive" else np.nextafter(.50, 1)),
            "turnover": (common["median_turnover"] or 999) <= 30,
            "concentration": (common["median_best10_contribution"] or 999) <= .35,
            "correlation": maximum_existing_correlation < .85,
        }
        if phase == "validation":
            checks["positive_excess_years"] = common["positive_csi300_excess_year_count"] >= 3
    checks = {key: bool(value) for key, value in checks.items()}
    return common | {"gate_results": checks, "gate_passed": all(checks.values()),
                     "failed_gates": [key for key, value in checks.items() if not value]}


def evaluate_locked(*, evaluator, normalized: pd.DataFrame, proposal: dict,
                    parameters: dict, orientation: int, periods: dict[str, tuple[str, str]],
                    phase: str) -> dict[str, Any]:
    compiled, values = factor_values(
        parse_template(proposal["template"]), evaluator.contract, parameters, evaluator.matrix,
    )
    similarities = [
        signal_similarity(values, prior) for _, prior in evaluator.known_values
    ]
    maximum = max(
        (abs(row["spearman"]) for row in similarities if row["spearman"] is not None),
        default=0.0,
    )
    before = evaluator.qlib.calls
    annual = []
    all_primary = []
    for year, period in periods.items():
        row = _year_result(evaluator, values, orientation, compiled.factor_instance_id, year, period, phase)
        tails = tail_observations(values, normalized, orientation, *period)
        row["tail"] = {
            "observation_count": len(tails),
            "non_overlapping_10_session_windows": True,
            "top20_universe_spread_mean": float(np.mean([x["top20_universe_spread"] for x in tails])) if tails else None,
            "q10_universe_spread_mean": float(np.mean([x["q10_universe_spread"] for x in tails])) if tails else None,
            "top20_hit_rate": float(np.mean([x["top20_hit"] for x in tails])) if tails else None,
            "observations": tails,
        }
        if proposal["primary_archetype"] == "monotonic_rank_factor":
            all_primary.extend(daily_rankic(values, evaluator.matrix, orientation, *period))
        else:
            all_primary.extend(x["top20_universe_spread"] for x in tails)
        annual.append(row)
    summary = _summary(annual, proposal["primary_archetype"], maximum, phase)
    lag = 10 if proposal["primary_archetype"] == "monotonic_rank_factor" else 1
    statistical = hac_mean_test(all_primary, lag=lag)
    statistical["primary_test_statistic"] = proposal["primary_test_statistic"]
    return {
        "factor_instance_id": compiled.factor_instance_id,
        "parameters": parameters, "orientation": orientation,
        "primary_archetype": proposal["primary_archetype"],
        "primary_test_statistic": proposal["primary_test_statistic"],
        "annual": annual, "summary": summary, "statistical_test": statistical,
        "qlib_calls": evaluator.qlib.calls - before, "values": values,
    }


def choose_orientation(*, evaluator, normalized: pd.DataFrame, proposal: dict,
                       parameters: dict, start: str, end: str) -> int:
    _, values = factor_values(parse_template(proposal["template"]), evaluator.contract, parameters, evaluator.matrix)
    if proposal["primary_archetype"] == "monotonic_rank_factor":
        sample = daily_rankic(values, evaluator.matrix, 1, start, end)
    else:
        sample = [row["top20_universe_spread"] for row in tail_observations(values, normalized, 1, start, end)]
    return 1 if not sample or float(np.mean(sample)) >= 0 else -1
