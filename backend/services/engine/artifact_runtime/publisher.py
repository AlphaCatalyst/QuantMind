from __future__ import annotations

from pathlib import Path

from backend.services.engine.artifact_store.errors import ArtifactStoreError
from backend.services.engine.artifact_store.validators import DomainValidationContext

from .enums import LocalPathPurpose
from .errors import ArtifactPublicationError
from .guards import guard_local_path
from .models import ArtifactRuntimeContext, PublishedArtifact
from .reference import reference_from_descriptor


def publish_domain_artifact(
    runtime_context: ArtifactRuntimeContext,
    artifact_kind: str,
    artifact_id: str,
    local_staging_root: str | Path,
    *,
    lineage: tuple[str, ...] = (),
    validation_context: DomainValidationContext | None = None,
) -> PublishedArtifact:
    staging = guard_local_path(
        runtime_context, local_staging_root, purpose=LocalPathPurpose.STAGING
    )
    try:
        receipt = runtime_context.store.import_artifact(
            artifact_kind,
            staging,
            artifact_id,
            lineage=tuple(sorted(set(lineage))),
            validation_context=validation_context,
        )
        descriptor = runtime_context.store.get_descriptor(receipt.descriptor_id)
    except ArtifactStoreError as exc:
        raise ArtifactPublicationError("Store publication failed") from exc
    reference = reference_from_descriptor(
        descriptor,
        store_format_version=runtime_context.store.validate_format()["store_format_version"],
        inventory_id=runtime_context.inventory_id,
    )
    return PublishedArtifact(
        reference,
        receipt.exact_existing,
        receipt.new_blob_count,
        receipt.reused_blob_count,
        runtime_context.store.verify_artifact(receipt.descriptor_id),
    )
