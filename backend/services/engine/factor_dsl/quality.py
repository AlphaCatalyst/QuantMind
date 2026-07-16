import math


def factor_quality(frame, warmup_periods):
    values = frame["factor_value"]
    finite = values.dropna().map(math.isfinite)
    if not finite.all():
        raise ValueError("factor output contains infinity")
    non_null = int(values.notna().sum())
    rows = len(frame)
    daily_counts = frame.assign(_valid=values.notna()).groupby("trade_date")["_valid"].sum()
    warnings = []
    if non_null == 0:
        raise ValueError("factor output is entirely null")
    if values.dropna().nunique() <= 1:
        warnings.append("factor output is constant")
    if non_null / rows < 0.8:
        warnings.append("factor output finite coverage is below 80 percent")
    if (daily_counts < 2).any():
        warnings.append("one or more dates have fewer than two finite observations")
    return {"row_count": rows, "finite_count": non_null, "null_count": rows - non_null,
            "finite_ratio": non_null / rows, "unique_finite_values": int(values.dropna().nunique()),
            "date_count": int(frame["trade_date"].nunique()), "symbol_count": int(frame["symbol"].nunique()),
            "warmup_periods": warmup_periods, "warnings": warnings}
