from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.api.project_knowledge.indexing import (
    LedgerIndexConflictError,
    LedgerIndexer,
)
from backend.services.api.project_knowledge.indexing.models import ImplementationDomainBundle
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
    ImpactType,
    ImplementationArtifact,
    ImplementationRun,
    ImplementationRunStatus,
    ImplementationTask,
    ImplementationTaskStatus,
    Limitation,
    LimitationSeverity,
    LimitationStatus,
    RecommendationPriority,
    RecommendedTask,
    RunRelationship,
    RunRelationshipType,
    SymbolChangeType,
    SymbolType,
    TestExecution,
    TestExecutionStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.testing import InMemoryLedgerRepository


NOW = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64
BASE = "1" * 40
RESULT = "2" * 40


class _AsyncRepository:
    def __init__(self, repository: InMemoryLedgerRepository) -> None:
        self._repository = repository

    async def create_task(self, value):  # noqa: ANN001
        return self._repository.create_task(value)

    async def get_run(self, run_id: str):
        return self._repository.get_run(run_id)

    async def record_run_details_atomic(self, run, **children):  # noqa: ANN001
        return self._repository.record_run_details_atomic(run, **children)

    async def add_relationship(self, value):  # noqa: ANN001
        return self._repository.add_relationship(value)

    async def list_runs(self, query):  # noqa: ANN001
        return self._repository.list_runs(query)


class _UnitOfWork:
    def __init__(self, repository: InMemoryLedgerRepository, events: list[str]) -> None:
        self.repository = _AsyncRepository(repository)
        self.events = events

    async def __aenter__(self):
        self.events.append("enter")
        return self

    async def commit(self) -> None:
        self.events.append("commit")

    async def __aexit__(self, *args) -> None:  # noqa: ANN002
        self.events.append("exit")


def _task(task_id: str, parent: str | None, minute: int) -> ImplementationTask:
    return ImplementationTask(
        task_id,
        parent,
        f"Task {task_id}",
        "Verify deterministic Ledger indexing.",
        ("indexing",),
        ("production",),
        ImplementationTaskStatus.COMPLETED,
        NOW + timedelta(minutes=minute),
    )


def _run(run_id: str, task_id: str, minute: int) -> ImplementationRun:
    started = NOW + timedelta(minutes=minute)
    return ImplementationRun(
        run_id,
        task_id,
        "quantmind-main",
        "master",
        BASE,
        RESULT,
        ImplementationRunStatus.COMPLETED_COMMITTED,
        CompletionLevel.COMPLETE,
        VerificationLevel.INTEGRATION_TESTS,
        False,
        False,
        started,
        started + timedelta(minutes=1),
        "codex",
        "2.0.0",
        f"runs/{run_id}/manifest.json",
        HASH_A,
        f"runs/{run_id}/report.md",
        HASH_B,
        None,
        None,
        ConsistencyStatus.CONSISTENT,
        CanonicalStatus.NONCANONICAL,
    )


def _bundle(run_id: str, task: ImplementationTask, minute: int) -> ImplementationDomainBundle:
    run = _run(run_id, task.task_id, minute)
    return ImplementationDomainBundle(
        task=task,
        run=run,
        changed_files=(ChangedFile(run_id, "file.py", FileChangeType.ADDED, after_hash=HASH_A),),
        changed_symbols=(ChangedSymbol(run_id, "file.py", "module.fn", SymbolType.FUNCTION, SymbolChangeType.ADDED),),
        tests=(TestExecution("test-" + run_id, run_id, "pytest -q", "Verify indexer", TestExecutionStatus.PASSED, 1, 0, 0),),
        artifacts=(ImplementationArtifact("artifact-" + run_id, run_id, "report", f"runs/{run_id}/report.md", HASH_B, "1.0.0", 42),),
        component_refs=(ComponentReference(run_id, "quantmind2.project_knowledge", ImpactType.MODIFIED),),
        adr_refs=(ArchitectureDecisionReference(run_id, "ADR-0010", ADRReferenceRelation.IMPLEMENTS),),
        limitations=(Limitation("limit-" + run_id, run_id, LimitationSeverity.LOW, None, "Synthetic limitation.", LimitationStatus.OPEN),),
        recommended_tasks=(RecommendedTask("next-" + run_id, run_id, "QM2-P0-003", RecommendationPriority.P0, "Continue to data foundation."),),
    )


def test_indexer_orders_tasks_writes_children_atomically_then_relationships() -> None:
    repository = InMemoryLedgerRepository()
    events: list[str] = []
    indexer = LedgerIndexer(lambda: _UnitOfWork(repository, events))
    root_task = _task("task-root", None, 0)
    child_task = _task("task-child", "task-root", 1)
    root = _bundle("run-root", root_task, 2)
    child = _bundle("run-child", child_task, 3)
    relationship = RunRelationship(
        "relationship-1",
        "run-child",
        "run-root",
        RunRelationshipType.DEPENDS_ON,
        "Child follows root.",
        NOW + timedelta(minutes=5),
    )
    child = replace(child, relationships=(relationship,))

    result = asyncio.run(
        indexer.index_bundles(
            repository_id="quantmind-main",
            ref_commit=RESULT,
            discovered=2,
            validated=2,
            bundles=(child, root),
        )
    )
    assert result.indexed == 2
    assert result.relationships == 1
    assert repository.require_task("task-root") == root_task
    assert repository.require_run("run-child") == child.run
    assert len(repository.list_changed_files("run-child")) == 1
    assert repository.require_relationship("relationship-1") == relationship
    assert events.count("commit") == 5

    replay = asyncio.run(
        indexer.index_bundles(
            repository_id="quantmind-main",
            ref_commit=RESULT,
            discovered=2,
            validated=2,
            bundles=(child, root),
        )
    )
    assert replay.replayed == 2
    assert replay.indexed == 0


def test_indexer_surfaces_immutable_conflict_without_partial_child_write() -> None:
    repository = InMemoryLedgerRepository()
    indexer = LedgerIndexer(lambda: _UnitOfWork(repository, []))
    bundle = _bundle("run-one", _task("task-one", None, 0), 1)
    asyncio.run(
        indexer.index_bundles(
            repository_id="quantmind-main",
            ref_commit=RESULT,
            discovered=1,
            validated=1,
            bundles=(bundle,),
        )
    )
    conflict = replace(bundle, run=replace(bundle.run, branch="conflict"))
    with pytest.raises(LedgerIndexConflictError):
        asyncio.run(
            indexer.index_bundles(
                repository_id="quantmind-main",
                ref_commit=RESULT,
                discovered=1,
                validated=1,
                bundles=(conflict,),
            )
        )
    assert repository.require_run("run-one") == bundle.run
    assert len(repository.list_artifacts("run-one")) == 1
