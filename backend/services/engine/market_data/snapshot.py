from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .errors import DataQualityError, SnapshotConflictError, SnapshotValidationError
from .models import DailyBarsRequest
from .normalization import CANONICAL_UNITS, NORMALIZATION_VERSION, normalize_daily_bars
from .quality import evaluate_daily_bars
from .storage import canonical_json_bytes, capture_raw, sha256_bytes, sha256_file, write_json


SNAPSHOT_SCHEMA_VERSION = "1.0.0"
FIELD_SCHEMA = [
    {"name": "symbol", "type": "string", "nullable": False},
    {"name": "trade_date", "type": "date32", "nullable": False},
    *[{"name": name, "type": "float64", "nullable": False} for name in ("open", "high", "low", "close", "volume", "amount")],
]


class DatasetSnapshotService:
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)

    def create(self, provider: Any, request: DailyBarsRequest) -> dict[str, Any]:
        probe = provider.probe()
        if not probe.available:
            from .errors import ProviderUnavailableError
            raise ProviderUnavailableError(probe.safe_error or "provider unavailable")
        if request.adjustment_mode.value not in probe.supported_adjustments:
            raise DataQualityError("provider does not support requested adjustment")
        batch = provider.fetch_daily_bars(request)
        ingest_id, raw = capture_raw(self.output_root, batch)
        frame = normalize_daily_bars(batch)
        quality = evaluate_daily_bars(frame, request)
        if quality["summary"]["error"]:
            raise DataQualityError("daily-bar quality gate failed")

        staging = self.output_root / f".snapshot-staging-{uuid.uuid4().hex}"
        try:
            partition_dir = staging / "partitions" / "daily_bars"
            partition_dir.mkdir(parents=True)
            parquet = partition_dir / "part-00000.parquet"
            frame.to_parquet(parquet, engine="pyarrow", index=False, compression="zstd")
            partition_hash = sha256_file(parquet)
            identity_payload = {
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "provider_id": batch.provider_id,
                "provider_version": batch.provider_version,
                "request": request.to_dict(),
                "adjustment_mode": request.adjustment_mode.value,
                "symbol_format": "uppercase-prefix-v1",
                "field_schema": FIELD_SCHEMA,
                "units": CANONICAL_UNITS,
                "normalization_version": NORMALIZATION_VERSION,
                "raw_input_hashes": [raw["response_sha256"]],
                "partition_hashes": [partition_hash],
            }
            snapshot_id = "ds_" + sha256_bytes(canonical_json_bytes(identity_payload))
            final = self.output_root / "snapshots" / snapshot_id
            manifest = {
                **identity_payload,
                "snapshot_id": snapshot_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "request_time": batch.fetched_at.isoformat(),
                "date_range": {"start": request.start_date.isoformat(), "end": request.end_date.isoformat()},
                "calendar_id": "weekday-only-unverified-v1",
                "universe_id": "explicit-symbols-v1",
                "row_count": int(len(frame)), "symbol_count": int(frame["symbol"].nunique()),
                "partition_count": 1,
                "raw_inputs": [{"ingest_id": ingest_id, "response_sha256": raw["response_sha256"]}],
                "file_hashes": {"partitions/daily_bars/part-00000.parquet": partition_hash},
                "quality_summary": quality["summary"],
                "identity_payload": identity_payload,
            }
            write_json(staging / "schema.json", {"schema_version": SNAPSHOT_SCHEMA_VERSION, "fields": FIELD_SCHEMA})
            write_json(staging / "quality.json", quality)
            write_json(staging / "manifest.json", manifest)
            self._validate_directory(staging, expected_id=snapshot_id)
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                existing = json.loads((final / "manifest.json").read_text())
                if existing["identity_payload"] != identity_payload:
                    raise SnapshotConflictError("snapshot ID content conflict")
                shutil.rmtree(staging)
                return {"status": "existing", "snapshot_id": snapshot_id, "path": str(final), "manifest": existing}
            staging.replace(final)
            return {"status": "created", "snapshot_id": snapshot_id, "path": str(final), "manifest": manifest}
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    def validate(self, snapshot_id: str) -> dict[str, Any]:
        return self._validate_directory(self.output_root / "snapshots" / snapshot_id, expected_id=snapshot_id)

    @staticmethod
    def _validate_directory(root: Path, *, expected_id: str) -> dict[str, Any]:
        try:
            manifest = json.loads((root / "manifest.json").read_text())
            quality = json.loads((root / "quality.json").read_text())
            schema = json.loads((root / "schema.json").read_text())
        except Exception as exc:
            raise SnapshotValidationError("snapshot metadata missing or invalid") from exc
        computed_id = "ds_" + sha256_bytes(canonical_json_bytes(manifest["identity_payload"]))
        if expected_id != computed_id or manifest.get("snapshot_id") != computed_id:
            raise SnapshotValidationError("snapshot identity mismatch")
        if schema.get("fields") != FIELD_SCHEMA or quality.get("summary", {}).get("error"):
            raise SnapshotValidationError("snapshot schema or quality invalid")
        for relative, expected_hash in manifest["file_hashes"].items():
            path = root / relative
            if not path.is_file() or sha256_file(path) != expected_hash:
                raise SnapshotValidationError("snapshot file hash mismatch")
        frame = pd.read_parquet(root / "partitions/daily_bars/part-00000.parquet", engine="pyarrow")
        if len(frame) != manifest["row_count"] or frame["symbol"].nunique() != manifest["symbol_count"]:
            raise SnapshotValidationError("snapshot row or symbol count mismatch")
        return {"status": "valid", "snapshot_id": computed_id, "rows": len(frame), "symbols": frame["symbol"].nunique()}


def load_daily_bars(output_root: Path, snapshot_id: str, symbols: tuple[str, ...] | None = None, date_range: tuple[date, date] | None = None) -> pd.DataFrame:
    service = DatasetSnapshotService(output_root)
    service.validate(snapshot_id)
    frame = pd.read_parquet(Path(output_root) / "snapshots" / snapshot_id / "partitions/daily_bars/part-00000.parquet", engine="pyarrow")
    if symbols:
        from .symbol import normalize_symbol
        wanted = {normalize_symbol(item) for item in symbols}
        frame = frame[frame["symbol"].isin(wanted)]
    if date_range:
        dates = pd.to_datetime(frame["trade_date"]).dt.date
        frame = frame[(dates >= date_range[0]) & (dates <= date_range[1])]
    return frame.reset_index(drop=True)
