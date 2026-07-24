#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime  # noqa: E402
from backend.services.engine.fresh_heartbeat_scheduler import (  # noqa: E402
    FreshHeartbeatSchedulerStatusV1,
    cold_recover,
    replay_operational_run,
    run_scheduled_heartbeat,
)
from backend.services.engine.fresh_heartbeat_scheduler.models import (  # noqa: E402
    LAUNCH_AGENT_LABEL,
    SCHEDULE,
)
from backend.services.engine.fresh_heartbeat_scheduler.service import (  # noqa: E402
    atomic_json,
    rotate_log,
)


HOME = Path.home()
TEMPLATE = ROOT / "deploy/launchd/com.quantmind.fresh-model-heartbeat.plist"
INSTALLED = HOME / "Library/LaunchAgents/com.quantmind.fresh-model-heartbeat.plist"
LOG_ROOT = HOME / "Library/Logs/QuantMind"
SUPPORT_ROOT = HOME / "Library/Application Support/QuantMind"
WRAPPER_TEMPLATE = ROOT / "tools/quantmind2/supervisor_fresh_heartbeat.sh"
INSTALLED_WRAPPER = SUPPORT_ROOT / "bin/supervisor_fresh_heartbeat.sh"
LOCK_PATH = SUPPORT_ROOT / "locks/fresh-heartbeat.lock"
STATE_PATH = LOG_ROOT / "fresh-heartbeat.status.json"
HISTORY_PATH = LOG_ROOT / "fresh-heartbeat.history.jsonl"
STDOUT_PATH = LOG_ROOT / "fresh-heartbeat.stdout.log"
STDERR_PATH = LOG_ROOT / "fresh-heartbeat.stderr.log"
WORK_ROOT = SUPPORT_ROOT / "fresh-heartbeat"
PYTHON_BIN = Path(
    "/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/.venv/bin/python"
)
LIBOMP_DIR = Path(
    "/Users/yj/Documents/Codex/2026-06-30/nih/work/AlphaQuant/third-party/runtime/libomp/libomp/22.1.8/lib"
)


class SchedulerError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], *, check: bool = False, env: dict | None = None):
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _loaded() -> bool:
    return _run(["/bin/launchctl", "print", f"{_domain()}/{LAUNCH_AGENT_LABEL}"]).returncode == 0


def _login_token_available() -> bool:
    result = _run(
        ["/bin/zsh", "-lc", '[[ -n "${TUSHARE_TOKEN:-}" ]]'],
        env=os.environ.copy(),
    )
    return result.returncode == 0


def _python_ready() -> bool:
    if not PYTHON_BIN.is_file():
        return False
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = (
        str(LIBOMP_DIR)
        + (f":{env['DYLD_LIBRARY_PATH']}" if env.get("DYLD_LIBRARY_PATH") else "")
    )
    result = _run(
        [
            str(PYTHON_BIN),
            "-c",
            "import pandas,numpy,pyarrow,lightgbm; print('ready')",
        ],
        env=env,
    )
    return result.returncode == 0 and result.stdout.strip() == "ready"


def _plist() -> dict[str, Any]:
    with TEMPLATE.open("rb") as handle:
        return plistlib.load(handle)


def validate_template() -> dict[str, Any]:
    value = _plist()
    required = {
        "Label",
        "ProgramArguments",
        "WorkingDirectory",
        "StartCalendarInterval",
        "RunAtLoad",
        "ProcessType",
        "LowPriorityIO",
        "ThrottleInterval",
        "StandardOutPath",
        "StandardErrorPath",
    }
    missing = sorted(required - set(value))
    if missing:
        raise SchedulerError(f"plist required keys missing: {missing}")
    if value["Label"] != LAUNCH_AGENT_LABEL:
        raise SchedulerError("LaunchAgent label mismatch")
    if value["ProgramArguments"][:2] != ["/bin/zsh", "-lc"]:
        raise SchedulerError("LaunchAgent must use /bin/zsh -lc")
    if "Library/Application Support/QuantMind/bin/supervisor_fresh_heartbeat.sh" not in value["ProgramArguments"][2]:
        raise SchedulerError("LaunchAgent must execute the installed operational wrapper")
    if not Path(value["WorkingDirectory"]).is_absolute():
        raise SchedulerError("WorkingDirectory must be absolute")
    if value["StartCalendarInterval"] != list(SCHEDULE):
        raise SchedulerError("LaunchAgent schedule mismatch")
    if value["ThrottleInterval"] < 300 or not value["RunAtLoad"]:
        raise SchedulerError("LaunchAgent throttle or RunAtLoad mismatch")
    serialized = TEMPLATE.read_text(encoding="utf-8").lower()
    if "tushare_token" in serialized or "<key>environmentvariables</key>" in serialized:
        raise SchedulerError("credential material is forbidden in plist")
    return value


def preflight() -> dict[str, Any]:
    value = validate_template()
    return {
        "status": "passed" if _login_token_available() and _python_ready() else "blocked",
        "reason": (
            None
            if _login_token_available() and _python_ready()
            else "launch_context_token_unavailable"
            if not _login_token_available()
            else "python_runtime_unavailable"
        ),
        "platform": sys.platform,
        "uid": os.getuid(),
        "gui_domain": _domain(),
        "token_available_in_launch_context": _login_token_available(),
        "python_ready": _python_ready(),
        "repository_root": str(ROOT),
        "template_path": str(TEMPLATE),
        "template_checksum": _sha256(TEMPLATE),
        "schedule_count": len(value["StartCalendarInterval"]),
    }


def render() -> dict[str, Any]:
    value = validate_template()
    return {
        "status": "rendered",
        "template_path": str(TEMPLATE),
        "template_checksum": _sha256(TEMPLATE),
        "label": value["Label"],
        "program_arguments": value["ProgramArguments"],
        "working_directory": value["WorkingDirectory"],
    }


def _ensure_operational_directories() -> None:
    for path in (
        INSTALLED.parent,
        LOG_ROOT,
        SUPPORT_ROOT,
        INSTALLED_WRAPPER.parent,
        LOCK_PATH.parent,
        WORK_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)
    for path in (STDOUT_PATH, STDERR_PATH, HISTORY_PATH):
        path.touch(exist_ok=True)


def install() -> dict[str, Any]:
    check = preflight()
    if check["status"] != "passed":
        return {
            "status": "blocked",
            "reason": check["reason"],
            "installed": False,
        }
    _ensure_operational_directories()
    temporary = INSTALLED.with_name(f".{INSTALLED.name}.{os.getpid()}.tmp")
    shutil.copyfile(TEMPLATE, temporary)
    os.chmod(temporary, 0o600)
    os.replace(temporary, INSTALLED)
    wrapper_temporary = INSTALLED_WRAPPER.with_name(
        f".{INSTALLED_WRAPPER.name}.{os.getpid()}.tmp"
    )
    shutil.copyfile(WRAPPER_TEMPLATE, wrapper_temporary)
    os.chmod(wrapper_temporary, 0o700)
    os.replace(wrapper_temporary, INSTALLED_WRAPPER)
    if _sha256(TEMPLATE) != _sha256(INSTALLED):
        raise SchedulerError("installed plist checksum mismatch")
    if _sha256(WRAPPER_TEMPLATE) != _sha256(INSTALLED_WRAPPER):
        raise SchedulerError("installed wrapper checksum mismatch")
    return {
        "status": "installed",
        "installed": True,
        "installed_path": str(INSTALLED),
        "template_checksum": _sha256(TEMPLATE),
        "installed_checksum": _sha256(INSTALLED),
        "installed_wrapper_path": str(INSTALLED_WRAPPER),
        "wrapper_template_checksum": _sha256(WRAPPER_TEMPLATE),
        "installed_wrapper_checksum": _sha256(INSTALLED_WRAPPER),
    }


def _next_runs(count: int = 12) -> list[str]:
    now = datetime.now().astimezone()
    rows = []
    for offset in range(0, 15):
        date = (now + timedelta(days=offset)).date()
        launch_weekday = date.weekday() + 1
        for item in SCHEDULE:
            if item["Weekday"] != launch_weekday:
                continue
            value = datetime(
                date.year,
                date.month,
                date.day,
                item["Hour"],
                item["Minute"],
                tzinfo=now.tzinfo,
            )
            if value > now:
                rows.append(value.isoformat())
    return sorted(rows)[:count]


def _publish_scheduler_status() -> dict[str, Any]:
    local = {}
    if STATE_PATH.exists():
        try:
            local = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            local = {}
    head = _run(["/usr/bin/git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True).stdout.strip()
    status = FreshHeartbeatSchedulerStatusV1(
        template_path=str(TEMPLATE),
        installed_path=str(INSTALLED),
        template_checksum=_sha256(TEMPLATE),
        installed_checksum=_sha256(INSTALLED),
        loaded=_loaded(),
        enabled=True,
        last_exit_status=local.get("last_exit_status"),
        last_run_at=local.get("last_run_at"),
        last_success_at=local.get("last_success_at"),
        consecutive_failures=int(local.get("consecutive_failures", 0)),
        next_expected_run=_next_runs(1)[0] if _next_runs(1) else None,
        token_available_in_launch_context=_login_token_available(),
        repository_head_at_install=head,
        latest_heartbeat_id=local.get("latest_heartbeat_id"),
    ).payload()
    _, repository = _runtime(ROOT, WORK_ROOT / "scheduler-status", None)
    receipt = repository.publish(
        "fresh_heartbeat_scheduler_status",
        status,
        {"fresh_heartbeat_scheduler_status.json": status},
        lineage=tuple(
            value for value in (status.get("latest_heartbeat_id"),) if value
        ),
    )
    return status | {
        "fresh_heartbeat_scheduler_status_id": receipt["artifact_id"],
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def load() -> dict[str, Any]:
    if not INSTALLED.is_file():
        raise SchedulerError("LaunchAgent is not installed")
    initial = {
        "schema_version": "fresh-heartbeat-scheduler-local-status-v1",
        "launch_agent_label": LAUNCH_AGENT_LABEL,
        "loaded": False,
        "enabled": True,
        "template_path": str(TEMPLATE),
        "installed_path": str(INSTALLED),
        "template_checksum": _sha256(TEMPLATE),
        "installed_checksum": _sha256(INSTALLED),
        "next_expected_run": _next_runs(1)[0] if _next_runs(1) else None,
        "token_available_in_launch_context": True,
        "repository_head_at_install": None,
        "fresh_heartbeat_scheduler_status_id": None,
        "last_exit_status": None,
        "last_run_at": None,
        "last_success_at": None,
        "last_launchd_run_at": None,
        "last_launchd_exit_status": None,
        "consecutive_failures": 0,
        "failure_notified": False,
        "candidate_statuses": {},
        "cohort_status": "fresh_evidence_accumulating",
        "credential_persisted": False,
    }
    if not STATE_PATH.exists():
        atomic_json(STATE_PATH, initial)
    _run(["/bin/launchctl", "enable", f"{_domain()}/{LAUNCH_AGENT_LABEL}"])
    if not _loaded():
        result = _run(["/bin/launchctl", "bootstrap", _domain(), str(INSTALLED)])
        if result.returncode != 0:
            raise SchedulerError("launchctl bootstrap failed")
    if not _loaded():
        raise SchedulerError("LaunchAgent did not enter GUI domain")
    status = _publish_scheduler_status()
    try:
        local = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        local = initial
    local |= {
        "loaded": True,
        "enabled": True,
        "template_path": str(TEMPLATE),
        "installed_path": str(INSTALLED),
        "template_checksum": _sha256(TEMPLATE),
        "installed_checksum": _sha256(INSTALLED),
        "next_expected_run": status["next_expected_run"],
        "token_available_in_launch_context": True,
        "repository_head_at_install": status["repository_head_at_install"],
        "fresh_heartbeat_scheduler_status_id": status[
            "fresh_heartbeat_scheduler_status_id"
        ],
        "credential_persisted": False,
    }
    atomic_json(STATE_PATH, local)
    return status | {"status": "loaded", "gui_domain": _domain()}


def unload() -> dict[str, Any]:
    if _loaded():
        result = _run(["/bin/launchctl", "bootout", f"{_domain()}/{LAUNCH_AGENT_LABEL}"])
        if result.returncode != 0:
            raise SchedulerError("launchctl bootout failed")
    return {"status": "unloaded", "loaded": _loaded(), "gui_domain": _domain()}


def uninstall(remove_operational_logs: bool = False) -> dict[str, Any]:
    unload()
    INSTALLED.unlink(missing_ok=True)
    INSTALLED_WRAPPER.unlink(missing_ok=True)
    if remove_operational_logs:
        for path in (
            STDOUT_PATH,
            STDERR_PATH,
            STATE_PATH,
            HISTORY_PATH,
            *LOG_ROOT.glob("fresh-heartbeat.*.log.*"),
        ):
            path.unlink(missing_ok=True)
    return {
        "status": "uninstalled",
        "installed": INSTALLED.exists(),
        "installed_wrapper": INSTALLED_WRAPPER.exists(),
        "logs_preserved": not remove_operational_logs,
        "artifacts_deleted": 0,
    }


def status() -> dict[str, Any]:
    local = (
        json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if STATE_PATH.exists()
        else None
    )
    return {
        "status": "loaded" if _loaded() else "not_loaded",
        "loaded": _loaded(),
        "enabled": _loaded(),
        "installed": INSTALLED.is_file(),
        "installed_wrapper": INSTALLED_WRAPPER.is_file(),
        "installed_path": str(INSTALLED),
        "template_checksum": _sha256(TEMPLATE),
        "installed_checksum": _sha256(INSTALLED) if INSTALLED.is_file() else None,
        "checksums_match": (
            INSTALLED.is_file() and _sha256(TEMPLATE) == _sha256(INSTALLED)
        ),
        "wrapper_checksums_match": (
            INSTALLED_WRAPPER.is_file()
            and _sha256(WRAPPER_TEMPLATE) == _sha256(INSTALLED_WRAPPER)
        ),
        "token_available_in_launch_context": _login_token_available(),
        "local_status": local,
        "next_expected_runs": _next_runs(),
    }


def validate() -> dict[str, Any]:
    check = preflight()
    current = status()
    local = current.get("local_status") or {}
    valid = (
        check["status"] == "passed"
        and current["installed"]
        and current["loaded"]
        and current["checksums_match"]
        and current["wrapper_checksums_match"]
        and local.get("last_launchd_run_at") is not None
        and local.get("last_launchd_exit_status") == 0
    )
    return {
        "status": "valid" if valid else "invalid",
        "valid": valid,
        "preflight": check,
        "scheduler": current,
        "launchd_execution_verified": (
            local.get("last_launchd_run_at") is not None
            and local.get("last_launchd_exit_status") == 0
        ),
    }


def run_now(trigger: str) -> dict[str, Any]:
    _ensure_operational_directories()
    rotate_log(STDOUT_PATH)
    rotate_log(STDERR_PATH)
    os.environ["DYLD_LIBRARY_PATH"] = (
        str(LIBOMP_DIR)
        + (
            f":{os.environ['DYLD_LIBRARY_PATH']}"
            if os.environ.get("DYLD_LIBRARY_PATH")
            else ""
        )
    )
    local = (
        json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if STATE_PATH.exists()
        else {}
    )
    result = run_scheduled_heartbeat(
        repository_root=ROOT,
        work_root=WORK_ROOT,
        state_path=STATE_PATH,
        history_path=HISTORY_PATH,
        lock_path=LOCK_PATH,
        python_executable=PYTHON_BIN,
        trigger=trigger,
        scheduler_status_id=local.get("fresh_heartbeat_scheduler_status_id"),
    )
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Manage QuantMind Fresh Heartbeat LaunchAgent")
    commands = value.add_subparsers(dest="command", required=True)
    for name in (
        "preflight",
        "render",
        "install",
        "load",
        "unload",
        "status",
        "validate",
        "show-next-runs",
        "cold-recover",
        "replay",
    ):
        commands.add_parser(name)
    uninstall_parser = commands.add_parser("uninstall")
    uninstall_parser.add_argument("--remove-operational-logs", action="store_true")
    run_parser = commands.add_parser("run-now")
    run_parser.add_argument("--trigger", default="manual")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight()
        elif args.command == "render":
            result = render()
        elif args.command == "install":
            result = install()
        elif args.command == "load":
            result = load()
        elif args.command == "unload":
            result = unload()
        elif args.command == "uninstall":
            result = uninstall(args.remove_operational_logs)
        elif args.command == "status":
            result = status()
        elif args.command == "validate":
            result = validate()
        elif args.command == "show-next-runs":
            result = {"status": "scheduled", "next_expected_runs": _next_runs()}
        elif args.command == "run-now":
            result = run_now(args.trigger)
        elif args.command == "cold-recover":
            result = cold_recover(
                repository_root=ROOT,
                work_root=WORK_ROOT / "recovery",
                state_path=STATE_PATH,
            )
        else:
            result = replay_operational_run(
                repository_root=ROOT,
                work_root=WORK_ROOT / "replay",
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0 if result.get("status") not in {"blocked", "invalid", "failed"} else 2
    except (OSError, SchedulerError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error_class": "contract_failure",
                    "safe_summary": str(exc)[:300],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
