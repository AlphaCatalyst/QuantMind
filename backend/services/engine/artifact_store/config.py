from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .enums import ArtifactKind


DEFAULT_ROOT = "~/.quantmind2/artifact-store/v1"


@dataclass(frozen=True)
class ArtifactStoreConfig:
    root: Path
    root_resolution_source: str
    format_version: str = "1.0.0"
    hash_algorithm: str = "sha256"
    verify_on_read: bool = True
    fsync_on_publish: bool = True
    maximum_file_count: int = 100_000
    maximum_artifact_bytes: int = 1 << 40
    allowed_artifact_kinds: tuple[str, ...] = field(
        default_factory=lambda: tuple(item.value for item in ArtifactKind)
    )
    def __post_init__(self) -> None:
        if self.format_version != "1.0.0" or self.hash_algorithm != "sha256":
            raise ValueError("Artifact Store v1 format and hash algorithm are frozen")
        if not 0 < self.maximum_file_count <= 100_000:
            raise ValueError("maximum_file_count must be between 1 and 100000")
        if self.maximum_artifact_bytes <= 0:
            raise ValueError("maximum_artifact_bytes must be positive")


def resolve_config(
    explicit_root: str | Path | None = None,
    *,
    maximum_file_count: int = 100_000,
    maximum_artifact_bytes: int = 1 << 40,
) -> ArtifactStoreConfig:
    if explicit_root is not None:
        raw, source = str(explicit_root), "cli"
    elif os.environ.get("QUANTMIND_ARTIFACT_STORE_ROOT"):
        raw, source = os.environ["QUANTMIND_ARTIFACT_STORE_ROOT"], "environment"
    else:
        raw, source = DEFAULT_ROOT, "default"
    return ArtifactStoreConfig(
        root=Path(raw).expanduser().resolve(),
        root_resolution_source=source,
        maximum_file_count=maximum_file_count,
        maximum_artifact_bytes=maximum_artifact_bytes,
    )
