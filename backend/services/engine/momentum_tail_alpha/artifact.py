from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .protocol import CLASSIFICATIONS, COMPLETENESS, DECISIONS, TASK_ID


KINDS = {
    "momentum_quantile_return_report": ("quantile_report_id", "mqrr1_"),
    "momentum_rank_transition_report": ("transition_report_id", "mrtr1_"),
    "momentum_tail_style_exposure": ("style_exposure_id", "mtse1_"),
    "momentum_tail_signal_classification": ("classification_id", "mtsc1_"),
    "momentum_tail_alpha_diagnostic": ("diagnostic_id", "mtad1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or expected_kind is not None and kind != expected_kind:
        raise ValueError("momentum tail-alpha artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or manifest.get(field) != expected_id:
        raise ValueError("momentum tail-alpha artifact identity mismatch")
    if expected_id != prefix + hash_payload(identity):
        raise ValueError("momentum tail-alpha semantic hash mismatch")
    if identity.get("provider_id") != "tushare-pro-v1":
        raise ValueError("momentum tail-alpha provider boundary failed")
    missing = [name for name in COMPLETENESS[kind] if name not in identity]
    if missing:
        raise ValueError("TAIL_DIAGNOSTIC_INCOMPLETE:" + ",".join(missing))
    hashes = manifest.get("file_hashes")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if not isinstance(hashes, dict) or "manifest.json" in hashes or set(hashes) != actual:
        raise ValueError("momentum tail-alpha file inventory mismatch")
    if any(hash_file(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("momentum tail-alpha file hash mismatch")
    if kind == "momentum_tail_signal_classification":
        if identity["primary_classification"] not in CLASSIFICATIONS or identity["research_decision"] not in DECISIONS:
            raise ValueError("momentum tail-alpha classification boundary failed")
    if kind == "momentum_tail_alpha_diagnostic":
        counts = identity["execution_counts"]
        forbidden = ("agent_calls", "factor_optimization_calls", "strategy_optimization_calls",
                     "combined_optimization_calls", "qlib_strategy_calls", "network_calls",
                     "registry_writes", "promotion_writes")
        if identity.get("task_id") != TASK_ID or any(counts.get(name) != 0 for name in forbidden):
            raise ValueError("momentum tail-alpha governance boundary failed")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported momentum tail-alpha artifact kind")
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
        manifest = {"schema_version": "momentum-tail-alpha-artifact-v1", "artifact_kind": kind,
                    field: artifact_id, "identity": stable, "file_hashes": hashes}
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
