from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from backend.services.engine.factor_validation.labels import (
    build_production_labels, label_contract_id, production_label_contract,
)
from backend.services.engine.market_data.feature_snapshot import LegacyFeatureSnapshotService
from backend.services.engine.market_data.legacy_models import (
    ColumnRole, LegacyFeatureBatch, LegacyFeatureInventory, LegacyFeatureRequest,
    LegacyFeatureSchema,
)
from backend.services.engine.market_data.storage import sha256_file

from .artifact import publish_historical_artifact
from .universe import select_fixed_universe


YEARS = tuple(range(2019, 2027))
FEATURES = (
    "mom_ret_1d", "liq_volume_ratio_5", "style_beta_20", "style_idio_vol_20",
    "style_ln_mv_float", "liq_amount",
)
SOURCE_COLUMNS = (
    "symbol", "trade_date", "open", "high", "low", "close", "volume", "factor",
    *FEATURES, "ind_code_l1",
)
END_DATE = pd.Timestamp("2026-06-23")


class _FrameProvider:
    def __init__(self, frame, symbols, inventory):
        self.frame, self.symbols, self.inventory = frame, symbols, inventory

    def read(self, request):
        return LegacyFeatureBatch(
            "fixed-universe-historical-adapter", "1.0.0", request,
            self.frame[["symbol", "trade_date", *FEATURES]].copy(), self.inventory,
            self.symbols, "fixed-universe-lock-explicit-symbols-v1",
        )


def _source_inventory(source_root: Path) -> list[dict]:
    rows = []
    for year in YEARS:
        path = source_root / f"model_features_{year}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"missing production feature source for {year}")
        metadata = pq.ParquetFile(path).metadata
        rows.append({"year": year, "file_relative_path": path.name,
                     "size_bytes": path.stat().st_size, "row_count": metadata.num_rows,
                     "sha256": sha256_file(path), "hash_evidence": "computed_from_current_bytes"})
    return rows


def _read_year(source_root: Path, year: int, symbols: tuple[str, ...] | None = None) -> pd.DataFrame:
    filters = [("symbol", "in", list(symbols))] if symbols else None
    table = pq.read_table(source_root / f"model_features_{year}.parquet",
                          columns=list(SOURCE_COLUMNS), filters=filters)
    frame = table.to_pandas()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="raise")
    return frame


def build_historical_dataset(source_root: Path, output_root: Path, snapshot_root: Path) -> dict:
    source_root, output_root, snapshot_root = map(Path, (source_root, output_root, snapshot_root))
    inventory_rows = _source_inventory(source_root)
    universe_source = _read_year(source_root, 2019)
    universe = select_fixed_universe(universe_source)
    symbols = tuple(universe["symbols"])
    frames = [_read_year(source_root, year, symbols) for year in YEARS]
    frame = pd.concat(frames, ignore_index=True).sort_values(["trade_date", "symbol"], kind="mergesort")
    if frame.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("historical source has duplicate symbol/date keys")
    label_contract = production_label_contract(1)
    labels = build_production_labels(frame[["symbol", "trade_date", "open", "close", "factor"]], label_contract)
    feature_frame = frame[frame.trade_date <= END_DATE].copy()
    labels = labels[labels.trade_date <= END_DATE]
    combined = feature_frame.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")

    annual_audit = []
    for year in YEARS:
        part = combined[combined.trade_date.dt.year == year]
        counts = part.groupby("symbol").size()
        annual_audit.append({
            "year": year, "source_sha256": inventory_rows[year - YEARS[0]]["sha256"],
            "date_start": part.trade_date.min().date().isoformat(),
            "date_end": part.trade_date.max().date().isoformat(),
            "row_count": int(len(part)), "observed_symbol_count": int(part.symbol.nunique()),
            "minimum_rows_per_locked_symbol": int(counts.reindex(symbols, fill_value=0).min()),
            "maximum_rows_per_locked_symbol": int(counts.reindex(symbols, fill_value=0).max()),
            "duplicate_keys": int(part.duplicated(["symbol", "trade_date"]).sum()),
            "missing_rates": {name: float(part[name].isna().mean()) for name in SOURCE_COLUMNS[2:]},
            "dtypes": {name: str(part[name].dtype) for name in SOURCE_COLUMNS},
        })

    schema = LegacyFeatureSchema(
        ("symbol", "trade_date", *FEATURES),
        tuple((name, str(feature_frame[name].dtype)) for name in ("symbol", "trade_date", *FEATURES)),
        (("symbol", ColumnRole.KEY), ("trade_date", ColumnRole.KEY),
         *((name, ColumnRole.FEATURE) for name in FEATURES)), FEATURES, (), (),
    )
    inventory = LegacyFeatureInventory(
        "quantmind-production-feature-snapshots-v1", "fixed-universe-bounded-reader-v1",
        "mixed-annual-schema-projected-v1", tuple(inventory_rows), schema,
    )
    request = LegacyFeatureRequest(
        inventory.source_id, YEARS, date(2019, 1, 2), END_DATE.date(), symbols=symbols,
        columns=FEATURES,
    )
    snapshot = LegacyFeatureSnapshotService(snapshot_root).create(
        _FrameProvider(feature_frame, symbols, inventory), request,
    )
    staging = output_root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    parquet_path = staging / "historical_matrix.parquet"
    combined.to_parquet(parquet_path, index=False, engine="pyarrow", compression="zstd")
    audit_path = staging / "annual_audit.json"
    audit_path.write_text(json.dumps(annual_audit, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")) + "\n", encoding="utf-8")
    identity = {
        "schema_version": "fixed-universe-historical-dataset-v1",
        "universe_lock_id": universe["universe_lock_id"], "symbols": list(symbols),
        "feature_snapshot_id": snapshot["snapshot_id"], "source_files": inventory_rows,
        "label_contract_id": label_contract_id(label_contract),
        "label_formula": "adjusted_close[T+1] / adjusted_open[T+1] - 1",
        "label_columns": ["raw_label", "model_label", "sample_weight"],
        "feature_columns": list(FEATURES), "date_range": ["2019-01-02", "2026-06-23"],
        "round_splits": {"1": ["2019-01-02", "2020-12-31", "2021"],
                         "2": ["2019-01-02", "2021-12-31", "2022"],
                         "3": ["2019-01-02", "2022-12-30", "2023"],
                         "4": ["2019-01-02", "2023-12-29", "2024"]},
        "holdouts": [["2025-01-02", "2025-12-30"], ["2026-01-05", "2026-06-23"]],
        "missing_symbol_policy": "preserve_without_replacement",
        "quality": {"duplicate_keys": 0, "annual_audit": annual_audit},
    }
    result = publish_historical_artifact(
        output_root, "fixed_universe_historical_dataset", identity,
        {"historical_matrix.parquet": parquet_path, "annual_audit.json": audit_path},
    )
    return {**result, "universe": universe, "snapshot": snapshot, "annual_audit": annual_audit}
