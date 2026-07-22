from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_payload, write_json

from .protocol import ARTIFACT_FILES


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict:
    if kind not in ARTIFACT_FILES:
        raise ValueError(f"unsupported parameter ablation artifact kind: {kind}")
    stable = dict(identity)
    artifact_id = "poa1_" + hash_payload({"kind": kind, "identity": stable})
    target = Path(root) / kind / artifact_id
    if target.exists():
        raise FileExistsError(f"diagnostic artifact already exists in staging: {artifact_id}")
    target.mkdir(parents=True)
    for name, value in files.items():
        path = target / name
        if isinstance(value, Path):
            path.write_bytes(value.read_bytes())
        elif isinstance(value, bytes):
            path.write_bytes(value)
        else:
            write_json(path, value)
    manifest = {
        "schema_version": "parameter-optimization-ablation-artifact-v1",
        "artifact_id": artifact_id, "artifact_kind": kind, "identity": stable,
        "files": [
            {"path": name, "sha256": hashlib.sha256((target / name).read_bytes()).hexdigest(),
             "size_bytes": (target / name).stat().st_size}
            for name in sorted(files)
        ],
    }
    write_json(target / "manifest.json", manifest)
    validate_artifact(target, artifact_id, kind)
    return {"artifact_id": artifact_id, "artifact_kind": kind, "path": str(target)}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in ARTIFACT_FILES or manifest.get("artifact_id") != expected_id:
        raise ValueError("parameter ablation artifact identity mismatch")
    if expected_kind is not None and kind != expected_kind:
        raise ValueError("parameter ablation artifact kind mismatch")
    identity = manifest.get("identity", {})
    rebuilt = "poa1_" + hash_payload({"kind": kind, "identity": identity})
    if rebuilt != expected_id:
        raise ValueError("parameter ablation content identity mismatch")
    if identity.get("provider_id") != "tushare-pro-v1":
        raise ValueError("parameter ablation data authority mismatch")
    if any(identity.get(name, 0) for name in ("agent_calls", "network_calls", "promotion_writes")):
        raise ValueError("parameter ablation crossed forbidden execution boundary")
    recorded = {item["path"] for item in manifest.get("files", [])}
    required = set(ARTIFACT_FILES[kind])
    if not required.issubset(recorded):
        raise ValueError(f"parameter ablation missing required files: {sorted(required-recorded)}")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != recorded:
        raise ValueError("parameter ablation file inventory mismatch")
    for item in manifest["files"]:
        path = root / item["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"parameter ablation file hash mismatch: {item['path']}")
    return {"status": "valid", "artifact_id": expected_id, "artifact_kind": kind,
            "file_count": len(recorded)}
