from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .blob_store import ContentAddressedBlobStore
from .canonical import canonical_json_bytes
from .config import ArtifactStoreConfig
from .descriptor import descriptor_from_dict
from .errors import ArtifactNotFound, StoreFormatError
from .models import ArtifactImportReceipt, StoredArtifactDescriptor


FORMAT_PAYLOAD = {
    "store_format_version": "1.0.0",
    "hash_algorithm": "sha256",
    "descriptor_schema_version": "1.0.0",
    "created_by": "quantmind2-artifact-store",
}


class ResearchArtifactStore(Protocol):
    def get_descriptor(self, identity: str) -> StoredArtifactDescriptor: ...
    def find_by_artifact_id(self, artifact_id: str, *, verify: bool = True) -> StoredArtifactDescriptor | None: ...
    def list_artifacts(self) -> tuple[StoredArtifactDescriptor, ...]: ...
    def list_by_kind(self, artifact_kind: str) -> tuple[StoredArtifactDescriptor, ...]: ...
    def verify_artifact(self, identity: str) -> bool: ...
    def import_artifact(self, *args, **kwargs) -> ArtifactImportReceipt: ...
    def materialize_artifact(self, *args, **kwargs): ...


class FileSystemResearchArtifactStore:
    def __init__(self, config: ArtifactStoreConfig) -> None:
        self.config = config
        self.root = config.root
        self.blobs = ContentAddressedBlobStore(self.root, fsync_on_publish=config.fsync_on_publish)

    def initialize(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("objects/sha256", "artifacts", "inventories", "receipts", "staging", "quarantine"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        path = self.root / "FORMAT.json"
        payload = canonical_json_bytes(FORMAT_PAYLOAD) + b"\n"
        if path.exists() and path.read_bytes() != payload:
            raise StoreFormatError("Artifact Store FORMAT.json conflicts with v1")
        if not path.exists():
            try:
                with path.open("xb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise StoreFormatError("Artifact Store FORMAT.json conflicts with v1")
        return dict(FORMAT_PAYLOAD)

    def validate_format(self) -> dict:
        try:
            value = json.loads((self.root / "FORMAT.json").read_text(encoding="utf-8"))
        except Exception as exc:
            raise StoreFormatError("Artifact Store FORMAT.json is unreadable") from exc
        if value != FORMAT_PAYLOAD:
            raise StoreFormatError("Artifact Store format is unsupported")
        return value

    def list_artifacts(self) -> tuple[StoredArtifactDescriptor, ...]:
        self.validate_format()
        descriptors = []
        for path in sorted((self.root / "artifacts").glob("*/*/descriptor.json")):
            if path.parent.name.startswith("."):
                continue
            descriptors.append(descriptor_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return tuple(descriptors)

    def find_by_artifact_id(self, artifact_id: str, *, verify: bool = True) -> StoredArtifactDescriptor | None:
        matches = [item for item in self.list_artifacts() if item.artifact_id == artifact_id]
        if len(matches) > 1:
            raise StoreFormatError("Artifact ID is not unique")
        if not matches:
            return None
        if verify:
            self.verify_artifact(matches[0].descriptor_id)
        return matches[0]

    def get_descriptor(self, identity: str) -> StoredArtifactDescriptor:
        matches = [item for item in self.list_artifacts()
                   if item.descriptor_id == identity or item.artifact_id == identity]
        if len(matches) != 1:
            raise ArtifactNotFound("Artifact descriptor identity is absent or ambiguous")
        descriptor = matches[0]
        if self.config.verify_on_read:
            self.verify_artifact(descriptor.descriptor_id)
        return descriptor

    def list_by_kind(self, artifact_kind: str) -> tuple[StoredArtifactDescriptor, ...]:
        return tuple(item for item in self.list_artifacts() if item.artifact_kind == artifact_kind)

    def verify_artifact(self, identity: str) -> bool:
        descriptors = self.list_artifacts()
        matches = [item for item in descriptors if item.descriptor_id == identity or item.artifact_id == identity]
        if len(matches) != 1:
            raise ArtifactNotFound("Artifact descriptor identity is absent or ambiguous")
        for item in matches[0].files:
            if not self.blobs.verify(item.sha256, item.size_bytes):
                return False
        return True

    def publish_receipt(self, receipt: ArtifactImportReceipt) -> None:
        path = self.root / "receipts" / f"{receipt.receipt_id}.json"
        payload = canonical_json_bytes(asdict(receipt)) + b"\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != payload:
            raise StoreFormatError("immutable Receipt ID conflict")
        if not path.exists():
            try:
                with path.open("xb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError:
                for attempt in range(20):
                    if path.read_bytes() == payload:
                        break
                    if attempt == 19:
                        raise StoreFormatError("immutable Receipt ID conflict")
                    time.sleep(0.005)

    def import_artifact(self, *args, **kwargs):
        from .importer import import_artifact
        return import_artifact(self, *args, **kwargs)

    def materialize_artifact(self, *args, **kwargs):
        from .materializer import materialize_artifact
        return materialize_artifact(self, *args, **kwargs)
