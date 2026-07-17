from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import time

from .canonical import hash_payload
from .descriptor import build_descriptor, publish_descriptor
from .errors import ArtifactNotFound
from .identity import receipt_id
from .models import ArtifactImportReceipt
from .security import inspect_source
from .validators import DomainValidationContext, validate_domain_artifact


def import_artifact(
    store,
    artifact_kind: str,
    source_directory: Path,
    expected_artifact_id: str | None = None,
    *,
    lineage: tuple[str, ...] = (),
    validation_context: DomainValidationContext | None = None,
) -> ArtifactImportReceipt:
    source = Path(source_directory)
    inventory = inspect_source(
        source,
        maximum_file_count=store.config.maximum_file_count,
        maximum_artifact_bytes=store.config.maximum_artifact_bytes,
    )
    domain = validate_domain_artifact(
        artifact_kind,
        source,
        expected_artifact_id=expected_artifact_id,
        context=validation_context,
    )
    inventory_payload = [asdict(item) for item in inventory.files]
    source_inventory_sha256 = hash_payload(inventory_payload)
    descriptor = build_descriptor(
        artifact_kind=artifact_kind,
        artifact_id=domain.artifact_id,
        source_protocol=domain.source_protocol,
        source_manifest_sha256=domain.source_manifest_sha256,
        files=inventory.files,
        lineage=lineage,
        domain_validation=domain.validation,
    )
    existing = store.find_by_artifact_id(domain.artifact_id, verify=False)
    if existing is not None:
        if existing.descriptor_id != descriptor.descriptor_id:
            from .errors import ArtifactDescriptorConflict
            raise ArtifactDescriptorConflict("Artifact ID already has different inventory or lineage")
        payload = {
            "artifact_kind": artifact_kind,
            "artifact_id": domain.artifact_id,
            "descriptor_id": descriptor.descriptor_id,
            "source_inventory_sha256": source_inventory_sha256,
            "file_count": len(inventory.files),
            "logical_bytes": inventory.total_bytes,
            "new_blob_count": 0,
            "reused_blob_count": len(inventory.files),
            "new_blob_bytes": 0,
            "reused_blob_bytes": inventory.total_bytes,
            "exact_existing": True,
        }
        return ArtifactImportReceipt(receipt_id(payload), **payload)

    new_count = reused_count = new_bytes = reused_bytes = 0
    for item in inventory.files:
        created, _ = store.blobs.ingest(source / item.relative_path, item.sha256, item.size_bytes)
        if created:
            new_count += 1
            new_bytes += item.size_bytes
        else:
            reused_count += 1
            reused_bytes += item.size_bytes
    publish_descriptor(store.root, descriptor)
    # A concurrent publisher may have won the atomic directory publication;
    # wait only for that already-committed descriptor to become observable.
    for attempt in range(20):
        try:
            store.get_descriptor(descriptor.descriptor_id)
            break
        except ArtifactNotFound:
            if attempt == 19:
                raise
            time.sleep(0.005)
    payload = {
        "artifact_kind": artifact_kind,
        "artifact_id": domain.artifact_id,
        "descriptor_id": descriptor.descriptor_id,
        "source_inventory_sha256": source_inventory_sha256,
        "file_count": len(inventory.files),
        "logical_bytes": inventory.total_bytes,
        "new_blob_count": new_count,
        "reused_blob_count": reused_count,
        "new_blob_bytes": new_bytes,
        "reused_blob_bytes": reused_bytes,
        "exact_existing": False,
    }
    receipt = ArtifactImportReceipt(receipt_id(payload), **payload)
    store.publish_receipt(receipt)
    return receipt
