"""Static contract tests for Component and ADR reference ORM mappings."""

from __future__ import annotations

import ast
import inspect
import unittest

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql.sqltypes import String

from backend.services.api.models.base import Base
from backend.services.api.project_knowledge.persistence import orm_reference_models
from backend.services.api.project_knowledge.persistence.orm_reference_models import (
    ArchitectureDecisionReferenceRecord,
    ComponentReferenceRecord,
)
from backend.services.api.project_knowledge.persistence.orm_types import (
    ADR_REFERENCE_RELATION_VALUES,
    IDENTIFIER_LENGTH,
    IMPACT_TYPE_VALUES,
    POSTGRESQL_IDENTIFIER_LIMIT,
    enum_check_sql,
    enum_values,
)
from backend.services.engine.project_knowledge.domain.enums import (
    ADRReferenceRelation,
    ImpactType,
)


CORE_AND_DETAIL_TABLE_KEYS = {
    "quantmind2.implementation_tasks",
    "quantmind2.implementation_runs",
    "quantmind2.implementation_run_relationships",
    "quantmind2.implementation_changed_files",
    "quantmind2.implementation_changed_symbols",
    "quantmind2.implementation_test_executions",
    "quantmind2.implementation_artifacts",
}
REFERENCE_TABLE_KEYS = {
    "quantmind2.implementation_component_references",
    "quantmind2.implementation_adr_references",
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


class LedgerReferenceImportAndScopeTests(unittest.TestCase):
    models = (ComponentReferenceRecord, ArchitectureDecisionReferenceRecord)

    def test_models_use_selected_api_base(self):
        for model in self.models:
            self.assertIs(model.metadata, Base.metadata)
            self.assertIn(model.__table__.key, Base.metadata.tables)

    def test_exact_two_reference_tables_are_registered(self):
        actual = {
            key
            for key, table in Base.metadata.tables.items()
            if table.schema == "quantmind2" and key not in CORE_AND_DETAIL_TABLE_KEYS
        }
        self.assertEqual(actual, REFERENCE_TABLE_KEYS)

    def test_no_annotation_or_out_of_scope_table_is_registered(self):
        actual = {key for key, table in Base.metadata.tables.items() if table.schema == "quantmind2"}
        forbidden = ("limitation", "recommendation", "manifest", "report", "indexer", "migration")
        self.assertFalse(any(marker in key for key in actual for marker in forbidden))

    def test_module_has_no_engine_session_mapper_or_runtime_ddl(self):
        source = inspect.getsource(orm_reference_models)
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


class ComponentReferenceOrmTests(unittest.TestCase):
    table = ComponentReferenceRecord.__table__

    def test_table_schema_columns_types_and_nullability(self):
        self.assertEqual(self.table.schema, "quantmind2")
        self.assertEqual(self.table.name, "implementation_component_references")
        self.assertEqual(
            tuple(self.table.columns.keys()),
            ("implementation_run_id", "component_id", "impact_type"),
        )
        self.assertTrue(all(not column.nullable for column in self.table.columns))
        self.assertIsInstance(self.table.c.implementation_run_id.type, String)
        self.assertEqual(self.table.c.implementation_run_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.component_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.impact_type.type.length, 32)

    def test_natural_identity_is_the_named_composite_primary_key(self):
        primary_key = constraints(self.table, PrimaryKeyConstraint)[0]
        self.assertEqual(primary_key.name, "pk_qm2_component_refs")
        self.assertEqual(
            tuple(column.name for column in primary_key.columns),
            ("implementation_run_id", "component_id"),
        )
        self.assertNotIn("impact_type", tuple(column.name for column in primary_key.columns))
        self.assertNotIn("component_reference_id", self.table.columns)

    def test_only_foreign_key_is_restrictive_run_reference(self):
        foreign_keys = constraints(self.table, ForeignKeyConstraint)
        self.assertEqual(len(foreign_keys), 1)
        foreign_key = foreign_keys[0]
        self.assertEqual(foreign_key.name, "fk_qm2_component_refs_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(
            next(iter(foreign_key.elements)).target_fullname,
            "quantmind2.implementation_runs.implementation_run_id",
        )

    def test_nonblank_and_domain_enum_checks_are_exact(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {"ck_qm2_component_refs_id_nonempty", "ck_qm2_component_refs_impact_type"},
        )
        self.assertIn("btrim(component_id) <> ''", actual["ck_qm2_component_refs_id_nonempty"])
        self.assertEqual(
            actual["ck_qm2_component_refs_impact_type"],
            enum_check_sql("impact_type", ImpactType),
        )

    def test_indexes_support_cross_run_reference_queries_without_pk_duplication(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_component_refs_component": ("component_id",),
                "ix_qm2_component_refs_impact": ("impact_type",),
                "ix_qm2_component_refs_component_impact": ("component_id", "impact_type"),
            },
        )
        self.assertNotIn(
            ("implementation_run_id", "component_id"),
            index_columns(self.table).values(),
        )


class ArchitectureDecisionReferenceOrmTests(unittest.TestCase):
    table = ArchitectureDecisionReferenceRecord.__table__

    def test_table_schema_columns_types_and_nullability(self):
        self.assertEqual(self.table.schema, "quantmind2")
        self.assertEqual(self.table.name, "implementation_adr_references")
        self.assertEqual(
            tuple(self.table.columns.keys()),
            ("implementation_run_id", "adr_id", "relation"),
        )
        self.assertTrue(all(not column.nullable for column in self.table.columns))
        self.assertEqual(self.table.c.implementation_run_id.type.length, IDENTIFIER_LENGTH)
        self.assertEqual(self.table.c.adr_id.type.length, 32)
        self.assertEqual(self.table.c.relation.type.length, 32)

    def test_natural_identity_is_the_named_composite_primary_key(self):
        primary_key = constraints(self.table, PrimaryKeyConstraint)[0]
        self.assertEqual(primary_key.name, "pk_qm2_adr_refs")
        self.assertEqual(
            tuple(column.name for column in primary_key.columns),
            ("implementation_run_id", "adr_id"),
        )
        self.assertNotIn("relation", tuple(column.name for column in primary_key.columns))
        self.assertNotIn("adr_reference_id", self.table.columns)

    def test_only_foreign_key_is_restrictive_run_reference(self):
        foreign_keys = constraints(self.table, ForeignKeyConstraint)
        self.assertEqual(len(foreign_keys), 1)
        foreign_key = foreign_keys[0]
        self.assertEqual(foreign_key.name, "fk_qm2_adr_refs_run")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")
        self.assertEqual(
            next(iter(foreign_key.elements)).target_fullname,
            "quantmind2.implementation_runs.implementation_run_id",
        )

    def test_format_and_domain_enum_checks_are_exact(self):
        actual = checks_by_name(self.table)
        self.assertEqual(
            set(actual),
            {"ck_qm2_adr_refs_id_format", "ck_qm2_adr_refs_relation"},
        )
        self.assertEqual(actual["ck_qm2_adr_refs_id_format"], "adr_id ~ '^ADR-[0-9]{4}$'")
        self.assertEqual(
            actual["ck_qm2_adr_refs_relation"],
            enum_check_sql("relation", ADRReferenceRelation),
        )

    def test_indexes_support_cross_run_reference_queries_without_pk_duplication(self):
        self.assertEqual(
            index_columns(self.table),
            {
                "ix_qm2_adr_refs_adr": ("adr_id",),
                "ix_qm2_adr_refs_relation": ("relation",),
                "ix_qm2_adr_refs_adr_relation": ("adr_id", "relation"),
            },
        )
        self.assertNotIn(
            ("implementation_run_id", "adr_id"),
            index_columns(self.table).values(),
        )


class LedgerReferenceEnumNamingAndDdlTests(unittest.TestCase):
    tables = (
        ComponentReferenceRecord.__table__,
        ArchitectureDecisionReferenceRecord.__table__,
    )

    def test_enum_constants_match_domain(self):
        self.assertEqual(IMPACT_TYPE_VALUES, enum_values(ImpactType))
        self.assertEqual(
            ADR_REFERENCE_RELATION_VALUES,
            enum_values(ADRReferenceRelation),
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
            self.assertIn("PRIMARY KEY (implementation_run_id", ddl)
            self.assertIn("ON DELETE RESTRICT", ddl)

    def test_ddl_has_no_cascade_trigger_external_fk_or_secret(self):
        ddl = "\n".join(postgresql_ddl(table) for table in self.tables)
        upper = ddl.upper()
        self.assertNotIn("CASCADE", upper)
        self.assertNotIn("TRIGGER", upper)
        self.assertNotIn("REFERENCES quantmind2.components", ddl)
        self.assertNotIn("REFERENCES quantmind2.architecture_decisions", ddl)
        for marker in ("postgresql://", "password=", "secret=", "token=", "api_key="):
            self.assertNotIn(marker, ddl.lower())


if __name__ == "__main__":
    unittest.main()
