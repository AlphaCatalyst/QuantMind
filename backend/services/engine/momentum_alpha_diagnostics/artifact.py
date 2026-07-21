from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_payload, write_json

from .protocol import ARTIFACT_FILES


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict:
    if kind not in ARTIFACT_FILES:
        raise ValueError(f"unsupported diagnostic artifact kind: {kind}")
    stable = dict(identity)
    artifact_id = "mada1_" + hash_payload({"kind": kind, "identity": stable})
    target = Path(root) / kind / artifact_id
    target.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        path = target / name
        if isinstance(value, Path):
            path.write_bytes(value.read_bytes())
        elif isinstance(value, bytes):
            path.write_bytes(value)
        else:
            write_json(path, value)
    manifest = {
        "schema_version": "momentum-alpha-diagnostic-artifact-v1",
        "artifact_id": artifact_id, "artifact_kind": kind,
        "identity": stable,
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
    kind = manifest["artifact_kind"]
    if manifest["artifact_id"] != expected_id or (expected_kind and kind != expected_kind):
        raise ValueError("diagnostic artifact identity mismatch")
    required = set(ARTIFACT_FILES.get(kind, ()))
    recorded = {item["path"] for item in manifest["files"]}
    if not required.issubset(recorded):
        raise ValueError(f"diagnostic artifact missing files: {sorted(required - recorded)}")
    for item in manifest["files"]:
        path = root / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"diagnostic artifact hash mismatch: {item['path']}")
    rebuilt = "mada1_" + hash_payload({"kind": kind, "identity": manifest["identity"]})
    if rebuilt != expected_id:
        raise ValueError("diagnostic artifact content identity mismatch")
    return {"status": "valid", "artifact_id": expected_id, "artifact_kind": kind,
            "file_count": len(manifest["files"])}
