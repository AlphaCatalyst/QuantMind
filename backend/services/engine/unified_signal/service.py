from __future__ import annotations

import json
import math
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .errors import LegacyMarketDataAuthorityForbidden, UnifiedSignalError
from .models import COMBINATIONS, EVIDENCE_CLASSES, TRANSFORMS, FactorSignalInput, UnifiedSignalSpec

SIGNAL_SCHEMA_VERSION = "1.0.0"
SIGNAL_ENGINE_VERSION = "1.0.0"


def _strict(value: Mapping[str, Any], allowed: set[str], required: set[str], where: str) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown or missing:
        raise UnifiedSignalError(f"{where} fields invalid: unknown={sorted(unknown)} missing={sorted(missing)}")


def parse_spec(value: Mapping[str, Any]) -> UnifiedSignalSpec:
    fields = {
        "schema_version", "name", "description", "inputs", "transformation", "combination",
        "weights", "missing_policy", "winsor_lower", "winsor_upper", "universe_id", "dataset_id",
        "start_date", "end_date", "data_authority", "predictive_claim", "eligible_for_production",
    }
    _strict(value, fields, fields - {"winsor_lower", "winsor_upper"}, "UnifiedSignalSpec")
    input_fields = {
        "template_id", "factor_instance_id", "factor_values_id", "source_artifact_kind",
        "source_artifact_id", "source_relative_path", "orientation", "dataset_id", "universe_id",
        "values_are_oriented", "evidence_class", "canonicality",
    }
    inputs = []
    for raw in value["inputs"]:
        _strict(raw, input_fields, input_fields, "FactorSignalInput")
        item = FactorSignalInput(**raw)
        if item.orientation not in {-1, 1} or item.evidence_class not in EVIDENCE_CLASSES:
            raise UnifiedSignalError("factor orientation or evidence class is invalid")
        if item.dataset_id != value["dataset_id"] or item.universe_id != value["universe_id"]:
            raise UnifiedSignalError("all factor inputs must bind the same Dataset and Universe")
        inputs.append(item)
    if not inputs:
        raise UnifiedSignalError("at least one factor input is required")
    transformation = str(value["transformation"])
    combination = str(value["combination"])
    if transformation not in TRANSFORMS or combination not in COMBINATIONS:
        raise UnifiedSignalError("unsupported signal transformation or combination")
    if value["missing_policy"] != "require_all_factors":
        raise UnifiedSignalError("v1 only supports require_all_factors")
    if value["data_authority"] != "tushare-pro-v1":
        raise LegacyMarketDataAuthorityForbidden("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    if bool(value["predictive_claim"]) or bool(value["eligible_for_production"]):
        raise UnifiedSignalError("research-diagnostic signal cannot claim prediction or production eligibility")
    weights = tuple(float(x) for x in value["weights"])
    if combination == "single_factor" and len(inputs) != 1:
        raise UnifiedSignalError("single_factor requires exactly one input")
    if combination == "equal_weight":
        weights = tuple(1.0 / len(inputs) for _ in inputs)
    if len(weights) != len(inputs) or any(x < 0 for x in weights) or not math.isclose(sum(weights), 1.0, abs_tol=1e-12):
        raise UnifiedSignalError("weights must be non-negative, align with inputs, and sum to one")
    lo, hi = value.get("winsor_lower"), value.get("winsor_upper")
    if transformation == "winsorized_cs_zscore" and not (
        isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and 0 <= lo < hi <= 1
    ):
        raise UnifiedSignalError("winsorized_cs_zscore requires explicit quantile bounds")
    if transformation != "winsorized_cs_zscore" and (lo is not None or hi is not None):
        raise UnifiedSignalError("winsor bounds are only valid for winsorized_cs_zscore")
    return UnifiedSignalSpec(
        str(value["schema_version"]), str(value["name"]), str(value["description"]), tuple(inputs),
        transformation, combination, weights, str(value["missing_policy"]), lo, hi,
        str(value["universe_id"]), str(value["dataset_id"]), str(value["start_date"]),
        str(value["end_date"]), str(value["data_authority"]), bool(value["predictive_claim"]),
        bool(value["eligible_for_production"]),
    )


def _transform(frame: pd.DataFrame, spec: UnifiedSignalSpec, column: str) -> pd.Series:
    oriented = pd.to_numeric(frame[column], errors="coerce")
    grouped = oriented.groupby(frame["trade_date"])
    if spec.transformation == "raw":
        return oriented
    if spec.transformation == "cs_rank":
        return grouped.rank(method="average", pct=True)
    if spec.transformation == "winsorized_cs_zscore":
        oriented = grouped.transform(lambda x: x.clip(x.quantile(spec.winsor_lower), x.quantile(spec.winsor_upper)))
        grouped = oriented.groupby(frame["trade_date"])
    return grouped.transform(lambda x: (x - x.mean()) / x.std(ddof=0) if x.notna().sum() > 1 and x.std(ddof=0) > 0 else np.nan)


def signal_spec_id(spec: UnifiedSignalSpec) -> str:
    return "uss_" + hash_payload({**spec.to_dict(), "engine_version": SIGNAL_ENGINE_VERSION})


def build_unified_signal(spec: UnifiedSignalSpec, source_roots: Mapping[str, Path], output_root: Path) -> dict[str, Any]:
    frames: list[pd.DataFrame] = []
    for ordinal, item in enumerate(spec.inputs):
        root = Path(source_roots[item.source_artifact_id])
        source = root / item.source_relative_path
        frame = pd.read_parquet(source, engine="pyarrow")
        value_columns = [name for name in frame if name not in {"symbol", "trade_date"}]
        if len(value_columns) != 1 or frame.duplicated(["symbol", "trade_date"]).any():
            raise UnifiedSignalError("factor values require one value column and unique keys")
        values = pd.to_numeric(frame[value_columns[0]], errors="coerce")
        if not item.values_are_oriented:
            values = values * item.orientation
        if np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).any():
            raise UnifiedSignalError("factor values contain Infinity")
        part = frame[["symbol", "trade_date"]].copy()
        part[f"factor_{ordinal}"] = values
        frames.append(part)
    merged = frames[0]
    for part in frames[1:]:
        merged = merged.merge(part, on=["symbol", "trade_date"], how="outer", validate="one_to_one")
    merged["trade_date"] = pd.to_datetime(merged["trade_date"])
    merged = merged[merged["trade_date"].between(spec.start_date, spec.end_date)].copy()
    columns = [f"factor_{i}" for i in range(len(frames))]
    for column in columns:
        merged[column] = _transform(merged, spec, column)
    if spec.combination == "equal_weight":
        # This is the frozen v1 arithmetic contract and preserves parity with the
        # historical research implementation's equal-weight row mean.
        merged["score"] = merged[columns].mean(axis=1, skipna=False)
    else:
        merged["score"] = sum(merged[column] * weight for column, weight in zip(columns, spec.weights))
    merged.loc[merged[columns].isna().any(axis=1), "score"] = np.nan
    output = merged[["symbol", "trade_date", "score"]].sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    if output.duplicated(["symbol", "trade_date"]).any() or np.isinf(output["score"].to_numpy()).any():
        raise UnifiedSignalError("unified signal keys or finite-value contract failed")
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".signal-{uuid.uuid4().hex}"
    temporary.mkdir()
    parquet = temporary / "signal.parquet"
    output.to_parquet(parquet, index=False, compression="zstd", engine="pyarrow")
    spec_payload = spec.to_dict()
    spec_id = signal_spec_id(spec)
    expected = int(len(output))
    finite = int(output["score"].notna().sum())
    daily = output.groupby("trade_date")["score"].count()
    quality = {
        "expected_cells": expected, "finite_cells": finite, "nan_cells": expected - finite,
        "nan_ratio": (expected - finite) / expected if expected else None,
        "daily_finite_count": {str(k.date()): int(v) for k, v in daily.items()},
        "minimum_daily_finite_count": int(daily.min()) if len(daily) else 0,
    }
    write_json(temporary / "spec.json", {**spec_payload, "unified_signal_spec_id": spec_id})
    write_json(temporary / "quality.json", quality)
    files = {name: hash_file(temporary / name) for name in ("spec.json", "quality.json", "signal.parquet")}
    identity = {
        "unified_signal_spec_id": spec_id, "spec": spec_payload,
        "output_parquet_hash": files["signal.parquet"], "engine_version": SIGNAL_ENGINE_VERSION,
    }
    artifact_id = "usa_" + hash_payload(identity)
    manifest = {
        "schema_version": "unified-signal-artifact-v1", "artifact_kind": "unified_signal",
        "unified_signal_artifact_id": artifact_id, "identity": identity, "file_hashes": files,
    }
    write_json(temporary / "manifest.json", manifest)
    target = output_root / artifact_id
    if target.exists():
        shutil.rmtree(temporary)
        validate_signal_artifact(target, artifact_id)
        return {**json.loads((target / "manifest.json").read_text()), "path": str(target), "exact_existing": True}
    os.replace(temporary, target)
    validate_signal_artifact(target, artifact_id)
    return {**manifest, "path": str(target), "exact_existing": False}


def validate_signal_artifact(root: Path, artifact_id: str) -> dict[str, Any]:
    from backend.services.engine.strategy_layer.artifact import validate_strategy_domain_artifact
    return validate_strategy_domain_artifact(Path(root), artifact_id, "unified_signal")
