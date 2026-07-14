"""Static contract tests for the three core Implementation Ledger mappings."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql.sqltypes import CHAR, DateTime, Integer, String, Text

from backend.services.api.models.base import Base
from backend.services.api.project_knowledge.persistence import orm_models
from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationRunRecord,
    ImplementationTaskRecord,
    RunRelationshipRecord,
)
from backend.services.api.project_knowledge.persistence.orm_types import (
    CANONICAL_STATUS_VALUES,
    COMPLETION_LEVEL_VALUES,
    CONSISTENCY_STATUS_VALUES,
    GIT_COMMIT_LENGTH,
    IDENTIFIER_LENGTH,
    POSTGRESQL_IDENTIFIER_LIMIT,
    RUN_RELATIONSHIP_TYPE_VALUES,
    RUN_STATUS_VALUES,
    SHA256_LENGTH,
    TASK_STATUS_VALUES,
    VERIFICATION_LEVEL_VALUES,
    enum_check_sql,
    enum_values,
)
from backend.services.engine.project_knowledge.domain.enums import (
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    ImplementationRunStatus,
    ImplementationTaskStatus,
    RunRelationshipType,
    VerificationLevel,
)


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


class LedgerCoreOrmImportAndBaseTests(unittest.TestCase):
    def test_models_use_selected_api_base_metadata(self):
        for model in (ImplementationTaskRecord, ImplementationRunRecord, RunRelationshipRecord):
            self.assertIs(model.metadata, Base.metadata)
            self.assertIn(model.__table__.key, Base.metadata.tables)

    def test_import_registers_exactly_three_quantmind2_tables(self):
        actual = {key for key, table in Base.metadata.tables.items() if table.schema == "quantmind2"}
        self.assertEqual(actual, CORE_TABLE_KEYS)

    def test_no_detail_table_is_registered(self):
        forbidden = ("changed_files", "changed_symbols", "test_executions", "artifacts")
        self.assertFalse(any(name in key for key in CORE_TABLE_KEYS for name in forbidden))

    def test_module_has_no_engine_session_or_runtime_ddl_calls(self):
        tree = ast.parse(inspect.getsource(orm_models))
        forbidden_imports = {
            "create_engine",
            "create_async_engine",
            "Session",
            "sessionmaker",
            "AsyncSession",
        }
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(forbidden_imports.isdisjoint(imported))
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertTrue(
            {"create_all", "drop_all", "execute", "commit", "rollback"}.isdisjoint(called)
        )

    def test_orm_records_define_no_business_methods_or_relationships(self):
        for model in (ImplementationTaskRecord, ImplementationRunRecord, RunRelationshipRecord):
            methods = [
                name
                for name, value in vars(model).items()
                if callable(value) and not name.startswith("_")
            ]
            self.assertEqual(methods, [])
            self.assertEqual(tuple(model.__mapper__.relationships), ())


class LedgerCoreOrmTableIdentityTests(unittest.TestCase):
    def test_table_names_and_schema_are_exact(self):
        expected = {
            ImplementationTaskRecord: "implementation_tasks",
            ImplementationRunRecord: "implementation_runs",
            RunRelationshipRecord: "implementation_run_relationships",
        }
        for model, name in expected.items():
            self.assertEqual(model.__tablename__, name)
            self.assertEqual(model.__table__.schema, "quantmind2")

    def test_table_keys_are_unique(self):
        tables = [ImplementationTaskRecord.__table__, ImplementationRunRecord.__table__, RunRelationshipRecord.__table__]
        self.assertEqual(len({table.key for table in tables}), 3)

    def test_all_columns_have_expected_names(self):
        self.assertEqual(
            tuple(ImplementationTaskRecord.__table__.columns.keys()),
            ("task_id", "parent_task_id", "title", "objective", "scope", "explicit_non_goals", "status", "created_at", "version"),
        )
        self.assertEqual(
            tuple(RunRelationshipRecord.__table__.columns.keys()),
            ("relationship_id", "source_run_id", "target_run_id", "relationship_type", "reason", "created_at"),
        )
        self.assertEqual(len(ImplementationRunRecord.__table__.columns), 24)


class ImplementationTaskOrmTests(unittest.TestCase):
    table = ImplementationTaskRecord.__table__

    def test_primary_key_and_identifier_capacity(self):
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("task_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_tasks")
        self.assertEqual(self.table.c.task_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.parent_task_id.type.length, IDENTIFIER_LENGTH)

    def test_nullability_and_types(self):
        self.assertFalse(self.table.c.task_id.nullable)
        self.assertTrue(self.table.c.parent_task_id.nullable)
        for name in ("title", "objective", "scope", "explicit_non_goals", "status", "created_at", "version"):
            self.assertFalse(self.table.c[name].nullable)
        self.assertIsInstance(self.table.c.title.type, Text)
        self.assertIsInstance(self.table.c.objective.type, Text)
        self.assertIsInstance(self.table.c.scope.type, JSONB)
        self.assertIsInstance(self.table.c.explicit_non_goals.type, JSONB)
        self.assertIsInstance(self.table.c.created_at.type, DateTime)
        self.assertTrue(self.table.c.created_at.type.timezone)
        self.assertIsInstance(self.table.c.version.type, Integer)

    def test_parent_foreign_key_is_named_restrictive_and_schema_qualified(self):
        foreign_keys = constraints(self.table, ForeignKeyConstraint)
        self.assertEqual(len(foreign_keys), 1)
        foreign_key = foreign_keys[0]
        self.assertEqual(foreign_key.name, "fk_qm2_tasks_parent")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(next(iter(foreign_key.elements)).target_fullname, "quantmind2.implementation_tasks.task_id")

    def test_required_checks_exist(self):
        actual = checks_by_name(self.table)
        required = {
            "ck_qm2_tasks_status",
            "ck_qm2_tasks_parent_differs",
            "ck_qm2_tasks_version_positive",
            "ck_qm2_tasks_title_nonempty",
            "ck_qm2_tasks_objective_nonempty",
            "ck_qm2_tasks_scope_array",
            "ck_qm2_tasks_non_goals_array",
        }
        self.assertEqual(set(actual), required)
        self.assertIn("jsonb_typeof", actual["ck_qm2_tasks_scope_array"])
        self.assertIn("jsonb_typeof", actual["ck_qm2_tasks_non_goals_array"])

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_tasks_status": ("status",),
                "ix_qm2_tasks_parent": ("parent_task_id",),
                "ix_qm2_tasks_created": ("created_at",),
            },
        )


class ImplementationRunOrmTests(unittest.TestCase):
    table = ImplementationRunRecord.__table__

    def test_primary_key_and_task_foreign_key(self):
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("implementation_run_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_runs")
        foreign_key = constraints(self.table, ForeignKeyConstraint)[0]
        self.assertEqual(foreign_key.name, "fk_qm2_runs_task")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(next(iter(foreign_key.elements)).target_fullname, "quantmind2.implementation_tasks.task_id")

    def test_identifier_commit_and_hash_types_match_domain_limits(self):
        for name in ("implementation_run_id", "task_id", "repository_root", "branch", "agent_type", "manifest_schema_version"):
            self.assertIsInstance(self.table.c[name].type, String)
            self.assertEqual(self.table.c[name].type.length, IDENTIFIER_LENGTH)
        for name in ("base_commit", "result_commit"):
            self.assertIsInstance(self.table.c[name].type, CHAR)
            self.assertEqual(self.table.c[name].type.length, GIT_COMMIT_LENGTH)
        for name in ("manifest_hash", "report_hash", "source_bundle_hash", "git_diff_hash"):
            self.assertIsInstance(self.table.c[name].type, CHAR)
            self.assertEqual(self.table.c[name].type.length, SHA256_LENGTH)

    def test_nullability_is_explicit(self):
        nullable = {"result_commit", "completed_at", "manifest_hash", "report_hash", "source_bundle_hash", "git_diff_hash"}
        for column in self.table.columns:
            self.assertEqual(column.nullable, column.name in nullable, column.name)

    def test_time_columns_are_timezone_aware(self):
        for name in ("started_at", "completed_at"):
            self.assertIsInstance(self.table.c[name].type, DateTime)
            self.assertTrue(self.table.c[name].type.timezone)

    def test_required_state_and_format_checks_exist(self):
        actual = checks_by_name(self.table)
        required = {
            "ck_qm2_runs_status", "ck_qm2_runs_completion", "ck_qm2_runs_verification",
            "ck_qm2_runs_consistency", "ck_qm2_runs_canonical_status", "ck_qm2_runs_version_positive",
            "ck_qm2_runs_base_commit_format", "ck_qm2_runs_result_commit_format",
            "ck_qm2_runs_manifest_hash_format", "ck_qm2_runs_report_hash_format",
            "ck_qm2_runs_source_hash_format", "ck_qm2_runs_diff_hash_format",
            "ck_qm2_runs_time_order", "ck_qm2_runs_terminal_time",
            "ck_qm2_runs_committed_result", "ck_qm2_runs_uncommitted_result",
            "ck_qm2_runs_completed_level", "ck_qm2_runs_partial_level",
            "ck_qm2_runs_canonical_gate", "ck_qm2_runs_failure_noncanonical",
        }
        self.assertEqual(set(actual), required)

    def test_commit_and_hash_checks_use_hex_formats(self):
        actual = checks_by_name(self.table)
        self.assertIn("{40}", actual["ck_qm2_runs_base_commit_format"])
        self.assertIn("{40}", actual["ck_qm2_runs_result_commit_format"])
        for name in ("ck_qm2_runs_manifest_hash_format", "ck_qm2_runs_report_hash_format", "ck_qm2_runs_source_hash_format", "ck_qm2_runs_diff_hash_format"):
            self.assertIn("{64}", actual[name])
            self.assertIn("A-Fa-f", actual[name])

    def test_canonical_and_terminal_combinations_are_checked(self):
        actual = checks_by_name(self.table)
        gate = actual["ck_qm2_runs_canonical_gate"]
        for marker in ("completed_committed", "complete", "consistent", "result_commit IS NOT NULL"):
            self.assertIn(marker, gate)
        terminal = actual["ck_qm2_runs_terminal_time"]
        self.assertIn("running", terminal)
        self.assertIn("completed_at IS NULL", terminal)
        self.assertIn("completed_at IS NOT NULL", terminal)

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_runs_task": ("task_id",),
                "ix_qm2_runs_status": ("task_status",),
                "ix_qm2_runs_canonical": ("canonical_status",),
                "ix_qm2_runs_consistency": ("consistency_status",),
                "ix_qm2_runs_started": ("started_at",),
                "ix_qm2_runs_result_commit": ("result_commit",),
                "ix_qm2_runs_task_started": ("task_id", "started_at"),
            },
        )


class RunRelationshipOrmTests(unittest.TestCase):
    table = RunRelationshipRecord.__table__

    def test_primary_key_and_foreign_keys(self):
        self.assertEqual(tuple(column.name for column in self.table.primary_key.columns), ("relationship_id",))
        self.assertEqual(self.table.primary_key.name, "pk_qm2_rels")
        foreign_keys = {item.name: item for item in constraints(self.table, ForeignKeyConstraint)}
        self.assertEqual(set(foreign_keys), {"fk_qm2_rels_source_run", "fk_qm2_rels_target_run"})
        for foreign_key in foreign_keys.values():
            self.assertEqual(foreign_key.ondelete, "RESTRICT")
            self.assertIn("quantmind2.implementation_runs.implementation_run_id", next(iter(foreign_key.elements)).target_fullname)

    def test_unique_natural_key_is_named(self):
        unique = constraints(self.table, UniqueConstraint)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].name, "uq_qm2_rels_source_target_type")
        self.assertEqual(tuple(column.name for column in unique[0].columns), ("source_run_id", "target_run_id", "relationship_type"))

    def test_distinct_type_and_reason_checks_exist(self):
        actual = checks_by_name(self.table)
        self.assertEqual(set(actual), {"ck_qm2_rels_distinct_runs", "ck_qm2_rels_type", "ck_qm2_rels_reason_nonempty"})
        self.assertIn("source_run_id <> target_run_id", actual["ck_qm2_rels_distinct_runs"])
        self.assertIn("btrim(reason)", actual["ck_qm2_rels_reason_nonempty"])

    def test_required_indexes_exist(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_rels_source": ("source_run_id",),
                "ix_qm2_rels_target": ("target_run_id",),
                "ix_qm2_rels_type": ("relationship_type",),
                "ix_qm2_rels_source_type": ("source_run_id", "relationship_type"),
                "ix_qm2_rels_target_type": ("target_run_id", "relationship_type"),
            },
        )

    def test_no_cycle_trigger_is_defined(self):
        self.assertNotIn("TRIGGER", postgresql_ddl(self.table).upper())


class LedgerCoreOrmNamingAndEnumTests(unittest.TestCase):
    tables = (ImplementationTaskRecord.__table__, ImplementationRunRecord.__table__, RunRelationshipRecord.__table__)

    def test_all_constraints_and_indexes_are_explicitly_named(self):
        for table in self.tables:
            for item in (*table.constraints, *table.indexes):
                self.assertIsNotNone(item.name, f"anonymous object on {table.key}")
                self.assertTrue(item.name)

    def test_names_are_globally_unique_and_fit_postgresql(self):
        names = [item.name for table in self.tables for item in (*table.constraints, *table.indexes)]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(len(name) <= POSTGRESQL_IDENTIFIER_LIMIT for name in names))

    def test_names_match_constraint_or_index_kinds(self):
        expected_prefixes = {
            PrimaryKeyConstraint: "pk_",
            ForeignKeyConstraint: "fk_",
            UniqueConstraint: "uq_",
            CheckConstraint: "ck_",
        }
        for table in self.tables:
            for item in table.constraints:
                self.assertTrue(item.name.startswith(expected_prefixes[type(item)]), item.name)
            for index in table.indexes:
                self.assertTrue(index.name.startswith("ix_"), index.name)

    def test_enum_value_constants_match_domain_enums_exactly(self):
        comparisons = (
            (TASK_STATUS_VALUES, ImplementationTaskStatus),
            (RUN_STATUS_VALUES, ImplementationRunStatus),
            (COMPLETION_LEVEL_VALUES, CompletionLevel),
            (VERIFICATION_LEVEL_VALUES, VerificationLevel),
            (CONSISTENCY_STATUS_VALUES, ConsistencyStatus),
            (CANONICAL_STATUS_VALUES, CanonicalStatus),
            (RUN_RELATIONSHIP_TYPE_VALUES, RunRelationshipType),
        )
        for persisted, domain_enum in comparisons:
            self.assertEqual(persisted, enum_values(domain_enum))

    def test_enum_check_expressions_are_derived_from_domain_enums(self):
        task_checks = checks_by_name(ImplementationTaskRecord.__table__)
        run_checks = checks_by_name(ImplementationRunRecord.__table__)
        relationship_checks = checks_by_name(RunRelationshipRecord.__table__)
        self.assertEqual(task_checks["ck_qm2_tasks_status"], enum_check_sql("status", ImplementationTaskStatus))
        self.assertEqual(run_checks["ck_qm2_runs_status"], enum_check_sql("task_status", ImplementationRunStatus))
        self.assertEqual(run_checks["ck_qm2_runs_completion"], enum_check_sql("completion_level", CompletionLevel))
        self.assertEqual(run_checks["ck_qm2_runs_verification"], enum_check_sql("verification_level", VerificationLevel))
        self.assertEqual(run_checks["ck_qm2_runs_consistency"], enum_check_sql("consistency_status", ConsistencyStatus))
        self.assertEqual(run_checks["ck_qm2_runs_canonical_status"], enum_check_sql("canonical_status", CanonicalStatus))
        self.assertEqual(relationship_checks["ck_qm2_rels_type"], enum_check_sql("relationship_type", RunRelationshipType))


class LedgerCoreOrmPostgresqlDdlTests(unittest.TestCase):
    tables = (ImplementationTaskRecord.__table__, ImplementationRunRecord.__table__, RunRelationshipRecord.__table__)

    def test_all_tables_and_indexes_compile_without_engine_or_connection(self):
        for table in self.tables:
            ddl = postgresql_ddl(table)
            self.assertIn(f"CREATE TABLE quantmind2.{table.name}", ddl)
            self.assertIn("quantmind2.", ddl)

    def test_ddl_contains_jsonb_timestamptz_and_restrict(self):
        task_ddl = postgresql_ddl(ImplementationTaskRecord.__table__)
        run_ddl = postgresql_ddl(ImplementationRunRecord.__table__)
        relationship_ddl = postgresql_ddl(RunRelationshipRecord.__table__)
        self.assertIn("JSONB NOT NULL", task_ddl)
        self.assertIn("TIMESTAMP WITH TIME ZONE", task_ddl)
        self.assertIn("TIMESTAMP WITH TIME ZONE", run_ddl)
        self.assertIn("ON DELETE RESTRICT", task_ddl)
        self.assertIn("ON DELETE RESTRICT", run_ddl)
        self.assertEqual(relationship_ddl.count("ON DELETE RESTRICT"), 2)

    def test_ddl_contains_no_cascade_database_url_or_secret(self):
        ddl = "\n".join(postgresql_ddl(table) for table in self.tables)
        upper = ddl.upper()
        self.assertNotIn("CASCADE", upper)
        self.assertNotIn("CREATE TRIGGER", upper)
        for marker in ("postgresql://", "password=", "secret=", "token=", "api_key="):
            self.assertNotIn(marker, ddl.lower())


if __name__ == "__main__":
    unittest.main()
