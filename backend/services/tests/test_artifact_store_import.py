import hashlib
import json
import os

import pytest
from concurrent.futures import ThreadPoolExecutor

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.errors import ArtifactDescriptorConflict, SourceSecurityError
from backend.services.engine.artifact_store.security import inspect_source, validate_relative_path
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


def bundle(root, artifact_id, payload=b"values"):
    root.mkdir()
    (root / "values.bin").write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": "1.0.0", "result_id": artifact_id,
        "file_hashes": {"values.bin": digest},
    }))
    return root


def store_at(path):
    value = FileSystemResearchArtifactStore(resolve_config(path))
    value.initialize()
    return value


def test_import_is_immutable_deduplicated_and_materializable(tmp_path):
    store = store_at(tmp_path / "store")
    first = bundle(tmp_path / "one", "gen_one")
    receipt = store.import_artifact("generic_research_bundle", first)
    assert receipt.exact_existing is False
    assert store.import_artifact("generic_research_bundle", first).exact_existing is True
    second = bundle(tmp_path / "two", "gen_two")
    receipt2 = store.import_artifact("generic_research_bundle", second)
    assert receipt2.reused_blob_count >= 1
    destination = tmp_path / "restored"
    result = store.materialize_artifact("gen_one", destination)
    assert result.verified and (destination / "values.bin").read_bytes() == b"values"
    with pytest.raises(Exception):
        store.materialize_artifact("gen_one", destination)
    (first / "values.bin").write_bytes(b"changed")
    with pytest.raises(Exception):
        store.import_artifact("generic_research_bundle", first)


def test_source_security_rejects_links_limits_and_paths(tmp_path):
    source = bundle(tmp_path / "source", "gen_security")
    os.symlink(source / "values.bin", source / "link")
    with pytest.raises(SourceSecurityError):
        inspect_source(source, maximum_file_count=10, maximum_artifact_bytes=10000)
    (source / "link").unlink()
    os.link(source / "values.bin", source / "hard")
    with pytest.raises(SourceSecurityError):
        inspect_source(source, maximum_file_count=10, maximum_artifact_bytes=10000)
    with pytest.raises(SourceSecurityError):
        validate_relative_path("../escape")
    with pytest.raises(SourceSecurityError):
        inspect_source(source, maximum_file_count=1, maximum_artifact_bytes=10000)


def test_concurrent_same_artifact_is_one_descriptor(tmp_path):
    store = store_at(tmp_path / "store")
    source = bundle(tmp_path / "source", "gen_concurrent")
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: store.import_artifact("generic_research_bundle", source), range(4)))
    assert len({item.descriptor_id for item in receipts}) == 1
    assert len(store.list_artifacts()) == 1
