from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.momentum_factor_iteration.artifact import validate_artifact
from backend.services.engine.momentum_factor_iteration.engine import replay_experiment


pytestmark = pytest.mark.skipif(
    os.environ.get("QUANTMIND2_RUN_REAL_MOMENTUM_TESTS") != "1",
    reason="requires the local immutable Tushare research Artifact Store",
)

EXPERIMENT_ID = "mfi1_87177b7c06420e65159d3f5bdafee8149cdb3290c32f08712cd73e59a4e19dee"
CATALOG_ID = "mfc1_51dc0901c6d01ce07eec6228f881d49bb57ade13c8b6a7adb85bf14ae633b47c"


@pytest.fixture(scope="module")
def store():
    return FileSystemResearchArtifactStore(resolve_config(None))


def _materialize(store, artifact_id: str, root: Path) -> tuple[object, Path, dict]:
    descriptor = store.find_by_artifact_id(artifact_id)
    assert descriptor is not None
    target = root / artifact_id
    store.materialize_artifact(descriptor.descriptor_id, target)
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    return descriptor, target, manifest


def test_real_catalog_has_36_features_and_nine_families(store, tmp_path):
    _, root, manifest = _materialize(store, CATALOG_ID, tmp_path)
    assert validate_artifact(root, CATALOG_ID, "momentum_feature_catalog")["status"] == "valid"
    assert manifest["identity"]["feature_count"] == 36
    assert manifest["identity"]["family_count"] == 9


def test_real_canonical_experiment_supersedes_diversity_deficient_attempt(store, tmp_path):
    _, root, manifest = _materialize(store, EXPERIMENT_ID, tmp_path)
    identity = manifest["identity"]
    assert identity["contract_revision"] == 2
    assert identity["supersedes_experiment_id"] == "mfi1_cb0953420f15e3bf162e84be1cac7cd0c0794064197e65c11d430d24a985cf32"
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["round_count"] == 5
    assert len(summary["explored_families"]) == 8
    assert summary["locked_candidate_count"] == 0
    assert summary["strategy_optimization_calls"] == 0


def test_real_rounds_are_cold_recoverable_and_diverse(store, tmp_path):
    _, root, manifest = _materialize(store, EXPERIMENT_ID, tmp_path / "experiment")
    families = set()
    for round_id in manifest["identity"]["round_result_ids"]:
        descriptor, round_root, round_manifest = _materialize(store, round_id, tmp_path / "rounds")
        assert descriptor.artifact_kind == "momentum_factor_round_result"
        assert validate_artifact(round_root, round_id, descriptor.artifact_kind)["status"] == "valid"
        families.update(round_manifest["identity"]["feedback"]["theme_families"])
    assert len(families) >= 6


def test_real_store_is_healthy_without_missing_or_unreferenced_blobs(store):
    integrity = scan_store_integrity(store)
    assert integrity.status == "healthy"
    assert not integrity.issues
    assert not integrity.unreferenced_blobs


def test_real_exact_replay_is_zero_call_and_zero_write(tmp_path):
    result = replay_experiment(
        repository_root=Path(__file__).resolve().parents[3],
        work_root=tmp_path / "cold-replay",
    )
    assert result["experiment_id"] == EXPERIMENT_ID
    assert result["exact_existing"] is True
    assert result["agent_calls"] == 0
    assert result["factor_optimization_trials"] == 0
    assert result["qlib_calls"] == 0
    assert result["network_calls"] == 0
    assert result["new_artifacts"] == 0
    assert result["new_blobs"] == 0
    assert result["store_integrity"] == "healthy"
