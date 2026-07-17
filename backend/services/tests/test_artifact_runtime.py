from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.services.engine.artifact_runtime import (
    ArtifactReferenceMismatch,
    ArtifactResolutionError,
    ArtifactRuntimeMode,
    InvalidRuntimeMode,
    LegacyArtifactPathForbidden,
    LocalPathPurpose,
    StoreBackedArtifactRef,
    guard_local_path,
    policy_for_mode,
    publish_domain_artifact,
    reference_from_descriptor,
    resolve_artifact,
    resolve_or_import_artifact,
    resolve_runtime_context,
)
from backend.services.engine.artifact_runtime.errors import ArtifactPublicationError
from backend.services.engine.artifact_runtime.cli import safe_error_payload
from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, artifact_id: str, content: str = "payload") -> Path:
    root.mkdir(parents=True)
    payload = root / "payload.txt"
    payload.write_text(content, encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": "generic-research-v1",
        "snapshot_id": artifact_id,
        "file_hashes": {"payload.txt": _sha(payload)},
    }), encoding="utf-8")
    return root


def _context(tmp_path: Path, *, mode="store_required"):
    store_root = tmp_path / "store"
    store = FileSystemResearchArtifactStore(resolve_config(store_root))
    store.initialize()
    return resolve_runtime_context(
        explicit_mode=mode,
        explicit_store_root=store_root,
        explicit_cache_root=tmp_path / "cache",
    )


def _publish_fixture(context, tmp_path: Path, artifact_id="bundle_alpha", content="payload"):
    source = _source(tmp_path / f"source-{content}", artifact_id, content)
    return publish_domain_artifact(
        context, "generic_research_bundle", artifact_id, source
    )


def test_runtime_policy_defaults_environment_and_invalid_mode(monkeypatch, tmp_path):
    context = _context(tmp_path)
    assert context.policy.mode is ArtifactRuntimeMode.STORE_REQUIRED
    assert not context.policy.allow_legacy_read
    assert policy_for_mode("legacy_local").allow_legacy_read
    assert policy_for_mode("store_preferred").allow_store_miss_local_import
    monkeypatch.setenv("QUANTMIND_ARTIFACT_RUNTIME_MODE", "store_preferred")
    selected = resolve_runtime_context(
        explicit_store_root=context.store.root,
        explicit_cache_root=tmp_path / "other-cache",
    )
    assert selected.policy.mode is ArtifactRuntimeMode.STORE_PREFERRED
    explicit = resolve_runtime_context(
        explicit_mode="legacy_local", explicit_store_root=context.store.root,
        explicit_cache_root=tmp_path / "third-cache",
    )
    assert explicit.policy.mode is ArtifactRuntimeMode.LEGACY_LOCAL
    with pytest.raises(InvalidRuntimeMode):
        policy_for_mode("unsafe_fallback")


def test_reference_is_deterministic_and_contains_no_physical_path(tmp_path):
    context = _context(tmp_path)
    published = _publish_fixture(context, tmp_path)
    descriptor = context.store.get_descriptor(published.reference.descriptor_id)
    first = reference_from_descriptor(descriptor)
    second = reference_from_descriptor(descriptor)
    assert first == second
    assert first.reference_id.startswith("sbar_")
    rendered = json.dumps(first.identity_payload())
    assert str(tmp_path) not in rendered and "/tmp/" not in rendered


def test_legacy_guard_is_origin_aware(tmp_path):
    context = _context(tmp_path)
    with pytest.raises(LegacyArtifactPathForbidden) as raised:
        guard_local_path(context, "/private/tmp/qm2-old", purpose=LocalPathPurpose.LEGACY_INPUT)
    assert raised.value.code == "LEGACY_ARTIFACT_PATH_FORBIDDEN"
    cache = context.cache_root / "safe"
    assert guard_local_path(context, cache, purpose=LocalPathPurpose.CACHE) == cache.resolve()
    assert guard_local_path(context, tmp_path / "stage", purpose=LocalPathPurpose.STAGING)
    assert guard_local_path(context, tmp_path / "control.json", purpose=LocalPathPurpose.GIT_CONTROL)
    legacy = _context(tmp_path / "legacy", mode="legacy_local")
    assert guard_local_path(legacy, "/private/tmp/qm2-old", purpose=LocalPathPurpose.LEGACY_INPUT)


def test_resolver_cold_warm_corrupt_concurrent_and_mismatch(tmp_path):
    context = _context(tmp_path)
    published = _publish_fixture(context, tmp_path)
    cold = resolve_artifact(context, "generic_research_bundle", "bundle_alpha")
    assert cold.verified and not cold.cache_hit
    warm = resolve_artifact(context, "generic_research_bundle", "bundle_alpha")
    assert warm.cache_hit and warm.materialized_root == cold.materialized_root
    (warm.materialized_root / "payload.txt").write_text("corrupt", encoding="utf-8")
    repaired = resolve_artifact(context, "generic_research_bundle", "bundle_alpha")
    assert not repaired.cache_hit and (repaired.materialized_root / "payload.txt").read_text() == "payload"
    with ThreadPoolExecutor(max_workers=4) as executor:
        values = list(executor.map(
            lambda _: resolve_artifact(context, "generic_research_bundle", "bundle_alpha"),
            range(8),
        ))
    assert all(item.verified and item.materialized_root == cold.materialized_root for item in values)
    with pytest.raises(ArtifactReferenceMismatch):
        resolve_artifact(context, "factor_registry", "bundle_alpha")
    bad = StoreBackedArtifactRef(
        "sbar_" + "0" * 64, "generic_research_bundle", "bundle_alpha",
        published.reference.descriptor_id, "1.0.0", "wrong", (), None,
    )
    with pytest.raises(ArtifactReferenceMismatch):
        resolve_artifact(context, "generic_research_bundle", "bundle_alpha", reference=bad)
    with pytest.raises(ArtifactResolutionError, match="recomputation is forbidden"):
        resolve_artifact(context, "generic_research_bundle", "bundle_missing")


def test_publisher_new_exact_existing_conflict_and_no_duplicate_blob(tmp_path):
    context = _context(tmp_path)
    first = _publish_fixture(context, tmp_path)
    assert not first.exact_existing and first.new_blob_count == 2
    second = publish_domain_artifact(
        context, "generic_research_bundle", "bundle_alpha",
        tmp_path / "source-payload",
    )
    assert second.exact_existing and second.new_blob_count == 0
    assert second.reference == first.reference
    assert context.store.verify_artifact(first.reference.descriptor_id)
    conflicting = _source(tmp_path / "conflicting", "bundle_alpha", "different")
    with pytest.raises(ArtifactPublicationError):
        publish_domain_artifact(
            context, "generic_research_bundle", "bundle_alpha", conflicting
        )
    invalid = tmp_path / "invalid"; invalid.mkdir(); (invalid / "payload.txt").write_text("x")
    with pytest.raises(ArtifactPublicationError):
        publish_domain_artifact(context, "generic_research_bundle", "bundle_invalid", invalid)


def test_store_preferred_imports_once_but_store_required_never_falls_back(tmp_path):
    preferred = _context(tmp_path, mode="store_preferred")
    source = _source(tmp_path / "preferred-source", "bundle_preferred")
    resolved = resolve_or_import_artifact(
        preferred, "generic_research_bundle", "bundle_preferred",
        local_artifact_root=source,
    )
    assert resolved.verified and preferred.store.find_by_artifact_id("bundle_preferred")
    required = resolve_runtime_context(
        explicit_mode="store_required", explicit_store_root=preferred.store.root,
        explicit_cache_root=tmp_path / "required-cache",
    )
    missing = _source(tmp_path / "required-source", "bundle_required")
    with pytest.raises(ArtifactResolutionError):
        resolve_or_import_artifact(
            required, "generic_research_bundle", "bundle_required",
            local_artifact_root=missing,
        )


def test_cli_error_payload_never_echoes_unknown_physical_path():
    payload = safe_error_payload(OSError("failed at /private/tmp/secret-source"))
    rendered = json.dumps(payload)
    assert "/private/tmp" not in rendered
    assert payload["status"] == "error"
