"""Complete Ledger Mapper round-trip, identity, error, and drift verification."""

from __future__ import annotations

import ast
from dataclasses import fields
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import unittest

from backend.services.api.project_knowledge.persistence import mappers
from backend.services.api.project_knowledge.persistence.mappers.errors import (
    DomainToRecordError,
    RecordToDomainError,
)
from backend.services.api.project_knowledge.persistence.orm_annotation_models import (
    LimitationRecord,
    RecommendedTaskRecord,
)
from backend.services.api.project_knowledge.persistence.orm_detail_models import (
    ChangedFileRecord,
    ChangedSymbolRecord,
    ImplementationArtifactRecord,
    TestExecutionRecord,
)
from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationRunRecord,
    ImplementationTaskRecord,
    RunRelationshipRecord,
)
from backend.services.api.project_knowledge.persistence.orm_reference_models import (
    ArchitectureDecisionReferenceRecord,
    ComponentReferenceRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    ADRReferenceRelation,
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    FileChangeType,
    ImpactType,
    ImplementationRunStatus,
    ImplementationTaskStatus,
    LimitationSeverity,
    LimitationStatus,
    RecommendationPriority,
    RunRelationshipType,
    SymbolChangeType,
    SymbolType,
    TestExecutionStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.domain.models import (
    ArchitectureDecisionReference,
    ChangedFile,
    ChangedSymbol,
    ComponentReference,
    ImplementationArtifact,
    ImplementationRun,
    ImplementationTask,
    Limitation,
    RecommendedTask,
    RunRelationship,
    TestExecution,
)


NOW = datetime(2026, 7, 15, 1, 2, 3, 456789, tzinfo=timezone(timedelta(hours=8)))
UTC_NOW = NOW.astimezone(timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64
COMMIT = "1" * 40
RUN_ID = "run-001"
ROOT = Path(__file__).resolve().parents[3]


def domain_values():  # noqa: ANN201
    task = ImplementationTask(
        "task-001", None, "Task", "Objective", ("scope",), ("non-goal",),
        ImplementationTaskStatus.READY, NOW,
    )
    run = ImplementationRun(
        RUN_ID, task.task_id, "quantmind-main", "master", COMMIT, None,
        ImplementationRunStatus.COMPLETED_UNCOMMITTED, CompletionLevel.COMPLETE,
        VerificationLevel.TARGETED_TESTS, False, True, NOW, NOW,
        "codex", "1.0.0", "docs/manifest.json", HASH_A,
        "docs/report.md", HASH_B, None, None,
        ConsistencyStatus.UNVERIFIED, CanonicalStatus.NONCANONICAL,
    )
    relationship = RunRelationship(
        "rel-001", "run-previous", RUN_ID, RunRelationshipType.CONTINUES,
        "Continues the previous bounded task", NOW,
    )
    changed_file = ChangedFile(
        RUN_ID, "src/因子.py", FileChangeType.MODIFIED, HASH_A, HASH_B,
    )
    changed_symbol = ChangedSymbol(
        RUN_ID, "src/因子.py", "Factor.run", SymbolType.METHOD,
        SymbolChangeType.MODIFIED,
    )
    test_execution = TestExecution(
        "test-001", RUN_ID, "python -m unittest safe", "Mapper verification",
        TestExecutionStatus.PASSED, 7, 0, 1, None,
        "artifact://mapper/results", HASH_A,
    )
    artifact = ImplementationArtifact(
        "artifact-001", RUN_ID, "test-result", "docs/results.json", HASH_A,
        "1.0.0", 42,
    )
    component = ComponentReference(RUN_ID, "quantmind2.project_knowledge", ImpactType.MODIFIED)
    adr = ArchitectureDecisionReference(RUN_ID, "ADR-0005", ADRReferenceRelation.CONFORMS_TO)
    limitation = Limitation(
        "limitation-001", RUN_ID, LimitationSeverity.MEDIUM, None,
        "Migration remains deferred", LimitationStatus.OPEN,
    )
    recommendation = RecommendedTask(
        "recommendation-001", RUN_ID, "QM2-P0-002A2b",
        RecommendationPriority.P0, "Verify isolated PostgreSQL persistence",
    )
    return (
        task, run, relationship, changed_file, changed_symbol, test_execution,
        artifact, component, adr, limitation, recommendation,
    )


MAPPER_PAIRS = (
    (mappers.implementation_task_to_record, mappers.implementation_task_from_record, False),
    (mappers.implementation_run_to_record, mappers.implementation_run_from_record, False),
    (mappers.run_relationship_to_record, mappers.run_relationship_from_record, False),
    (mappers.changed_file_to_record, mappers.changed_file_from_record, True),
    (mappers.changed_symbol_to_record, mappers.changed_symbol_from_record, True),
    (mappers.test_execution_to_record, mappers.test_execution_from_record, True),
    (mappers.implementation_artifact_to_record, mappers.implementation_artifact_from_record, True),
    (mappers.component_reference_to_record, mappers.component_reference_from_record, True),
    (
        mappers.architecture_decision_reference_to_record,
        mappers.architecture_decision_reference_from_record,
        True,
    ),
    (mappers.limitation_to_record, mappers.limitation_from_record, True),
    (mappers.recommended_task_to_record, mappers.recommended_task_from_record, True),
)


class CompleteRoundTripTests(unittest.TestCase):
    def test_all_eleven_domain_objects_round_trip(self):
        for item, (to_record, from_record, needs_parent) in zip(domain_values(), MAPPER_PAIRS):
            with self.subTest(domain_type=type(item).__name__):
                record = to_record(RUN_ID, item) if needs_parent else to_record(item)
                self.assertEqual(from_record(record), item)

    def test_all_remaining_orm_business_fields_round_trip(self):
        for item, (to_record, from_record, needs_parent) in zip(domain_values()[2:], MAPPER_PAIRS[2:]):
            first = to_record(RUN_ID, item) if needs_parent else to_record(item)
            rebuilt_domain = from_record(first)
            second = to_record(RUN_ID, rebuilt_domain) if needs_parent else to_record(rebuilt_domain)
            columns = tuple(column.name for column in first.__table__.columns)
            with self.subTest(record_type=type(first).__name__):
                self.assertEqual(
                    {name: getattr(first, name) for name in columns},
                    {name: getattr(second, name) for name in columns},
                )

    def test_relationship_datetime_is_normalized_to_utc(self):
        relationship = domain_values()[2]
        record = mappers.run_relationship_to_record(relationship)
        self.assertEqual(record.created_at, UTC_NOW)
        self.assertEqual(mappers.run_relationship_from_record(record).created_at, UTC_NOW)

    def test_artifact_uri_and_nullable_values_round_trip(self):
        item = ImplementationArtifact(
            "artifact-uri", RUN_ID, "report", "s3://bucket/key", None, None, None
        )
        self.assertEqual(
            mappers.implementation_artifact_from_record(
                mappers.implementation_artifact_to_record(RUN_ID, item)
            ),
            item,
        )

    def test_parent_run_mismatch_is_rejected(self):
        for item, (to_record, _, needs_parent) in zip(domain_values(), MAPPER_PAIRS):
            if not needs_parent:
                continue
            with self.subTest(domain_type=type(item).__name__):
                with self.assertRaises(DomainToRecordError) as captured:
                    to_record("different-run", item)
                self.assertEqual(captured.exception.error_code, "PARENT_RUN_ID_MISMATCH")


class TechnicalIdentityTests(unittest.TestCase):
    def test_all_frozen_vectors(self):
        path = ROOT / "docs/quantmind2/implementation/test_vectors/ledger_mapper_identity_v1.json"
        vectors = json.loads(path.read_text(encoding="utf-8"))["vectors"]
        for vector in vectors:
            values = vector["input"]
            with self.subTest(case=vector["case"]):
                if vector["kind"] == "changed_file":
                    actual = mappers.changed_file_record_id(
                        implementation_run_id=values["implementation_run_id"],
                        path=values["path"],
                        change_type=FileChangeType(values["change_type"]),
                    )
                else:
                    actual = mappers.changed_symbol_record_id(
                        implementation_run_id=values["implementation_run_id"],
                        file_path=values["file_path"],
                        qualified_name=values["qualified_name"],
                    )
                self.assertEqual(actual, vector["expected_id"])

    def test_unicode_nfc_is_stable_and_case_is_preserved(self):
        composed = mappers.changed_symbol_record_id(
            implementation_run_id=RUN_ID,
            file_path="docs/café.py",
            qualified_name="Café.run",
        )
        decomposed = mappers.changed_symbol_record_id(
            implementation_run_id=RUN_ID,
            file_path="docs/cafe\u0301.py",
            qualified_name="Cafe\u0301.run",
        )
        upper = mappers.changed_symbol_record_id(
            implementation_run_id=RUN_ID,
            file_path="Docs/café.py",
            qualified_name="Café.run",
        )
        self.assertEqual(composed, decomposed)
        self.assertNotEqual(composed, upper)

    def test_identity_excludes_non_identity_content(self):
        first = ChangedFile(RUN_ID, "x.py", FileChangeType.MODIFIED, HASH_A, HASH_B)
        second = ChangedFile(RUN_ID, "x.py", FileChangeType.MODIFIED, "c" * 64, "d" * 64)
        self.assertEqual(
            mappers.changed_file_to_record(RUN_ID, first).changed_file_id,
            mappers.changed_file_to_record(RUN_ID, second).changed_file_id,
        )
        symbols = (
            ChangedSymbol(RUN_ID, "x.py", "X.run", SymbolType.METHOD, SymbolChangeType.ADDED),
            ChangedSymbol(RUN_ID, "x.py", "X.run", SymbolType.FUNCTION, SymbolChangeType.DELETED),
        )
        self.assertEqual(
            mappers.changed_symbol_to_record(RUN_ID, symbols[0]).changed_symbol_id,
            mappers.changed_symbol_to_record(RUN_ID, symbols[1]).changed_symbol_id,
        )

    def test_wrong_stored_technical_ids_are_rejected(self):
        file_record = mappers.changed_file_to_record(RUN_ID, domain_values()[3])
        file_record.changed_file_id = "cf_" + "0" * 64
        symbol_record = mappers.changed_symbol_to_record(RUN_ID, domain_values()[4])
        symbol_record.changed_symbol_id = "cs_" + "0" * 64
        for record, converter in (
            (file_record, mappers.changed_file_from_record),
            (symbol_record, mappers.changed_symbol_from_record),
        ):
            with self.subTest(record_type=type(record).__name__):
                with self.assertRaises(RecordToDomainError) as captured:
                    converter(record)
                self.assertEqual(captured.exception.error_code, "MAPPER_IDENTITY_MISMATCH")


class EnumAndInvalidRecordTests(unittest.TestCase):
    def test_every_file_change_enum_round_trips(self):
        cases = {
            FileChangeType.ADDED: (None, HASH_A, None),
            FileChangeType.DELETED: (HASH_A, None, None),
            FileChangeType.MODIFIED: (HASH_A, HASH_B, None),
            FileChangeType.RENAMED: (HASH_A, HASH_A, "old.py"),
            FileChangeType.UNCHANGED: (HASH_A, HASH_A, None),
        }
        for change_type, (before, after, previous) in cases.items():
            item = ChangedFile(RUN_ID, "new.py", change_type, before, after, previous)
            with self.subTest(change_type=change_type):
                self.assertEqual(
                    mappers.changed_file_from_record(
                        mappers.changed_file_to_record(RUN_ID, item)
                    ),
                    item,
                )

    def test_every_symbol_enum_value_converts_exactly(self):
        for symbol_type in SymbolType:
            for change_type in SymbolChangeType:
                item = ChangedSymbol(RUN_ID, "x.py", "X", symbol_type, change_type)
                with self.subTest(symbol_type=symbol_type, change_type=change_type):
                    self.assertEqual(
                        mappers.changed_symbol_from_record(
                            mappers.changed_symbol_to_record(RUN_ID, item)
                        ),
                        item,
                    )

    def test_unknown_enums_and_missing_columns_fail_atomically(self):
        records_and_converters = []
        for item, (to_record, from_record, needs_parent) in zip(domain_values()[2:], MAPPER_PAIRS[2:]):
            record = to_record(RUN_ID, item) if needs_parent else to_record(item)
            records_and_converters.append((record, from_record))
        enum_fields = (
            "relationship_type", "change_type", "symbol_type", "status",
            None, "impact_type", "relation", "severity", "priority",
        )
        for (record, converter), enum_field in zip(records_and_converters, enum_fields):
            with self.subTest(record_type=type(record).__name__, failure="missing"):
                missing = type(record)(**{
                    key: value for key, value in vars(record).items() if key != "_sa_instance_state"
                })
                vars(missing).pop(next(column.name for column in record.__table__.columns))
                with self.assertRaises(RecordToDomainError):
                    converter(missing)
            if enum_field is not None:
                setattr(record, enum_field, "unsupported-enum")
                with self.subTest(record_type=type(record).__name__, failure="enum"):
                    with self.assertRaises(RecordToDomainError):
                        converter(record)

    def test_invalid_domain_shapes_from_records_are_safe(self):
        test = mappers.test_execution_to_record(RUN_ID, domain_values()[5])
        test.status = TestExecutionStatus.FAILED.value
        test.failed_count = 0
        artifact = mappers.implementation_artifact_to_record(RUN_ID, domain_values()[6])
        artifact.path_or_uri = "../escape"
        limitation = mappers.limitation_to_record(RUN_ID, domain_values()[9])
        limitation.description = "password=do-not-leak"
        recommendation = mappers.recommended_task_to_record(RUN_ID, domain_values()[10])
        recommendation.reason = "token=do-not-leak"
        for record, converter, secret in (
            (test, mappers.test_execution_from_record, None),
            (artifact, mappers.implementation_artifact_from_record, None),
            (limitation, mappers.limitation_from_record, "do-not-leak"),
            (recommendation, mappers.recommended_task_from_record, "do-not-leak"),
        ):
            with self.subTest(record_type=type(record).__name__):
                with self.assertRaises(RecordToDomainError) as captured:
                    converter(record)
                if secret:
                    self.assertNotIn(secret, str(captured.exception))


class MapperDriftAndPurityTests(unittest.TestCase):
    def test_domain_and_orm_fields_match_explicit_allowlists(self):
        pairs = (
            (RunRelationship, RunRelationshipRecord, ()),
            (ChangedFile, ChangedFileRecord, ("changed_file_id",)),
            (ChangedSymbol, ChangedSymbolRecord, ("changed_symbol_id",)),
            (TestExecution, TestExecutionRecord, ()),
            (ImplementationArtifact, ImplementationArtifactRecord, ()),
            (ComponentReference, ComponentReferenceRecord, ()),
            (ArchitectureDecisionReference, ArchitectureDecisionReferenceRecord, ()),
            (Limitation, LimitationRecord, ()),
            (RecommendedTask, RecommendedTaskRecord, ()),
        )
        for domain_type, record_type, technical in pairs:
            domain_fields = {field.name for field in fields(domain_type)}
            orm_fields = {column.name for column in record_type.__table__.columns}
            with self.subTest(domain_type=domain_type.__name__):
                self.assertEqual(orm_fields, domain_fields | set(technical))

    def test_complete_public_mapper_inventory(self):
        expected = {
            "implementation_task", "implementation_run", "run_relationship",
            "changed_file", "changed_symbol", "test_execution",
            "implementation_artifact", "component_reference",
            "architecture_decision_reference", "limitation", "recommended_task",
        }
        exported = set(mappers.__all__)
        for prefix in expected:
            self.assertIn(f"{prefix}_to_record", exported)
            self.assertIn(f"{prefix}_from_record", exported)

    def test_mapper_modules_have_no_forbidden_side_effect_calls_or_imports(self):
        modules = (
            mappers.common, mappers.identity, mappers.relationship, mappers.details,
            mappers.references, mappers.annotations, mappers.task, mappers.run,
        )
        forbidden_imports = {
            "asyncio", "git", "httpx", "os", "pathlib", "random", "requests",
            "socket", "subprocess", "urllib.request",
        }
        forbidden_calls = {
            "add", "commit", "connect", "create_engine", "execute", "exists",
            "flush", "getenv", "merge", "open", "query", "refresh", "rollback",
            "sessionmaker", "urandom", "uuid4",
        }
        for module in modules:
            tree = ast.parse(inspect.getsource(module))
            imports = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imports.update(
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            )
            calls = {
                node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
            }
            with self.subTest(module=module.__name__):
                self.assertTrue(forbidden_imports.isdisjoint(imports))
                self.assertTrue(forbidden_calls.isdisjoint(calls))


if __name__ == "__main__":
    unittest.main()
