"""Pure bidirectional mapping for ImplementationRun only."""

from __future__ import annotations

import re

from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationRunRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    ImplementationRunStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.models import ImplementationRun

from .common import (
    datetime_from_storage,
    datetime_to_storage,
    enum_from_storage,
    enum_to_storage,
)
from .errors import DomainToRecordError, LedgerMapperError, RecordToDomainError


_OBJECT_TYPE = "ImplementationRun"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_SECRET_ID_MARKERS = ("password", "passwd", "token", "secret", "api_key", "apikey")


def _safe_run_identity(value: object) -> str | None:
    if (
        isinstance(value, str)
        and _SAFE_ID_RE.fullmatch(value)
        and not any(marker in value.lower() for marker in _SECRET_ID_MARKERS)
    ):
        return value
    return None


def _loaded_column(
    values: dict[str, object],
    field_name: str,
    *,
    identity: str | None,
) -> object:
    """Read loaded SQLAlchemy state without invoking descriptor refresh."""
    if field_name not in values:
        raise RecordToDomainError(
            "required ORM column is not loaded",
            object_type=_OBJECT_TYPE,
            safe_identity=identity,
            field_name=field_name,
            error_code="MISSING_REQUIRED_VALUE",
        )
    return values[field_name]


def implementation_run_to_record(run: ImplementationRun) -> ImplementationRunRecord:
    """Create a new version-1 ORM record from one validated Domain Run."""
    if not isinstance(run, ImplementationRun):
        raise DomainToRecordError(
            "expected an ImplementationRun domain object",
            object_type=_OBJECT_TYPE,
            underlying_error_type=type(run).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    identity = _safe_run_identity(run.implementation_run_id)
    completed_at = (
        datetime_to_storage(
            run.completed_at,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="completed_at",
        )
        if run.completed_at is not None
        else None
    )
    return ImplementationRunRecord(
        implementation_run_id=run.implementation_run_id,
        task_id=run.task_id,
        # This is already a logical repository identity, never an execution path.
        repository_root=run.repository_root,
        branch=run.branch,
        base_commit=run.base_commit,
        result_commit=run.result_commit,
        task_status=enum_to_storage(
            run.task_status,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="task_status",
        ),
        completion_level=enum_to_storage(
            run.completion_level,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="completion_level",
        ),
        verification_level=enum_to_storage(
            run.verification_level,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="verification_level",
        ),
        workspace_dirty_before=run.workspace_dirty_before,
        workspace_dirty_after=run.workspace_dirty_after,
        started_at=datetime_to_storage(
            run.started_at,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="started_at",
        ),
        completed_at=completed_at,
        agent_type=run.agent_type,
        manifest_schema_version=run.manifest_schema_version,
        manifest_path=run.manifest_path,
        manifest_hash=run.manifest_hash,
        report_path=run.report_path,
        report_hash=run.report_hash,
        source_bundle_hash=run.source_bundle_hash,
        git_diff_hash=run.git_diff_hash,
        consistency_status=enum_to_storage(
            run.consistency_status,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="consistency_status",
        ),
        canonical_status=enum_to_storage(
            run.canonical_status,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="canonical_status",
        ),
        version=1,
    )


def implementation_run_from_record(record: ImplementationRunRecord) -> ImplementationRun:
    """Rebuild a validated Domain Run from one ORM record's loaded columns."""
    if not isinstance(record, ImplementationRunRecord):
        raise RecordToDomainError(
            "expected an ImplementationRunRecord",
            object_type=_OBJECT_TYPE,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = _safe_run_identity(values.get("implementation_run_id"))
    version = _loaded_column(values, "version", identity=identity)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise RecordToDomainError(
            "stored version must be a positive integer",
            object_type=_OBJECT_TYPE,
            safe_identity=identity,
            field_name="version",
            underlying_error_type=type(version).__name__,
            error_code="INVALID_VERSION",
        )
    try:
        completed_at_value = _loaded_column(values, "completed_at", identity=identity)
        completed_at = (
            datetime_from_storage(
                completed_at_value,
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="completed_at",
            )
            if completed_at_value is not None
            else None
        )
        return ImplementationRun(
            implementation_run_id=_loaded_column(
                values, "implementation_run_id", identity=identity
            ),
            task_id=_loaded_column(values, "task_id", identity=identity),
            # Stored value is a logical identity; path/Manifest binding is external.
            repository_root=_loaded_column(
                values, "repository_root", identity=identity
            ),
            branch=_loaded_column(values, "branch", identity=identity),
            base_commit=_loaded_column(values, "base_commit", identity=identity),
            result_commit=_loaded_column(values, "result_commit", identity=identity),
            task_status=enum_from_storage(
                ImplementationRunStatus,
                _loaded_column(values, "task_status", identity=identity),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="task_status",
            ),
            completion_level=enum_from_storage(
                CompletionLevel,
                _loaded_column(values, "completion_level", identity=identity),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="completion_level",
            ),
            verification_level=enum_from_storage(
                VerificationLevel,
                _loaded_column(values, "verification_level", identity=identity),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="verification_level",
            ),
            workspace_dirty_before=_loaded_column(
                values, "workspace_dirty_before", identity=identity
            ),
            workspace_dirty_after=_loaded_column(
                values, "workspace_dirty_after", identity=identity
            ),
            started_at=datetime_from_storage(
                _loaded_column(values, "started_at", identity=identity),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="started_at",
            ),
            completed_at=completed_at,
            agent_type=_loaded_column(values, "agent_type", identity=identity),
            manifest_schema_version=_loaded_column(
                values, "manifest_schema_version", identity=identity
            ),
            manifest_path=_loaded_column(values, "manifest_path", identity=identity),
            manifest_hash=_loaded_column(values, "manifest_hash", identity=identity),
            report_path=_loaded_column(values, "report_path", identity=identity),
            report_hash=_loaded_column(values, "report_hash", identity=identity),
            source_bundle_hash=_loaded_column(
                values, "source_bundle_hash", identity=identity
            ),
            git_diff_hash=_loaded_column(values, "git_diff_hash", identity=identity),
            consistency_status=enum_from_storage(
                ConsistencyStatus,
                _loaded_column(values, "consistency_status", identity=identity),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="consistency_status",
            ),
            canonical_status=enum_from_storage(
                CanonicalStatus,
                _loaded_column(values, "canonical_status", identity=identity),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="canonical_status",
            ),
        )
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise RecordToDomainError(
            "stored values failed Domain validation",
            object_type=_OBJECT_TYPE,
            safe_identity=identity,
            field_name=exc.field,
            underlying_error_type=type(exc).__name__,
            error_code=exc.error_code,
        ) from exc
