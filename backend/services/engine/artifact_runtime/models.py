from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.artifact_store import FileSystemResearchArtifactStore

from .enums import ArtifactRuntimeMode


@dataclass(frozen=True)
class ArtifactRuntimePolicy:
    mode: ArtifactRuntimeMode
    allow_legacy_read: bool
    require_store_publication: bool
    allow_store_miss_local_import: bool


@dataclass
class ArtifactRuntimeEvidence:
    """Non-identity operational counters for one Runtime invocation."""

    store_descriptor_reads: int = 0
    store_miss_count: int = 0
    cold_materializations: int = 0
    warm_cache_hits: int = 0
    published_artifacts: int = 0
    published_blobs: int = 0
    reused_blobs: int = 0

    def safe_summary(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "runtime_mode": "store_required",
            "legacy_path_inputs": 0,
            "legacy_fallback_used": False,
        }


@dataclass(frozen=True)
class StoreBackedArtifactRef:
    reference_id: str
    artifact_kind: str
    artifact_id: str
    descriptor_id: str
    store_format_version: str
    domain_validator: str
    lineage_summary: tuple[str, ...]
    inventory_id: str | None = None

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_kind": self.artifact_kind,
            "artifact_id": self.artifact_id,
            "descriptor_id": self.descriptor_id,
            "store_format_version": self.store_format_version,
            "domain_validator": self.domain_validator,
            "lineage_summary": list(self.lineage_summary),
            "inventory_id": self.inventory_id,
        }


@dataclass(frozen=True)
class ArtifactRuntimeContext:
    policy: ArtifactRuntimePolicy
    store: FileSystemResearchArtifactStore
    cache_root: Path
    inventory_id: str | None = None
    evidence: ArtifactRuntimeEvidence = field(default_factory=ArtifactRuntimeEvidence)


@dataclass(frozen=True)
class ResolvedArtifact:
    reference: StoreBackedArtifactRef
    materialized_root: Path
    cache_hit: bool
    verified: bool
    domain_validation_summary: Mapping[str, str]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference.reference_id,
            "artifact_kind": self.reference.artifact_kind,
            "artifact_id": self.reference.artifact_id,
            "descriptor_id": self.reference.descriptor_id,
            "cache_hit": self.cache_hit,
            "verified": self.verified,
            "domain_validation": dict(self.domain_validation_summary),
        }


@dataclass(frozen=True)
class PublishedArtifact:
    reference: StoreBackedArtifactRef
    exact_existing: bool
    new_blob_count: int
    reused_blob_count: int
    verified: bool

    def safe_summary(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference.reference_id,
            "artifact_kind": self.reference.artifact_kind,
            "artifact_id": self.reference.artifact_id,
            "descriptor_id": self.reference.descriptor_id,
            "exact_existing": self.exact_existing,
            "new_blob_count": self.new_blob_count,
            "reused_blob_count": self.reused_blob_count,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class ExactReplayResult:
    resolved: ResolvedArtifact
    exact_existing: bool = True
    agent_calls: int = 0
    optimization_calls: int = 0
    registry_writes: int = 0

    def safe_summary(self) -> dict[str, Any]:
        return {
            **self.resolved.safe_summary(),
            "exact_existing": self.exact_existing,
            "agent_calls": self.agent_calls,
            "optimization_calls": self.optimization_calls,
            "registry_writes": self.registry_writes,
        }


@dataclass(frozen=True)
class RecoveredResearchState:
    canonical_registry_id: str
    registry_entry_count: int
    campaign_ids: tuple[str, ...]
    optimization_study_ids: tuple[str, ...]
    validation_result_id: str
    frozen_result_id: str
    fresh_admission_result_id: str
    candidate_lock_id: str
    fresh_protocol_id: str
    exposure_ledger_id: str
    watermark_id: str
    fresh_status: str
    fresh_eligible_date_count: int
    promotion_candidate_count: int
    approved_count: int
    active_count: int

    def to_dict(self) -> dict[str, Any]:
        value = dict(self.__dict__)
        value["campaign_ids"] = list(self.campaign_ids)
        value["optimization_study_ids"] = list(self.optimization_study_ids)
        return value
