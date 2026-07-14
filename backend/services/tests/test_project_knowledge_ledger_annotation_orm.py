"""Static contract tests for Limitation and RecommendedTask ORM mappings."""

from __future__ import annotations

import ast
import inspect
import unittest

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql.sqltypes import String, Text

from backend.services.api.models.base import Base
from backend.services.api.project_knowledge.persistence import orm_annotation_models
from backend.services.api.project_knowledge.persistence.orm_annotation_models import (
    LimitationRecord,
    RecommendedTaskRecord,
)
from backend.services.api.project_knowledge.persistence.orm_types import (
    IDENTIFIER_LENGTH,
    LIMITATION_SEVERITY_VALUES,
    LIMITATION_STATUS_VALUES,
    POSTGRESQL_IDENTIFIER_LIMIT,
    RECOMMENDATION_PRIORITY_VALUES,
    enum_check_sql,
    enum_values,
)
from backend.services.engine.project_knowledge.domain.enums import (
    LimitationSeverity,
    LimitationStatus,
    RecommendationPriority,
)


PRIOR_TABLE_KEYS = {
    "quantmind2.implementation_tasks",
    "quantmind2.implementation_runs",
    "quantmind2.implementation_run_relationships",
    "quantmind2.implementation_changed_files",
    "quantmind2.implementation_changed_symbols",
    "quantmind2.implementation_test_executions",
    "quantmind2.implementation_artifacts",
    "quantmind2.implementation_component_references",
    "quantmind2.implementation_adr_references",
}
ANNOTATION_TABLE_KEYS = {
    "quantmind2.implementation_limitations",
    "quantmind2.implementation_recommended_tasks",
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


class LedgerAnnotationImportAndScopeTests(unittest.TestCase):
    models = (LimitationRecord, RecommendedTaskRecord)

    def test_models_use_selected_api_base(self):
        for model in self.models:
            self.assertIs(model.metadata, Base.metadata)
            self.assertIn(model.__table__.key, Base.metadata.tables)

    def test_exact_two_annotation_tables_are_registered(self):
        actual = {
            key
            for key, table in Base.metadata.tables.items()
            if table.schema == "quantmind2" and key not in PRIOR_TABLE_KEYS
        }
        self.assertEqual(actual, ANNOTATION_TABLE_KEYS)

    def test_no_out_of_scope_table_is_registered(self):
        actual = {key for key, table in Base.metadata.tables.items() if table.schema == "quantmind2"}
        forbidden = ("manifest", "report", "indexer", "migration", "project_state")
        self.assertFalse(any(marker in key for key in actual for marker in forbidden))

    def test_module_has_no_engine_session_mapper_repository_or_runtime_ddl(self):
        source = inspect.getsource(orm_annotation_models)
        tree = ast.parse(source)
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
        for marker in (
            "to_domain",
            "from_domain",
            "serializer",
            "deserializer",
            "upsert",
            "merge",
            "on_conflict_do_update",
            "update_status",
        ):
            self.assertNotIn(marker, source.lower())

    def test_records_have_no_business_methods_or_relationships(self):
        for model in self.models:
            methods = [
                name
                for name, value in vars(model).items()
                if callable(value) and not name.startswith("_")
            ]
            self.assertEqual(methods, [])
            self.assertEqual(tuple(model.__mapper__.relationships), ())


class LimitationOrmTests(unittest.TestCase):
    table = LimitationRecord.__table__

    def test_table_schema_columns_types_and_nullability(self):
        self.assertEqual(self.table.schema, "quantmind2")
        self.assertEqual(self.table.name, "implementation_limitations")
        self.assertEqual(
            tuple(self.table.columns.keys()),
            (
                "limitation_id",
                "implementation_run_id",
                "severity",
                "component_id",
                "description",
                "status",
            ),
        )
        self.assertEqual(
            {column.name for column in self.table.columns if column.nullable},
            {"component_id"},
        )
        self.assertEqual(self.table.c.limitation_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.implementation_run_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.component_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.severity.type.length, 32)
        self.assertEqual(self.table.c.status.type.length, 32)
        self.assertIsInstance(self.table.c.description.type, Text)

    def test_domain_id_is_named_primary_key_without_generator(self):
        primary_key = constraints(self.table, PrimaryKeyConstraint)[0]
        self.assertEqual(primary_key.name, "pk_qm2_limitations")
        self.assertEqual(tuple(column.name for column in primary_key.columns), ("limitation_id",))
        self.assertIsNone(self.table.c.limitation_id.default)
        self.assertIsNone(self.table.c.limitation_id.server_default)

    def test_a1b2_run_scoped_natural_identity_is_named_unique(self):
        unique = constraints(self.table, UniqueConstraint)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].name, "uq_qm2_limitations_run_id")
        self.assertEqual(
            tuple(column.name for column in unique[0].columns),
            ("implementation_run_id", "limitation_id"),
        )

    def test_only_foreign_key_is_restrictive_run_reference(self):
        foreign_keys = constraints(self.table, ForeignKeyConstraint)
        self.assertEqual(len(foreign_keys), 1)
        foreign_key = foreign_keys[0]
        self.assertEqual(foreign_key.name, "fk_qm2_limitations_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(
            next(iter(foreign_key.elements)).target_fullname,
            "quantmind2.implementation_runs.implementation_run_id",
        )

    def test_checks_cover_enums_description_and_optional_component(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {
                "ck_qm2_limitations_severity",
                "ck_qm2_limitations_component_nonempty",
                "ck_qm2_limitations_description_nonempty",
                "ck_qm2_limitations_status",
            },
        )
        self.assertEqual(
            actual["ck_qm2_limitations_severity"],
            enum_check_sql("severity", LimitationSeverity),
        )
        self.assertEqual(
            actual["ck_qm2_limitations_status"],
            enum_check_sql("status", LimitationStatus),
        )
        self.assertIn("component_id IS NULL", actual["ck_qm2_limitations_component_nonempty"])
        self.assertIn("btrim(description) <> ''", actual["ck_qm2_limitations_description_nonempty"])

    def test_indexes_cover_run_state_and_component_queries(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_limitations_run": ("implementation_run_id",),
                "ix_qm2_limitations_severity": ("severity",),
                "ix_qm2_limitations_status": ("status",),
                "ix_qm2_limitations_component": ("component_id",),
                "ix_qm2_limitations_run_status": ("implementation_run_id", "status"),
                "ix_qm2_limitations_component_status": ("component_id", "status"),
            },
        )


class RecommendedTaskOrmTests(unittest.TestCase):
    table = RecommendedTaskRecord.__table__

    def test_table_schema_columns_types_and_nullability(self):
        self.assertEqual(self.table.schema, "quantmind2")
        self.assertEqual(self.table.name, "implementation_recommended_tasks")
        self.assertEqual(
            tuple(self.table.columns.keys()),
            ("recommendation_id", "implementation_run_id", "next_task_id", "priority", "reason"),
        )
        self.assertTrue(all(not column.nullable for column in self.table.columns))
        for name in ("recommendation_id", "implementation_run_id", "next_task_id"):
            self.assertIsInstance(self.table.c[name].type, String)
            self.assertEqual(self.table.c[name].type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.priority.type.length, 16)
        self.assertIsInstance(self.table.c.reason.type, Text)

    def test_domain_id_is_named_primary_key_without_generator(self):
        primary_key = constraints(self.table, PrimaryKeyConstraint)[0]
        self.assertEqual(primary_key.name, "pk_qm2_recommendations")
        self.assertEqual(tuple(column.name for column in primary_key.columns), ("recommendation_id",))
        self.assertIsNone(self.table.c.recommendation_id.default)
        self.assertIsNone(self.table.c.recommendation_id.server_default)

    def test_a1b2_run_scoped_natural_identity_is_named_unique(self):
        unique = constraints(self.table, UniqueConstraint)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].name, "uq_qm2_recommendations_run_id")
        self.assertEqual(
            tuple(column.name for column in unique[0].columns),
            ("implementation_run_id", "recommendation_id"),
        )

    def test_only_foreign_key_is_restrictive_run_reference(self):
        foreign_keys = constraints(self.table, ForeignKeyConstraint)
        self.assertEqual(len(foreign_keys), 1)
        foreign_key = foreign_keys[0]
        self.assertEqual(foreign_key.name, "fk_qm2_recommendations_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(
            next(iter(foreign_key.elements)).target_fullname,
            "quantmind2.implementation_runs.implementation_run_id",
        )

    def test_checks_cover_task_priority_and_reason(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {
                "ck_qm2_recommendations_task_nonempty",
                "ck_qm2_recommendations_priority",
                "ck_qm2_recommendations_reason_nonempty",
            },
        )
        self.assertIn("btrim(next_task_id) <> ''", actual["ck_qm2_recommendations_task_nonempty"])
        self.assertEqual(
            actual["ck_qm2_recommendations_priority"],
            enum_check_sql("priority", RecommendationPriority),
        )
        self.assertIn("btrim(reason) <> ''", actual["ck_qm2_recommendations_reason_nonempty"])

    def test_indexes_allow_multiple_recommendations_for_one_next_task(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_recommendations_run": ("implementation_run_id",),
                "ix_qm2_recommendations_task": ("next_task_id",),
                "ix_qm2_recommendations_priority": ("priority",),
                "ix_qm2_recommendations_run_priority": ("implementation_run_id", "priority"),
                "ix_qm2_recommendations_task_priority": ("next_task_id", "priority"),
            },
        )
        unique_columns = {
            tuple(column.name for column in item.columns)
            for item in constraints(self.table, UniqueConstraint)
        }
        self.assertNotIn(("implementation_run_id", "next_task_id"), unique_columns)


class LedgerAnnotationEnumNamingAndDdlTests(unittest.TestCase):
    tables = (LimitationRecord.__table__, RecommendedTaskRecord.__table__)

    def test_enum_constants_match_domain(self):
        self.assertEqual(LIMITATION_SEVERITY_VALUES, enum_values(LimitationSeverity))
        self.assertEqual(LIMITATION_STATUS_VALUES, enum_values(LimitationStatus))
        self.assertEqual(
            RECOMMENDATION_PRIORITY_VALUES,
            enum_values(RecommendationPriority),
        )

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
        for table in self.tables:
            for item in table.constraints:
                self.assertTrue(item.name.startswith(prefixes[type(item)]), item.name)
            for index in table.indexes:
                self.assertTrue(index.name.startswith("ix_"), index.name)

    def test_tables_and_indexes_compile_without_connection(self):
        for table in self.tables:
            ddl = postgresql_ddl(table)
            self.assertIn(f"CREATE TABLE quantmind2.{table.name}", ddl)
            self.assertIn("ON DELETE RESTRICT", ddl)

    def test_ddl_has_no_cascade_trigger_external_fk_or_secret(self):
        ddl = "\n".join(postgresql_ddl(table) for table in self.tables)
        upper = ddl.upper()
        self.assertNotIn("CASCADE", upper)
        self.assertNotIn("TRIGGER", upper)
        self.assertNotIn("REFERENCES quantmind2.components", ddl)
        self.assertNotIn("REFERENCES quantmind2.implementation_tasks", ddl)
        for marker in ("postgresql://", "password=", "secret=", "token=", "api_key="):
            self.assertNotIn(marker, ddl.lower())


if __name__ == "__main__":
    unittest.main()
