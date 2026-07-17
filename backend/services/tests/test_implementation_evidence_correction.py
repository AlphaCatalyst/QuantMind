from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from backend.services.api.project_knowledge.indexing import (
    GitSnapshot,
    ImplementationRunPlanner,
    bind_repository,
)
from tools.quantmind2.validate_context_bootstrap import ValidationError, validate_instance


ROOT = Path(__file__).resolve().parents[3]
TARGET_RUN_ID = "QM2-P0-006-20260716T181959Z-07a3df9"
CORRECTION_RUN_ID = "QM2-P0-006F-20260717T044608Z-8ad3e22"
TARGET_BASE = "07a3df9e5809b4b87e31736e00994521af896ebf"
TARGET_CONTAINING = "8ad3e22575f9339955dd5fde4255269d87e9b138"
TARGET_PATH = "docs/quantmind2/implementation/schemas/handoff_v1.schema.json"
RECORDED_HASH = "11db9e00e1babe3ee77c18b9a38a29461c3afba33519e401b3f321eadf07ae4a"
VERIFIED_HASH = "11db9e00e1aabe3ee77c18b9a38a29461c3afba33519e401b3f321eadf07ae4a"
CORRECTION_PATH = ROOT / "docs/quantmind2/implementation/corrections/QM2-P0-006-evidence-correction-v1.json"
SCHEMA_PATH = ROOT / "docs/quantmind2/implementation/schemas/implementation_evidence_correction_v1.schema.json"
TARGET_RUN_ROOT = ROOT / "docs/quantmind2/implementation/runs/2026/2026-07" / TARGET_RUN_ID
CORRECTION_RUN_ROOT = ROOT / "docs/quantmind2/implementation/runs/2026/2026-07" / CORRECTION_RUN_ID


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=True
    ).stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_correction_schema_and_raw_base_blob_evidence() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    validate_instance(correction, schema)

    raw_blob = _git_bytes("cat-file", "blob", f"{TARGET_BASE}:{TARGET_PATH}")
    assert len(raw_blob) == correction["verified_blob_size"] == 2443
    assert hashlib.sha256(raw_blob).hexdigest() == correction["verified_value"]
    assert correction["recorded_value"] == RECORDED_HASH
    assert correction["verified_value"] == VERIFIED_HASH
    assert correction["recorded_value"] != correction["verified_value"]
    assert correction["target_run_id"] == TARGET_RUN_ID
    assert correction["target_base_commit"] == TARGET_BASE
    assert correction["target_containing_commit"] == TARGET_CONTAINING
    assert correction["path"] == TARGET_PATH
    assert correction["effect"] == "evidence_correction_only"
    assert correction["promotion_effect"] == "none"

    invalid = dict(correction)
    invalid["validation_metrics"] = {"rank_ic": 1.0}
    with pytest.raises(ValidationError, match="additional properties"):
        validate_instance(invalid, schema)


def test_target_run_and_validation_artifact_identities_are_immutable() -> None:
    correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    assert _sha256(TARGET_RUN_ROOT / "report.md") == correction["immutable_target_report_sha256"]
    assert _sha256(TARGET_RUN_ROOT / "manifest.json") == correction["immutable_target_manifest_sha256"]
    assert correction["validation_result_id"] == "fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"
    assert correction["candidate_selection_id"] == "fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c"
    assert correction["frozen_test_result_id"] == "fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"


def test_committed_correction_run_is_strict_and_target_remains_inconsistent() -> None:
    manifest_path = CORRECTION_RUN_ROOT / "manifest.json"
    relative_manifest = manifest_path.relative_to(ROOT).as_posix()
    if subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{relative_manifest}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    ).returncode:
        pytest.skip("Correction Run Git verification requires its containing commit")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relationships = manifest["relationships"]
    assert len(relationships) == 1
    assert relationships[0]["relationship_type"] == "corrects"
    assert relationships[0]["source_run_id"] == CORRECTION_RUN_ID
    assert relationships[0]["target_run_id"] == TARGET_RUN_ID
    assert all(item["relationship_type"] != "supersedes" for item in relationships)
    assert all(item["path"] != relative_manifest for item in manifest["changed_files"])

    correction_artifact = next(
        item for item in manifest["artifacts"]
        if item["artifact_type"] == "implementation_evidence_correction"
    )
    assert correction_artifact["path_or_uri"] == CORRECTION_PATH.relative_to(ROOT).as_posix()
    assert correction_artifact["content_hash"] == _sha256(CORRECTION_PATH)

    planner = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    )
    correction_run = planner.plan(CORRECTION_RUN_ID).runs[0]
    assert correction_run.validated and correction_run.indexable
    assert correction_run.evidence.consistent
    assert correction_run.evidence.warnings == ()
    assert correction_run.domain_build is not None
    assert correction_run.domain_build.gaps == ()
    assert correction_run.domain_build.bundle is not None
    assert len(correction_run.domain_build.bundle.artifacts) == 3

    target_run = planner.plan(TARGET_RUN_ID).runs[0]
    assert not target_run.validated and not target_run.indexable
    assert {
        check.name for check in target_run.evidence.checks
        if check.mandatory and not check.passed
    } == {"changed_file_hashes"}
