from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json


KINDS = {
    "breadth_momentum_gate_spec": ("gate_spec_id", "bmgs1_"),
    "breadth_gated_momentum_historical_diagnostic": ("historical_diagnostic_id", "bgmhd1_"),
    "breadth_gated_momentum_fresh_lock": ("fresh_lock_id", "bgmfl1_"),
    "tushare_incremental_market_snapshot": ("incremental_snapshot_id", "tims1_"),
    "breadth_gated_momentum_fresh_observation": ("fresh_observation_id", "bgmfo1_"),
    "breadth_gated_momentum_fresh_assessment": ("fresh_assessment_id", "bgmfa1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or expected_kind is not None and kind != expected_kind:
        raise ValueError("breadth-gated momentum artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or manifest.get(field) != expected_id:
        raise ValueError("breadth-gated momentum artifact identity mismatch")
    if expected_id != prefix + hash_payload(identity):
        raise ValueError("breadth-gated momentum semantic hash mismatch")
    if identity.get("provider_id") != "tushare-pro-v1":
        raise ValueError("breadth-gated momentum provider mismatch")
    if identity.get("registry_writes", 0) != 0 or identity.get("promotion_writes", 0) != 0:
        raise ValueError("breadth-gated momentum governance boundary failed")
    if kind == "breadth_momentum_gate_spec":
        if identity.get("active_regime") != "narrow_or_weak" or identity.get("gate_lag") != 1:
            raise ValueError("breadth gate contract mismatch")
        if not identity.get("double_lag_forbidden") or identity.get("parameter_optimization_allowed") is not False:
            raise ValueError("breadth gate optimization boundary failed")
    if kind == "breadth_gated_momentum_fresh_lock":
        if identity.get("fresh_start_date") != "2026-06-24" or identity.get("no_backfill") is not True:
            raise ValueError("fresh lock boundary failed")
    if kind in {"breadth_gated_momentum_fresh_observation", "breadth_gated_momentum_fresh_assessment"}:
        if identity.get("fresh_start_date") != "2026-06-24":
            raise ValueError("fresh observation boundary failed")
    hashes = manifest.get("file_hashes")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if not isinstance(hashes, dict) or "manifest.json" in hashes or set(hashes) != actual:
        raise ValueError("breadth-gated momentum file inventory mismatch")
    if any(hash_file(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("breadth-gated momentum file hash mismatch")
    serialized = json.dumps({"manifest": manifest}, sort_keys=True)
    if "TUSHARE_TOKEN" in serialized or "token_hash" in serialized:
        raise ValueError("credential material forbidden")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported breadth-gated momentum artifact kind")
    field, prefix = KINDS[kind]
    stable = dict(identity)
    stable.pop(field, None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_artifact(target, artifact_id, kind)
        return json.loads((target / "manifest.json").read_text(encoding="utf-8")) | {"path": str(target), "exact_existing": True}
    staging = target.parent / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        for relative, value in sorted(files.items()):
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, Path):
                shutil.copyfile(value, destination)
            elif isinstance(value, pd.DataFrame):
                value.to_parquet(destination, index=False, compression="zstd", engine="pyarrow")
            elif isinstance(value, bytes):
                destination.write_bytes(value)
            elif isinstance(value, str):
                destination.write_text(value, encoding="utf-8")
            else:
                write_json(destination, value)
        hashes = {p.relative_to(staging).as_posix(): hash_file(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        manifest = {"schema_version": "breadth-gated-momentum-artifact-v1", "artifact_kind": kind,
                    field: artifact_id, "identity": stable, "file_hashes": hashes}
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
