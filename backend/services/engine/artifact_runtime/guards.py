from __future__ import annotations

from pathlib import Path

from .enums import ArtifactRuntimeMode, LocalPathPurpose
from .errors import LegacyArtifactPathForbidden
from .models import ArtifactRuntimeContext


def guard_local_path(
    context: ArtifactRuntimeContext,
    path: str | Path,
    *,
    purpose: LocalPathPurpose,
) -> Path:
    resolved = Path(path).expanduser().resolve()
    if (
        context.policy.mode is ArtifactRuntimeMode.STORE_REQUIRED
        and purpose is LocalPathPurpose.LEGACY_INPUT
    ):
        raise LegacyArtifactPathForbidden(
            "store_required forbids local Artifact inputs; use an Artifact ID or reference"
        )
    if purpose is LocalPathPurpose.CACHE:
        try:
            resolved.relative_to(context.cache_root)
        except ValueError as exc:
            raise LegacyArtifactPathForbidden("cache path is outside configured cache root") from exc
    return resolved
