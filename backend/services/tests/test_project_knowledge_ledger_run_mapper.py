"""Contract tests for the pure ImplementationRun Domain/ORM mapper."""

from __future__ import annotations

import ast
import inspect
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.services.api.project_knowledge.persistence.mappers import (
    DomainToRecordError,
    RecordToDomainError,
    implementation_run_from_record,
    implementation_run_to_record,
)
from backend.services.api.project_knowledge.persistence.mappers import common, run
from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationRunRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    ImplementationRunStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.domain.models import ImplementationRun


UTC = timezone.utc
OFFSET = timezone(timedelta(hours=8))
BASE_COMMIT = "a" * 40
RESULT_COMMIT = "b" * 40
HASHES = {
    "manifest_hash": "1" * 64,
    "report_hash": "2" * 64,
    "source_bundle_hash": "3" * 64,
    "git_diff_hash": "4" * 64,
}
BUSINESS_FIELDS = (
    "implementation_run_id",
    "task_id",
    "repository_root",
    "branch",
    "base_commit",
    "result_commit",
    "task_status",
    "completion_level",
    "verification_level",
    "workspace_dirty_before",
    "workspace_dirty_after",
    "started_at",
    "completed_at",
    "agent_type",
    "manifest_schema_version",
    "manifest_path",
    "manifest_hash",
    "report_path",
    "report_hash",
    "source_bundle_hash",
    "git_diff_hash",
    "consistency_status",
    "canonical_status",
)


def make_run(**overrides) -> ImplementationRun:
    values = {
        "implementation_run_id": "QM2-P0-RUN-TEST",
        "task_id": "QM2-P0-TASK-TEST",
        "repository_root": "quantmind-main",
        "branch": "master",
        "base_commit": BASE_COMMIT,
        "result_commit": None,
        "task_status": ImplementationRunStatus.RUNNING,
        "completion_level": CompletionLevel.NONE,
        "verification_level": VerificationLevel.NOT_VERIFIED,
        "workspace_dirty_before": False,
        "workspace_dirty_after": True,
        "started_at": datetime(2026, 7, 15, 8, 1, 2, 345678, tzinfo=UTC),
        "completed_at": None,
        "agent_type": "codex",
        "manifest_schema_version": "1.0.0",
        "manifest_path": "docs/runs/manifest.json",
        "manifest_hash": None,
        "report_path": "docs/runs/report.md",
        "report_hash": None,
        "source_bundle_hash": None,
        "git_diff_hash": None,
        "consistency_status": ConsistencyStatus.UNVERIFIED,
        "canonical_status": CanonicalStatus.NONCANONICAL,
    }
    values.update(overrides)
    return ImplementationRun(**values)


def make_record(**overrides) -> ImplementationRunRecord:
    values = {
        "implementation_run_id": "QM2-P0-RUN-TEST",
        "task_id": "QM2-P0-TASK-TEST",
        "repository_root": "quantmind-main",
        "branch": "master",
        "base_commit": BASE_COMMIT,
        "result_commit": None,
        "task_status": "running",
        "completion_level": "none",
        "verification_level": "not_verified",
        "workspace_dirty_before": False,
        "workspace_dirty_after": True,
        "started_at": datetime(2026, 7, 15, 8, 1, 2, 345678, tzinfo=UTC),
        "completed_at": None,
        "agent_type": "codex",
        "manifest_schema_version": "1.0.0",
        "manifest_path": "docs/runs/manifest.json",
        "manifest_hash": None,
        "report_path": "docs/runs/report.md",
        "report_hash": None,
        "source_bundle_hash": None,
        "git_diff_hash": None,
        "consistency_status": "unverified",
        "canonical_status": "noncanonical",
        "version": 1,
    }
    values.update(overrides)
    return ImplementationRunRecord(**values)


def terminal_values(
    status: ImplementationRunStatus,
    completion: CompletionLevel,
    *,
    committed: bool = False,
    canonical: bool = False,
) -> dict[str, object]:
    return {
        "task_status": status,
        "completion_level": completion,
        "result_commit": RESULT_COMMIT if committed else None,
        "completed_at": datetime(2026, 7, 15, 8, 11, 12, 987654, tzinfo=UTC),
        "verification_level": VerificationLevel.TARGETED_TESTS,
        "workspace_dirty_after": not committed,
        "consistency_status": (
            ConsistencyStatus.CONSISTENT if canonical else ConsistencyStatus.UNVERIFIED
        ),
        "canonical_status": (
            CanonicalStatus.CANONICAL if canonical else CanonicalStatus.NONCANONICAL
        ),
    }


class ImplementationRunDomainToRecordTests(unittest.TestCase):
    def test_maps_all_business_fields_and_initial_version(self):
        domain = make_run(
            started_at=datetime(2026, 7, 15, 16, 1, 2, 345678, tzinfo=OFFSET),
            **HASHES,
        )
        record = implementation_run_to_record(domain)
        self.assertIsInstance(record, ImplementationRunRecord)
        for field in BUSINESS_FIELDS:
            self.assertEqual(getattr(record, field), getattr(domain, field), field)
        self.assertEqual(record.version, 1)
        self.assertIs(record.started_at.tzinfo, UTC)
        self.assertEqual(record.started_at.microsecond, 345678)

    def test_all_supported_state_shapes_map(self):
        cases = (
            make_run(),
            make_run(**terminal_values(
                ImplementationRunStatus.COMPLETED_UNCOMMITTED,
                CompletionLevel.COMPLETE,
            )),
            make_run(**terminal_values(
                ImplementationRunStatus.COMPLETED_COMMITTED,
                CompletionLevel.COMPLETE,
                committed=True,
            )),
            make_run(**terminal_values(
                ImplementationRunStatus.COMPLETED_COMMITTED,
                CompletionLevel.COMPLETE,
                committed=True,
                canonical=True,
            )),
            make_run(**terminal_values(
                ImplementationRunStatus.PARTIAL_COMMITTED,
                CompletionLevel.PARTIAL,
                committed=True,
            )),
            make_run(**terminal_values(ImplementationRunStatus.FAILED, CompletionLevel.NONE)),
            make_run(**terminal_values(ImplementationRunStatus.BLOCKED, CompletionLevel.PARTIAL)),
            make_run(**terminal_values(ImplementationRunStatus.CANCELLED, CompletionLevel.NONE)),
        )
        for domain in cases:
            with self.subTest(status=domain.task_status, canonical=domain.canonical_status):
                record = implementation_run_to_record(domain)
                self.assertEqual(record.task_status, domain.task_status.value)
                self.assertEqual(record.completion_level, domain.completion_level.value)
                self.assertEqual(record.verification_level, domain.verification_level.value)
                self.assertEqual(record.consistency_status, domain.consistency_status.value)
                self.assertEqual(record.canonical_status, domain.canonical_status.value)

    def test_nullable_commits_hashes_and_completed_time_remain_none(self):
        record = implementation_run_to_record(make_run())
        for field in (
            "result_commit",
            "completed_at",
            "manifest_hash",
            "report_hash",
            "source_bundle_hash",
            "git_diff_hash",
        ):
            self.assertIsNone(getattr(record, field), field)

    def test_returns_new_records_without_mutating_domain(self):
        domain = make_run(**HASHES)
        before = domain
        first = implementation_run_to_record(domain)
        second = implementation_run_to_record(domain)
        self.assertIsNot(first, second)
        self.assertEqual(domain, before)

    def test_rejects_non_run_input(self):
        class Duck:
            implementation_run_id = "QM2-P0-RUN-TEST"

        for value in ({"implementation_run_id": "QM2-P0-RUN-TEST"}, Duck(), None):
            with self.subTest(value=value):
                with self.assertRaises(DomainToRecordError) as captured:
                    implementation_run_to_record(value)
                self.assertEqual(captured.exception.error_code, "INVALID_OBJECT_TYPE")


class ImplementationRunRecordToDomainTests(unittest.TestCase):
    def test_maps_all_fields_and_rebuilds_five_enums(self):
        values = terminal_values(
            ImplementationRunStatus.COMPLETED_COMMITTED,
            CompletionLevel.COMPLETE,
            committed=True,
            canonical=True,
        )
        record_values = {
            key: value.value if hasattr(value, "value") else value
            for key, value in values.items()
        }
        record = make_record(version=8, **record_values, **HASHES)
        domain = implementation_run_from_record(record)
        self.assertIs(domain.task_status, ImplementationRunStatus.COMPLETED_COMMITTED)
        self.assertIs(domain.completion_level, CompletionLevel.COMPLETE)
        self.assertIs(domain.verification_level, VerificationLevel.TARGETED_TESTS)
        self.assertIs(domain.consistency_status, ConsistencyStatus.CONSISTENT)
        self.assertIs(domain.canonical_status, CanonicalStatus.CANONICAL)
        self.assertFalse(hasattr(domain, "version"))
        for field in HASHES:
            self.assertEqual(getattr(domain, field), HASHES[field])

    def test_offset_times_normalize_to_utc_and_none_is_preserved(self):
        source = datetime(2026, 7, 15, 16, 1, 2, 345678, tzinfo=OFFSET)
        running = implementation_run_from_record(make_record(started_at=source))
        self.assertEqual(
            running.started_at,
            datetime(2026, 7, 15, 8, 1, 2, 345678, tzinfo=UTC),
        )
        self.assertIsNone(running.completed_at)

        terminal = implementation_run_from_record(
            make_record(
                task_status="failed",
                completion_level="partial",
                started_at=source,
                completed_at=datetime(
                    2026, 7, 15, 16, 2, 3, 456789, tzinfo=OFFSET
                ),
            )
        )
        self.assertIs(terminal.completed_at.tzinfo, UTC)
        self.assertEqual(terminal.completed_at.microsecond, 456789)

    def test_invalid_versions_fail(self):
        for value in (0, -1, True, 1.5, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_run_from_record(make_record(version=value))
                self.assertEqual(captured.exception.error_code, "INVALID_VERSION")

    def test_unknown_enum_values_fail_exactly(self):
        for field in (
            "task_status",
            "completion_level",
            "verification_level",
            "consistency_status",
            "canonical_status",
        ):
            for value in ("UNKNOWN", " running ", None, 1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(RecordToDomainError) as captured:
                        implementation_run_from_record(make_record(**{field: value}))
                    self.assertEqual(captured.exception.error_code, "UNKNOWN_ENUM")
                    self.assertEqual(captured.exception.field_name, field)

    def test_naive_started_and_completed_times_fail(self):
        with self.assertRaises(RecordToDomainError) as started:
            implementation_run_from_record(
                make_record(started_at=datetime(2026, 7, 15, 8, 1, 2))
            )
        self.assertEqual(started.exception.error_code, "INVALID_TIME")
        with self.assertRaises(RecordToDomainError) as completed:
            implementation_run_from_record(
                make_record(
                    task_status="failed",
                    completed_at=datetime(2026, 7, 15, 8, 2, 3),
                )
            )
        self.assertEqual(completed.exception.error_code, "INVALID_TIME")

    def test_domain_state_combinations_and_value_validation_are_safely_wrapped(self):
        cases = (
            ({
                "task_status": "completed_committed",
                "completion_level": "complete",
                "completed_at": datetime(2026, 7, 15, 8, 2, tzinfo=UTC),
                "result_commit": None,
            }, "INVALID_STATE_COMBINATION", "result_commit"),
            ({"completed_at": datetime(2026, 7, 15, 8, 2, tzinfo=UTC)},
             "INVALID_STATE_COMBINATION", "completed_at"),
            ({"task_status": "failed", "completed_at": None},
             "INVALID_STATE_COMBINATION", "completed_at"),
            ({"canonical_status": "canonical"},
             "FORBIDDEN_CANONICAL_STATE", "canonical_status"),
            ({"manifest_hash": "z" * 64}, "INVALID_HASH", "manifest_hash"),
            ({"base_commit": "a" * 39}, "INVALID_GIT_COMMIT", "base_commit"),
            ({"manifest_path": "/tmp/manifest.json"},
             "INVALID_REPOSITORY_PATH", "manifest_path"),
            ({"repository_root": "/tmp/private/repository"},
             "INVALID_IDENTIFIER", "repository_root"),
        )
        for overrides, code, field in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_run_from_record(make_record(**overrides))
                self.assertEqual(captured.exception.error_code, code)
                self.assertEqual(captured.exception.field_name, field)
                self.assertNotIn("/tmp/private/repository", str(captured.exception))
                self.assertNotIn("ImplementationRunRecord(", str(captured.exception))

    def test_every_required_column_must_already_be_loaded(self):
        for field in BUSINESS_FIELDS + ("version",):
            record = make_record()
            del vars(record)[field]
            with self.subTest(field=field):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_run_from_record(record)
                self.assertEqual(captured.exception.error_code, "MISSING_REQUIRED_VALUE")
                self.assertEqual(captured.exception.field_name, field)

    def test_non_record_input_fails(self):
        for value in ({"implementation_run_id": "QM2-P0-RUN-TEST"}, make_run(), None):
            with self.subTest(value=value):
                with self.assertRaises(RecordToDomainError) as captured:
                    implementation_run_from_record(value)
                self.assertEqual(captured.exception.error_code, "INVALID_OBJECT_TYPE")

    def test_error_identity_is_safe_and_rejected_values_are_not_disclosed(self):
        record = make_record(
            implementation_run_id="password:secret",
            repository_root="/Users/private/very-long-repository",
        )
        with self.assertRaises(RecordToDomainError) as captured:
            implementation_run_from_record(record)
        rendered = str(captured.exception)
        self.assertNotIn("password:secret", rendered)
        self.assertNotIn("/Users/private/very-long-repository", rendered)


class ImplementationRunRoundTripTests(unittest.TestCase):
    def test_domain_round_trips_across_primary_states(self):
        cases = (
            make_run(),
            make_run(
                started_at=datetime(2026, 7, 15, 16, 1, 2, 345678, tzinfo=OFFSET),
            ),
            make_run(**terminal_values(
                ImplementationRunStatus.COMPLETED_UNCOMMITTED,
                CompletionLevel.COMPLETE,
            )),
            make_run(**terminal_values(
                ImplementationRunStatus.COMPLETED_COMMITTED,
                CompletionLevel.COMPLETE,
                committed=True,
                canonical=True,
            ), **HASHES),
            make_run(**terminal_values(ImplementationRunStatus.FAILED, CompletionLevel.NONE)),
        )
        for domain in cases:
            with self.subTest(status=domain.task_status, canonical=domain.canonical_status):
                rebuilt = implementation_run_from_record(
                    implementation_run_to_record(domain)
                )
                self.assertEqual(rebuilt, domain)
                self.assertEqual(rebuilt.repository_root, "quantmind-main")

    def test_record_business_values_round_trip_and_version_resets(self):
        original = make_record(version=9)
        rebuilt = implementation_run_to_record(
            implementation_run_from_record(original)
        )
        for field in BUSINESS_FIELDS:
            self.assertEqual(getattr(rebuilt, field), getattr(original, field), field)
        self.assertEqual(rebuilt.version, 1)


class ImplementationRunMapperScopeAndPurityTests(unittest.TestCase):
    def test_exact_complete_mapper_package_and_runtime_boundary(self):
        root = Path(common.__file__).resolve().parent
        self.assertEqual(
            {path.name for path in root.glob("*.py")},
            {
                "__init__.py", "errors.py", "common.py", "task.py", "run.py",
                "identity.py", "relationship.py", "details.py", "references.py",
                "annotations.py",
            },
        )
        source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
        self.assertIn("implementation_run_to_record", source)
        self.assertIn("implementation_run_from_record", source)
        for marker in (
            "run_from_manifest",
            "manifest_to_run",
            "resolve_repository_identity",
            "execution_path_to_repository_id",
        ):
            self.assertNotIn(marker, source)

    def test_run_mapper_imports_no_relationship_record(self):
        self.assertNotIn("RunRelationshipRecord", inspect.getsource(run))

    def test_mapper_source_has_no_io_git_network_environment_or_database_behavior(self):
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
            "exists",
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
        tree = ast.parse(inspect.getsource(run))
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
        self.assertTrue(forbidden_imports.isdisjoint(imports))
        calls = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertTrue(forbidden_calls.isdisjoint(calls))


if __name__ == "__main__":
    unittest.main()
