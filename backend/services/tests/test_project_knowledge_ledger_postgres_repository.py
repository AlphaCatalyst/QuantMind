"""Contract and concurrency tests for the PostgreSQL Ledger Repository.

Set ``QM2_LEDGER_POSTGRES_INTEGRATION=1`` to create a disposable
``postgres:15-alpine`` container.  The container has no volume mount and is
always removed by the module fixture.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.services.api.project_knowledge.persistence.orm_detail_models import (
    ImplementationArtifactRecord,
)
from backend.services.api.project_knowledge.persistence.orm_models import (
    ImplementationRunRecord,
    ImplementationTaskRecord,
    RunRelationshipRecord,
)
from backend.services.api.project_knowledge.repositories import (
    AsyncLedgerUnitOfWork,
    LedgerTransactionError,
)
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
    RunQuery,
    RunRelationship,
    RunRelationshipCycleError,
    RunRelationshipType,
    SymbolChangeType,
    SymbolType,
    TaskQuery,
    TestExecution,
    TestExecutionStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.testing import InMemoryLedgerRepository


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "tools/quantmind2/ledger_migrations.py"
PYTHON = os.environ.get("QM2_TEST_PYTHON", os.sys.executable)
NOW = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)
BASE = "a" * 40
RESULT = "b" * 40
HASH_A = "1" * 64
HASH_B = "2" * 64


def make_task(
    task_id: str,
    *,
    parent_task_id: str | None = None,
    created_at: datetime = NOW,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id,
        parent_task_id=parent_task_id,
        title=f"Task {task_id}",
        objective="Verify PostgreSQL repository behavior.",
        scope=("Ledger persistence",),
        explicit_non_goals=("No production database",),
        status=ImplementationTaskStatus.PLANNED,
        created_at=created_at,
    )


def make_run(
    run_id: str,
    task_id: str,
    *,
    started_at: datetime = NOW,
    status: ImplementationRunStatus = ImplementationRunStatus.RUNNING,
    consistency: ConsistencyStatus = ConsistencyStatus.UNVERIFIED,
    canonical: CanonicalStatus = CanonicalStatus.NONCANONICAL,
) -> ImplementationRun:
    committed = status in {
        ImplementationRunStatus.COMPLETED_COMMITTED,
        ImplementationRunStatus.PARTIAL_COMMITTED,
    }
    terminal = status is not ImplementationRunStatus.RUNNING
    completed = status in {
        ImplementationRunStatus.COMPLETED_COMMITTED,
        ImplementationRunStatus.COMPLETED_UNCOMMITTED,
    }
    partial = status in {
        ImplementationRunStatus.PARTIAL_COMMITTED,
        ImplementationRunStatus.PARTIAL_UNCOMMITTED,
    }
    return ImplementationRun(
        implementation_run_id=run_id,
        task_id=task_id,
        repository_root="quantmind",
        branch="master",
        base_commit=BASE,
        result_commit=RESULT if committed else None,
        task_status=status,
        completion_level=(
            CompletionLevel.COMPLETE
            if completed
            else CompletionLevel.PARTIAL
            if partial
            else CompletionLevel.NONE
        ),
        verification_level=VerificationLevel.INTEGRATION_TESTS,
        workspace_dirty_before=False,
        workspace_dirty_after=not committed,
        started_at=started_at,
        completed_at=started_at + timedelta(minutes=1) if terminal else None,
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


def make_artifact(run_id: str, artifact_id: str, *, path: str | None = None) -> ImplementationArtifact:
    return ImplementationArtifact(
        artifact_id=artifact_id,
        implementation_run_id=run_id,
        artifact_type="report",
        path_or_uri=path or f"runs/{run_id}/report.md",
        content_hash=HASH_A,
        schema_version="1.0.0",
        size_bytes=42,
    )


def _run(argv: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, text=True, capture_output=True, env=env, check=False)
    if result.returncode:
        raise AssertionError(f"isolated PostgreSQL setup command failed: {result.stderr}")
    return result


@pytest.fixture(scope="module")
def postgres_url() -> str:
    if os.environ.get("QM2_LEDGER_POSTGRES_INTEGRATION") != "1":
        pytest.skip("requires explicit disposable PostgreSQL opt-in")
    if shutil.which("docker") is None or shutil.which("psql") is None:
        pytest.skip("docker and psql are required")
    token = secrets.token_hex(6)
    container = f"qm2-ledger-repository-{token}"
    password = secrets.token_hex(24)
    docker_env = os.environ.copy()
    docker_env["POSTGRES_PASSWORD"] = password
    psql_env = os.environ.copy()
    psql_env["PGPASSWORD"] = password
    started = False
    try:
        _run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_DB=qm2_ledger_repository_test",
                "-p",
                "127.0.0.1::5432",
                "postgres:15-alpine",
            ],
            env=docker_env,
        )
        started = True
        port = _run(["docker", "port", container, "5432/tcp"], env=os.environ.copy()).stdout.strip().rsplit(":", 1)[1]
        connection = [
            "--host",
            "127.0.0.1",
            "--port",
            port,
            "--username",
            "postgres",
            "--dbname",
            "qm2_ledger_repository_test",
        ]
        runner_connection = [
            "--host",
            "127.0.0.1",
            "--port",
            port,
            "--username",
            "postgres",
            "--database",
            "qm2_ledger_repository_test",
        ]
        for _ in range(80):
            probe = subprocess.run(
                ["psql", *connection, "-X", "--no-psqlrc", "-qAt", "-c", "SELECT 1"],
                text=True,
                capture_output=True,
                env=psql_env,
                check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise AssertionError("disposable PostgreSQL did not become ready")
        _run(
            [PYTHON, str(RUNNER), "up", *runner_connection],
            env=psql_env,
        )
        yield f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/qm2_ledger_repository_test"
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "-f", container],
                text=True,
                capture_output=True,
                check=False,
            )


async def _factory(maker: async_sessionmaker[AsyncSession]) -> AsyncSession:
    return maker()


def test_unit_of_work_lifecycle_and_repository_transaction_neutrality() -> None:
    async def scenario() -> None:
        committed = AsyncSession()
        with (
            patch.object(committed, "commit", new=AsyncMock()) as commit,
            patch.object(committed, "rollback", new=AsyncMock()) as rollback,
            patch.object(committed, "close", new=AsyncMock()) as close,
        ):
            async def committed_factory() -> AsyncSession:
                return committed

            async with AsyncLedgerUnitOfWork(session_factory=committed_factory) as uow:
                assert uow.repository is not None
                await uow.commit()
                with pytest.raises(LedgerTransactionError):
                    await uow.commit()
                with pytest.raises(LedgerTransactionError):
                    await uow.repository.create_task(make_task("after-commit"))
            commit.assert_awaited_once()
            rollback.assert_not_awaited()
            close.assert_awaited_once()

        uncommitted = AsyncSession()
        with (
            patch.object(uncommitted, "rollback", new=AsyncMock()) as rollback,
            patch.object(uncommitted, "close", new=AsyncMock()) as close,
        ):
            async def uncommitted_factory() -> AsyncSession:
                return uncommitted

            async with AsyncLedgerUnitOfWork(session_factory=uncommitted_factory):
                pass
            rollback.assert_awaited_once()
            close.assert_awaited_once()

        exceptional = AsyncSession()
        with patch.object(exceptional, "rollback", new=AsyncMock()) as rollback:
            with pytest.raises(RuntimeError):
                async with AsyncLedgerUnitOfWork(session=exceptional):
                    raise RuntimeError("expected")
            rollback.assert_awaited_once()

        failing = AsyncSession()
        with (
            patch.object(failing, "commit", new=AsyncMock(side_effect=RuntimeError("db"))),
            patch.object(failing, "rollback", new=AsyncMock()) as rollback,
        ):
            with pytest.raises(LedgerTransactionError):
                async with AsyncLedgerUnitOfWork(session=failing) as uow:
                    await uow.commit()
            rollback.assert_awaited_once()

    asyncio.run(scenario())
    source = (ROOT / "backend/services/api/project_knowledge/repositories/postgres.py").read_text()
    assert ".commit(" not in source
    assert ".rollback(" not in source


def test_postgres_repository_full_contract(postgres_url: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(postgres_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        factory = lambda: _factory(maker)  # noqa: E731
        try:
            task = make_task("contract-root")
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                repo = uow.repository
                assert repo is not None
                assert await repo.create_task(task) == task
                assert await repo.create_task(task) == task
                with pytest.raises(ImmutableEntityConflictError):
                    await repo.create_task(replace(task, title="Different"))
                child = make_task("contract-child", parent_task_id=task.task_id, created_at=NOW + timedelta(seconds=1))
                await repo.create_task(child)
                page = await repo.list_tasks(TaskQuery(parent_task_id=task.task_id, limit=1))
                assert page.total == 1 and page.items == (child,)
                updated = await repo.update_task_status(task.task_id, ImplementationTaskStatus.READY, 1)
                assert updated.status is ImplementationTaskStatus.READY
                assert await repo.get_task_version(task.task_id) == 2
                with pytest.raises(OptimisticConcurrencyError):
                    await repo.update_task_status(task.task_id, ImplementationTaskStatus.RUNNING, 1)
                await uow.commit()

            run = make_run("contract-run", task.task_id)
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                repo = uow.repository
                assert repo is not None
                assert await repo.create_run(run) == run
                assert await repo.create_run(run) == run
                with pytest.raises(ImmutableEntityConflictError):
                    await repo.create_run(replace(run, branch="other"))
                terminal = make_run(
                    run.implementation_run_id,
                    task.task_id,
                    status=ImplementationRunStatus.COMPLETED_UNCOMMITTED,
                    consistency=ConsistencyStatus.CONSISTENT,
                )
                finalized = await repo.finalize_run(run.implementation_run_id, terminal, 1)
                assert finalized == terminal and await repo.get_run_version(run.implementation_run_id) == 2
                with pytest.raises(InvalidStateTransitionError):
                    await repo.finalize_run(run.implementation_run_id, terminal, 2)
                assert await repo.set_consistency_status(run.implementation_run_id, ConsistencyStatus.CONSISTENT, 2) == terminal
                await uow.commit()

            canonical = make_run(
                "canonical-run",
                task.task_id,
                started_at=NOW + timedelta(seconds=1),
                status=ImplementationRunStatus.COMPLETED_COMMITTED,
                consistency=ConsistencyStatus.CONSISTENT,
                canonical=CanonicalStatus.CANDIDATE,
            )
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                repo = uow.repository
                assert repo is not None
                await repo.create_run(canonical)
                promoted = await repo.set_canonical_status(canonical.implementation_run_id, CanonicalStatus.CANONICAL, 1)
                assert promoted.canonical_status is CanonicalStatus.CANONICAL
                assert await repo.set_canonical_status(canonical.implementation_run_id, CanonicalStatus.CANONICAL, 2) == promoted
                page = await repo.list_runs(RunQuery(task_id=task.task_id, canonical_status=CanonicalStatus.CANONICAL))
                assert page.total == 1 and page.items == (promoted,)
                await uow.commit()

            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                repo = uow.repository
                assert repo is not None
                changed_file = ChangedFile("contract-run", "backend/a.py", FileChangeType.ADDED, after_hash=HASH_A)
                changed_symbol = ChangedSymbol("contract-run", "backend/a.py", "A.f", SymbolType.METHOD, SymbolChangeType.ADDED)
                test = TestExecution("test-contract", "contract-run", "pytest -q", "contract", TestExecutionStatus.PASSED, 1, 0, 0)
                artifact = make_artifact("contract-run", "artifact-contract")
                component = ComponentReference("contract-run", "quantmind2.project_knowledge", ImpactType.MODIFIED)
                adr = ArchitectureDecisionReference("contract-run", "ADR-0005", ADRReferenceRelation.CONFORMS_TO)
                limitation = Limitation("limit-contract", "contract-run", LimitationSeverity.LOW, None, "Read optimization is deferred.", LimitationStatus.OPEN)
                recommendation = RecommendedTask("recommend-contract", "contract-run", "QM2-P0-002B", RecommendationPriority.P0, "Continue with the indexer.")
                pairs = (
                    (repo.append_changed_file, repo.list_changed_files, changed_file),
                    (repo.append_changed_symbol, repo.list_changed_symbols, changed_symbol),
                    (repo.append_test_execution, repo.list_test_executions, test),
                    (repo.append_artifact, repo.list_artifacts, artifact),
                    (repo.append_component_reference, repo.list_component_references, component),
                    (repo.append_adr_reference, repo.list_adr_references, adr),
                    (repo.append_limitation, repo.list_limitations, limitation),
                    (repo.append_recommended_task, repo.list_recommended_tasks, recommendation),
                )
                for append, listing, item in pairs:
                    assert await append(item) == item
                    assert await append(item) == item
                    assert await listing("contract-run") == (item,)
                with pytest.raises(ImmutableEntityConflictError):
                    await repo.append_artifact(replace(artifact, path_or_uri="runs/contract-run/other.md"))
                assert (await repo.list_run_history(HistoryQuery(path="backend/a.py"))).items == (terminal,)
                assert (await repo.list_run_history(HistoryQuery(component_id=component.component_id))).items == (terminal,)
                assert (await repo.list_run_history(HistoryQuery(adr_id=adr.adr_id))).items == (terminal,)
                await uow.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_relationship_dag_and_atomic_batch(postgres_url: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(postgres_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        factory = lambda: _factory(maker)  # noqa: E731
        task_id = "graph-task"
        try:
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                repo = uow.repository
                assert repo is not None
                await repo.create_task(make_task(task_id))
                for index in range(3):
                    await repo.create_run(make_run(f"graph-{index}", task_id, started_at=NOW + timedelta(seconds=index)))
                first = RunRelationship("rel-01", "graph-0", "graph-1", RunRelationshipType.DEPENDS_ON, "first edge", NOW)
                second = RunRelationship("rel-12", "graph-1", "graph-2", RunRelationshipType.CONTINUES, "second edge", NOW + timedelta(seconds=1))
                assert await repo.add_relationship(first) == first
                assert await repo.add_relationship(first) == first
                await repo.add_relationship(second)
                assert await repo.relationship_exists("graph-0", "graph-1", RunRelationshipType.DEPENDS_ON)
                assert await repo.would_create_cycle("graph-2", "graph-0")
                with pytest.raises(RunRelationshipCycleError):
                    await repo.add_relationship(RunRelationship("rel-20", "graph-2", "graph-0", RunRelationshipType.CORRECTS, "would cycle", NOW + timedelta(seconds=2)))
                assert await repo.list_outgoing_relationships("graph-0") == (first,)
                assert await repo.list_incoming_relationships("graph-2") == (second,)
                await uow.commit()

            batch_run = make_run("batch-success", task_id, started_at=NOW + timedelta(minutes=1))
            artifact = make_artifact(batch_run.implementation_run_id, "batch-artifact")
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                assert uow.repository is not None
                await uow.repository.record_run_details_atomic(batch_run, artifacts=(artifact,))
                await uow.repository.record_run_details_atomic(batch_run, artifacts=(artifact,))
                await uow.commit()

            failed_run = make_run("batch-failed", task_id, started_at=NOW + timedelta(minutes=2))
            collision = make_artifact(failed_run.implementation_run_id, artifact.artifact_id)
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                assert uow.repository is not None
                with pytest.raises(ImmutableEntityConflictError):
                    await uow.repository.record_run_details_atomic(failed_run, artifacts=(collision,))
                assert await uow.repository.get_run(failed_run.implementation_run_id) is None
                await uow.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_in_memory_and_postgres_shared_contract_scenario(postgres_url: str) -> None:
    task = make_task("parity-task")
    run_a = make_run("parity-a", task.task_id)
    run_b = make_run("parity-b", task.task_id, started_at=NOW + timedelta(seconds=1))
    artifact = make_artifact(run_a.implementation_run_id, "parity-artifact")
    edge = RunRelationship(
        "parity-edge",
        run_a.implementation_run_id,
        run_b.implementation_run_id,
        RunRelationshipType.CONTINUES,
        "shared contract edge",
        NOW,
    )

    memory = InMemoryLedgerRepository()
    assert memory.create_task(task) == memory.create_task(task)
    memory.create_run(run_a)
    memory.create_run(run_b)
    assert memory.create_run(run_a) == run_a
    assert memory.append_artifact(artifact) == memory.append_artifact(artifact)
    assert memory.add_relationship(edge) == memory.add_relationship(edge)
    with pytest.raises(RunRelationshipCycleError):
        memory.add_relationship(
            RunRelationship(
                "parity-cycle-memory",
                run_b.implementation_run_id,
                run_a.implementation_run_id,
                RunRelationshipType.DEPENDS_ON,
                "shared contract cycle",
                NOW,
            )
        )
    expected = {
        "task": memory.require_task(task.task_id),
        "runs": memory.list_runs(RunQuery(task_id=task.task_id)).items,
        "artifacts": memory.list_artifacts(run_a.implementation_run_id),
        "outgoing": memory.list_outgoing_relationships(run_a.implementation_run_id),
    }

    async def scenario() -> None:
        engine = create_async_engine(postgres_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with AsyncLedgerUnitOfWork(
                session_factory=lambda: _factory(maker)
            ) as uow:
                repo = uow.repository
                assert repo is not None
                assert await repo.create_task(task) == await repo.create_task(task)
                await repo.create_run(run_a)
                await repo.create_run(run_b)
                assert await repo.create_run(run_a) == run_a
                assert await repo.append_artifact(artifact) == await repo.append_artifact(artifact)
                assert await repo.add_relationship(edge) == await repo.add_relationship(edge)
                with pytest.raises(RunRelationshipCycleError):
                    await repo.add_relationship(
                        RunRelationship(
                            "parity-cycle-postgres",
                            run_b.implementation_run_id,
                            run_a.implementation_run_id,
                            RunRelationshipType.DEPENDS_ON,
                            "shared contract cycle",
                            NOW,
                        )
                    )
                actual = {
                    "task": await repo.require_task(task.task_id),
                    "runs": (await repo.list_runs(RunQuery(task_id=task.task_id))).items,
                    "artifacts": await repo.list_artifacts(run_a.implementation_run_id),
                    "outgoing": await repo.list_outgoing_relationships(run_a.implementation_run_id),
                }
                assert actual == expected
                await uow.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_real_postgres_concurrency(postgres_url: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(postgres_url, pool_size=10, max_overflow=10)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        factory = lambda: _factory(maker)  # noqa: E731
        try:
            same = make_task("concurrent-same")

            async def create_task_worker(task: ImplementationTask):
                async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                    assert uow.repository is not None
                    stored = await uow.repository.create_task(task)
                    await uow.commit()
                    return stored

            results = await asyncio.gather(create_task_worker(same), create_task_worker(same))
            assert results == [same, same]

            different = make_task("concurrent-different")
            outcomes = await asyncio.gather(
                create_task_worker(different),
                create_task_worker(replace(different, title="Different concurrent content")),
                return_exceptions=True,
            )
            assert sum(isinstance(item, ImplementationTask) for item in outcomes) == 1
            assert sum(isinstance(item, ImmutableEntityConflictError) for item in outcomes) == 1

            stale = make_task("concurrent-version")
            await create_task_worker(stale)

            async def update_worker(status: ImplementationTaskStatus):
                async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                    assert uow.repository is not None
                    result = await uow.repository.update_task_status(stale.task_id, status, 1)
                    await uow.commit()
                    return result

            outcomes = await asyncio.gather(
                update_worker(ImplementationTaskStatus.READY),
                update_worker(ImplementationTaskStatus.RUNNING),
                return_exceptions=True,
            )
            assert sum(isinstance(item, ImplementationTask) for item in outcomes) == 1
            assert sum(isinstance(item, OptimisticConcurrencyError) for item in outcomes) == 1

            graph_task = make_task("concurrent-graph-task")
            await create_task_worker(graph_task)
            async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                assert uow.repository is not None
                await uow.repository.create_run(make_run("race-a", graph_task.task_id))
                await uow.repository.create_run(make_run("race-b", graph_task.task_id, started_at=NOW + timedelta(seconds=1)))
                await uow.commit()

            async def relationship_worker(relationship: RunRelationship):
                async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                    assert uow.repository is not None
                    result = await uow.repository.add_relationship(relationship)
                    await uow.commit()
                    return result

            outcomes = await asyncio.gather(
                relationship_worker(RunRelationship("race-ab", "race-a", "race-b", RunRelationshipType.DEPENDS_ON, "race edge", NOW)),
                relationship_worker(RunRelationship("race-ba", "race-b", "race-a", RunRelationshipType.CONTINUES, "reverse race edge", NOW)),
                return_exceptions=True,
            )
            assert sum(isinstance(item, RunRelationship) for item in outcomes) == 1
            assert sum(isinstance(item, RunRelationshipCycleError) for item in outcomes) == 1

            async with maker() as session:
                assert (await session.execute(select(func.count()).select_from(ImplementationTaskRecord).where(ImplementationTaskRecord.task_id == same.task_id))).scalar_one() == 1
                assert (await session.execute(select(ImplementationTaskRecord.version).where(ImplementationTaskRecord.task_id == stale.task_id))).scalar_one() == 2
                assert (await session.execute(select(func.count()).select_from(RunRelationshipRecord).where(RunRelationshipRecord.relationship_id.in_(("race-ab", "race-ba"))))).scalar_one() == 1

            legal_run = make_run("concurrent-batch-legal", graph_task.task_id, started_at=NOW + timedelta(minutes=1))
            conflict_run = make_run("concurrent-batch-conflict", graph_task.task_id, started_at=NOW + timedelta(minutes=2))
            shared_artifact_id = "concurrent-batch-artifact"

            async def batch_worker(run: ImplementationRun, artifact_path: str):
                async with AsyncLedgerUnitOfWork(session_factory=factory) as uow:
                    assert uow.repository is not None
                    result = await uow.repository.record_run_details_atomic(
                        run,
                        artifacts=(make_artifact(run.implementation_run_id, shared_artifact_id, path=artifact_path),),
                    )
                    await uow.commit()
                    return result

            outcomes = await asyncio.gather(
                batch_worker(legal_run, "runs/legal/report.md"),
                batch_worker(conflict_run, "runs/conflict/report.md"),
                return_exceptions=True,
            )
            assert sum(isinstance(item, ImplementationRun) for item in outcomes) == 1
            assert sum(isinstance(item, ImmutableEntityConflictError) for item in outcomes) == 1
            winner = next(item for item in outcomes if isinstance(item, ImplementationRun))
            loser_id = conflict_run.implementation_run_id if winner == legal_run else legal_run.implementation_run_id
            async with maker() as session:
                assert (await session.execute(select(func.count()).select_from(ImplementationArtifactRecord).where(ImplementationArtifactRecord.artifact_id == shared_artifact_id))).scalar_one() == 1
                assert (await session.execute(select(func.count()).select_from(ImplementationRunRecord).where(ImplementationRunRecord.implementation_run_id == loser_id))).scalar_one() == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())
