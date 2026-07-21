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
from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


ROOT = Path(__file__).resolve().parents[3]
TARGET_RUN_ID = "QM2-R1-001-20260720T182257Z-a574580"
TARGET_BASE = "a574580a61b57c17c0215f69ae350efadbdb37be"
TARGET_COMMIT = "4de8b1e8e1f8562c0ef0a4a8d692df2fc7f3cfab"
TARGET_DIRECTORY = (
    "docs/quantmind2/implementation/runs/2026/2026-07/" + TARGET_RUN_ID
)
TARGET_MANIFEST = f"{TARGET_DIRECTORY}/manifest.json"
TARGET_REPORT = f"{TARGET_DIRECTORY}/report.md"
CORRECTION = ROOT / (
    "docs/quantmind2/implementation/corrections/"
    "QM2-R1-001-git-evidence-correction-v1.json"
)


def _git(*args: str, text: bool = False):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=text)


def _blob(commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _target_inventory() -> tuple[list[str], list[str], list[dict]]:
    changed: list[str] = []
    added: list[str] = []
    business: list[dict] = []
    for line in _git(
        "diff", "--name-status", TARGET_BASE, TARGET_COMMIT, "--", text=True
    ).splitlines():
        status, path = line.split("\t")
        changed.append(path)
        if status == "A":
            added.append(path)
        if path == TARGET_MANIFEST:
            continue
        before = _blob(TARGET_BASE, path)
        after = _blob(TARGET_COMMIT, path)
        business.append(
            {
                "path": path,
                "change_type": {"A": "added", "M": "modified", "D": "deleted"}[
                    status
                ],
                "before_sha256": None if before is None else _sha256(before),
                "after_sha256": None if after is None else _sha256(after),
            }
        )
    return sorted(changed), sorted(added), business


def test_git_evidence_correction_exactly_reconstructs_target_commit() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    changed, added, business = _target_inventory()

    assert payload["object_type"] == "GitEvidenceCorrectionV1"
    assert payload["target_task_id"] == "QM2-R1-001"
    assert payload["target_run_id"] == TARGET_RUN_ID
    assert payload["target_commit"] == TARGET_COMMIT
    assert payload["target_git_changed_paths"] == changed
    assert payload["target_git_added_paths"] == added
    assert payload["target_business_changed_files"] == business
    assert len(changed) == 26 and len(added) == 13 and len(business) == 25
    assert TARGET_MANIFEST in changed and TARGET_MANIFEST in added
    assert TARGET_MANIFEST not in {item["path"] for item in business}
    assert TARGET_REPORT in {item["path"] for item in business}

    canonical = json.dumps(
        {
            "target_git_added_paths": added,
            "target_git_changed_paths": changed,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert _sha256(canonical) == payload["verified_by_git"][
        "canonical_inventory_sha256"
    ]
    assert _sha256(_blob(TARGET_COMMIT, TARGET_MANIFEST) or b"") == payload[
        "verified_by_git"
    ]["target_manifest_sha256"]
    assert _sha256(_blob(TARGET_COMMIT, TARGET_REPORT) or b"") == payload[
        "verified_by_git"
    ]["target_report_sha256"]


def test_original_run_is_immutable_partial_and_root_cause_is_invocation() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    manifest = json.loads((_blob(TARGET_COMMIT, TARGET_MANIFEST) or b"{}").decode())
    planner = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    )
    analyzed = planner.plan(TARGET_RUN_ID).runs[0]

    assert not analyzed.validated and not analyzed.indexable
    assert analyzed.evidence.resolved_status == "completed_committed"
    assert {
        check.name
        for check in analyzed.evidence.checks
        if check.mandatory and not check.passed
    } == {"git_changed_paths", "added_files"}
    assert analyzed.domain_build is not None
    assert [gap.code for gap in analyzed.domain_build.gaps] == ["GIT_INCONSISTENT"]
    assert analyzed.evidence.warnings == ()
    assert payload["historical_target_status"] == "partial_committed"
    assert payload["resolved_ledger_status"] == "completed_corrected"
    assert payload["root_cause"] == "incorrect_run_generation_usage"
    assert TARGET_MANIFEST not in {
        item["path"] for item in manifest["changed_files"]
    }
    assert TARGET_MANIFEST not in manifest["integrity"]["git_changed_paths"]
    assert TARGET_MANIFEST not in manifest["integrity"]["git_added_paths"]


def test_path_only_self_reference_is_not_a_business_hash_reference() -> None:
    run_manifests = list(
        (ROOT / "docs/quantmind2/implementation/runs/2026/2026-07").glob(
            "QM2-R1-001F-*/manifest.json"
        )
    )
    if not run_manifests:
        pytest.skip("Correction Manifest is created after focused evidence tests")
    manifest = json.loads(run_manifests[0].read_text(encoding="utf-8"))
    manifest_path = manifest["run"]["manifest_path"]
    assert manifest_path not in {item["path"] for item in manifest["changed_files"]}
    assert manifest_path in manifest["integrity"]["git_changed_paths"]
    assert manifest_path in manifest["integrity"]["git_added_paths"]
    assert manifest["integrity"]["manifest_payload_sha256"]


def test_committed_correction_run_is_gap_free_and_indexer_admissible() -> None:
    manifests = list(
        (ROOT / "docs/quantmind2/implementation/runs/2026/2026-07").glob(
            "QM2-R1-001F-*/manifest.json"
        )
    )
    if not manifests:
        pytest.skip("Correction Run is created after focused evidence tests")
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
    bundle = analyzed.domain_build.bundle
    assert bundle is not None
    LedgerIndexer.require_indexable(
        ImplementationRunPlanner(
            GitSnapshot(bind_repository("quantmind-main", ROOT))
        ).plan(run_id)
    )
    assert len(bundle.relationships) == 1
    assert bundle.relationships[0].relationship_type.value == "corrects"
    assert bundle.relationships[0].target_run_id == TARGET_RUN_ID


def test_research_artifact_store_remains_read_only_and_healthy() -> None:
    payload = json.loads(CORRECTION.read_text(encoding="utf-8"))
    store = FileSystemResearchArtifactStore(resolve_config())
    before = (len(store.list_artifacts()), scan_store_integrity(store).blob_count)
    report = scan_store_integrity(store)
    after = (len(store.list_artifacts()), report.blob_count)

    assert before == after == (285, 2508)
    assert report.status == "healthy"
    assert report.issues == () and report.unreferenced_blobs == ()
    assert payload["research_artifact_identity"] == {
        "experiment_id": "afi2_78fe313863910ce2cd47409ac1fbe66dbedaea1bfc8815a0e09f261288d57fcf",
        "candidate_lock_id": "afcl_27fb695b24bf92a63fb8a57e55bfdb102a675935e951b12184d7b9e8f6aba51e",
        "assessment": "mixed",
        "registry_status": "research_registered",
        "promotion_candidate_count": 0,
        "agent_calls": 0,
        "factor_optimization_calls": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "promotion_writes": 0,
    }
