from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.engine.artifact_store.models import StoredArtifactDescriptor
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


class CanonicalRuntimeArtifactResolutionError(RuntimeError):
    pass


def read_identity(
    store: FileSystemResearchArtifactStore, descriptor: StoredArtifactDescriptor
) -> dict[str, Any]:
    payload_file = next(
        (
            item
            for item in descriptor.files
            if item.relative_path == f"{descriptor.artifact_kind}.json"
        ),
        None,
    )
    if payload_file is None:
        raise CanonicalRuntimeArtifactResolutionError(
            f"identity payload absent for {descriptor.artifact_id}"
        )
    path = store.blobs.path_for(payload_file.sha256)
    if not store.blobs.verify(payload_file.sha256, payload_file.size_bytes):
        raise CanonicalRuntimeArtifactResolutionError(
            f"identity payload invalid for {descriptor.artifact_id}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanonicalRuntimeArtifactResolutionError(
            f"identity payload is not an object for {descriptor.artifact_id}"
        )
    return value


@dataclass(frozen=True)
class ResolvedRuntimeArtifacts:
    resolution_source: str
    app_snapshot: dict[str, Any]
    deployment_status: dict[str, Any]
    scheduler_status: dict[str, Any]
    historical_artifacts: dict[str, tuple[str, ...]]


class CanonicalRuntimeArtifactResolverV1:
    KINDS = (
        "fresh_runtime_app_snapshot",
        "fresh_runtime_deployment_status",
        "fresh_heartbeat_scheduler_status",
    )

    def __init__(
        self,
        *,
        store: FileSystemResearchArtifactStore,
        current_deployment_pointer: Path,
    ) -> None:
        self.store = store
        self.current_deployment_pointer = Path(current_deployment_pointer)

    def _descriptors(self, kind: str) -> tuple[StoredArtifactDescriptor, ...]:
        return self.store.list_by_kind(kind)

    def _by_id(self, kind: str, artifact_id: str) -> dict[str, Any]:
        descriptor = self.store.find_by_artifact_id(artifact_id)
        if descriptor is None or descriptor.artifact_kind != kind:
            raise CanonicalRuntimeArtifactResolutionError(
                f"current deployment references absent {kind}: {artifact_id}"
            )
        return read_identity(self.store, descriptor) | {"artifact_id": artifact_id}

    @staticmethod
    def _order_key(
        descriptor: StoredArtifactDescriptor, identity: dict[str, Any]
    ) -> tuple[str, int, str, str]:
        timestamp = str(
            identity.get("published_at_utc")
            or identity.get("deployed_at")
            or identity.get("created_at")
            or identity.get("last_run_at")
            or descriptor.created_at
        )
        revision = int(identity.get("revision_number", 0) or 0)
        created = str(identity.get("created_at_utc") or descriptor.created_at)
        return timestamp, revision, created, descriptor.artifact_id

    def _latest_by_revision(self, kind: str) -> dict[str, Any]:
        rows = self._descriptors(kind)
        if not rows:
            raise CanonicalRuntimeArtifactResolutionError(
                f"runtime Artifact kind is absent: {kind}"
            )
        identities = [(row, read_identity(self.store, row)) for row in rows]
        descriptor, identity = max(
            identities, key=lambda item: self._order_key(item[0], item[1])
        )
        return identity | {"artifact_id": descriptor.artifact_id}

    def resolve(self) -> ResolvedRuntimeArtifacts:
        historical = {
            kind: tuple(row.artifact_id for row in self._descriptors(kind))
            for kind in self.KINDS
        }
        if self.current_deployment_pointer.is_file():
            pointer = json.loads(
                self.current_deployment_pointer.read_text(encoding="utf-8")
            )
            required = {
                "deployment_status_id",
                "scheduler_status_id",
                "app_snapshot_id",
            }
            if not required.issubset(pointer):
                raise CanonicalRuntimeArtifactResolutionError(
                    "current deployment pointer is incomplete"
                )
            app = self._by_id(
                "fresh_runtime_app_snapshot", pointer["app_snapshot_id"]
            )
            deployment = self._by_id(
                "fresh_runtime_deployment_status",
                pointer["deployment_status_id"],
            )
            scheduler = self._by_id(
                "fresh_heartbeat_scheduler_status",
                pointer["scheduler_status_id"],
            )
            return ResolvedRuntimeArtifacts(
                "explicit_current_deployment_pointer",
                app,
                deployment,
                scheduler,
                historical,
            )
        return ResolvedRuntimeArtifacts(
            "immutable_revision_metadata",
            self._latest_by_revision("fresh_runtime_app_snapshot"),
            self._latest_by_revision("fresh_runtime_deployment_status"),
            self._latest_by_revision("fresh_heartbeat_scheduler_status"),
            historical,
        )
