"""Contract tests for the pure ImplementationTask Domain/ORM mapper."""

from __future__ import annotations

import ast
import inspect
import unittest
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from backend.services.api.project_knowledge.persistence.mappers import (
    MAPPER_CONTRACT_VERSION,
    DomainToRecordError,
    InvalidMapperValueError,
    LedgerMapperError,
    MapperContractVersionError,
    RecordToDomainError,
    UnknownEnumValueError,
    datetime_from_storage,
    datetime_to_storage,
    enum_from_storage,
    enum_to_storage,
    implementation_task_from_record,
    implementation_task_to_record,
    json_array_to_string_tuple,
    string_tuple_to_json_array,
)
from backend.services.api.project_knowledge.persistence.mappers import common, errors, run, task
from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationTaskRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    ImplementationTaskStatus,
)
from backend.services.engine.project_knowledge.domain.models import ImplementationTask


UTC = timezone.utc
OFFSET = timezone(timedelta(hours=8))


def make_task(*, parent: str | None = None, created_at: datetime | None = None):
    return ImplementationTask(
        task_id="QM2-P0-TEST",
        parent_task_id=parent,
        title="Task title",
        objective="Task objective",
        scope=("first", "repeat", "repeat"),
        explicit_non_goals=("no database", "no API"),
        status=ImplementationTaskStatus.READY,
        created_at=created_at or datetime(2026, 7, 14, 12, 3, 4, 567890, tzinfo=UTC),
    )


def make_record(**overrides):
    values = {
        "task_id": "QM2-P0-TEST",
        "parent_task_id": None,
        "title": "Task title",
        "objective": "Task objective",
        "scope": ["first", "repeat", "repeat"],
        "explicit_non_goals": ["no database", "no API"],
        "status": "ready",
        "created_at": datetime(2026, 7, 14, 12, 3, 4, 567890, tzinfo=UTC),
        "version": 1,
    }
    values.update(overrides)
    return ImplementationTaskRecord(**values)


class MapperErrorTests(unittest.TestCase):
    def test_error_metadata_and_string_are_stable_and_safe(self):
        error = RecordToDomainError(
            "stored value is invalid",
            object_type="ImplementationTask",
            safe_identity="QM2-P0-TEST",
            field_name="status",
            underlying_error_type="ValueError",
            error_code="UNKNOWN_ENUM",
        )
        self.assertEqual(error.error_code, "UNKNOWN_ENUM")
        self.assertEqual(error.safe_identity, "QM2-P0-TEST")
        self.assertEqual(error.underlying_error_type, "ValueError")
        self.assertEqual(
            str(error),
            "UNKNOWN_ENUM/ImplementationTask/QM2-P0-TEST/status: stored value is invalid",
        )

    def test_error_hierarchy_is_transport_and_sqlalchemy_independent(self):
        for error_type in (
            LedgerMapperError,
            RecordToDomainError,
            DomainToRecordError,
            UnknownEnumValueError,
            InvalidMapperValueError,
            MapperContractVersionError,
        ):
            self.assertTrue(issubclass(error_type, ValueError))
        source = inspect.getsource(errors).lower()
        self.assertNotIn("fastapi", source)
        self.assertNotIn("http", source)
        self.assertNotIn("sqlalchemy", source)

    def test_domain_failure_does_not_leak_record_or_sensitive_text(self):
        objective = "TOP-SECRET-OBJECTIVE-" + "x" * 50
        record = make_record(
            task_id="password:secret",
            objective=objective,
            parent_task_id="password:secret",
        )
        with self.assertRaises(RecordToDomainError) as captured:
            implementation_task_from_record(record)
        rendered = str(captured.exception)
        self.assertNotIn(objective, rendered)
        self.assertNotIn("password:secret", rendered)
        self.assertNotIn("ImplementationTaskRecord(", rendered)


class CommonEnumConversionTests(unittest.TestCase):
    def test_enum_round_trip_uses_value_not_name(self):
        raw = enum_to_storage(
            ImplementationTaskStatus.READY,
            field_name="status",
        )
        self.assertEqual(raw, "ready")
        self.assertIs(
            enum_from_storage(
                ImplementationTaskStatus,
                raw,
                object_type="ImplementationTask",
                identity="QM2-P0-TEST",
                field_name="status",
            ),
            ImplementationTaskStatus.READY,
        )

    def test_unknown_case_whitespace_and_non_string_values_fail(self):
        for value in ("unknown", "READY", " ready ", None, True, 1):
            with self.subTest(value=value):
                with self.assertRaises(UnknownEnumValueError) as captured:
                    enum_from_storage(
                        ImplementationTaskStatus,
                        value,
                        object_type="ImplementationTask",
                        identity="QM2-P0-TEST",
                        field_name="status",
                    )
                self.assertEqual(captured.exception.error_code, "UNKNOWN_ENUM")

    def test_forward_conversion_rejects_strings_and_non_string_enum_values(self):
        class IntegerEnum(Enum):
            ONE = 1

        for value in ("ready", IntegerEnum.ONE):
            with self.subTest(value=value):
                with self.assertRaises(InvalidMapperValueError):
                    enum_to_storage(value, field_name="status")


class CommonDatetimeConversionTests(unittest.TestCase):
    def test_both_directions_normalize_to_utc_and_preserve_microseconds(self):
        source = datetime(2026, 7, 14, 20, 3, 4, 567890, tzinfo=OFFSET)
        for result in (
            datetime_to_storage(source, field_name="created_at"),
            datetime_from_storage(
                source,
                object_type="ImplementationTask",
                identity="QM2-P0-TEST",
                field_name="created_at",
            ),
        ):
            self.assertEqual(result, datetime(2026, 7, 14, 12, 3, 4, 567890, tzinfo=UTC))
            self.assertEqual(result.microsecond, 567890)
            self.assertIs(result.tzinfo, UTC)

    def test_naive_and_non_datetime_values_fail_without_timezone_guessing(self):
        for value in (datetime(2026, 7, 14), "2026-07-14T00:00:00Z", None):
            with self.subTest(value=value):
                with self.assertRaises(InvalidMapperValueError):
                    datetime_to_storage(value, field_name="created_at")
                with self.assertRaises(RecordToDomainError):
                    datetime_from_storage(
                        value,
                        object_type="ImplementationTask",
                        identity=None,
                        field_name="created_at",
                    )


class CommonJsonConversionTests(unittest.TestCase):
    def test_tuple_to_new_list_preserves_order_and_duplicates(self):
        source = ("b", "a", "a")
        result = string_tuple_to_json_array(source, field_name="scope")
        self.assertEqual(result, ["b", "a", "a"])
        self.assertIsNot(result, source)
        result.append("new")
        self.assertEqual(source, ("b", "a", "a"))

    def test_list_or_tuple_to_new_tuple_preserves_values(self):
        for source in (["b", "a", "a"], ("b", "a", "a")):
            result = json_array_to_string_tuple(
                source,
                object_type="ImplementationTask",
                identity="QM2-P0-TEST",
                field_name="scope",
            )
            self.assertEqual(result, ("b", "a", "a"))
            self.assertIsNot(result, source)

    def test_invalid_forward_and_reverse_shapes_fail(self):
        for value in (["not", "tuple"], {"item": "value"}, None, ("ok", 1)):
            with self.subTest(direction="forward", value=value):
                with self.assertRaises(InvalidMapperValueError) as captured:
                    string_tuple_to_json_array(value, field_name="scope")
                self.assertEqual(captured.exception.error_code, "INVALID_JSON_SHAPE")
        for value in ({"item": "value"}, 1, True, None, ["ok", 1], ["ok", None]):
            with self.subTest(direction="reverse", value=value):
                with self.assertRaises(RecordToDomainError) as captured:
                    json_array_to_string_tuple(
                        value,
                        object_type="ImplementationTask",
                        identity=None,
                        field_name="scope",
                    )
                self.assertEqual(captured.exception.error_code, "INVALID_JSON_SHAPE")


class ImplementationTaskMapperTests(unittest.TestCase):
    def test_domain_to_record_maps_every_field_and_initial_version(self):
        domain = make_task(parent="QM2-P0-PARENT")
        record = implementation_task_to_record(domain)
        self.assertIsInstance(record, ImplementationTaskRecord)
        self.assertEqual(record.task_id, domain.task_id)
        self.assertEqual(record.parent_task_id, "QM2-P0-PARENT")
        self.assertEqual(record.title, domain.title)
        self.assertEqual(record.objective, domain.objective)
        self.assertEqual(record.scope, list(domain.scope))
        self.assertEqual(record.explicit_non_goals, list(domain.explicit_non_goals))
        self.assertEqual(record.status, "ready")
        self.assertEqual(record.created_at, domain.created_at)
        self.assertEqual(record.version, 1)

    def test_domain_to_record_returns_new_records_and_does_not_mutate_domain(self):
        domain = make_task()
        before = domain
        first = implementation_task_to_record(domain)
        second = implementation_task_to_record(domain)
        self.assertIsNot(first, second)
        self.assertEqual(domain, before)
        self.assertIsNot(first.scope, second.scope)

    def test_domain_to_record_rejects_dict_and_duck_type(self):
        class Duck:
            task_id = "QM2-P0-TEST"

        for value in ({"task_id": "QM2-P0-TEST"}, Duck(), None):
            with self.subTest(value=value):
                with self.assertRaises(DomainToRecordError) as captured:
                    implementation_task_to_record(value)
                self.assertEqual(captured.exception.error_code, "INVALID_OBJECT_TYPE")

    def test_record_to_domain_maps_parent_enum_tuple_time_and_ignores_version(self):
        source_time = datetime(2026, 7, 14, 20, 3, 4, 567890, tzinfo=OFFSET)
        record = make_record(
            parent_task_id="QM2-P0-PARENT",
            created_at=source_time,
            version=7,
        )
        domain = implementation_task_from_record(record)
        self.assertEqual(domain.parent_task_id, "QM2-P0-PARENT")
        self.assertIs(domain.status, ImplementationTaskStatus.READY)
        self.assertEqual(domain.scope, ("first", "repeat", "repeat"))
        self.assertEqual(domain.created_at.tzinfo, UTC)
        self.assertEqual(domain.created_at.microsecond, 567890)
        self.assertFalse(hasattr(domain, "version"))

    def test_record_to_domain_rejects_invalid_version(self):
        for value in (0, -1, True, 1.5, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_task_from_record(make_record(version=value))
                self.assertEqual(captured.exception.error_code, "INVALID_VERSION")

    def test_record_to_domain_rejects_unknown_status_json_and_naive_time(self):
        cases = (
            ({"status": "READY"}, "UNKNOWN_ENUM"),
            ({"scope": {"bad": "shape"}}, "INVALID_JSON_SHAPE"),
            ({"created_at": datetime(2026, 7, 14)}, "INVALID_TIME"),
        )
        for override, code in cases:
            with self.subTest(override=override):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_task_from_record(make_record(**override))
                self.assertEqual(captured.exception.error_code, code)

    def test_record_to_domain_rejects_unloaded_column_without_descriptor_access(self):
        record = make_record()
        del vars(record)["status"]
        with self.assertRaises(RecordToDomainError) as captured:
            implementation_task_from_record(record)
        self.assertEqual(captured.exception.error_code, "MISSING_REQUIRED_VALUE")
        self.assertEqual(captured.exception.field_name, "status")

    def test_record_to_domain_wraps_domain_validation_safely(self):
        objective = "DO-NOT-LEAK-" + "x" * 100
        with self.assertRaises(RecordToDomainError) as captured:
            implementation_task_from_record(
                make_record(parent_task_id="QM2-P0-TEST", objective=objective)
            )
        error = captured.exception
        self.assertEqual(error.error_code, "INVALID_STATE_COMBINATION")
        self.assertEqual(error.field_name, "parent_task_id")
        self.assertEqual(error.underlying_error_type, "InvalidStateCombinationError")
        self.assertNotIn(objective, str(error))

    def test_record_to_domain_rejects_non_record(self):
        for value in ({"task_id": "QM2-P0-TEST"}, make_task(), None):
            with self.subTest(value=value):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_task_from_record(value)
                self.assertEqual(captured.exception.error_code, "INVALID_OBJECT_TYPE")

    def test_domain_round_trip_with_parent_offset_and_duplicates(self):
        for parent in (None, "QM2-P0-PARENT"):
            with self.subTest(parent=parent):
                original = make_task(
                    parent=parent,
                    created_at=datetime(2026, 7, 14, 20, 3, 4, 567890, tzinfo=OFFSET),
                )
                result = implementation_task_from_record(
                    implementation_task_to_record(original)
                )
                self.assertEqual(result, original)
                self.assertEqual(result.scope, ("first", "repeat", "repeat"))

    def test_record_business_values_round_trip_and_version_resets(self):
        original = make_record(version=9)
        rebuilt = implementation_task_to_record(
            implementation_task_from_record(original)
        )
        for field in (
            "task_id",
            "parent_task_id",
            "title",
            "objective",
            "scope",
            "explicit_non_goals",
            "status",
            "created_at",
        ):
            self.assertEqual(getattr(rebuilt, field), getattr(original, field))
        self.assertEqual(rebuilt.version, 1)


class MapperScopeAndPurityTests(unittest.TestCase):
    def test_contract_version_and_exact_package_files(self):
        self.assertEqual(MAPPER_CONTRACT_VERSION, "1.0.0")
        root = Path(common.__file__).resolve().parent
        self.assertEqual(
            {path.name for path in root.glob("*.py")},
            {
                "__init__.py", "errors.py", "common.py", "task.py", "run.py",
                "identity.py", "relationship.py", "details.py", "references.py",
                "annotations.py",
            },
        )

    def test_complete_mapper_symbols_exist_without_runtime_layers(self):
        root = Path(common.__file__).resolve().parent
        source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
        required = (
            "run_relationship_to_record",
            "run_relationship_from_record",
            "changed_file_to_record",
            "changed_symbol_to_record",
            "implementation_artifact_to_record",
            "limitation_to_record",
            "recommended_task_to_record",
            "component_reference_to_record",
            "architecture_decision_reference_to_record",
        )
        for marker in required:
            self.assertIn(marker, source)
        for marker in ("create_engine(", "sessionmaker(", "run_from_manifest"):
            self.assertNotIn(marker, source)

    def test_mapper_source_has_no_io_runtime_or_database_behavior(self):
        from backend.services.api.project_knowledge.persistence.mappers import (
            annotations, details, identity, references, relationship,
        )
        modules = (
            common, errors, task, run, annotations, details, identity, references,
            relationship,
        )
        forbidden_imports = {
            "asyncio",
            "git",
            "httpx",
            "os",
            "pathlib",
            "random",
            "requests",
            "socket",
            "sqlalchemy.exc",
            "subprocess",
            "urllib.request",
        }
        forbidden_calls = {
            "add",
            "commit",
            "connect",
            "create_engine",
            "execute",
            "flush",
            "getenv",
            "merge",
            "open",
            "query",
            "refresh",
            "rollback",
            "sessionmaker",
            "urandom",
            "uuid4",
        }
        for module in modules:
            tree = ast.parse(inspect.getsource(module))
            imports = {
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            }
            imports.update(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            self.assertTrue(forbidden_imports.isdisjoint(imports), module.__name__)
            calls = {
                node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, (ast.Attribute, ast.Name))
            }
            self.assertTrue(forbidden_calls.isdisjoint(calls), module.__name__)


if __name__ == "__main__":
    unittest.main()
