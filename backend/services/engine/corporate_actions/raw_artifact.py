from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .capability import CapabilityResult
from .tushare_client import SafeTushareResult


ARTIFACT_CONTRACTS = {
    "tushare_corporate_action_raw": ("raw_snapshot_id", "tsca_raw_"),
    "security_corporate_action_event": ("event_artifact_id", "scae_"),
    "fixed_universe_benchmark_contract": ("benchmark_contract_id", "fubc_"),
    "fixed_universe_benchmark_revision": ("benchmark_revision_id", "fubr_"),
    "historical_backtest_benchmark_followup": ("benchmark_followup_id", "hbfr_"),
}


def artifact_id(manifest: Mapping[str, Any]) -> str:
    kind = manifest.get("artifact_kind")
    if kind not in ARTIFACT_CONTRACTS:
        raise ValueError("unsupported corporate-action Artifact kind")
    return str(manifest[ARTIFACT_CONTRACTS[str(kind)][0]])


def validate_corporate_action_artifact(
    root: Path, expected_id: str, *, expected_kind: str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in ARTIFACT_CONTRACTS or (expected_kind and kind != expected_kind):
        raise ValueError("corporate-action Artifact kind mismatch")
    field, prefix = ARTIFACT_CONTRACTS[kind]
    identity = manifest.get("identity")
    if (
        manifest.get(field) != expected_id
        or not expected_id.startswith(prefix)
        or not isinstance(identity, dict)
        or expected_id != prefix + hash_payload(identity)
    ):
        raise ValueError("corporate-action Artifact identity mismatch")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("corporate-action file inventory is invalid")
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != set(hashes):
        raise ValueError("corporate-action file inventory mismatch")
    for relative, digest in hashes.items():
        if hash_file(root / relative) != digest:
            raise ValueError("corporate-action file hash mismatch")
    if any("token" in path.read_text(encoding="utf-8", errors="ignore").lower()
           for path in root.rglob("*.json") if path.name != "manifest.json"):
        raise ValueError("corporate-action Artifact contains credential-shaped key")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id,
            "file_count": len(actual)}


def publish_artifact(
    root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any],
) -> dict[str, Any]:
    if kind not in ARTIFACT_CONTRACTS:
        raise ValueError("unsupported corporate-action Artifact kind")
    field, prefix = ARTIFACT_CONTRACTS[kind]
    stable = dict(identity)
    stable.pop(field, None)
    intended = prefix + hash_payload(stable)
    target = Path(root) / kind / intended
    if target.exists():
        validate_corporate_action_artifact(target, intended, expected_kind=kind)
        return json.loads((target / "manifest.json").read_text()) | {
            "path": str(target), "exact_existing": True,
        }
    staging = target.parent / f".{intended}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        for relative, value in sorted(files.items()):
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, pd.DataFrame):
                value.to_parquet(path, index=False, compression="zstd")
            elif isinstance(value, bytes):
                path.write_bytes(value)
            elif isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)
        hashes = {
            path.relative_to(staging).as_posix(): hash_file(path)
            for path in sorted(staging.rglob("*")) if path.is_file()
        }
        manifest = {
            "schema_version": "corporate-action-artifact-v1",
            "artifact_kind": kind, field: intended,
            "provider_id": "tushare-pro-v1", "identity": stable,
            "file_hashes": hashes,
        }
        write_json(staging / "manifest.json", manifest)
        validate_corporate_action_artifact(staging, intended, expected_kind=kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}


def publish_raw_snapshot(
    root: Path,
    *,
    symbols: tuple[str, ...],
    capabilities: tuple[CapabilityResult, ...],
    responses: tuple[SafeTushareResult, ...],
) -> dict[str, Any]:
    requests, event_rows, announcement_rows, response_hashes = [], [], [], []
    for index, response in enumerate(responses):
        response_payload = {
            "endpoint": response.endpoint, "params": response.params,
            "requested_fields": list(response.requested_fields),
            "available_fields": list(response.available_fields),
            "status": response.status.value, "safe_error_code": response.safe_error_code,
            "rows": list(response.rows),
        }
        digest = hash_payload(response_payload)
        response_hashes.append({"request_index": index, "sha256": digest})
        requests.append({key: value for key, value in response_payload.items() if key != "rows"})
        destination = announcement_rows if response.endpoint == "major_news" else event_rows
        for row_index, row in enumerate(response.rows):
            destination.append({
                "endpoint": response.endpoint,
                "request_index": index,
                "source_record_id": "tscar_" + hash_payload({
                    "response_hash": digest, "row_index": row_index, "row": row,
                }),
                "symbol": response.params.get("ts_code"),
                "payload_json": json.dumps(
                    row, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ),
            })
    identity = {
        "schema_version": "tushare-corporate-action-raw-v1",
        "provider_id": "tushare-pro-v1", "symbols": list(symbols),
        "request_contracts": requests, "response_hashes": response_hashes,
    }
    capability_payload = [item.payload() for item in capabilities]
    quality = {
        "schema_version": "corporate-action-raw-quality-v1",
        "request_count": len(requests),
        "available_request_count": sum(row["status"] == "available" for row in requests),
        "event_row_count": len(event_rows),
        "announcement_row_count": len(announcement_rows),
        "raw_issuer_announcement_available": any(
            row["endpoint"] == "anns_d" and row["status"] == "available"
            for row in requests
        ),
        "structured_settlement_evidence_complete": False,
        "safe_errors_only": True,
    }
    return publish_artifact(root, "tushare_corporate_action_raw", identity, {
        "requests.json": {"requests": requests, "capabilities": capability_payload},
        "events.parquet": pd.DataFrame(event_rows, columns=(
            "endpoint", "request_index", "source_record_id", "symbol", "payload_json",
        )),
        "announcements.parquet": pd.DataFrame(announcement_rows, columns=(
            "endpoint", "request_index", "source_record_id", "symbol", "payload_json",
        )),
        "quality.json": quality,
    })
