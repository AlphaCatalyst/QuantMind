from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from backend.services.api.project_knowledge.indexing import (
    GitSnapshot,
    ImplementationManifestParser,
    ImplementationRunPlanner,
    ManifestParseError,
    UnsupportedManifestSchemaError,
    bind_repository,
    canonical_manifest_v2_payload_hash,
    finalize_manifest_v2_payload,
    validate_manifest_v2_payload,
)
from backend.services.api.project_knowledge.indexing.domain_bundle import DomainBundleBuilder
from backend.services.api.project_knowledge.indexing.models import RepositoryBinding
from tools.quantmind2.create_implementation_manifest import new_draft
from tools.quantmind2.validate_context_bootstrap import validate_instance


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads(
    (ROOT / "docs/quantmind2/implementation/schemas/implementation_manifest_v2.schema.json").read_text()
)
EXAMPLE = json.loads(
    (ROOT / "docs/quantmind2/implementation/examples/implementation_manifest_v2.example.json").read_text()
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()


def build_v2_repository(tmp_path: Path, *, execution_path: str | None = None):  # noqa: ANN001
    root = tmp_path / "v2-repository"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "QuantMind Test")
    (root / "base.txt").write_text("base\n")
    _git(root, "add", "base.txt")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD")
    run_id = f"QM2-P0-997-20260716T010000Z-{base[:7]}"
    related_run_id = "QM2-P0-996-20260716T000000Z-7654321"
    directory = Path("docs/quantmind2/implementation/runs/2026/2026-07") / run_id
    (root / directory).mkdir(parents=True)
    source_path = "src/implementation.py"
    (root / "src").mkdir()
    source = b"def implementation():\n    return 'v2'\n"
    (root / source_path).write_bytes(source)
    report_path = (directory / "report.md").as_posix()
    manifest_path = (directory / "manifest.json").as_posix()
    report = b"# V2 Test Run\n"
    (root / report_path).write_bytes(report)
    payload = {
        "schema_version": "2.0.0",
        "mapper_contract_version": "1.0.0",
        "identity_versions": {"changed_file": "changed-file-v1", "changed_symbol": "changed-symbol-v1"},
        "repository": {
            "repository_id": "synthetic-main",
            "execution_repository_path": execution_path or "/different/machine/checkout",
            "branch": "master",
            "base_commit": base,
        },
        "task": {
            "task_id": "QM2-P0-997", "parent_task_id": None,
            "title": "Synthetic v2", "objective": "Verify v2 forward indexability.",
            "scope": ["test"], "explicit_non_goals": ["production"],
            "status": "completed", "created_at": "2026-07-16T01:00:00Z",
        },
        "run": {
            "implementation_run_id": run_id, "task_id": "QM2-P0-997",
            "repository_id": "synthetic-main", "branch": "master", "base_commit": base,
            "result_commit": None, "task_status": "completed_uncommitted",
            "completion_level": "complete", "verification_level": "integration_tests",
            "workspace_dirty_before": False, "workspace_dirty_after": True,
            "started_at": "2026-07-16T01:00:00Z", "completed_at": "2026-07-16T01:01:00Z",
            "agent_type": "codex", "manifest_schema_version": "2.0.0",
            "manifest_path": manifest_path, "report_path": report_path,
            "source_bundle_hash": "0" * 64, "git_diff_hash": "0" * 64,
            "consistency_status": "unverified", "canonical_status": "noncanonical",
        },
        "relationships": [{
            "relationship_id": "relationship-v2-prior",
            "source_run_id": run_id,
            "target_run_id": related_run_id,
            "relationship_type": "depends_on",
            "reason": "Synthetic prior evidence exists before indexing.",
            "created_at": "2026-07-16T01:00:30Z",
        }],
        "changed_files": [{
            "path": source_path, "change_type": "added", "before_hash": None,
            "after_hash": hashlib.sha256(source).hexdigest(), "previous_path": None,
        }],
        "changed_symbols": [{
            "file_path": source_path, "qualified_name": "implementation.implementation",
            "symbol_type": "function", "change_type": "added",
        }],
        "tests": [{
            "test_execution_id": "test-v2-1", "command": "python -m pytest -q",
            "purpose": "Verify v2", "status": "passed", "passed_count": 1,
            "failed_count": 0, "skipped_count": 0, "not_run_reason": None,
            "artifact_uri": None, "artifact_hash": None,
        }],
        "artifacts": [
            {"artifact_id": "artifact-v2-report", "artifact_type": "implementation_report", "path_or_uri": report_path, "location_kind": "repository_path", "content_hash": None, "schema_version": "2.0.0", "size_bytes": None},
            {"artifact_id": "artifact-v2-manifest", "artifact_type": "implementation_manifest", "path_or_uri": manifest_path, "location_kind": "repository_path", "content_hash": None, "schema_version": "2.0.0", "size_bytes": None},
        ],
        "component_references": [{"component_id": "quantmind2.project_knowledge", "impact_type": "modified"}],
        "adr_references": [{"adr_id": "ADR-0010", "relation": "conforms_to"}],
        "limitations": [{"limitation_id": "limit-v2-1", "severity": "low", "component_id": None, "description": "Synthetic evidence only.", "status": "accepted"}],
        "recommended_tasks": [{"recommendation_id": "recommend-v2-1", "next_task_id": "QM2-P0-003", "priority": "P0", "reason": "Continue to TDX."}],
        "integrity": {
            "canonicalization_version": "implementation-manifest-v2-canonical-json-v1",
            "report_sha256": "0" * 64, "manifest_payload_sha256": "0" * 64,
            "source_bundle_sha256": "0" * 64, "git_diff_sha256": "0" * 64,
            "git_changed_paths": sorted([source_path, report_path, manifest_path]),
            "git_added_paths": sorted([source_path, report_path, manifest_path]),
            "git_deleted_paths": [], "artifact_hashes": [],
        },
    }
    finalized = finalize_manifest_v2_payload(payload, report_bytes=report, repository_root=root)
    (root / manifest_path).write_text(json.dumps(finalized, indent=2, sort_keys=True) + "\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "add v2 run")
    analyzed = ImplementationRunPlanner(
        GitSnapshot(bind_repository("synthetic-main", root))
    ).plan(run_id).runs[0]
    return root, run_id, finalized, analyzed


def test_v2_example_schema_hash_and_all_domain_families() -> None:
    validate_instance(EXAMPLE, SCHEMA)
    validate_manifest_v2_payload(EXAMPLE)
    assert canonical_manifest_v2_payload_hash(EXAMPLE) == EXAMPLE["integrity"]["manifest_payload_sha256"]
    bundle = DomainBundleBuilder(
        RepositoryBinding("quantmind-example", Path("/not/the/execution/path"))
    ).build_source_v2(EXAMPLE)
    assert bundle.run.repository_root == "quantmind-example"
    assert bundle.run.manifest_schema_version == "2.0.0"
    assert all((bundle.relationships, bundle.changed_files, bundle.changed_symbols, bundle.tests, bundle.artifacts, bundle.component_refs, bundle.adr_refs, bundle.limitations, bundle.recommended_tasks))
    report = ROOT / EXAMPLE["run"]["report_path"]
    recomputed = finalize_manifest_v2_payload(
        EXAMPLE, report_bytes=report.read_bytes(), repository_root=ROOT
    )
    assert recomputed == EXAMPLE


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(extra="forbidden"),
        lambda p: p["task"].pop("status"),
        lambda p: p["run"].pop("task_id"),
        lambda p: p["tests"][0].pop("test_execution_id"),
        lambda p: p["component_references"][0].update(impact_type="invalid"),
        lambda p: p["task"].update(created_at="not-a-time"),
        lambda p: p["artifacts"][0].update(location_kind="unknown"),
        lambda p: p["integrity"].update(report_sha256="bad"),
    ],
)
def test_v2_schema_rejects_incomplete_or_invalid_values(mutation) -> None:  # noqa: ANN001
    payload = copy.deepcopy(EXAMPLE)
    mutation(payload)
    with pytest.raises((ManifestParseError, UnsupportedManifestSchemaError)):
        validate_manifest_v2_payload(payload)


def test_v2_rejects_mapper_identity_and_binding_mismatch() -> None:
    payload = copy.deepcopy(EXAMPLE)
    payload["mapper_contract_version"] = "2.0.0"
    with pytest.raises(UnsupportedManifestSchemaError):
        validate_manifest_v2_payload(payload)
    payload = copy.deepcopy(EXAMPLE)
    payload["identity_versions"]["changed_file"] = "changed-file-v2"
    with pytest.raises(UnsupportedManifestSchemaError):
        validate_manifest_v2_payload(payload)
    with pytest.raises(ManifestParseError):
        DomainBundleBuilder(RepositoryBinding("wrong-repository", Path("/tmp"))).build_source_v2(EXAMPLE)


def test_v2_new_draft_is_deterministic_and_does_not_infer_task() -> None:
    source = copy.deepcopy(EXAMPLE)
    source.pop("schema_version")
    source.pop("mapper_contract_version")
    source.pop("identity_versions")
    assert new_draft(source) == new_draft(source)
    source.pop("task")
    draft = new_draft(source)
    with pytest.raises(ManifestParseError):
        validate_manifest_v2_payload(draft)


def test_v2_producer_cli_new_and_validate(tmp_path: Path) -> None:
    source = copy.deepcopy(EXAMPLE)
    source.pop("schema_version")
    source.pop("mapper_contract_version")
    source.pop("identity_versions")
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "manifest.json"
    input_path.write_text(json.dumps(source), encoding="utf-8")
    tool = ROOT / "tools/quantmind2/create_implementation_manifest.py"
    created = subprocess.run(
        [sys.executable, str(tool), "new", "--input", str(input_path),
         "--output", str(output_path)],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert json.loads(created.stdout)["status"] == "draft_created"
    assert json.loads(output_path.read_text()) == EXAMPLE
    validated = subprocess.run(
        [sys.executable, str(tool), "validate", "--manifest", str(output_path),
         "--repository-id", "quantmind-example", "--repository-path", str(ROOT)],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert json.loads(validated.stdout) == {
        "domain_object_families": 11,
        "run_id": EXAMPLE["run"]["implementation_run_id"],
        "schema_version": "2.0.0",
        "status": "valid",
    }


def test_v2_committed_git_is_consistent_indexable_and_path_independent(tmp_path: Path) -> None:
    root, run_id, _, analyzed = build_v2_repository(tmp_path)
    assert analyzed.validated
    assert analyzed.indexable
    assert analyzed.domain_build is not None
    assert analyzed.domain_build.gaps == ()
    assert analyzed.domain_build.bundle is not None
    assert analyzed.domain_build.bundle.relationships[0].target_run_id == (
        "QM2-P0-996-20260716T000000Z-7654321"
    )
    assert analyzed.domain_build.bundle.run.repository_root == "synthetic-main"
    assert analyzed.evidence.resolved_status == "completed_committed"
    assert analyzed.evidence.resolved_result_commit == _git(root, "rev-parse", "HEAD")
    wrong = ImplementationRunPlanner(
        GitSnapshot(bind_repository("another-logical-id", root))
    ).plan(run_id).runs[0]
    assert not wrong.validated


def test_v1_parser_still_routes_and_unsupported_version_fails() -> None:
    v1_path = sorted((ROOT / "docs/quantmind2/implementation/runs").glob("*/*/*/manifest.json"))[0]
    v1 = json.loads(v1_path.read_text())
    parsed = ImplementationManifestParser().parse(
        v1_path.read_bytes(), manifest_path=v1_path.relative_to(ROOT).as_posix(),
        directory_run_id=v1["implementation_run_id"],
    )
    assert parsed.schema_version == "1.0.0"
    payload = copy.deepcopy(EXAMPLE)
    payload["schema_version"] = "3.0.0"
    with pytest.raises(UnsupportedManifestSchemaError):
        validate_manifest_v2_payload(payload)
