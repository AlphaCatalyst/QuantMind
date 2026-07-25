from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
OWNER_FILE = "owner.json"


class RuntimeTemporaryDirectoryError(RuntimeError):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


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


def _validated_child(root: Path, run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id) or run_id in {".", ".."}:
        raise RuntimeTemporaryDirectoryError("invalid runtime temporary run id")
    root = root.expanduser()
    if root.is_symlink():
        raise RuntimeTemporaryDirectoryError("runtime temporary root cannot be a symlink")
    root = root.resolve()
    child = root / run_id
    if child.parent != root:
        raise RuntimeTemporaryDirectoryError("runtime temporary path escaped root")
    return child


def create_runtime_tmp(root: Path, run_id: str, *, owner_pid: int) -> dict[str, Any]:
    child = _validated_child(root, run_id)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if child.exists() or child.is_symlink():
        raise RuntimeTemporaryDirectoryError("runtime temporary directory already exists")
    child.mkdir(mode=0o700)
    metadata = {
        "schema_version": "fresh-runtime-tmp-owner-v1",
        "run_id": run_id,
        "owner_pid": owner_pid,
        "created_at": _utcnow(),
    }
    (child / OWNER_FILE).write_text(
        json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(child / OWNER_FILE, 0o600)
    return {"created": True, "run_id": run_id}


def remove_runtime_tmp(root: Path, run_id: str) -> dict[str, Any]:
    child = _validated_child(root, run_id)
    if not child.exists():
        return {"removed": False, "run_id": run_id, "reason": "absent"}
    if child.is_symlink() or not child.is_dir():
        raise RuntimeTemporaryDirectoryError("runtime temporary child is unsafe")
    shutil.rmtree(child)
    return {"removed": True, "run_id": run_id}


def cleanup_stale_runtime_tmp(
    root: Path,
    *,
    scheduler_lock: Path,
    now: float | None = None,
    minimum_age_seconds: int = 24 * 60 * 60,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    clock = time.time() if now is None else now
    protected_run_id = None
    lock_owner = scheduler_lock / "owner.json"
    if lock_owner.is_file():
        try:
            owner = json.loads(lock_owner.read_text(encoding="utf-8"))
            if _pid_running(int(owner.get("pid", -1))):
                protected_run_id = owner.get("runtime_run_id")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            protected_run_id = "__unknown_live_lock__"
    scanned = stale = removed = failed = 0
    removed_names: list[str] = []
    for child in sorted(root.iterdir()):
        scanned += 1
        try:
            if child.is_symlink() or not child.is_dir() or not RUN_ID.fullmatch(child.name):
                continue
            metadata_path = child / OWNER_FILE
            if not metadata_path.is_file():
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("run_id") != child.name:
                continue
            pid = int(metadata.get("owner_pid", -1))
            age = clock - child.stat().st_mtime
            if _pid_running(pid) or age <= minimum_age_seconds:
                continue
            if protected_run_id in {child.name, "__unknown_live_lock__"}:
                continue
            stale += 1
            shutil.rmtree(child)
            removed += 1
            removed_names.append(child.name)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            failed += 1
    digest = hashlib.sha256(
        "\n".join(sorted(removed_names)).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "fresh-runtime-tmp-cleanup-status-v1",
        "scanned_count": scanned,
        "stale_count": stale,
        "removed_count": removed,
        "failed_count": failed,
        "removed_paths_hash": digest,
    }


def cleanup_owned_scheduler_lock(
    lock_path: Path, *, owner_pid: int, run_id: str
) -> dict[str, Any]:
    if not RUN_ID.fullmatch(run_id):
        raise RuntimeTemporaryDirectoryError("invalid runtime run id")
    if not lock_path.exists():
        return {"removed": False, "reason": "absent"}
    if lock_path.is_symlink() or not lock_path.is_dir():
        raise RuntimeTemporaryDirectoryError("scheduler lock path is unsafe")
    metadata_path = lock_path / "owner.json"
    try:
        owner = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeTemporaryDirectoryError("scheduler lock owner is unreadable") from exc
    if (
        int(owner.get("pid", -1)) != owner_pid
        or owner.get("runtime_run_id") != run_id
        or _pid_running(owner_pid)
    ):
        return {"removed": False, "reason": "owner_mismatch_or_live"}
    shutil.rmtree(lock_path)
    return {"removed": True, "reason": "dead_owned_lock"}
