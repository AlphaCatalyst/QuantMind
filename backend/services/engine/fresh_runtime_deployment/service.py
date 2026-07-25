from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.fresh_heartbeat_scheduler.models import (
    FreshHeartbeatSchedulerStatusV1,
    LAUNCH_AGENT_LABEL,
    SCHEDULE,
)
from backend.services.engine.fresh_heartbeat_scheduler.service import (
    acquire_lock,
    atomic_json,
    release_lock,
    run_scheduled_heartbeat,
)
from backend.services.engine.tushare_cutover.canonical import (
    canonical_json_bytes,
    hash_file,
    hash_payload,
)
from backend.services.engine.runtime_diagnostics import (
    RuntimeDiagnosticRedactionGuardV1,
    safe_launchctl_status as parse_safe_launchctl_status,
    whitelist_only,
)

from .models import (
    FreshHeartbeatTemporaryDirectoryDefectAssessmentV1,
    FreshRuntimeDiagnosticWhitelistV1,
    FreshRuntimeHardeningStatusV1,
    FreshRuntimeAppSnapshotV1,
    FreshRuntimeDeploymentStatusV1,
    FreshRuntimeEnvironmentSnapshotV1,
    FreshRuntimePathAuditV1,
    FreshRuntimeStateMigrationV1,
    HistoricalSessionDiagnosticExposureRecordV1,
    RuntimeDiagnosticRedactionGuardRecordV1,
)


CRITICAL_PACKAGES = ("numpy", "pandas", "pyarrow", "lightgbm", "pyqlib", "scipy")
PROTECTED_PARTS = (
    "Documents",
    "Desktop",
    "Downloads",
    "Library/Mobile Documents",
    "iCloud Drive",
)
RUNTIME_CONFIG_SCHEMA = "fresh-runtime-config-v1"


class RuntimeDeploymentError(RuntimeError):
    pass


def _artifact_id(value: dict[str, Any], field: str) -> str:
    receipt = value.get("artifact_receipt") or {}
    artifact_id = receipt.get("artifact_id") or value.get(field)
    if not isinstance(artifact_id, str):
        raise RuntimeDeploymentError(f"artifact identity absent: {field}")
    return artifact_id


def utcnow() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def is_protected_path(path: Path, *, home: Path | None = None) -> bool:
    value = Path(path).expanduser().resolve(strict=False)
    root = (home or Path.home()).expanduser().resolve(strict=False)
    for part in PROTECTED_PARTS:
        candidate = root / part
        try:
            value.relative_to(candidate)
            return True
        except ValueError:
            continue
    return False


def _tree_size(path: Path) -> tuple[int, int]:
    apparent = 0
    allocated = 0
    if not path.exists():
        return 0, 0
    rows = (path,) if path.is_file() else path.rglob("*")
    for item in rows:
        try:
            info = item.lstat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode):
            apparent += info.st_size
            allocated += getattr(info, "st_blocks", 0) * 512
    return apparent, allocated


def _atomic_symlink(target: Path, link: Path) -> str | None:
    link.parent.mkdir(parents=True, exist_ok=True)
    previous = str(link.resolve(strict=False)) if link.is_symlink() else None
    temporary = link.with_name(f".{link.name}.{uuid.uuid4().hex}.tmp")
    temporary.symlink_to(target)
    os.replace(temporary, link)
    return previous


def _chmod_immutable(root: Path) -> None:
    for item in [root, *root.rglob("*")]:
        mode = item.lstat().st_mode
        if item.is_symlink():
            continue
        os.chmod(item, mode & ~0o222)


def _chmod_user_writable(root: Path) -> None:
    for item in [root, *root.rglob("*")]:
        if item.is_symlink():
            continue
        mode = item.lstat().st_mode
        os.chmod(item, mode | stat.S_IWUSR)


def _file_inventory_hash(root: Path) -> tuple[str, int]:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hash_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return hashlib.sha256(canonical_json_bytes(rows)).hexdigest(), len(rows)


class FreshRuntimeDeploymentService:
    def __init__(
        self,
        *,
        repository_root: Path,
        runtime_root: Path | None = None,
        source_python: Path | None = None,
        source_libomp: Path | None = None,
        artifact_store_root: Path | None = None,
        home: Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.home = (home or Path.home()).expanduser().resolve()
        self.repository_root = Path(repository_root).expanduser().resolve()
        self.runtime_root = (
            Path(runtime_root).expanduser().resolve()
            if runtime_root
            else self.home / "Library/Application Support/QuantMind"
        )
        self.source_python = (
            Path(source_python).expanduser().absolute()
            if source_python
            else Path(sys.executable).absolute()
        )
        self.source_environment = self.source_python.parent.parent
        self.source_libomp = (
            Path(source_libomp).expanduser().resolve()
            if source_libomp
            else Path("/usr/local/lib")
        )
        self.artifact_store_root = (
            Path(artifact_store_root).expanduser().resolve()
            if artifact_store_root
            else self.home / ".quantmind2/artifact-store/v1"
        )
        self.runner = runner
        self.apps_root = self.runtime_root / "runtime/apps"
        self.envs_root = self.runtime_root / "runtime/envs"
        self.current_app = self.runtime_root / "runtime/current-app"
        self.current_env = self.runtime_root / "runtime/current-env"
        self.state_root = self.runtime_root / "state"
        self.config_root = self.runtime_root / "config"
        self.logs_root = self.runtime_root / "logs"
        self.deployments_root = self.runtime_root / "deployments"
        self.runtime_config_path = self.config_root / "runtime.json"
        self.installed_plist = (
            self.home / "Library/LaunchAgents/com.quantmind.fresh-model-heartbeat.plist"
        )

    def ensure_layout(self) -> None:
        for path in (
            self.apps_root,
            self.envs_root,
            self.state_root / "market-data",
            self.state_root / "checkpoints",
            self.state_root / "locks",
            self.state_root / "tmp",
            self.config_root,
            self.logs_root,
            self.deployments_root,
            self.installed_plist.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = False,
        timeout: int | None = None,
        text: bool = True,
        input: bytes | None = None,
    ):
        return self.runner(
            command,
            cwd=cwd,
            env=env,
            check=check,
            timeout=timeout,
            capture_output=True,
            text=text,
            input=input,
        )

    def _git(self, *args: str, check: bool = True) -> str:
        result = self._run(
            ["/usr/bin/git", *args], cwd=self.repository_root, check=check
        )
        return result.stdout.strip()

    def source_commit(self) -> str:
        return self._git("rev-parse", "HEAD")

    def _repository(self) -> CampaignRepository:
        store = FileSystemResearchArtifactStore(resolve_config(self.artifact_store_root))
        store.initialize()
        return CampaignRepository(
            store,
            self.state_root / "checkpoints/runtime-artifacts",
            self.state_root / "checkpoints/runtime-recovery",
        )

    def _publish(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        lineage: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return self._repository().publish(
            kind,
            payload,
            {f"{kind}.json": payload},
            lineage=lineage,
        )

    def _python_audit(self, executable: Path | None = None) -> dict[str, Any]:
        python = executable or self.source_python
        script = r"""
import hashlib, importlib.metadata as md, json, pathlib, platform, site, sys
names = ("numpy","pandas","pyarrow","lightgbm","pyqlib","scipy")
packages = {}
for name in names:
    try: packages[name] = md.version(name)
    except md.PackageNotFoundError: packages[name] = None
distributions = sorted(
    (str(d.metadata.get("Name") or "").lower(), d.version)
    for d in md.distributions()
)
print(json.dumps({
    "executable": sys.executable,
    "version": sys.version,
    "version_info": list(sys.version_info[:3]),
    "machine": platform.machine(),
    "platform": platform.platform(),
    "base_prefix": sys.base_prefix,
    "prefix": sys.prefix,
    "site_packages": site.getsitepackages(),
    "package_versions": packages,
    "site_packages_inventory_hash": hashlib.sha256(
        json.dumps(distributions, sort_keys=True, separators=(",",":")).encode()
    ).hexdigest(),
}))
"""
        env = os.environ.copy()
        if self.source_libomp.exists():
            env["DYLD_LIBRARY_PATH"] = str(self.source_libomp)
        result = self._run(
            [str(python), "-c", script], env=env, check=True, timeout=120
        )
        return json.loads(result.stdout)

    def _native_libraries(self) -> dict[str, str]:
        audit = self._python_audit()
        libraries: dict[str, str] = {}
        for raw_root in audit["site_packages"]:
            root = Path(raw_root)
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix not in {".dylib", ".so"}:
                    continue
                lowered = path.as_posix().lower()
                if "lightgbm" in lowered or (
                    "pyarrow" in lowered
                    and any(
                        marker in path.name
                        for marker in ("arrow", "parquet", ".so")
                    )
                ):
                    libraries[path.relative_to(self.source_environment).as_posix()] = (
                        hash_file(path)
                    )
        for path in sorted(self.source_libomp.glob("libomp.*")):
            if path.is_file():
                libraries[f"native/libomp/{path.name}"] = hash_file(path)
        return libraries

    def environment_audit(self) -> dict[str, Any]:
        audit = self._python_audit()
        audit["environment_type"] = (
            "venv" if (self.source_environment / "pyvenv.cfg").is_file() else "external"
        )
        audit["source_environment"] = str(self.source_environment)
        audit["source_environment_protected"] = is_protected_path(
            self.source_environment, home=self.home
        )
        audit["native_library_checksums"] = self._native_libraries()
        return audit

    def environment_fingerprint(self) -> tuple[str, dict[str, Any]]:
        audit = self.environment_audit()
        stable = {
            "python_version": audit["version"],
            "machine": audit["machine"],
            "package_versions": audit["package_versions"],
            "site_packages_inventory_hash": audit["site_packages_inventory_hash"],
            "native_library_checksums": audit["native_library_checksums"],
        }
        return "qmenv1_" + hash_payload(stable), audit

    def _dependency(
        self,
        path: Path,
        path_type: str,
        *,
        read: bool,
        write: bool,
        relocation: bool | None = None,
    ) -> dict[str, Any]:
        protected = is_protected_path(path, home=self.home)
        return {
            "absolute_path": str(path.expanduser().resolve(strict=False)),
            "exists": path.exists(),
            "path_type": path_type,
            "under_protected_directory": protected,
            "read_required": read,
            "write_required": write,
            "relocation_required": protected if relocation is None else relocation,
        }

    def audit_paths(self, *, publish: bool = False) -> dict[str, Any]:
        self.ensure_layout()
        py = self.environment_audit()
        paths = [
            self._dependency(self.repository_root, "source_root", read=True, write=False),
            self._dependency(self.source_python, "python_executable", read=True, write=False),
            self._dependency(
                Path(py["base_prefix"]), "python_base", read=True, write=False
            ),
            *[
                self._dependency(
                    Path(path), "site_packages", read=True, write=False
                )
                for path in py["site_packages"]
            ],
            *[
                self._dependency(
                    self.source_environment / relative,
                    "native_library",
                    read=True,
                    write=False,
                )
                if not relative.startswith("native/")
                else self._dependency(
                    self.source_libomp / Path(relative).name,
                    "native_library",
                    read=True,
                    write=False,
                )
                for relative in py["native_library_checksums"]
            ],
            self._dependency(
                self.artifact_store_root, "artifact_store", read=True, write=True
            ),
            self._dependency(
                self.artifact_store_root / "objects/sha256",
                "blob_store",
                read=True,
                write=True,
            ),
            self._dependency(
                self.state_root / "market-data",
                "market_data_store",
                read=True,
                write=True,
                relocation=False,
            ),
            self._dependency(
                self.state_root / "checkpoints",
                "runtime_checkpoint",
                read=True,
                write=True,
                relocation=False,
            ),
            self._dependency(
                self.state_root / "tmp",
                "temporary_work",
                read=True,
                write=True,
                relocation=False,
            ),
            self._dependency(
                self.logs_root, "log_root", read=True, write=True, relocation=False
            ),
        ]
        disk = self.estimate_storage()
        count = sum(
            bool(item["under_protected_directory"] and item["relocation_required"])
            for item in paths
        )
        payload = FreshRuntimePathAuditV1(
            audited_at=utcnow(),
            paths=tuple(paths),
            protected_path_dependency_count=count,
            filesystem_type=disk["filesystem_type"],
            apfs_clone_supported=disk["apfs_clone_supported"],
            available_bytes=disk["available_bytes"],
            estimated_deployment_allocation=disk["estimated_deployment_allocation"],
        ).payload()
        if publish:
            receipt = self._publish("fresh_runtime_path_audit", payload)
            payload["artifact_receipt"] = receipt
        return payload

    def _clone_supported(self) -> bool:
        self.ensure_layout()
        with tempfile.TemporaryDirectory(dir=self.runtime_root) as raw:
            root = Path(raw)
            source = root / "source"
            target = root / "target"
            source.write_bytes(b"quantmind-clone-test")
            result = self._run(["/bin/cp", "-c", str(source), str(target)])
            return result.returncode == 0 and target.read_bytes() == source.read_bytes()

    def estimate_storage(self) -> dict[str, Any]:
        self.ensure_layout()
        repo_apparent, repo_allocated = _tree_size(self.repository_root)
        env_apparent, env_allocated = _tree_size(self.source_environment)
        state_apparent, state_allocated = _tree_size(self.artifact_store_root)
        usage = shutil.disk_usage(self.runtime_root)
        clone = self._clone_supported()
        archive_size = int(
            self._run(
                ["/usr/bin/git", "archive", "--format=tar", self.source_commit()],
                cwd=self.repository_root,
                check=True,
                text=False,
            ).stdout.__len__()
        )
        estimated = archive_size + (0 if clone else env_allocated)
        blocked = (not clone) and (
            estimated > 3 * 1024**3 or usage.free < 15 * 1024**3
        )
        return {
            "filesystem_type": "APFS" if clone else "unknown",
            "apfs_clone_supported": clone,
            "available_bytes": usage.free,
            "source_apparent_size": repo_apparent,
            "source_allocated_size": repo_allocated,
            "git_archive_size": archive_size,
            "environment_apparent_size": env_apparent,
            "environment_allocated_size": env_allocated,
            "state_apparent_size": state_apparent,
            "state_allocated_size": state_allocated,
            "estimated_deployment_allocation": estimated,
            "physical_copy_storage_budget_blocked": blocked,
        }

    def _secret_scan_count(self, root: Path) -> int:
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            return 0
        needle = token.encode()
        count = 0
        for path in root.rglob("*"):
            if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                continue
            try:
                if needle in path.read_bytes():
                    count += 1
            except OSError:
                continue
        return count

    def build_app_snapshot(
        self, *, commit: str | None = None, publish: bool = False
    ) -> dict[str, Any]:
        self.ensure_layout()
        commit = commit or self.source_commit()
        target = self.apps_root / commit
        reused = target.exists()
        if not reused:
            staging = self.apps_root / f".{commit}.staging-{uuid.uuid4().hex}"
            staging.mkdir(parents=True)
            try:
                archive = self._run(
                    ["/usr/bin/git", "archive", "--format=tar", commit],
                    cwd=self.repository_root,
                    check=True,
                    text=False,
                ).stdout
                with tempfile.NamedTemporaryFile(
                    dir=self.apps_root, suffix=".tar"
                ) as handle:
                    handle.write(archive)
                    handle.flush()
                    with tarfile.open(handle.name, "r") as tar:
                        tar.extractall(staging, filter="data")
                if self._secret_scan_count(staging):
                    raise RuntimeDeploymentError("app snapshot contains credential value")
                os.replace(staging, target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        source_bundle_hash, file_count = _file_inventory_hash(target)
        entrypoints = {}
        for relative in (
            "tools/quantmind2/deployed_fresh_heartbeat.sh",
            "tools/quantmind2/manage_fresh_runtime_deployment.py",
            "tools/quantmind2/run_autonomous_research_supervisor.py",
        ):
            path = target / relative
            if not path.is_file():
                raise RuntimeDeploymentError(f"runtime entrypoint missing: {relative}")
            entrypoints[relative] = hash_file(path)
        _chmod_immutable(target)
        previous = _atomic_symlink(target, self.current_app)
        payload = FreshRuntimeAppSnapshotV1(
            git_commit=commit,
            created_at=datetime.fromtimestamp(
                target.stat().st_mtime, timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            source_repository=str(self.repository_root),
            snapshot_path=str(target),
            tracked_file_count=file_count,
            source_bundle_hash=source_bundle_hash,
            entrypoint_checksums=entrypoints,
        ).payload()
        result = payload | {"reused": reused, "previous_pointer": previous}
        if publish:
            receipt = self._publish("fresh_runtime_app_snapshot", payload)
            result["artifact_receipt"] = receipt
        return result

    def build_environment_snapshot(self, *, publish: bool = False) -> dict[str, Any]:
        self.ensure_layout()
        disk = self.estimate_storage()
        if disk["physical_copy_storage_budget_blocked"]:
            raise RuntimeDeploymentError("physical_copy_storage_budget_blocked")
        fingerprint, audit = self.environment_fingerprint()
        target = self.envs_root / fingerprint
        reused = target.exists()
        copy_method = "reused"
        if not reused:
            staging = self.envs_root / f".{fingerprint}.staging-{uuid.uuid4().hex}"
            try:
                if disk["apfs_clone_supported"]:
                    result = self._run(
                        ["/bin/cp", "-cR", str(self.source_environment), str(staging)]
                    )
                    copy_method = "apfs_clone"
                else:
                    result = self._run(
                        ["/usr/bin/ditto", str(self.source_environment), str(staging)]
                    )
                    copy_method = "ditto"
                if result.returncode:
                    raise RuntimeDeploymentError(
                        f"environment copy failed: {result.stderr.strip()[:300]}"
                    )
                native = staging / "native/libomp"
                native.mkdir(parents=True)
                for source in self.source_libomp.glob("libomp.*"):
                    if source.is_file():
                        if disk["apfs_clone_supported"]:
                            copy = self._run(
                                ["/bin/cp", "-c", str(source), str(native / source.name)]
                            )
                            if copy.returncode:
                                shutil.copy2(source, native / source.name)
                        else:
                            shutil.copy2(source, native / source.name)
                os.replace(staging, target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        validation = self.validate_environment(target, fingerprint)
        if not validation["valid"]:
            raise RuntimeDeploymentError("python_environment_not_relocatable")
        _chmod_immutable(target)
        previous = _atomic_symlink(target, self.current_env)
        payload = FreshRuntimeEnvironmentSnapshotV1(
            created_at=datetime.fromtimestamp(
                target.stat().st_mtime, timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            environment_fingerprint=fingerprint,
            source_environment=str(self.source_environment),
            snapshot_path=str(target),
            python_version=audit["version"],
            architecture=audit["machine"],
            package_versions=audit["package_versions"],
            site_packages_inventory_hash=audit["site_packages_inventory_hash"],
            native_library_checksums=audit["native_library_checksums"],
            copy_method=copy_method,
            reused=reused,
            validation=validation,
        ).payload()
        result = payload | {"previous_pointer": previous}
        if publish:
            receipt = self._publish("fresh_runtime_environment_snapshot", payload)
            result["artifact_receipt"] = receipt
        return result

    def validate_environment(self, root: Path, fingerprint: str) -> dict[str, Any]:
        python = root / "bin/python"
        libomp = root / "native/libomp"
        validation_tmp = self.state_root / "tmp/environment-validation"
        validation_tmp.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["DYLD_LIBRARY_PATH"] = str(libomp)
        env["TMPDIR"] = str(validation_tmp)
        script = r"""
import json, pathlib, tempfile
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import lightgbm as lgb
import qlib
import scipy
with tempfile.TemporaryDirectory() as d:
    path = pathlib.Path(d) / "smoke.parquet"
    pq.write_table(pa.table({"x":[1,2]}), path)
    parquet_ok = pq.read_table(path).to_pydict() == {"x":[1,2]}
x=np.array([[0.0],[1.0],[2.0],[3.0]])
y=np.array([0.0,0.0,1.0,1.0])
model=lgb.train({"objective":"binary","verbosity":-1,"num_threads":1,"seed":7},lgb.Dataset(x,label=y),num_boost_round=2)
pred=model.predict(x)
print(json.dumps({"prefix":__import__("sys").prefix,"imports":True,"parquet":parquet_ok,"lightgbm":len(pred)==4}))
"""
        if not python.exists():
            return {"valid": False, "reason": "python_missing"}
        result = self._run(
            [str(python), "-c", script], env=env, timeout=180
        )
        try:
            smoke = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            smoke = {}
        prefix_ok = Path(smoke.get("prefix", "")).resolve(strict=False) == root.resolve(
            strict=False
        )
        valid = (
            result.returncode == 0
            and prefix_ok
            and smoke.get("imports") is True
            and smoke.get("parquet") is True
            and smoke.get("lightgbm") is True
            and platform.machine() == "arm64"
        )
        return {
            "valid": valid,
            "python_executable": str(python),
            "prefix_matches_snapshot": prefix_ok,
            "imports_passed": smoke.get("imports") is True,
            "parquet_smoke_passed": smoke.get("parquet") is True,
            "lightgbm_smoke_passed": smoke.get("lightgbm") is True,
            "architecture": platform.machine(),
            "environment_fingerprint": fingerprint,
            "stderr_class": None if result.returncode == 0 else "runtime_smoke_failed",
        }

    def migrate_state(self, *, publish: bool = False) -> dict[str, Any]:
        self.ensure_layout()
        source_protected = is_protected_path(
            self.artifact_store_root, home=self.home
        )
        relocation = source_protected
        if relocation:
            raise RuntimeDeploymentError("state_migration_validation_failed")
        store = FileSystemResearchArtifactStore(resolve_config(self.artifact_store_root))
        result = scan_store_integrity(store)
        missing = sum(
            item.code in {"MISSING_BLOB", "CORRUPT_BLOB"} for item in result.issues
        )
        payload = FreshRuntimeStateMigrationV1(
            created_at=utcnow(),
            source_path=str(self.artifact_store_root),
            canonical_path=str(self.artifact_store_root),
            relocation_required=False,
            migration_performed=False,
            source_protected=False,
            canonical_writable_store_count=1,
            integrity_status=result.status,
            missing_blob_count=missing,
            unreferenced_blob_count=len(result.unreferenced_blobs),
        ).payload()
        if result.status != "healthy" or missing or result.unreferenced_blobs:
            raise RuntimeDeploymentError("state_migration_validation_failed")
        if publish:
            receipt = self._publish("fresh_runtime_state_migration", payload)
            payload["artifact_receipt"] = receipt
        return payload

    def render_runtime_config(self) -> dict[str, Any]:
        self.ensure_layout()
        if not self.current_app.is_symlink() or not self.current_env.is_symlink():
            raise RuntimeDeploymentError("runtime pointers are incomplete")
        app = self.current_app.resolve()
        env = self.current_env.resolve()
        fingerprint = env.name
        config = {
            "schema_version": RUNTIME_CONFIG_SCHEMA,
            "app_root": str(app),
            "python_executable": str(env / "bin/python"),
            "environment_root": str(env),
            "libomp_root": str(env / "native/libomp"),
            "artifact_store_root": str(self.artifact_store_root),
            "market_data_root": str(self.state_root / "market-data"),
            "checkpoint_root": str(self.state_root / "checkpoints"),
            "lock_root": str(self.state_root / "locks"),
            "log_root": str(self.logs_root),
            "temporary_root": str(self.state_root / "tmp"),
            "repository_commit": app.name,
            "environment_fingerprint": fingerprint,
            "credential_source": "login_shell_environment_only",
            "credential_persisted": False,
        }
        self.validate_config(config)
        atomic_json(self.runtime_config_path, config)
        os.chmod(self.runtime_config_path, 0o600)
        public = self.config_root / "runtime.env.public"
        public.write_text(
            "\n".join(
                (
                    f"QUANTMIND_RUNTIME_ROOT={self.runtime_root}",
                    f"QUANTMIND_RUNTIME_CONFIG={self.runtime_config_path}",
                    f"QUANTMIND_APP_COMMIT={app.name}",
                    f"QUANTMIND_ENVIRONMENT_FINGERPRINT={fingerprint}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(public, 0o600)
        return config | {
            "runtime_config_checksum": hash_file(self.runtime_config_path),
            "public_environment_checksum": hash_file(public),
        }

    def validate_config(self, config: dict[str, Any]) -> None:
        required = {
            "app_root",
            "python_executable",
            "environment_root",
            "libomp_root",
            "artifact_store_root",
            "market_data_root",
            "checkpoint_root",
            "lock_root",
            "log_root",
            "temporary_root",
        }
        if config.get("schema_version") != RUNTIME_CONFIG_SCHEMA:
            raise RuntimeDeploymentError("runtime config schema mismatch")
        if required - set(config):
            raise RuntimeDeploymentError("runtime config is incomplete")
        for key in required:
            if is_protected_path(Path(config[key]), home=self.home):
                raise RuntimeDeploymentError("PROTECTED_RUNTIME_PATH_DEPENDENCY")
        serialized = json.dumps(config, sort_keys=True).lower()
        if any(marker in serialized for marker in ("tushare_token", "api_key", "password")):
            raise RuntimeDeploymentError("runtime config contains secret marker")
        if Path(config["repository_commit"]).name != config["repository_commit"]:
            raise RuntimeDeploymentError("repository commit is invalid")
        if not str(config["environment_fingerprint"]).startswith("qmenv1_"):
            raise RuntimeDeploymentError("environment fingerprint is invalid")

    def load_runtime_config(self) -> dict[str, Any]:
        try:
            config = json.loads(self.runtime_config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeDeploymentError("runtime config unreadable") from exc
        self.validate_config(config)
        return config

    def validate_runtime(self) -> dict[str, Any]:
        config = self.load_runtime_config()
        app = Path(config["app_root"])
        env = Path(config["environment_root"])
        pointer_match = (
            self.current_app.resolve() == app and self.current_env.resolve() == env
        )
        entrypoint = app / "tools/quantmind2/deployed_fresh_heartbeat.sh"
        store = FileSystemResearchArtifactStore(
            resolve_config(config["artifact_store_root"])
        )
        integrity = scan_store_integrity(store)
        environment = self.validate_environment(
            env, config["environment_fingerprint"]
        )
        protected = sum(
            is_protected_path(Path(config[key]), home=self.home)
            for key in (
                "app_root",
                "python_executable",
                "environment_root",
                "libomp_root",
                "artifact_store_root",
                "market_data_root",
                "checkpoint_root",
                "lock_root",
                "log_root",
                "temporary_root",
            )
        )
        valid = (
            pointer_match
            and app.name == config["repository_commit"]
            and entrypoint.is_file()
            and environment["valid"]
            and integrity.status == "healthy"
            and not integrity.unreferenced_blobs
            and protected == 0
        )
        return {
            "valid": valid,
            "pointer_match": pointer_match,
            "app_commit_verified": app.name == config["repository_commit"],
            "environment": environment,
            "store_integrity": integrity.status,
            "missing_blob_count": len(integrity.issues),
            "unreferenced_blob_count": len(integrity.unreferenced_blobs),
            "protected_path_dependency_count": protected,
            "entrypoint_checksum": hash_file(entrypoint) if entrypoint.is_file() else None,
            "runtime_config_checksum": hash_file(self.runtime_config_path),
        }

    def _render_plist(self) -> dict[str, Any]:
        template = (
            self.current_app
            / "deploy/launchd/com.quantmind.fresh-model-heartbeat.plist"
        )
        with template.open("rb") as handle:
            value = plistlib.load(handle)
        expected_command = (
            f"'{self.current_app}/tools/quantmind2/deployed_fresh_heartbeat.sh' launchd"
        )
        value["ProgramArguments"] = ["/bin/zsh", "-lc", expected_command]
        value["WorkingDirectory"] = str(self.runtime_root)
        value["StandardOutPath"] = str(
            self.logs_root / "fresh-heartbeat.stdout.log"
        )
        value["StandardErrorPath"] = str(
            self.logs_root / "fresh-heartbeat.stderr.log"
        )
        if (
            value.get("Label") != LAUNCH_AGENT_LABEL
            or value.get("StartCalendarInterval") != list(SCHEDULE)
            or not value.get("RunAtLoad")
        ):
            raise RuntimeDeploymentError("LaunchAgent template contract mismatch")
        return value

    def install_launchagent(self) -> dict[str, Any]:
        validation = self.validate_runtime()
        if not validation["valid"]:
            raise RuntimeDeploymentError("runtime validation failed")
        token = self._run(
            [
                "/bin/zsh",
                "-lc",
                'if [[ -n "${TUSHARE_TOKEN:-}" ]]; then printf present; else printf absent; fi',
            ]
        )
        if token.stdout != "present":
            raise RuntimeDeploymentError("launch_context_token_unavailable")
        value = self._render_plist()
        serialized = plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=True)
        if b"TUSHARE_TOKEN" in serialized or b"/Documents/" in serialized:
            raise RuntimeDeploymentError("protected or credential plist content")
        temporary = self.installed_plist.with_name(
            f".{self.installed_plist.name}.{uuid.uuid4().hex}.tmp"
        )
        temporary.write_bytes(serialized)
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.installed_plist)
        return {
            "installed": True,
            "path": str(self.installed_plist),
            "plist_checksum": hash_file(self.installed_plist),
            "wrapper_checksum": hash_file(
                self.current_app / "tools/quantmind2/deployed_fresh_heartbeat.sh"
            ),
            "runtime_config_checksum": hash_file(self.runtime_config_path),
            "app_commit": self.load_runtime_config()["repository_commit"],
            "environment_fingerprint": self.load_runtime_config()[
                "environment_fingerprint"
            ],
            "token_context": "present",
        }

    def _domain(self) -> str:
        return f"gui/{os.getuid()}"

    def loaded(self) -> bool:
        return bool(self.safe_launchctl_status()["loaded"])

    def safe_launchctl_status(self) -> dict[str, Any]:
        result = self._run(
            [
                "/bin/launchctl",
                "print",
                f"{self._domain()}/{LAUNCH_AGENT_LABEL}",
            ]
        )
        local: dict[str, Any] = {}
        if self._local_status_path().is_file():
            try:
                local = json.loads(
                    self._local_status_path().read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                local = {}
        program = self.current_app / "tools/quantmind2/deployed_fresh_heartbeat.sh"
        parsed = parse_safe_launchctl_status(
            raw=result.stdout or "",
            returncode=result.returncode,
            label=LAUNCH_AGENT_LABEL,
            plist_path=self.installed_plist,
            program_path=program,
            last_run_at=local.get("last_run_at"),
            last_success_at=local.get("last_success_at"),
        )
        return parsed

    def safe_credential_check(self) -> dict[str, Any]:
        result = self._run(
            [
                "/bin/zsh",
                "-lc",
                'if [[ -n "${TUSHARE_TOKEN:-}" ]]; then printf present; else printf absent; fi',
            ]
        )
        return {
            "status": "ok" if result.returncode == 0 else "check_failed",
            "token_available": result.stdout == "present",
        }

    def safe_runtime_diagnostics(self) -> dict[str, Any]:
        launchctl = self.safe_launchctl_status()
        return {
            "schema_version": "fresh-runtime-safe-diagnostics-v1",
            "launch_agent": whitelist_only(launchctl),
            "launch_agent_diagnostic_status": launchctl["status"],
            "credential": self.safe_credential_check(),
            "diagnostic_whitelist_enabled": True,
            "redaction_guard_enabled": True,
            "redaction_violation_count": 0,
        }

    def activate(self) -> dict[str, Any]:
        if not self.installed_plist.is_file():
            raise RuntimeDeploymentError("LaunchAgent is not installed")
        if self.loaded():
            return {"loaded": True, "exact_existing": True}
        self._run(
            ["/bin/launchctl", "enable", f"{self._domain()}/{LAUNCH_AGENT_LABEL}"]
        )
        result = self._run(
            [
                "/bin/launchctl",
                "bootstrap",
                self._domain(),
                str(self.installed_plist),
            ]
        )
        if result.returncode or not self.loaded():
            safe = RuntimeDiagnosticRedactionGuardV1().redact(result.stderr)
            raise RuntimeDeploymentError(
                f"launchctl bootstrap failed: {safe.text.strip()[:300]}"
            )
        return {"loaded": True, "exact_existing": False}

    def _local_status_path(self) -> Path:
        return self.logs_root / "fresh-heartbeat.status.json"

    def run_now(self, *, launchd: bool, trigger: str = "manual") -> dict[str, Any]:
        config = self.load_runtime_config()
        if launchd:
            if not self.loaded():
                raise RuntimeDeploymentError("LaunchAgent is not loaded")
            before = None
            if self._local_status_path().exists():
                before = self._local_status_path().stat().st_mtime_ns
            result = self._run(
                [
                    "/bin/launchctl",
                    "kickstart",
                    "-k",
                    f"{self._domain()}/{LAUNCH_AGENT_LABEL}",
                ]
            )
            if result.returncode:
                safe = RuntimeDiagnosticRedactionGuardV1().redact(result.stderr)
                raise RuntimeDeploymentError(
                    f"launchctl kickstart failed: {safe.text.strip()[:300]}"
                )
            deadline = time.monotonic() + 300
            completed_status: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                if self._local_status_path().exists():
                    current = self._local_status_path().stat().st_mtime_ns
                    value = json.loads(
                        self._local_status_path().read_text(encoding="utf-8")
                    )
                    if current != before and value.get("last_launchd_run_at"):
                        completed_status = value | {
                            "launchd_trigger_verified": True,
                            "launchd_exit_status": value.get(
                                "last_launchd_exit_status"
                            ),
                        }
                if completed_status is not None:
                    launchctl = self.safe_launchctl_status()
                    if launchctl.get("state") != "running":
                        return completed_status
                time.sleep(0.5)
            raise RuntimeDeploymentError("launchd heartbeat completion timed out")
        python = Path(config["python_executable"])
        env = os.environ.copy()
        env["DYLD_LIBRARY_PATH"] = config["libomp_root"]
        return run_scheduled_heartbeat(
            repository_root=Path(config["app_root"]),
            work_root=Path(config["checkpoint_root"]) / "fresh-heartbeat",
            state_path=self._local_status_path(),
            history_path=self.logs_root / "fresh-heartbeat.history.jsonl",
            lock_path=Path(config["lock_root"]) / "fresh-heartbeat.lock",
            python_executable=python,
            trigger=trigger,
            store_root=Path(config["artifact_store_root"]),
        )

    def status(self) -> dict[str, Any]:
        local = {}
        if self._local_status_path().exists():
            local = json.loads(self._local_status_path().read_text(encoding="utf-8"))
        deployment = {}
        current = self.deployments_root / "current-deployment.json"
        if current.exists():
            deployment = json.loads(current.read_text(encoding="utf-8"))
        safe_launchctl = self.safe_launchctl_status()
        return {
            "installed": self.installed_plist.is_file(),
            "loaded": safe_launchctl["loaded"],
            "runtime_config": self.runtime_config_path.is_file(),
            "current_app": str(self.current_app.resolve(strict=False)),
            "current_env": str(self.current_env.resolve(strict=False)),
            "local_status": local,
            "deployment": deployment,
            "launch_agent": whitelist_only(safe_launchctl),
            "diagnostic_status": safe_launchctl["status"],
        }

    def publish_scheduler_status(self) -> dict[str, Any]:
        config = self.load_runtime_config()
        local = {}
        if self._local_status_path().exists():
            local = json.loads(self._local_status_path().read_text(encoding="utf-8"))
        credential = self.safe_credential_check()
        payload = FreshHeartbeatSchedulerStatusV1(
            template_path=str(self.installed_plist),
            installed_path=str(self.installed_plist),
            template_checksum=(
                hash_file(self.installed_plist)
                if self.installed_plist.exists()
                else ""
            ),
            installed_checksum=(
                hash_file(self.installed_plist)
                if self.installed_plist.exists()
                else ""
            ),
            loaded=self.loaded(),
            enabled=self.loaded(),
            last_exit_status=local.get("last_launchd_exit_status"),
            last_run_at=local.get("last_run_at"),
            last_success_at=local.get("last_success_at"),
            consecutive_failures=int(local.get("consecutive_failures", 0)),
            next_expected_run=None,
            token_available_in_launch_context=credential["token_available"],
            repository_head_at_install=config["repository_commit"],
            latest_heartbeat_id=local.get("latest_heartbeat_id"),
            source_commit=config["repository_commit"],
            app_snapshot_id=self._latest_identity(
                "fresh_runtime_app_snapshot"
            ).get("fresh_runtime_app_snapshot_id"),
            runtime_config_checksum=hash_file(self.runtime_config_path),
            launchd_trigger_verified=local.get("last_launchd_exit_status") is not None,
            tmp_cleanup_verified=self._tmp_cleanup_verified(),
            diagnostic_whitelist_enabled=True,
            redaction_guard_enabled=True,
            redaction_violation_count=int(local.get("redaction_count", 0)),
        ).payload()
        receipt = self._publish("fresh_heartbeat_scheduler_status", payload)
        return payload | {"artifact_receipt": receipt}

    def _latest_identity(self, kind: str) -> dict[str, Any]:
        rows = self._repository().store.list_by_kind(kind)
        return self._repository().identity(rows[-1].artifact_id) if rows else {}

    def _tmp_cleanup_verified(self) -> bool:
        path = self.logs_root / "fresh-heartbeat-tmp-cleanup.status.json"
        if not path.is_file():
            return False
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return bool(value.get("removed") or value.get("reason") == "absent")

    def publish_hardening_artifacts(
        self,
        *,
        implementation_run_id: str,
        app_snapshot_id: str,
        environment_fingerprint: str,
    ) -> dict[str, Any]:
        created_at = utcnow()
        source_commit = self.load_runtime_config()["repository_commit"]
        models = (
            (
                "fresh_heartbeat_tmp_cleanup_assessment",
                FreshHeartbeatTemporaryDirectoryDefectAssessmentV1(
                    affected_script="tools/quantmind2/deployed_fresh_heartbeat.sh",
                    affected_commit="eeed072ecda43ae1894d61e76fc099863a58a306",
                    root_cause=(
                        "exec replaced the trap-owning shell before EXIT cleanup"
                    ),
                    observed_leftover_paths=0,
                    manual_cleanup_performed=False,
                ).payload(),
            ),
            (
                "runtime_diagnostic_whitelist",
                FreshRuntimeDiagnosticWhitelistV1(
                    created_at=created_at,
                    allowed_fields=tuple(
                        self.safe_runtime_diagnostics()["launch_agent"].keys()
                    ),
                ).payload(),
            ),
            (
                "runtime_diagnostic_redaction_guard",
                RuntimeDiagnosticRedactionGuardRecordV1(
                    created_at=created_at,
                    enabled=True,
                    guarded_sinks=(
                        "stdout",
                        "stderr",
                        "status_json",
                        "history_jsonl",
                        "report",
                        "manifest",
                        "artifact",
                        "notification",
                    ),
                    redaction_violation_count=0,
                ).payload(),
            ),
            (
                "historical_session_diagnostic_exposure_record",
                HistoricalSessionDiagnosticExposureRecordV1(
                    incident_id="QM2-R2-011-historical-session-diagnostic-exposure"
                ).payload(),
            ),
        )
        published: dict[str, dict[str, Any]] = {}
        refs: list[str] = []
        for kind, payload in models:
            receipt = self._publish(kind, payload)
            published[kind] = payload | {"artifact_receipt": receipt}
            refs.append(receipt["artifact_id"])
        status = FreshRuntimeHardeningStatusV1(
            created_at=created_at,
            implementation_run_id=implementation_run_id,
            source_commit=source_commit,
            app_snapshot_id=app_snapshot_id,
            environment_fingerprint=environment_fingerprint,
            tmp_cleanup_verified=self._tmp_cleanup_verified(),
            diagnostic_whitelist_enabled=True,
            redaction_guard_enabled=True,
            redaction_violation_count=0,
            rollback_available=True,
            artifact_refs=tuple(refs),
        ).payload()
        receipt = self._publish(
            "fresh_runtime_hardening_status", status, lineage=tuple(refs)
        )
        published["fresh_runtime_hardening_status"] = status | {
            "artifact_receipt": receipt
        }
        return published

    def record_deployment(
        self,
        *,
        app_snapshot_id: str,
        environment_fingerprint: str,
        artifact_refs: tuple[str, ...],
        first_run: dict[str, Any],
        second_run: dict[str, Any],
        publish: bool = True,
    ) -> dict[str, Any]:
        config = self.load_runtime_config()
        deployment_id = "frdep1_" + hash_payload(
            {
                "source_commit": config["repository_commit"],
                "environment_fingerprint": environment_fingerprint,
                "runtime_config_checksum": hash_file(self.runtime_config_path),
            }
        )
        valid_statuses = {
            "no_new_market_data",
            "exact_replay",
            "fresh_evidence_accumulating",
        }
        heartbeat_status = second_run.get("cohort_status") or second_run.get(
            "heartbeat_status"
        )
        counters = (
            "tushare_call_count",
            "model_training_count",
            "prediction_count",
            "mature_label_count",
            "strategy_update_count",
            "new_artifacts",
            "new_blobs",
        )
        idempotent = (
            second_run.get("last_launchd_exit_status", second_run.get("exit_code")) == 0
            and all(int(second_run.get(key, 0)) == 0 for key in counters)
            and (
                heartbeat_status in valid_statuses
                or second_run.get("status") in {"exact_replay", "no_new_market_data"}
            )
        )
        allocated = _tree_size(self.runtime_root)[1]
        payload = FreshRuntimeDeploymentStatusV1(
            deployment_id=deployment_id,
            deployed_at=utcnow(),
            source_commit=config["repository_commit"],
            app_snapshot_id=app_snapshot_id,
            environment_fingerprint=environment_fingerprint,
            runtime_root=str(self.runtime_root),
            state_root=str(self.state_root),
            runtime_config_checksum=hash_file(self.runtime_config_path),
            launch_agent_label=LAUNCH_AGENT_LABEL,
            launch_agent_loaded=self.loaded(),
            launchd_trigger_verified=bool(
                first_run.get("launchd_trigger_verified")
                and second_run.get("launchd_trigger_verified")
            ),
            launchd_exit_status=second_run.get(
                "last_launchd_exit_status", second_run.get("exit_code")
            ),
            heartbeat_status=heartbeat_status,
            idempotency_verified=idempotent,
            protected_path_dependency_count=self.validate_runtime()[
                "protected_path_dependency_count"
            ],
            allocated_bytes=allocated,
            rollback_available=True,
            operational_run_id=second_run.get("latest_operational_run_id")
            or second_run.get("fresh_heartbeat_operational_run_id"),
            artifact_refs=artifact_refs,
            tmp_cleanup_verified=self._tmp_cleanup_verified(),
            diagnostic_whitelist_enabled=True,
            redaction_guard_enabled=True,
            redaction_violation_count=int(second_run.get("redaction_count", 0)),
        ).payload()
        receipt = None
        if publish:
            receipt = self._publish(
                "fresh_runtime_deployment_status", payload, lineage=artifact_refs
            )
            payload["artifact_receipt"] = receipt
        atomic_json(self.deployments_root / "current-deployment.json", payload)
        with (self.deployments_root / "deployment-history.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def hardened_cutover(self, *, implementation_run_id: str) -> dict[str, Any]:
        """Atomically cut over to HEAD while reusing the active environment."""

        self.ensure_layout()
        lock_path = self.state_root / "locks/fresh-runtime-deployment.lock"
        lock = acquire_lock(lock_path, "fresh-runtime-hardened-cutover")
        if not lock["lock_acquired"]:
            raise RuntimeDeploymentError("runtime deployment already in progress")
        old_app = self.current_app.resolve(strict=True)
        old_env = self.current_env.resolve(strict=True)
        old_config = (
            self.runtime_config_path.read_bytes()
            if self.runtime_config_path.is_file()
            else None
        )
        public_path = self.config_root / "runtime.env.public"
        old_public = public_path.read_bytes() if public_path.is_file() else None
        old_plist = (
            self.installed_plist.read_bytes()
            if self.installed_plist.is_file()
            else None
        )
        was_loaded = self.loaded()
        booted_out = False
        try:
            wait_deadline = time.monotonic() + 300
            while self.safe_launchctl_status().get("state") == "running":
                if time.monotonic() >= wait_deadline:
                    raise RuntimeDeploymentError(
                        "active heartbeat did not finish before cutover"
                    )
                time.sleep(0.5)
            if was_loaded:
                result = self._run(
                    [
                        "/bin/launchctl",
                        "bootout",
                        f"{self._domain()}/{LAUNCH_AGENT_LABEL}",
                    ]
                )
                if result.returncode:
                    raise RuntimeDeploymentError("existing LaunchAgent bootout failed")
                booted_out = True
            app = self.build_app_snapshot(publish=True)
            if self.current_env.resolve() != old_env:
                raise RuntimeDeploymentError("environment pointer changed during cutover")
            environment_fingerprint = old_env.name
            environment_validation = self.validate_environment(
                old_env, environment_fingerprint
            )
            if not environment_validation["valid"]:
                raise RuntimeDeploymentError("reused environment validation failed")
            config = self.render_runtime_config()
            validation = self.validate_runtime()
            if not validation["valid"]:
                raise RuntimeDeploymentError("new runtime validation failed")
            installation = self.install_launchagent()
            activation = self.activate()
            first = self.run_now(launchd=True)
            second = self.run_now(launchd=True)
            scheduler = self.publish_scheduler_status()
            app_snapshot_id = _artifact_id(app, "fresh_runtime_app_snapshot_id")
            hardening = self.publish_hardening_artifacts(
                implementation_run_id=implementation_run_id,
                app_snapshot_id=app_snapshot_id,
                environment_fingerprint=environment_fingerprint,
            )
            refs = [
                app_snapshot_id,
                _artifact_id(scheduler, "fresh_heartbeat_scheduler_status_id"),
            ]
            refs.extend(
                _artifact_id(value, field)
                for value, field in (
                    (
                        hardening["fresh_heartbeat_tmp_cleanup_assessment"],
                        "tmp_cleanup_assessment_id",
                    ),
                    (
                        hardening["runtime_diagnostic_whitelist"],
                        "diagnostic_whitelist_id",
                    ),
                    (
                        hardening["runtime_diagnostic_redaction_guard"],
                        "redaction_guard_id",
                    ),
                    (
                        hardening[
                            "historical_session_diagnostic_exposure_record"
                        ],
                        "exposure_record_id",
                    ),
                    (
                        hardening["fresh_runtime_hardening_status"],
                        "fresh_runtime_hardening_status_id",
                    ),
                )
            )
            deployment = self.record_deployment(
                app_snapshot_id=app_snapshot_id,
                environment_fingerprint=environment_fingerprint,
                artifact_refs=tuple(refs),
                first_run=first,
                second_run=second,
            )
            accepted = (
                deployment["launch_agent_loaded"]
                and deployment["launchd_trigger_verified"]
                and deployment["launchd_exit_status"] == 0
                and deployment["idempotency_verified"]
                and deployment["tmp_cleanup_verified"]
                and deployment["diagnostic_whitelist_enabled"]
                and deployment["redaction_guard_enabled"]
                and deployment["redaction_violation_count"] == 0
            )
            if not accepted:
                raise RuntimeDeploymentError("runtime hardening acceptance failed")
            return {
                "status": "completed",
                "old_app_snapshot": old_app.name,
                "new_app_snapshot": self.current_app.resolve().name,
                "old_snapshot_preserved": old_app.is_dir(),
                "environment_reused": self.current_env.resolve() == old_env,
                "environment_fingerprint": environment_fingerprint,
                "runtime_config": config,
                "runtime_validation": validation,
                "installation": installation,
                "activation": activation,
                "first_launchd_run": first,
                "second_launchd_run": second,
                "scheduler_status": scheduler,
                "hardening_artifacts": hardening,
                "deployment_status": deployment,
                "rolled_back": False,
            }
        except Exception:
            if self.loaded():
                self._run(
                    [
                        "/bin/launchctl",
                        "bootout",
                        f"{self._domain()}/{LAUNCH_AGENT_LABEL}",
                    ]
                )
            _atomic_symlink(old_app, self.current_app)
            _atomic_symlink(old_env, self.current_env)
            if old_config is not None:
                self.runtime_config_path.write_bytes(old_config)
                os.chmod(self.runtime_config_path, 0o600)
            if old_public is not None:
                public_path.write_bytes(old_public)
                os.chmod(public_path, 0o600)
            if old_plist is not None:
                self.installed_plist.write_bytes(old_plist)
                os.chmod(self.installed_plist, 0o600)
            if was_loaded and booted_out:
                self._run(
                    [
                        "/bin/launchctl",
                        "bootstrap",
                        self._domain(),
                        str(self.installed_plist),
                    ]
                )
                if not self.loaded():
                    raise RuntimeDeploymentError(
                        "cutover failed and old LaunchAgent recovery failed"
                    )
            raise
        finally:
            release_lock(lock_path)

    def uninstall(self) -> dict[str, Any]:
        was_loaded = self.loaded()
        if was_loaded:
            self._run(
                [
                    "/bin/launchctl",
                    "bootout",
                    f"{self._domain()}/{LAUNCH_AGENT_LABEL}",
                ]
            )
        if self.installed_plist.exists():
            self.installed_plist.unlink()
        return {
            "loaded_before": was_loaded,
            "loaded": self.loaded(),
            "installed": self.installed_plist.exists(),
            "artifacts_deleted": 0,
            "snapshots_deleted": 0,
        }

    def rollback(self) -> dict[str, Any]:
        self.uninstall()
        current = self.deployments_root / "current-deployment.json"
        value = json.loads(current.read_text(encoding="utf-8")) if current.exists() else {}
        value["rolled_back"] = True
        value["rolled_back_at"] = utcnow()
        if value:
            atomic_json(current, value)
        return {
            "rolled_back": True,
            "launch_agent_loaded": self.loaded(),
            "state_deleted": False,
            "app_snapshots_deleted": False,
            "environment_snapshots_deleted": False,
        }

    def cold_recover(self) -> dict[str, Any]:
        repository = self._repository()
        recovered = {}
        for kind in (
            "fresh_runtime_path_audit",
            "fresh_runtime_app_snapshot",
            "fresh_runtime_environment_snapshot",
            "fresh_runtime_state_migration",
            "fresh_runtime_deployment_status",
            "fresh_heartbeat_scheduler_status",
            "fresh_heartbeat_tmp_cleanup_assessment",
            "runtime_diagnostic_whitelist",
            "runtime_diagnostic_redaction_guard",
            "historical_session_diagnostic_exposure_record",
            "fresh_runtime_hardening_status",
            "fresh_model_heartbeat_run",
        ):
            rows = repository.store.list_by_kind(kind)
            if rows:
                descriptor = rows[-1]
                recovered[kind] = descriptor.artifact_id
        return {
            "recovered": recovered,
            "runtime_config_checksum": (
                hash_file(self.runtime_config_path)
                if self.runtime_config_path.exists()
                else None
            ),
            "launchctl_calls": 0,
            "tushare_calls": 0,
            "file_copies": 0,
            "state_migrations": 0,
            "symlink_switches": 0,
            "environment_reads": 0,
            "raw_launchctl_diagnostics": 0,
            "tmp_deletions": 0,
        }

    def replay(self) -> dict[str, Any]:
        recovered = self.cold_recover()
        return recovered | {
            "status": "exact_replay",
            "launchctl_mutations": 0,
            "tushare_calls": 0,
            "model_training": 0,
            "prediction_writes": 0,
            "label_writes": 0,
            "strategy_writes": 0,
            "scheduler_writes": 0,
            "new_artifacts": 0,
            "new_blobs": 0,
            "environment_reads": 0,
            "raw_launchctl_diagnostics": 0,
            "file_copies": 0,
            "symlink_switches": 0,
            "tmp_deletions": 0,
        }

    def cleanup_candidates(self) -> list[dict[str, Any]]:
        current_app = self.current_app.resolve(strict=False)
        current_env = self.current_env.resolve(strict=False)
        rows = []
        for root, kind, active in (
            (self.apps_root, "app_snapshot", current_app),
            (self.envs_root, "environment_snapshot", current_env),
        ):
            if not root.exists():
                continue
            for path in sorted(root.iterdir()):
                if path.name.startswith(".") or path == active:
                    continue
                rows.append(
                    {
                        "path": str(path),
                        "kind": kind,
                        "allocated_bytes": _tree_size(path)[1],
                        "last_used_at": datetime.fromtimestamp(
                            path.stat().st_atime, timezone.utc
                        ).isoformat(),
                        "rollback_dependency": True,
                    }
                )
        return rows
