"""SQLAlchemy mappings for Component and ADR Implementation Run references.

Importing this module only registers two tables on the selected API ``Base``.
It creates no identifier, engine, session, connection, schema, table, or
transaction and defines no Repository or mapping behavior.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
)

from backend.services.api.models.base import Base
from backend.services.engine.project_knowledge.domain.enums import (
    ADRReferenceRelation,
    ImpactType,
)

from .orm_models import RUN_TABLE_NAME, SCHEMA_NAME
from .orm_types import IDENTIFIER_LENGTH, enum_check_sql


COMPONENT_REFERENCE_TABLE_NAME = "implementation_component_references"
ADR_REFERENCE_TABLE_NAME = "implementation_adr_references"


class ComponentReferenceRecord(Base):
    """Persistence shape for one append-only ComponentReference value."""

    __tablename__ = COMPONENT_REFERENCE_TABLE_NAME

    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_component_refs_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    component_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    impact_type = Column(String(32), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "implementation_run_id",
            "component_id",
            name="pk_qm2_component_refs",
        ),
        CheckConstraint(
            "btrim(component_id) <> ''",
            name="ck_qm2_component_refs_id_nonempty",
        ),
        CheckConstraint(
            enum_check_sql("impact_type", ImpactType),
            name="ck_qm2_component_refs_impact_type",
        ),
        Index("ix_qm2_component_refs_component", "component_id"),
        Index("ix_qm2_component_refs_impact", "impact_type"),
        Index(
            "ix_qm2_component_refs_component_impact",
            "component_id",
            "impact_type",
        ),
        {"schema": SCHEMA_NAME},
    )


class ArchitectureDecisionReferenceRecord(Base):
    """Persistence shape for one append-only ADR reference value."""

    __tablename__ = ADR_REFERENCE_TABLE_NAME

    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_adr_refs_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    adr_id = Column(String(32), nullable=False)
    relation = Column(String(32), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "implementation_run_id",
            "adr_id",
            name="pk_qm2_adr_refs",
        ),
        CheckConstraint(
            "adr_id ~ '^ADR-[0-9]{4}$'",
            name="ck_qm2_adr_refs_id_format",
        ),
        CheckConstraint(
            enum_check_sql("relation", ADRReferenceRelation),
            name="ck_qm2_adr_refs_relation",
        ),
        Index("ix_qm2_adr_refs_adr", "adr_id"),
        Index("ix_qm2_adr_refs_relation", "relation"),
        Index("ix_qm2_adr_refs_adr_relation", "adr_id", "relation"),
        {"schema": SCHEMA_NAME},
    )
