"""Pure explicit mappings for Component and ADR references."""

from backend.services.api.project_knowledge.persistence.orm_reference_models import (
    ArchitectureDecisionReferenceRecord,
    ComponentReferenceRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    ADRReferenceRelation,
    ImpactType,
)
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.models import (
    ArchitectureDecisionReference,
    ComponentReference,
)

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


def component_reference_to_record(
    implementation_run_id: str,
    item: ComponentReference,
) -> ComponentReferenceRecord:
    if not isinstance(item, ComponentReference):
        raise DomainToRecordError(
            "expected a ComponentReference domain object",
            object_type="ComponentReference",
            underlying_error_type=type(item).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    run_id = validate_parent_run_id(
        implementation_run_id,
        item.implementation_run_id,
        object_type="ComponentReference",
    )
    return ComponentReferenceRecord(
        implementation_run_id=run_id,
        component_id=item.component_id,
        impact_type=enum_to_storage(
            item.impact_type,
            field_name="impact_type",
            object_type="ComponentReference",
            identity=safe_record_identity(item.component_id),
        ),
    )


def component_reference_from_record(
    record: ComponentReferenceRecord,
) -> ComponentReference:
    object_type = "ComponentReference"
    if not isinstance(record, ComponentReferenceRecord):
        raise RecordToDomainError(
            "expected a ComponentReferenceRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("component_id"))
    try:
        return ComponentReference(
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            component_id=_read(values, "component_id", object_type, identity),
            impact_type=enum_from_storage(
                ImpactType,
                _read(values, "impact_type", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="impact_type",
            ),
        )
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _domain_error(exc, object_type, identity) from exc


def architecture_decision_reference_to_record(
    implementation_run_id: str,
    item: ArchitectureDecisionReference,
) -> ArchitectureDecisionReferenceRecord:
    if not isinstance(item, ArchitectureDecisionReference):
        raise DomainToRecordError(
            "expected an ArchitectureDecisionReference domain object",
            object_type="ArchitectureDecisionReference",
            underlying_error_type=type(item).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    run_id = validate_parent_run_id(
        implementation_run_id,
        item.implementation_run_id,
        object_type="ArchitectureDecisionReference",
    )
    return ArchitectureDecisionReferenceRecord(
        implementation_run_id=run_id,
        adr_id=item.adr_id,
        relation=enum_to_storage(
            item.relation,
            field_name="relation",
            object_type="ArchitectureDecisionReference",
            identity=safe_record_identity(item.adr_id),
        ),
    )


def architecture_decision_reference_from_record(
    record: ArchitectureDecisionReferenceRecord,
) -> ArchitectureDecisionReference:
    object_type = "ArchitectureDecisionReference"
    if not isinstance(record, ArchitectureDecisionReferenceRecord):
        raise RecordToDomainError(
            "expected an ArchitectureDecisionReferenceRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("adr_id"))
    try:
        return ArchitectureDecisionReference(
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            adr_id=_read(values, "adr_id", object_type, identity),
            relation=enum_from_storage(
                ADRReferenceRelation,
                _read(values, "relation", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="relation",
            ),
        )
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _domain_error(exc, object_type, identity) from exc
