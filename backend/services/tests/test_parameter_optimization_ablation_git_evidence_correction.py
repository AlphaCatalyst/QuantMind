from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from backend.services.api.project_knowledge.indexing import (
    GitSnapshot,
    ImplementationRunPlanner,
    LedgerIndexer,
    bind_repository,
)
from tools.quantmind2.parameter_optimization_ablation_git_evidence_correction import (
    TARGET_COMMIT,
    TARGET_MANIFEST,
    TARGET_RUN_ID,
    build_correction,
    validate_correction,
)


ROOT = Path(__file__).resolve().parents[3]
CORRECTION = ROOT / (
    "docs/quantmind2/implementation/corrections/"
    "QM2-R1-005-git-evidence-correction-v1.json"
)


def _blob(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def test_correction_is_rebuilt_from_immutable_target_commit() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert validate_correction(payload) == payload == build_correction()
    assert payload["target_commit"] == TARGET_COMMIT
    assert payload["target_manifest_path"] == TARGET_MANIFEST
    assert TARGET_MANIFEST in payload["target_git_changed_paths"]
    assert TARGET_MANIFEST in payload["target_git_added_paths"]
    assert TARGET_MANIFEST not in {
        item["path"] for item in payload["target_changed_file_hashes"]
    }
    assert payload["verified_by_git"]["target_manifest_sha256"] == hashlib.sha256(
        _blob(TARGET_COMMIT, TARGET_MANIFEST)
    ).hexdigest()


def test_original_run_remains_immutable_and_git_inconsistent() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    analyzed = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    ).plan(TARGET_RUN_ID).runs[0]
    failures = {
        check.name
        for check in analyzed.evidence.checks
        if check.mandatory and not check.passed
    }
    assert not analyzed.validated and not analyzed.indexable
    assert failures == {"changed_file_hashes", "source_bundle_hash"}
    assert analyzed.evidence.warnings == ()
    assert payload["historical_target_task_result"] == "blocked"
    assert payload["historical_target_git_status"] == "git_inconsistent"
    assert payload["resolved_ledger_status"] == "completed_corrected"


def test_only_contract_blob_hash_and_source_bundle_require_correction() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    mismatches = payload["changed_file_hash_mismatches"]
    assert len(mismatches) == 1
    assert mismatches[0]["path"] == (
        "docs/quantmind2/contracts/"
        "PARAMETER_OPTIMIZATION_OVERFIT_ABLATION_V1.md"
    )
    assert mismatches[0]["recorded"]["after_hash"] != mismatches[0]["verified"][
        "after_hash"
    ]
    assert not payload["source_bundle_hash_matches"]
    assert payload["original_gap_codes"] == [
        "changed_file_hashes",
        "source_bundle_hash",
    ]


def test_correction_has_zero_research_execution() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert set(payload["research_execution"].values()) == {0}


def test_committed_correction_run_is_gap_free_and_indexable() -> None:
    manifests = list(
        (ROOT / "docs/quantmind2/implementation/runs/2026/2026-07").glob(
            "QM2-R1-005F-*/manifest.json"
        )
    )
    if not manifests:
        pytest.skip("Correction Manifest is created after focused evidence tests")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    run_id = manifest["run"]["implementation_run_id"]
    manifest_path = manifest["run"]["manifest_path"]
    if subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{manifest_path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    ).returncode:
        pytest.skip("Correction Run Git verification requires its containing commit")
    analyzed = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    ).plan(run_id).runs[0]
    assert analyzed.validated and analyzed.indexable
    assert analyzed.evidence.consistent and analyzed.evidence.warnings == ()
    assert analyzed.domain_build is not None and analyzed.domain_build.gaps == ()
    LedgerIndexer.require_indexable(
        ImplementationRunPlanner(
            GitSnapshot(bind_repository("quantmind-main", ROOT))
        ).plan(run_id)
    )
    relationship = analyzed.domain_build.bundle.relationships[0]
    assert relationship.relationship_type.value == "corrects"
    assert relationship.target_run_id == TARGET_RUN_ID
