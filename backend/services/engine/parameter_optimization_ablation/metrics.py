from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

import numpy as np
import pandas as pd


def rankic_metrics(signal: pd.DataFrame, matrix: pd.DataFrame, start: str, end: str) -> dict[str, Any]:
    labels = matrix[matrix["trade_date"].between(start, end)][
        ["symbol", "trade_date", "model_label"]
    ]
    merged = signal.merge(labels, on=["symbol", "trade_date"], how="inner", validate="one_to_one")
    daily = merged.groupby("trade_date", sort=True).apply(
        lambda g: _spearman(g["pred"], g["model_label"])
        if g[["pred", "model_label"]].dropna().shape[0] >= 20 else np.nan,
        include_groups=False,
    ).dropna()
    if daily.empty:
        return {"mean_rankic": None, "rankicir": None, "rankic_positive_rate": None,
                "session_count": 0}
    std = daily.std(ddof=0)
    return {
        "mean_rankic": float(daily.mean()),
        "rankicir": None if std == 0 else float(daily.mean() / std),
        "rankic_positive_rate": float((daily > 0).mean()),
        "session_count": int(len(daily)),
    }


def clean_qlib(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "status", "gross_return", "net_return", "benchmark_return", "net_excess_csi300",
        "sharpe_ratio", "max_drawdown", "turnover", "transaction_cost",
        "best_10_days_contribution", "return_without_best_10_days", "formal_chain",
    )
    return {key: result.get(key) for key in keys}


def selection_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    rankics = [float(row["rankic"]) for row in rows if row.get("rankic") is not None]
    excess = [float(row["excess"]) for row in rows if row.get("excess") is not None]
    drawdowns = [abs(float(row["maximum_drawdown"])) for row in rows if row.get("maximum_drawdown") is not None]
    turnover = [float(row["turnover"]) for row in rows if row.get("turnover") is not None]
    cost = [float(row["transaction_cost"]) for row in rows if row.get("transaction_cost") is not None]
    return {
        "positive_rankic_year_count": sum(value > 0 for value in rankics),
        "median_rankic": _median(rankics), "worst_rankic": min(rankics) if rankics else None,
        "positive_csi300_excess_year_count": sum(value > 0 for value in excess),
        "median_csi300_excess": _median(excess), "worst_csi300_excess": min(excess) if excess else None,
        "maximum_drawdown_abs": max(drawdowns) if drawdowns else None,
        "turnover": sum(turnover), "transaction_cost": sum(cost),
        "eligible": len(rankics) == len(rows) and len(excess) == len(rows),
    }


def ordering_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metric = row["selection_metrics"]
    return (
        -metric["positive_rankic_year_count"], -metric["median_rankic"],
        -metric["worst_rankic"], -metric["positive_csi300_excess_year_count"],
        -metric["median_csi300_excess"], -metric["worst_csi300_excess"],
        metric["maximum_drawdown_abs"], metric["turnover"],
        metric["transaction_cost"], row.get("configuration_id", row["trial_id"]),
    )


def select_trial(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["selection_metrics"].get("eligible")]
    if not eligible:
        raise RuntimeError("no eligible parameter ablation trial")
    return min(eligible, key=ordering_key)


def parameter_consistency(parameter_rows: list[dict[str, Any]], legal_rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = sorted({key for row in parameter_rows for key in row})
    exact = 1.0 if parameter_rows and all(row == parameter_rows[0] for row in parameter_rows) else 0.0
    adjacent_pairs = 0
    for left, right in zip(parameter_rows, parameter_rows[1:]):
        adjacent_pairs += int(_adjacent(left, right, legal_rows))
    adjacent_rate = 1.0 if len(parameter_rows) <= 1 else adjacent_pairs / (len(parameter_rows) - 1)
    dispersion = {}
    for key in keys:
        values = [float(row[key]) for row in parameter_rows]
        dispersion[key] = float(np.std(values, ddof=0))
    return {
        "exact_match_rate": exact, "adjacent_match_rate": adjacent_rate,
        "parameter_dispersion": dispersion,
        "fold_parameter_instability": adjacent_rate < 0.5,
    }


def plateau_analysis(selected: dict[str, Any], trials: list[dict[str, Any]], parameter_fields: tuple[str, ...]) -> dict[str, Any]:
    neighbors = [row for row in trials if row["trial_id"] != selected["trial_id"] and
                 sum(row.get(key) != selected.get(key) for key in parameter_fields) == 1]
    best_rankic = selected["selection_metrics"]["median_rankic"]
    best_excess = selected["selection_metrics"]["median_csi300_excess"]
    rankic_pass = [row for row in neighbors if row["selection_metrics"]["median_rankic"] >= best_rankic - 0.003]
    excess_pass = [row for row in neighbors if row["selection_metrics"]["median_csi300_excess"] >= best_excess - 0.10]
    denominator = len(neighbors)
    rankic_ratio = 1.0 if denominator == 0 else len(rankic_pass) / denominator
    excess_ratio = 1.0 if denominator == 0 else len(excess_pass) / denominator
    ratio = min(rankic_ratio, excess_ratio)
    return {
        "selected_trial_id": selected["trial_id"], "neighbor_count": denominator,
        "plateau_ratio_rankic": rankic_ratio, "plateau_ratio_excess": excess_ratio,
        "plateau_ratio": ratio,
        "classification": "broad_plateau" if ratio >= 0.70 else
        "acceptable_plateau" if ratio >= 0.50 else "sharp_peak",
    }


def rank_stability(research: dict[str, float], later: dict[str, float], selected_trial_id: str,
                   label: str) -> dict[str, Any]:
    common = sorted(set(research) & set(later))
    left = pd.Series([research[key] for key in common])
    right = pd.Series([later[key] for key in common])
    later_order = sorted(common, key=lambda key: (-later[key], key))
    percentile = None
    if selected_trial_id in later_order:
        percentile = 1.0 if len(later_order) == 1 else 1 - later_order.index(selected_trial_id) / (len(later_order) - 1)
    return {
        "period": label, "trial_count": len(common),
        "spearman_rank_correlation": _spearman(left, right),
        "kendall_rank_correlation": _kendall(left, right),
        "selected_trial_later_percentile": percentile,
    }


def gains(optimized: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "rankic": _difference(optimized.get("mean_rankic"), baseline.get("mean_rankic")),
        "csi300_excess": _difference(optimized.get("net_csi300_excess"), baseline.get("net_csi300_excess")),
        "sharpe": _difference(optimized.get("sharpe_ratio"), baseline.get("sharpe_ratio")),
        "drawdown": _difference(
            None if optimized.get("maximum_drawdown") is None else -abs(optimized["maximum_drawdown"]),
            None if baseline.get("maximum_drawdown") is None else -abs(baseline["maximum_drawdown"]),
        ),
    }


@dataclass(frozen=True)
class ParameterOptimizationOverfitPolicyV1:
    minimum_plateau_ratio: float = 0.50
    minimum_adjacent_match_rate: float = 0.50
    later_bottom_percentile: float = 0.50
    significant_excess_gap: float = 0.05

    def classify(self, research_gain: dict[str, Any], report_gains: list[dict[str, Any]],
                 plateau_ratio: float, adjacent_rate: float,
                 later_percentiles: list[float | None]) -> str:
        research = float(research_gain.get("csi300_excess") or 0.0)
        reports = [float(row.get("csi300_excess") or 0.0) for row in report_gains]
        average_report = float(np.mean(reports)) if reports else 0.0
        robust = (research > 0 and all(value >= 0 for value in reports)
                  and plateau_ratio >= self.minimum_plateau_ratio
                  and adjacent_rate >= self.minimum_adjacent_match_rate)
        observed = [value for value in later_percentiles if value is not None]
        later_bottom = len(observed) == 2 and all(
            value < self.later_bottom_percentile for value in observed)
        overfit = (research > 0 and average_report < 0) or later_bottom or (
            plateau_ratio < self.minimum_plateau_ratio
            and research - average_report > self.significant_excess_gap
        )
        return "likely_robust" if robust else "likely_overfit" if overfit else "inconclusive"


def classify_overfit(research_gain: dict[str, Any], report_gains: list[dict[str, Any]],
                     plateau_ratio: float, adjacent_rate: float,
                     later_percentiles: list[float | None]) -> str:
    return ParameterOptimizationOverfitPolicyV1().classify(
        research_gain, report_gains, plateau_ratio, adjacent_rate, later_percentiles)


def _adjacent(left: dict[str, Any], right: dict[str, Any], legal: list[dict[str, Any]]) -> bool:
    if left == right:
        return True
    differing = [key for key in set(left) | set(right) if left.get(key) != right.get(key)]
    if len(differing) != 1:
        return False
    key = differing[0]
    values = sorted({row[key] for row in legal if key in row})
    return abs(values.index(left[key]) - values.index(right[key])) <= 1


def _median(values: list[float]) -> float | None:
    return None if not values else float(median(values))


def _difference(left: Any, right: Any) -> float | None:
    return None if left is None or right is None else float(left) - float(right)


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    pair = pd.concat([pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")], axis=1).dropna()
    if len(pair) < 2 or pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return None
    return float(pair.iloc[:, 0].rank(method="average").corr(pair.iloc[:, 1].rank(method="average")))


def _kendall(left: pd.Series, right: pd.Series) -> float | None:
    pair = pd.concat([pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")], axis=1).dropna()
    concordant = discordant = 0
    values = pair.to_numpy()
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            product = (values[i, 0] - values[j, 0]) * (values[i, 1] - values[j, 1])
            concordant += product > 0
            discordant += product < 0
    denominator = concordant + discordant
    return None if denominator == 0 else float((concordant - discordant) / denominator)
