"""SQLAlchemy mappings for the four core Implementation Run detail records.

Importing this module only registers tables on the selected API ``Base``.
It creates no identifiers, engine, session, connection, schema, table, or
transaction and defines no persistence behavior.
"""

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)

from backend.services.api.models.base import Base
from backend.services.engine.project_knowledge.domain.enums import (
    FileChangeType,
    SymbolChangeType,
    SymbolType,
    TestExecutionStatus,
)

from .orm_models import RUN_TABLE_NAME, SCHEMA_NAME
from .orm_types import IDENTIFIER_LENGTH, SHA256_LENGTH, enum_check_sql


CHANGED_FILE_TABLE_NAME = "implementation_changed_files"
CHANGED_SYMBOL_TABLE_NAME = "implementation_changed_symbols"
TEST_EXECUTION_TABLE_NAME = "implementation_test_executions"
ARTIFACT_TABLE_NAME = "implementation_artifacts"


class ChangedFileRecord(Base):
    """Persistence shape for one append-only ChangedFile domain value."""

    __tablename__ = CHANGED_FILE_TABLE_NAME

    changed_file_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_files_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    path = Column(Text, nullable=False)
    change_type = Column(String(32), nullable=False)
    before_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    after_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    previous_path = Column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("changed_file_id", name="pk_qm2_files"),
        UniqueConstraint(
            "implementation_run_id",
            "path",
            "change_type",
            name="uq_qm2_files_run_path_type",
        ),
        CheckConstraint("btrim(path) <> ''", name="ck_qm2_files_path_nonempty"),
        CheckConstraint(
            enum_check_sql("change_type", FileChangeType),
            name="ck_qm2_files_change_type",
        ),
        CheckConstraint(
            "before_hash IS NULL OR before_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_files_before_hash",
        ),
        CheckConstraint(
            "after_hash IS NULL OR after_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_files_after_hash",
        ),
        CheckConstraint(
            "change_type <> 'added' OR "
            "(before_hash IS NULL AND after_hash IS NOT NULL AND previous_path IS NULL)",
            name="ck_qm2_files_added_shape",
        ),
        CheckConstraint(
            "change_type <> 'deleted' OR "
            "(before_hash IS NOT NULL AND after_hash IS NULL AND previous_path IS NULL)",
            name="ck_qm2_files_deleted_shape",
        ),
        CheckConstraint(
            "change_type <> 'modified' OR "
            "(before_hash IS NOT NULL AND after_hash IS NOT NULL "
            "AND before_hash <> after_hash AND previous_path IS NULL)",
            name="ck_qm2_files_modified_shape",
        ),
        CheckConstraint(
            "change_type <> 'renamed' OR "
            "(previous_path IS NOT NULL AND btrim(previous_path) <> '' "
            "AND previous_path <> path)",
            name="ck_qm2_files_renamed_shape",
        ),
        CheckConstraint(
            "change_type <> 'unchanged' OR "
            "(before_hash IS NOT NULL AND after_hash IS NOT NULL "
            "AND before_hash = after_hash AND previous_path IS NULL)",
            name="ck_qm2_files_unchanged_shape",
        ),
        CheckConstraint(
            "change_type = 'renamed' OR previous_path IS NULL",
            name="ck_qm2_files_previous_path_scope",
        ),
        Index("ix_qm2_files_run", "implementation_run_id"),
        Index("ix_qm2_files_path", "path"),
        Index("ix_qm2_files_previous_path", "previous_path"),
        Index("ix_qm2_files_change_type", "change_type"),
        Index("ix_qm2_files_run_path", "implementation_run_id", "path"),
        {"schema": SCHEMA_NAME},
    )


class ChangedSymbolRecord(Base):
    """Persistence shape for one append-only ChangedSymbol domain value."""

    __tablename__ = CHANGED_SYMBOL_TABLE_NAME

    changed_symbol_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_symbols_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    file_path = Column(Text, nullable=False)
    qualified_name = Column(String(512), nullable=False)
    symbol_type = Column(String(32), nullable=False)
    change_type = Column(String(32), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("changed_symbol_id", name="pk_qm2_symbols"),
        UniqueConstraint(
            "implementation_run_id",
            "file_path",
            "qualified_name",
            name="uq_qm2_symbols_run_file_name",
        ),
        CheckConstraint(
            "btrim(file_path) <> ''",
            name="ck_qm2_symbols_file_nonempty",
        ),
        CheckConstraint(
            "btrim(qualified_name) <> ''",
            name="ck_qm2_symbols_name_nonempty",
        ),
        CheckConstraint(
            enum_check_sql("symbol_type", SymbolType),
            name="ck_qm2_symbols_symbol_type",
        ),
        CheckConstraint(
            enum_check_sql("change_type", SymbolChangeType),
            name="ck_qm2_symbols_change_type",
        ),
        Index("ix_qm2_symbols_run", "implementation_run_id"),
        Index("ix_qm2_symbols_file", "file_path"),
        Index("ix_qm2_symbols_name", "qualified_name"),
        Index("ix_qm2_symbols_symbol_type", "symbol_type"),
        Index("ix_qm2_symbols_run_file", "implementation_run_id", "file_path"),
        {"schema": SCHEMA_NAME},
    )


class TestExecutionRecord(Base):
    """Persistence shape for one append-only TestExecution domain value."""

    __tablename__ = TEST_EXECUTION_TABLE_NAME

    test_execution_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_tests_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    command = Column(Text, nullable=False)
    purpose = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)
    passed_count = Column(Integer, nullable=False)
    failed_count = Column(Integer, nullable=False)
    skipped_count = Column(Integer, nullable=False)
    not_run_reason = Column(Text, nullable=True)
    artifact_uri = Column(Text, nullable=True)
    artifact_hash = Column(CHAR(SHA256_LENGTH), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("test_execution_id", name="pk_qm2_tests"),
        UniqueConstraint(
            "implementation_run_id",
            "test_execution_id",
            name="uq_qm2_tests_run_id",
        ),
        CheckConstraint("btrim(command) <> ''", name="ck_qm2_tests_command_nonempty"),
        CheckConstraint("btrim(purpose) <> ''", name="ck_qm2_tests_purpose_nonempty"),
        CheckConstraint(
            enum_check_sql("status", TestExecutionStatus),
            name="ck_qm2_tests_status",
        ),
        CheckConstraint(
            "passed_count >= 0 AND failed_count >= 0 AND skipped_count >= 0",
            name="ck_qm2_tests_counts_nonnegative",
        ),
        CheckConstraint(
            "status <> 'passed' OR failed_count = 0",
            name="ck_qm2_tests_passed_shape",
        ),
        CheckConstraint(
            "status <> 'failed' OR failed_count > 0",
            name="ck_qm2_tests_failed_shape",
        ),
        CheckConstraint(
            "(status = 'not_run' AND not_run_reason IS NOT NULL "
            "AND btrim(not_run_reason) <> '') OR "
            "(status <> 'not_run' AND not_run_reason IS NULL)",
            name="ck_qm2_tests_not_run_shape",
        ),
        CheckConstraint(
            "artifact_hash IS NULL OR artifact_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_tests_artifact_hash",
        ),
        Index("ix_qm2_tests_run", "implementation_run_id"),
        Index("ix_qm2_tests_status", "status"),
        Index("ix_qm2_tests_run_status", "implementation_run_id", "status"),
        {"schema": SCHEMA_NAME},
    )


class ImplementationArtifactRecord(Base):
    """Persistence shape for one append-only ImplementationArtifact value."""

    __tablename__ = ARTIFACT_TABLE_NAME

    artifact_id = Column(String(IDENTIFIER_LENGTH), nullable=False)
    implementation_run_id = Column(
        String(IDENTIFIER_LENGTH),
        ForeignKey(
            f"{SCHEMA_NAME}.{RUN_TABLE_NAME}.implementation_run_id",
            name="fk_qm2_artifacts_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    artifact_type = Column(String(IDENTIFIER_LENGTH), nullable=False)
    path_or_uri = Column(Text, nullable=False)
    content_hash = Column(CHAR(SHA256_LENGTH), nullable=True)
    schema_version = Column(String(IDENTIFIER_LENGTH), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("artifact_id", name="pk_qm2_artifacts"),
        UniqueConstraint(
            "implementation_run_id",
            "artifact_id",
            name="uq_qm2_artifacts_run_id",
        ),
        CheckConstraint(
            "btrim(artifact_type) <> ''",
            name="ck_qm2_artifacts_type_nonempty",
        ),
        CheckConstraint(
            "btrim(path_or_uri) <> ''",
            name="ck_qm2_artifacts_location_nonempty",
        ),
        CheckConstraint(
            "content_hash IS NULL OR content_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="ck_qm2_artifacts_content_hash",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_qm2_artifacts_size_nonnegative",
        ),
        Index("ix_qm2_artifacts_run", "implementation_run_id"),
        Index("ix_qm2_artifacts_type", "artifact_type"),
        Index("ix_qm2_artifacts_content_hash", "content_hash"),
        Index(
            "ix_qm2_artifacts_run_type",
            "implementation_run_id",
            "artifact_type",
        ),
        {"schema": SCHEMA_NAME},
    )
