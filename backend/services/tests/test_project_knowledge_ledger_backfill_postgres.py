"""Disposable PostgreSQL verification for the Git Ledger indexer's write path."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

import pytest

from backend.services.api.project_knowledge.indexing import (
    GitSnapshot,
    ImplementationRunPlanner,
    LedgerIndexConflictError,
    LedgerIndexer,
    bind_repository,
)
from backend.services.api.project_knowledge.repositories import AsyncLedgerUnitOfWork
from backend.services.tests.test_project_knowledge_ledger_indexer import _bundle, _task
from backend.services.tests.test_project_knowledge_manifest_v2 import build_v2_repository
from backend.shared.database_manager_v2 import DatabaseConfig, DatabaseManager


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "tools/quantmind2/ledger_migrations.py"
pytestmark = pytest.mark.skipif(
    os.environ.get("QM2_LEDGER_POSTGRES_INTEGRATION") != "1",
    reason="requires explicit disposable PostgreSQL opt-in",
)


def _command(argv: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, text=True, capture_output=True, env=env, check=False)
    if result.returncode:
        raise AssertionError(f"command failed: {result.stderr}")
    return result


@pytest.fixture(scope="module")
def postgres_url() -> str:
    if not shutil.which("docker") or not shutil.which("psql"):
        pytest.skip("docker and psql are required")
    token = secrets.token_hex(6)
    container = f"qm2-ledger-indexer-{token}"
    password = secrets.token_hex(24)
    docker_env = os.environ.copy()
    docker_env["POSTGRES_PASSWORD"] = password
    started = False
    try:
        _command(
            [
                "docker", "run", "-d", "--rm", "--name", container,
                "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB=qm2_indexer_test",
                "-p", "127.0.0.1::5432", "postgres:15-alpine",
            ],
            env=docker_env,
        )
        started = True
        port = _command(["docker", "port", container, "5432/tcp"], env=os.environ.copy()).stdout.strip().rsplit(":", 1)[1]
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        connection = ["--host", "127.0.0.1", "--port", port, "--username", "postgres", "--dbname", "qm2_indexer_test"]
        runner_connection = ["--host", "127.0.0.1", "--port", port, "--username", "postgres", "--database", "qm2_indexer_test"]
        for _ in range(80):
            probe = subprocess.run(
                ["psql", *connection, "-X", "--no-psqlrc", "-qAt", "-c", "SELECT 1"],
                text=True, capture_output=True, env=env, check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise AssertionError("PostgreSQL did not become ready")
        _command([os.sys.executable, str(RUNNER), "up", *runner_connection], env=env)
        yield f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/qm2_indexer_test"
    finally:
        if started:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, check=False)


def test_postgresql_index_replay_conflict_and_no_partial_write(postgres_url: str) -> None:
    async def scenario() -> None:
        config = DatabaseConfig()
        config.database_url = postgres_url
        config.pool_size = 2
        config.max_overflow = 0
        manager = DatabaseManager(config)
        await manager.initialize()
        try:
            indexer = LedgerIndexer(lambda: AsyncLedgerUnitOfWork(database_manager=manager))
            bundle = _bundle("run-postgres", _task("task-postgres", None, 0), 1)
            first = await indexer.index_bundles(
                repository_id="quantmind-main",
                ref_commit="2" * 40,
                discovered=1,
                validated=1,
                bundles=(bundle,),
            )
            assert first.indexed == 1
            second = await indexer.index_bundles(
                repository_id="quantmind-main",
                ref_commit="2" * 40,
                discovered=1,
                validated=1,
                bundles=(bundle,),
            )
            assert second.replayed == 1

            conflict = replace(bundle, run=replace(bundle.run, branch="conflict"))
            with pytest.raises(LedgerIndexConflictError):
                await indexer.index_bundles(
                    repository_id="quantmind-main",
                    ref_commit="2" * 40,
                    discovered=1,
                    validated=1,
                    bundles=(conflict,),
                )
            async with AsyncLedgerUnitOfWork(database_manager=manager) as uow:
                assert uow.repository is not None
                assert await uow.repository.get_run("run-postgres") == bundle.run
                assert len(await uow.repository.list_artifacts("run-postgres")) == 1
        finally:
            await manager.close()

    asyncio.run(scenario())


def test_manifest_v2_git_plan_indexes_all_families_and_replays_exactly(
    postgres_url: str, tmp_path: Path
) -> None:
    root, run_id, _, analyzed = build_v2_repository(tmp_path)
    assert analyzed.validated and analyzed.indexable
    plan = ImplementationRunPlanner(
        GitSnapshot(bind_repository("synthetic-main", root))
    ).plan(run_id)
    bundle = plan.runs[0].domain_build.bundle
    assert bundle is not None

    async def scenario() -> None:
        config = DatabaseConfig()
        config.database_url = postgres_url
        config.pool_size = 2
        config.max_overflow = 0
        manager = DatabaseManager(config)
        await manager.initialize()
        try:
            indexer = LedgerIndexer(lambda: AsyncLedgerUnitOfWork(database_manager=manager))
            target = _bundle(
                "QM2-P0-996-20260716T000000Z-7654321",
                _task("QM2-P0-996", None, 0),
                1,
            )
            await indexer.index_bundles(
                repository_id="synthetic-main", ref_commit="1" * 40,
                discovered=1, validated=1, bundles=(target,),
            )
            first = await indexer.index_plan(plan)
            assert first.indexed == 1 and first.relationships == 1
            second = await indexer.index_plan(plan)
            assert second.replayed == 1 and second.relationships == 1
            async with AsyncLedgerUnitOfWork(database_manager=manager) as uow:
                repository = uow.repository
                assert repository is not None
                assert len(await repository.list_changed_files(run_id)) == 2
                assert len(await repository.list_changed_symbols(run_id)) == 1
                assert len(await repository.list_test_executions(run_id)) == 1
                assert len(await repository.list_artifacts(run_id)) == 2
                assert len(await repository.list_component_references(run_id)) == 1
                assert len(await repository.list_adr_references(run_id)) == 1
                assert len(await repository.list_limitations(run_id)) == 1
                assert len(await repository.list_recommended_tasks(run_id)) == 1
                assert len(await repository.list_outgoing_relationships(run_id)) == 1
        finally:
            await manager.close()

    asyncio.run(scenario())


def test_real_003l_indexes_replays_and_omits_manifest_changed_file(
    postgres_url: str,
) -> None:
    run_id = "QM2-P0-003L-20260716T151140Z-7d29df7"
    plan = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    ).plan(run_id)
    analyzed = plan.runs[0]
    assert analyzed.validated and analyzed.indexable
    assert analyzed.domain_build is not None
    assert analyzed.domain_build.bundle is not None
    assert analyzed.domain_build.gaps == ()

    async def scenario() -> None:
        config = DatabaseConfig()
        config.database_url = postgres_url
        config.pool_size = 2
        config.max_overflow = 0
        manager = DatabaseManager(config)
        await manager.initialize()
        try:
            indexer = LedgerIndexer(
                lambda: AsyncLedgerUnitOfWork(database_manager=manager)
            )
            target = _bundle(
                "QM2-P0-003-20260716T142422Z-0114f35",
                _task("QM2-P0-003", None, 0),
                1,
            )
            await indexer.index_bundles(
                repository_id="quantmind-main",
                ref_commit="1" * 40,
                discovered=1,
                validated=1,
                bundles=(target,),
            )
            first = await indexer.index_plan(plan)
            assert first.indexed == 1 and first.replayed == 0
            second = await indexer.index_plan(plan)
            assert second.indexed == 0 and second.replayed == 1
            async with AsyncLedgerUnitOfWork(database_manager=manager) as uow:
                repository = uow.repository
                assert repository is not None
                assert await repository.get_task("QM2-P0-003L") is not None
                stored_run = await repository.get_run(run_id)
                assert stored_run == analyzed.domain_build.bundle.run
                changed_files = await repository.list_changed_files(run_id)
                assert len(changed_files) == 28
                assert all(item.path != analyzed.discovered.manifest_path for item in changed_files)
                artifacts = await repository.list_artifacts(run_id)
                assert any(
                    "ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7"
                    in item.path_or_uri
                    for item in artifacts
                )
        finally:
            await manager.close()

    asyncio.run(scenario())


def test_real_003lf_indexes_replays_after_containing_commit(
    postgres_url: str,
) -> None:
    run_id = "QM2-P0-003LF-20260716T153535Z-22461e0"
    manifest_path = (
        "docs/quantmind2/implementation/runs/2026/2026-07/"
        f"{run_id}/manifest.json"
    )
    committed = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{manifest_path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if committed.returncode != 0:
        pytest.skip("003LF verification requires its containing commit")
    plan = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    ).plan(run_id)
    analyzed = plan.runs[0]
    assert analyzed.validated and analyzed.indexable
    assert analyzed.domain_build is not None
    assert analyzed.domain_build.bundle is not None
    assert analyzed.domain_build.gaps == ()
    assert analyzed.evidence.consistent
    assert analyzed.evidence.warnings == ()

    async def scenario() -> None:
        config = DatabaseConfig()
        config.database_url = postgres_url
        config.pool_size = 2
        config.max_overflow = 0
        manager = DatabaseManager(config)
        await manager.initialize()
        try:
            indexer = LedgerIndexer(
                lambda: AsyncLedgerUnitOfWork(database_manager=manager)
            )
            first = await indexer.index_plan(plan)
            assert first.indexed == 1 and first.replayed == 0
            second = await indexer.index_plan(plan)
            assert second.indexed == 0 and second.replayed == 1
            async with AsyncLedgerUnitOfWork(database_manager=manager) as uow:
                repository = uow.repository
                assert repository is not None
                assert await repository.get_task("QM2-P0-003LF") is not None
                stored_run = await repository.get_run(run_id)
                assert stored_run == analyzed.domain_build.bundle.run
                changed_files = await repository.list_changed_files(run_id)
                assert changed_files
                assert all(
                    item.path != analyzed.discovered.manifest_path
                    for item in changed_files
                )
                assert any(item.path.endswith("/report.md") for item in changed_files)
        finally:
            await manager.close()

    asyncio.run(scenario())


def test_real_006f_correction_indexes_relationship_artifact_and_replays_exactly(
    postgres_url: str,
) -> None:
    run_id = "QM2-P0-006F-20260717T044608Z-8ad3e22"
    target_run_id = "QM2-P0-006-20260716T181959Z-07a3df9"
    manifest_path = (
        "docs/quantmind2/implementation/runs/2026/2026-07/"
        f"{run_id}/manifest.json"
    )
    committed = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{manifest_path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if committed.returncode != 0:
        pytest.skip("006F verification requires its containing commit")
    plan = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    ).plan(run_id)
    analyzed = plan.runs[0]
    assert analyzed.validated and analyzed.indexable
    assert analyzed.evidence.consistent and analyzed.evidence.warnings == ()
    assert analyzed.domain_build is not None
    assert analyzed.domain_build.gaps == ()
    assert analyzed.domain_build.bundle is not None
    bundle = analyzed.domain_build.bundle
    assert len(bundle.relationships) == 1
    assert bundle.relationships[0].relationship_type.value == "corrects"
    assert bundle.relationships[0].target_run_id == target_run_id
    assert any(
        item.artifact_type == "implementation_evidence_correction"
        for item in bundle.artifacts
    )

    async def scenario() -> None:
        config = DatabaseConfig()
        config.database_url = postgres_url
        config.pool_size = 2
        config.max_overflow = 0
        manager = DatabaseManager(config)
        await manager.initialize()
        try:
            indexer = LedgerIndexer(
                lambda: AsyncLedgerUnitOfWork(database_manager=manager)
            )
            target = _bundle(
                target_run_id,
                _task("QM2-P0-006", None, 0),
                1,
            )
            target_result = await indexer.index_bundles(
                repository_id="quantmind-main",
                ref_commit="8" * 40,
                discovered=1,
                validated=1,
                bundles=(target,),
            )
            assert target_result.indexed == 1

            first = await indexer.index_plan(plan)
            assert first.indexed == 1 and first.replayed == 0
            assert first.relationships == 1 and first.failed == 0
            second = await indexer.index_plan(plan)
            assert second.indexed == 0 and second.replayed == 1
            assert second.relationships == 1 and second.failed == 0

            async with AsyncLedgerUnitOfWork(database_manager=manager) as uow:
                repository = uow.repository
                assert repository is not None
                assert await repository.get_run(target_run_id) == target.run
                assert await repository.get_run(run_id) == bundle.run
                relationships = await repository.list_outgoing_relationships(run_id)
                assert tuple(relationships) == bundle.relationships
                artifacts = await repository.list_artifacts(run_id)
                correction_artifacts = [
                    item for item in artifacts
                    if item.artifact_type == "implementation_evidence_correction"
                ]
                assert len(correction_artifacts) == 1
                assert correction_artifacts[0].path_or_uri.endswith(
                    "QM2-P0-006-evidence-correction-v1.json"
                )
                changed_files = await repository.list_changed_files(run_id)
                assert changed_files
                assert all(item.path != manifest_path for item in changed_files)
        finally:
            await manager.close()

    asyncio.run(scenario())


def test_real_009f_correction_indexes_relationship_artifact_and_replays_exactly(
    postgres_url: str,
) -> None:
    run_id = "QM2-P0-009F-20260717T145233Z-a2a4168"
    target_run_id = "QM2-P0-009-20260717T141500Z-34dfa6e"
    manifest_path = (
        "docs/quantmind2/implementation/runs/2026/2026-07/"
        f"{run_id}/manifest.json"
    )
    committed = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{manifest_path}"],
        cwd=ROOT, capture_output=True, check=False,
    )
    if committed.returncode != 0:
        pytest.skip("009F verification requires its containing commit")
    plan = ImplementationRunPlanner(
        GitSnapshot(bind_repository("quantmind-main", ROOT))
    ).plan(run_id)
    analyzed = plan.runs[0]
    assert analyzed.validated and analyzed.indexable
    assert analyzed.evidence.consistent and analyzed.evidence.warnings == ()
    assert analyzed.domain_build is not None and analyzed.domain_build.gaps == ()
    bundle = analyzed.domain_build.bundle
    assert bundle is not None and len(bundle.relationships) == 1
    assert bundle.relationships[0].relationship_type.value == "corrects"
    assert bundle.relationships[0].target_run_id == target_run_id
    assert any(item.artifact_type == "implementation_changed_files_correction"
               for item in bundle.artifacts)

    async def scenario() -> None:
        config = DatabaseConfig(); config.database_url = postgres_url
        config.pool_size = 2; config.max_overflow = 0
        manager = DatabaseManager(config); await manager.initialize()
        try:
            indexer = LedgerIndexer(lambda: AsyncLedgerUnitOfWork(database_manager=manager))
            target = _bundle(target_run_id, _task("QM2-P0-009", None, 0), 1)
            target_result = await indexer.index_bundles(
                repository_id="quantmind-main", ref_commit="a" * 40,
                discovered=1, validated=1, bundles=(target,),
            )
            assert target_result.indexed == 1
            first = await indexer.index_plan(plan)
            assert first.indexed == 1 and first.replayed == 0 and first.relationships == 1
            second = await indexer.index_plan(plan)
            assert second.indexed == 0 and second.replayed == 1 and second.relationships == 1
            async with AsyncLedgerUnitOfWork(database_manager=manager) as uow:
                repository = uow.repository; assert repository is not None
                assert await repository.get_run(target_run_id) == target.run
                assert await repository.get_run(run_id) == bundle.run
                assert tuple(await repository.list_outgoing_relationships(run_id)) == bundle.relationships
                artifacts = await repository.list_artifacts(run_id)
                assert len([item for item in artifacts if item.artifact_type ==
                            "implementation_changed_files_correction"]) == 1
                changed_files = await repository.list_changed_files(run_id)
                assert changed_files and all(item.path != manifest_path for item in changed_files)
        finally:
            await manager.close()

    asyncio.run(scenario())
