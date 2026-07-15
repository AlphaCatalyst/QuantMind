"""Pure explicit mappings for limitation and recommendation annotations."""

from backend.services.api.project_knowledge.persistence.orm_annotation_models import (
    LimitationRecord,
    RecommendedTaskRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    LimitationSeverity,
    LimitationStatus,
    RecommendationPriority,
)
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.models import Limitation, RecommendedTask

from .common import (
    enum_from_storage,
    enum_to_storage,
    loaded_column,
    safe_record_identity,
    validate_parent_run_id,
)
from .errors import DomainToRecordError, LedgerMapperError, RecordToDomainError


def _read(values: dict[str, object], name: str, object_type: str, identity: str | None) -> object:
    return loaded_column(values, name, object_type=object_type, identity=identity)


def _domain_error(exc: LedgerDomainError, object_type: str, identity: str | None):  # noqa: ANN201
    return RecordToDomainError(
        "stored values failed Domain validation",
        object_type=object_type,
        safe_identity=identity,
        field_name=exc.field,
        underlying_error_type=type(exc).__name__,
        error_code=exc.error_code,
    )


def limitation_to_record(
    implementation_run_id: str,
    item: Limitation,
) -> LimitationRecord:
    if not isinstance(item, Limitation):
        raise DomainToRecordError(
            "expected a Limitation domain object",
            object_type="Limitation",
            underlying_error_type=type(item).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    run_id = validate_parent_run_id(
        implementation_run_id, item.implementation_run_id, object_type="Limitation"
    )
    identity = safe_record_identity(item.limitation_id)
    return LimitationRecord(
        limitation_id=item.limitation_id,
        implementation_run_id=run_id,
        severity=enum_to_storage(
            item.severity,
            field_name="severity",
            object_type="Limitation",
            identity=identity,
        ),
        component_id=item.component_id,
        description=item.description,
        status=enum_to_storage(
            item.status,
            field_name="status",
            object_type="Limitation",
            identity=identity,
        ),
    )


def limitation_from_record(record: LimitationRecord) -> Limitation:
    object_type = "Limitation"
    if not isinstance(record, LimitationRecord):
        raise RecordToDomainError(
            "expected a LimitationRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("limitation_id"))
    try:
        return Limitation(
            limitation_id=_read(values, "limitation_id", object_type, identity),
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            severity=enum_from_storage(
                LimitationSeverity,
                _read(values, "severity", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="severity",
            ),
            component_id=_read(values, "component_id", object_type, identity),
            description=_read(values, "description", object_type, identity),
            status=enum_from_storage(
                LimitationStatus,
                _read(values, "status", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="status",
            ),
        )
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _domain_error(exc, object_type, identity) from exc


def recommended_task_to_record(
    implementation_run_id: str,
    item: RecommendedTask,
) -> RecommendedTaskRecord:
    if not isinstance(item, RecommendedTask):
        raise DomainToRecordError(
            "expected a RecommendedTask domain object",
            object_type="RecommendedTask",
            underlying_error_type=type(item).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    run_id = validate_parent_run_id(
        implementation_run_id,
        item.implementation_run_id,
        object_type="RecommendedTask",
    )
    identity = safe_record_identity(item.recommendation_id)
    return RecommendedTaskRecord(
        recommendation_id=item.recommendation_id,
        implementation_run_id=run_id,
        next_task_id=item.next_task_id,
        priority=enum_to_storage(
            item.priority,
            field_name="priority",
            object_type="RecommendedTask",
            identity=identity,
        ),
        reason=item.reason,
    )


def recommended_task_from_record(record: RecommendedTaskRecord) -> RecommendedTask:
    object_type = "RecommendedTask"
    if not isinstance(record, RecommendedTaskRecord):
        raise RecordToDomainError(
            "expected a RecommendedTaskRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("recommendation_id"))
    try:
        return RecommendedTask(
            recommendation_id=_read(values, "recommendation_id", object_type, identity),
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            next_task_id=_read(values, "next_task_id", object_type, identity),
            priority=enum_from_storage(
                RecommendationPriority,
                _read(values, "priority", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="priority",
            ),
            reason=_read(values, "reason", object_type, identity),
        )
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _domain_error(exc, object_type, identity) from exc
