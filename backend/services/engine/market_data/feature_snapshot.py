from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .errors import (
    DataQualityError,
    LegacyFeatureAccessError,
    SnapshotConflictError,
    SnapshotValidationError,
)
from .feature_quality import evaluate_feature_matrix
from .legacy_models import FeatureAccessPolicy, LegacyFeatureRequest, LegacyFeatureSourceBinding
from .storage import canonical_json_bytes, sha256_bytes, sha256_file, write_json
from .symbol import normalize_symbol


LEGACY_DATASET_KIND = "legacy_feature_matrix_v1"
LEGACY_NORMALIZATION_VERSION = "legacy-feature-pass-through-v1"
SNAPSHOT_SCHEMA_VERSION = "1.0.0"


def _arrow_schema_payload(schema: pa.Schema) -> list[dict[str, Any]]:
    return [
        {"name": field.name, "type": str(field.type), "nullable": field.nullable}
        for field in schema
    ]


class LegacyFeatureSnapshotService:
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)

    def create(self, provider: Any, request: LegacyFeatureRequest) -> dict[str, Any]:
        batch = provider.read(request)
        quality = evaluate_feature_matrix(batch)
        if quality["summary"]["error"]:
            raise DataQualityError("legacy feature quality gate failed")
        staging = self.output_root / f".snapshot-staging-{uuid.uuid4().hex}"
        try:
            partition_dir = staging / "partitions" / "feature_matrix"
            partition_dir.mkdir(parents=True)
            parquet_path = partition_dir / "part-00000.parquet"
            table = pa.Table.from_pandas(batch.frame, preserve_index=False)
            pq.write_table(table, parquet_path, compression="zstd", version="2.6")
            parquet_hash = sha256_file(parquet_path)
            output_schema = _arrow_schema_payload(table.schema)
            inventory = batch.inventory.to_dict()
            access_policy = FeatureAccessPolicy.from_schema(batch.inventory.schema).to_dict()
            identity_payload = {
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "dataset_kind": LEGACY_DATASET_KIND,
                "provider_id": batch.provider_id,
                "provider_version": batch.provider_version,
                "source_id": inventory["source_id"],
                "loader_id": inventory["loader_id"],
                "source_schema_version": inventory["source_schema_version"],
                "source_files": [
                    {
                        "file_relative_path": item["file_relative_path"],
                        "year": item["year"],
                        "size_bytes": item["size_bytes"],
                        "sha256": item["sha256"],
                    }
                    for item in inventory["files"]
                ],
                "source_schema": inventory["schema"],
                "feature_access_policy": access_policy,
                "request": request.to_dict(),
                "symbol_selection_rule": batch.symbol_selection_rule,
                "selected_symbols": list(batch.selected_symbols),
                "included_feature_columns": list(request.columns or batch.inventory.schema.research_feature_columns),
                "included_label_columns": list(batch.inventory.schema.label_columns) if request.include_labels else [],
                "normalization_version": LEGACY_NORMALIZATION_VERSION,
                "output_schema": output_schema,
                "partition_hashes": [parquet_hash],
            }
            snapshot_id = "ds_" + sha256_bytes(canonical_json_bytes(identity_payload))
            final = self.output_root / "snapshots" / snapshot_id
            manifest = {
                **identity_payload,
                "snapshot_id": snapshot_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "date_range": {
                    "start": request.start_date.isoformat(),
                    "end": request.end_date.isoformat(),
                },
                "calendar_id": "source-observed-dates-v1",
                "universe_id": batch.symbol_selection_rule,
                "row_count": int(len(batch.frame)),
                "symbol_count": int(batch.frame["symbol"].nunique()),
                "date_count": int(pd.to_datetime(batch.frame["trade_date"]).nunique()),
                "feature_count": len(identity_payload["included_feature_columns"]),
                "label_count": len(identity_payload["included_label_columns"]),
                "partition_count": 1,
                "file_hashes": {"partitions/feature_matrix/part-00000.parquet": parquet_hash},
                "quality_summary": quality["summary"],
                "identity_payload": identity_payload,
            }
            write_json(staging / "source_inventory.json", inventory)
            write_json(staging / "schema.json", {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "dataset_kind": LEGACY_DATASET_KIND,
                "output_schema": output_schema,
                "column_roles": inventory["schema"]["column_roles"],
                "access_policy": access_policy,
            })
            write_json(staging / "quality.json", quality)
            write_json(staging / "manifest.json", manifest)
            self._validate_directory(staging, expected_id=snapshot_id)
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                existing = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
                if existing.get("identity_payload") != identity_payload:
                    raise SnapshotConflictError("legacy Snapshot ID content conflict")
                shutil.rmtree(staging)
                return {"status": "existing", "snapshot_id": snapshot_id, "path": str(final), "manifest": existing}
            staging.replace(final)
            return {"status": "created", "snapshot_id": snapshot_id, "path": str(final), "manifest": manifest}
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    def validate(
        self,
        snapshot_id: str,
        binding: LegacyFeatureSourceBinding | None = None,
    ) -> dict[str, Any]:
        root = self.output_root / "snapshots" / snapshot_id
        result = self._validate_directory(root, expected_id=snapshot_id)
        if binding is not None:
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            if binding.source_id != manifest["source_id"] or binding.loader_id != manifest["loader_id"]:
                raise SnapshotValidationError("source binding identity mismatch")
            for item in manifest["source_files"]:
                source = (binding.local_root / item["file_relative_path"]).resolve()
                if binding.local_root not in source.parents:
                    raise SnapshotValidationError("source inventory path escapes binding")
                if not source.is_file() or source.stat().st_size != item["size_bytes"] or sha256_file(source) != item["sha256"]:
                    raise SnapshotValidationError("legacy source file drift")
            result["source_lineage"] = "valid"
        return result

    @staticmethod
    def _validate_directory(root: Path, *, expected_id: str) -> dict[str, Any]:
        try:
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            quality = json.loads((root / "quality.json").read_text(encoding="utf-8"))
            schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
            inventory = json.loads((root / "source_inventory.json").read_text(encoding="utf-8"))
        except Exception as exc:
            raise SnapshotValidationError("legacy Snapshot metadata missing or invalid") from exc
        if manifest.get("dataset_kind") != LEGACY_DATASET_KIND or schema.get("dataset_kind") != LEGACY_DATASET_KIND:
            raise SnapshotValidationError("legacy Snapshot dataset kind mismatch")
        computed = "ds_" + sha256_bytes(canonical_json_bytes(manifest["identity_payload"]))
        if expected_id != computed or manifest.get("snapshot_id") != computed:
            raise SnapshotValidationError("legacy Snapshot identity mismatch")
        if quality.get("summary", {}).get("error"):
            raise SnapshotValidationError("legacy Snapshot quality contains errors")
        if inventory.get("source_id") != manifest.get("source_id"):
            raise SnapshotValidationError("legacy source inventory mismatch")
        for relative, expected_hash in manifest["file_hashes"].items():
            path = root / relative
            if not path.is_file() or sha256_file(path) != expected_hash:
                raise SnapshotValidationError("legacy Snapshot file hash mismatch")
        parquet_path = root / "partitions" / "feature_matrix" / "part-00000.parquet"
        table = pq.read_table(parquet_path)
        if _arrow_schema_payload(table.schema) != manifest["output_schema"]:
            raise SnapshotValidationError("legacy Snapshot output schema mismatch")
        frame = table.to_pandas()
        if len(frame) != manifest["row_count"] or frame["symbol"].nunique() != manifest["symbol_count"]:
            raise SnapshotValidationError("legacy Snapshot row or symbol count mismatch")
        return {
            "status": "valid",
            "snapshot_id": computed,
            "dataset_kind": LEGACY_DATASET_KIND,
            "rows": len(frame),
            "symbols": int(frame["symbol"].nunique()),
            "dates": int(pd.to_datetime(frame["trade_date"]).nunique()),
        }


def _load_manifest_and_frame(output_root: Path, snapshot_id: str) -> tuple[dict[str, Any], pd.DataFrame]:
    root = Path(output_root) / "snapshots" / snapshot_id
    LegacyFeatureSnapshotService(output_root).validate(snapshot_id)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_parquet(root / "partitions" / "feature_matrix" / "part-00000.parquet", engine="pyarrow")
    return manifest, frame


def load_feature_matrix(
    output_root: Path,
    snapshot_id: str,
    symbols: tuple[str, ...] | None = None,
    date_range: tuple[date, date] | None = None,
    feature_columns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    manifest, frame = _load_manifest_and_frame(output_root, snapshot_id)
    allowed = tuple(manifest["included_feature_columns"])
    requested = feature_columns or allowed
    if any(name not in allowed for name in requested):
        raise LegacyFeatureAccessError("feature reader cannot access labels, forbidden, unknown, or absent columns")
    if symbols:
        wanted = {normalize_symbol(item) for item in symbols}
        frame = frame[frame["symbol"].isin(wanted)]
    if date_range:
        dates = pd.to_datetime(frame["trade_date"]).dt.date
        frame = frame[(dates >= date_range[0]) & (dates <= date_range[1])]
    return frame[["symbol", "trade_date", *requested]].sort_values(
        ["trade_date", "symbol"], kind="mergesort"
    ).reset_index(drop=True)


def load_labels(
    output_root: Path,
    snapshot_id: str,
    label_columns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    manifest, frame = _load_manifest_and_frame(output_root, snapshot_id)
    allowed = tuple(manifest["included_label_columns"])
    if not allowed:
        raise LegacyFeatureAccessError("Snapshot contains no explicitly included labels")
    requested = label_columns or allowed
    if any(name not in allowed for name in requested):
        raise LegacyFeatureAccessError("label reader requested an unavailable label")
    return frame[["symbol", "trade_date", *requested]].sort_values(
        ["trade_date", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
