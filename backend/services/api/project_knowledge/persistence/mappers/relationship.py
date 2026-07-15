"""Pure bidirectional mapping for immutable Run relationships."""

from backend.services.api.project_knowledge.persistence.orm_models import RunRelationshipRecord
from backend.services.engine.project_knowledge.domain.enums import RunRelationshipType
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.models import RunRelationship

from .common import (
    datetime_from_storage,
    datetime_to_storage,
    enum_from_storage,
    enum_to_storage,
    loaded_column,
    safe_record_identity,
)
from .errors import DomainToRecordError, LedgerMapperError, RecordToDomainError


_OBJECT_TYPE = "RunRelationship"


def run_relationship_to_record(relationship: RunRelationship) -> RunRelationshipRecord:
    """Map one validated relationship without repository or graph checks."""
    if not isinstance(relationship, RunRelationship):
        raise DomainToRecordError(
            "expected a RunRelationship domain object",
            object_type=_OBJECT_TYPE,
            underlying_error_type=type(relationship).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    identity = safe_record_identity(relationship.relationship_id)
    return RunRelationshipRecord(
        relationship_id=relationship.relationship_id,
        source_run_id=relationship.source_run_id,
        target_run_id=relationship.target_run_id,
        relationship_type=enum_to_storage(
            relationship.relationship_type,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="relationship_type",
        ),
        reason=relationship.reason,
        created_at=datetime_to_storage(
            relationship.created_at,
            object_type=_OBJECT_TYPE,
            identity=identity,
            field_name="created_at",
        ),
    )


def run_relationship_from_record(record: RunRelationshipRecord) -> RunRelationship:
    """Rebuild a relationship from loaded columns using Domain validation."""
    if not isinstance(record, RunRelationshipRecord):
        raise RecordToDomainError(
            "expected a RunRelationshipRecord",
            object_type=_OBJECT_TYPE,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("relationship_id"))
    read = lambda name: loaded_column(  # noqa: E731
        values, name, object_type=_OBJECT_TYPE, identity=identity
    )
    try:
        return RunRelationship(
            relationship_id=read("relationship_id"),
            source_run_id=read("source_run_id"),
            target_run_id=read("target_run_id"),
            relationship_type=enum_from_storage(
                RunRelationshipType,
                read("relationship_type"),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="relationship_type",
            ),
            reason=read("reason"),
            created_at=datetime_from_storage(
                read("created_at"),
                object_type=_OBJECT_TYPE,
                identity=identity,
                field_name="created_at",
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
