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
    tmp_cleanup_verified: bool = False
    diagnostic_whitelist_enabled: bool = False
    redaction_guard_enabled: bool = False
    redaction_violation_count: int = 0

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-deployment-status-v1",
            "credential_source": "login_shell_environment_only",
            "credential_persisted": False,
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("frds1_", "fresh_runtime_deployment_status_id", value)


@dataclass(frozen=True)
class FreshHeartbeatTemporaryDirectoryDefectAssessmentV1:
    affected_script: str
    affected_commit: str
    root_cause: str
    observed_leftover_paths: int
    manual_cleanup_performed: bool
    fresh_artifacts_affected: bool = False
    store_affected: bool = False

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-heartbeat-tmp-cleanup-assessment-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("fhtca1_", "tmp_cleanup_assessment_id", value)


@dataclass(frozen=True)
class FreshRuntimeDiagnosticWhitelistV1:
    created_at: str
    allowed_fields: tuple[str, ...]
    raw_environment_output_disabled: bool = True
    raw_launchctl_output_disabled: bool = True

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "runtime-diagnostic-whitelist-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("rdw1_", "diagnostic_whitelist_id", value)


@dataclass(frozen=True)
class RuntimeDiagnosticRedactionGuardRecordV1:
    created_at: str
    enabled: bool
    guarded_sinks: tuple[str, ...]
    redaction_violation_count: int
    secret_hashes_persisted: bool = False

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "runtime-diagnostic-redaction-guard-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("rdrg1_", "redaction_guard_id", value)


@dataclass(frozen=True)
class HistoricalSessionDiagnosticExposureRecordV1:
    incident_id: str
    source_task: str = "QM2-R2-011"
    persistence_to_repo: bool = False
    persistence_to_config: bool = False
    persistence_to_artifact: bool = False
    credential_rotation_status: str = "user_governed"
    future_raw_environment_output_disabled: bool = True

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "historical-session-diagnostic-exposure-record-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("hsder1_", "exposure_record_id", value)


@dataclass(frozen=True)
class FreshRuntimeHardeningStatusV1:
    created_at: str
    implementation_run_id: str
    source_commit: str
    app_snapshot_id: str
    environment_fingerprint: str
    tmp_cleanup_verified: bool
    diagnostic_whitelist_enabled: bool
    redaction_guard_enabled: bool
    redaction_violation_count: int
    rollback_available: bool
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-hardening-status-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("frhs1_", "fresh_runtime_hardening_status_id", value)


@dataclass(frozen=True)
class EnvironmentValidationTemporaryDirectoryAssessmentV1:
    created_at: str
    creator: str
    purpose: str
    previous_path: str
    run_scoped: bool
    success_cleanup_verified: bool
    failure_cleanup_verified: bool
    signal_cleanup_verified: bool
    historical_empty_directory_removed: bool
    concurrent_use_detected: bool = False

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "environment-validation-tmp-assessment-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("evta1_", "environment_validation_tmp_assessment_id", value)


@dataclass(frozen=True)
class FreshRuntimeStatusConsistencyValidationV1:
    created_at: str
    scheduler_status_id: str
    deployment_status_id: str
    consistent: bool
    mismatch_code: str | None
    checked_fields: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-status-consistency-validation-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified(
            "frscv1_", "fresh_runtime_status_consistency_validation_id", value
        )


@dataclass(frozen=True)
class CanonicalRuntimeArtifactResolutionV1:
    created_at: str
    resolution_source: str
    app_snapshot_id: str
    deployment_status_id: str
    scheduler_status_id: str
    source_commit: str
    historical_artifact_count: int

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "canonical-runtime-artifact-resolution-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified(
            "crar1_", "canonical_runtime_artifact_resolution_id", value
        )


@dataclass(frozen=True)
class FreshRuntimeHardeningCompletionV1:
    created_at: str
    implementation_run_id: str
    source_commit: str
    app_snapshot_id: str
    deployment_status_id: str
    scheduler_status_id: str
    consistency_validation_id: str
    resolution_id: str
    tmp_before_hash: str
    tmp_after_hash: str
    completed: bool

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-runtime-hardening-completion-v1",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        return _identified("frhc1_", "fresh_runtime_hardening_completion_id", value)
