import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

from .canonical import hash_payload, sha256_file, write_json
from .decisions import decision_payload
from .errors import RegistryArtifactError, RegistryMergeConflict
from .parser import entry_payload


SCHEMA_VERSION = "registry-reconciliation-v1"
MERGE_POLICY_VERSION = "registry-reconciliation-merge-v1"


@dataclass(frozen=True)
class RegistryReconciliation:
    reconciliation_id: str
    common_ancestor_snapshot_id: str
    source_snapshot_ids: Tuple[str, ...]
    source_campaign_ids: Tuple[str, ...]
    source_result_ids: Tuple[str, ...]
    entry_merge_summary: Mapping[str, int]
    decision_merge_summary: Mapping[str, int]
    duplicate_entries: Tuple[Mapping[str, str], ...]
    conflicts: Tuple[Mapping[str, str], ...]
    resulting_snapshot_id: str
    merge_policy_version: str
    artifact_path: str = ""
    exact_existing: bool = False


def merge_registry_snapshots(left, right, common_ancestor_snapshot_id):
    sources = tuple(sorted((left.registry_snapshot_id, right.registry_snapshot_id)))
    if left.registry_snapshot_id == right.registry_snapshot_id:
        raise RegistryArtifactError("Registry reconciliation requires two sibling snapshots")
    if (left.previous_registry_snapshot_id != common_ancestor_snapshot_id or
            right.previous_registry_snapshot_id != common_ancestor_snapshot_id):
        raise RegistryArtifactError("Registry snapshots are not siblings of the declared ancestor")
    if left.policy != right.policy:
        raise RegistryMergeConflict("REGISTRY_POLICY_MERGE_CONFLICT")
    entries = {}; duplicates = []
    source_entries = 0
    for snapshot in (left, right):
        for entry in snapshot.entries:
            source_entries += 1
            existing = entries.get(entry.factor_instance_id)
            if existing is None:
                entries[entry.factor_instance_id] = entry
            elif entry_payload(existing) == entry_payload(entry):
                duplicates.append({"factor_instance_id": entry.factor_instance_id,
                                   "resolution": "exact_duplicate_deduplicated"})
            else:
                raise RegistryMergeConflict(
                    f"REGISTRY_ENTRY_MERGE_CONFLICT: {entry.factor_instance_id}"
                )
    decisions = {}; decision_duplicates = 0
    for snapshot in (left, right):
        for decision in snapshot.decisions:
            existing = decisions.get(decision.decision_id)
            if existing is None:
                decisions[decision.decision_id] = decision
            elif decision_payload(existing) == decision_payload(decision):
                decision_duplicates += 1
            else:
                raise RegistryMergeConflict(
                    f"REGISTRY_DECISION_MERGE_CONFLICT: {decision.decision_id}"
                )
    entry_summary = {"source_entry_occurrences": source_entries, "result_entry_count": len(entries),
                     "exact_duplicates_deduplicated": len(duplicates), "conflict_count": 0}
    decision_summary = {"source_decision_occurrences": sum(len(x.decisions) for x in (left, right)),
                        "result_decision_count": len(decisions),
                        "exact_duplicates_deduplicated": decision_duplicates, "conflict_count": 0}
    ordered_entries = tuple(entries[key] for key in sorted(entries))
    ordered_decisions = tuple(sorted(decisions.values(), key=lambda x: (x.created_at, x.decision_id)))
    return sources, ordered_entries, ordered_decisions, tuple(duplicates), entry_summary, decision_summary


def reconciliation_payload(*, common_ancestor_snapshot_id, source_snapshot_ids,
                           source_campaign_ids, source_result_ids, entry_merge_summary,
                           decision_merge_summary, duplicate_entries, conflicts,
                           resulting_snapshot_id):
    return {"schema_version": SCHEMA_VERSION,
            "common_ancestor_snapshot_id": common_ancestor_snapshot_id,
            "source_snapshot_ids": list(sorted(source_snapshot_ids)),
            "source_campaign_ids": list(sorted(source_campaign_ids)),
            "source_result_ids": list(sorted(source_result_ids)),
            "entry_merge_summary": dict(entry_merge_summary),
            "decision_merge_summary": dict(decision_merge_summary),
            "duplicate_entries": list(duplicate_entries), "conflicts": list(conflicts),
            "resulting_snapshot_id": resulting_snapshot_id,
            "merge_policy_version": MERGE_POLICY_VERSION}


def reconciliation_id(payload):
    stable = {key: value for key, value in payload.items() if key != "reconciliation_id"}
    return "frr_" + hash_payload(stable)


def publish_reconciliation(output_root, payload):
    rid = reconciliation_id(payload); full = {**payload, "reconciliation_id": rid}
    target = Path(output_root) / "reconciliations" / rid
    if target.exists(): return validate_reconciliation(output_root, rid, exact_existing=True)
    staging = target.parent / f".{rid}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        write_json(staging / "reconciliation.json", full)
        hashes = {"reconciliation.json": sha256_file(staging / "reconciliation.json")}
        write_json(staging / "manifest.json", {"schema_version": SCHEMA_VERSION,
            "reconciliation_id": rid, "file_hashes": hashes})
        target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target); staging = None
    finally:
        if staging is not None and staging.exists(): shutil.rmtree(staging)
    return validate_reconciliation(output_root, rid)


def validate_reconciliation(output_root, rid, exact_existing=False):
    if not re.fullmatch(r"^frr_[0-9a-f]{64}$", str(rid)):
        raise RegistryArtifactError("Registry reconciliation ID is invalid")
    root = Path(output_root) / "reconciliations" / rid
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        payload = json.loads((root / "reconciliation.json").read_text())
    except Exception as exc:
        raise RegistryArtifactError("Registry reconciliation is unreadable") from exc
    if (manifest != {"schema_version": SCHEMA_VERSION, "reconciliation_id": rid,
                     "file_hashes": {"reconciliation.json": sha256_file(root / "reconciliation.json")}} or
            payload.get("schema_version") != SCHEMA_VERSION or payload.get("reconciliation_id") != rid or
            reconciliation_id(payload) != rid or
            payload.get("source_snapshot_ids") != sorted(payload.get("source_snapshot_ids", ())) or
            len(payload.get("source_snapshot_ids", ())) != 2):
        raise RegistryArtifactError("Registry reconciliation identity or lineage is invalid")
    return RegistryReconciliation(rid, payload["common_ancestor_snapshot_id"],
        tuple(payload["source_snapshot_ids"]), tuple(payload["source_campaign_ids"]),
        tuple(payload["source_result_ids"]), payload["entry_merge_summary"],
        payload["decision_merge_summary"], tuple(payload["duplicate_entries"]),
        tuple(payload["conflicts"]), payload["resulting_snapshot_id"],
        payload["merge_policy_version"], str(root), exact_existing)


__all__ = ["MERGE_POLICY_VERSION", "RegistryReconciliation", "merge_registry_snapshots",
           "publish_reconciliation", "reconciliation_id", "reconciliation_payload",
           "validate_reconciliation"]
