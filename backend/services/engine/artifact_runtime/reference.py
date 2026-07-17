from __future__ import annotations

from backend.services.engine.artifact_store.canonical import hash_payload
from backend.services.engine.artifact_store.models import StoredArtifactDescriptor

from .models import StoreBackedArtifactRef


def reference_from_descriptor(
    descriptor: StoredArtifactDescriptor,
    *,
    store_format_version: str = "1.0.0",
    inventory_id: str | None = None,
) -> StoreBackedArtifactRef:
    identity = {
        "artifact_kind": descriptor.artifact_kind,
        "artifact_id": descriptor.artifact_id,
        "descriptor_id": descriptor.descriptor_id,
        "store_format_version": store_format_version,
        "domain_validator": descriptor.domain_validation.validator,
        "lineage_summary": list(descriptor.lineage),
        "inventory_id": inventory_id,
    }
    return StoreBackedArtifactRef(
        reference_id="sbar_" + hash_payload(identity),
        artifact_kind=descriptor.artifact_kind,
        artifact_id=descriptor.artifact_id,
        descriptor_id=descriptor.descriptor_id,
        store_format_version=store_format_version,
        domain_validator=descriptor.domain_validation.validator,
        lineage_summary=descriptor.lineage,
        inventory_id=inventory_id,
    )
