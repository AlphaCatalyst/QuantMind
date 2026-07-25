from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from backend.services.engine.fresh_runtime_deployment.temporary_directory import (
    RuntimeTemporaryDirectoryError,
    cleanup_owned_scheduler_lock,
    cleanup_stale_runtime_tmp,
    create_runtime_tmp,
    remove_runtime_tmp,
)
from backend.services.engine.runtime_diagnostics import (
    LAUNCHCTL_WHITELIST,
    REDACTED,
    RuntimeDiagnosticRedactionGuardV1,
    safe_launchctl_status,
    whitelist_only,
)


REPOSITORY = Path(__file__).resolve().parents[3]


def test_redaction_guard_covers_canary_and_headers() -> None:
    canary = "TEST_CANARY_DO_NOT_USE_123456789012345678901234567890"
    raw = (
        f"TUSHARE_TOKEN={canary}\n"
        f"Authorization: Bearer {canary}\n"
        f"API_KEY={canary}\n"
        f"Bearer {canary}\n"
        "environment = { TOKEN = should-not-survive; }\n"
    )
    result = RuntimeDiagnosticRedactionGuardV1().redact(raw)
    assert canary not in result.text
    assert REDACTED in result.text
    assert result.redaction_count >= 4
    assert "authorization_header" in result.categories
    assert not hasattr(result, "secret_hash")


def test_launchctl_parser_emits_only_whitelist_and_no_raw_secret(
    tmp_path: Path,
) -> None:
    canary = "TEST_CANARY_DO_NOT_USE_123456789012345678901234567890"
    plist = tmp_path / "agent.plist"
    program = tmp_path / "entrypoint"
    plist.write_text("plist", encoding="utf-8")
    program.write_text("program", encoding="utf-8")
    raw = (
        "state = running\nruns = 4\npid = 321\nlast exit code = 0\n"
        f"environment = {{ TUSHARE_TOKEN = {canary}; }}\n"
    )
    result = safe_launchctl_status(
        raw=raw,
        returncode=0,
        label="com.quantmind.fresh-model-heartbeat",
        plist_path=plist,
        program_path=program,
    )
    safe = whitelist_only(result)
    assert tuple(safe) == LAUNCHCTL_WHITELIST
    assert safe["state"] == "running"
    assert safe["runs"] == 4
    assert safe["last_exit_code"] == 0
    assert safe["pid"] == 321
    assert canary not in json.dumps(result)


def test_launchctl_parse_failure_never_echoes_raw(tmp_path: Path) -> None:
    canary = "TEST_CANARY_DO_NOT_USE_123456789012345678901234567890"
    result = safe_launchctl_status(
        raw=canary,
        returncode=0,
        label="label",
        plist_path=tmp_path / "absent",
        program_path=None,
    )
    assert result["status"] == "diagnostic_parse_failed"
    assert canary not in json.dumps(result)


def test_runtime_tmp_contract_rejects_escape_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    with pytest.raises(RuntimeTemporaryDirectoryError):
        create_runtime_tmp(root, "../escape", owner_pid=os.getpid())
    root.mkdir()
    (root / "linked").symlink_to(tmp_path)
    with pytest.raises(RuntimeTemporaryDirectoryError):
        remove_runtime_tmp(root, "linked")


def test_runtime_tmp_create_and_remove(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    created = create_runtime_tmp(root, "run-1", owner_pid=os.getpid())
    child = root / "run-1"
    assert created["created"] is True
    assert child.stat().st_mode & 0o077 == 0
    assert json.loads((child / "owner.json").read_text())["owner_pid"] == os.getpid()
    assert remove_runtime_tmp(root, "run-1")["removed"] is True
    assert not child.exists()


def _age(path: Path, seconds: int) -> None:
    value = time.time() - seconds
    os.utime(path, (value, value))


def test_stale_cleanup_obeys_age_pid_and_scheduler_lock(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    lock = tmp_path / "locks/fresh-heartbeat.lock"
    create_runtime_tmp(root, "old-dead", owner_pid=99999999)
    create_runtime_tmp(root, "young-dead", owner_pid=99999998)
    create_runtime_tmp(root, "live", owner_pid=os.getpid())
    create_runtime_tmp(root, "lock-protected", owner_pid=99999997)
    for name in ("old-dead", "lock-protected"):
        _age(root / name, 25 * 60 * 60)
    lock.mkdir(parents=True)
    (lock / "owner.json").write_text(
        json.dumps({"pid": os.getpid(), "runtime_run_id": "lock-protected"})
    )
    result = cleanup_stale_runtime_tmp(root, scheduler_lock=lock)
    assert result["scanned_count"] == 4
    assert result["stale_count"] == result["removed_count"] == 1
    assert result["failed_count"] == 0
    assert not (root / "old-dead").exists()
    assert (root / "young-dead").exists()
    assert (root / "live").exists()
    assert (root / "lock-protected").exists()
    assert "old-dead" not in json.dumps(result)


def test_owned_dead_scheduler_lock_cleanup_is_exact(tmp_path: Path) -> None:
    lock = tmp_path / "fresh-heartbeat.lock"
    lock.mkdir()
    (lock / "owner.json").write_text(
        json.dumps({"pid": 99999996, "runtime_run_id": "run-1"})
    )
    mismatch = cleanup_owned_scheduler_lock(
        lock, owner_pid=99999996, run_id="other-run"
    )
    assert mismatch["removed"] is False
    result = cleanup_owned_scheduler_lock(
        lock, owner_pid=99999996, run_id="run-1"
    )
    assert result["removed"] is True
    assert not lock.exists()


def _fake_runtime(tmp_path: Path, *, mode: str) -> tuple[Path, dict[str, str]]:
    home = tmp_path / "home"
    runtime = home / "Library/Application Support/QuantMind"
    (runtime / "config").mkdir(parents=True)
    (runtime / "config/runtime.json").write_text("{}")
    (runtime / "runtime/current-app/tools/quantmind2").mkdir(parents=True)
    (runtime / "runtime/current-app/tools/quantmind2/manage_fresh_runtime_deployment.py").write_text(
        "# fixture\n"
    )
    binary = runtime / "runtime/current-env/bin/python"
    binary.parent.mkdir(parents=True)
    binary.write_text(
        """#!/bin/sh
set -eu
case "$*" in
  *cleanup-stale-runtime-tmp*) echo '{"removed_count":0}' ;;
  *create-runtime-tmp*)
    previous=""
    run_id=""
    for argument in "$@"; do
      if [ "$previous" = "--run-id" ]; then run_id="$argument"; fi
      previous="$argument"
    done
    mkdir -p "$HOME/Library/Application Support/QuantMind/state/tmp/$run_id"
    ;;
  *cleanup-runtime-tmp*)
    previous=""
    run_id=""
    for argument in "$@"; do
      if [ "$previous" = "--run-id" ]; then run_id="$argument"; fi
      previous="$argument"
    done
    rm -rf "$HOME/Library/Application Support/QuantMind/state/tmp/$run_id"
    echo '{"removed":true}'
    ;;
  *run-now*)
    if [ "${QM2_TEST_CHILD_MODE:-success}" = "signal" ]; then exec sleep 30; fi
    if [ "${QM2_TEST_CHILD_MODE:-success}" = "failure" ]; then exit 37; fi
    echo '{"status":"exact_replay"}'
    ;;
esac
""",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TUSHARE_TOKEN": "TEST_CANARY_DO_NOT_USE_123456789",
            "QM2_TEST_CHILD_MODE": mode,
        }
    )
    return runtime, env


@pytest.mark.parametrize(("mode", "expected"), (("success", 0), ("failure", 37)))
def test_entrypoint_cleans_tmp_and_propagates_exit(
    tmp_path: Path, mode: str, expected: int
) -> None:
    runtime, env = _fake_runtime(tmp_path, mode=mode)
    result = subprocess.run(
        ["/bin/sh", str(REPOSITORY / "tools/quantmind2/deployed_fresh_heartbeat.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == expected
    assert list((runtime / "state/tmp").iterdir()) == []
    assert "TEST_CANARY" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("sig", "expected"), ((signal.SIGTERM, 143), (signal.SIGINT, 130))
)
def test_entrypoint_signal_cleans_tmp(
    tmp_path: Path, sig: signal.Signals, expected: int
) -> None:
    runtime, env = _fake_runtime(tmp_path, mode="signal")
    process = subprocess.Popen(
        ["/bin/sh", str(REPOSITORY / "tools/quantmind2/deployed_fresh_heartbeat.sh")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        root = runtime / "state/tmp"
        if root.exists() and list(root.iterdir()):
            break
        time.sleep(0.05)
    process.send_signal(sig)
    process.communicate(timeout=5)
    assert process.returncode == expected
    assert list((runtime / "state/tmp").iterdir()) == []


def test_entrypoint_no_longer_execs_heartbeat() -> None:
    text = (
        REPOSITORY / "tools/quantmind2/deployed_fresh_heartbeat.sh"
    ).read_text(encoding="utf-8")
    assert "exec \"${PYTHON}\"" not in text
    assert "trap cleanup_runtime_tmp EXIT" in text
    assert 'exit "${heartbeat_rc}"' in text
