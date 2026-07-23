from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json


KINDS = {
    "autonomous_factor_campaign_spec": ("campaign_spec_id", "afc1_"),
    "autonomous_factor_campaign": ("campaign_id", "afcs1_"),
    "autonomous_factor_round": ("round_result_id", "afr1_"),
    "autonomous_factor_proposal": ("proposal_artifact_id", "afp1_"),
    "autonomous_factor_failure_memory": ("memory_id", "affm1_"),
    "autonomous_factor_round_plan": ("round_plan_id", "afrp1_"),
    "autonomous_factor_candidate_lock": ("candidate_lock_id", "afcl1_"),
    "autonomous_factor_near_miss": ("near_miss_id", "afnm1_"),
    "autonomous_factor_campaign_report": ("report_id", "afcr1_"),
    "autonomous_factor_value_materialization": ("factor_values_id", "afcv1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or (expected_kind and kind != expected_kind):
        raise ValueError("autonomous campaign Artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or expected_id != prefix + hash_payload(identity):
        raise ValueError("autonomous campaign Artifact identity mismatch")
    if manifest.get(field) != expected_id:
        raise ValueError("autonomous campaign Artifact ID field mismatch")
    if identity.get("provider_id") != "tushare-pro-v1":
        raise ValueError("autonomous campaign data authority mismatch")
    if identity.get("promotion_writes", 0) != 0:
        raise ValueError("autonomous campaign crossed Promotion boundary")
    if kind == "autonomous_factor_candidate_lock" and identity.get("status") != "research_registered":
        raise ValueError("autonomous candidate status is not research_registered")
    if any(key in json.dumps(identity, sort_keys=True).lower() for key in ("tushare_token", "access_token", "api_key")):
        raise ValueError("secret marker is forbidden")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("autonomous campaign file inventory invalid")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != set(hashes) or any(hash_file(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("autonomous campaign file hash mismatch")
    for name in actual:
        if name.endswith(".json"):
            lowered = (root / name).read_bytes().lower()
            if any(marker in lowered for marker in (b"tushare_token", b"access_token", b"api_key", b"private_key")):
                raise ValueError("autonomous campaign JSON contains a forbidden secret marker")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported autonomous campaign Artifact kind")
    field, prefix = KINDS[kind]
    stable = dict(identity)
    stable.pop(field, None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_artifact(target, artifact_id, kind)
        return json.loads((target / "manifest.json").read_text()) | {"path": str(target), "exact_existing": True}
    staging = target.parent / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        for relative, value in sorted(files.items()):
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
        hashes = {p.relative_to(staging).as_posix(): hash_file(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        manifest = {
            "schema_version": "autonomous-factor-campaign-artifact-v1",
            "artifact_kind": kind, field: artifact_id, "identity": stable, "file_hashes": hashes,
        }
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
