from __future__ import annotations

import json
import errno
import os
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_json_bytes
from .errors import ArtifactDescriptorConflict, ArtifactNotFound
from .identity import descriptor_id
from .models import ArtifactFile, DomainValidation, StoredArtifactDescriptor
from .security import validate_relative_path


DESCRIPTOR_SCHEMA_VERSION = "1.0.0"
_ID = re.compile(r"^[a-z][a-z0-9]*_[A-Za-z0-9._-]+$")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_descriptor(
    *, artifact_kind: str, artifact_id: str, source_protocol: str,
    source_manifest_sha256: str, files: tuple[ArtifactFile, ...],
    lineage: tuple[str, ...], domain_validation: DomainValidation,
    created_at: str | None = None,
) -> StoredArtifactDescriptor:
    if not _ID.fullmatch(artifact_id):
        raise ArtifactDescriptorConflict("Domain Artifact ID format is invalid")
    ordered = tuple(sorted(files, key=lambda x: x.relative_path))
    if len({item.relative_path for item in ordered}) != len(ordered):
        raise ArtifactDescriptorConflict("Descriptor has duplicate paths")
    for item in ordered:
        validate_relative_path(item.relative_path)
    values = dict(
        artifact_kind=artifact_kind,
        artifact_id=artifact_id,
        source_manifest_sha256=source_manifest_sha256,
        files=ordered,
        lineage=tuple(sorted(set(lineage))),
        domain_validation=domain_validation,
    )
    did = descriptor_id(**values)
    return StoredArtifactDescriptor(
        DESCRIPTOR_SCHEMA_VERSION, did, artifact_kind, artifact_id,
        source_protocol, source_manifest_sha256, ordered,
        values["lineage"], domain_validation, len(ordered),
        sum(item.size_bytes for item in ordered), created_at or utcnow(),
    )


def descriptor_from_dict(value: dict) -> StoredArtifactDescriptor:
    required = {
        "descriptor_schema_version", "descriptor_id", "artifact_kind", "artifact_id",
        "source_protocol", "source_manifest_sha256", "files", "lineage",
        "domain_validation", "total_file_count", "total_bytes", "created_at",
    }
    if set(value) != required:
        raise ArtifactDescriptorConflict("Descriptor schema is not closed")
    files = tuple(ArtifactFile(**item) for item in value["files"])
    validation = DomainValidation(**value["domain_validation"])
    descriptor = StoredArtifactDescriptor(
        value["descriptor_schema_version"], value["descriptor_id"],
        value["artifact_kind"], value["artifact_id"], value["source_protocol"],
        value["source_manifest_sha256"], files, tuple(value["lineage"]),
        validation, value["total_file_count"], value["total_bytes"], value["created_at"],
    )
    expected = build_descriptor(
        artifact_kind=descriptor.artifact_kind,
        artifact_id=descriptor.artifact_id,
        source_protocol=descriptor.source_protocol,
        source_manifest_sha256=descriptor.source_manifest_sha256,
        files=descriptor.files,
        lineage=descriptor.lineage,
        domain_validation=descriptor.domain_validation,
        created_at=descriptor.created_at,
    )
    if descriptor != expected:
        raise ArtifactDescriptorConflict("Descriptor identity or summary mismatch")
    return descriptor


def descriptor_path(root: Path, kind: str, artifact_id: str) -> Path:
    return Path(root) / "artifacts" / kind / artifact_id / "descriptor.json"


def publish_descriptor(root: Path, descriptor: StoredArtifactDescriptor) -> bool:
    target = descriptor_path(root, descriptor.artifact_kind, descriptor.artifact_id)
    payload = canonical_json_bytes(descriptor.to_dict()) + b"\n"
    if target.exists():
        existing = descriptor_from_dict(json.loads(target.read_text(encoding="utf-8")))
        if existing.descriptor_id != descriptor.descriptor_id:
            raise ArtifactDescriptorConflict("Artifact ID already maps to different content")
        return False
    target.parent.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent.parent / f".{descriptor.artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        staged = staging / "descriptor.json"
        with staged.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.rename(staging, target.parent)
        except OSError as exc:
            if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
            if not target.exists():
                raise ArtifactDescriptorConflict("concurrent descriptor publication conflict")
            existing = descriptor_from_dict(json.loads(target.read_text(encoding="utf-8")))
            if existing.descriptor_id != descriptor.descriptor_id:
                raise ArtifactDescriptorConflict("concurrent descriptor publication conflict")
            return False
        return True
    finally:
        if staging.exists():
            for path in staging.iterdir():
                path.unlink()
            staging.rmdir()


def load_descriptor(root: Path, kind: str, artifact_id: str) -> StoredArtifactDescriptor:
    path = descriptor_path(root, kind, artifact_id)
    if not path.is_file():
        raise ArtifactNotFound("Stored Artifact Descriptor does not exist")
    try:
        return descriptor_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, ArtifactDescriptorConflict):
            raise
        raise ArtifactDescriptorConflict("Stored Artifact Descriptor is invalid") from exc
