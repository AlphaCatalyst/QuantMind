from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone

from .canonical import canonical_json_bytes, hash_payload
from .integrity import scan_store_integrity
from .models import ArtifactStoreInventory


def publish_inventory(store) -> ArtifactStoreInventory:
    descriptors = store.list_artifacts()
    blob_sizes: dict[str, int] = {}
    logical = 0
    kinds: dict[str, int] = {}
    for descriptor in descriptors:
        kinds[descriptor.artifact_kind] = kinds.get(descriptor.artifact_kind, 0) + 1
        logical += descriptor.total_bytes
        for item in descriptor.files:
            blob_sizes[item.sha256] = item.size_bytes
    integrity = scan_store_integrity(store)
    stable = {
        "store_format_version": store.config.format_version,
        "artifact_kind_counts": dict(sorted(kinds.items())),
        "descriptor_ids": sorted(item.descriptor_id for item in descriptors),
        "artifact_ids": sorted(item.artifact_id for item in descriptors),
        "blobs": [{"sha256": key, "size_bytes": value} for key, value in sorted(blob_sizes.items())],
        "integrity_status": integrity.status,
    }
    inventory_id = "sai_" + hash_payload(stable)
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    unique = sum(blob_sizes.values())
    inventory = ArtifactStoreInventory(
        inventory_id, store.config.format_version, len(descriptors),
        stable["artifact_kind_counts"], tuple(stable["descriptor_ids"]),
        tuple(stable["artifact_ids"]), len(blob_sizes), logical, unique,
        logical - unique,
        {"status": integrity.status, "issue_count": len(integrity.issues),
         "unreferenced_blob_count": len(integrity.unreferenced_blobs)},
        created_at,
    )
    path = store.root / "inventories" / f"{inventory_id}.json"
    payload = canonical_json_bytes(asdict(inventory)) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("inventory_id") != inventory_id:
            raise RuntimeError("immutable Inventory ID conflict")
        return ArtifactStoreInventory(
            existing["inventory_id"], existing["store_format_version"], existing["artifact_count"],
            existing["artifact_kind_counts"], tuple(existing["descriptor_ids"]),
            tuple(existing["artifact_ids"]), existing["unique_blob_count"],
            existing["logical_bytes"], existing["unique_blob_bytes"],
            existing["deduplicated_bytes"], existing["integrity_summary"], existing["created_at"],
        )
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return inventory
