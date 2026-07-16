import math

import numpy as np
import pandas as pd

from .errors import ValidationArtifactError
from .models import SplitMetrics


def _pearson(left, right, minimum_observations=20):
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < minimum_observations:
        return math.nan
    x = x[mask]; y = y[mask]
    if np.std(x, ddof=0) == 0 or np.std(y, ddof=0) == 0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def _rank_ic(left, right, minimum_observations=20):
    pair = pd.DataFrame({"left": left, "right": right}).dropna()
    pair = pair[np.isfinite(pair["left"]) & np.isfinite(pair["right"])]
    if len(pair) < minimum_observations:
        return math.nan
    return _pearson(pair["left"].rank(method="average"), pair["right"].rank(method="average"), minimum_observations)


def _nullable(value):
    return None if value is None or not np.isfinite(value) else float(value)


def calculate_split_metrics(factor_values, labels, *, label_column="model_label", orientation=1, minimum_observations=20):
    if factor_values.duplicated(["symbol", "trade_date"]).any() or labels.duplicated(["symbol", "trade_date"]).any():
        raise ValidationArtifactError("factor/label alignment keys must be unique")
    left = factor_values[["symbol", "trade_date", "factor_value"]].copy()
    right = labels[["symbol", "trade_date", label_column]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]); right["trade_date"] = pd.to_datetime(right["trade_date"])
    merged = right.merge(left, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    merged["factor_value"] = pd.to_numeric(merged["factor_value"], errors="coerce") * orientation
    merged[label_column] = pd.to_numeric(merged[label_column], errors="coerce")
    finite_factor = np.isfinite(merged["factor_value"])
    finite_label = np.isfinite(merged[label_column])
    valid = finite_factor & finite_label
    total = len(merged)
    daily = []
    for trade_date, group in merged.groupby("trade_date", sort=True):
        group_valid = np.isfinite(group["factor_value"]) & np.isfinite(group[label_column])
        count = int(group_valid.sum())
        daily.append({"trade_date": trade_date, "rows": len(group), "valid": count,
                      "coverage": count / len(group) if len(group) else 0.0,
                      "ic": _pearson(group["factor_value"], group[label_column], minimum_observations),
                      "rank_ic": _rank_ic(group["factor_value"], group[label_column], minimum_observations)})
    daily_frame = pd.DataFrame(daily)
    ic = daily_frame["ic"].dropna().to_numpy(dtype=float)
    rank_ic = daily_frame["rank_ic"].dropna().to_numpy(dtype=float)
    def summary(values):
        if len(values) == 0: return None, None, None, None
        mean = float(np.mean(values)); std = float(np.std(values, ddof=0))
        return mean, std, None if std == 0 else mean/std, float(np.mean(values > 0))
    mean_ic, std_ic, icir, ic_positive = summary(ic)
    mean_rank, std_rank, rank_icir, rank_positive = summary(rank_ic)
    finite_values = merged.loc[finite_factor, "factor_value"]
    return SplitMetrics(
        int(merged["trade_date"].nunique()), int(len(rank_ic)), int(valid.sum()),
        _nullable(mean_ic), _nullable(std_ic), _nullable(icir), _nullable(ic_positive),
        _nullable(mean_rank), _nullable(std_rank), _nullable(rank_icir), _nullable(rank_positive),
        float(daily_frame["coverage"].median()) if len(daily_frame) else 0.0,
        float(daily_frame["coverage"].min()) if len(daily_frame) else 0.0,
        float(daily_frame["valid"].median()) if len(daily_frame) else 0.0,
        int(daily_frame["valid"].min()) if len(daily_frame) else 0,
        float(finite_factor.sum()/total) if total else 0.0,
        float(finite_label.sum()/total) if total else 0.0,
        bool(len(finite_values) > 0 and finite_values.nunique() <= 1),
    )


def metrics_payload(metrics):
    return dict(metrics.__dict__)


def train_orientation(metrics):
    if metrics.date_count_valid < 1 or metrics.mean_rank_ic is None:
        return None
    return 1 if metrics.mean_rank_ic >= 0 else -1


def selection_eligibility(train_metrics, validation_metrics, requirements):
    reasons = []
    if train_metrics.date_count_valid < requirements["train_minimum_valid_rank_ic_dates"]: reasons.append("train_valid_rank_ic_dates_below_gate")
    if train_metrics.median_daily_observations < requirements["train_minimum_median_daily_observations"]: reasons.append("train_daily_observations_below_gate")
    if train_metrics.factor_finite_coverage < requirements["minimum_factor_finite_coverage"]: reasons.append("train_factor_coverage_below_gate")
    if train_metrics.constant_output: reasons.append("train_constant_output")
    if validation_metrics.date_count_valid < requirements["validation_minimum_valid_rank_ic_dates"]: reasons.append("validation_valid_rank_ic_dates_below_gate")
    if validation_metrics.median_daily_observations < requirements["validation_minimum_median_daily_observations"]: reasons.append("validation_daily_observations_below_gate")
    if validation_metrics.factor_finite_coverage < requirements["minimum_factor_finite_coverage"]: reasons.append("validation_factor_coverage_below_gate")
    if validation_metrics.rank_icir is None: reasons.append("validation_rank_icir_unavailable")
    if validation_metrics.mean_rank_ic is None or validation_metrics.mean_rank_ic <= 0: reasons.append("validation_mean_rank_ic_not_positive")
    if validation_metrics.rank_ic_positive_rate is None or validation_metrics.rank_ic_positive_rate <= 0.50: reasons.append("validation_rank_ic_positive_rate_not_above_half")
    return not reasons, tuple(reasons)
