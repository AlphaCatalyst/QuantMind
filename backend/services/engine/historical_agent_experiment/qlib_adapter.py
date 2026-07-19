from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from .canonical import hash_file, hash_payload, write_json


FIELDS = ("open", "high", "low", "close", "volume", "amount", "factor", "adjclose", "vwap", "change")


def build_qlib_consumer_view(dataset_directory: Path, output_root: Path) -> dict:
    dataset_directory, output_root = Path(dataset_directory), Path(output_root)
    dataset_manifest = json.loads((dataset_directory / "manifest.json").read_text())
    frame = pd.read_parquet(dataset_directory / "historical_matrix.parquet", engine="pyarrow")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    required = {"symbol", "trade_date", "open", "high", "low", "close", "volume", "liq_amount", "factor"}
    if required - set(frame.columns):
        raise ValueError("Dataset Snapshot lacks formal Qlib exchange fields")
    observed_calendar = tuple(day.strftime("%Y-%m-%d") for day in sorted(frame.trade_date.drop_duplicates()))
    # QlibBacktestService deliberately backs off one session at the physical calendar
    # boundary.  The next production source session is therefore represented only as
    # an empty boundary sentinel; no feature/label/quote from it enters the experiment.
    calendar = (*observed_calendar, "2026-06-24")
    symbols = tuple(dataset_manifest["symbols"])
    identity = {
        "schema_version": "fixed-universe-qlib-consumer-view-v1",
        "dataset_id": dataset_manifest["dataset_id"], "universe_lock_id": dataset_manifest["universe_lock_id"],
        "symbols": list(symbols), "calendar_start": calendar[0], "calendar_end": calendar[-1],
        "calendar_count": len(calendar), "fields": list(FIELDS), "dtype": "float32",
        "calendar_boundary_sentinel": "2026-06-24 (no experiment rows or quotes)",
        "missing_quote_policy": "NaN; no forward fill; preserve suspension and delisting",
        "volume_transform": "raw shares / 100", "amount_transform": "raw currency / 1000",
        "adjustment": "adjclose=close*factor; raw OHLC retained; factor retained",
        "authority": "Dataset Snapshot; Qlib is a consumer view",
    }
    view_id = "qcv_" + hash_payload(identity)
    target = output_root / view_id
    if target.exists():
        return validate_qlib_consumer_view(target, view_id)
    staging = output_root / f".{view_id}.staging-{uuid.uuid4().hex}"
    try:
        (staging / "calendars").mkdir(parents=True)
        (staging / "instruments").mkdir()
        (staging / "features").mkdir()
        (staging / "calendars" / "day.txt").write_text("\n".join(calendar) + "\n")
        cal_index = {value: index for index, value in enumerate(calendar)}
        instruments = []
        for symbol in symbols:
            observed = frame[frame.symbol == symbol].copy().sort_values("trade_date")
            if observed.empty:
                continue
            dates = observed.trade_date.dt.strftime("%Y-%m-%d")
            start_date, end_date = dates.iloc[0], dates.iloc[-1]
            instruments.append(f"{symbol}\t{start_date}\t{end_date}")
            start_index = cal_index[start_date]
            local_calendar = calendar[start_index:]
            observed = observed.assign(_date=dates).set_index("_date").reindex(local_calendar)
            adjusted = pd.to_numeric(observed["close"], errors="coerce") * pd.to_numeric(observed["factor"], errors="coerce")
            payloads = {
                "open": observed["open"], "high": observed["high"], "low": observed["low"],
                "close": observed["close"], "volume": pd.to_numeric(observed["volume"], errors="coerce") / 100.0,
                "amount": pd.to_numeric(observed["liq_amount"], errors="coerce") / 1000.0,
                "factor": observed["factor"], "adjclose": adjusted,
                "vwap": pd.to_numeric(observed["liq_amount"], errors="coerce") / pd.to_numeric(observed["volume"], errors="coerce"),
                "change": adjusted.pct_change(fill_method=None),
            }
            directory = staging / "features" / symbol.lower(); directory.mkdir()
            for field, values in payloads.items():
                binary = np.concatenate(([np.float32(start_index)], np.asarray(values, dtype=np.float32)))
                (directory / f"{field}.day.bin").write_bytes(binary.tobytes())
        (staging / "instruments" / "all.txt").write_text("\n".join(instruments) + "\n")
        file_hashes = {str(path.relative_to(staging)): hash_file(path)
                       for path in sorted(staging.rglob("*")) if path.is_file()}
        manifest = {**identity, "qlib_view_id": view_id, "instrument_count": len(instruments),
                    "file_hashes": file_hashes}
        write_json(staging / "manifest.json", manifest)
        target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return validate_qlib_consumer_view(target, view_id)


def validate_qlib_consumer_view(root: Path, view_id: str) -> dict:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    stable = {key: value for key, value in manifest.items() if key not in {"qlib_view_id", "instrument_count", "file_hashes"}}
    if manifest.get("qlib_view_id") != view_id or view_id != "qcv_" + hash_payload(stable):
        raise ValueError("Qlib consumer view identity mismatch")
    if manifest.get("instrument_count") != 100 or len(manifest.get("symbols", [])) != 100:
        raise ValueError("Qlib consumer view is not the locked 100 universe")
    for relative, digest in manifest["file_hashes"].items():
        if not (root / relative).is_file() or hash_file(root / relative) != digest:
            raise ValueError("Qlib consumer view file hash mismatch")
    return {"status": "valid", "qlib_view_id": view_id, "path": str(root), "manifest": manifest}
