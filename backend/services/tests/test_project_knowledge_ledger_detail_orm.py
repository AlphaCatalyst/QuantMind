"""Static contract tests for the four core Implementation Run detail mappings."""

from __future__ import annotations

import ast
import inspect
import unittest

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql.sqltypes import BigInteger, CHAR, Integer, String, Text

from backend.services.api.models.base import Base
from backend.services.api.project_knowledge.persistence import orm_detail_models
from backend.services.api.project_knowledge.persistence.orm_detail_models import (
    ChangedFileRecord,
    ChangedSymbolRecord,
    ImplementationArtifactRecord,
    TestExecutionRecord,
)
from backend.services.api.project_knowledge.persistence.orm_types import (
    FILE_CHANGE_TYPE_VALUES,
    IDENTIFIER_LENGTH,
    POSTGRESQL_IDENTIFIER_LIMIT,
    SHA256_LENGTH,
    SYMBOL_CHANGE_TYPE_VALUES,
    SYMBOL_TYPE_VALUES,
    TEST_EXECUTION_STATUS_VALUES,
    enum_check_sql,
    enum_values,
)
from backend.services.engine.project_knowledge.domain.enums import (
    FileChangeType,
    SymbolChangeType,
    SymbolType,
    TestExecutionStatus,
)


DETAIL_TABLE_KEYS = {
    "quantmind2.implementation_changed_files",
    "quantmind2.implementation_changed_symbols",
    "quantmind2.implementation_test_executions",
    "quantmind2.implementation_artifacts",
}
CORE_TABLE_KEYS = {
    "quantmind2.implementation_tasks",
    "quantmind2.implementation_runs",
    "quantmind2.implementation_run_relationships",
}


def constraints(table, kind):  # noqa: ANN001
    return [item for item in table.constraints if isinstance(item, kind)]


def checks_by_name(table):  # noqa: ANN001
    return {item.name: str(item.sqltext) for item in constraints(table, CheckConstraint)}


def index_columns(table):  # noqa: ANN001
    return {item.name: tuple(column.name for column in item.columns) for item in table.indexes}


def postgresql_ddl(table):  # noqa: ANN001
    dialect = postgresql.dialect()
    statements = [str(CreateTable(table).compile(dialect=dialect))]
    statements.extend(
        str(CreateIndex(index).compile(dialect=dialect))
        for index in sorted(table.indexes, key=lambda item: item.name)
    )
    return "\n".join(statements)


class LedgerDetailImportAndScopeTests(unittest.TestCase):
    models = (
        ChangedFileRecord,
        ChangedSymbolRecord,
        TestExecutionRecord,
        ImplementationArtifactRecord,
    )

    def test_models_use_selected_api_base(self):
        for model in self.models:
            self.assertIs(model.metadata, Base.metadata)
            self.assertIn(model.__table__.key, Base.metadata.tables)

    def test_exact_four_detail_tables_are_registered(self):
        actual = {
            key
            for key, table in Base.metadata.tables.items()
            if table.schema == "quantmind2" and key not in CORE_TABLE_KEYS
        }
        self.assertEqual(actual, DETAIL_TABLE_KEYS)

    def test_no_reference_or_annotation_table_is_registered(self):
        forbidden = ("component", "adr", "limitation", "recommendation", "manifest", "indexer")
        actual = {key for key, table in Base.metadata.tables.items() if table.schema == "quantmind2"}
        self.assertFalse(any(marker in key for key in actual for marker in forbidden))

    def test_module_has_no_engine_session_mapper_or_runtime_ddl(self):
        tree = ast.parse(inspect.getsource(orm_detail_models))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            {"create_engine", "create_async_engine", "Session", "AsyncSession", "sessionmaker"}.isdisjoint(imported)
        )
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertTrue(
            {"create_all", "drop_all", "execute", "commit", "rollback"}.isdisjoint(called)
        )
        for marker in ("to_domain", "from_domain", "serializer", "deserializer"):
            self.assertNotIn(marker, inspect.getsource(orm_detail_models))

    def test_records_have_no_business_methods_or_relationships(self):
        for model in self.models:
            methods = [
                name
                for name, value in vars(model).items()
                if callable(value) and not name.startswith("_")
            ]
            self.assertEqual(methods, [])
            self.assertEqual(tuple(model.__mapper__.relationships), ())


class ChangedFileOrmTests(unittest.TestCase):
    table = ChangedFileRecord.__table__

    def test_columns_types_and_nullability(self):
        self.assertEqual(
            tuple(self.table.columns.keys()),
            ("changed_file_id", "implementation_run_id", "path", "change_type", "before_hash", "after_hash", "previous_path"),
        )
        nullable = {"before_hash", "after_hash", "previous_path"}
        for column in self.table.columns:
            self.assertEqual(column.nullable, column.name in nullable, column.name)
        self.assertEqual(self.table.c.changed_file_id.type.length, IDENTIFIER_LENGTH)
        self.assertIsInstance(self.table.c.path.type, Text)
        for name in ("before_hash", "after_hash"):
            self.assertIsInstance(self.table.c[name].type, CHAR)
            self.assertEqual(self.table.c[name].type.length, SHA256_LENGTH)

    def test_technical_primary_key_has_no_generator(self):
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("changed_file_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_files")
        self.assertIsNone(self.table.c.changed_file_id.default)
        self.assertIsNone(self.table.c.changed_file_id.server_default)

    def test_run_foreign_key_is_restrictive(self):
        foreign_key = constraints(self.table, ForeignKeyConstraint)[0]
        self.assertEqual(foreign_key.name, "fk_qm2_files_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(
            next(iter(foreign_key.elements)).target_fullname,
            "quantmind2.implementation_runs.implementation_run_id",
        )

    def test_natural_key_matches_repository_contract(self):
        unique = constraints(self.table, UniqueConstraint)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].name, "uq_qm2_files_run_path_type")
        self.assertEqual(
            tuple(column.name for column in unique[0].columns),
            ("implementation_run_id", "path", "change_type"),
        )

    def test_change_and_hash_checks_are_complete(self):
        actual = checks_by_name(self.table)
        required = {
            "ck_qm2_files_path_nonempty",
            "ck_qm2_files_change_type",
            "ck_qm2_files_before_hash",
            "ck_qm2_files_after_hash",
            "ck_qm2_files_added_shape",
            "ck_qm2_files_deleted_shape",
            "ck_qm2_files_modified_shape",
            "ck_qm2_files_renamed_shape",
            "ck_qm2_files_unchanged_shape",
            "ck_qm2_files_previous_path_scope",
        }
        self.assertEqual(set(actual), required)
        self.assertIn("before_hash IS NULL", actual["ck_qm2_files_added_shape"])
        self.assertIn("after_hash IS NULL", actual["ck_qm2_files_deleted_shape"])
        self.assertIn("before_hash <> after_hash", actual["ck_qm2_files_modified_shape"])
        self.assertIn("previous_path <> path", actual["ck_qm2_files_renamed_shape"])
        self.assertIn("before_hash = after_hash", actual["ck_qm2_files_unchanged_shape"])

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_files_run": ("implementation_run_id",),
                "ix_qm2_files_path": ("path",),
                "ix_qm2_files_previous_path": ("previous_path",),
                "ix_qm2_files_change_type": ("change_type",),
                "ix_qm2_files_run_path": ("implementation_run_id", "path"),
            },
        )


class ChangedSymbolOrmTests(unittest.TestCase):
    table = ChangedSymbolRecord.__table__

    def test_columns_types_and_primary_key(self):
        self.assertEqual(
            tuple(self.table.columns.keys()),
            ("changed_symbol_id", "implementation_run_id", "file_path", "qualified_name", "symbol_type", "change_type"),
        )
        self.assertTrue(all(not column.nullable for column in self.table.columns))
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("changed_symbol_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_symbols")
        self.assertEqual(self.table.c.qualified_name.type.length, 512)
        self.assertIsNone(self.table.c.changed_symbol_id.default)
        self.assertIsNone(self.table.c.changed_symbol_id.server_default)

    def test_run_foreign_key_is_restrictive(self):
        foreign_key = constraints(self.table, ForeignKeyConstraint)[0]
        self.assertEqual(foreign_key.name, "fk_qm2_symbols_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")

    def test_natural_key_excludes_change_type_per_repository_contract(self):
        unique = constraints(self.table, UniqueConstraint)[0]
        self.assertEqual(unique.name, "uq_qm2_symbols_run_file_name")
        self.assertEqual(
            tuple(column.name for column in unique.columns),
            ("implementation_run_id", "file_path", "qualified_name"),
        )
        self.assertNotIn("change_type", tuple(column.name for column in unique.columns))

    def test_enum_and_nonempty_checks_exist(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {
                "ck_qm2_symbols_file_nonempty",
                "ck_qm2_symbols_name_nonempty",
                "ck_qm2_symbols_symbol_type",
                "ck_qm2_symbols_change_type",
            },
        )
        self.assertIn("btrim(qualified_name)", actual["ck_qm2_symbols_name_nonempty"])

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_symbols_run": ("implementation_run_id",),
                "ix_qm2_symbols_file": ("file_path",),
                "ix_qm2_symbols_name": ("qualified_name",),
                "ix_qm2_symbols_symbol_type": ("symbol_type",),
                "ix_qm2_symbols_run_file": ("implementation_run_id", "file_path"),
            },
        )


class TestExecutionOrmTests(unittest.TestCase):
    table = TestExecutionRecord.__table__

    def test_columns_types_and_nullability(self):
        self.assertEqual(len(self.table.columns), 11)
        nullable = {"not_run_reason", "artifact_uri", "artifact_hash"}
        for column in self.table.columns:
            self.assertEqual(column.nullable, column.name in nullable, column.name)
        for name in ("passed_count", "failed_count", "skipped_count"):
            self.assertIsInstance(self.table.c[name].type, Integer)
        self.assertIsInstance(self.table.c.command.type, Text)
        self.assertIsInstance(self.table.c.purpose.type, Text)
        self.assertEqual(self.table.c.artifact_hash.type.length, SHA256_LENGTH)

    def test_domain_id_is_primary_key_without_generator(self):
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("test_execution_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_tests")
        self.assertIsNone(self.table.c.test_execution_id.default)
        self.assertIsNone(self.table.c.test_execution_id.server_default)

    def test_run_foreign_key_and_natural_key(self):
        foreign_key = constraints(self.table, ForeignKeyConstraint)[0]
        self.assertEqual(foreign_key.name, "fk_qm2_tests_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        unique = constraints(self.table, UniqueConstraint)[0]
        self.assertEqual(unique.name, "uq_qm2_tests_run_id")
        self.assertEqual(
            tuple(column.name for column in unique.columns),
            ("implementation_run_id", "test_execution_id"),
        )

    def test_status_count_reason_and_hash_checks_exist(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {
                "ck_qm2_tests_command_nonempty",
                "ck_qm2_tests_purpose_nonempty",
                "ck_qm2_tests_status",
                "ck_qm2_tests_counts_nonnegative",
                "ck_qm2_tests_passed_shape",
                "ck_qm2_tests_failed_shape",
                "ck_qm2_tests_not_run_shape",
                "ck_qm2_tests_artifact_hash",
            },
        )
        self.assertIn("failed_count = 0", actual["ck_qm2_tests_passed_shape"])
        self.assertIn("failed_count > 0", actual["ck_qm2_tests_failed_shape"])
        self.assertIn("not_run_reason IS NOT NULL", actual["ck_qm2_tests_not_run_shape"])
        self.assertIn("not_run_reason IS NULL", actual["ck_qm2_tests_not_run_shape"])
        self.assertIn("{64}", actual["ck_qm2_tests_artifact_hash"])

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_tests_run": ("implementation_run_id",),
                "ix_qm2_tests_status": ("status",),
                "ix_qm2_tests_run_status": ("implementation_run_id", "status"),
            },
        )


class ImplementationArtifactOrmTests(unittest.TestCase):
    table = ImplementationArtifactRecord.__table__

    def test_columns_types_and_nullability(self):
        self.assertEqual(
            tuple(self.table.columns.keys()),
            ("artifact_id", "implementation_run_id", "artifact_type", "path_or_uri", "content_hash", "schema_version", "size_bytes"),
        )
        nullable = {"content_hash", "schema_version", "size_bytes"}
        for column in self.table.columns:
            self.assertEqual(column.nullable, column.name in nullable, column.name)
        self.assertEqual(self.table.c.artifact_type.type.length, IDENTIFIER_LENGTH)
        self.assertIsInstance(self.table.c.path_or_uri.type, Text)
        self.assertIsInstance(self.table.c.size_bytes.type, BigInteger)

    def test_domain_id_is_primary_key_without_generator(self):
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("artifact_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_artifacts")
        self.assertIsNone(self.table.c.artifact_id.default)
        self.assertIsNone(self.table.c.artifact_id.server_default)

    def test_run_foreign_key_and_natural_key(self):
        foreign_key = constraints(self.table, ForeignKeyConstraint)[0]
        self.assertEqual(foreign_key.name, "fk_qm2_artifacts_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        unique = constraints(self.table, UniqueConstraint)[0]
        self.assertEqual(unique.name, "uq_qm2_artifacts_run_id")
        self.assertEqual(
            tuple(column.name for column in unique.columns),
            ("implementation_run_id", "artifact_id"),
        )

    def test_nonempty_hash_and_size_checks_exist(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {
                "ck_qm2_artifacts_type_nonempty",
                "ck_qm2_artifacts_location_nonempty",
                "ck_qm2_artifacts_content_hash",
                "ck_qm2_artifacts_size_nonnegative",
            },
        )
        self.assertIn("btrim(path_or_uri)", actual["ck_qm2_artifacts_location_nonempty"])
        self.assertIn("{64}", actual["ck_qm2_artifacts_content_hash"])
        self.assertIn("size_bytes >= 0", actual["ck_qm2_artifacts_size_nonnegative"])

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_artifacts_run": ("implementation_run_id",),
                "ix_qm2_artifacts_type": ("artifact_type",),
                "ix_qm2_artifacts_content_hash": ("content_hash",),
                "ix_qm2_artifacts_run_type": ("implementation_run_id", "artifact_type"),
            },
        )


class LedgerDetailEnumNamingAndDdlTests(unittest.TestCase):
    detail_tables = (
        ChangedFileRecord.__table__,
        ChangedSymbolRecord.__table__,
        TestExecutionRecord.__table__,
        ImplementationArtifactRecord.__table__,
    )

    def test_enum_constants_match_domain(self):
        comparisons = (
            (FILE_CHANGE_TYPE_VALUES, FileChangeType),
            (SYMBOL_TYPE_VALUES, SymbolType),
            (SYMBOL_CHANGE_TYPE_VALUES, SymbolChangeType),
            (TEST_EXECUTION_STATUS_VALUES, TestExecutionStatus),
        )
        for persisted, domain_enum in comparisons:
            self.assertEqual(persisted, enum_values(domain_enum))

    def test_enum_checks_are_derived_from_domain(self):
        file_checks = checks_by_name(ChangedFileRecord.__table__)
        symbol_checks = checks_by_name(ChangedSymbolRecord.__table__)
        test_checks = checks_by_name(TestExecutionRecord.__table__)
        self.assertEqual(file_checks["ck_qm2_files_change_type"], enum_check_sql("change_type", FileChangeType))
        self.assertEqual(symbol_checks["ck_qm2_symbols_symbol_type"], enum_check_sql("symbol_type", SymbolType))
        self.assertEqual(symbol_checks["ck_qm2_symbols_change_type"], enum_check_sql("change_type", SymbolChangeType))
        self.assertEqual(test_checks["ck_qm2_tests_status"], enum_check_sql("status", TestExecutionStatus))

    def test_all_metadata_names_are_explicit_unique_and_bounded(self):
        tables = tuple(table for table in Base.metadata.tables.values() if table.schema == "quantmind2")
        names = []
        for table in tables:
            for item in (*table.constraints, *table.indexes):
                self.assertIsNotNone(item.name, table.key)
                self.assertTrue(item.name)
                self.assertLessEqual(len(item.name), POSTGRESQL_IDENTIFIER_LIMIT)
                names.append(item.name)
        self.assertEqual(len(names), len(set(names)))

    def test_names_match_object_kinds(self):
        prefixes = {
            PrimaryKeyConstraint: "pk_",
            ForeignKeyConstraint: "fk_",
            UniqueConstraint: "uq_",
            CheckConstraint: "ck_",
        }
        for table in self.detail_tables:
            for item in table.constraints:
                self.assertTrue(item.name.startswith(prefixes[type(item)]), item.name)
            for index in table.indexes:
                self.assertTrue(index.name.startswith("ix_"), index.name)

    def test_all_detail_tables_and_indexes_compile_without_connection(self):
        for table in self.detail_tables:
            ddl = postgresql_ddl(table)
            self.assertIn(f"CREATE TABLE quantmind2.{table.name}", ddl)
            self.assertIn("ON DELETE RESTRICT", ddl)

    def test_ddl_has_no_cascade_trigger_url_or_secret(self):
        ddl = "\n".join(postgresql_ddl(table) for table in self.detail_tables)
        upper = ddl.upper()
        self.assertNotIn("CASCADE", upper)
        self.assertNotIn("TRIGGER", upper)
        for marker in ("postgresql://", "password=", "secret=", "token=", "api_key="):
            self.assertNotIn(marker, ddl.lower())


if __name__ == "__main__":
    unittest.main()
