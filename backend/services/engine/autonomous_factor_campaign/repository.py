from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore

from .artifact import publish_artifact, validate_artifact


class CampaignRepository:
    def __init__(self, store: FileSystemResearchArtifactStore, domain_root: Path, recovery_root: Path):
        self.store = store
        self.domain_root = Path(domain_root)
        self.recovery_root = Path(recovery_root)

    def publish(self, kind: str, identity: dict, files: dict[str, Any], lineage=()) -> dict:
        artifact = publish_artifact(self.domain_root, kind, identity, files)
        field = next(key for key in artifact if key.endswith("_id") and key != "schema_version")
        artifact_id = artifact[field]
        receipt = self.store.import_artifact(
            kind, Path(artifact["path"]), artifact_id, lineage=tuple(item for item in lineage if item)
        )
        return {
            "artifact_kind": kind, "artifact_id": artifact_id,
            "descriptor_id": receipt.descriptor_id, "exact_existing": receipt.exact_existing,
            "new_blob_count": receipt.new_blob_count,
        }

    def identity(self, artifact_id: str) -> dict:
        descriptor = self.store.find_by_artifact_id(artifact_id)
        if descriptor is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        target = self.recovery_root / descriptor.artifact_kind / artifact_id
        if target.exists():
            shutil.rmtree(target)
        self.store.materialize_artifact(descriptor.descriptor_id, target)
        validate_artifact(target, artifact_id, descriptor.artifact_kind)
        return json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]

    def materialize(self, artifact_id: str) -> Path:
        descriptor = self.store.find_by_artifact_id(artifact_id)
        if descriptor is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        target = self.recovery_root / descriptor.artifact_kind / artifact_id
        if target.exists():
            shutil.rmtree(target)
        self.store.materialize_artifact(descriptor.descriptor_id, target)
        validate_artifact(target, artifact_id, descriptor.artifact_kind)
        return target

    def find_spec(self, campaign_spec_id: str) -> dict:
        descriptor = self.store.find_by_artifact_id(campaign_spec_id)
        if descriptor is None or descriptor.artifact_kind != "autonomous_factor_campaign_spec":
            raise ValueError("Autonomous Campaign Spec is absent")
        return self.identity(campaign_spec_id) | {"campaign_spec_id": campaign_spec_id}

    def latest_state(self, campaign_spec_id: str) -> dict | None:
        rows = []
        for descriptor in self.store.list_by_kind("autonomous_factor_campaign"):
            identity = self.identity(descriptor.artifact_id)
            if identity.get("campaign_spec_id") == campaign_spec_id:
                rows.append(identity)
        return max(rows, key=lambda item: (item.get("checkpoint_sequence", 0), item.get("state", "")), default=None)

    def identities_by_kind(self, kind: str, campaign_spec_id: str) -> list[dict]:
        rows = []
        for descriptor in self.store.list_by_kind(kind):
            identity = self.identity(descriptor.artifact_id)
            if identity.get("campaign_spec_id") == campaign_spec_id:
                rows.append(identity | {"artifact_id": descriptor.artifact_id})
        return rows

    def integrity(self) -> dict:
        result = scan_store_integrity(self.store)
        return {
            "status": result.status, "missing": len(result.issues),
            "unreferenced": len(result.unreferenced_blobs),
        }
