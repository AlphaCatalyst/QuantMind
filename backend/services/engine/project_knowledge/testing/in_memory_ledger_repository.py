"""Pure in-memory test double for Ledger repository contract verification.

This class is intentionally synchronous, process-local, and non-durable. Its
atomic batch behavior validates all-or-nothing contract semantics only; it is
not evidence of a database transaction or production Repository.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Hashable, Iterable, Sequence, TypeVar

from ..domain.enums import (
    CanonicalStatus,
    ConsistencyStatus,
    ImplementationRunStatus,
    ImplementationTaskStatus,
    RunRelationshipType,
)
from ..domain.models import (
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
from ..domain.repository_errors import (
    DuplicateChildEntityError,
    ImmutableEntityConflictError,
    InvalidStateTransitionError,
    OptimisticConcurrencyError,
    RelationshipNotFoundError,
    RunNotFoundError,
    RunRelationshipCycleError,
    TaskNotFoundError,
)
from ..domain.repository_queries import HistoryQuery, Page, RunQuery, SortOrder, TaskQuery
from ..domain.validators import validate_identifier


_T = TypeVar("_T")


_TASK_TRANSITIONS = {
    ImplementationTaskStatus.PLANNED: {
        ImplementationTaskStatus.READY,
        ImplementationTaskStatus.RUNNING,
        ImplementationTaskStatus.BLOCKED,
        ImplementationTaskStatus.CANCELLED,
    },
    ImplementationTaskStatus.READY: {
        ImplementationTaskStatus.RUNNING,
        ImplementationTaskStatus.BLOCKED,
        ImplementationTaskStatus.CANCELLED,
    },
    ImplementationTaskStatus.RUNNING: {
        ImplementationTaskStatus.COMPLETED,
        ImplementationTaskStatus.PARTIAL,
        ImplementationTaskStatus.BLOCKED,
        ImplementationTaskStatus.CANCELLED,
    },
    ImplementationTaskStatus.BLOCKED: {
        ImplementationTaskStatus.READY,
        ImplementationTaskStatus.RUNNING,
        ImplementationTaskStatus.CANCELLED,
    },
    ImplementationTaskStatus.COMPLETED: set(),
    ImplementationTaskStatus.PARTIAL: set(),
    ImplementationTaskStatus.CANCELLED: set(),
}

_CANONICAL_TRANSITIONS = {
    CanonicalStatus.NONCANONICAL: {
        CanonicalStatus.CANDIDATE,
        CanonicalStatus.CANONICAL,
        CanonicalStatus.REJECTED,
    },
    CanonicalStatus.CANDIDATE: {
        CanonicalStatus.NONCANONICAL,
        CanonicalStatus.CANONICAL,
        CanonicalStatus.REJECTED,
    },
    CanonicalStatus.CANONICAL: {
        CanonicalStatus.NONCANONICAL,
        CanonicalStatus.REJECTED,
    },
    CanonicalStatus.REJECTED: {CanonicalStatus.NONCANONICAL},
}


class InMemoryLedgerRepository:
    """Instance-local test double implementing every Ledger Protocol."""

    def __init__(self) -> None:
        self._tasks: dict[str, ImplementationTask] = {}
        self._task_versions: dict[str, int] = {}
        self._runs: dict[str, ImplementationRun] = {}
        self._run_versions: dict[str, int] = {}
        self._relationships: dict[str, RunRelationship] = {}
        self._changed_files: dict[Hashable, ChangedFile] = {}
        self._changed_symbols: dict[Hashable, ChangedSymbol] = {}
        self._tests: dict[Hashable, TestExecution] = {}
        self._artifacts: dict[Hashable, ImplementationArtifact] = {}
        self._component_refs: dict[Hashable, ComponentReference] = {}
        self._adr_refs: dict[Hashable, ArchitectureDecisionReference] = {}
        self._limitations: dict[Hashable, Limitation] = {}
        self._recommended_tasks: dict[Hashable, RecommendedTask] = {}

    @property
    def task_repository(self) -> "InMemoryLedgerRepository":
        return self

    @property
    def run_repository(self) -> "InMemoryLedgerRepository":
        return self

    @property
    def relationship_repository(self) -> "InMemoryLedgerRepository":
        return self

    @property
    def detail_repository(self) -> "InMemoryLedgerRepository":
        return self

    @staticmethod
    def _store_immutable(
        store: dict[Hashable, _T],
        key: Hashable,
        item: _T,
        *,
        entity_type: str,
        entity_id: str,
    ) -> _T:
        existing = store.get(key)
        if existing is None:
            store[key] = item
            return item
        if existing == item:
            return existing
        raise ImmutableEntityConflictError(
            "same identity has different immutable content",
            entity_type=entity_type,
            entity_id=entity_id,
        )

    @staticmethod
    def _check_version(
        versions: dict[str, int],
        entity_id: str,
        expected_version: int,
        *,
        entity_type: str,
    ) -> None:
        actual = versions[entity_id]
        if not isinstance(expected_version, int) or isinstance(expected_version, bool):
            raise OptimisticConcurrencyError(
                entity_type=entity_type,
                entity_id=entity_id,
                expected_version=None,
                actual_version=actual,
            )
        if expected_version != actual:
            raise OptimisticConcurrencyError(
                entity_type=entity_type,
                entity_id=entity_id,
                expected_version=expected_version,
                actual_version=actual,
            )

    def create_task(self, task: ImplementationTask) -> ImplementationTask:
        result = self._store_immutable(
            self._tasks,
            task.task_id,
            task,
            entity_type="task",
            entity_id=task.task_id,
        )
        self._task_versions.setdefault(task.task_id, 1)
        return result

    def get_task(self, task_id: str) -> ImplementationTask | None:
        return self._tasks.get(validate_identifier(task_id, field="task_id"))

    def require_task(self, task_id: str) -> ImplementationTask:
        normalized = validate_identifier(task_id, field="task_id")
        task = self._tasks.get(normalized)
        if task is None:
            raise TaskNotFoundError("task does not exist", entity_type="task", entity_id=normalized)
        return task

    def get_task_version(self, task_id: str) -> int:
        task = self.require_task(task_id)
        return self._task_versions[task.task_id]

    def list_tasks(self, query: TaskQuery) -> Page[ImplementationTask]:
        items = list(self._tasks.values())
        if query.status is not None:
            items = [item for item in items if item.status is query.status]
        if query.parent_task_id is not None:
            items = [item for item in items if item.parent_task_id == query.parent_task_id]
        items.sort(key=lambda item: (item.created_at, item.task_id))
        total = len(items)
        return Page.from_items(
            items[query.offset : query.offset + query.limit],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    def update_task_status(
        self,
        task_id: str,
        new_status: ImplementationTaskStatus,
        expected_version: int,
    ) -> ImplementationTask:
        current = self.require_task(task_id)
        self._check_version(
            self._task_versions,
            current.task_id,
            expected_version,
            entity_type="task",
        )
        try:
            status = ImplementationTaskStatus(new_status)
        except (TypeError, ValueError) as exc:
            raise InvalidStateTransitionError(
                "task status is unsupported", entity_type="task", entity_id=current.task_id
            ) from exc
        if status is current.status:
            return current
        if status not in _TASK_TRANSITIONS[current.status]:
            raise InvalidStateTransitionError(
                f"task transition {current.status.value} -> {status.value} is forbidden",
                entity_type="task",
                entity_id=current.task_id,
            )
        updated = replace(current, status=status)
        self._tasks[current.task_id] = updated
        self._task_versions[current.task_id] += 1
        return updated

    def create_run(self, run: ImplementationRun) -> ImplementationRun:
        self.require_task(run.task_id)
        result = self._store_immutable(
            self._runs,
            run.implementation_run_id,
            run,
            entity_type="run",
            entity_id=run.implementation_run_id,
        )
        self._run_versions.setdefault(run.implementation_run_id, 1)
        return result

    def get_run(self, run_id: str) -> ImplementationRun | None:
        return self._runs.get(validate_identifier(run_id, field="run_id"))

    def require_run(self, run_id: str) -> ImplementationRun:
        normalized = validate_identifier(run_id, field="run_id")
        run = self._runs.get(normalized)
        if run is None:
            raise RunNotFoundError("run does not exist", entity_type="run", entity_id=normalized)
        return run

    def get_run_version(self, run_id: str) -> int:
        run = self.require_run(run_id)
        return self._run_versions[run.implementation_run_id]

    def list_runs(self, query: RunQuery) -> Page[ImplementationRun]:
        items = list(self._runs.values())
        if query.task_id is not None:
            items = [item for item in items if item.task_id == query.task_id]
        if query.task_status is not None:
            items = [item for item in items if item.task_status is query.task_status]
        if query.canonical_status is not None:
            items = [item for item in items if item.canonical_status is query.canonical_status]
        if query.consistency_status is not None:
            items = [item for item in items if item.consistency_status is query.consistency_status]
        if query.component_id is not None:
            run_ids = {
                item.implementation_run_id
                for item in self._component_refs.values()
                if item.component_id == query.component_id
            }
            items = [item for item in items if item.implementation_run_id in run_ids]
        if query.adr_id is not None:
            run_ids = {
                item.implementation_run_id
                for item in self._adr_refs.values()
                if item.adr_id == query.adr_id
            }
            items = [item for item in items if item.implementation_run_id in run_ids]
        if query.file_path is not None:
            run_ids = {
                item.implementation_run_id
                for item in self._changed_files.values()
                if query.file_path in {item.path, item.previous_path}
            }
            items = [item for item in items if item.implementation_run_id in run_ids]
        if query.started_from is not None:
            items = [item for item in items if item.started_at >= query.started_from]
        if query.started_to is not None:
            items = [item for item in items if item.started_at <= query.started_to]
        items.sort(
            key=lambda item: (item.started_at, item.implementation_run_id),
            reverse=query.sort_order is SortOrder.DESC,
        )
        total = len(items)
        return Page.from_items(
            items[query.offset : query.offset + query.limit],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    @staticmethod
    def _run_identity(run: ImplementationRun) -> tuple[object, ...]:
        return (
            run.implementation_run_id,
            run.task_id,
            run.repository_root,
            run.branch,
            run.base_commit,
            run.workspace_dirty_before,
            run.started_at,
            run.agent_type,
            run.manifest_schema_version,
            run.manifest_path,
            run.report_path,
        )

    def finalize_run(
        self,
        run_id: str,
        terminal_run: ImplementationRun,
        expected_version: int,
    ) -> ImplementationRun:
        current = self.require_run(run_id)
        self._check_version(
            self._run_versions,
            current.implementation_run_id,
            expected_version,
            entity_type="run",
        )
        if current.task_status is not ImplementationRunStatus.RUNNING:
            raise InvalidStateTransitionError(
                "only a running run may be finalized",
                entity_type="run",
                entity_id=current.implementation_run_id,
            )
        if terminal_run.task_status is ImplementationRunStatus.RUNNING:
            raise InvalidStateTransitionError(
                "terminal_run must have a terminal status",
                entity_type="run",
                entity_id=current.implementation_run_id,
            )
        if self._run_identity(current) != self._run_identity(terminal_run):
            raise ImmutableEntityConflictError(
                "finalization changes immutable run identity",
                entity_type="run",
                entity_id=current.implementation_run_id,
            )
        if terminal_run.canonical_status is not current.canonical_status:
            raise InvalidStateTransitionError(
                "finalize_run cannot change canonical status",
                entity_type="run",
                entity_id=current.implementation_run_id,
            )
        self._runs[current.implementation_run_id] = terminal_run
        self._run_versions[current.implementation_run_id] += 1
        return terminal_run

    def set_consistency_status(
        self,
        run_id: str,
        status: ConsistencyStatus,
        expected_version: int,
    ) -> ImplementationRun:
        current = self.require_run(run_id)
        self._check_version(
            self._run_versions,
            current.implementation_run_id,
            expected_version,
            entity_type="run",
        )
        try:
            normalized = ConsistencyStatus(status)
        except (TypeError, ValueError) as exc:
            raise InvalidStateTransitionError(
                "consistency status is unsupported",
                entity_type="run",
                entity_id=current.implementation_run_id,
            ) from exc
        if normalized is current.consistency_status:
            return current
        try:
            updated = replace(current, consistency_status=normalized)
        except ValueError as exc:
            raise InvalidStateTransitionError(
                "consistency transition violates run invariants",
                entity_type="run",
                entity_id=current.implementation_run_id,
            ) from exc
        self._runs[current.implementation_run_id] = updated
        self._run_versions[current.implementation_run_id] += 1
        return updated

    def set_canonical_status(
        self,
        run_id: str,
        status: CanonicalStatus,
        expected_version: int,
    ) -> ImplementationRun:
        current = self.require_run(run_id)
        self._check_version(
            self._run_versions,
            current.implementation_run_id,
            expected_version,
            entity_type="run",
        )
        try:
            normalized = CanonicalStatus(status)
        except (TypeError, ValueError) as exc:
            raise InvalidStateTransitionError(
                "canonical status is unsupported",
                entity_type="run",
                entity_id=current.implementation_run_id,
            ) from exc
        if normalized is current.canonical_status:
            return current
        if normalized not in _CANONICAL_TRANSITIONS[current.canonical_status]:
            raise InvalidStateTransitionError(
                "canonical status transition is forbidden",
                entity_type="run",
                entity_id=current.implementation_run_id,
            )
        try:
            updated = replace(current, canonical_status=normalized)
        except ValueError as exc:
            raise InvalidStateTransitionError(
                "canonical transition violates run invariants",
                entity_type="run",
                entity_id=current.implementation_run_id,
            ) from exc
        self._runs[current.implementation_run_id] = updated
        self._run_versions[current.implementation_run_id] += 1
        return updated

    def add_relationship(self, relationship: RunRelationship) -> RunRelationship:
        self.require_run(relationship.source_run_id)
        self.require_run(relationship.target_run_id)
        existing = self._relationships.get(relationship.relationship_id)
        if existing is not None:
            if existing == relationship:
                return existing
            raise ImmutableEntityConflictError(
                "relationship ID has different immutable content",
                entity_type="relationship",
                entity_id=relationship.relationship_id,
            )
        for item in self._relationships.values():
            if (
                item.source_run_id,
                item.target_run_id,
                item.relationship_type,
            ) == (
                relationship.source_run_id,
                relationship.target_run_id,
                relationship.relationship_type,
            ):
                raise DuplicateChildEntityError(
                    "relationship natural key already exists",
                    entity_type="relationship",
                    entity_id=relationship.relationship_id,
                )
        if self.would_create_cycle(relationship.source_run_id, relationship.target_run_id):
            raise RunRelationshipCycleError(
                f"edge {relationship.source_run_id} -> {relationship.target_run_id} creates a cycle",
                entity_type="relationship",
                entity_id=relationship.relationship_id,
            )
        self._relationships[relationship.relationship_id] = relationship
        return relationship

    def get_relationship(self, relationship_id: str) -> RunRelationship | None:
        normalized = validate_identifier(relationship_id, field="relationship_id")
        return self._relationships.get(normalized)

    def require_relationship(self, relationship_id: str) -> RunRelationship:
        normalized = validate_identifier(relationship_id, field="relationship_id")
        relationship = self._relationships.get(normalized)
        if relationship is None:
            raise RelationshipNotFoundError(
                "relationship does not exist",
                entity_type="relationship",
                entity_id=normalized,
            )
        return relationship

    def list_outgoing_relationships(self, run_id: str) -> tuple[RunRelationship, ...]:
        normalized = self.require_run(run_id).implementation_run_id
        return tuple(
            item for item in self._relationships.values() if item.source_run_id == normalized
        )

    def list_incoming_relationships(self, run_id: str) -> tuple[RunRelationship, ...]:
        normalized = self.require_run(run_id).implementation_run_id
        return tuple(
            item for item in self._relationships.values() if item.target_run_id == normalized
        )

    def relationship_exists(
        self,
        source_run_id: str,
        target_run_id: str,
        relationship_type: RunRelationshipType,
    ) -> bool:
        source = validate_identifier(source_run_id, field="source_run_id")
        target = validate_identifier(target_run_id, field="target_run_id")
        kind = RunRelationshipType(relationship_type)
        return any(
            (item.source_run_id, item.target_run_id, item.relationship_type)
            == (source, target, kind)
            for item in self._relationships.values()
        )

    def would_create_cycle(self, source_run_id: str, target_run_id: str) -> bool:
        source = validate_identifier(source_run_id, field="source_run_id")
        target = validate_identifier(target_run_id, field="target_run_id")
        if source == target:
            return True
        adjacency: dict[str, list[str]] = {}
        for item in self._relationships.values():
            adjacency.setdefault(item.source_run_id, []).append(item.target_run_id)
        pending = [target]
        visited: set[str] = set()
        while pending:
            node = pending.pop()
            if node == source:
                return True
            if node in visited:
                continue
            visited.add(node)
            pending.extend(adjacency.get(node, ()))
        return False

    def _require_parent_run(self, run_id: str) -> None:
        self.require_run(run_id)

    def _append_child(
        self,
        store: dict[Hashable, _T],
        key: Hashable,
        item: _T,
        *,
        entity_type: str,
        entity_id: str,
    ) -> _T:
        self._require_parent_run(getattr(item, "implementation_run_id"))
        return self._store_immutable(
            store,
            key,
            item,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def append_changed_file(self, item: ChangedFile) -> ChangedFile:
        key = (item.implementation_run_id, item.path, item.change_type)
        return self._append_child(
            self._changed_files,
            key,
            item,
            entity_type="changed_file",
            entity_id=item.path,
        )

    def append_changed_symbol(self, item: ChangedSymbol) -> ChangedSymbol:
        key = (item.implementation_run_id, item.file_path, item.qualified_name)
        return self._append_child(
            self._changed_symbols,
            key,
            item,
            entity_type="changed_symbol",
            entity_id=item.qualified_name,
        )

    def append_test_execution(self, item: TestExecution) -> TestExecution:
        key = (item.implementation_run_id, item.test_execution_id)
        return self._append_child(
            self._tests,
            key,
            item,
            entity_type="test_execution",
            entity_id=item.test_execution_id,
        )

    def append_artifact(self, item: ImplementationArtifact) -> ImplementationArtifact:
        key = (item.implementation_run_id, item.artifact_id)
        return self._append_child(
            self._artifacts,
            key,
            item,
            entity_type="artifact",
            entity_id=item.artifact_id,
        )

    def append_component_reference(self, item: ComponentReference) -> ComponentReference:
        key = (item.implementation_run_id, item.component_id)
        return self._append_child(
            self._component_refs,
            key,
            item,
            entity_type="component_reference",
            entity_id=item.component_id,
        )

    def append_adr_reference(
        self, item: ArchitectureDecisionReference
    ) -> ArchitectureDecisionReference:
        key = (item.implementation_run_id, item.adr_id)
        return self._append_child(
            self._adr_refs,
            key,
            item,
            entity_type="adr_reference",
            entity_id=item.adr_id,
        )

    def append_limitation(self, item: Limitation) -> Limitation:
        key = (item.implementation_run_id, item.limitation_id)
        return self._append_child(
            self._limitations,
            key,
            item,
            entity_type="limitation",
            entity_id=item.limitation_id,
        )

    def append_recommended_task(self, item: RecommendedTask) -> RecommendedTask:
        key = (item.implementation_run_id, item.recommendation_id)
        return self._append_child(
            self._recommended_tasks,
            key,
            item,
            entity_type="recommended_task",
            entity_id=item.recommendation_id,
        )

    def _list_children(self, store: dict[Hashable, _T], run_id: str) -> tuple[_T, ...]:
        normalized = self.require_run(run_id).implementation_run_id
        return tuple(
            item
            for item in store.values()
            if getattr(item, "implementation_run_id") == normalized
        )

    def list_changed_files(self, run_id: str) -> tuple[ChangedFile, ...]:
        return self._list_children(self._changed_files, run_id)

    def list_changed_symbols(self, run_id: str) -> tuple[ChangedSymbol, ...]:
        return self._list_children(self._changed_symbols, run_id)

    def list_test_executions(self, run_id: str) -> tuple[TestExecution, ...]:
        return self._list_children(self._tests, run_id)

    def list_artifacts(self, run_id: str) -> tuple[ImplementationArtifact, ...]:
        return self._list_children(self._artifacts, run_id)

    def list_component_references(self, run_id: str) -> tuple[ComponentReference, ...]:
        return self._list_children(self._component_refs, run_id)

    def list_adr_references(
        self, run_id: str
    ) -> tuple[ArchitectureDecisionReference, ...]:
        return self._list_children(self._adr_refs, run_id)

    def list_limitations(self, run_id: str) -> tuple[Limitation, ...]:
        return self._list_children(self._limitations, run_id)

    def list_recommended_tasks(self, run_id: str) -> tuple[RecommendedTask, ...]:
        return self._list_children(self._recommended_tasks, run_id)

    def list_run_history(self, query: HistoryQuery) -> Page[ImplementationRun]:
        run_ids: set[str]
        if query.path is not None:
            run_ids = {
                item.implementation_run_id
                for item in self._changed_files.values()
                if query.path in {item.path, item.previous_path}
            }
        elif query.component_id is not None:
            run_ids = {
                item.implementation_run_id
                for item in self._component_refs.values()
                if item.component_id == query.component_id
            }
        else:
            run_ids = {
                item.implementation_run_id
                for item in self._adr_refs.values()
                if item.adr_id == query.adr_id
            }
        items = [item for item in self._runs.values() if item.implementation_run_id in run_ids]
        items.sort(key=lambda item: (item.started_at, item.implementation_run_id))
        total = len(items)
        return Page.from_items(
            items[query.offset : query.offset + query.limit],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    def _copy_for_atomic_write(self) -> "InMemoryLedgerRepository":
        clone = InMemoryLedgerRepository()
        for name in (
            "_tasks",
            "_task_versions",
            "_runs",
            "_run_versions",
            "_relationships",
            "_changed_files",
            "_changed_symbols",
            "_tests",
            "_artifacts",
            "_component_refs",
            "_adr_refs",
            "_limitations",
            "_recommended_tasks",
        ):
            setattr(clone, name, dict(getattr(self, name)))
        return clone

    def _adopt_atomic_write(self, clone: "InMemoryLedgerRepository") -> None:
        for name in (
            "_tasks",
            "_task_versions",
            "_runs",
            "_run_versions",
            "_relationships",
            "_changed_files",
            "_changed_symbols",
            "_tests",
            "_artifacts",
            "_component_refs",
            "_adr_refs",
            "_limitations",
            "_recommended_tasks",
        ):
            setattr(self, name, getattr(clone, name))

    def record_run_details_atomic(
        self,
        run: ImplementationRun,
        *,
        changed_files: Sequence[ChangedFile] = (),
        changed_symbols: Sequence[ChangedSymbol] = (),
        tests: Sequence[TestExecution] = (),
        artifacts: Sequence[ImplementationArtifact] = (),
        component_refs: Sequence[ComponentReference] = (),
        adr_refs: Sequence[ArchitectureDecisionReference] = (),
        limitations: Sequence[Limitation] = (),
        recommended_tasks: Sequence[RecommendedTask] = (),
    ) -> ImplementationRun:
        clone = self._copy_for_atomic_write()
        stored_run = clone.create_run(run)
        operations: tuple[tuple[Callable[[_T], _T], Iterable[_T]], ...] = (
            (clone.append_changed_file, changed_files),
            (clone.append_changed_symbol, changed_symbols),
            (clone.append_test_execution, tests),
            (clone.append_artifact, artifacts),
            (clone.append_component_reference, component_refs),
            (clone.append_adr_reference, adr_refs),
            (clone.append_limitation, limitations),
            (clone.append_recommended_task, recommended_tasks),
        )
        for operation, items in operations:
            for item in items:
                operation(item)
        self._adopt_atomic_write(clone)
        return stored_run
