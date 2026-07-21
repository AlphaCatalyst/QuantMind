from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .protocol import COMPLETENESS_REQUIRED


KINDS = {
    "research_agent_raw_response": ("raw_response_artifact_id", "rar1_"),
    "research_proposal": ("proposal_artifact_id", "rpa1_"),
    "factor_template_definition": ("template_definition_id", "ftd1_"),
    "factor_optimization_trial_detail": ("trial_detail_id", "fotd1_"),
    "factor_fold_candidate_lock": ("fold_lock_id", "ffcl1_"),
    "factor_candidate_eligibility_evidence": ("eligibility_evidence_id", "fcee1_"),
    "skip_recent_momentum_experiment": ("experiment_id", "srme1_"),
    "skip_recent_momentum_candidate_lock": ("candidate_lock_id", "srmcl1_"),
    "skip_recent_momentum_report": ("report_id", "srmr1_"),
    "skip_recent_momentum_assessment": ("assessment_id", "srma1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or (expected_kind and kind != expected_kind):
        raise ValueError("skip-recent artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or manifest.get(field) != expected_id or expected_id != prefix + hash_payload(identity):
        raise ValueError("skip-recent artifact identity mismatch")
    if identity.get("provider_id") != "tushare-pro-v1" or identity.get("promotion_writes", 0) != 0:
        raise ValueError("skip-recent authority boundary failed")
    missing = [name for name in COMPLETENESS_REQUIRED.get(kind, ()) if name not in identity]
    if missing:
        raise ValueError("ARTIFACT_COMPLETENESS_FAILED:" + ",".join(missing))
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("skip-recent file inventory invalid")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != set(hashes) or any(hash_file(root / rel) != digest for rel, digest in hashes.items()):
        raise ValueError("skip-recent file inventory/hash mismatch")
    if kind == "research_agent_raw_response":
        raw = (root / "raw_response.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != identity["raw_response_hash"] or len(raw) != identity["response_size_bytes"]:
            raise ValueError("Agent response hash/length mismatch")
        lowered = raw.lower()
        if any(marker in lowered for marker in (b"tushare_token", b"api_key", b"access_token", b"private_key")):
            raise ValueError("Agent response contains a forbidden secret marker")
    if kind == "skip_recent_momentum_candidate_lock":
        if identity.get("status") != "research_registered" or any(identity.get(name) for name in ("predictive_claim", "fresh_validation", "usable_for_promotion", "eligible_for_production")):
            raise ValueError("candidate lock crossed research-only boundary")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Path | bytes | str | Mapping[str, Any]]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported skip-recent artifact kind")
    field, prefix = KINDS[kind]
    stable = dict(identity); stable.pop(field, None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_artifact(target, artifact_id, kind)
        return json.loads((target / "manifest.json").read_text()) | {"path": str(target), "exact_existing": True}
    staging = target.parent / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        for relative, value in sorted(files.items()):
            destination = staging / relative; destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, Path): shutil.copyfile(value, destination)
            elif isinstance(value, bytes): destination.write_bytes(value)
            elif isinstance(value, str): destination.write_text(value, encoding="utf-8")
            else: write_json(destination, value)
        hashes = {p.relative_to(staging).as_posix(): hash_file(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        manifest = {"schema_version": "research-artifact-completeness-v1", "artifact_kind": kind, field: artifact_id, "identity": stable, "file_hashes": hashes}
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}


def assert_complete(kind: str, identity: Mapping[str, Any]) -> None:
    missing = [name for name in COMPLETENESS_REQUIRED.get(kind, ()) if name not in identity]
    if missing:
        raise RuntimeError("ARTIFACT_COMPLETENESS_FAILED:" + ",".join(missing))
