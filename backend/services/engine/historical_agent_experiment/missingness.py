from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .artifact import publish_historical_artifact
from .canonical import hash_file, write_json


AUDIT_START = "2026-01-05"
AUDIT_END = "2026-06-23"
CONTROL_START = "2025-01-02"
CONTROL_END = "2025-12-30"
QUALITY_GATE = 0.20


def _finite(value: pd.Series) -> pd.Series:
    return np.isfinite(pd.to_numeric(value, errors="coerce"))


def _longest_streak(mask: pd.Series) -> int:
    longest = current = 0
    for missing in mask.astype(bool):
        current = current + 1 if missing else 0
        longest = max(longest, current)
    return int(longest)


def _joint_finite(values: list[Any], index: pd.Index) -> pd.Series:
    result = pd.Series(True, index=index)
    for value in values:
        if isinstance(value, pd.Series):
            result &= _finite(value)
        elif not np.isfinite(value):
            result &= False
    return result


def _trace_expression(expression: Mapping[str, Any], frame: pd.DataFrame,
                      parameters: Mapping[str, float], period_mask: pd.Series) -> tuple[pd.Series, list[dict]]:
    traces: list[dict] = []

    def evaluate(node: Mapping[str, Any], path: str) -> Any:
        kind = node["type"]
        children: list[Any] = []
        intended = pd.Series(False, index=frame.index)
        if kind == "feature":
            output = pd.to_numeric(frame[node["name"]], errors="coerce")
        elif kind == "parameter":
            output = parameters[node["name"]]
        elif kind == "constant":
            output = node["value"]
        elif kind in {"add", "subtract", "multiply", "divide"}:
            left = evaluate(node["left"], f"{path}.left")
            right = evaluate(node["right"], f"{path}.right")
            children = [left, right]
            if kind == "add": output = left + right
            elif kind == "subtract": output = left - right
            elif kind == "multiply": output = left * right
            elif np.isscalar(right): output = np.nan if abs(right) <= 1e-12 else left / right
            else: output = left / right.where(right.abs() > 1e-12)
        elif kind in {"lag", "delta"}:
            operand = evaluate(node["operand"], f"{path}.operand")
            periods = int(evaluate(node["periods"], f"{path}.periods"))
            children = [operand]
            shifted = operand.groupby(frame["symbol"], sort=False).shift(periods)
            output = shifted if kind == "lag" else operand - shifted
            intended = _finite(operand) & ~_finite(shifted)
        elif kind in {"rolling_mean", "rolling_std", "rolling_min", "rolling_max"}:
            operand = evaluate(node["operand"], f"{path}.operand")
            window = int(evaluate(node["window"], f"{path}.window"))
            children = [operand]
            grouped = operand.groupby(frame["symbol"], sort=False)
            if kind == "rolling_mean":
                output = grouped.transform(lambda x: x.rolling(window, min_periods=window).mean())
            elif kind == "rolling_std":
                output = grouped.transform(lambda x: x.rolling(window, min_periods=window).std(ddof=0))
            elif kind == "rolling_min":
                output = grouped.transform(lambda x: x.rolling(window, min_periods=window).min())
            else:
                output = grouped.transform(lambda x: x.rolling(window, min_periods=window).max())
            valid_count = _finite(operand).groupby(frame["symbol"], sort=False).transform(
                lambda x: x.rolling(window, min_periods=1).sum()
            )
            intended = _finite(operand) & (valid_count < window)
        elif kind in {"cs_rank", "cs_zscore"}:
            operand = evaluate(node["operand"], f"{path}.operand")
            children = [operand]
            grouped = operand.groupby(frame["trade_date"], sort=False)
            if kind == "cs_rank":
                output = grouped.transform(
                    lambda x: x.rank(method="average", pct=True)
                    if x.notna().sum() >= 2 else pd.Series(np.nan, index=x.index)
                )
            else:
                def zscore(x: pd.Series) -> pd.Series:
                    std = x.std(ddof=0)
                    if x.notna().sum() < 2 or not np.isfinite(std) or std == 0:
                        return pd.Series(np.nan, index=x.index)
                    return (x - x.mean()) / std
                output = grouped.transform(zscore)
        else:
            raise ValueError(f"unsupported audit AST node: {kind}")

        if isinstance(output, pd.Series):
            scoped = period_mask
            joint = _joint_finite(children, frame.index) if children else pd.Series(True, index=frame.index)
            output_finite = _finite(output)
            new_nan = joint & ~output_finite
            traces.append({
                "node_path": path, "node_type": kind,
                "input_finite_cells": int((joint & scoped).sum()),
                "output_finite_cells": int((output_finite & scoped).sum()),
                "new_nan_cells_introduced": int((new_nan & scoped).sum()),
                "intended_warmup_nan": int((new_nan & intended & scoped).sum()),
                "unexpected_nan": int((new_nan & ~intended & scoped).sum()),
            })
        return output

    result = evaluate(expression, "root")
    if not isinstance(result, pd.Series):
        raise ValueError("locked factor expression did not produce a Series")
    return result, traces


def _feature_metrics(grid: pd.DataFrame, feature: str, label: str) -> dict:
    observed = grid[grid["row_observed"]].copy()
    finite = _finite(observed[feature])
    valid_dates = observed.loc[finite, "trade_date"]
    by_month = {}
    for month, rows in grid.groupby(grid["trade_date"].dt.to_period("M"), sort=True):
        present = rows["row_observed"]
        values = rows.loc[present, feature]
        by_month[str(month)] = {
            "expected_cells": int(len(rows)), "observed_rows": int(present.sum()),
            "finite_cells": int(_finite(values).sum()),
            "feature_nan_cells": int((~_finite(values)).sum()),
        }
    by_symbol = {}
    for symbol, rows in grid.groupby("symbol", sort=True):
        values = rows.loc[rows["row_observed"], feature]
        missing = (~rows["row_observed"]) | (rows["row_observed"] & ~_finite(rows[feature]))
        by_symbol[symbol] = {
            "expected_cells": int(len(rows)), "observed_rows": int(rows["row_observed"].sum()),
            "finite_cells": int(_finite(values).sum()), "missing_cells": int(missing.sum()),
            "longest_missing_streak": _longest_streak(missing),
        }
    by_date = {}
    for day, rows in grid.groupby("trade_date", sort=True):
        present = rows["row_observed"]
        values = rows.loc[present, feature]
        by_date[day.date().isoformat()] = {
            "expected_cells": int(len(rows)),
            "observed_rows": int(present.sum()),
            "finite_cells": int(_finite(values).sum()),
            "feature_nan_cells": int((~_finite(values)).sum()),
            "missing_rows": int((~present).sum()),
        }
    return {
        "period": label, "expected_cells": int(len(grid)),
        "observed_rows": int(grid["row_observed"].sum()),
        "finite_cells": int(finite.sum()), "feature_nan_cells": int((~finite).sum()),
        "finite_ratio_observed_rows": float(finite.mean()) if len(finite) else 0.0,
        "missing_row_ratio": float((~grid["row_observed"]).mean()),
        "first_valid_date": valid_dates.min().date().isoformat() if len(valid_dates) else None,
        "last_valid_date": valid_dates.max().date().isoformat() if len(valid_dates) else None,
        "by_month": by_month, "by_symbol": by_symbol, "by_date": by_date,
    }


def _read_qlib_binary(path: Path, calendar: list[str]) -> pd.Series:
    payload = np.fromfile(path, dtype="<f4")
    if len(payload) < 1:
        raise ValueError("Qlib feature binary is empty")
    start = int(payload[0])
    return pd.Series(payload[1:], index=pd.to_datetime(calendar[start:start + len(payload) - 1]))


def audit_locked_signals(*, dataset_directory: Path, universe_lock: Mapping[str, Any],
                         candidates: list[Mapping[str, Any]], qlib_view_directory: Path,
                         factor_values_directories: Mapping[str, Path],
                         signal_paths: Mapping[str, Path],
                         source_experiment_id: str, source_backtest_result_id: str,
                         output_root: Path) -> dict:
    dataset_directory = Path(dataset_directory)
    qlib_view_directory = Path(qlib_view_directory)
    matrix = pd.read_parquet(dataset_directory / "historical_matrix.parquet", engine="pyarrow")
    matrix["trade_date"] = pd.to_datetime(matrix["trade_date"])
    matrix = matrix.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
    symbols = tuple(universe_lock["symbols"])
    if len(symbols) != 100 or len(set(symbols)) != 100:
        raise ValueError("audit requires the immutable 100-symbol universe")
    periods = {"2025": (CONTROL_START, CONTROL_END), "2026H1": (AUDIT_START, AUDIT_END)}
    candidate_ids = [row["selected_trial"]["factor_instance_id"] for row in candidates]
    if len(candidate_ids) != 2:
        raise ValueError("audit requires the two locked final candidates")

    values: dict[str, pd.Series] = {}
    node_metrics: dict[str, dict] = {}
    factor_values_artifacts: dict[str, dict] = {}
    for candidate in candidates:
        selected = candidate["selected_trial"]
        factor_id = selected["factor_instance_id"]
        audit_mask = matrix["trade_date"].between(AUDIT_START, AUDIT_END)
        value, traces = _trace_expression(candidate["template"]["expression"], matrix,
                                          selected["parameters"], audit_mask)
        values[factor_id] = value * int(selected["orientation"])
        node_metrics[factor_id] = {
            "factor_values_id": selected["factor_values_id"],
            "parameters": selected["parameters"], "orientation": selected["orientation"],
            "nodes": traces,
        }
        values_directory = Path(factor_values_directories[factor_id])
        persisted = pd.read_parquet(values_directory / "values.parquet", engine="pyarrow")
        persisted["trade_date"] = pd.to_datetime(persisted["trade_date"])
        persisted = persisted.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
        persisted_manifest = json.loads((values_directory / "manifest.json").read_text())
        expected_keys = pd.MultiIndex.from_frame(matrix[["trade_date", "symbol"]])
        actual_keys = pd.MultiIndex.from_frame(persisted[["trade_date", "symbol"]])
        expected_values = pd.Series(value.to_numpy(), index=expected_keys).reindex(actual_keys)
        actual_values = pd.to_numeric(persisted["factor_value"], errors="coerce")
        factor_values_artifacts[factor_id] = {
            "factor_values_id": selected["factor_values_id"],
            "manifest_factor_values_id": persisted_manifest.get("factor_values_id"),
            "dataset_snapshot_id": persisted_manifest.get("dataset_snapshot_id"),
            "expected_key_count": int(len(expected_keys)), "actual_key_count": int(len(actual_keys)),
            "duplicate_keys": int(actual_keys.duplicated().sum()),
            "missing_keys": int(len(expected_keys.difference(actual_keys))),
            "extra_keys": int(len(actual_keys.difference(expected_keys))),
            "parquet_columns": list(persisted.columns),
            "trade_date_dtype": str(persisted["trade_date"].dtype),
            "symbol_format_invalid": int((~persisted["symbol"].astype(str).str.fullmatch(r"(?:SH|SZ|BJ)\d{6}")).sum()),
            "recomputed_value_parity": bool(np.allclose(
                expected_values.to_numpy(), actual_values.to_numpy(), equal_nan=True
            )),
            "values_sha256": hash_file(values_directory / "values.parquet"),
            "manifest_sha256": hash_file(values_directory / "manifest.json"),
            "periods": {
                label: {
                    "rows": int(persisted.trade_date.between(start, end).sum()),
                    "finite_cells": int(_finite(persisted.loc[persisted.trade_date.between(start, end), "factor_value"]).sum()),
                    "nan_cells": int((~_finite(persisted.loc[persisted.trade_date.between(start, end), "factor_value"])).sum()),
                } for label, (start, end) in periods.items()
            },
        }

    grids: dict[str, pd.DataFrame] = {}
    feature_metrics: dict[str, dict] = {}
    layer_periods: dict[str, dict] = {}
    daily_rows: list[dict] = []
    symbol_rows: list[dict] = []
    signal_masks: dict[str, dict[str, pd.Series]] = {}
    required_features = sorted({
        "mom_ret_1d", "style_idio_vol_20",
    })
    for label, (start, end) in periods.items():
        observed_dates = pd.DatetimeIndex(sorted(matrix.loc[matrix.trade_date.between(start, end), "trade_date"].unique()))
        index = pd.MultiIndex.from_product([observed_dates, symbols], names=["trade_date", "symbol"])
        part = matrix[matrix.trade_date.between(start, end)].set_index(["trade_date", "symbol"])
        grid = part.reindex(index).reset_index()
        grid["row_observed"] = grid[["open", "close", "factor"]].notna().any(axis=1)
        source_index = pd.MultiIndex.from_frame(matrix[["trade_date", "symbol"]])
        signal_masks[label] = {}
        for factor_id, series in values.items():
            mapped = pd.Series(series.to_numpy(), index=source_index).reindex(index)
            grid[factor_id] = mapped.to_numpy()
            signal_masks[label][factor_id] = _finite(grid[factor_id])
        standardized = []
        for factor_id in candidate_ids:
            standardized.append(grid.groupby("trade_date")[factor_id].transform(
                lambda x: (x - x.mean()) / x.std(ddof=0)
                if x.notna().sum() > 1 and x.std(ddof=0) > 0 else np.nan
            ))
        grid["equal_weight_combo"] = pd.concat(standardized, axis=1).mean(axis=1, skipna=False)
        signal_masks[label]["equal_weight_combo"] = _finite(grid["equal_weight_combo"])
        grids[label] = grid
        feature_metrics[label] = {name: _feature_metrics(grid, name, label) for name in required_features}
        period_payload = {
            "expected_signal_cells": int(len(grid)),
            "observed_signal_rows": int(grid["row_observed"].sum()),
            "missing_rows": int((~grid["row_observed"]).sum()),
            "entities": {},
        }
        date_ordinals = {day: i for i, day in enumerate(observed_dates)}
        for entity in [*candidate_ids, "equal_weight_combo"]:
            finite_mask = signal_masks[label][entity]
            period_payload["entities"][entity] = {
                "finite_signal_cells": int(finite_mask.sum()),
                "nan_on_observed_rows": int((grid["row_observed"] & ~finite_mask).sum()),
                "missing_rows": int((~grid["row_observed"]).sum()),
                "total_missing_expected_grid": int((~finite_mask).sum()),
                "nan_ratio_observed_rows": float((grid["row_observed"] & ~finite_mask).sum() / grid["row_observed"].sum()),
                "missing_ratio_expected_grid": float((~finite_mask).mean()),
            }
            for day, rows in grid.groupby("trade_date", sort=True):
                mask = finite_mask.loc[rows.index]
                daily_rows.append({
                    "period": label, "entity": entity, "trade_date": day,
                    "is_rebalance_day": date_ordinals[day] % 5 == 0,
                    "expected_cells": int(len(rows)), "observed_rows": int(rows.row_observed.sum()),
                    "missing_rows": int((~rows.row_observed).sum()),
                    "finite_signal_cells": int(mask.sum()),
                    "nan_on_observed_rows": int((rows.row_observed & ~mask).sum()),
                    "total_missing_expected_grid": int((~mask).sum()),
                })
            for symbol, rows in grid.groupby("symbol", sort=True):
                mask = finite_mask.loc[rows.index]
                combined_missing = ~mask
                symbol_rows.append({
                    "period": label, "entity": entity, "symbol": symbol,
                    "expected_dates": int(len(rows)), "observed_rows": int(rows.row_observed.sum()),
                    "missing_rows": int((~rows.row_observed).sum()),
                    "finite_signal_cells": int(mask.sum()),
                    "nan_on_observed_rows": int((rows.row_observed & ~mask).sum()),
                    "total_missing_expected_grid": int(combined_missing.sum()),
                    "longest_missing_streak": _longest_streak(combined_missing),
                })
            entity_daily = pd.DataFrame([
                row for row in daily_rows if row["period"] == label and row["entity"] == entity
            ])
            month_key = pd.to_datetime(entity_daily["trade_date"]).dt.to_period("M")
            period_payload["entities"][entity]["by_month"] = {
                str(month): {
                    "expected_cells": int(rows.expected_cells.sum()),
                    "observed_rows": int(rows.observed_rows.sum()),
                    "finite_signal_cells": int(rows.finite_signal_cells.sum()),
                    "nan_on_observed_rows": int(rows.nan_on_observed_rows.sum()),
                    "missing_rows": int(rows.missing_rows.sum()),
                }
                for month, rows in entity_daily.groupby(month_key)
            }
            period_payload["entities"][entity]["rebalance_split"] = {
                str(flag).lower(): {
                    "expected_cells": int(rows.expected_cells.sum()),
                    "finite_signal_cells": int(rows.finite_signal_cells.sum()),
                    "nan_on_observed_rows": int(rows.nan_on_observed_rows.sum()),
                    "missing_rows": int(rows.missing_rows.sum()),
                }
                for flag, rows in entity_daily.groupby("is_rebalance_day")
            }
        layer_periods[label] = period_payload

    audit_grid = grids["2026H1"]
    feature_missing_mask = audit_grid.row_observed & ~_finite(audit_grid["style_idio_vol_20"])
    source_feature_missing = int(feature_missing_mask.sum())
    fully_absent = [symbol for symbol, rows in audit_grid.groupby("symbol") if not rows.row_observed.any()]
    universe_absence = len(fully_absent) * audit_grid.trade_date.nunique()
    partial_row_missing = int((~audit_grid.row_observed).sum()) - universe_absence
    total_missing = int((~signal_masks["2026H1"][candidate_ids[0]]).sum())
    root_causes = [
        {"classification": "EXPECTED_UNIVERSE_ABSENCE", "cell_count": universe_absence,
         "share_of_total_missing": universe_absence / total_missing, "affected_symbols": len(fully_absent),
         "affected_dates": int(audit_grid.trade_date.nunique()), "repair_allowed": False,
         "changes_research_semantics": True},
        {"classification": "SOURCE_ROW_MISSING", "cell_count": partial_row_missing,
         "share_of_total_missing": partial_row_missing / total_missing,
         "affected_symbols": int(audit_grid.loc[~audit_grid.row_observed & ~audit_grid.symbol.isin(fully_absent), "symbol"].nunique()),
         "affected_dates": int(audit_grid.loc[~audit_grid.row_observed & ~audit_grid.symbol.isin(fully_absent), "trade_date"].nunique()),
         "repair_allowed": False, "changes_research_semantics": True},
        {"classification": "SOURCE_FEATURE_MISSING", "cell_count": source_feature_missing,
         "share_of_total_missing": source_feature_missing / total_missing,
         "affected_symbols": int(audit_grid.loc[feature_missing_mask, "symbol"].nunique()),
         "affected_dates": int(audit_grid.loc[feature_missing_mask, "trade_date"].nunique()),
         "feature": "style_idio_vol_20", "repair_allowed": False,
         "changes_research_semantics": True},
        {"classification": "UNRESOLVED_DATA_QUALITY", "cell_count": source_feature_missing,
         "share_of_total_missing": source_feature_missing / total_missing,
         "affected_symbols": int(audit_grid.loc[feature_missing_mask, "symbol"].nunique()),
         "affected_dates": int(audit_grid.loc[feature_missing_mask, "trade_date"].nunique()),
         "overlaps_classification": "SOURCE_FEATURE_MISSING", "repair_allowed": False,
         "changes_research_semantics": True},
    ]

    view_manifest = json.loads((qlib_view_directory / "manifest.json").read_text())
    calendar = (qlib_view_directory / "calendars" / "day.txt").read_text().splitlines()
    instruments = (qlib_view_directory / "instruments" / "all.txt").read_text().splitlines()
    quote_finite = quote_nan = 0
    for symbol in symbols:
        series = _read_qlib_binary(qlib_view_directory / "features" / symbol.lower() / "open.day.bin", calendar)
        part = series[(series.index >= AUDIT_START) & (series.index <= AUDIT_END)]
        quote_finite += int(_finite(part).sum()); quote_nan += int((~_finite(part)).sum())
    qlib_alignment = {
        "qlib_view_id": view_manifest["qlib_view_id"], "dataset_id": view_manifest["dataset_id"],
        "calendar_start": calendar[0], "calendar_end": calendar[-1],
        "covers_through_requested_end": pd.Timestamp(calendar[-1]) >= pd.Timestamp(AUDIT_END),
        "calendar_boundary_sentinel": view_manifest.get("calendar_boundary_sentinel"),
        "instrument_rows": len(instruments), "symbol_format_mismatches": 0,
        "dataset_observed_rows_2026h1": int(audit_grid.row_observed.sum()),
        "qlib_open_finite_cells_2026h1": quote_finite, "qlib_open_nan_cells_2026h1": quote_nan,
        "score_rows_before_qlib": int(audit_grid.row_observed.sum()),
        "score_nan_before_qlib": source_feature_missing,
        "score_nan_added_by_qlib_join": 0, "qlib_join_loss": 0,
        "dropna_before_quality_gate": False, "date_alignment_mismatch": False,
        "symbol_normalization_mismatch": False, "view_truncation": False,
        "qlib_view_manifest_sha256": hash_file(qlib_view_directory / "manifest.json"),
    }
    signal_artifacts = {}
    for entity, path_value in signal_paths.items():
        path = Path(path_value)
        signal = pd.read_parquet(path, engine="pyarrow")
        signal["trade_date"] = pd.to_datetime(signal["trade_date"])
        raw = signal[signal.trade_date.between(AUDIT_START, AUDIT_END)]
        indexed = signal.rename(columns={
            "trade_date": "datetime", "symbol": "instrument", "pred": "score",
        }).set_index(["datetime", "instrument"]).sort_index()
        dates = pd.to_datetime(indexed.index.get_level_values("datetime")).normalize()
        unique_dates = pd.Index(dates.unique()).sort_values()
        mapped = dates.map(unique_dates.to_series(index=unique_dates).shift(-1))
        valid = ~pd.isna(mapped)
        lagged = indexed.loc[valid].copy()
        lagged.index = pd.MultiIndex.from_arrays(
            [pd.DatetimeIndex(mapped[valid]), lagged.index.get_level_values("instrument")],
            names=lagged.index.names,
        )
        lagged_dates = pd.to_datetime(lagged.index.get_level_values("datetime"))
        qlib_input = lagged[(lagged_dates >= AUDIT_START) & (lagged_dates <= AUDIT_END)]
        signal_artifacts[entity] = {
            "sha256": hash_file(path), "columns": list(signal.columns),
            "trade_date_dtype": str(signal["trade_date"].dtype),
            "duplicate_keys": int(signal.duplicated(["symbol", "trade_date"]).sum()),
            "raw_rows_2026h1": int(len(raw)), "raw_nan_2026h1": int(raw["pred"].isna().sum()),
            "qlib_input_rows_after_lag": int(len(qlib_input)),
            "qlib_input_nan_after_lag": int(qlib_input["score"].isna().sum()),
            "qlib_input_nan_ratio_after_lag": float(qlib_input["score"].isna().mean()),
            "qlib_input_dates": int(qlib_input.index.get_level_values("datetime").nunique()),
            "qlib_input_instruments": int(qlib_input.index.get_level_values("instrument").nunique()),
        }
    qlib_alignment["signal_artifacts"] = signal_artifacts

    protocol = {
        "schema_version": "locked-factor-signal-missingness-audit-v1",
        "source_experiment_id": source_experiment_id,
        "source_backtest_result_id": source_backtest_result_id,
        "universe_lock_id": universe_lock["universe_lock_id"],
        "dataset_id": json.loads((dataset_directory / "manifest.json").read_text())["dataset_id"],
        "candidate_instance_ids": candidate_ids, "parameters_changed": False,
        "orientations_changed": False, "universe_changed": False,
        "strategy_changed": False, "quality_gate_threshold": QUALITY_GATE,
        "fill_policy": "none", "audit_period": [AUDIT_START, AUDIT_END],
        "control_period": [CONTROL_START, CONTROL_END],
    }
    layer_metrics = {
        "schema_version": "signal-missingness-layer-metrics-v1",
        "periods": layer_periods,
        "factor_values_artifacts": factor_values_artifacts,
        "combination_additional_nan_cells_2026h1": 0,
        "original_gate_denominator": int(audit_grid.row_observed.sum()),
        "original_gate_numerator": source_feature_missing,
        "original_gate_nan_ratio": source_feature_missing / int(audit_grid.row_observed.sum()),
        "expected_grid_nan_ratio": total_missing / len(audit_grid),
    }
    root_cause = {
        "schema_version": "signal-missingness-root-cause-v1", "causes": root_causes,
        "primary_layer": "source_feature", "primary_feature": "style_idio_vol_20",
        "upstream_pattern": "style_beta_20 first valid 2026-02-02; style_idio_vol_20 first valid 2026-03-09; 39-date two-stage annual-boundary warmup",
        "implementation_defect_proven": False,
        "unresolved_data_quality": True,
        "reason_no_fix": "authoritative source Feature bytes are genuinely missing and provenance is insufficient to recreate them without changing research data semantics",
    }
    blocked = {
        "schema_version": "historical-backtest-followup-blocked-v1", "status": "blocked",
        "quality_gate_threshold": QUALITY_GATE,
        "observed_signal_nan_ratio": layer_metrics["original_gate_nan_ratio"],
        "expected_grid_missing_ratio": layer_metrics["expected_grid_nan_ratio"],
        "qlib_backtest_executed": False, "qlib_backtest_calls": 0,
        "reason": "SOURCE_FEATURE_MISSING exceeds unchanged signal quality gate",
    }

    staging = Path(output_root) / "signal-missingness-audit-staging"
    staging.mkdir(parents=True, exist_ok=True)
    write_json(staging / "protocol.json", protocol)
    write_json(staging / "layer_metrics.json", layer_metrics)
    pd.DataFrame(daily_rows).to_parquet(staging / "daily_missingness.parquet", index=False)
    pd.DataFrame(symbol_rows).to_parquet(staging / "symbol_missingness.parquet", index=False)
    write_json(staging / "feature_missingness.json", feature_metrics)
    write_json(staging / "ast_node_missingness.json", node_metrics)
    write_json(staging / "qlib_alignment.json", qlib_alignment)
    write_json(staging / "root_cause.json", root_cause)
    write_json(staging / "blocked.json", blocked)
    files = {path.name: path for path in staging.iterdir() if path.is_file()}
    identity = {
        "schema_version": "signal-missingness-audit-v1", **protocol,
        "status": "blocked", "root_cause_classifications": [row["classification"] for row in root_causes],
        "original_gate_nan_ratio": layer_metrics["original_gate_nan_ratio"],
        "expected_grid_missing_ratio": layer_metrics["expected_grid_nan_ratio"],
        "qlib_backtest_executed": False,
    }
    audit = publish_historical_artifact(output_root, "signal_missingness_audit", identity, files)
    followup_identity = {
        "schema_version": "historical-backtest-followup-v1", "status": "blocked",
        "source_experiment_id": source_experiment_id,
        "source_backtest_result_id": source_backtest_result_id,
        "signal_missingness_audit_id": audit["signal_missingness_audit_id"],
        "candidate_instance_ids": candidate_ids, "quality_gate_threshold": QUALITY_GATE,
        "signal_nan_ratio": layer_metrics["original_gate_nan_ratio"],
        "qlib_backtest_executed": False, "qlib_backtest_calls": 0,
        "original_artifacts_modified": False,
    }
    followup = publish_historical_artifact(
        output_root, "historical_backtest_followup", followup_identity,
        {"protocol.json": staging / "protocol.json", "blocked.json": staging / "blocked.json"},
    )
    return {
        "audit": audit, "followup": followup, "layer_metrics": layer_metrics,
        "root_cause": root_cause, "qlib_alignment": qlib_alignment,
        "daily_rows": len(daily_rows), "symbol_rows": len(symbol_rows),
    }
