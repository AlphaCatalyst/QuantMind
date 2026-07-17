from __future__ import annotations

from dataclasses import asdict

from .canonical import hash_payload
from .models import ArtifactFile, DomainValidation


def descriptor_identity_payload(
    *, artifact_kind: str, artifact_id: str, source_manifest_sha256: str,
    files: tuple[ArtifactFile, ...], lineage: tuple[str, ...],
    domain_validation: DomainValidation,
) -> dict:
    return {
        "descriptor_schema_version": "1.0.0",
        "artifact_kind": artifact_kind,
        "artifact_id": artifact_id,
        "source_manifest_sha256": source_manifest_sha256,
        "files": [asdict(item) for item in sorted(files, key=lambda x: x.relative_path)],
        "lineage": sorted(lineage),
        "domain_validation": asdict(domain_validation),
    }


def descriptor_id(**values) -> str:
    return "sad_" + hash_payload(descriptor_identity_payload(**values))


def receipt_id(payload: dict) -> str:
    return "sar_" + hash_payload(payload)
