from __future__ import annotations

import json
import os
import plistlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.autonomous_factor_campaign.artifact import (
    KINDS,
    publish_artifact,
)
from backend.services.engine.fresh_heartbeat_scheduler import models, service
from backend.services.engine.fresh_heartbeat_scheduler.models import (
    FreshHeartbeatSchedulerStatusV1,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload
from tools.quantmind2 import manage_fresh_heartbeat_launchagent as manager


class FakeStore:
    def __init__(self):
        self.descriptors = []

    def list_by_kind(self, kind):
        return [row for row in self.descriptors if row.artifact_kind == kind]


class FakeRepository:
    def __init__(self):
        self.store = FakeStore()
        self.values = {}

    def identity(self, artifact_id):
        return dict(self.values[artifact_id])

    def publish(self, kind, identity, files, lineage=()):
        field, prefix = KINDS[kind]
        artifact_id = identity.get(field) or prefix + hash_payload(identity)
        stable = dict(identity)
        stable.pop(field, None)
        exact = artifact_id in self.values
        self.values[artifact_id] = stable
        if not exact:
            self.store.descriptors.append(
                SimpleNamespace(artifact_kind=kind, artifact_id=artifact_id)
            )
        return {
            "artifact_id": artifact_id,
            "exact_existing": exact,
            "new_blob_count": 0 if exact else 1,
        }


def _add_fresh_state(repository, status="fresh_evidence_accumulating"):
    candidate_ids = ("candidate-b", "candidate-c")
    assessment_ids = []
    for index, candidate_id in enumerate(candidate_ids):
        artifact_id = f"fmca1_{index:064x}"
        repository.values[artifact_id] = {
            "candidate_id": candidate_id,
            "status": status,
        }
        repository.store.descriptors.append(
            SimpleNamespace(
                artifact_kind="fresh_model_candidate_assessment",
                artifact_id=artifact_id,
            )
        )
        assessment_ids.append(artifact_id)
    heartbeat_id = f"fmhr1_{1:064x}"
    repository.values[heartbeat_id] = {
        "status": status,
        "data_as_of_date": "2026-07-24",
        "candidate_assessment_ids": assessment_ids,
    }
    repository.store.descriptors.append(
        SimpleNamespace(
            artifact_kind="fresh_model_heartbeat_run",
            artifact_id=heartbeat_id,
        )
    )
    snapshot_id = f"fms1_{1:064x}"
    repository.values[snapshot_id] = {"data_as_of_date": "2026-07-24"}
    repository.store.descriptors.append(
        SimpleNamespace(artifact_kind="fresh_market_snapshot", artifact_id=snapshot_id)
    )
    return heartbeat_id


def _completed(payload, returncode=0, stderr=""):
    return SimpleNamespace(
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def test_launch_agent_plist_schema_and_security():
    value = manager.validate_template()
    assert value["Label"] == models.LAUNCH_AGENT_LABEL
    assert value["ProgramArguments"][:2] == ["/bin/zsh", "-lc"]
    assert Path(value["WorkingDirectory"]).is_absolute()
    assert value["RunAtLoad"] is True
    assert value["ProcessType"] == "Background"
    assert value["LowPriorityIO"] is True
    assert value["ThrottleInterval"] >= 300
    text = manager.TEMPLATE.read_text(encoding="utf-8").lower()
    assert "tushare_token" not in text
    assert "keepalive" not in text


def test_schedule_is_exactly_frozen():
    value = manager.validate_template()
    assert value["StartCalendarInterval"] == list(models.SCHEDULE)
    assert len(value["StartCalendarInterval"]) == 15
    assert {row["Weekday"] for row in value["StartCalendarInterval"]} == {
        1,
        2,
        3,
        4,
        5,
        6,
    }


def test_gui_domain_is_current_user(monkeypatch):
    monkeypatch.setattr(manager.os, "getuid", lambda: 501)
    assert manager._domain() == "gui/501"


def test_token_missing_is_legal_preflight_block(monkeypatch):
    monkeypatch.setattr(manager, "_login_token_available", lambda: False)
    monkeypatch.setattr(manager, "_python_ready", lambda: True)
    result = manager.preflight()
    assert result["status"] == "blocked"
    assert result["reason"] == "launch_context_token_unavailable"


def test_token_present_is_not_serialized(monkeypatch):
    monkeypatch.setattr(manager, "_login_token_available", lambda: True)
    monkeypatch.setattr(manager, "_python_ready", lambda: True)
    result = manager.preflight()
    assert result["token_available_in_launch_context"] is True
    assert "token" not in json.dumps(result).lower().replace(
        "token_available_in_launch_context", ""
    )


def test_atomic_lock_records_required_owner_fields(tmp_path):
    lock = tmp_path / "lock"
    result = service.acquire_lock(lock, "run-fresh-heartbeat")
    owner = json.loads((lock / "owner.json").read_text())
    assert result["lock_acquired"] is True
    assert {"pid", "started_at", "hostname", "command"} <= set(owner)
    service.release_lock(lock)
    assert not lock.exists()


def test_concurrent_lock_is_rejected(tmp_path):
    lock = tmp_path / "lock"
    lock.mkdir()
    (lock / "owner.json").write_text(
        json.dumps({"pid": os.getpid(), "command": "active"}),
        encoding="utf-8",
    )
    result = service.acquire_lock(lock, "second")
    assert result["status"] == "already_running"
    assert result["lock_acquired"] is False


def test_stale_lock_is_cleaned(tmp_path):
    lock = tmp_path / "lock"
    lock.mkdir()
    (lock / "owner.json").write_text(
        json.dumps({"pid": 99999999, "command": "stale"}),
        encoding="utf-8",
    )
    result = service.acquire_lock(lock, "replacement")
    assert result["lock_acquired"] is True
    assert result["stale_lock_removed"] is True
    service.release_lock(lock)


def test_trap_equivalent_finally_cleans_lock(monkeypatch, tmp_path):
    repository = FakeRepository()
    _add_fresh_state(repository)
    monkeypatch.setattr(service, "_runtime", lambda *args, **kwargs: (None, repository))

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("heartbeat", 1)

    with pytest.raises(subprocess.TimeoutExpired):
        service.run_scheduled_heartbeat(
            repository_root=tmp_path,
            work_root=tmp_path / "work",
            state_path=tmp_path / "status.json",
            history_path=tmp_path / "history.jsonl",
            lock_path=tmp_path / "lock",
            python_executable=Path("/python"),
            trigger="test",
            subprocess_runner=timeout,
        )
    assert not (tmp_path / "lock").exists()


def test_log_rotation_is_bounded(tmp_path):
    path = tmp_path / "fresh.log"
    path.write_bytes(b"x" * 20)
    assert service.rotate_log(path, maximum_bytes=10, keep=3) is True
    assert (tmp_path / "fresh.log.1").exists()
    for _ in range(5):
        path.write_bytes(b"x" * 20)
        service.rotate_log(path, maximum_bytes=10, keep=3)
    assert not (tmp_path / "fresh.log.4").exists()


def test_scheduler_status_contract_has_no_secret():
    payload = FreshHeartbeatSchedulerStatusV1(
        template_path="/repo/template.plist",
        installed_path="/home/LaunchAgents/agent.plist",
        template_checksum="a" * 64,
        installed_checksum="a" * 64,
        loaded=True,
        enabled=True,
        last_exit_status=0,
        last_run_at=None,
        last_success_at=None,
        consecutive_failures=0,
        next_expected_run=None,
        token_available_in_launch_context=True,
        repository_head_at_install="b" * 40,
    ).payload()
    assert payload["credential_persisted"] is False
    assert "tushare_token" not in json.dumps(payload).lower()


def test_successful_exact_replay_writes_structured_summary(monkeypatch, tmp_path):
    repository = FakeRepository()
    heartbeat_id = _add_fresh_state(repository)
    monkeypatch.setattr(service, "_runtime", lambda *args, **kwargs: (None, repository))
    result = service.run_scheduled_heartbeat(
        repository_root=tmp_path,
        work_root=tmp_path / "work",
        state_path=tmp_path / "status.json",
        history_path=tmp_path / "history.jsonl",
        lock_path=tmp_path / "lock",
        python_executable=Path("/python"),
        trigger="test",
        subprocess_runner=lambda *args, **kwargs: _completed(
            {
                "status": "exact_replay",
                "fresh_model_heartbeat_run_id": heartbeat_id,
                "execution_counts": {
                    "tushare_calls": 0,
                    "model_training_calls": 0,
                    "prediction_writes": 0,
                    "label_writes": 0,
                    "strategy_writes": 0,
                    "new_artifacts": 0,
                    "new_blobs": 0,
                },
            }
        ),
    )
    assert result["status"] == "exact_replay"
    assert result["tushare_call_count"] == 0
    assert result["model_training_count"] == 0
    assert result["prediction_count"] == 0
    assert result["mature_label_count"] == 0
    assert result["strategy_update_count"] == 0
    assert json.loads((tmp_path / "status.json").read_text())["last_exit_status"] == 0
    assert len((tmp_path / "history.jsonl").read_text().splitlines()) == 1


def test_same_operational_result_is_exact_existing(monkeypatch, tmp_path):
    repository = FakeRepository()
    heartbeat_id = _add_fresh_state(repository)
    monkeypatch.setattr(service, "_runtime", lambda *args, **kwargs: (None, repository))
    kwargs = {
        "repository_root": tmp_path,
        "work_root": tmp_path / "work",
        "state_path": tmp_path / "status.json",
        "history_path": tmp_path / "history.jsonl",
        "lock_path": tmp_path / "lock",
        "python_executable": Path("/python"),
        "trigger": "test",
        "subprocess_runner": lambda *args, **options: _completed(
            {
                "status": "exact_replay",
                "fresh_model_heartbeat_run_id": heartbeat_id,
                "execution_counts": {},
            }
        ),
    }
    first = service.run_scheduled_heartbeat(**kwargs)
    second = service.run_scheduled_heartbeat(**kwargs)
    assert first["new_artifacts"] == 1
    assert second["new_artifacts"] == 0
    assert second["new_blobs"] == 0
    assert second["exact_existing"] is True


def test_third_failure_notifies_once_and_recovery_notifies(monkeypatch, tmp_path):
    repository = FakeRepository()
    _add_fresh_state(repository)
    monkeypatch.setattr(service, "_runtime", lambda *args, **kwargs: (None, repository))
    notifications = []
    results = [
        _completed({"status": "blocked", "error_code": "network"}, 2, "network"),
        _completed({"status": "blocked", "error_code": "network"}, 2, "network"),
        _completed({"status": "blocked", "error_code": "network"}, 2, "network"),
        _completed({"status": "blocked", "error_code": "network"}, 2, "network"),
        _completed({"status": "exact_replay", "execution_counts": {}}, 0),
    ]

    def runner(*args, **kwargs):
        return results.pop(0)

    kwargs = {
        "repository_root": tmp_path,
        "work_root": tmp_path / "work",
        "state_path": tmp_path / "status.json",
        "history_path": tmp_path / "history.jsonl",
        "lock_path": tmp_path / "lock",
        "python_executable": Path("/python"),
        "trigger": "test",
        "subprocess_runner": runner,
        "notifier": lambda title, message: notifications.append((title, message)),
    }
    for _ in range(5):
        service.run_scheduled_heartbeat(**kwargs)
    assert sum("three consecutive" in message for _, message in notifications) == 1
    assert sum("recovered" in message for _, message in notifications) == 1


def test_accumulating_state_does_not_notify(monkeypatch, tmp_path):
    repository = FakeRepository()
    _add_fresh_state(repository)
    monkeypatch.setattr(service, "_runtime", lambda *args, **kwargs: (None, repository))
    notifications = []
    service.run_scheduled_heartbeat(
        repository_root=tmp_path,
        work_root=tmp_path / "work",
        state_path=tmp_path / "status.json",
        history_path=tmp_path / "history.jsonl",
        lock_path=tmp_path / "lock",
        python_executable=Path("/python"),
        trigger="test",
        subprocess_runner=lambda *args, **kwargs: _completed(
            {"status": "exact_replay", "execution_counts": {}}
        ),
        notifier=lambda title, message: notifications.append((title, message)),
    )
    assert notifications == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("TUSHARE_TOKEN missing", "credential_failure"),
        ("transport timeout", "network_failure"),
        ("calendar quality", "data_quality_failure"),
        ("LightGBM failed", "model_failure"),
        ("artifact store", "artifact_failure"),
        ("contract mismatch", "contract_failure"),
        ("unexpected", "unknown_failure"),
    ],
)
def test_failure_classification(text, expected):
    assert service.classify_failure(None, text) == expected


def test_install_uses_checksum_and_preserves_secret_boundary(monkeypatch, tmp_path):
    installed = tmp_path / "LaunchAgents/agent.plist"
    installed_wrapper = tmp_path / "support/bin/wrapper.sh"
    monkeypatch.setattr(manager, "INSTALLED", installed)
    monkeypatch.setattr(manager, "INSTALLED_WRAPPER", installed_wrapper)
    monkeypatch.setattr(manager, "LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(manager, "SUPPORT_ROOT", tmp_path / "support")
    monkeypatch.setattr(manager, "LOCK_PATH", tmp_path / "support/locks/lock")
    monkeypatch.setattr(manager, "WORK_ROOT", tmp_path / "support/work")
    monkeypatch.setattr(manager, "STDOUT_PATH", tmp_path / "logs/stdout.log")
    monkeypatch.setattr(manager, "STDERR_PATH", tmp_path / "logs/stderr.log")
    monkeypatch.setattr(manager, "HISTORY_PATH", tmp_path / "logs/history.jsonl")
    monkeypatch.setattr(manager, "_login_token_available", lambda: True)
    monkeypatch.setattr(manager, "_python_ready", lambda: True)
    result = manager.install()
    assert result["installed"] is True
    assert result["template_checksum"] == result["installed_checksum"]
    assert result["wrapper_template_checksum"] == result["installed_wrapper_checksum"]
    assert installed_wrapper.stat().st_mode & 0o700 == 0o700
    assert "tushare_token" not in installed.read_text().lower()


def test_uninstall_preserves_logs_and_artifacts(monkeypatch, tmp_path):
    installed = tmp_path / "agent.plist"
    installed.write_text("plist")
    installed_wrapper = tmp_path / "wrapper.sh"
    installed_wrapper.write_text("wrapper")
    log = tmp_path / "status.json"
    log.write_text("{}")
    monkeypatch.setattr(manager, "INSTALLED", installed)
    monkeypatch.setattr(manager, "INSTALLED_WRAPPER", installed_wrapper)
    monkeypatch.setattr(manager, "STATE_PATH", log)
    monkeypatch.setattr(manager, "_loaded", lambda: False)
    result = manager.uninstall(False)
    assert result["artifacts_deleted"] == 0
    assert result["logs_preserved"] is True
    assert log.exists()
    assert not installed_wrapper.exists()


def test_validate_requires_successful_launchd_execution(monkeypatch):
    monkeypatch.setattr(manager, "preflight", lambda: {"status": "passed"})
    healthy = {
        "installed": True,
        "loaded": True,
        "checksums_match": True,
        "wrapper_checksums_match": True,
        "local_status": {
            "last_launchd_run_at": "2026-07-24T17:00:00Z",
            "last_launchd_exit_status": 0,
        },
    }
    monkeypatch.setattr(manager, "status", lambda: healthy)
    assert manager.validate()["status"] == "valid"
    healthy["local_status"]["last_launchd_run_at"] = None
    healthy["local_status"]["last_launchd_exit_status"] = None
    result = manager.validate()
    assert result["status"] == "invalid"
    assert result["launchd_execution_verified"] is False


def test_cold_recovery_and_replay_have_zero_mutations(monkeypatch, tmp_path):
    repository = FakeRepository()
    heartbeat_id = _add_fresh_state(repository)
    scheduler_id = f"fhss1_{1:064x}"
    operational_id = f"fhor1_{1:064x}"
    repository.values[scheduler_id] = {"loaded": True}
    repository.values[operational_id] = {
        "fresh_model_heartbeat_run_id": heartbeat_id,
        "heartbeat_status": "fresh_evidence_accumulating",
    }
    repository.store.descriptors.extend(
        [
            SimpleNamespace(
                artifact_kind="fresh_heartbeat_scheduler_status",
                artifact_id=scheduler_id,
            ),
            SimpleNamespace(
                artifact_kind="fresh_heartbeat_operational_run",
                artifact_id=operational_id,
            ),
        ]
    )
    monkeypatch.setattr(service, "_runtime", lambda *args, **kwargs: (None, repository))
    state = tmp_path / "status.json"
    state.write_text(json.dumps({"loaded": True}))
    recovered = service.cold_recover(
        repository_root=tmp_path,
        work_root=tmp_path,
        state_path=state,
    )
    replay = service.replay_operational_run(
        repository_root=tmp_path,
        work_root=tmp_path,
    )
    assert recovered["status"] == "recovered"
    assert all(value == 0 for value in recovered["execution_counts"].values())
    assert replay["status"] == "exact_replay"
    assert all(value == 0 for value in replay["execution_counts"].values())


def test_new_artifact_kinds_are_registered():
    assert ArtifactKind.FRESH_HEARTBEAT_SCHEDULER_STATUS.value in KINDS
    assert ArtifactKind.FRESH_HEARTBEAT_OPERATIONAL_RUN.value in KINDS
    assert KINDS["fresh_heartbeat_scheduler_status"][1] == "fhss1_"
    assert KINDS["fresh_heartbeat_operational_run"][1] == "fhor1_"


def test_operational_artifacts_do_not_claim_market_data_authority(tmp_path):
    identity = {
        "schema_version": "fresh-heartbeat-scheduler-status-v1",
        "fresh_heartbeat_scheduler_status_id": "ignored",
        "launch_agent_label": models.LAUNCH_AGENT_LABEL,
        "promotion_writes": 0,
    }
    result = publish_artifact(
        tmp_path,
        "fresh_heartbeat_scheduler_status",
        identity,
        {"fresh_heartbeat_scheduler_status.json": identity},
    )
    assert result["artifact_kind"] == "fresh_heartbeat_scheduler_status"
