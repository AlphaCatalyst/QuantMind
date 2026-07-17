from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactFile:
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str
    role: str


@dataclass(frozen=True)
class DomainValidation:
    validator: str
    validator_version: str
    status: str


@dataclass(frozen=True)
class StoredArtifactDescriptor:
    descriptor_schema_version: str
    descriptor_id: str
    artifact_kind: str
    artifact_id: str
    source_protocol: str
    source_manifest_sha256: str
    files: tuple[ArtifactFile, ...]
    lineage: tuple[str, ...]
    domain_validation: DomainValidation
    total_file_count: int
    total_bytes: int
    created_at: str
    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["files"] = [asdict(item) for item in self.files]
        value["lineage"] = list(self.lineage)
        return value


@dataclass(frozen=True)
class ArtifactImportReceipt:
    receipt_id: str
    artifact_kind: str
    artifact_id: str
    descriptor_id: str
    source_inventory_sha256: str
    file_count: int
    logical_bytes: int
    new_blob_count: int
    reused_blob_count: int
    new_blob_bytes: int
    reused_blob_bytes: int
    exact_existing: bool


@dataclass(frozen=True)
class MaterializationReceipt:
    descriptor_id: str
    artifact_id: str
    materialized_file_count: int
    materialized_bytes: int
    verified: bool


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    subject: str
    detail: str


@dataclass(frozen=True)
class IntegrityReport:
    status: str
    artifact_count: int
    blob_count: int
    issues: tuple[IntegrityIssue, ...]
    unreferenced_blobs: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ArtifactStoreInventory:
    inventory_id: str
    store_format_version: str
    artifact_count: int
    artifact_kind_counts: dict[str, int]
    descriptor_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    unique_blob_count: int
    logical_bytes: int
    unique_blob_bytes: int
    deduplicated_bytes: int
    integrity_summary: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class ResearchArtifactReachabilityPlan:
    plan_id: str
    root_ids: tuple[str, ...]
    reachable_artifact_ids: tuple[str, ...]
    missing_artifact_ids: tuple[str, ...]
    unresolved_references: tuple[str, ...]
    optional_artifact_ids: tuple[str, ...]
    created_at: str
