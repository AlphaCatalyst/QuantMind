from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .legacy_models import ColumnRole, LegacyFeatureBatch


def evaluate_feature_matrix(batch: LegacyFeatureBatch) -> dict[str, Any]:
    frame = batch.frame
    schema = batch.inventory.schema
    roles = schema.role_map()
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, count: int, message: str) -> None:
        if count:
            issues.append({"code": code, "severity": severity, "count": int(count), "message": message})

    if frame.empty:
        add("EMPTY_RESULT", "error", 1, "Legacy feature selection returned no rows")
    missing_keys = [name for name in ("symbol", "trade_date") if name not in frame.columns]
    add("MISSING_KEY", "error", len(missing_keys), "Feature matrix is missing key columns")
    expected_features = list(batch.request.columns or schema.research_feature_columns)
    missing_features = [name for name in expected_features if name not in frame.columns]
    add("MISSING_FEATURE", "error", len(missing_features), "Requested research features are missing")
    if not frame.empty and not missing_keys:
        add(
            "DUPLICATE_KEY", "error",
            int(frame.duplicated(["symbol", "trade_date"]).sum()),
            "Duplicate symbol and trade_date",
        )
        symbols = frame["symbol"].astype("string")
        add("EMPTY_SYMBOL", "error", int((symbols.isna() | (symbols.str.len() == 0)).sum()), "Empty symbol")
        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        add("INVALID_DATE", "error", int(dates.isna().sum()), "Invalid trade_date")
        if dates.notna().any():
            outside = (dates.dt.date < batch.request.start_date) | (dates.dt.date > batch.request.end_date)
            add("DATE_OUT_OF_RANGE", "error", int(outside.sum()), "Date outside request")
        sorted_index = frame.sort_values(["trade_date", "symbol"], kind="mergesort").index
        add("UNSTABLE_SORT", "error", int(not sorted_index.equals(frame.index)), "Rows are not sorted by trade_date and symbol")

    exposed_labels = [name for name in frame.columns if roles.get(name) == ColumnRole.LABEL.value]
    if not batch.request.include_labels:
        add("LABEL_LEAKAGE", "error", len(exposed_labels), "Label is exposed in default feature view")
    exposed_forbidden = [
        name for name in frame.columns
        if roles.get(name) in {ColumnRole.FORBIDDEN.value, ColumnRole.UNKNOWN.value}
    ]
    add("FORBIDDEN_EXPOSURE", "error", len(exposed_forbidden), "Forbidden or unknown source column is exposed")

    for name in expected_features:
        if name not in frame.columns:
            continue
        series = frame[name]
        if not pd.api.types.is_numeric_dtype(series):
            add("FEATURE_DTYPE", "error", 1, f"Research feature {name} is not numeric")
            continue
        non_finite = series.notna() & ~series.map(lambda value: math.isfinite(float(value)))
        add("INFINITY", "error", int(non_finite.sum()), f"Research feature {name} contains Infinity")
        null_ratio = float(series.isna().mean()) if len(series) else 1.0
        add("ALL_NULL_FEATURE", "warning", int(null_ratio == 1.0), f"Research feature {name} is all null")
        add("HIGH_NAN_RATIO", "warning", int(null_ratio >= 0.5 and null_ratio < 1.0), f"Research feature {name} has at least 50 percent nulls")
        finite_values = series[series.notna() & ~non_finite]
        add("CONSTANT_FEATURE", "warning", int(not finite_values.empty and finite_values.nunique(dropna=True) <= 1), f"Research feature {name} is constant")

    add("UNKNOWN_SOURCE_ROLE", "warning", len(schema.unknown_columns), "Source contains columns with an unproven role; they are inaccessible")
    summary = {
        severity: sum(item["count"] for item in issues if item["severity"] == severity)
        for severity in ("error", "warning", "info")
    }
    return {
        "status": "error" if summary["error"] else "warning" if summary["warning"] else "passed",
        "summary": summary,
        "issues": issues,
        "access_policy": {
            "default_view": "keys_plus_research_features",
            "labels": "explicit_reader_only",
            "metadata": "not_exposed",
            "forbidden": "never_exposed",
            "unknown": "never_exposed",
        },
    }
