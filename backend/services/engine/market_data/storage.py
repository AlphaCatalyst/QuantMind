from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
import uuid

from .errors import SnapshotConflictError


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def capture_raw(output_root: Path, batch: Any) -> tuple[str, dict[str, Any]]:
    rows = [dict(row) for row in batch.rows]
    response_bytes = canonical_json_bytes(rows)
    response_hash = sha256_bytes(response_bytes)
    identity = {"provider_id": batch.provider_id, "provider_version": batch.provider_version, "request": batch.request.to_dict(), "response_sha256": response_hash}
    ingest_id = "ing_" + sha256_bytes(canonical_json_bytes(identity))
    target = output_root / "raw" / batch.provider_id / ingest_id
    if target.exists():
        existing = json.loads((target / "raw_sha256.json").read_text())
        if existing.get("raw_response.json") != response_hash:
            raise SnapshotConflictError("raw capture identity conflict")
        return ingest_id, {"ingest_id": ingest_id, "response_sha256": response_hash}
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{ingest_id}.staging-{uuid.uuid4().hex}"
    try:
        staging.mkdir(parents=False, exist_ok=False)
        write_json(staging / "request.json", batch.request.to_dict())
        write_json(staging / "provider_metadata.json", {
            "provider_id": batch.provider_id, "provider_version": batch.provider_version,
            "fetched_at": batch.fetched_at.isoformat(), "units": dict(batch.units),
            "source_metadata": dict(batch.source_metadata),
        })
        (staging / "raw_response.json").write_bytes(response_bytes)
        write_json(staging / "raw_sha256.json", {"raw_response.json": response_hash})
        staging.replace(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return ingest_id, {"ingest_id": ingest_id, "response_sha256": response_hash}
