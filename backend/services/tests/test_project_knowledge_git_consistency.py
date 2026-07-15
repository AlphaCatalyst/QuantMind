from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from backend.services.api.project_knowledge.indexing import (
    GitSnapshot,
    ImplementationRunPlanner,
    bind_repository,
)
from tools.quantmind2.validate_context_bootstrap import canonical_manifest_payload_hash


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _repository(tmp_path: Path, *, explicit_result: str | None = None) -> tuple[Path, str]:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "QuantMind Test")
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "base.txt")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD")
    run_id = f"QM2-P0-999-20260715T000000Z-{base[:7]}"
    directory = Path("docs/quantmind2/implementation/runs/2026/2026-07") / run_id
    full = root / directory
    full.mkdir(parents=True)
    report_path = (directory / "report.md").as_posix()
    manifest_path = (directory / "manifest.json").as_posix()
    report = b"# Synthetic Run\n"
    (root / report_path).write_bytes(report)
    payload = {
        "manifest_schema_version": "1.0.0",
        "implementation_run_id": run_id,
        "task_id": "QM2-P0-999",
        "parent_task_id": None,
        "title": "Synthetic Run",
        "objective": "Verify committed Git evidence.",
        "scope": ["test"],
        "explicit_non_goals": ["production"],
        "repository": "synthetic",
        "repository_root": str(root),
        "branch": "master",
        "base_commit": base,
        "result_commit": explicit_result,
        "workspace_dirty_before": False,
        "workspace_dirty_after": True,
        "unrelated_dirty_files": [],
        "source_bundle_hash": "1" * 64,
        "git_diff_hash": "2" * 64,
        "started_at": "2026-07-15T00:00:00Z",
        "completed_at": "2026-07-15T00:01:00Z",
        "agent_type": "codex",
        "task_status": "completed_uncommitted" if explicit_result is None else "completed_committed",
        "completion_level": "complete",
        "verification_level": "targeted_tests",
        "changed_files": sorted([manifest_path, report_path]),
        "added_files": sorted([manifest_path, report_path]),
        "deleted_files": [],
        "changed_symbols": [],
        "database_migrations": [],
        "api_endpoints": [],
        "schemas_changed": [],
        "config_changed": [],
        "dependencies_changed": False,
        "tests_executed": [],
        "test_results": {"status": "passed", "passed": 1, "failed": 0, "skipped": 0, "not_run": 0},
        "artifacts": [],
        "architecture_decision_refs": [],
        "component_refs": [],
        "known_limitations": [],
        "unresolved_questions": [],
        "next_recommended_tasks": [],
        "rollback_information": "Revert the containing commit.",
        "frozen_architecture_compliance": "compliant",
        "security_impact": "None.",
        "data_lineage_impact": "None.",
        "report_path": report_path,
        "report_hash": hashlib.sha256(report).hexdigest(),
        "manifest_path": manifest_path,
        "manifest_payload_hash": "0" * 64,
        "generated_context_versions": {},
        "corrects_run_id": None,
    }
    payload["manifest_payload_hash"] = canonical_manifest_payload_hash(payload)
    (root / manifest_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "add run")
    return root, run_id


def _plan(root: Path, run_id: str):  # noqa: ANN001
    binding = bind_repository("synthetic-main", root)
    return ImplementationRunPlanner(GitSnapshot(binding)).plan(run_id).runs[0]


def test_committed_snapshot_resolves_precommit_status_and_ignores_worktree(tmp_path: Path) -> None:
    root, run_id = _repository(tmp_path)
    analyzed = _plan(root, run_id)
    assert analyzed.validated
    assert analyzed.evidence.source_status == "completed_uncommitted"
    assert analyzed.evidence.resolved_status == "completed_committed"
    assert analyzed.evidence.resolved_result_commit == _git(root, "rev-parse", "HEAD")

    (root / "base.txt").write_text("dirty\n", encoding="utf-8")
    (root / "docs/quantmind2/implementation/runs/untracked.json").write_text("{}")
    after = _plan(root, run_id)
    assert after.evidence == analyzed.evidence


def test_result_commit_mismatch_and_immutable_history_fail(tmp_path: Path) -> None:
    root, run_id = _repository(tmp_path, explicit_result="f" * 40)
    analyzed = _plan(root, run_id)
    assert "result_commit" in {
        check.name for check in analyzed.evidence.checks if not check.passed
    }

    manifest = Path(analyzed.discovered.manifest_path)
    (root / manifest).write_text((root / manifest).read_text() + "\n")
    _git(root, "add", manifest.as_posix())
    _git(root, "commit", "-qm", "illegally mutate run")
    mutated = _plan(root, run_id)
    failures = {check.name for check in mutated.evidence.checks if not check.passed}
    assert {"immutable_run_files", "manifest_blob_immutable"} <= failures


def test_current_history_is_measured_without_inventing_v1_fields() -> None:
    root = Path(__file__).resolve().parents[3]
    plan = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", root))
    ).plan()
    assert plan.discovered_count == 16
    assert plan.validated_count == 15
    assert plan.indexable_count == 0
    assert any(
        gap.code == "MANIFEST_V1_TASK_STATUS_MISSING"
        for run in plan.runs
        if run.domain_build
        for gap in run.domain_build.gaps
    )
