from __future__ import annotations

import json
import os
import plistlib
import subprocess
from pathlib import Path

import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.fresh_heartbeat_scheduler.models import SCHEDULE
from backend.services.engine.fresh_runtime_deployment.models import (
    FreshRuntimeAppSnapshotV1,
    FreshRuntimeDeploymentStatusV1,
    FreshRuntimeEnvironmentSnapshotV1,
    FreshRuntimePathAuditV1,
    FreshRuntimeStateMigrationV1,
)
from backend.services.engine.fresh_runtime_deployment.service import (
    FreshRuntimeDeploymentService,
    RuntimeDeploymentError,
    _atomic_symlink,
    _chmod_immutable,
    is_protected_path,
)


REPOSITORY = Path(__file__).resolve().parents[3]


def _service(tmp_path: Path) -> FreshRuntimeDeploymentService:
    home = tmp_path / "home"
    runtime = home / "Library/Application Support/QuantMind"
    store = home / ".quantmind2/artifact-store/v1"
    FileSystemResearchArtifactStore(resolve_config(store)).initialize()
    return FreshRuntimeDeploymentService(
        repository_root=REPOSITORY,
        runtime_root=runtime,
        source_python=Path(os.environ.get("QM2_TEST_PYTHON", os.sys.executable)),
        source_libomp=tmp_path / "libomp",
        artifact_store_root=store,
        home=home,
    )


@pytest.mark.parametrize(
    "relative",
    (
        "Documents/repo",
        "Desktop/runtime",
        "Downloads/env",
        "Library/Mobile Documents/state",
        "iCloud Drive/data",
    ),
)
def test_protected_path_detection(tmp_path: Path, relative: str) -> None:
    assert is_protected_path(tmp_path / relative, home=tmp_path)


def test_allowed_runtime_paths_are_not_protected(tmp_path: Path) -> None:
    assert not is_protected_path(
        tmp_path / "Library/Application Support/QuantMind", home=tmp_path
    )
    assert not is_protected_path(tmp_path / ".quantmind2", home=tmp_path)


@pytest.mark.parametrize(
    ("model", "field", "prefix"),
    (
        (
            FreshRuntimePathAuditV1(
                "2026-01-01T00:00:00Z", (), 0, "APFS", True, 1, 1
            ),
            "fresh_runtime_path_audit_id",
            "frpa1_",
        ),
        (
            FreshRuntimeAppSnapshotV1(
                "a" * 40, "2026-01-01T00:00:00Z", "/repo", "/app", 1, "b" * 64, {}
            ),
            "fresh_runtime_app_snapshot_id",
            "fras1_",
        ),
        (
            FreshRuntimeEnvironmentSnapshotV1(
                "2026-01-01T00:00:00Z",
                "qmenv1_" + "c" * 64,
                "/env",
                "/snapshot",
                "3.12",
                "arm64",
                {},
                "d" * 64,
                {},
                "apfs_clone",
                False,
                {"valid": True},
            ),
            "fresh_runtime_environment_snapshot_id",
            "fres1_",
        ),
        (
            FreshRuntimeStateMigrationV1(
                "2026-01-01T00:00:00Z",
                "/store",
                "/store",
                False,
                False,
                False,
                1,
                "healthy",
                0,
                0,
            ),
            "fresh_runtime_state_migration_id",
            "frsm1_",
        ),
        (
            FreshRuntimeDeploymentStatusV1(
                "deployment",
                "2026-01-01T00:00:00Z",
                "a" * 40,
                "fras1_x",
                "qmenv1_x",
                "/runtime",
                "/state",
                "e" * 64,
                "com.quantmind.fresh-model-heartbeat",
                True,
                True,
                0,
                "exact_replay",
                True,
                0,
                1,
                True,
            ),
            "fresh_runtime_deployment_status_id",
            "frds1_",
        ),
    ),
)
def test_runtime_artifact_identities(model, field: str, prefix: str) -> None:
    payload = model.payload()
    assert payload[field].startswith(prefix)
    assert "tushare_token" not in json.dumps(payload).lower()


def test_atomic_pointer_switch_preserves_previous(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    link = tmp_path / "current"
    assert _atomic_symlink(first, link) is None
    assert link.resolve() == first
    assert _atomic_symlink(second, link) == str(first)
    assert link.resolve() == second


def test_immutable_snapshot_removes_write_bits(tmp_path: Path) -> None:
    root = tmp_path / "app"
    root.mkdir()
    file = root / "entrypoint"
    file.write_text("ok")
    os.chmod(file, 0o755)
    _chmod_immutable(root)
    assert file.stat().st_mode & 0o222 == 0
    assert file.stat().st_mode & 0o111


def test_app_snapshot_contains_only_committed_git_objects(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    required = (
        "tools/quantmind2/deployed_fresh_heartbeat.sh",
        "tools/quantmind2/manage_fresh_runtime_deployment.py",
        "tools/quantmind2/run_autonomous_research_supervisor.py",
    )
    for relative in required:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(path, 0o755)
    (repository / "committed.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=QuantMind Test",
            "-c",
            "user.email=quantmind-test@example.invalid",
            "commit",
            "-qm",
            "snapshot",
        ],
        cwd=repository,
        check=True,
    )
    (repository / "untracked-secret.txt").write_text(
        "worktree-only", encoding="utf-8"
    )
    service = _service(tmp_path)
    service.repository_root = repository
    result = service.build_app_snapshot()
    snapshot = Path(result["snapshot_path"])
    assert (snapshot / "committed.txt").read_text() == "tracked"
    assert not (snapshot / "untracked-secret.txt").exists()
    assert not (snapshot / ".git").exists()
    assert result["tracked_file_count"] == 4
    assert result["immutable"] is True
    assert all(
        path.stat().st_mode & 0o222 == 0
        for path in snapshot.rglob("*")
        if not path.is_symlink()
    )


def test_runtime_config_accepts_only_external_paths(tmp_path: Path) -> None:
    service = _service(tmp_path)
    root = service.runtime_root
    config = {
        "schema_version": "fresh-runtime-config-v1",
        "app_root": str(root / "runtime/apps" / ("a" * 40)),
        "python_executable": str(root / "runtime/envs/qmenv1_x/bin/python"),
        "environment_root": str(root / "runtime/envs/qmenv1_x"),
        "libomp_root": str(root / "runtime/envs/qmenv1_x/native/libomp"),
        "artifact_store_root": str(service.artifact_store_root),
        "market_data_root": str(root / "state/market-data"),
        "checkpoint_root": str(root / "state/checkpoints"),
        "lock_root": str(root / "state/locks"),
        "log_root": str(root / "logs"),
        "temporary_root": str(root / "state/tmp"),
        "repository_commit": "a" * 40,
        "environment_fingerprint": "qmenv1_x",
    }
    service.validate_config(config)


def test_runtime_config_rejects_protected_dependency(tmp_path: Path) -> None:
    service = _service(tmp_path)
    config = {
        "schema_version": "fresh-runtime-config-v1",
        "app_root": str(service.home / "Documents/repo"),
        "python_executable": str(service.runtime_root / "env/bin/python"),
        "environment_root": str(service.runtime_root / "env"),
        "libomp_root": str(service.runtime_root / "env/native"),
        "artifact_store_root": str(service.artifact_store_root),
        "market_data_root": str(service.runtime_root / "state/market-data"),
        "checkpoint_root": str(service.runtime_root / "state/checkpoints"),
        "lock_root": str(service.runtime_root / "state/locks"),
        "log_root": str(service.runtime_root / "logs"),
        "temporary_root": str(service.runtime_root / "state/tmp"),
        "repository_commit": "a" * 40,
        "environment_fingerprint": "qmenv1_x",
    }
    with pytest.raises(RuntimeDeploymentError, match="PROTECTED"):
        service.validate_config(config)


def test_runtime_config_rejects_secret_marker(tmp_path: Path) -> None:
    service = _service(tmp_path)
    config = {
        "schema_version": "fresh-runtime-config-v1",
        "app_root": str(service.runtime_root / "app"),
        "python_executable": str(service.runtime_root / "env/bin/python"),
        "environment_root": str(service.runtime_root / "env"),
        "libomp_root": str(service.runtime_root / "env/native"),
        "artifact_store_root": str(service.artifact_store_root),
        "market_data_root": str(service.runtime_root / "state/market-data"),
        "checkpoint_root": str(service.runtime_root / "state/checkpoints"),
        "lock_root": str(service.runtime_root / "state/locks"),
        "log_root": str(service.runtime_root / "logs"),
        "temporary_root": str(service.runtime_root / "state/tmp"),
        "repository_commit": "a" * 40,
        "environment_fingerprint": "qmenv1_x",
        "password": "forbidden",
    }
    with pytest.raises(RuntimeDeploymentError, match="secret"):
        service.validate_config(config)


def test_environment_fingerprint_is_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    audit = {
        "version": "3.12.1",
        "machine": "arm64",
        "package_versions": {"numpy": "2"},
        "site_packages_inventory_hash": "a" * 64,
        "native_library_checksums": {"lib": "b" * 64},
    }
    monkeypatch.setattr(service, "environment_audit", lambda: audit)
    first = service.environment_fingerprint()[0]
    second = service.environment_fingerprint()[0]
    assert first == second
    assert first.startswith("qmenv1_")


def test_environment_fingerprint_changes_with_native_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    audit = {
        "version": "3.12.1",
        "machine": "arm64",
        "package_versions": {"numpy": "2"},
        "site_packages_inventory_hash": "a" * 64,
        "native_library_checksums": {"lib": "b" * 64},
    }
    monkeypatch.setattr(service, "environment_audit", lambda: dict(audit))
    first = service.environment_fingerprint()[0]
    audit["native_library_checksums"] = {"lib": "c" * 64}
    second = service.environment_fingerprint()[0]
    assert first != second


def test_state_audit_preserves_single_healthy_store(tmp_path: Path) -> None:
    service = _service(tmp_path)
    result = service.migrate_state()
    assert result["relocation_required"] is False
    assert result["migration_performed"] is False
    assert result["canonical_writable_store_count"] == 1
    assert result["integrity_status"] == "healthy"


def test_store_integrity_remains_healthy(tmp_path: Path) -> None:
    service = _service(tmp_path)
    store = FileSystemResearchArtifactStore(resolve_config(service.artifact_store_root))
    result = scan_store_integrity(store)
    assert result.status == "healthy"
    assert not result.issues
    assert not result.unreferenced_blobs


def test_runtime_artifact_kinds_publish_and_verify(tmp_path: Path) -> None:
    service = _service(tmp_path)
    payloads = (
        (
            "fresh_runtime_path_audit",
            FreshRuntimePathAuditV1(
                "2026-01-01T00:00:00Z", (), 0, "APFS", True, 1, 1
            ).payload(),
        ),
        (
            "fresh_runtime_app_snapshot",
            FreshRuntimeAppSnapshotV1(
                "a" * 40,
                "2026-01-01T00:00:00Z",
                "/repo",
                "/app",
                1,
                "b" * 64,
                {},
            ).payload(),
        ),
        (
            "fresh_runtime_environment_snapshot",
            FreshRuntimeEnvironmentSnapshotV1(
                "2026-01-01T00:00:00Z",
                "qmenv1_" + "c" * 64,
                "/env",
                "/snapshot",
                "3.12",
                "arm64",
                {},
                "d" * 64,
                {},
                "apfs_clone",
                False,
                {"valid": True},
            ).payload(),
        ),
        (
            "fresh_runtime_state_migration",
            FreshRuntimeStateMigrationV1(
                "2026-01-01T00:00:00Z",
                "/store",
                "/store",
                False,
                False,
                False,
                1,
                "healthy",
                0,
                0,
            ).payload(),
        ),
        (
            "fresh_runtime_deployment_status",
            FreshRuntimeDeploymentStatusV1(
                "deployment",
                "2026-01-01T00:00:00Z",
                "a" * 40,
                "fras1_x",
                "qmenv1_x",
                "/runtime",
                "/state",
                "e" * 64,
                "com.quantmind.fresh-model-heartbeat",
                True,
                True,
                0,
                "exact_replay",
                True,
                0,
                1,
                True,
            ).payload(),
        ),
    )
    ids = [service._publish(kind, payload)["artifact_id"] for kind, payload in payloads]
    assert len(ids) == len(set(ids)) == 5
    result = scan_store_integrity(service._repository().store)
    assert result.status == "healthy"
    assert not result.issues
    assert not result.unreferenced_blobs


def test_launchagent_template_has_frozen_schedule_and_external_paths() -> None:
    path = REPOSITORY / "deploy/launchd/com.quantmind.fresh-model-heartbeat.plist"
    with path.open("rb") as handle:
        value = plistlib.load(handle)
    serialized = path.read_text(encoding="utf-8")
    assert value["StartCalendarInterval"] == list(SCHEDULE)
    assert value["ProgramArguments"][:2] == ["/bin/zsh", "-lc"]
    assert "/Documents/" not in serialized
    assert "TUSHARE_TOKEN" not in serialized
    assert "KeepAlive" not in value


def test_deployed_entrypoint_has_external_runtime_and_cleanup() -> None:
    path = REPOSITORY / "tools/quantmind2/deployed_fresh_heartbeat.sh"
    text = path.read_text(encoding="utf-8")
    assert "/Documents/" not in text
    assert "runtime/current-env/bin/python" in text
    assert "runtime/current-app" in text
    assert "state/tmp" in text
    assert "trap cleanup" in text
    assert "TUSHARE_TOKEN" in text


def test_cleanup_candidates_never_selects_active_pointers(tmp_path: Path) -> None:
    service = _service(tmp_path)
    app = service.apps_root / ("a" * 40)
    old = service.apps_root / ("b" * 40)
    env = service.envs_root / "qmenv1_active"
    service.ensure_layout()
    app.mkdir()
    old.mkdir()
    env.mkdir()
    _atomic_symlink(app, service.current_app)
    _atomic_symlink(env, service.current_env)
    rows = service.cleanup_candidates()
    assert [row["path"] for row in rows] == [str(old)]
    assert rows[0]["rollback_dependency"] is True


def test_cold_recovery_and_replay_have_zero_side_effects(tmp_path: Path) -> None:
    service = _service(tmp_path)
    recovered = service.cold_recover()
    replay = service.replay()
    assert recovered["launchctl_calls"] == 0
    assert recovered["tushare_calls"] == 0
    assert replay["status"] == "exact_replay"
    for key in (
        "launchctl_mutations",
        "tushare_calls",
        "model_training",
        "prediction_writes",
        "label_writes",
        "strategy_writes",
        "scheduler_writes",
        "new_artifacts",
        "new_blobs",
    ):
        assert replay[key] == 0


def test_uninstall_preserves_runtime_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    service.ensure_layout()
    service.installed_plist.write_text("plist")
    state = service.state_root / "checkpoint"
    state.write_text("keep")
    monkeypatch.setattr(service, "loaded", lambda: False)
    result = service.uninstall()
    assert not service.installed_plist.exists()
    assert state.read_text() == "keep"
    assert result["artifacts_deleted"] == 0
    assert result["snapshots_deleted"] == 0


def test_plist_lints() -> None:
    result = subprocess.run(
        [
            "/usr/bin/plutil",
            "-lint",
            str(
                REPOSITORY
                / "deploy/launchd/com.quantmind.fresh-model-heartbeat.plist"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
