from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_payload, write_json


ARTIFACT_FILES = {
    "factor_optimization_policy": ("policy.json",),
    "strategy_optimization_policy": ("policy.json",),
    "combined_optimization_policy": ("policy.json",),
    "optimization_governance_decision": ("decision.json",),
}
PREFIXES = {
    "factor_optimization_policy": "fop2_",
    "strategy_optimization_policy": "sop2_",
    "combined_optimization_policy": "cop1_",
    "optimization_governance_decision": "ogd1_",
}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict:
    if kind not in ARTIFACT_FILES:
        raise ValueError(f"unsupported optimization governance artifact kind: {kind}")
    stable = dict(identity)
    artifact_id = PREFIXES[kind] + hash_payload({"kind": kind, "identity": stable})
    target = Path(root) / kind / artifact_id
    if target.exists():
        raise FileExistsError(f"optimization governance artifact exists in staging: {artifact_id}")
    target.mkdir(parents=True)
    for name, value in files.items():
        write_json(target / name, value)
    manifest = {
        "schema_version": "optimization-governance-artifact-v1",
        "artifact_id": artifact_id,
        "artifact_kind": kind,
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
    kind = manifest.get("artifact_kind")
    identity = manifest.get("identity", {})
    if kind not in ARTIFACT_FILES or manifest.get("artifact_id") != expected_id:
        raise ValueError("optimization governance artifact identity mismatch")
    if expected_kind is not None and kind != expected_kind:
        raise ValueError("optimization governance artifact kind mismatch")
    if PREFIXES[kind] + hash_payload({"kind": kind, "identity": identity}) != expected_id:
        raise ValueError("optimization governance content identity mismatch")
    if identity.get("task_id") != "QM2-R1-006":
        raise ValueError("optimization governance task identity mismatch")
    forbidden = ("agent_calls", "factor_optimization_calls", "strategy_optimization_calls",
                 "qlib_calls", "network_calls", "promotion_writes")
    if any(identity.get(name, 0) for name in forbidden):
        raise ValueError("optimization governance crossed forbidden execution boundary")
    recorded = {item["path"] for item in manifest.get("files", [])}
    if recorded != set(ARTIFACT_FILES[kind]):
        raise ValueError("optimization governance file inventory mismatch")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and p.name != "manifest.json"}
    if actual != recorded:
        raise ValueError("optimization governance actual file inventory mismatch")
    for item in manifest["files"]:
        if hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("optimization governance file hash mismatch")
    payload = json.loads((root / next(iter(recorded))).read_text(encoding="utf-8"))
    if kind == "optimization_governance_decision":
        required = {"source_ablation_task", "source_correction_task", "factor_decision",
                    "strategy_decision", "combined_decision", "auto_applied", "effective_from_task"}
        if not required.issubset(payload) or payload["auto_applied"] is not True:
            raise ValueError("optimization governance decision contract mismatch")
    return {"status": "valid", "artifact_id": expected_id, "artifact_kind": kind,
            "file_count": len(recorded)}
