import json
import os
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from backend.services.engine.market_data.feature_snapshot import LegacyFeatureSnapshotService
from backend.services.engine.market_data.legacy_models import (
    ColumnRole, LegacyFeatureBatch, LegacyFeatureInventory, LegacyFeatureRequest, LegacyFeatureSchema,
)
from backend.services.engine.market_data.storage import canonical_json_bytes, sha256_bytes, sha256_file

from .canonical import hash_payload
from .errors import ValidationArtifactError
from .labels import build_production_labels, label_contract_id, label_contract_payload, production_label_contract


DATASET_SCHEMA_VERSION = "factor-validation-dataset-v1"
LABEL_SNAPSHOT_SCHEMA_VERSION = "factor-label-snapshot-v1"
REQUIRED_FEATURES = ("mom_ret_1d", "liq_volume_ratio_5", "style_beta_20", "style_idio_vol_20")
LABEL_INPUTS = ("open", "close", "factor")
YEARS = tuple(range(2021, 2027))
SPLIT_WINDOWS = {
    "train": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2024-12-31"),
    "quarantined_development": ("2025-01-01", "2025-12-31"),
    "frozen_test": ("2026-01-01", "2026-12-31"),
}


def _utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path, payload):
    path.write_bytes(canonical_json_bytes(payload) + b"\n")


def _source_files(source_root):
    root = Path(source_root).resolve()
    files = []
    for year in YEARS:
        path = root / f"model_features_{year}.parquet"
        if not path.is_file():
            raise ValidationArtifactError(f"missing annual source file for {year}")
        digest = sha256_file(path)
        files.append({"file_relative_path": path.name, "year": year, "size_bytes": path.stat().st_size,
                      "sha256": digest, "hash_evidence": "computed_from_current_bytes"})
    return files


def _read_source(source_root, symbol_limit):
    root = Path(source_root).resolve()
    columns = ["symbol", "trade_date", *LABEL_INPUTS, *REQUIRED_FEATURES]
    symbol_sets = []
    for year in YEARS:
        symbols = pq.read_table(root / f"model_features_{year}.parquet", columns=["symbol"]).column(0).to_pylist()
        symbol_sets.append(set(str(item) for item in symbols if item is not None))
    common = set.intersection(*symbol_sets)
    eligible = sorted(item for item in common if not item.startswith(("BJ", "SH9", "SZ2")))
    selected = tuple(eligible[:symbol_limit])
    if len(selected) < symbol_limit:
        raise ValidationArtifactError("insufficient common symbols for validation universe")
    frames = []
    for year in YEARS:
        table = pq.read_table(root / f"model_features_{year}.parquet", columns=columns,
                              filters=[("symbol", "in", list(selected))])
        frames.append(table.to_pandas())
    frame = pd.concat(frames, ignore_index=True)
    frame["symbol"] = frame["symbol"].astype(str)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    if frame["trade_date"].isna().any() or frame.duplicated(["symbol", "trade_date"]).any():
        raise ValidationArtifactError("source contains invalid validation keys")
    frame = frame.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
    return frame, selected


def _split_labels(labels):
    split_frames = {}
    split_records = {}
    for name, (start, end) in SPLIT_WINDOWS.items():
        raw = labels[(labels.trade_date >= start) & (labels.trade_date <= end)].copy()
        observed_dates = sorted(raw.trade_date.drop_duplicates())
        if len(observed_dates) < 2:
            raise ValidationArtifactError(f"split {name} has insufficient dates")
        embargo_dates = observed_dates[-1:]
        complete = raw[~raw.trade_date.isin(embargo_dates) & raw["model_label"].notna()].copy()
        split_frames[name] = complete
        split_records[name] = {
            "declared_start": start, "declared_end": end,
            "effective_start": complete.trade_date.min().date().isoformat(),
            "effective_end": complete.trade_date.max().date().isoformat(),
            "date_count": int(complete.trade_date.nunique()), "row_count": int(len(complete)),
            "purged_label_incomplete_dates": [item.date().isoformat() for item in embargo_dates],
            "embargo_trading_dates": 1,
        }
    names = list(split_frames)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            if set(split_frames[left].trade_date) & set(split_frames[right].trade_date):
                raise ValidationArtifactError("validation splits overlap")
    return split_frames, split_records


class _FrameProvider:
    def __init__(self, frame, selected, inventory):
        self.frame, self.selected, self.inventory = frame, selected, inventory

    def read(self, request):
        return LegacyFeatureBatch("factor-validation-feature-adapter", "1.0.0", request,
                                  self.frame[["symbol", "trade_date", *REQUIRED_FEATURES]].copy(),
                                  self.inventory, self.selected,
                                  "lexicographic-common-2021-2026-symbols-v1")


def build_validation_dataset(source_root, output_root, snapshot_root, *, symbol_limit=300):
    output_root, snapshot_root = Path(output_root), Path(snapshot_root)
    source_files = _source_files(source_root)
    frame, selected = _read_source(source_root, symbol_limit)
    contract = production_label_contract(1)
    labels = build_production_labels(frame, contract)
    split_frames, split_records = _split_labels(labels)

    schema = LegacyFeatureSchema(
        ("symbol", "trade_date", *REQUIRED_FEATURES),
        tuple((name, str(frame[name].dtype)) for name in ("symbol", "trade_date", *REQUIRED_FEATURES)),
        (("symbol", ColumnRole.KEY), ("trade_date", ColumnRole.KEY),
         *((name, ColumnRole.FEATURE) for name in REQUIRED_FEATURES)),
        REQUIRED_FEATURES, (), (),
    )
    inventory = LegacyFeatureInventory("quantmind-production-feature-snapshots-v1",
                                       "factor-validation-bounded-reader-v1", "mixed-annual-schema-projected-v1",
                                       tuple(source_files), schema)
    request = LegacyFeatureRequest("quantmind-production-feature-snapshots-v1", YEARS,
                                   date(2021, 1, 1), frame.trade_date.max().date(),
                                   symbols=selected, columns=REQUIRED_FEATURES)
    snapshot_result = LegacyFeatureSnapshotService(snapshot_root).create(_FrameProvider(frame, selected, inventory), request)

    prepared = output_root / f".validation-content-{uuid.uuid4().hex}"
    prepared.mkdir(parents=True, exist_ok=False)
    feature_prepared = prepared / "features.parquet"
    frame[["symbol", "trade_date", *REQUIRED_FEATURES]].to_parquet(feature_prepared, index=False, engine="pyarrow")
    development = pd.concat([split_frames["train"], split_frames["validation"], split_frames["quarantined_development"]], ignore_index=True)
    public = pd.concat([split_frames["train"], split_frames["validation"]], ignore_index=True)
    public.to_parquet(prepared / "train_validation_labels.parquet", index=False, engine="pyarrow")
    development.to_parquet(prepared / "development_labels.parquet", index=False, engine="pyarrow")
    split_frames["frozen_test"].to_parquet(prepared / "frozen_labels.parquet", index=False, engine="pyarrow")
    output_content_hashes = {path.name: sha256_file(path) for path in sorted(prepared.glob("*.parquet"))}

    identity = {
        "validation_dataset_schema_version": DATASET_SCHEMA_VERSION,
        "source_id": inventory.source_id, "source_schema_version": inventory.source_schema_version,
        "source_files": source_files, "required_features": list(REQUIRED_FEATURES),
        "label_input_columns": list(LABEL_INPUTS), "label_contract": label_contract_payload(contract),
        "label_contract_id": label_contract_id(contract), "feature_snapshot_id": snapshot_result["snapshot_id"],
        "selected_symbols": list(selected), "split_windows": SPLIT_WINDOWS, "splits": split_records,
        "quarantined_periods": [{"start": "2025-01-01", "end": "2025-12-31", "reason": "used in DSL and optimization development"}],
        "max_factor_lookback": 20, "label_horizon": 1, "embargo_trading_dates": 1,
        "output_content_hashes": output_content_hashes,
    }
    dataset_id = "vd_" + hash_payload(identity)
    target = output_root / "datasets" / dataset_id
    if target.exists():
        try:
            return validate_validation_dataset(output_root, dataset_id, expected_identity=identity)
        finally:
            shutil.rmtree(prepared)
    staging = output_root / "datasets" / f".{dataset_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        feature_file = staging / "features.parquet"
        os.replace(feature_prepared, feature_file)
        label_root = staging / "label_snapshot"; label_root.mkdir()
        for name in ("train_validation_labels.parquet", "development_labels.parquet", "frozen_labels.parquet"):
            os.replace(prepared / name, label_root / name)
        label_identity = {"schema_version": LABEL_SNAPSHOT_SCHEMA_VERSION, "validation_dataset_id": dataset_id,
                          "label_contract_id": identity["label_contract_id"], "splits": split_records,
                          "label_content_hashes": {name: output_content_hashes[name] for name in output_content_hashes if "labels" in name},
                          "access_policy": {"optimizer": "denied", "validation": ["train", "validation"],
                                            "frozen_evaluator": ["frozen_test"]}}
        label_snapshot_id = "ls_" + hash_payload(label_identity)
        _write_json(label_root / "manifest.json", {**label_identity, "label_snapshot_id": label_snapshot_id})
        _write_json(staging / "splits.json", split_records)
        _write_json(staging / "schema.json", {"schema_version": DATASET_SCHEMA_VERSION,
                                              "features": ["symbol", "trade_date", *REQUIRED_FEATURES],
                                              "labels": ["raw_label", "model_label", "sample_weight"],
                                              "validation_label": "model_label"})
        files = [feature_file, *sorted(label_root.iterdir()), staging / "splits.json", staging / "schema.json"]
        hashes = {str(path.relative_to(staging)): sha256_file(path) for path in files}
        manifest = {**identity, "validation_dataset_id": dataset_id, "label_snapshot_id": label_snapshot_id,
                    "created_at": _utcnow(), "date_range": {"start": frame.trade_date.min().date().isoformat(),
                    "end": frame.trade_date.max().date().isoformat()}, "row_count": len(frame),
                    "symbol_count": len(selected), "file_hashes": hashes,
                    "quality_summary": {"duplicate_keys": 0, "split_overlap": 0, "frozen_access_default": "denied"}}
        _write_json(staging / "manifest.json", manifest)
        target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
        if prepared.exists(): shutil.rmtree(prepared)
    return validate_validation_dataset(output_root, dataset_id, expected_identity=identity)


def validate_validation_dataset(output_root, dataset_id, expected_identity=None, source_root=None):
    root = Path(output_root) / "datasets" / dataset_id
    try: manifest = json.loads((root / "manifest.json").read_text())
    except Exception as exc: raise ValidationArtifactError("validation dataset manifest unreadable") from exc
    identity = {key: manifest[key] for key in (
        "validation_dataset_schema_version", "source_id", "source_schema_version", "source_files", "required_features",
        "label_input_columns", "label_contract", "label_contract_id", "feature_snapshot_id", "selected_symbols",
        "split_windows", "splits", "quarantined_periods", "max_factor_lookback", "label_horizon", "embargo_trading_dates",
        "output_content_hashes")}
    if dataset_id != "vd_" + hash_payload(identity) or manifest.get("validation_dataset_id") != dataset_id:
        raise ValidationArtifactError("validation dataset identity mismatch")
    if expected_identity is not None and hash_payload(identity) != hash_payload(expected_identity):
        raise ValidationArtifactError("validation dataset immutable identity conflict")
    for relative, expected in manifest.get("file_hashes", {}).items():
        if not (root / relative).is_file() or sha256_file(root / relative) != expected:
            raise ValidationArtifactError("validation dataset file hash mismatch")
    if source_root is not None:
        current = _source_files(source_root)
        if current != manifest["source_files"]:
            raise ValidationArtifactError("validation source bytes drifted from immutable inventory")
    return {"status": "existing" if expected_identity is not None else "valid", "validation_dataset_id": dataset_id,
            "path": str(root), "manifest": manifest}


def load_validation_labels(output_root, dataset_id):
    root = Path(output_root) / "datasets" / dataset_id
    validate_validation_dataset(output_root, dataset_id)
    return pd.read_parquet(root / "label_snapshot" / "train_validation_labels.parquet", engine="pyarrow")


def load_development_labels(output_root, dataset_id):
    root = Path(output_root) / "datasets" / dataset_id
    validate_validation_dataset(output_root, dataset_id)
    return pd.read_parquet(root / "label_snapshot" / "development_labels.parquet", engine="pyarrow")
