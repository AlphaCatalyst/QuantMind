from __future__ import annotations

import math

import numpy as np


def normal_survival(value: float) -> float:
    return 0.5 * math.erfc(value / math.sqrt(2.0))


def hac_mean_test(values: list[float], lag: int = 10) -> dict:
    sample = np.asarray([item for item in values if np.isfinite(item)], dtype=float)
    count = len(sample)
    if count < 2:
        return {
            "observation_count": count, "mean_rankic": None,
            "hac_standard_error": None, "t_statistic": None,
            "raw_p_value": 1.0, "hac_lag": lag,
        }
    centered = sample - sample.mean()
    long_run = float(centered @ centered / count)
    for distance in range(1, min(lag, count - 1) + 1):
        weight = 1.0 - distance / (lag + 1.0)
        covariance = float(centered[distance:] @ centered[:-distance] / count)
        long_run += 2.0 * weight * covariance
    standard_error = math.sqrt(max(long_run, 0.0) / count)
    statistic = float(sample.mean() / standard_error) if standard_error > 0 else (
        math.inf if sample.mean() > 0 else 0.0
    )
    return {
        "observation_count": count, "mean_rankic": float(sample.mean()),
        "hac_standard_error": standard_error, "t_statistic": statistic,
        "raw_p_value": normal_survival(statistic), "hac_lag": lag,
    }


def benjamini_hochberg(rows: list[dict], q: float = .10) -> list[dict]:
    count = len(rows)
    ordered = sorted(enumerate(rows), key=lambda pair: (pair[1]["raw_p_value"], pair[0]))
    adjusted = [1.0] * count
    running = 1.0
    for reverse_rank, (original, row) in enumerate(reversed(ordered), 1):
        rank = count - reverse_rank + 1
        running = min(running, row["raw_p_value"] * count / rank)
        adjusted[original] = min(1.0, running)
    ranks = {original: rank for rank, (original, _) in enumerate(ordered, 1)}
    return [
        row | {
            "adjusted_q_value": adjusted[index], "hypothesis_count": count,
            "rank_in_multiple_test": ranks[index],
            "fdr_threshold": q, "multiple_testing_passed": adjusted[index] <= q,
        }
        for index, row in enumerate(rows)
    ]
