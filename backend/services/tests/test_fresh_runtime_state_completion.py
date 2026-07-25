from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.fresh_heartbeat_scheduler.models import (
    FreshHeartbeatSchedulerStatusV1,
)
from backend.services.engine.fresh_runtime_deployment.models import (
    FreshRuntimeAppSnapshotV1,
    FreshRuntimeDeploymentStatusV1,
)
from backend.services.engine.fresh_runtime_deployment.resolver import (
    CanonicalRuntimeArtifactResolverV1,
)
from backend.services.engine.fresh_runtime_deployment.service import (
    FreshRuntimeDeploymentService,
)
from backend.services.engine.fresh_runtime_deployment.status_consistency import (
    FreshRuntimeStatusConsistencyError,
    FreshRuntimeStatusConsistencyValidatorV1,
)


REPOSITORY = Path(__file__).resolve().parents[3]


def _service(tmp_path: Path) -> FreshRuntimeDeploymentService:
    home = tmp_path / "home"
    store = home / ".quantmind2/artifact-store/v1"
    FileSystemResearchArtifactStore(resolve_config(store)).initialize()
    service = FreshRuntimeDeploymentService(
        repository_root=REPOSITORY,
        runtime_root=home / "Library/Application Support/QuantMind",
        source_python=Path(os.sys.executable),
        source_libomp=tmp_path / "libomp",
        artifact_store_root=store,
        home=home,
    )
    service.ensure_layout()
    return service


def _app(service: FreshRuntimeDeploymentService, commit: str, created: str) -> dict:
    payload = FreshRuntimeAppSnapshotV1(
        git_commit=commit,
        created_at=created,
        source_repository=str(REPOSITORY),
        snapshot_path=f"/runtime/apps/{commit}",
        tracked_file_count=1,
        source_bundle_hash="f" * 64,
        entrypoint_checksums={},
    ).payload()
    receipt = service._publish("fresh_runtime_app_snapshot", payload)
    return payload | {"artifact_receipt": receipt}


def _deployment(
    service: FreshRuntimeDeploymentService, app_id: str, deployed: str
) -> dict:
    payload = FreshRuntimeDeploymentStatusV1(
        deployment_id="deployment-" + app_id[-8:],
        deployed_at=deployed,
        source_commit="b" * 40,
        app_snapshot_id=app_id,
        environment_fingerprint="qmenv1_" + "c" * 64,
        runtime_root=str(service.runtime_root),
        state_root=str(service.state_root),
        runtime_config_checksum="d" * 64,
        launch_agent_label="com.quantmind.fresh-model-heartbeat",
        launch_agent_loaded=True,
        launchd_trigger_verified=True,
        launchd_exit_status=0,
        heartbeat_status="exact_replay",
        idempotency_verified=True,
        protected_path_dependency_count=0,
        allocated_bytes=1,
        rollback_available=True,
        tmp_cleanup_verified=True,
        diagnostic_whitelist_enabled=True,
        redaction_guard_enabled=True,
        redaction_violation_count=0,
    ).payload()
    receipt = service._publish("fresh_runtime_deployment_status", payload)
    return payload | {"artifact_receipt": receipt}


def _scheduler(
    service: FreshRuntimeDeploymentService, deployment: dict
) -> dict:
    deployment_id = deployment["artifact_receipt"]["artifact_id"]
    payload = FreshHeartbeatSchedulerStatusV1(
        template_path="/runtime/agent.plist",
        installed_path="/runtime/agent.plist",
        template_checksum="e" * 64,
        installed_checksum="e" * 64,
        loaded=True,
        enabled=True,
        last_exit_status=0,
        last_run_at="2026-07-25T08:00:00Z",
        last_success_at="2026-07-25T08:00:00Z",
        consecutive_failures=0,
        next_expected_run=None,
        token_available_in_launch_context=True,
        repository_head_at_install=deployment["source_commit"],
        source_commit=deployment["source_commit"],
        app_snapshot_id=deployment["app_snapshot_id"],
        environment_fingerprint=deployment["environment_fingerprint"],
        runtime_config_checksum=deployment["runtime_config_checksum"],
        deployment_status_id=deployment_id,
        launchd_trigger_verified=True,
        idempotency_verified=True,
        tmp_cleanup_verified=True,
        diagnostic_whitelist_enabled=True,
        redaction_guard_enabled=True,
        redaction_violation_count=0,
    ).payload()
    receipt = service._publish(
        "fresh_heartbeat_scheduler_status", payload, lineage=(deployment_id,)
    )
    return payload | {"artifact_receipt": receipt}


def test_status_consistency_accepts_bound_final_revision(tmp_path: Path) -> None:
    service = _service(tmp_path)
    app = _app(service, "a" * 40, "2026-07-25T07:00:00Z")
    deployment = _deployment(
        service, app["artifact_receipt"]["artifact_id"], "2026-07-25T08:00:00Z"
    )
    scheduler = _scheduler(service, deployment)
    result = FreshRuntimeStatusConsistencyValidatorV1().validate(
        scheduler=scheduler, deployment=deployment
    )
    assert result["consistent"] is True
    broken = scheduler | {"app_snapshot_id": "fras1_" + "0" * 64}
    with pytest.raises(
        FreshRuntimeStatusConsistencyError,
        match="RUNTIME_STATUS_CROSS_ARTIFACT_MISMATCH",
    ):
        FreshRuntimeStatusConsistencyValidatorV1().validate(
            scheduler=broken, deployment=deployment
        )


def test_scheduler_final_revision_binds_deployment_and_second_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    app = service.apps_root / ("b" * 40)
    program = app / "tools/quantmind2/deployed_fresh_heartbeat.sh"
    program.parent.mkdir(parents=True)
    program.write_text("#!/bin/sh\n", encoding="utf-8")
    environment = service.envs_root / ("qmenv1_" + "c" * 64)
    (environment / "bin").mkdir(parents=True)
    service.runtime_config_path.write_text(
        json.dumps(
            {
                "schema_version": "fresh-runtime-config-v1",
                "app_root": str(app),
                "python_executable": str(environment / "bin/python"),
                "environment_root": str(environment),
                "libomp_root": str(environment / "native/libomp"),
                "artifact_store_root": str(service.artifact_store_root),
                "market_data_root": str(service.state_root / "market-data"),
                "checkpoint_root": str(service.state_root / "checkpoints"),
                "lock_root": str(service.state_root / "locks"),
                "log_root": str(service.logs_root),
                "temporary_root": str(service.state_root / "tmp"),
                "repository_commit": app.name,
                "environment_fingerprint": environment.name,
                "credential_persisted": False,
            }
        ),
        encoding="utf-8",
    )
    service.installed_plist.write_text("plist", encoding="utf-8")
    service._local_status_path().write_text(
        json.dumps(
            {
                "last_launchd_exit_status": 0,
                "last_run_at": "2026-07-25T08:00:00Z",
                "last_success_at": "2026-07-25T08:00:00Z",
                "latest_heartbeat_id": "fmhr1_" + "a" * 64,
                "redaction_count": 0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(service, "loaded", lambda: True)
    monkeypatch.setattr(
        service, "safe_credential_check", lambda: {"token_available": True}
    )
    monkeypatch.setattr(
        service,
        "_publish",
        lambda kind, payload, **kwargs: {
            "artifact_id": payload["fresh_heartbeat_scheduler_status_id"]
        },
    )
    deployment = {
        "fresh_runtime_deployment_status_id": "frds1_" + "d" * 64,
        "source_commit": app.name,
        "app_snapshot_id": "fras1_" + "e" * 64,
        "environment_fingerprint": environment.name,
        "runtime_config_checksum": "f" * 64,
        "launchd_trigger_verified": True,
        "idempotency_verified": True,
        "tmp_cleanup_verified": True,
        "redaction_violation_count": 0,
    }
    monkeypatch.setattr(
        "backend.services.engine.fresh_runtime_deployment.service.hash_file",
        lambda path: (
            deployment["runtime_config_checksum"]
            if path == service.runtime_config_path
            else "1" * 64
        ),
    )
    status = service.publish_scheduler_status(
        deployment_status=deployment,
        operational_run={"latest_operational_run_id": "fhor1_" + "2" * 64},
        app_snapshot_id=deployment["app_snapshot_id"],
    )
    assert status["app_snapshot_id"] == deployment["app_snapshot_id"]
    assert status["deployment_status_id"] == deployment[
        "fresh_runtime_deployment_status_id"
    ]
    assert status["idempotency_verified"] is True
    assert status["operational_run_id"].startswith("fhor1_")


def test_pointer_selects_canonical_instead_of_artifact_id_order(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    old_app = _app(service, "1" * 40, "2026-07-25T06:00:00Z")
    new_app = _app(service, "2" * 40, "2026-07-25T08:00:00Z")
    old_deployment = _deployment(
        service,
        old_app["artifact_receipt"]["artifact_id"],
        "2026-07-25T06:30:00Z",
    )
    _scheduler(service, old_deployment)
    deployment = _deployment(
        service,
        new_app["artifact_receipt"]["artifact_id"],
        "2026-07-25T08:30:00Z",
    )
    scheduler = _scheduler(service, deployment)
    pointer = service.publish_current_deployment_pointer(
        deployment_status=deployment, scheduler_status=scheduler
    )
    resolver = CanonicalRuntimeArtifactResolverV1(
        store=service._repository().store,
        current_deployment_pointer=(
            service.deployments_root / "current-deployment.json"
        ),
    )
    resolved = resolver.resolve()
    assert resolved.resolution_source == "explicit_current_deployment_pointer"
    assert resolved.app_snapshot["artifact_id"] == pointer["app_snapshot_id"]
    assert (
        resolved.deployment_status["artifact_id"]
        == pointer["deployment_status_id"]
    )
    assert (
        resolved.scheduler_status["artifact_id"] == pointer["scheduler_status_id"]
    )
    assert len(resolved.historical_artifacts["fresh_runtime_app_snapshot"]) == 2


def test_revision_order_key_uses_time_before_artifact_id() -> None:
    older = type(
        "Descriptor",
        (),
        {"created_at": "2026-07-25T06:00:00Z", "artifact_id": "zzzz_older"},
    )()
    newer = type(
        "Descriptor",
        (),
        {"created_at": "2026-07-25T08:00:00Z", "artifact_id": "aaaa_newer"},
    )()
    older_key = CanonicalRuntimeArtifactResolverV1._order_key(
        older, {"created_at": "2026-07-25T06:00:00Z"}
    )
    newer_key = CanonicalRuntimeArtifactResolverV1._order_key(
        newer, {"created_at": "2026-07-25T08:00:00Z"}
    )
    assert newer_key > older_key


def test_pointer_write_failure_preserves_previous_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    pointer = service.deployments_root / "current-deployment.json"
    pointer.write_text('{"old":true}\n', encoding="utf-8")
    old = pointer.read_bytes()
    app = _app(service, "3" * 40, "2026-07-25T08:00:00Z")
    deployment = _deployment(
        service, app["artifact_receipt"]["artifact_id"], "2026-07-25T08:30:00Z"
    )
    scheduler = _scheduler(service, deployment)

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("injected pointer switch failure")

    monkeypatch.setattr(
        "backend.services.engine.fresh_heartbeat_scheduler.service.os.replace",
        fail_replace,
    )
    with pytest.raises(OSError, match="injected"):
        service.publish_current_deployment_pointer(
            deployment_status=deployment, scheduler_status=scheduler
        )
    assert pointer.read_bytes() == old


def test_environment_validation_directory_is_removed_on_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    root = tmp_path / "environment"
    python = root / "bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        "backend.services.engine.fresh_runtime_deployment.service.platform.machine",
        lambda: "arm64",
    )

    def success(command, *, env, timeout):
        assert Path(env["TMPDIR"]).parent == service.state_root / "tmp"
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "prefix": str(root),
                    "imports": True,
                    "parquet": True,
                    "lightgbm": True,
                }
            ),
            "",
        )

    monkeypatch.setattr(service, "_run", success)
    assert service.validate_environment(root, "qmenv1_test")["valid"] is True
    assert list((service.state_root / "tmp").iterdir()) == []

    def failure(*_args, **_kwargs):
        raise RuntimeError("injected environment validation failure")

    monkeypatch.setattr(service, "_run", failure)
    with pytest.raises(RuntimeError, match="injected"):
        service.validate_environment(root, "qmenv1_test")
    assert list((service.state_root / "tmp").iterdir()) == []
