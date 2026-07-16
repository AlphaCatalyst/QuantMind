import math
from pathlib import Path

import numpy as np
import pandas as pd

from .models import MechanicalMetrics


def compute_mechanical_metrics(factor_values_path, warmup_periods):
    frame = pd.read_parquet(Path(factor_values_path) / "values.parquet", columns=["symbol", "trade_date", "factor_value"])
    values = frame["factor_value"].astype(float)
    infinity_count = int(np.isinf(values.to_numpy()).sum())
    finite_mask = np.isfinite(values.to_numpy())
    finite = values[finite_mask]
    daily_rows = frame.groupby("trade_date", sort=True).size()
    daily_finite = frame.assign(_finite=finite_mask).groupby("trade_date", sort=True)["_finite"].sum()
    daily_coverage = daily_finite / daily_rows
    non_null_count = int(values.notna().sum())
    finite_count = int(finite_mask.sum())
    def stat(method):
        return None if finite.empty else float(method(finite.to_numpy()))
    return MechanicalMetrics(
        row_count=len(frame), non_null_count=non_null_count, null_count=int(values.isna().sum()),
        finite_coverage=finite_count/len(frame) if len(frame) else 0.0,
        symbol_count=int(frame["symbol"].nunique()), date_count=int(frame["trade_date"].nunique()),
        warmup_periods=int(warmup_periods), warmup_date_count=int((daily_finite == 0).sum()),
        median_daily_finite_symbols=float(daily_finite.median()) if len(daily_finite) else 0.0,
        minimum_daily_finite_symbols=int(daily_finite.min()) if len(daily_finite) else 0,
        maximum_daily_finite_symbols=int(daily_finite.max()) if len(daily_finite) else 0,
        daily_coverage_median=float(daily_coverage.median()) if len(daily_coverage) else 0.0,
        daily_coverage_minimum=float(daily_coverage.min()) if len(daily_coverage) else 0.0,
        global_mean=stat(np.mean), global_std=stat(lambda x: np.std(x, ddof=0)),
        global_min=stat(np.min), global_max=stat(np.max),
        unique_finite_count=int(finite.nunique()), constant_output=bool(not finite.empty and finite.nunique() <= 1),
        infinity_count=infinity_count,
    )


def metrics_payload(metrics):
    return dict(metrics.__dict__)
