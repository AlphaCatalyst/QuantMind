"""Contract tests for the pure in-memory Implementation Ledger repository."""

from __future__ import annotations

import ast
import unittest
from dataclasses import replace
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
    DuplicateChildEntityError,
    FileChangeType,
    HistoryQuery,
    ImmutableEntityConflictError,
    ImpactType,
    ImplementationArtifact,
    ImplementationRun,
    ImplementationRunStatus,
    ImplementationTask,
    ImplementationTaskStatus,
    InvalidStateTransitionError,
    Limitation,
    LimitationSeverity,
    LimitationStatus,
    OptimisticConcurrencyError,
    RecommendationPriority,
    RecommendedTask,
    RepositoryQueryError,
    RunNotFoundError,
    RunQuery,
    RunRelationship,
    RunRelationshipCycleError,
    RunRelationshipType,
    SortOrder,
    SymbolChangeType,
    SymbolType,
    TaskNotFoundError,
    TaskQuery,
    TestExecution,
    TestExecutionStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.testing import InMemoryLedgerRepository


BASE = "a" * 40
RESULT = "b" * 40
HASH_A = "1" * 64
HASH_B = "2" * 64
NOW = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)
DOMAIN_ROOT = Path(__file__).resolve().parents[1] / "engine" / "project_knowledge" / "domain"
TESTING_ROOT = Path(__file__).resolve().parents[1] / "engine" / "project_knowledge" / "testing"
REPO_ROOT = Path(__file__).resolve().parents[3]


def make_task(
    task_id: str = "QM2-P0-002A1b2",
    *,
    status: ImplementationTaskStatus = ImplementationTaskStatus.PLANNED,
    created_at: datetime = NOW,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id,
        parent_task_id="QM2-P0-002A1",
        title=f"Task {task_id}",
        objective="Verify repository semantics.",
        scope=("Repository contract",),
        explicit_non_goals=("No database",),
        status=status,
        created_at=created_at,
    )


def make_run(
    run_id: str = "run-1",
    *,
    task_id: str = "QM2-P0-002A1b2",
    started_at: datetime = NOW,
    status: ImplementationRunStatus = ImplementationRunStatus.RUNNING,
    consistency: ConsistencyStatus = ConsistencyStatus.UNVERIFIED,
    canonical: CanonicalStatus = CanonicalStatus.NONCANONICAL,
) -> ImplementationRun:
    committed = status in {
        ImplementationRunStatus.COMPLETED_COMMITTED,
        ImplementationRunStatus.PARTIAL_COMMITTED,
    }
    completed_status = status in {
        ImplementationRunStatus.COMPLETED_COMMITTED,
        ImplementationRunStatus.COMPLETED_UNCOMMITTED,
    }
    partial_status = status in {
        ImplementationRunStatus.PARTIAL_COMMITTED,
        ImplementationRunStatus.PARTIAL_UNCOMMITTED,
    }
    terminal = status is not ImplementationRunStatus.RUNNING
    completion = (
        CompletionLevel.COMPLETE
        if completed_status
        else CompletionLevel.PARTIAL
        if partial_status
        else CompletionLevel.NONE
    )
    return ImplementationRun(
        implementation_run_id=run_id,
        task_id=task_id,
        repository_root="quantmind",
        branch="master",
        base_commit=BASE,
        result_commit=RESULT if committed else None,
        task_status=status,
        completion_level=completion,
        verification_level=VerificationLevel.TARGETED_TESTS,
        workspace_dirty_before=False,
        workspace_dirty_after=not committed,
        started_at=started_at,
        completed_at=started_at + timedelta(minutes=5) if terminal else None,
        agent_type="codex",
        manifest_schema_version="1.0.0",
        manifest_path=f"runs/{run_id}/manifest.json",
        manifest_hash=HASH_A if terminal else None,
        report_path=f"runs/{run_id}/report.md",
        report_hash=HASH_B if terminal else None,
        source_bundle_hash=None,
        git_diff_hash=None,
        consistency_status=consistency,
        canonical_status=canonical,
    )


def repository_with_task() -> InMemoryLedgerRepository:
    repository = InMemoryLedgerRepository()
    repository.create_task(make_task())
    return repository


def repository_with_run(run_id: str = "run-1") -> InMemoryLedgerRepository:
    repository = repository_with_task()
    repository.create_run(make_run(run_id))
    return repository


class TaskRepositoryTests(unittest.TestCase):
    def test_create_and_get_task(self):
        repository = InMemoryLedgerRepository()
        task = make_task()
        self.assertEqual(repository.create_task(task), task)
        self.assertEqual(repository.get_task(task.task_id), task)
        self.assertEqual(repository.get_task_version(task.task_id), 1)

    def test_require_missing_task_fails(self):
        with self.assertRaises(TaskNotFoundError):
            InMemoryLedgerRepository().require_task("missing-task")

    def test_exact_task_replay_is_idempotent(self):
        repository = InMemoryLedgerRepository()
        task = make_task()
        first = repository.create_task(task)
        second = repository.create_task(task)
        self.assertIs(first, second)
        self.assertEqual(repository.get_task_version(task.task_id), 1)

    def test_task_identity_conflict_fails(self):
        repository = InMemoryLedgerRepository()
        task = make_task()
        repository.create_task(task)
        with self.assertRaises(ImmutableEntityConflictError):
            repository.create_task(replace(task, title="Different"))
        self.assertEqual(repository.require_task(task.task_id), task)

    def test_task_status_update_increments_version(self):
        repository = repository_with_task()
        updated = repository.update_task_status(
            "QM2-P0-002A1b2", ImplementationTaskStatus.READY, 1
        )
        self.assertEqual(updated.status, ImplementationTaskStatus.READY)
        self.assertEqual(repository.get_task_version(updated.task_id), 2)

    def test_same_task_status_is_idempotent(self):
        repository = repository_with_task()
        task = repository.update_task_status(
            "QM2-P0-002A1b2", ImplementationTaskStatus.PLANNED, 1
        )
        self.assertEqual(task.status, ImplementationTaskStatus.PLANNED)
        self.assertEqual(repository.get_task_version(task.task_id), 1)

    def test_invalid_task_transition_fails(self):
        repository = InMemoryLedgerRepository()
        task = make_task(status=ImplementationTaskStatus.COMPLETED)
        repository.create_task(task)
        with self.assertRaises(InvalidStateTransitionError):
            repository.update_task_status(task.task_id, ImplementationTaskStatus.RUNNING, 1)

    def test_stale_task_version_fails(self):
        repository = repository_with_task()
        repository.update_task_status("QM2-P0-002A1b2", ImplementationTaskStatus.READY, 1)
        with self.assertRaises(OptimisticConcurrencyError):
            repository.update_task_status(
                "QM2-P0-002A1b2", ImplementationTaskStatus.RUNNING, 1
            )

    def test_task_query_and_pagination(self):
        repository = InMemoryLedgerRepository()
        repository.create_task(make_task("task-1", created_at=NOW))
        repository.create_task(make_task("task-2", created_at=NOW + timedelta(seconds=1)))
        page = repository.list_tasks(TaskQuery(limit=1, offset=1))
        self.assertEqual(page.total, 2)
        self.assertEqual(tuple(item.task_id for item in page.items), ("task-2",))


class RunRepositoryTests(unittest.TestCase):
    def test_create_get_and_require_run(self):
        repository = repository_with_task()
        run = make_run()
        self.assertEqual(repository.create_run(run), run)
        self.assertEqual(repository.get_run(run.implementation_run_id), run)
        self.assertEqual(repository.require_run(run.implementation_run_id), run)
        self.assertEqual(repository.get_run_version(run.implementation_run_id), 1)

    def test_run_requires_existing_task(self):
        with self.assertRaises(TaskNotFoundError):
            InMemoryLedgerRepository().create_run(make_run())

    def test_require_missing_run_fails(self):
        with self.assertRaises(RunNotFoundError):
            repository_with_task().require_run("missing-run")

    def test_exact_run_replay_is_idempotent(self):
        repository = repository_with_task()
        run = make_run()
        self.assertIs(repository.create_run(run), repository.create_run(run))
        self.assertEqual(repository.get_run_version(run.implementation_run_id), 1)

    def test_run_identity_conflict_fails(self):
        repository = repository_with_task()
        run = make_run()
        repository.create_run(run)
        with self.assertRaises(ImmutableEntityConflictError):
            repository.create_run(replace(run, branch="other"))

    def test_run_query_by_task_and_status(self):
        repository = repository_with_task()
        repository.create_run(make_run("run-1"))
        repository.create_run(make_run("run-2", started_at=NOW + timedelta(seconds=1)))
        page = repository.list_runs(
            RunQuery(task_id="QM2-P0-002A1b2", task_status=ImplementationRunStatus.RUNNING)
        )
        self.assertEqual(page.total, 2)

    def test_finalize_running_run(self):
        repository = repository_with_run()
        terminal = make_run("run-1", status=ImplementationRunStatus.COMPLETED_UNCOMMITTED)
        self.assertEqual(repository.finalize_run("run-1", terminal, 1), terminal)
        self.assertEqual(repository.get_run_version("run-1"), 2)

    def test_terminal_run_cannot_be_refinalized(self):
        repository = repository_with_run()
        terminal = make_run("run-1", status=ImplementationRunStatus.COMPLETED_UNCOMMITTED)
        repository.finalize_run("run-1", terminal, 1)
        with self.assertRaises(InvalidStateTransitionError):
            repository.finalize_run("run-1", terminal, 2)

    def test_finalization_cannot_change_identity(self):
        repository = repository_with_run()
        terminal = make_run("run-1", status=ImplementationRunStatus.COMPLETED_UNCOMMITTED)
        with self.assertRaises(ImmutableEntityConflictError):
            repository.finalize_run("run-1", replace(terminal, branch="other"), 1)

    def test_finalize_cannot_set_canonical(self):
        repository = repository_with_run()
        terminal = make_run(
            "run-1",
            status=ImplementationRunStatus.COMPLETED_COMMITTED,
            consistency=ConsistencyStatus.CONSISTENT,
            canonical=CanonicalStatus.CANONICAL,
        )
        with self.assertRaises(InvalidStateTransitionError):
            repository.finalize_run("run-1", terminal, 1)

    def test_consistency_update(self):
        repository = repository_with_run()
        updated = repository.set_consistency_status("run-1", ConsistencyStatus.CONSISTENT, 1)
        self.assertEqual(updated.consistency_status, ConsistencyStatus.CONSISTENT)
        self.assertEqual(repository.get_run_version("run-1"), 2)

    def test_illegal_canonical_transition_fails_domain_gate(self):
        repository = repository_with_run()
        with self.assertRaises(InvalidStateTransitionError):
            repository.set_canonical_status("run-1", CanonicalStatus.CANONICAL, 1)

    def test_valid_canonical_transition(self):
        repository = repository_with_task()
        run = make_run(
            "run-1",
            status=ImplementationRunStatus.COMPLETED_COMMITTED,
            consistency=ConsistencyStatus.CONSISTENT,
        )
        repository.create_run(run)
        updated = repository.set_canonical_status("run-1", CanonicalStatus.CANONICAL, 1)
        self.assertEqual(updated.canonical_status, CanonicalStatus.CANONICAL)

    def test_stale_run_version_fails(self):
        repository = repository_with_run()
        repository.set_consistency_status("run-1", ConsistencyStatus.CONSISTENT, 1)
        with self.assertRaises(OptimisticConcurrencyError):
            repository.set_canonical_status("run-1", CanonicalStatus.CANDIDATE, 1)


class RelationshipRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_with_task()
        for index in range(1, 4):
            self.repository.create_run(make_run(f"run-{index}"))

    def relationship(self, relationship_id: str, source: str, target: str):
        return RunRelationship(
            relationship_id,
            source,
            target,
            RunRelationshipType.DEPENDS_ON,
            "Explicit dependency.",
            NOW,
        )

    def test_add_and_get_relationship(self):
        relationship = self.relationship("rel-1", "run-1", "run-2")
        self.assertEqual(self.repository.add_relationship(relationship), relationship)
        self.assertEqual(self.repository.get_relationship("rel-1"), relationship)

    def test_relationship_exact_replay(self):
        relationship = self.relationship("rel-1", "run-1", "run-2")
        self.assertIs(
            self.repository.add_relationship(relationship),
            self.repository.add_relationship(relationship),
        )

    def test_relationship_identity_conflict(self):
        relationship = self.relationship("rel-1", "run-1", "run-2")
        self.repository.add_relationship(relationship)
        with self.assertRaises(ImmutableEntityConflictError):
            self.repository.add_relationship(replace(relationship, target_run_id="run-3"))

    def test_duplicate_relationship_natural_key_fails(self):
        self.repository.add_relationship(self.relationship("rel-1", "run-1", "run-2"))
        with self.assertRaises(DuplicateChildEntityError):
            self.repository.add_relationship(self.relationship("rel-2", "run-1", "run-2"))

    def test_missing_source_fails(self):
        with self.assertRaises(RunNotFoundError):
            self.repository.add_relationship(self.relationship("rel-1", "missing", "run-2"))

    def test_missing_target_fails(self):
        with self.assertRaises(RunNotFoundError):
            self.repository.add_relationship(self.relationship("rel-1", "run-1", "missing"))

    def test_self_loop_is_rejected_by_domain(self):
        with self.assertRaises(ValueError):
            self.relationship("rel-1", "run-1", "run-1")

    def test_three_node_cycle_fails(self):
        self.repository.add_relationship(self.relationship("rel-1", "run-1", "run-2"))
        self.repository.add_relationship(self.relationship("rel-2", "run-2", "run-3"))
        self.assertTrue(self.repository.would_create_cycle("run-3", "run-1"))
        with self.assertRaises(RunRelationshipCycleError):
            self.repository.add_relationship(self.relationship("rel-3", "run-3", "run-1"))

    def test_incoming_outgoing_and_exists(self):
        relationship = self.relationship("rel-1", "run-1", "run-2")
        self.repository.add_relationship(relationship)
        self.assertEqual(self.repository.list_outgoing_relationships("run-1"), (relationship,))
        self.assertEqual(self.repository.list_incoming_relationships("run-2"), (relationship,))
        self.assertTrue(
            self.repository.relationship_exists(
                "run-1", "run-2", RunRelationshipType.DEPENDS_ON
            )
        )

    def test_relationship_history_has_no_delete_operation(self):
        self.assertFalse(hasattr(self.repository, "delete_relationship"))


class ChildEntityRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_with_run()
        self.changed_file = ChangedFile("run-1", "a.py", FileChangeType.ADDED, None, HASH_A)
        self.changed_symbol = ChangedSymbol(
            "run-1", "a.py", "pkg.fn", SymbolType.FUNCTION, SymbolChangeType.ADDED
        )
        self.test = TestExecution(
            "test-1", "run-1", "python -m unittest", "Verify.", TestExecutionStatus.PASSED, 1, 0, 0
        )
        self.artifact = ImplementationArtifact(
            "artifact-1", "run-1", "report", "reports/r.md", HASH_A, "1.0.0", 10
        )
        self.component = ComponentReference("run-1", "quantmind2.project_knowledge", ImpactType.MODIFIED)
        self.adr = ArchitectureDecisionReference("run-1", "ADR-0005", ADRReferenceRelation.CONFORMS_TO)
        self.limitation = Limitation(
            "limitation-1", "run-1", LimitationSeverity.MEDIUM, None, "No database.", LimitationStatus.OPEN
        )
        self.recommendation = RecommendedTask(
            "recommendation-1", "run-1", "QM2-P0-002A2", RecommendationPriority.P0, "Implement ORM separately."
        )

    def test_append_changed_file(self):
        self.assertEqual(self.repository.append_changed_file(self.changed_file), self.changed_file)
        self.assertEqual(self.repository.list_changed_files("run-1"), (self.changed_file,))

    def test_changed_file_exact_replay(self):
        self.repository.append_changed_file(self.changed_file)
        self.assertIs(self.repository.append_changed_file(self.changed_file), self.changed_file)

    def test_changed_file_identity_conflict(self):
        self.repository.append_changed_file(self.changed_file)
        with self.assertRaises(ImmutableEntityConflictError):
            self.repository.append_changed_file(replace(self.changed_file, after_hash=HASH_B))

    def test_child_requires_parent_run(self):
        with self.assertRaises(RunNotFoundError):
            self.repository.append_changed_file(replace(self.changed_file, implementation_run_id="missing"))

    def test_append_and_list_every_child_type(self):
        pairs = (
            (self.repository.append_changed_symbol, self.repository.list_changed_symbols, self.changed_symbol),
            (self.repository.append_test_execution, self.repository.list_test_executions, self.test),
            (self.repository.append_artifact, self.repository.list_artifacts, self.artifact),
            (self.repository.append_component_reference, self.repository.list_component_references, self.component),
            (self.repository.append_adr_reference, self.repository.list_adr_references, self.adr),
            (self.repository.append_limitation, self.repository.list_limitations, self.limitation),
            (self.repository.append_recommended_task, self.repository.list_recommended_tasks, self.recommendation),
        )
        for append, listing, item in pairs:
            with self.subTest(item=type(item).__name__):
                self.assertEqual(append(item), item)
                self.assertEqual(listing("run-1"), (item,))

    def test_component_natural_key_conflict(self):
        self.repository.append_component_reference(self.component)
        with self.assertRaises(ImmutableEntityConflictError):
            self.repository.append_component_reference(
                replace(self.component, impact_type=ImpactType.VERIFIED)
            )

    def test_list_returns_immutable_new_tuple(self):
        self.repository.append_changed_file(self.changed_file)
        first = self.repository.list_changed_files("run-1")
        second = self.repository.list_changed_files("run-1")
        self.assertIsInstance(first, tuple)
        self.assertIsNot(first, second)
        self.assertFalse(hasattr(first, "append"))

    def test_detail_repository_has_no_replace_or_delete(self):
        self.assertFalse(hasattr(self.repository, "replace_changed_files"))
        self.assertFalse(hasattr(self.repository, "delete_artifact"))


class AtomicBatchTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_with_task()
        self.run = make_run("run-1")
        self.file = ChangedFile("run-1", "a.py", FileChangeType.ADDED, None, HASH_A)
        self.artifact = ImplementationArtifact(
            "artifact-1", "run-1", "report", "reports/r.md", HASH_A, None, 1
        )

    def test_valid_atomic_batch(self):
        self.repository.record_run_details_atomic(
            self.run, changed_files=(self.file,), artifacts=(self.artifact,)
        )
        self.assertEqual(self.repository.require_run("run-1"), self.run)
        self.assertEqual(self.repository.list_changed_files("run-1"), (self.file,))
        self.assertEqual(self.repository.list_artifacts("run-1"), (self.artifact,))

    def test_invalid_child_rolls_back_entire_batch(self):
        invalid = replace(self.file, implementation_run_id="other-run")
        with self.assertRaises(RunNotFoundError):
            self.repository.record_run_details_atomic(
                self.run, changed_files=(invalid,), artifacts=(self.artifact,)
            )
        self.assertIsNone(self.repository.get_run("run-1"))

    def test_late_conflict_rolls_back_earlier_batch_items(self):
        self.repository.record_run_details_atomic(self.run, changed_files=(self.file,))
        new_artifact = self.artifact
        conflicting_recommendation = RecommendedTask(
            "recommendation-1", "run-1", "QM2-P0-002A2", RecommendationPriority.P0, "First."
        )
        self.repository.append_recommended_task(conflicting_recommendation)
        changed_recommendation = replace(conflicting_recommendation, reason="Different.")
        with self.assertRaises(ImmutableEntityConflictError):
            self.repository.record_run_details_atomic(
                self.run,
                artifacts=(new_artifact,),
                recommended_tasks=(changed_recommendation,),
            )
        self.assertEqual(self.repository.list_artifacts("run-1"), ())

    def test_exact_atomic_batch_replay_is_idempotent(self):
        for _ in range(2):
            self.repository.record_run_details_atomic(
                self.run, changed_files=(self.file,), artifacts=(self.artifact,)
            )
        self.assertEqual(len(self.repository.list_changed_files("run-1")), 1)
        self.assertEqual(len(self.repository.list_artifacts("run-1")), 1)


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.repository = repository_with_task()
        for index in range(3):
            run = make_run(f"run-{index}", started_at=NOW + timedelta(hours=index))
            self.repository.create_run(run)
            self.repository.append_changed_file(
                ChangedFile(run.implementation_run_id, "shared.py", FileChangeType.ADDED, None, HASH_A)
            )
            self.repository.append_component_reference(
                ComponentReference(run.implementation_run_id, "component.shared", ImpactType.MODIFIED)
            )
            self.repository.append_adr_reference(
                ArchitectureDecisionReference(run.implementation_run_id, "ADR-0005", ADRReferenceRelation.CONFORMS_TO)
            )

    def test_filter_run_by_file(self):
        self.assertEqual(self.repository.list_runs(RunQuery(file_path="shared.py")).total, 3)

    def test_filter_run_by_component(self):
        self.assertEqual(self.repository.list_runs(RunQuery(component_id="component.shared")).total, 3)

    def test_filter_run_by_adr(self):
        self.assertEqual(self.repository.list_runs(RunQuery(adr_id="ADR-0005")).total, 3)

    def test_time_range_filter(self):
        page = self.repository.list_runs(
            RunQuery(started_from=NOW + timedelta(minutes=30), started_to=NOW + timedelta(hours=2))
        )
        self.assertEqual(tuple(item.implementation_run_id for item in page.items), ("run-1", "run-2"))

    def test_stable_sort_order(self):
        asc = self.repository.list_runs(RunQuery(sort_order=SortOrder.ASC))
        desc = self.repository.list_runs(RunQuery(sort_order=SortOrder.DESC))
        self.assertEqual(tuple(item.implementation_run_id for item in asc.items), ("run-0", "run-1", "run-2"))
        self.assertEqual(tuple(item.implementation_run_id for item in desc.items), ("run-2", "run-1", "run-0"))

    def test_total_is_before_pagination(self):
        page = self.repository.list_runs(RunQuery(limit=1, offset=1))
        self.assertEqual(page.total, 3)
        self.assertEqual(len(page.items), 1)

    def test_history_by_file_component_and_adr(self):
        for query in (
            HistoryQuery(path="shared.py"),
            HistoryQuery(component_id="component.shared"),
            HistoryQuery(adr_id="ADR-0005"),
        ):
            with self.subTest(query=query):
                self.assertEqual(self.repository.list_run_history(query).total, 3)

    def test_limit_above_maximum_fails(self):
        with self.assertRaises(RepositoryQueryError):
            RunQuery(limit=201)

    def test_negative_offset_fails(self):
        with self.assertRaises(RepositoryQueryError):
            RunQuery(offset=-1)

    def test_naive_query_time_fails(self):
        with self.assertRaises(RepositoryQueryError):
            RunQuery(started_from=datetime(2026, 7, 14))

    def test_history_requires_exactly_one_criterion(self):
        with self.assertRaises(RepositoryQueryError):
            HistoryQuery()
        with self.assertRaises(RepositoryQueryError):
            HistoryQuery(path="a.py", component_id="component.shared")


class ContractScopeTests(unittest.TestCase):
    def test_repository_protocols_and_test_double_have_no_sqlalchemy_or_fastapi_imports(self):
        for root in (DOMAIN_ROOT, TESTING_ROOT):
            for path in root.glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [node.module or ""]
                    else:
                        continue
                    self.assertFalse(any(name.startswith(("sqlalchemy", "fastapi")) for name in names))

    def test_test_double_has_no_file_or_database_io(self):
        text = (TESTING_ROOT / "in_memory_ledger_repository.py").read_text(encoding="utf-8")
        for forbidden in ("open(", "Path(", "sqlite", "postgres", "create_engine", "AsyncSession"):
            self.assertNotIn(forbidden, text)

    def test_api_persistence_boundary_has_only_authorized_task_and_run_mapper_files(self):
        api_root = REPO_ROOT / "backend/services/api/project_knowledge"
        self.assertEqual(
            {path.relative_to(api_root).as_posix() for path in api_root.rglob("*.py")},
            {
                "__init__.py",
                "persistence/__init__.py",
                "persistence/orm_annotation_models.py",
                "persistence/orm_detail_models.py",
                "persistence/orm_models.py",
                "persistence/orm_reference_models.py",
                "persistence/orm_types.py",
                "persistence/mappers/__init__.py",
                "persistence/mappers/common.py",
                "persistence/mappers/errors.py",
                "persistence/mappers/run.py",
                "persistence/mappers/task.py",
            },
        )
        for forbidden in ("repository.py", "api.py", "session.py", "unit_of_work.py"):
            self.assertFalse((api_root / forbidden).exists())
        self.assertFalse(list((REPO_ROOT / "data/migrations").glob("*ledger*")))

    def test_no_unit_of_work_implementation(self):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for root in (DOMAIN_ROOT, TESTING_ROOT)
            for path in root.glob("*.py")
        )
        self.assertNotIn("class UnitOfWork", text)
        self.assertNotIn("class LedgerWriteBatch", text)


if __name__ == "__main__":
    unittest.main()
