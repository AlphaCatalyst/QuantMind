from __future__ import annotations

from pathlib import Path

from backend.services.engine.artifact_store.errors import ArtifactStoreError
from backend.services.engine.artifact_store.validators import (
    DomainValidationContext,
    validate_domain_artifact,
)

from .cache import (
    collection_destination,
    descriptor_lock,
    discard_cached_copy,
    domain_service_root,
    validate_cached_copy,
    write_cache_record,
)
from .errors import ArtifactReferenceMismatch, ArtifactResolutionError
from .models import ArtifactRuntimeContext, ResolvedArtifact, StoreBackedArtifactRef
from .reference import reference_from_descriptor


def _assert_reference(
    expected: StoreBackedArtifactRef,
    provided: StoreBackedArtifactRef | None,
) -> None:
    if provided is not None and provided != expected:
        raise ArtifactReferenceMismatch(
            "Store-backed reference differs from the verified Store descriptor"
        )


def _validation_context(
    context: ArtifactRuntimeContext,
    artifact_kind: str,
    lineage: tuple[str, ...],
    stack: tuple[str, ...],
) -> DomainValidationContext:
    if artifact_kind not in {"factor_values", "factor_optimization"}:
        return DomainValidationContext()
    snapshot = next((item for item in lineage if item.startswith("ds_")), None)
    if snapshot is None:
        raise ArtifactResolutionError("Artifact lineage lacks Dataset Snapshot")
    snapshot_resolved = resolve_artifact(
        context, "dataset_snapshot", snapshot, _stack=stack
    )
    snapshot_root = domain_service_root(
        snapshot_resolved.materialized_root, "dataset_snapshot"
    )
    if artifact_kind == "factor_values":
        return DomainValidationContext(snapshot_root=snapshot_root)
    for values_id in sorted(item for item in lineage if item.startswith("fv_")):
        resolve_artifact(context, "factor_values", values_id, _stack=stack)
    factor_values_root = context.cache_root / "collections" / "factor-values"
    return DomainValidationContext(snapshot_root, factor_values_root)


def resolve_artifact(
    runtime_context: ArtifactRuntimeContext,
    artifact_kind: str,
    artifact_id: str,
    *,
    reference: StoreBackedArtifactRef | None = None,
    _stack: tuple[str, ...] = (),
) -> ResolvedArtifact:
    if artifact_id in _stack:
        raise ArtifactResolutionError("Artifact lineage contains a cycle")
    try:
        descriptor = runtime_context.store.find_by_artifact_id(artifact_id)
    except ArtifactStoreError as exc:
        raise ArtifactResolutionError("Store descriptor lookup failed") from exc
    if descriptor is None:
        raise ArtifactResolutionError("Store Artifact is missing; recomputation is forbidden")
    if descriptor.artifact_kind != artifact_kind:
        raise ArtifactReferenceMismatch("Artifact kind differs from Store descriptor")
    expected_reference = reference_from_descriptor(
        descriptor,
        store_format_version=runtime_context.store.validate_format()["store_format_version"],
        inventory_id=runtime_context.inventory_id,
    )
    _assert_reference(expected_reference, reference)
    destination = collection_destination(
        runtime_context.cache_root, artifact_kind, artifact_id
    )
    stack = (*_stack, artifact_id)
    validation_context = _validation_context(
        runtime_context, artifact_kind, descriptor.lineage, stack
    )
    lock = descriptor_lock(descriptor.descriptor_id)
    with lock:
        cache_hit = validate_cached_copy(
            runtime_context.cache_root, descriptor, destination
        )
        if not cache_hit:
            discard_cached_copy(runtime_context.cache_root, descriptor, destination)
            try:
                receipt = runtime_context.store.materialize_artifact(
                    descriptor.descriptor_id,
                    destination,
                    validation_context=validation_context,
                )
            except ArtifactStoreError as exc:
                raise ArtifactResolutionError("verified Store materialization failed") from exc
            if not receipt.verified:
                raise ArtifactResolutionError("Store materialization was not verified")
            write_cache_record(runtime_context.cache_root, descriptor, destination)
        try:
            domain = validate_domain_artifact(
                artifact_kind,
                destination,
                expected_artifact_id=artifact_id,
                context=validation_context,
            )
        except ArtifactStoreError as exc:
            discard_cached_copy(runtime_context.cache_root, descriptor, destination)
            raise ArtifactResolutionError("cached Domain validation failed") from exc
    return ResolvedArtifact(
        expected_reference,
        destination,
        cache_hit,
        True,
        {
            "validator": domain.validation.validator,
            "validator_version": domain.validation.validator_version,
            "status": domain.validation.status,
        },
    )


def resolve_or_import_artifact(
    runtime_context: ArtifactRuntimeContext,
    artifact_kind: str,
    artifact_id: str,
    *,
    local_artifact_root: str | Path | None = None,
    lineage: tuple[str, ...] = (),
    validation_context: DomainValidationContext | None = None,
) -> ResolvedArtifact:
    try:
        return resolve_artifact(runtime_context, artifact_kind, artifact_id)
    except ArtifactResolutionError:
        if not runtime_context.policy.allow_store_miss_local_import or local_artifact_root is None:
            raise
    from .enums import LocalPathPurpose
    from .guards import guard_local_path
    from .publisher import publish_domain_artifact
    local = guard_local_path(
        runtime_context, local_artifact_root, purpose=LocalPathPurpose.LEGACY_INPUT
    )
    publish_domain_artifact(
        runtime_context, artifact_kind, artifact_id, local,
        lineage=lineage, validation_context=validation_context,
    )
    return resolve_artifact(runtime_context, artifact_kind, artifact_id)
