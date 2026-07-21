from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json


KINDS = {
    "momentum_feature_catalog": ("catalog_id", "mfc1_"),
    "momentum_feature_dataset": ("feature_dataset_id", "mfd1_"),
    "momentum_factor_iteration": ("experiment_id", "mfi1_"),
    "momentum_factor_round_result": ("round_result_id", "mfr1_"),
    "momentum_factor_candidate_lock": ("candidate_lock_id", "mfcl1_"),
    "momentum_factor_ensemble": ("ensemble_id", "mfe1_"),
    "momentum_iteration_assessment": ("assessment_id", "mia1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or (expected_kind is not None and kind != expected_kind):
        raise ValueError("momentum factor iteration artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or manifest.get(field) != expected_id or expected_id != prefix + hash_payload(identity):
        raise ValueError("momentum factor iteration artifact identity mismatch")
    if identity.get("provider_id") != "tushare-pro-v1" or identity.get("promotion_writes", 0) != 0:
        raise ValueError("momentum factor iteration authority boundary failed")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("momentum factor iteration file inventory invalid")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "manifest.json"}
    if actual != set(hashes):
        raise ValueError("momentum factor iteration file inventory mismatch")
    if any(hash_file(root / relative) != digest for relative, digest in hashes.items()):
        raise ValueError("momentum factor iteration file hash mismatch")
    if kind in {"momentum_factor_round_result", "momentum_factor_iteration"}:
        serialized = json.dumps(identity, sort_keys=True).lower()
        for forbidden in ("daily_label", "daily_ic", "holdout_2025", "holdout_2026h1", "fixed_100_excess"):
            if forbidden in serialized:
                raise ValueError("Agent-visible momentum artifact leaks forbidden evidence")
    if kind == "momentum_factor_candidate_lock" and identity.get("status") != "research_registered":
        raise ValueError("momentum candidate lock has forbidden Registry status")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any],
                     files: Mapping[str, Path | bytes | str | Mapping[str, Any]] | None = None) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported momentum factor iteration artifact kind")
    field, prefix = KINDS[kind]
    stable = dict(identity)
    stable.pop(field, None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_artifact(target, artifact_id, kind)
        return json.loads((target / "manifest.json").read_text(encoding="utf-8")) | {"path": str(target), "exact_existing": True}
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
        hashes = {path.relative_to(staging).as_posix(): hash_file(path) for path in sorted(staging.rglob("*")) if path.is_file()}
        manifest = {"schema_version": "momentum-factor-iteration-artifact-v1", "artifact_kind": kind, field: artifact_id, "identity": stable, "file_hashes": hashes}
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
