from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.services.engine.factor_validation.metrics import calculate_split_metrics, metrics_payload


YEAR_WINDOWS = {
    "2019": ("2019-01-02", "2019-12-31"), "2020": ("2020-01-02", "2020-12-31"),
    "2021": ("2021-01-04", "2021-12-31"), "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"), "2024": ("2024-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-30"), "2026H1": ("2026-01-05", "2026-06-23"),
}


def annual_factor_metrics(values: pd.DataFrame, labels: pd.DataFrame, orientation: int) -> dict:
    output = {}
    dates = pd.to_datetime(labels["trade_date"])
    for label, (start, end) in YEAR_WINDOWS.items():
        subset = labels[(dates >= start) & (dates <= end)]
        output[label] = metrics_payload(calculate_split_metrics(values, subset, orientation=orientation))
    return output


def eligible_evaluation_years(origin_round: int) -> tuple[str, ...]:
    first = {1: 2021, 2: 2022, 3: 2023, 4: 2024}[origin_round]
    return tuple(str(year) for year in range(first, 2025))


def lock_final_candidates(candidates: list[dict], annual_metrics: dict[str, dict],
                          qlib_metrics: dict[str, dict], maximum: int = 3) -> dict:
    rows = []
    for candidate in candidates:
        selected = candidate["selected_trial"]
        factor_id = selected["factor_instance_id"]
        years = eligible_evaluation_years(candidate["origin_round"])
        rank_values = [annual_metrics[factor_id][year]["mean_rank_ic"] for year in years]
        rank_values = [value for value in rank_values if value is not None]
        net_excess = [qlib_metrics.get(factor_id, {}).get(year, {}).get("net_excess") for year in years]
        net_excess = [value for value in net_excess if value is not None]
        positive_rank = sum(value > 0 for value in rank_values)
        mean_rank = float(np.mean(rank_values)) if rank_values else None
        positive_ratio = positive_rank / len(rank_values) if rank_values else 0.0
        positive_excess = sum(value > 0 for value in net_excess)
        eligible = (len(rank_values) >= 2 and positive_rank >= 2 and (mean_rank or 0) > 0 and
                    positive_ratio > 0.5 and positive_excess >= 1)
        rows.append({
            "factor_instance_id": factor_id, "origin_round": candidate["origin_round"],
            "evaluation_years": list(years), "mean_rank_ic": mean_rank,
            "positive_rank_ic_years": positive_rank, "rank_ic_positive_year_ratio": positive_ratio,
            "positive_net_excess_years": positive_excess, "eligible": eligible,
            "candidate": candidate,
        })
    rows.sort(key=lambda row: (
        row["eligible"], row["mean_rank_ic"] or -999, row["positive_rank_ic_years"],
        row["positive_net_excess_years"], row["factor_instance_id"],
    ), reverse=True)
    selected = [row for row in rows if row["eligible"]][:maximum]
    return {"maximum_candidates": maximum, "selection_data_end": "2024-12-31",
            "holdout_metrics_used": False, "ranked_candidates": rows,
            "selected_factor_instance_ids": [row["factor_instance_id"] for row in selected]}


def fixed_universe_equal_weight_benchmark(matrix: pd.DataFrame) -> pd.Series:
    data = matrix[["symbol", "trade_date", "close", "factor"]].copy()
    data["trade_date"] = pd.to_datetime(data["trade_date"])
    data["adjusted_close"] = pd.to_numeric(data["close"], errors="coerce") * pd.to_numeric(data["factor"], errors="coerce")
    data["return"] = data.sort_values(["symbol", "trade_date"]).groupby("symbol")["adjusted_close"].pct_change(fill_method=None)
    return data.groupby("trade_date")["return"].mean().sort_index().fillna(0.0)
