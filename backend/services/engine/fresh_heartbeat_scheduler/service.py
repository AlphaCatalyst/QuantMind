from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime

from .models import LAUNCH_AGENT_LABEL
from backend.services.engine.runtime_diagnostics import (
    RuntimeDiagnosticRedactionGuardV1,
)


MAX_LOG_BYTES = 10 * 1024 * 1024
MAX_LOG_FILES = 10
TERMINAL_CANDIDATE_STATES = {
    "fresh_supported",
    "fresh_rejected",
    "fresh_inconclusive",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def rotate_log(path: Path, *, maximum_bytes: int = MAX_LOG_BYTES, keep: int = MAX_LOG_FILES) -> bool:
    if not path.exists() or path.stat().st_size < maximum_bytes:
        return False
    oldest = path.with_name(f"{path.name}.{keep}")
    oldest.unlink(missing_ok=True)
    for index in range(keep - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            os.replace(source, path.with_name(f"{path.name}.{index + 1}"))
    os.replace(path, path.with_name(f"{path.name}.1"))
    return True


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(lock_path: Path, command: str) -> dict[str, Any]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stale_removed = False
    try:
        lock_path.mkdir()
    except FileExistsError:
        metadata_path = lock_path / "owner.json"
        try:
            owner = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            owner = {}
        if _pid_running(int(owner.get("pid", -1))):
            return {"status": "already_running", "owner": owner, "lock_acquired": False}
        shutil.rmtree(lock_path)
        stale_removed = True
        lock_path.mkdir()
    owner = {
        "pid": os.getpid(),
        "started_at": utcnow(),
        "hostname": socket.gethostname(),
        "command": command,
        "runtime_run_id": os.environ.get("QM2_RUNTIME_RUN_ID"),
    }
    atomic_json(lock_path / "owner.json", owner)
    return {
        "status": "acquired",
        "owner": owner,
        "lock_acquired": True,
        "stale_lock_removed": stale_removed,
    }


def release_lock(lock_path: Path) -> None:
    if lock_path.exists():
        shutil.rmtree(lock_path)


def classify_failure(error_code: str | None, stderr: str) -> str:
    text = f"{error_code or ''} {stderr}".lower()
    if "token" in text or "credential" in text:
        return "credential_failure"
    if "transport" in text or "network" in text or "timeout" in text:
        return "network_failure"
    if "quality" in text or "schema" in text or "calendar" in text:
        return "data_quality_failure"
    if "lightgbm" in text or "model" in text:
        return "model_failure"
    if "artifact" in text or "store" in text:
        return "artifact_failure"
    if "contract" in text or "mismatch" in text:
        return "contract_failure"
    return "unknown_failure"


def _notify(title: str, message: str, runner: Callable[..., Any] = subprocess.run) -> None:
    safe_title = title.replace('"', "'")[:120]
    safe_message = message.replace('"', "'").replace("\n", " ")[:240]
    runner(
        [
            "/usr/bin/osascript",
            "-e",
            f'display notification "{safe_message}" with title "{safe_title}"',
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _latest_trade_date(repository) -> str | None:
    dates = []
    for descriptor in repository.store.list_by_kind("fresh_market_snapshot"):
        value = repository.identity(descriptor.artifact_id).get("data_as_of_date")
        if value:
            dates.append(value)
    return max(dates) if dates else None


def _fresh_state(repository) -> tuple[dict[str, str], str, str | None]:
    assessments: dict[str, tuple[str, str]] = {}
    for descriptor in repository.store.list_by_kind("fresh_model_candidate_assessment"):
        value = repository.identity(descriptor.artifact_id)
        assessments[value["candidate_id"]] = (descriptor.artifact_id, value["status"])
    candidate_statuses = {
        candidate_id: status for candidate_id, (_, status) in sorted(assessments.items())
    }
    heartbeats = []
    for descriptor in repository.store.list_by_kind("fresh_model_heartbeat_run"):
        value = repository.identity(descriptor.artifact_id)
        heartbeats.append(value | {"artifact_id": descriptor.artifact_id})
    latest = max(
        heartbeats,
        key=lambda row: (row.get("data_as_of_date") or "", row["artifact_id"]),
        default=None,
    )
    return (
        candidate_statuses,
        latest.get("status", "fresh_locked") if latest else "fresh_locked",
        latest["artifact_id"] if latest else None,
    )


def _publish_operational_run(
    repository,
    *,
    scheduler_status_id: str | None,
    heartbeat_id: str | None,
    heartbeat_status: str,
    exit_code: int,
    candidate_statuses: dict[str, str],
    execution_counts: dict[str, int],
    error_class: str | None,
) -> dict[str, Any]:
    identity = {
        "schema_version": "fresh-heartbeat-operational-run-v1",
        "launch_agent_label": LAUNCH_AGENT_LABEL,
        "scheduler_status_id": scheduler_status_id,
        "fresh_model_heartbeat_run_id": heartbeat_id,
        "heartbeat_status": heartbeat_status,
        "exit_code": exit_code,
        "candidate_statuses": candidate_statuses,
        "cohort_status": heartbeat_status,
        "execution_counts": execution_counts,
        "error_class": error_class,
        "credential_source": "login_shell_environment_only",
        "credential_persisted": False,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    receipt = repository.publish(
        "fresh_heartbeat_operational_run",
        identity,
        {"fresh_heartbeat_operational_run.json": identity},
        lineage=tuple(
            value for value in (scheduler_status_id, heartbeat_id) if value
        ),
    )
    return {
        "fresh_heartbeat_operational_run_id": receipt["artifact_id"],
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
        "exact_existing": receipt["exact_existing"],
    }


def run_scheduled_heartbeat(
    *,
    repository_root: Path,
    work_root: Path,
    state_path: Path,
    history_path: Path,
    lock_path: Path,
    python_executable: Path,
    trigger: str,
    scheduler_status_id: str | None = None,
    store_root: Path | None = None,
    subprocess_runner: Callable[..., Any] = subprocess.run,
    notifier: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    started = utcnow()
    clock = time.monotonic()
    lock = acquire_lock(lock_path, "run-fresh-heartbeat")
    if not lock["lock_acquired"]:
        return {
            "schema_version": "fresh-heartbeat-operational-summary-v1",
            "run_id": None,
            "triggered_at": started,
            "started_at": started,
            "finished_at": started,
            "duration_seconds": 0.0,
            "exit_code": 0,
            "status": "already_running",
            "error_class": None,
            "scheduler_writes": 0,
            "new_artifacts": 0,
            "new_blobs": 0,
        }
    notify = notifier or (lambda title, message: _notify(title, message))
    try:
        _, repository = _runtime(repository_root, work_root, store_root)
        before_date = _latest_trade_date(repository)
        before_candidates, before_cohort, before_heartbeat = _fresh_state(repository)
        previous = {}
        if state_path.exists():
            try:
                previous = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = {}
        command = [
            str(python_executable),
            str(repository_root / "tools/quantmind2/run_autonomous_research_supervisor.py"),
            "--work-root",
            str(work_root / "heartbeat"),
            "run-fresh-heartbeat",
        ]
        completed = subprocess_runner(
            command,
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60 * 60,
        )
        guard = RuntimeDiagnosticRedactionGuardV1()
        stdout_result = guard.redact(completed.stdout.strip())
        stderr_result = guard.redact(completed.stderr.strip())
        stdout = stdout_result.text
        stderr = stderr_result.text
        try:
            result = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            result = {}
        exit_code = int(completed.returncode)
        status = str(result.get("status") or ("failed" if exit_code else "unknown"))
        error_class = (
            classify_failure(result.get("error_code"), stderr or result.get("safe_summary", ""))
            if exit_code
            else None
        )
        after_date = _latest_trade_date(repository)
        candidates, cohort_status, heartbeat_id = _fresh_state(repository)
        counts = {
            key: int(value)
            for key, value in result.get("execution_counts", {}).items()
            if isinstance(value, (int, float))
        }
        failed = exit_code != 0 or status in {"blocked", "fresh_data_blocked"}
        failures = int(previous.get("consecutive_failures", 0)) + 1 if failed else 0
        failure_notified = bool(previous.get("failure_notified", False))
        if failures >= 3 and not failure_notified:
            notify("QuantMind Fresh Heartbeat", "Fresh heartbeat failed three consecutive times.")
            failure_notified = True
        if not failed and int(previous.get("consecutive_failures", 0)) > 0:
            notify("QuantMind Fresh Heartbeat", "Fresh heartbeat recovered.")
            failure_notified = False
        for candidate_id, candidate_status in candidates.items():
            if (
                candidate_status in TERMINAL_CANDIDATE_STATES
                and before_candidates.get(candidate_id) != candidate_status
            ):
                notify(
                    "QuantMind Fresh Candidate",
                    f"Candidate status changed to {candidate_status}.",
                )
        finished = utcnow()
        summary = {
            "schema_version": "fresh-heartbeat-operational-summary-v1",
            "run_id": heartbeat_id or before_heartbeat,
            "trigger": trigger,
            "triggered_at": started,
            "started_at": started,
            "finished_at": finished,
            "duration_seconds": round(time.monotonic() - clock, 3),
            "exit_code": exit_code,
            "status": status,
            "latest_stored_trade_date_before": before_date,
            "latest_available_trade_date": result.get("data_as_of_date") or after_date,
            "latest_stored_trade_date_after": after_date,
            "tushare_call_count": counts.get("tushare_calls", 0),
            "model_training_count": counts.get("model_training_calls", 0),
            "prediction_count": counts.get("prediction_writes", 0),
            "mature_label_count": counts.get("label_writes", 0),
            "strategy_update_count": counts.get("strategy_writes", 0),
            "candidate_statuses": candidates,
            "cohort_status": cohort_status,
            "error_class": error_class,
            "consecutive_failures": failures,
            "fresh_model_heartbeat_run_id": heartbeat_id,
            "fresh_heartbeat_scheduler_status_id": scheduler_status_id,
            "credential_persisted": False,
            "registry_writes": 0,
            "promotion_writes": 0,
            "redaction_count": (
                stdout_result.redaction_count + stderr_result.redaction_count
            ),
            "redaction_event_categories": sorted(
                set(stdout_result.categories) | set(stderr_result.categories)
            ),
        }
        operational = _publish_operational_run(
            repository,
            scheduler_status_id=scheduler_status_id,
            heartbeat_id=heartbeat_id,
            heartbeat_status=cohort_status,
            exit_code=exit_code,
            candidate_statuses=candidates,
            execution_counts=counts,
            error_class=error_class,
        )
        summary |= operational
        local_status = previous | {
            "schema_version": "fresh-heartbeat-scheduler-local-status-v1",
            "launch_agent_label": LAUNCH_AGENT_LABEL,
            "last_exit_status": exit_code,
            "last_run_at": finished,
            "last_success_at": (
                previous.get("last_success_at") if failed else finished
            ),
            "last_launchd_run_at": (
                finished
                if trigger == "launchd"
                else previous.get("last_launchd_run_at")
            ),
            "last_launchd_exit_status": (
                exit_code
                if trigger == "launchd"
                else previous.get("last_launchd_exit_status")
            ),
            "consecutive_failures": failures,
            "failure_notified": failure_notified,
            "candidate_statuses": candidates,
            "cohort_status": cohort_status,
            "latest_heartbeat_id": heartbeat_id,
            "latest_operational_run_id": operational[
                "fresh_heartbeat_operational_run_id"
            ],
            "credential_persisted": False,
            "redaction_count": (
                stdout_result.redaction_count + stderr_result.redaction_count
            ),
            "redaction_event_categories": sorted(
                set(stdout_result.categories) | set(stderr_result.categories)
            ),
        }
        atomic_json(state_path, local_status)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n")
        return summary
    finally:
        release_lock(lock_path)


def cold_recover(
    *,
    repository_root: Path,
    work_root: Path,
    state_path: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    local = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    scheduler = [
        repository.identity(row.artifact_id) | {"artifact_id": row.artifact_id}
        for row in repository.store.list_by_kind("fresh_heartbeat_scheduler_status")
    ]
    operational = [
        repository.identity(row.artifact_id) | {"artifact_id": row.artifact_id}
        for row in repository.store.list_by_kind("fresh_heartbeat_operational_run")
    ]
    candidates, cohort, heartbeat = _fresh_state(repository)
    return {
        "status": "recovered",
        "scheduler_status": scheduler[-1] if scheduler else None,
        "local_status": local,
        "latest_operational_run": operational[-1] if operational else None,
        "fresh_model_heartbeat_run_id": heartbeat,
        "candidate_statuses": candidates,
        "cohort_status": cohort,
        "execution_counts": {
            "launchctl_mutations": 0,
            "tushare_calls": 0,
            "network_calls": 0,
            "model_training_calls": 0,
            "prediction_writes": 0,
            "label_writes": 0,
            "strategy_writes": 0,
            "scheduler_writes": 0,
            "new_artifacts": 0,
            "new_blobs": 0,
        },
    }


def replay_operational_run(
    *, repository_root: Path, work_root: Path, store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    rows = repository.store.list_by_kind("fresh_heartbeat_operational_run")
    if not rows:
        raise RuntimeError("FRESH_HEARTBEAT_OPERATIONAL_RUN_ABSENT")
    latest = repository.identity(rows[-1].artifact_id)
    return latest | {
        "fresh_heartbeat_operational_run_id": rows[-1].artifact_id,
        "status": "exact_replay",
        "execution_counts": {
            "launchctl_mutations": 0,
            "tushare_calls": 0,
            "network_calls": 0,
            "model_training_calls": 0,
            "prediction_writes": 0,
            "label_writes": 0,
            "strategy_writes": 0,
            "scheduler_writes": 0,
            "new_artifacts": 0,
            "new_blobs": 0,
        },
    }
