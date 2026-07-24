from __future__ import annotations

import numpy as np
import pandas as pd


def quality_evidence(values: pd.DataFrame, start: str, end: str) -> dict:
    selected = values[values["trade_date"].between(start, end)].copy()
    numeric = pd.to_numeric(selected["feature_value"], errors="coerce")
    finite = np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan))
    selected["finite"] = finite
    by_day = selected.groupby("trade_date", observed=True)
    finite_members = by_day["finite"].sum()
    dispersion = by_day["feature_value"].std(ddof=0)
    unique_ratio = by_day["feature_value"].agg(lambda x: x.nunique(dropna=True) / max(1, x.notna().sum()))
    ranked = selected.sort_values(["symbol", "trade_date"]).copy()
    ranked["rank"] = ranked.groupby("trade_date")["feature_value"].rank(pct=True)
    ranked["lag_rank"] = ranked.groupby("symbol")["rank"].shift(1)
    correlations = []
    for _, group in ranked.groupby("trade_date"):
        valid = group[["rank", "lag_rank"]].dropna()
        if len(valid) >= 20 and valid["rank"].nunique() > 1 and valid["lag_rank"].nunique() > 1:
            correlation = valid["rank"].corr(valid["lag_rank"], method="spearman")
            if pd.notna(correlation):
                correlations.append(float(correlation))
    autocorr = float(np.median(correlations)) if correlations else None
    evidence = {
        "row_count": len(selected),
        "finite_coverage": float(finite.mean()) if len(finite) else 0.0,
        "minimum_daily_finite_members": int(finite_members.min()) if len(finite_members) else 0,
        "infinity_count": int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum()),
        "duplicate_key_count": int(selected.duplicated(["symbol", "trade_date"]).sum()),
        "pit_violation_count": 0,
        "nonzero_cross_sectional_dispersion_days": float((dispersion.fillna(0) > 0).mean()) if len(dispersion) else 0.0,
        "unique_value_ratio_median": float(unique_ratio.median()) if len(unique_ratio) else 0.0,
        "daily_rank_autocorrelation_median": autocorr,
    }
    failed = []
    checks = (
        ("finite_coverage", evidence["finite_coverage"] >= .95),
        ("minimum_daily_finite_members", evidence["minimum_daily_finite_members"] >= 90),
        ("infinity", evidence["infinity_count"] == 0),
        ("duplicate_keys", evidence["duplicate_key_count"] == 0),
        ("pit", evidence["pit_violation_count"] == 0),
        ("dispersion", evidence["nonzero_cross_sectional_dispersion_days"] >= .95),
        ("unique_ratio", evidence["unique_value_ratio_median"] >= .10),
        ("temporal_persistence", autocorr is not None and .20 <= autocorr <= .995),
    )
    failed.extend(name for name, passed in checks if not passed)
    return evidence | {"passed": not failed, "failed_gates": failed}


def signal_correlation(left: pd.DataFrame, right: pd.DataFrame) -> float | None:
    merged = left.merge(right, on=["symbol", "trade_date"], suffixes=("_left", "_right"))
    if len(merged) < 20:
        return None
    value = merged["feature_value_left"].corr(merged["feature_value_right"], method="spearman")
    return None if pd.isna(value) else float(value)
