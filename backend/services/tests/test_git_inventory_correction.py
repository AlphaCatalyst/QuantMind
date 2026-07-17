from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from tools.quantmind2.git_inventory_correction import (
    OUTPUT,
    ROOT,
    TARGET_BASE,
    TARGET_COMMIT,
    TARGET_MANIFEST,
    TARGET_REPORT,
    TARGET_RUN_ID,
    GitInventoryCorrectionError,
    build_correction,
    canonical_inventory_hash,
    git_path_inventory,
    validate_correction,
    verify_finalized_run_inventory,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", message], check=True)
    return _git(root, "rev-parse", "HEAD")


def test_real_inventory_reconstruction_and_manifest_semantics_are_exact():
    payload = build_correction()
    changed = payload["fields"]["integrity.git_changed_paths"]
    added = payload["fields"]["integrity.git_added_paths"]
    assert payload["target_run_id"] == TARGET_RUN_ID
    assert payload["target_base_commit"] == TARGET_BASE
    assert payload["target_containing_commit"] == TARGET_COMMIT
    assert len(changed["verified"]) == 42
    assert len(added["verified"]) == 28
    assert changed["missing"] == [TARGET_MANIFEST]
    assert added["missing"] == [TARGET_MANIFEST]
    assert changed["unexpected"] == added["unexpected"] == []
    assert len(payload["verified_git_modified_paths"]) == 14
    assert payload["verified_git_deleted_paths"] == []
    assert payload["verified_git_renamed_paths"] == []
    assert TARGET_MANIFEST not in payload["business_changed_files"]
    assert TARGET_REPORT in payload["business_changed_files"]
    assert payload["verified_inventory_sha256"] == canonical_inventory_hash(
        changed["verified"], added["verified"]
    )


def test_inventory_and_guard_cover_add_modify_delete_rename_and_late_file(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "test")
    (tmp_path / "modify").write_text("before")
    (tmp_path / "delete").write_text("delete")
    (tmp_path / "old").write_text("rename-content")
    base = _commit(tmp_path, "base")
    (tmp_path / "modify").write_text("after")
    (tmp_path / "delete").unlink()
    (tmp_path / "old").rename(tmp_path / "new")
    (tmp_path / "business").write_text("business")
    run = tmp_path / "runs/run"
    run.mkdir(parents=True)
    (run / "report.md").write_text("report")
    (run / "manifest.json").write_text("{}")
    containing = _commit(tmp_path, "change")
    actual = git_path_inventory(tmp_path, base, containing)
    assert actual["changed"] == sorted(set(actual["changed"]))
    assert actual["added"] == sorted(set(actual["added"]))
    assert actual["modified"] == ["modify"]
    assert actual["deleted"] == ["delete", "old"]
    assert actual["renamed"] == [{"previous_path": "old", "path": "new"}]
    manifest = "runs/run/manifest.json"
    report = "runs/run/report.md"
    business = [path for path in actual["changed"] if path != manifest]
    verify_finalized_run_inventory(
        manifest_path=manifest,
        report_path=report,
        business_changed_files=business,
        declared_changed_paths=actual["changed"],
        declared_added_paths=actual["added"],
        actual=actual,
    )
    with pytest.raises(GitInventoryCorrectionError, match="git_changed_paths"):
        verify_finalized_run_inventory(
            manifest_path=manifest,
            report_path=report,
            business_changed_files=business,
            declared_changed_paths=actual["changed"][:-1],
            declared_added_paths=actual["added"],
            actual=actual,
        )
    with pytest.raises(GitInventoryCorrectionError, match="business ChangedFile"):
        verify_finalized_run_inventory(
            manifest_path=manifest,
            report_path=report,
            business_changed_files=[*business, manifest],
            declared_changed_paths=actual["changed"],
            declared_added_paths=actual["added"],
            actual=actual,
        )


def test_published_correction_matches_schema_git_and_immutable_target_bytes():
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert validate_correction(payload) == payload
    manifest = subprocess.check_output(
        ["git", "show", f"{TARGET_COMMIT}:{TARGET_MANIFEST}"], cwd=ROOT
    )
    report = subprocess.check_output(
        ["git", "show", f"{TARGET_COMMIT}:{TARGET_REPORT}"], cwd=ROOT
    )
    assert hashlib.sha256(manifest).hexdigest() == payload["immutable_target_manifest_sha256"]
    assert hashlib.sha256(report).hexdigest() == payload["immutable_target_report_sha256"]
    assert payload["root_cause"] == "incorrect_run_generation_usage"
    assert payload["effect"] == "evidence_correction_only"


def test_store_and_fresh_identities_remain_read_only_and_unchanged():
    store = FileSystemResearchArtifactStore(resolve_config())
    descriptors = store.list_artifacts()
    report = scan_store_integrity(store)
    inventory_id = "sai_a0b9e6183a7bed95d9dbcce918a19c9e2f63a67ffbc7617a2091b7a37955d312"
    inventory = json.loads(
        (store.root / "inventories" / f"{inventory_id}.json").read_text(encoding="utf-8")
    )
    assert len(descriptors) == inventory["artifact_count"] == 65
    assert report.blob_count == inventory["unique_blob_count"] == 280
    assert report.status == inventory["integrity_summary"]["status"] == "healthy"
    assert report.issues == () and report.unreferenced_blobs == ()
    assert inventory["inventory_id"] == inventory_id
    state = json.loads(
        (ROOT / "docs/quantmind2/context/current_state.json").read_text(encoding="utf-8")
    )["fresh_validation"]
    assert state["candidate_lock_id"].startswith("fvcl_716d7465")
    assert state["protocol_id"].startswith("fvp_93163e1b")
    assert state["exposure_ledger_id"].startswith("rdel_56d95b77")
    assert state["watermark_id"].startswith("fdw_3459fb5")
    assert state["eligible_date_count"] == 0
    assert state["status"] == "awaiting_first_fresh_date"


def test_correction_run_relationship_is_corrects_only_after_publication():
    candidates = list(
        (ROOT / "docs/quantmind2/implementation/runs/2026/2026-07").glob(
            "QM2-P0-010F-*/manifest.json"
        )
    )
    if not candidates:
        pytest.skip("010F Manifest is created after focused correction tests")
    manifest = json.loads(candidates[0].read_text(encoding="utf-8"))
    assert len(manifest["relationships"]) == 1
    relationship = manifest["relationships"][0]
    assert relationship["relationship_type"] == "corrects"
    assert relationship["target_run_id"] == TARGET_RUN_ID
    assert "supersedes" not in json.dumps(manifest)
    assert manifest["run"]["manifest_path"] not in {
        item["path"] for item in manifest["changed_files"]
    }
    assert manifest["run"]["manifest_path"] in manifest["integrity"]["git_changed_paths"]
    assert manifest["run"]["manifest_path"] in manifest["integrity"]["git_added_paths"]
