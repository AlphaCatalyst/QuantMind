from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from .canonical import CHUNK_SIZE, hash_file
from .errors import MaterializationError
from .models import MaterializationReceipt
from .security import validate_relative_path
from .validators import DomainValidationContext, validate_domain_artifact


def materialize_artifact(
    store,
    descriptor_id_or_artifact_id: str,
    destination: Path,
    *,
    validation_context: DomainValidationContext | None = None,
) -> MaterializationReceipt:
    descriptor = store.get_descriptor(descriptor_id_or_artifact_id)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise MaterializationError("materialization destination must not exist or must be empty")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging_container = parent / f".materialize-staging-{uuid.uuid4().hex}"
    # Preserve the Domain Artifact's conventional ``<collection>/<id>`` shape
    # while it is staged; existing validators resolve their service root from it.
    staging = staging_container / parent.name / destination.name
    staging.mkdir(parents=True)
    try:
        for item in descriptor.files:
            relative = validate_relative_path(item.relative_path)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            blob = store.blobs.path_for(item.sha256)
            if not store.blobs.verify(item.sha256, item.size_bytes):
                raise MaterializationError("referenced Blob is missing")
            with blob.open("rb") as reader, target.open("xb") as writer:
                for chunk in iter(lambda: reader.read(CHUNK_SIZE), b""):
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            if hash_file(target) != (item.sha256, item.size_bytes):
                raise MaterializationError("materialized file hash mismatch")
        validate_domain_artifact(
            descriptor.artifact_kind,
            staging,
            expected_artifact_id=descriptor.artifact_id,
            context=validation_context,
        )
        if destination.exists():
            destination.rmdir()
        os.rename(staging, destination)
        staging = None
        shutil.rmtree(staging_container)
        return MaterializationReceipt(
            descriptor.descriptor_id,
            descriptor.artifact_id,
            descriptor.total_file_count,
            descriptor.total_bytes,
            True,
        )
    finally:
        if staging_container.exists():
            shutil.rmtree(staging_container)
