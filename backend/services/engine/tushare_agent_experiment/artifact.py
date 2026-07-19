from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import (
    hash_file,
    hash_payload,
    write_json,
)


PREFIXES = {
    "tushare_historical_agent_experiment": ("experiment_id", "tha_"),
    "tushare_historical_round_lock": ("round_lock_id", "thl_"),
    "tushare_historical_round_evaluation": ("evaluation_id", "the_"),
    "tushare_qlib_backtest_result": ("backtest_result_id", "tqb_"),
    "tushare_historical_holdout_result": ("holdout_result_id", "thh_"),
    "tushare_agent_iteration_assessment": ("assessment_id", "tia_"),
    "tushare_historical_experiment_registry": (
        "historical_experiment_registry_id",
        "thr_",
    ),
}


def validate_experiment_artifact(
    root: Path, expected_id: str, *, expected_kind: str | None = None
) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in PREFIXES or (expected_kind is not None and kind != expected_kind):
        raise ValueError("Tushare experiment artifact kind mismatch")
    id_field, prefix = PREFIXES[kind]
    if manifest.get(id_field) != expected_id or not expected_id.startswith(prefix):
        raise ValueError("Tushare experiment artifact identity mismatch")
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or expected_id != prefix + hash_payload(identity):
        raise ValueError("Tushare experiment canonical identity mismatch")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("Tushare experiment file inventory is invalid")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != set(hashes):
        raise ValueError("Tushare experiment file inventory mismatch")
    for relative, digest in hashes.items():
        if hash_file(root / relative) != digest:
            raise ValueError("Tushare experiment file hash mismatch")
    if identity.get("provider_id") != "tushare-pro-v1":
        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    if identity.get("promotion_writes", 0) != 0:
        raise ValueError("historical experiment cannot write promotion state")
    if kind == "tushare_historical_round_lock" and identity.get("locked_before_evaluation") is not True:
        raise ValueError("round candidate was not locked before evaluation")
    if kind == "tushare_historical_holdout_result":
        lock = identity.get("candidate_lock", {})
        if lock.get("holdout_metrics_used") is not False or identity.get("holdout_feedback_to_agent") is not False:
            raise ValueError("holdout isolation evidence is invalid")
    if kind == "tushare_historical_experiment_registry":
        payload_path = root / "registry.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if (
            payload.get("promotion_candidate_count") != 0
            or payload.get("approved_count") != 0
            or payload.get("active_count") != 0
            or any(row.get("status") != "research_registered" for row in payload.get("entries", []))
        ):
            raise ValueError("historical Registry contains forbidden production state")
    if kind == "tushare_historical_agent_experiment":
        payload = json.loads((root / "experiment.json").read_text(encoding="utf-8"))
        if payload.get("legacy_reads") != 0 or payload.get("tushare_network_calls") != 0:
            raise ValueError("historical experiment authority boundary failed")
    return {
        "status": "valid",
        "artifact_kind": kind,
        "artifact_id": expected_id,
        "file_count": len(actual),
    }


def publish_experiment_artifact(
    root: Path,
    kind: str,
    identity: Mapping[str, Any],
    files: Mapping[str, Path | bytes | str | Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if kind not in PREFIXES:
        raise ValueError("unsupported Tushare experiment artifact kind")
    id_field, prefix = PREFIXES[kind]
    stable = dict(identity)
    stable.pop(id_field, None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_experiment_artifact(target, artifact_id, expected_kind=kind)
        return {
            **json.loads((target / "manifest.json").read_text(encoding="utf-8")),
            "path": str(target),
            "exact_existing": True,
        }
    staging = target.parent / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        for relative, value in sorted((files or {}).items()):
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, Path):
                shutil.copyfile(value, destination)
            elif isinstance(value, bytes):
                destination.write_bytes(value)
            elif isinstance(value, str):
                destination.write_text(value, encoding="utf-8")
            else:
                write_json(destination, value)
        hashes = {
            path.relative_to(staging).as_posix(): hash_file(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "schema_version": "tushare-historical-agent-artifact-v1",
            "artifact_kind": kind,
            id_field: artifact_id,
            "identity": stable,
            "file_hashes": hashes,
        }
        write_json(staging / "manifest.json", manifest)
        validate_experiment_artifact(staging, artifact_id, expected_kind=kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
