"""SQLAlchemy mappings for the three core Implementation Ledger records.

Importing this module only registers tables on the selected API ``Base``.
It creates no engine, session, connection, schema, table, or transaction.
"""

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.services.api.models.base import Base
from backend.services.engine.project_knowledge.domain.enums import (
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    ImplementationRunStatus,
    ImplementationTaskStatus,
    RunRelationshipType,
    VerificationLevel,
)

from .orm_types import (
    GIT_COMMIT_LENGTH,
    IDENTIFIER_LENGTH,
    SHA256_LENGTH,
    enum_check_sql,
)


SCHEMA_NAME = "quantmind2"
TASK_TABLE_NAME = "implementation_tasks"
RUN_TABLE_NAME = "implementation_runs"
RELATIONSHIP_TABLE_NAME = "implementation_run_relationships"


class ImplementationTaskRecord(Base):
    """Persistence shape for an ImplementationTask domain value."""

    __tablename__ = TASK_TABLE_NAME

    task_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    parent_task_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{TASK_TABLE_NAME}.task_id",
            name="fk_qm2_tasks_parent",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    title = Column(Text, nullable=False)
    objective = Column(Text, nullable=False)
    scope = Column(JSONB, nullable=False)
    explicit_non_goals = Column(JSONB, nullable=False)
    status = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    version = Column(Integer, nullable=False, server_default=text("1"))

    __table_args__ = (
        PrimaryKeyConstraint("task_id", name="pk_qm2_tasks"),
        CheckConstraint(
            enum_check_sql("status", ImplementationTaskStatus),
            name="ck_qm2_tasks_status",
        ),
        CheckConstraint(
            "parent_task_id IS NULL OR parent_task_id <> task_id",
            name="ck_qm2_tasks_parent_differs",
        ),
        CheckConstraint("version >= 1", name="ck_qm2_tasks_version_positive"),
        CheckConstraint("btrim(title) <> ''", name="ck_qm2_tasks_title_nonempty"),
        CheckConstraint(
            "btrim(objective) <> ''",
            name="ck_qm2_tasks_objective_nonempty",
        ),
        CheckConstraint(
            "jsonb_typeof(scope) = 'array'",
            name="ck_qm2_tasks_scope_array",
        ),
        CheckConstraint(
            "jsonb_typeof(explicit_non_goals) = 'array'",
            name="ck_qm2_tasks_non_goals_array",
        ),
        Index("ix_qm2_tasks_status", "status"),
        Index("ix_qm2_tasks_parent", "parent_task_id"),
        Index("ix_qm2_tasks_created", "created_at"),
        {"schema": SCHEMA_NAME},
    )


class ImplementationRunRecord(Base):
    """Persistence shape for an ImplementationRun domain value."""

    __tablename__ = RUN_TABLE_NAME

    implementation_run_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    task_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{TASK_TABLE_NAME}.task_id",
            name="fk_qm2_runs_task",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    repository_root = Column(String(IDENTIFIER_LENGTH), nullable=False)
    branch = Column(String(IDENTIFIER_LENGTH), nullable=False)
    base_commit = Column(CHAR(GIT_COMMIT_LENGTH), nullable=False)
    result_commit = Column(CHAR(GIT_COMMIT_LENGTH), nullable=True)
    task_status = Column(String(32), nullable=False)
    completion_level = Column(String(32), nullable=False)
    verification_level = Column(String(32), nullable=False)
    workspace_dirty_before = Column(Boolean, nullable=False)
    workspace_dirty_after = Column(Boolean, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    agent_type = Column(String(IDENTIFIER_LENGTH), nullable=False)
    manifest_schema_version = Column(String(IDENTIFIER_LENGTH), nullable=False)
    manifest_path = Column(Text, nullable=False)
    manifest_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    report_path = Column(Text, nullable=False)
    report_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    source_bundle_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    git_diff_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    consistency_status = Column(String(32), nullable=False)
    canonical_status = Column(String(32), nullable=False)
    version = Column(Integer, nullable=False, server_default=text("1"))

    __table_args__ = (
        PrimaryKeyConstraint("implementation_run_id", name="pk_qm2_runs"),
        CheckConstraint(
            enum_check_sql("task_status", ImplementationRunStatus),
            name="ck_qm2_runs_status",
        ),
        CheckConstraint(
            enum_check_sql("completion_level", CompletionLevel),
            name="ck_qm2_runs_completion",
        ),
        CheckConstraint(
            enum_check_sql("verification_level", VerificationLevel),
            name="ck_qm2_runs_verification",
        ),
        CheckConstraint(
            enum_check_sql("consistency_status", ConsistencyStatus),
            name="ck_qm2_runs_consistency",
        ),
        CheckConstraint(
            enum_check_sql("canonical_status", CanonicalStatus),
            name="ck_qm2_runs_canonical_status",
        ),
        CheckConstraint("version >= 1", name="ck_qm2_runs_version_positive"),
        CheckConstraint(
            "base_commit ~ '^[0-9A-Fa-f]{40}$'",
            name="ck_qm2_runs_base_commit_format",
        ),
        CheckConstraint(
            "result_commit IS NULL OR result_commit ~ '^[0-9A-Fa-f]{40}$'",
            name="ck_qm2_runs_result_commit_format",
        ),
        CheckConstraint(
            "manifest_hash IS NULL OR manifest_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_runs_manifest_hash_format",
        ),
        CheckConstraint(
            "report_hash IS NULL OR report_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_runs_report_hash_format",
        ),
        CheckConstraint(
            "source_bundle_hash IS NULL OR source_bundle_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_runs_source_hash_format",
        ),
        CheckConstraint(
            "git_diff_hash IS NULL OR git_diff_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_runs_diff_hash_format",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_qm2_runs_time_order",
        ),
        CheckConstraint(
            "(task_status = 'running' AND completed_at IS NULL) OR "
            "(task_status <> 'running' AND completed_at IS NOT NULL)",
            name="ck_qm2_runs_terminal_time",
        ),
        CheckConstraint(
            "task_status NOT IN ('completed_committed', 'partial_committed') "
            "OR result_commit IS NOT NULL",
            name="ck_qm2_runs_committed_result",
        ),
        CheckConstraint(
            "task_status NOT IN ('completed_uncommitted', 'partial_uncommitted') "
            "OR result_commit IS NULL",
            name="ck_qm2_runs_uncommitted_result",
        ),
        CheckConstraint(
            "task_status NOT IN ('completed_committed', 'completed_uncommitted') "
            "OR completion_level = 'complete'",
            name="ck_qm2_runs_completed_level",
        ),
        CheckConstraint(
            "task_status NOT IN ('partial_committed', 'partial_uncommitted') "
            "OR completion_level = 'partial'",
            name="ck_qm2_runs_partial_level",
        ),
        CheckConstraint(
            "canonical_status <> 'canonical' OR "
            "(task_status = 'completed_committed' "
            "AND completion_level = 'complete' "
            "AND consistency_status = 'consistent' "
            "AND result_commit IS NOT NULL)",
            name="ck_qm2_runs_canonical_gate",
        ),
        CheckConstraint(
            "task_status NOT IN ('failed', 'blocked', 'cancelled') "
            "OR canonical_status <> 'canonical'",
            name="ck_qm2_runs_failure_noncanonical",
        ),
        Index("ix_qm2_runs_task", "task_id"),
        Index("ix_qm2_runs_status", "task_status"),
        Index("ix_qm2_runs_canonical", "canonical_status"),
        Index("ix_qm2_runs_consistency", "consistency_status"),
        Index("ix_qm2_runs_started", "started_at"),
        Index("ix_qm2_runs_result_commit", "result_commit"),
        Index("ix_qm2_runs_task_started", "task_id", "started_at"),
        {"schema": SCHEMA_NAME},
    )


class RunRelationshipRecord(Base):
    """Persistence shape for an immutable directed Run relationship."""

    __tablename__ = RELATIONSHIP_TABLE_NAME

    relationship_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    source_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_rels_source_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    target_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_rels_target_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    relationship_type = Column(String(32), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("relationship_id", name="pk_qm2_rels"),
        UniqueConstraint(
            "source_run_id",
            "target_run_id",
            "relationship_type",
            name="uq_qm2_rels_source_target_type",
        ),
        CheckConstraint(
            "source_run_id <> target_run_id",
            name="ck_qm2_rels_distinct_runs",
        ),
        CheckConstraint(
            enum_check_sql("relationship_type", RunRelationshipType),
            name="ck_qm2_rels_type",
        ),
        CheckConstraint("btrim(reason) <> ''", name="ck_qm2_rels_reason_nonempty"),
        Index("ix_qm2_rels_source", "source_run_id"),
        Index("ix_qm2_rels_target", "target_run_id"),
        Index("ix_qm2_rels_type", "relationship_type"),
        Index(
            "ix_qm2_rels_source_type",
            "source_run_id",
            "relationship_type",
        ),
        Index(
            "ix_qm2_rels_target_type",
            "target_run_id",
            "relationship_type",
        ),
        {"schema": SCHEMA_NAME},
    )
