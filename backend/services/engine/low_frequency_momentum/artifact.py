from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .protocol import COMPLETENESS_REQUIRED, TASK_ID


KINDS = {
    "low_frequency_momentum_signal_spec": ("signal_artifact_id", "lfmsa1_"),
    "low_frequency_execution_protocol": ("protocol_id", "lfmep1_"),
    "low_frequency_momentum_annual_result": ("annual_result_id", "lfmar1_"),
    "low_frequency_momentum_candidate_lock": ("candidate_lock_id", "lfmcl1_"),
    "low_frequency_momentum_report": ("report_id", "lfmr1_"),
    "low_frequency_momentum_assessment": ("assessment_id", "lfma1_"),
    "low_frequency_momentum_study": ("study_artifact_id", "lfmsta1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or expected_kind is not None and kind != expected_kind:
        raise ValueError("low-frequency momentum artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or manifest.get(field) != expected_id or expected_id != prefix + hash_payload(identity):
        raise ValueError("low-frequency momentum artifact identity mismatch")
    if identity.get("provider_id") != "tushare-pro-v1" or identity.get("promotion_writes", 0) != 0:
        raise ValueError("low-frequency momentum authority boundary failed")
    missing = [name for name in COMPLETENESS_REQUIRED[kind] if name not in identity]
    if missing:
        raise ValueError("SIGNAL_SPEC_INCOMPLETE:" + ",".join(missing))
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("low-frequency momentum file inventory invalid")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != set(hashes) or any(hash_file(root / path) != digest for path, digest in hashes.items()):
        raise ValueError("low-frequency momentum file inventory/hash mismatch")
    if kind == "low_frequency_momentum_signal_spec":
        if identity.get("fixed_weights") is None or identity.get("optimizable_parameters") != []:
            raise ValueError("signal weights/parameter boundary failed")
    if kind == "low_frequency_execution_protocol":
        if identity.get("candidate_protocol") != "L1" or identity.get("strategy_optimization_allowed") is not False:
            raise ValueError("execution protocol boundary failed")
    if kind == "low_frequency_momentum_candidate_lock":
        if identity.get("status") != "research_registered" or identity.get("protocol_id") != "L1":
            raise ValueError("candidate lock crossed research-only boundary")
    if kind == "low_frequency_momentum_report":
        if not identity.get("not_used_for_selection") or not identity.get("not_fresh_validation"):
            raise ValueError("report-only boundary failed")
    if kind == "low_frequency_momentum_study" and identity.get("task_id") != TASK_ID:
        raise ValueError("low-frequency momentum task identity mismatch")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported low-frequency momentum artifact kind")
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
        manifest = {"schema_version": "low-frequency-momentum-artifact-v1", "artifact_kind": kind,
                    field: artifact_id, "identity": stable, "file_hashes": hashes}
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
