"""SQLAlchemy mappings for Limitation and RecommendedTask annotations.

Importing this module only registers two tables on the selected API ``Base``.
It creates no identifier, engine, session, connection, schema, table, or
transaction and defines no Repository, mapper, or update behavior.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)

from backend.services.api.models.base import Base
from backend.services.engine.project_knowledge.domain.enums import (
    LimitationSeverity,
    LimitationStatus,
    RecommendationPriority,
)

from .orm_models import RUN_TABLE_NAME, SCHEMA_NAME
from .orm_types import IDENTIFIER_LENGTH, enum_check_sql


LIMITATION_TABLE_NAME = "implementation_limitations"
RECOMMENDED_TASK_TABLE_NAME = "implementation_recommended_tasks"


class LimitationRecord(Base):
    """Persistence shape for one append-only Limitation domain value."""

    __tablename__ = LIMITATION_TABLE_NAME

    limitation_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_limitations_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    severity = Column(String(32), nullable=False)
    component_id = Column(String(IDENTIFIER_LENGTH), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("limitation_id", name="pk_qm2_limitations"),
        UniqueConstraint(
            "implementation_run_id",
            "limitation_id",
            name="uq_qm2_limitations_run_id",
        ),
        CheckConstraint(
            enum_check_sql("severity", LimitationSeverity),
            name="ck_qm2_limitations_severity",
        ),
        CheckConstraint(
            "component_id IS NULL OR btrim(component_id) <> ''",
            name="ck_qm2_limitations_component_nonempty",
        ),
        CheckConstraint(
            "btrim(description) <> ''",
            name="ck_qm2_limitations_description_nonempty",
        ),
        CheckConstraint(
            enum_check_sql("status", LimitationStatus),
            name="ck_qm2_limitations_status",
        ),
        Index("ix_qm2_limitations_run", "implementation_run_id"),
        Index("ix_qm2_limitations_severity", "severity"),
        Index("ix_qm2_limitations_status", "status"),
        Index("ix_qm2_limitations_component", "component_id"),
        Index("ix_qm2_limitations_run_status", "implementation_run_id", "status"),
        Index("ix_qm2_limitations_component_status", "component_id", "status"),
        {"schema": SCHEMA_NAME},
    )


class RecommendedTaskRecord(Base):
    """Persistence shape for one append-only RecommendedTask domain value."""

    __tablename__ = RECOMMENDED_TASK_TABLE_NAME

    recommendation_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_recommendations_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    next_task_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    priority = Column(String(16), nullable=False)
    reason = Column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("recommendation_id", name="pk_qm2_recommendations"),
        UniqueConstraint(
            "implementation_run_id",
            "recommendation_id",
            name="uq_qm2_recommendations_run_id",
        ),
        CheckConstraint(
            "btrim(next_task_id) <> ''",
            name="ck_qm2_recommendations_task_nonempty",
        ),
        CheckConstraint(
            enum_check_sql("priority", RecommendationPriority),
            name="ck_qm2_recommendations_priority",
        ),
        CheckConstraint(
            "btrim(reason) <> ''",
            name="ck_qm2_recommendations_reason_nonempty",
        ),
        Index("ix_qm2_recommendations_run", "implementation_run_id"),
        Index("ix_qm2_recommendations_task", "next_task_id"),
        Index("ix_qm2_recommendations_priority", "priority"),
        Index(
            "ix_qm2_recommendations_run_priority",
            "implementation_run_id",
            "priority",
        ),
        Index(
            "ix_qm2_recommendations_task_priority",
            "next_task_id",
            "priority",
        ),
        {"schema": SCHEMA_NAME},
    )
