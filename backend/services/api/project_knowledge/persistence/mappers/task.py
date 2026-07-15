"""Pure bidirectional mapping for ImplementationTask only."""

from __future__ import annotations

import re

from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationTaskRecord,
)
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.models import ImplementationTask
from backend.services.engine.project_knowledge.domain.enums import ImplementationTaskStatus

from .common import (
    datetime_from_storage,
    datetime_to_storage,
    enum_from_storage,
    enum_to_storage,
    json_array_to_string_tuple,
    string_tuple_to_json_array,
)
from .errors import DomainToRecordError, LedgerMapperError, RecordToDomainError


_OBJECT_TYPE = "ImplementationTask"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_SECRET_ID_MARKERS = ("password", "passwd", "token", "secret", "api_key", "apikey")


def _safe_task_identity(value: object) -> str | None:
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
    """Read already-loaded SQLAlchemy state without invoking a descriptor load."""
    if field_name not in values:
        raise RecordToDomainError(
            "required ORM column is not loaded",
            object_type=_OBJECT_TYPE,
            safe_identity=identity,
            field_name=field_name,
            error_code="MISSING_REQUIRED_VALUE",
        )
    return values[field_name]


def implementation_task_to_record(task: ImplementationTask) -> ImplementationTaskRecord:
    """Create a new version-1 ORM record from one validated Domain Task."""
    if not isinstance(task, ImplementationTask):
        raise DomainToRecordError(
            "expected an ImplementationTask domain object",
            object_type=_OBJECT_TYPE,
            underlying_error_type=type(task).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    identity = task.task_id
    return ImplementationTaskRecord(
        task_id=task.task_id,
        parent_task_id=task.parent_task_id,
        title=task.title,
        objective=task.objective,
        scope=string_tuple_to_json_array(
            task.scope,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="scope",
        ),
        explicit_non_goals=string_tuple_to_json_array(
            task.explicit_non_goals,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="explicit_non_goals",
        ),
        status=enum_to_storage(
            task.status,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="status",
        ),
        created_at=datetime_to_storage(
            task.created_at,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="created_at",
        ),
        version=1,
    )


def implementation_task_from_record(record: ImplementationTaskRecord) -> ImplementationTask:
    """Rebuild a validated Domain Task from one ORM record's loaded columns."""
    if not isinstance(record, ImplementationTaskRecord):
        raise RecordToDomainError(
            "expected an ImplementationTaskRecord",
            object_type=_OBJECT_TYPE,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    raw_task_id = values.get("task_id")
    identity = _safe_task_identity(raw_task_id)
    version = _loaded_column(values, "version", identity=identity)
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version < 1
    ):
        raise RecordToDomainError(
            "stored version must be a positive integer",
            object_type=_OBJECT_TYPE,
            safe_identity=identity,
            field_name="version",
            underlying_error_type=type(version).__name__,
            error_code="INVALID_VERSION",
        )
    try:
        status = enum_from_storage(
            ImplementationTaskStatus,
            _loaded_column(values, "status", identity=identity),
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="status",
        )
        scope = json_array_to_string_tuple(
            _loaded_column(values, "scope", identity=identity),
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="scope",
        )
        non_goals = json_array_to_string_tuple(
            _loaded_column(values, "explicit_non_goals", identity=identity),
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="explicit_non_goals",
        )
        created_at = datetime_from_storage(
            _loaded_column(values, "created_at", identity=identity),
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="created_at",
        )
        return ImplementationTask(
            task_id=_loaded_column(values, "task_id", identity=identity),
            parent_task_id=_loaded_column(values, "parent_task_id", identity=identity),
            title=_loaded_column(values, "title", identity=identity),
            objective=_loaded_column(values, "objective", identity=identity),
            scope=scope,
            explicit_non_goals=non_goals,
            status=status,
            created_at=created_at,
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
