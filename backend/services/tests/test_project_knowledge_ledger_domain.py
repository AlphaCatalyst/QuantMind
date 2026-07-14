from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.services.engine.project_knowledge.domain import (
    ADRReferenceRelation,
    ArchitectureDecisionReference,
    CanonicalStatus,
    ChangedFile,
    ChangedSymbol,
    CompletionLevel,
    ComponentReference,
    ConsistencyStatus,
    FileChangeType,
    ForbiddenCanonicalStateError,
    ImpactType,
    ImplementationArtifact,
    ImplementationRun,
    ImplementationRunStatus,
    ImplementationTask,
    ImplementationTaskStatus,
    InvalidGitCommitError,
    InvalidHashError,
    InvalidIdentifierError,
    InvalidRepositoryPathError,
    InvalidRunRelationshipError,
    InvalidStateCombinationError,
    InvalidTestExecutionError,
    InvalidTimeRangeError,
    LedgerDomainError,
    Limitation,
    LimitationSeverity,
    LimitationStatus,
    RecommendationPriority,
    RecommendedTask,
    RunRelationship,
    RunRelationshipType,
    SecretLikeValueRejectedError,
    SymbolChangeType,
    SymbolType,
    TestExecution,
    TestExecutionStatus,
    VerificationLevel,
    has_direct_reverse_conflict,
    relationship_semantics,
    validate_direct_relationship,
)
from backend.services.engine.project_knowledge.domain.validators import (
    validate_aware_datetime,
    validate_full_git_commit,
    validate_identifier,
    validate_optional_sha256,
    validate_repository_path,
    validate_sha256,
    validate_short_git_commit,
    validate_uri,
)
from tools.quantmind2.validate_context_bootstrap import validate_bootstrap


UTC_NOW = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)
FULL_COMMIT = "a" * 40
RESULT_COMMIT = "b" * 40
HASH_A = "1" * 64
HASH_B = "2" * 64
RUN_ID = "QM2-P0-002A1b1-20260714T150000Z-6ec76c0"
ROOT = Path(__file__).resolve().parents[3]
DOMAIN = ROOT / "backend/services/engine/project_knowledge/domain"


def make_run(**overrides) -> ImplementationRun:
    values = {
        "implementation_run_id": RUN_ID,
        "task_id": "QM2-P0-002A1b1",
        "repository_root": "quantmind",
        "branch": "master",
        "base_commit": FULL_COMMIT,
        "result_commit": None,
        "task_status": ImplementationRunStatus.RUNNING,
        "completion_level": CompletionLevel.NONE,
        "verification_level": VerificationLevel.NOT_VERIFIED,
        "workspace_dirty_before": False,
        "workspace_dirty_after": True,
        "started_at": UTC_NOW,
        "completed_at": None,
        "agent_type": "codex",
        "manifest_schema_version": "1.0.0",
        "manifest_path": "docs/quantmind2/run/manifest.json",
        "manifest_hash": None,
        "report_path": "docs/quantmind2/run/report.md",
        "report_hash": None,
        "source_bundle_hash": None,
        "git_diff_hash": None,
        "consistency_status": ConsistencyStatus.UNVERIFIED,
        "canonical_status": CanonicalStatus.NONCANONICAL,
    }
    values.update(overrides)
    return ImplementationRun(**values)


def make_relationship(**overrides) -> RunRelationship:
    values = {
        "relationship_id": "relationship-1",
        "source_run_id": "run-new",
        "target_run_id": "run-old",
        "relationship_type": RunRelationshipType.FINALIZES,
        "reason": "Final verification was recorded.",
        "created_at": UTC_NOW,
    }
    values.update(overrides)
    return RunRelationship(**values)


class LedgerEnumAndValueTests(unittest.TestCase):
    def test_all_enum_values_are_stable(self):
        expected = {
            ImplementationTaskStatus: {"planned", "ready", "running", "completed", "partial", "blocked", "cancelled"},
            ImplementationRunStatus: {"running", "completed_uncommitted", "partial_uncommitted", "completed_committed", "partial_committed", "failed", "blocked", "cancelled"},
            CompletionLevel: {"none", "partial", "complete"},
            VerificationLevel: {"not_verified", "static_checks", "targeted_tests", "integration_tests", "full_relevant_tests"},
            ConsistencyStatus: {"unverified", "consistent", "warning", "error", "stale"},
            CanonicalStatus: {"noncanonical", "candidate", "canonical", "rejected"},
            RunRelationshipType: {"finalizes", "corrects", "supersedes", "depends_on", "retries", "continues"},
            TestExecutionStatus: {"passed", "failed", "skipped", "not_run"},
            FileChangeType: {"added", "modified", "deleted", "renamed", "unchanged"},
            SymbolChangeType: {"added", "modified", "deleted", "renamed"},
            SymbolType: {"module", "class", "function", "method", "constant", "schema", "table", "endpoint", "document", "unknown"},
            ImpactType: {"introduced", "modified", "deprecated", "removed", "verified", "documented", "unaffected"},
            ADRReferenceRelation: {"implements", "conforms_to", "documents", "supersedes", "affected_by"},
            LimitationSeverity: {"info", "low", "medium", "high", "critical"},
            LimitationStatus: {"open", "accepted", "resolved", "superseded"},
            RecommendationPriority: {"P0", "P1", "P2"},
        }
        for enum_type, values in expected.items():
            self.assertEqual({item.value for item in enum_type}, values)

    def test_valid_identifier_supports_nested_task_suffix(self):
        self.assertEqual(validate_identifier("QM2-P0-002A1b1"), "QM2-P0-002A1b1")

    def test_empty_identifier_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            validate_identifier("  ")

    def test_identifier_with_path_separator_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            validate_identifier("task/../../shell")

    def test_valid_sha256(self):
        self.assertEqual(validate_sha256("A" * 64), "a" * 64)

    def test_invalid_hash_fails(self):
        with self.assertRaises(InvalidHashError):
            validate_sha256("abc")

    def test_empty_optional_hash_fails(self):
        with self.assertRaises(InvalidHashError):
            validate_optional_sha256("")

    def test_valid_full_git_commit(self):
        self.assertEqual(validate_full_git_commit("A" * 40), "a" * 40)

    def test_valid_short_git_commit_in_explicit_field(self):
        self.assertEqual(validate_short_git_commit("6ec76c0"), "6ec76c0")

    def test_invalid_commit_fails(self):
        with self.assertRaises(InvalidGitCommitError):
            validate_full_git_commit("6ec76c0")

    def test_valid_repository_relative_path(self):
        value = "docs/quantmind2/context/CURRENT_STATE.md"
        self.assertEqual(validate_repository_path(value), value)

    def test_absolute_path_fails(self):
        with self.assertRaises(InvalidRepositoryPathError):
            validate_repository_path("/tmp/manifest.json")

    def test_parent_traversal_fails(self):
        with self.assertRaises(InvalidRepositoryPathError):
            validate_repository_path("docs/../secret")

    def test_naive_datetime_fails(self):
        with self.assertRaises(InvalidTimeRangeError):
            validate_aware_datetime(datetime(2026, 7, 14))

    def test_aware_datetime_is_normalized_to_utc(self):
        offset = timezone(timedelta(hours=8))
        value = validate_aware_datetime(datetime(2026, 7, 14, 23, tzinfo=offset))
        self.assertEqual(value, datetime(2026, 7, 14, 15, tzinfo=timezone.utc))

    def test_uri_validation_is_structural_only(self):
        self.assertEqual(validate_uri("artifact://ledger/run-1"), "artifact://ledger/run-1")


class ImplementationTaskTests(unittest.TestCase):
    def test_valid_task_is_frozen_and_uses_tuples(self):
        task = ImplementationTask(
            task_id="QM2-P0-002A1b1",
            parent_task_id="QM2-P0-002A1b",
            title="Domain model",
            objective="Define immutable objects.",
            scope=["Models", "Validators"],
            explicit_non_goals=["No repository"],
            status=ImplementationTaskStatus.RUNNING,
            created_at=UTC_NOW,
        )
        self.assertEqual(task.scope, ("Models", "Validators"))
        with self.assertRaises(FrozenInstanceError):
            task.title = "changed"  # type: ignore[misc]

    def test_parent_equal_to_self_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            ImplementationTask("task-1", "task-1", "Title", "Objective", (), (), ImplementationTaskStatus.PLANNED, UTC_NOW)

    def test_empty_title_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            ImplementationTask("task-1", None, "", "Objective", (), (), ImplementationTaskStatus.PLANNED, UTC_NOW)

    def test_empty_objective_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            ImplementationTask("task-1", None, "Title", " ", (), (), ImplementationTaskStatus.PLANNED, UTC_NOW)


class ImplementationRunTests(unittest.TestCase):
    def test_valid_running_run(self):
        run = make_run()
        self.assertEqual(run.task_status, ImplementationRunStatus.RUNNING)
        self.assertIsNone(run.completed_at)

    def test_valid_completed_uncommitted_run(self):
        run = make_run(
            task_status=ImplementationRunStatus.COMPLETED_UNCOMMITTED,
            completion_level=CompletionLevel.COMPLETE,
            completed_at=UTC_NOW + timedelta(minutes=1),
        )
        self.assertIsNone(run.result_commit)

    def test_valid_completed_committed_is_not_automatically_canonical(self):
        run = make_run(
            task_status=ImplementationRunStatus.COMPLETED_COMMITTED,
            completion_level=CompletionLevel.COMPLETE,
            result_commit=RESULT_COMMIT,
            completed_at=UTC_NOW + timedelta(minutes=1),
        )
        self.assertEqual(run.canonical_status, CanonicalStatus.NONCANONICAL)

    def test_valid_canonical_run(self):
        run = make_run(
            task_status=ImplementationRunStatus.COMPLETED_COMMITTED,
            completion_level=CompletionLevel.COMPLETE,
            result_commit=RESULT_COMMIT,
            completed_at=UTC_NOW + timedelta(minutes=1),
            consistency_status=ConsistencyStatus.CONSISTENT,
            canonical_status=CanonicalStatus.CANONICAL,
        )
        self.assertEqual(run.canonical_status, CanonicalStatus.CANONICAL)

    def test_committed_without_result_commit_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            make_run(task_status=ImplementationRunStatus.COMPLETED_COMMITTED, completion_level=CompletionLevel.COMPLETE, completed_at=UTC_NOW)

    def test_running_with_completed_at_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            make_run(completed_at=UTC_NOW)

    def test_terminal_without_completed_at_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            make_run(task_status=ImplementationRunStatus.FAILED)

    def test_uncommitted_canonical_fails(self):
        with self.assertRaises(ForbiddenCanonicalStateError):
            make_run(task_status=ImplementationRunStatus.COMPLETED_UNCOMMITTED, completion_level=CompletionLevel.COMPLETE, completed_at=UTC_NOW, canonical_status=CanonicalStatus.CANONICAL)

    def test_failed_canonical_fails(self):
        with self.assertRaises(ForbiddenCanonicalStateError):
            make_run(task_status=ImplementationRunStatus.FAILED, completed_at=UTC_NOW, canonical_status=CanonicalStatus.CANONICAL)

    def test_dirty_uncommitted_canonical_fails(self):
        with self.assertRaises(ForbiddenCanonicalStateError):
            make_run(task_status=ImplementationRunStatus.PARTIAL_UNCOMMITTED, completion_level=CompletionLevel.PARTIAL, completed_at=UTC_NOW, workspace_dirty_after=True, canonical_status=CanonicalStatus.CANONICAL)

    def test_canonical_inconsistent_fails(self):
        with self.assertRaises(ForbiddenCanonicalStateError):
            make_run(task_status=ImplementationRunStatus.COMPLETED_COMMITTED, completion_level=CompletionLevel.COMPLETE, result_commit=RESULT_COMMIT, completed_at=UTC_NOW, consistency_status=ConsistencyStatus.WARNING, canonical_status=CanonicalStatus.CANONICAL)

    def test_canonical_incomplete_fails(self):
        with self.assertRaises(LedgerDomainError):
            make_run(task_status=ImplementationRunStatus.PARTIAL_COMMITTED, completion_level=CompletionLevel.PARTIAL, result_commit=RESULT_COMMIT, completed_at=UTC_NOW, consistency_status=ConsistencyStatus.CONSISTENT, canonical_status=CanonicalStatus.CANONICAL)

    def test_start_after_completion_fails(self):
        with self.assertRaises(InvalidTimeRangeError):
            make_run(completed_at=UTC_NOW - timedelta(seconds=1), task_status=ImplementationRunStatus.FAILED)

    def test_unsafe_report_path_fails(self):
        with self.assertRaises(InvalidRepositoryPathError):
            make_run(report_path="../report.md")

    def test_invalid_report_hash_fails(self):
        with self.assertRaises(InvalidHashError):
            make_run(report_hash="bad")

    def test_uncommitted_with_result_commit_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            make_run(task_status=ImplementationRunStatus.COMPLETED_UNCOMMITTED, completion_level=CompletionLevel.COMPLETE, completed_at=UTC_NOW, result_commit=RESULT_COMMIT)


class RelationshipTests(unittest.TestCase):
    def test_valid_finalizes(self):
        self.assertEqual(make_relationship().relationship_type, RunRelationshipType.FINALIZES)

    def test_valid_corrects(self):
        relation = make_relationship(relationship_type=RunRelationshipType.CORRECTS)
        self.assertEqual(relation.relationship_type, RunRelationshipType.CORRECTS)

    def test_self_relationship_fails(self):
        with self.assertRaises(InvalidRunRelationshipError):
            make_relationship(source_run_id="same", target_run_id="same")

    def test_empty_reason_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            make_relationship(reason="")

    def test_direct_reverse_conflict_is_detected(self):
        first = make_relationship(source_run_id="run-a", target_run_id="run-b")
        reverse = make_relationship(relationship_id="relationship-2", source_run_id="run-b", target_run_id="run-a")
        self.assertTrue(has_direct_reverse_conflict(reverse, first))
        with self.assertRaises(InvalidRunRelationshipError):
            validate_direct_relationship(reverse, [first])

    def test_finalizes_and_corrects_have_distinct_semantics(self):
        self.assertNotEqual(
            relationship_semantics(RunRelationshipType.FINALIZES),
            relationship_semantics(RunRelationshipType.CORRECTS),
        )


class ChangedRecordTests(unittest.TestCase):
    def test_valid_added_file(self):
        value = ChangedFile(RUN_ID, "new.py", FileChangeType.ADDED, after_hash=HASH_A)
        self.assertIsNone(value.before_hash)

    def test_valid_deleted_file(self):
        value = ChangedFile(RUN_ID, "old.py", FileChangeType.DELETED, before_hash=HASH_A)
        self.assertIsNone(value.after_hash)

    def test_valid_modified_file(self):
        value = ChangedFile(RUN_ID, "changed.py", FileChangeType.MODIFIED, HASH_A, HASH_B)
        self.assertNotEqual(value.before_hash, value.after_hash)

    def test_renamed_without_previous_path_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            ChangedFile(RUN_ID, "new.py", FileChangeType.RENAMED)

    def test_renamed_with_same_path_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            ChangedFile(RUN_ID, "same.py", FileChangeType.RENAMED, previous_path="same.py")

    def test_changed_file_unsafe_path_fails(self):
        with self.assertRaises(InvalidRepositoryPathError):
            ChangedFile(RUN_ID, "/abs.py", FileChangeType.ADDED, after_hash=HASH_A)

    def test_valid_changed_symbol(self):
        value = ChangedSymbol(RUN_ID, "domain/models.py", "ImplementationRun.__post_init__", SymbolType.METHOD, SymbolChangeType.ADDED)
        self.assertEqual(value.symbol_type, SymbolType.METHOD)

    def test_empty_qualified_name_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            ChangedSymbol(RUN_ID, "domain/models.py", "", SymbolType.CLASS, SymbolChangeType.ADDED)

    def test_unchanged_file_requires_equal_hashes(self):
        value = ChangedFile(RUN_ID, "verified.py", FileChangeType.UNCHANGED, HASH_A, HASH_A)
        self.assertEqual(value.before_hash, value.after_hash)


class TestExecutionTests(unittest.TestCase):
    def make_execution(self, **overrides) -> TestExecution:
        values = {
            "test_execution_id": "test-1",
            "implementation_run_id": RUN_ID,
            "command": "python3 -m unittest tests.test_domain",
            "purpose": "Verify domain invariants.",
            "status": TestExecutionStatus.PASSED,
            "passed_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
        }
        values.update(overrides)
        return TestExecution(**values)

    def test_passed_with_zero_failures(self):
        self.assertEqual(self.make_execution().status, TestExecutionStatus.PASSED)

    def test_passed_with_failures_fails(self):
        with self.assertRaises(InvalidTestExecutionError):
            self.make_execution(failed_count=1)

    def test_failed_with_zero_failures_fails(self):
        with self.assertRaises(InvalidTestExecutionError):
            self.make_execution(status=TestExecutionStatus.FAILED, failed_count=0)

    def test_not_run_without_reason_fails(self):
        with self.assertRaises(InvalidTestExecutionError):
            self.make_execution(status=TestExecutionStatus.NOT_RUN, passed_count=0)

    def test_executed_with_not_run_reason_fails(self):
        with self.assertRaises(InvalidTestExecutionError):
            self.make_execution(not_run_reason="Not needed")

    def test_negative_count_fails(self):
        with self.assertRaises(LedgerDomainError):
            self.make_execution(skipped_count=-1)

    def test_obvious_secret_in_command_fails(self):
        with self.assertRaises(SecretLikeValueRejectedError):
            self.make_execution(command="client --password=visible-value")

    def test_valid_not_run(self):
        value = self.make_execution(status=TestExecutionStatus.NOT_RUN, passed_count=0, not_run_reason="External service unavailable")
        self.assertEqual(value.not_run_reason, "External service unavailable")


class ArtifactAndReferenceTests(unittest.TestCase):
    def test_valid_artifact(self):
        value = ImplementationArtifact("artifact-1", RUN_ID, "report", "docs/report.md", HASH_A, "1.0.0", 10)
        self.assertEqual(value.content_hash, HASH_A)

    def test_artifact_without_path_or_uri_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            ImplementationArtifact("artifact-1", RUN_ID, "report", "", None, None, None)

    def test_artifact_negative_size_fails(self):
        with self.assertRaises(LedgerDomainError):
            ImplementationArtifact("artifact-1", RUN_ID, "report", "docs/report.md", None, None, -1)

    def test_valid_component_reference(self):
        value = ComponentReference(RUN_ID, "quantmind2.project_knowledge", ImpactType.INTRODUCED)
        self.assertEqual(value.impact_type, ImpactType.INTRODUCED)

    def test_valid_adr_reference(self):
        value = ArchitectureDecisionReference(RUN_ID, "ADR-0009", ADRReferenceRelation.CONFORMS_TO)
        self.assertEqual(value.adr_id, "ADR-0009")

    def test_valid_limitation(self):
        value = Limitation("limitation-1", RUN_ID, LimitationSeverity.MEDIUM, "quantmind2.project_knowledge", "Repository is not implemented.", LimitationStatus.OPEN)
        self.assertEqual(value.status, LimitationStatus.OPEN)

    def test_empty_limitation_description_fails(self):
        with self.assertRaises(InvalidIdentifierError):
            Limitation("limitation-1", RUN_ID, LimitationSeverity.MEDIUM, None, "", LimitationStatus.OPEN)

    def test_secret_like_limitation_description_fails(self):
        with self.assertRaises(SecretLikeValueRejectedError):
            Limitation("limitation-1", RUN_ID, LimitationSeverity.HIGH, None, "token=visible-value", LimitationStatus.OPEN)

    def test_valid_recommended_task(self):
        value = RecommendedTask("recommendation-1", RUN_ID, "QM2-P0-002A1b2", RecommendationPriority.P0, "Define the Repository contract separately.")
        self.assertEqual(value.priority, RecommendationPriority.P0)

    def test_invalid_priority_fails(self):
        with self.assertRaises(InvalidStateCombinationError):
            RecommendedTask("recommendation-1", RUN_ID, "QM2-P0-002A1b2", "urgent", "Reason")  # type: ignore[arg-type]


class DomainScopeRegressionTests(unittest.TestCase):
    def test_domain_package_has_no_sqlalchemy_import(self):
        self._assert_no_import_prefix("sqlalchemy")

    def test_domain_package_has_no_fastapi_import(self):
        self._assert_no_import_prefix("fastapi")

    def test_domain_package_has_no_database_calls(self):
        forbidden_calls = {"create_engine", "create_async_engine", "get_session", "get_db", "connect", "execute", "commit", "rollback"}
        for path in DOMAIN.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertFalse(calls & forbidden_calls, f"{path}: {calls & forbidden_calls}")

    def test_repository_contract_remains_persistence_agnostic(self):
        repository_contract = DOMAIN / "repositories.py"
        self.assertTrue(repository_contract.is_file())
        text = repository_contract.read_text(encoding="utf-8")
        self.assertIn("Protocol", text)
        self.assertNotIn("sqlalchemy", text.lower())
        self.assertNotIn("AsyncSession", text)

    def test_no_ledger_migration_exists(self):
        self.assertFalse(list((ROOT / "data/migrations").glob("*ledger*")))
        self.assertFalse(list((ROOT / "data/migrations").glob("*project_knowledge*")))

    def test_no_api_endpoint_exists_in_domain(self):
        for path in DOMAIN.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("APIRouter", text)
            self.assertNotIn("@app.", text)
            self.assertNotIn("@router.", text)

    def test_context_bootstrap_validator_passes(self):
        checks = validate_bootstrap()
        self.assertIn("implementation_runs", checks)

    def _assert_no_import_prefix(self, prefix: str) -> None:
        for path in DOMAIN.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                self.assertFalse(any(module == prefix or module.startswith(prefix + ".") for module in modules), f"{path}: {modules}")


if __name__ == "__main__":
    unittest.main()
