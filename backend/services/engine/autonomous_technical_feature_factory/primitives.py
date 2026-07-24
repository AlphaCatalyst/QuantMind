from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.default_first_momentum_search.protocol import SOURCE_DATASET_ID
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload


PRIMITIVE_FORMULAS = {
    "overnight_gap": "adjusted_open / lag(adjusted_close, 1) - 1",
    "intraday_return": "adjusted_close / adjusted_open - 1",
    "high_low_range": "(adjusted_high - adjusted_low) / lag(adjusted_close, 1)",
    "close_location_value": "(adjusted_close - adjusted_low) / (adjusted_high - adjusted_low)",
    "close_vs_vwap": "adjusted_close / (vwap * adj_factor) - 1",
    "turnover_pressure": "turnover_rate / rolling_mean(turnover_rate, 20)",
}


def primitive_values(frame: pd.DataFrame) -> dict[str, pd.Series]:
    grouped = frame.groupby("symbol", sort=False)
    prior_close = grouped["adjusted_close"].shift(1)
    adjusted_vwap = frame["vwap"] * frame["adj_factor"]
    turnover_mean = grouped["turnover_rate"].transform(
        lambda value: value.rolling(20, min_periods=20).mean()
    )
    def safe_divide(numerator, denominator):
        return numerator / denominator.where(denominator.abs() > 1e-12)
    return {
        "overnight_gap": safe_divide(frame["adjusted_open"], prior_close) - 1,
        "intraday_return": safe_divide(frame["adjusted_close"], frame["adjusted_open"]) - 1,
        "high_low_range": safe_divide(frame["adjusted_high"] - frame["adjusted_low"], prior_close),
        "close_location_value": safe_divide(
            frame["adjusted_close"] - frame["adjusted_low"],
            frame["adjusted_high"] - frame["adjusted_low"],
        ),
        "close_vs_vwap": safe_divide(frame["adjusted_close"], adjusted_vwap) - 1,
        "turnover_pressure": safe_divide(frame["turnover_rate"], turnover_mean),
    }


def build_primitive_catalog(*, repository, frame: pd.DataFrame, work_root: Path,
                            operator_extension_id: str) -> tuple[dict[str, Any], dict[str, int]]:
    required = {
        "adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close",
        "volume", "amount", "vwap", "adj_factor", "turnover_rate",
    }
    missing = sorted(required - set(frame))
    if missing:
        raise ValueError(f"Primitive inputs missing from formal Artifact: {missing}")
    values_by_name = primitive_values(frame)
    rows = []
    counts = {"primitive_writes": 0, "new_artifacts": 0, "new_blobs": 0}
    for name in PRIMITIVE_FORMULAS:
        values = frame[["symbol", "trade_date"]].copy()
        values["feature_value"] = values_by_name[name].replace([np.inf, -np.inf], np.nan)
        path = Path(work_root) / "primitives" / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        values.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
        finite = np.isfinite(values["feature_value"].to_numpy(dtype=float, na_value=np.nan))
        coverage = float(finite.mean())
        materialization = {
            "schema_version": "technical-primitive-materialization-v2",
            "provider_id": "tushare-pro-v1",
            "primitive_name": name,
            "dataset_id": SOURCE_DATASET_ID,
            "formula": PRIMITIVE_FORMULAS[name],
            "row_count": len(values),
            "minimum_date": values["trade_date"].min(),
            "maximum_date": values["trade_date"].max(),
            "finite_coverage": coverage,
            "infinity_count": int(np.isinf(values["feature_value"]).sum()),
            "duplicate_key_count": int(values.duplicated(["symbol", "trade_date"]).sum()),
            "pit_violation_count": 0,
            "values_sha256": hash_file(path),
            "status": "research_technical_primitive",
            "usable_for_production": False,
            "promotion_writes": 0,
        }
        receipt = repository.publish(
            "technical_primitive_materialization", materialization,
            {"primitive_values.parquet": path, "materialization.json": materialization},
            lineage=(SOURCE_DATASET_ID, operator_extension_id),
        )
        counts["primitive_writes"] += int(not receipt["exact_existing"])
        counts["new_artifacts"] += int(not receipt["exact_existing"])
        counts["new_blobs"] += receipt["new_blob_count"]
        rows.append({
            "primitive_id": "tpv2_" + hash_payload({
                "name": name, "formula": PRIMITIVE_FORMULAS[name],
                "materialization_id": receipt["artifact_id"],
            }),
            "name": name,
            "formula": PRIMITIVE_FORMULAS[name],
            "input_artifacts": [SOURCE_DATASET_ID],
            "pit_contract": "same_row_or_trailing_symbol_history_only",
            "adjustment_policy": (
                "adjusted OHLC; vwap multiplied by contemporaneous adj_factor"
                if name == "close_vs_vwap" else "uses formally normalized input fields"
            ),
            "availability_date": values.loc[finite, "trade_date"].min() if finite.any() else None,
            "coverage": coverage,
            "zero_division_policy": "return_nan_when_absolute_denominator_at_or_below_1e-12",
            "materialization_id": receipt["artifact_id"],
            "status": "research_technical_primitive",
            "usable_for_production": False,
        })
    stable = {
        "schema_version": "technical-primitive-catalog-v2",
        "provider_id": "tushare-pro-v1",
        "dataset_id": SOURCE_DATASET_ID,
        "operator_extension_id": operator_extension_id,
        "primitives": rows,
        "primitive_count": len(rows),
        "frozen": True,
        "research_only": True,
        "tushare_calls": 0,
        "network_data_calls": 0,
        "promotion_writes": 0,
    }
    receipt = repository.publish(
        "technical_primitive_catalog", stable,
        {"technical_primitive_catalog_v2.json": stable},
        lineage=(SOURCE_DATASET_ID, operator_extension_id, *[row["materialization_id"] for row in rows]),
    )
    counts["new_artifacts"] += int(not receipt["exact_existing"])
    counts["new_blobs"] += receipt["new_blob_count"]
    return stable | {"primitive_catalog_id": receipt["artifact_id"]}, counts
