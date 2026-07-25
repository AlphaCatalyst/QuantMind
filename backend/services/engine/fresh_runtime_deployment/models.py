from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


def _identified(prefix: str, field_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    value[field_name] = prefix + hash_payload(value)
    return value


@dataclass(frozen=True)
class FreshRuntimePathAuditV1:
    audited_at: str
    paths: tuple[dict[str, Any], ...]
    protected_path_dependency_count: int
    filesystem_type: str
    apfs_clone_supported: bool
    available_bytes: int
    estimated_deployment_allocation: int
    credential_source: str = "login_shell_environment_only"
    credential_persisted: bool = False

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-path-audit-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("frpa1_", "fresh_runtime_path_audit_id", value)


@dataclass(frozen=True)
class FreshRuntimeAppSnapshotV1:
    git_commit: str
    created_at: str
    source_repository: str
    snapshot_path: str
    tracked_file_count: int
    source_bundle_hash: str
    entrypoint_checksums: dict[str, str]
    immutable: bool = True

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-app-snapshot-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("fras1_", "fresh_runtime_app_snapshot_id", value)


@dataclass(frozen=True)
class FreshRuntimeEnvironmentSnapshotV1:
    created_at: str
    environment_fingerprint: str
    source_environment: str
    snapshot_path: str
    python_version: str
    architecture: str
    package_versions: dict[str, str | None]
    site_packages_inventory_hash: str
    native_library_checksums: dict[str, str]
    copy_method: str
    reused: bool
    validation: dict[str, Any]
    immutable: bool = True

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-environment-snapshot-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("fres1_", "fresh_runtime_environment_snapshot_id", value)


@dataclass(frozen=True)
class FreshRuntimeStateMigrationV1:
    created_at: str
    source_path: str
    canonical_path: str
    relocation_required: bool
    migration_performed: bool
    source_protected: bool
    canonical_writable_store_count: int
    integrity_status: str
    missing_blob_count: int
    unreferenced_blob_count: int
    backup_path: str | None = None

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-state-migration-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("frsm1_", "fresh_runtime_state_migration_id", value)


@dataclass(frozen=True)
class FreshRuntimeDeploymentStatusV1:
    deployment_id: str
    deployed_at: str
    source_commit: str
    app_snapshot_id: str
    environment_fingerprint: str
    runtime_root: str
    state_root: str
    runtime_config_checksum: str
    launch_agent_label: str
    launch_agent_loaded: bool
    launchd_trigger_verified: bool
    launchd_exit_status: int | None
    heartbeat_status: str | None
    idempotency_verified: bool
    protected_path_dependency_count: int
    allocated_bytes: int
    rollback_available: bool
    scheduler_status_id: str | None = None
    operational_run_id: str | None = None
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-deployment-status-v1",
            "credential_source": "login_shell_environment_only",
            "credential_persisted": False,
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("frds1_", "fresh_runtime_deployment_status_id", value)
