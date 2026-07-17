from __future__ import annotations

import os
from pathlib import Path

from backend.services.engine.artifact_store import (
    FileSystemResearchArtifactStore,
    resolve_config as resolve_store_config,
)

from .enums import ArtifactRuntimeMode
from .errors import InvalidRuntimeMode
from .models import ArtifactRuntimeContext, ArtifactRuntimePolicy


DEFAULT_CACHE_ROOT = "~/.cache/quantmind2/artifacts/v1"


def policy_for_mode(mode: ArtifactRuntimeMode | str) -> ArtifactRuntimePolicy:
    try:
        parsed = mode if isinstance(mode, ArtifactRuntimeMode) else ArtifactRuntimeMode(mode)
    except ValueError as exc:
        raise InvalidRuntimeMode("unsupported Artifact Runtime mode") from exc
    return {
        ArtifactRuntimeMode.LEGACY_LOCAL: ArtifactRuntimePolicy(parsed, True, False, False),
        ArtifactRuntimeMode.STORE_PREFERRED: ArtifactRuntimePolicy(parsed, True, True, True),
        ArtifactRuntimeMode.STORE_REQUIRED: ArtifactRuntimePolicy(parsed, False, True, False),
    }[parsed]


def resolve_runtime_context(
    *,
    explicit_mode: str | ArtifactRuntimeMode | None = None,
    explicit_store_root: str | Path | None = None,
    explicit_cache_root: str | Path | None = None,
    inventory_id: str | None = None,
) -> ArtifactRuntimeContext:
    raw_mode = explicit_mode or os.environ.get(
        "QUANTMIND_ARTIFACT_RUNTIME_MODE", ArtifactRuntimeMode.STORE_REQUIRED.value
    )
    policy = policy_for_mode(raw_mode)
    cache_raw = explicit_cache_root or os.environ.get(
        "QUANTMIND_ARTIFACT_CACHE_ROOT", DEFAULT_CACHE_ROOT
    )
    cache_root = Path(cache_raw).expanduser().resolve()
    store = FileSystemResearchArtifactStore(resolve_store_config(explicit_store_root))
    store.validate_format()
    return ArtifactRuntimeContext(policy, store, cache_root, inventory_id)
