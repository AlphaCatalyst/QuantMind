import json
import os
import shutil
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .canonical import hash_payload, sha256_file, write_json
from .decisions import decision_payload, status_after_decision
from .errors import RegistryArtifactError, RegistryDecisionError
from .models import RegistrySnapshot
from .parser import decision_from_payload, entry_payload, parse_entry, policy_from_payload
from .policy import policy_payload, validate_policy


SNAPSHOT_SCHEMA_VERSION = "factor-registry-snapshot-v1"


def stable_snapshot_payload(policy, entries, decisions, previous_registry_snapshot_id):
    return {"schema_version": SNAPSHOT_SCHEMA_VERSION, "policy": policy_payload(policy),
        "entries": [entry_payload(item) for item in sorted(entries, key=lambda x: x.factor_instance_id)],
        "decisions": [decision_payload(item) for item in sorted(decisions, key=lambda x: (x.created_at, x.decision_id))],
        "previous_registry_snapshot_id": previous_registry_snapshot_id}


def registry_snapshot_id(policy, entries, decisions=(), previous_registry_snapshot_id=None):
    return "frs_" + hash_payload(stable_snapshot_payload(policy, entries, decisions, previous_registry_snapshot_id))


def _index_payload(snapshot_id, policy, entries, decisions):
    counts = Counter(item.status.value for item in entries)
    families = Counter(item.family_id for item in entries)
    return {"registry_snapshot_id": snapshot_id, "policy_id": policy.policy_id, "entry_count": len(entries),
        "status_counts": dict(sorted(counts.items())), "family_counts": dict(sorted(families.items())),
        "promotion_candidate_ids": [x.factor_instance_id for x in entries if x.status.value == "promotion_candidate"],
        "approved_ids": [x.factor_instance_id for x in entries if x.status.value == "approved"],
        "active_ids": [x.factor_instance_id for x in entries if x.status.value == "active"],
        "decision_ids": [x.decision_id for x in decisions]}


def publish_snapshot(output_root, policy, entries, decisions=(), previous_registry_snapshot_id=None):
    validate_policy(policy); entries = tuple(sorted(entries, key=lambda x: x.factor_instance_id))
    decisions = tuple(sorted(decisions, key=lambda x: (x.created_at, x.decision_id)))
    snapshot_id = registry_snapshot_id(policy, entries, decisions, previous_registry_snapshot_id)
    root = Path(output_root); target = root / "snapshots" / snapshot_id
    if target.exists():
        return validate_registry_snapshot(output_root, snapshot_id, exact_existing=True)
    staging = root / "snapshots" / f".{snapshot_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True); (staging / "entries").mkdir(); (staging / "decisions").mkdir()
    try:
        write_json(staging / "policy.json", policy_payload(policy))
        for entry in entries: write_json(staging / "entries" / f"{entry.factor_instance_id}.json", entry_payload(entry))
        for decision in decisions: write_json(staging / "decisions" / f"{decision.decision_id}.json", decision_payload(decision))
        write_json(staging / "index.json", _index_payload(snapshot_id, policy, entries, decisions))
        files = sorted(p for p in staging.rglob("*.json") if p.name != "manifest.json")
        hashes = {p.relative_to(staging).as_posix(): sha256_file(p) for p in files}
        write_json(staging / "manifest.json", {"schema_version": SNAPSHOT_SCHEMA_VERSION,
            "registry_snapshot_id": snapshot_id, "policy_id": policy.policy_id,
            "previous_registry_snapshot_id": previous_registry_snapshot_id, "entry_count": len(entries),
            "decision_count": len(decisions), "file_hashes": hashes,
            "created_at": datetime.now(timezone.utc).isoformat()})
        target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target); staging = None
    finally:
        if staging is not None and staging.exists(): shutil.rmtree(staging)
    return validate_registry_snapshot(output_root, snapshot_id)


def validate_registry_snapshot(output_root, snapshot_id, exact_existing=False):
    root = Path(output_root) / "snapshots" / snapshot_id
    try: manifest = json.loads((root / "manifest.json").read_text()); policy = policy_from_payload(json.loads((root / "policy.json").read_text()))
    except Exception as exc: raise RegistryArtifactError("Registry Snapshot is unreadable") from exc
    if manifest.get("registry_snapshot_id") != snapshot_id or manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise RegistryArtifactError("Registry Snapshot identity/schema mismatch")
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob("*.json") if p.name != "manifest.json"}
    if actual_files != set(manifest.get("file_hashes", {})): raise RegistryArtifactError("Registry file inventory mismatch")
    for relative, digest in manifest["file_hashes"].items():
        if sha256_file(root / relative) != digest: raise RegistryArtifactError("Registry file hash mismatch")
    entries = tuple(parse_entry(json.loads(p.read_text())) for p in sorted((root / "entries").glob("*.json")))
    decisions = tuple(sorted(
        (decision_from_payload(json.loads(p.read_text())) for p in (root / "decisions").glob("*.json")),
        key=lambda item: (item.created_at, item.decision_id),
    ))
    expected = registry_snapshot_id(policy, entries, decisions, manifest["previous_registry_snapshot_id"])
    if expected != snapshot_id or len(entries) != manifest["entry_count"] or len(decisions) != manifest["decision_count"]:
        raise RegistryArtifactError("Registry canonical identity/count mismatch")
    if json.loads((root / "index.json").read_text()) != _index_payload(snapshot_id, policy, entries, decisions):
        raise RegistryArtifactError("Registry index mismatch")
    return RegistrySnapshot(snapshot_id, policy, entries, decisions, manifest["previous_registry_snapshot_id"], str(root), exact_existing)


def apply_decision(snapshot, decision, output_root):
    if decision.registry_snapshot_id != snapshot.registry_snapshot_id or decision.policy_id != snapshot.policy.policy_id:
        raise RegistryDecisionError("stale Registry Snapshot or Policy reference")
    entries = list(snapshot.entries); index = next((i for i,x in enumerate(entries) if x.factor_instance_id == decision.factor_instance_id), None)
    if index is None: raise RegistryDecisionError("Decision Factor Instance is absent")
    entries[index] = status_after_decision(entries[index], decision)
    return publish_snapshot(output_root, snapshot.policy, entries, (*snapshot.decisions, decision), snapshot.registry_snapshot_id)
