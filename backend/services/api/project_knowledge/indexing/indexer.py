"""Deterministic multi-pass indexing through the A3 Repository and UoW."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any
from backend.services.engine.project_knowledge.domain.repository_errors import LedgerRepositoryError
from backend.services.engine.project_knowledge.domain.repository_queries import RunQuery

from .errors import DomainBundleError, LedgerIndexConflictError
from .models import (
    BackfillPlan,
    BackfillResult,
    ImplementationDomainBundle,
    IndexRunResult,
    LedgerStatus,
)


UnitOfWorkFactory = Callable[[], Any]


class LedgerIndexer:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    @staticmethod
    def require_indexable(plan: BackfillPlan) -> tuple[ImplementationDomainBundle, ...]:
        inconsistent = [run.discovered.run_id for run in plan.runs if not run.validated]
        gaps = [run.discovered.run_id for run in plan.runs if run.validated and not run.indexable]
        if inconsistent:
            raise DomainBundleError(
                "mandatory consistency checks failed before indexing",
                run_id=inconsistent[0],
            )
        if gaps:
            raise DomainBundleError(
                "Manifest evidence cannot construct a complete Domain Bundle",
                run_id=gaps[0],
            )
        return tuple(run.domain_build.bundle for run in plan.runs if run.domain_build and run.domain_build.bundle)

    @staticmethod
    def _ordered_tasks(bundles: Iterable[ImplementationDomainBundle]):
        tasks = {}
        for bundle in bundles:
            existing = tasks.get(bundle.task.task_id)
            if existing is not None and existing != bundle.task:
                raise LedgerIndexConflictError(
                    "same Task ID has different definitions", run_id=bundle.run.implementation_run_id
                )
            tasks[bundle.task.task_id] = bundle.task
        ordered = []
        pending = dict(tasks)
        while pending:
            ready = sorted(
                (
                    task
                    for task in pending.values()
                    if task.parent_task_id is None
                    or task.parent_task_id not in tasks
                    or task.parent_task_id not in pending
                ),
                key=lambda task: (task.created_at, task.task_id),
            )
            if not ready:
                raise LedgerIndexConflictError("Task parent graph contains a cycle")
            for task in ready:
                ordered.append(task)
                pending.pop(task.task_id)
        return tuple(ordered)

    async def index_plan(self, plan: BackfillPlan) -> BackfillResult:
        return await self.index_bundles(
            repository_id=plan.repository_id,
            ref_commit=plan.ref_commit,
            discovered=plan.discovered_count,
            validated=plan.validated_count,
            bundles=self.require_indexable(plan),
        )

    async def index_bundles(
        self,
        *,
        repository_id: str,
        ref_commit: str,
        discovered: int,
        validated: int,
        bundles: tuple[ImplementationDomainBundle, ...],
    ) -> BackfillResult:
        results: list[IndexRunResult] = []
        indexed = replayed = relationship_count = 0
        try:
            for task in self._ordered_tasks(bundles):
                async with self._uow_factory() as uow:
                    assert uow.repository is not None
                    await uow.repository.create_task(task)
                    await uow.commit()

            for bundle in bundles:
                async with self._uow_factory() as uow:
                    assert uow.repository is not None
                    existing = await uow.repository.get_run(bundle.run.implementation_run_id)
                    await uow.repository.record_run_details_atomic(
                        bundle.run,
                        changed_files=bundle.changed_files,
                        changed_symbols=bundle.changed_symbols,
                        tests=bundle.tests,
                        artifacts=bundle.artifacts,
                        component_refs=bundle.component_refs,
                        adr_refs=bundle.adr_refs,
                        limitations=bundle.limitations,
                        recommended_tasks=bundle.recommended_tasks,
                    )
                    await uow.commit()
                status = "replayed" if existing == bundle.run else "indexed"
                replayed += status == "replayed"
                indexed += status == "indexed"
                results.append(IndexRunResult(bundle.run.implementation_run_id, status))

            relationships = sorted(
                (relationship for bundle in bundles for relationship in bundle.relationships),
                key=lambda item: (item.created_at, item.relationship_id),
            )
            for relationship in relationships:
                async with self._uow_factory() as uow:
                    assert uow.repository is not None
                    await uow.repository.add_relationship(relationship)
                    await uow.commit()
                relationship_count += 1
        except LedgerRepositoryError as exc:
            raise LedgerIndexConflictError("Ledger rejected immutable indexed evidence") from exc

        return BackfillResult(
            repository_id,
            ref_commit,
            discovered,
            validated,
            indexed,
            replayed,
            0,
            0,
            relationship_count,
            tuple(results),
        )

    async def status(self, plan: BackfillPlan) -> LedgerStatus:
        database_runs = []
        offset = 0
        while True:
            async with self._uow_factory() as uow:
                assert uow.repository is not None
                page = await uow.repository.list_runs(RunQuery(limit=200, offset=offset))
            database_runs.extend(
                run for run in page.items if run.repository_root == plan.repository_id
            )
            offset += len(page.items)
            if offset >= page.total:
                break
        by_id = {run.implementation_run_id: run for run in database_runs}
        git_ids = tuple(run.discovered.run_id for run in plan.runs)
        pending: list[str] = []
        replay: list[str] = []
        conflicts: list[str] = []
        for analyzed in plan.runs:
            run_id = analyzed.discovered.run_id
            stored = by_id.get(run_id)
            expected = analyzed.domain_build.resolved_run.run if analyzed.domain_build and analyzed.domain_build.resolved_run else None
            if not analyzed.validated or not analyzed.indexable:
                conflicts.append(run_id)
            elif stored is None:
                pending.append(run_id)
            elif stored == expected:
                replay.append(run_id)
            else:
                conflicts.append(run_id)
        database_ids = tuple(sorted(by_id))
        database_only = tuple(sorted(set(database_ids) - set(git_ids)))
        git_only = tuple(sorted(set(git_ids) - set(database_ids)))
        return LedgerStatus(
            plan.repository_id,
            plan.ref_commit,
            git_ids,
            database_ids,
            tuple(pending),
            tuple(replay),
            tuple(conflicts),
            database_only,
            git_only,
        )
