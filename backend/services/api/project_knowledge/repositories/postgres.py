"""Async SQLAlchemy/PostgreSQL implementation of Ledger Repository v1."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Sequence, TypeVar

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.project_knowledge.persistence.mappers import (
    LedgerMapperError,
    architecture_decision_reference_from_record,
    architecture_decision_reference_to_record,
    changed_file_from_record,
    changed_file_to_record,
    changed_symbol_from_record,
    changed_symbol_to_record,
    component_reference_from_record,
    component_reference_to_record,
    implementation_artifact_from_record,
    implementation_artifact_to_record,
    implementation_run_from_record,
    implementation_run_to_record,
    implementation_task_from_record,
    implementation_task_to_record,
    limitation_from_record,
    limitation_to_record,
    recommended_task_from_record,
    recommended_task_to_record,
    run_relationship_from_record,
    run_relationship_to_record,
    test_execution_from_record,
    test_execution_to_record,
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
    CanonicalStatus,
    ConsistencyStatus,
    ImplementationRunStatus,
    ImplementationTaskStatus,
    RunRelationshipType,
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
from backend.services.engine.project_knowledge.domain.repository_errors import (
    DuplicateChildEntityError,
    ImmutableEntityConflictError,
    InvalidStateTransitionError,
    OptimisticConcurrencyError,
    RelationshipNotFoundError,
    RunNotFoundError,
    RunRelationshipCycleError,
    TaskNotFoundError,
)
from backend.services.engine.project_knowledge.domain.repository_queries import (
    HistoryQuery,
    Page,
    RunQuery,
    SortOrder,
    TaskQuery,
)
from backend.services.engine.project_knowledge.domain.validators import validate_identifier

from .errors import (
    LedgerConstraintViolationError,
    LedgerPersistenceUnavailableError,
)


GRAPH_ADVISORY_LOCK_KEY = 6550840103452820112
_T = TypeVar("_T")
_R = TypeVar("_R")

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


def _constraint_name(exc: IntegrityError) -> str | None:
    """Extract a driver constraint name without parsing localized messages."""
    pending = [getattr(exc, "orig", None)]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        diagnostic = getattr(current, "diag", None)
        name = getattr(diagnostic, "constraint_name", None) if diagnostic else None
        name = name or getattr(current, "constraint_name", None)
        if name:
            return str(name)
        pending.extend((getattr(current, "__cause__", None), getattr(current, "__context__", None)))
    return None


class PostgresLedgerRepository:
    """One transaction-neutral Repository bound to one injected Session."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        write_guard: Callable[[], None] | None = None,
    ) -> None:
        if not isinstance(session, AsyncSession):
            raise TypeError("PostgresLedgerRepository requires an AsyncSession")
        self._session = session
        self._write_guard = write_guard

    @property
    def task_repository(self) -> "PostgresLedgerRepository":
        return self

    @property
    def run_repository(self) -> "PostgresLedgerRepository":
        return self

    @property
    def relationship_repository(self) -> "PostgresLedgerRepository":
        return self

    @property
    def detail_repository(self) -> "PostgresLedgerRepository":
        return self

    def _writable(self) -> None:
        if self._write_guard is not None:
            self._write_guard()

    async def _execute(self, statement):  # noqa: ANN001, ANN202
        try:
            return await self._session.execute(statement)
        except IntegrityError:
            raise
        except (DBAPIError, SQLAlchemyError) as exc:
            raise LedgerPersistenceUnavailableError(
                "Ledger persistence operation failed", entity_type="ledger"
            ) from exc

    @staticmethod
    def _mapped(mapper: Callable[[_R], _T], record: _R, entity_type: str, entity_id: str) -> _T:
        try:
            return mapper(record)
        except LedgerMapperError as exc:
            raise LedgerConstraintViolationError(
                "stored row cannot be reconstructed",
                entity_type=entity_type,
                entity_id=entity_id,
                mapper_error_code=exc.error_code,
            ) from exc

    async def _scalar_record(self, statement):  # noqa: ANN001, ANN202
        return (await self._execute(statement)).scalar_one_or_none()

    async def _insert_immutable(
        self,
        *,
        item: _T,
        record: Any,
        lookup,
        mapper: Callable[[Any], _T],
        entity_type: str,
        entity_id: str,
        identity_constraints: set[str],
    ) -> _T:
        existing_record = await self._scalar_record(lookup)
        if existing_record is not None:
            existing = self._mapped(mapper, existing_record, entity_type, entity_id)
            if existing == item:
                return existing
            raise ImmutableEntityConflictError(
                "same identity has different immutable content",
                entity_type=entity_type,
                entity_id=entity_id,
            )
        try:
            async with self._session.begin_nested():
                self._session.add(record)
                await self._session.flush()
        except IntegrityError as exc:
            constraint = _constraint_name(exc)
            if constraint not in identity_constraints:
                raise LedgerConstraintViolationError(
                    "database constraint rejected Ledger write",
                    entity_type=entity_type,
                    entity_id=entity_id,
                ) from exc
            existing_record = await self._scalar_record(lookup)
            if existing_record is None:
                raise ImmutableEntityConflictError(
                    "same technical identity belongs to different immutable content",
                    entity_type=entity_type,
                    entity_id=entity_id,
                ) from exc
            existing = self._mapped(mapper, existing_record, entity_type, entity_id)
            if existing == item:
                return existing
            raise ImmutableEntityConflictError(
                "same identity has different immutable content",
                entity_type=entity_type,
                entity_id=entity_id,
            ) from exc
        return item

    @staticmethod
    def _validate_expected(entity_type: str, entity_id: str, expected: int, actual: int) -> None:
        if not isinstance(expected, int) or isinstance(expected, bool) or expected != actual:
            raise OptimisticConcurrencyError(
                entity_type=entity_type,
                entity_id=entity_id,
                expected_version=expected if isinstance(expected, int) and not isinstance(expected, bool) else None,
                actual_version=actual,
            )

    async def create_task(self, task: ImplementationTask) -> ImplementationTask:
        self._writable()
        if task.parent_task_id is not None:
            await self.require_task(task.parent_task_id)
        return await self._insert_immutable(
            item=task,
            record=implementation_task_to_record(task),
            lookup=select(ImplementationTaskRecord).where(ImplementationTaskRecord.task_id == task.task_id),
            mapper=implementation_task_from_record,
            entity_type="task",
            entity_id=task.task_id,
            identity_constraints={"pk_qm2_tasks"},
        )

    async def get_task(self, task_id: str) -> ImplementationTask | None:
        normalized = validate_identifier(task_id, field="task_id")
        record = await self._scalar_record(select(ImplementationTaskRecord).where(ImplementationTaskRecord.task_id == normalized))
        return None if record is None else self._mapped(implementation_task_from_record, record, "task", normalized)

    async def require_task(self, task_id: str) -> ImplementationTask:
        normalized = validate_identifier(task_id, field="task_id")
        task = await self.get_task(normalized)
        if task is None:
            raise TaskNotFoundError("task does not exist", entity_type="task", entity_id=normalized)
        return task

    async def get_task_version(self, task_id: str) -> int:
        normalized = validate_identifier(task_id, field="task_id")
        value = (await self._execute(select(ImplementationTaskRecord.version).where(ImplementationTaskRecord.task_id == normalized))).scalar_one_or_none()
        if value is None:
            raise TaskNotFoundError("task does not exist", entity_type="task", entity_id=normalized)
        return value

    async def list_tasks(self, query: TaskQuery) -> Page[ImplementationTask]:
        predicates = []
        if query.status is not None:
            predicates.append(ImplementationTaskRecord.status == query.status.value)
        if query.parent_task_id is not None:
            predicates.append(ImplementationTaskRecord.parent_task_id == query.parent_task_id)
        base = select(ImplementationTaskRecord).where(*predicates)
        total = (await self._execute(select(func.count()).select_from(ImplementationTaskRecord).where(*predicates))).scalar_one()
        records = (await self._execute(base.order_by(ImplementationTaskRecord.created_at, ImplementationTaskRecord.task_id).limit(query.limit).offset(query.offset))).scalars().all()
        items = [self._mapped(implementation_task_from_record, record, "task", record.task_id) for record in records]
        return Page.from_items(items, total=total, limit=query.limit, offset=query.offset)

    async def update_task_status(self, task_id: str, new_status: ImplementationTaskStatus, expected_version: int) -> ImplementationTask:
        self._writable()
        normalized = validate_identifier(task_id, field="task_id")
        current = await self.require_task(normalized)
        actual = await self.get_task_version(normalized)
        self._validate_expected("task", normalized, expected_version, actual)
        try:
            status = ImplementationTaskStatus(new_status)
        except (TypeError, ValueError) as exc:
            raise InvalidStateTransitionError("task status is unsupported", entity_type="task", entity_id=normalized) from exc
        if status is current.status:
            return current
        if status not in _TASK_TRANSITIONS[current.status]:
            raise InvalidStateTransitionError("task status transition is forbidden", entity_type="task", entity_id=normalized)
        statement = (
            update(ImplementationTaskRecord)
            .where(ImplementationTaskRecord.task_id == normalized, ImplementationTaskRecord.version == expected_version)
            .values(status=status.value, version=ImplementationTaskRecord.version + 1)
            .returning(ImplementationTaskRecord)
        )
        record = (await self._execute(statement)).scalar_one_or_none()
        if record is None:
            latest = await self.get_task_version(normalized)
            raise OptimisticConcurrencyError(entity_type="task", entity_id=normalized, expected_version=expected_version, actual_version=latest)
        return self._mapped(implementation_task_from_record, record, "task", normalized)

    async def create_run(self, run: ImplementationRun) -> ImplementationRun:
        self._writable()
        await self.require_task(run.task_id)
        return await self._insert_immutable(
            item=run,
            record=implementation_run_to_record(run),
            lookup=select(ImplementationRunRecord).where(ImplementationRunRecord.implementation_run_id == run.implementation_run_id),
            mapper=implementation_run_from_record,
            entity_type="run",
            entity_id=run.implementation_run_id,
            identity_constraints={"pk_qm2_runs"},
        )

    async def get_run(self, run_id: str) -> ImplementationRun | None:
        normalized = validate_identifier(run_id, field="run_id")
        record = await self._scalar_record(select(ImplementationRunRecord).where(ImplementationRunRecord.implementation_run_id == normalized))
        return None if record is None else self._mapped(implementation_run_from_record, record, "run", normalized)

    async def require_run(self, run_id: str) -> ImplementationRun:
        normalized = validate_identifier(run_id, field="run_id")
        run = await self.get_run(normalized)
        if run is None:
            raise RunNotFoundError("run does not exist", entity_type="run", entity_id=normalized)
        return run

    async def get_run_version(self, run_id: str) -> int:
        normalized = validate_identifier(run_id, field="run_id")
        value = (await self._execute(select(ImplementationRunRecord.version).where(ImplementationRunRecord.implementation_run_id == normalized))).scalar_one_or_none()
        if value is None:
            raise RunNotFoundError("run does not exist", entity_type="run", entity_id=normalized)
        return value

    def _run_predicates(self, query: RunQuery) -> list[Any]:
        predicates: list[Any] = []
        if query.task_id is not None:
            predicates.append(ImplementationRunRecord.task_id == query.task_id)
        if query.task_status is not None:
            predicates.append(ImplementationRunRecord.task_status == query.task_status.value)
        if query.canonical_status is not None:
            predicates.append(ImplementationRunRecord.canonical_status == query.canonical_status.value)
        if query.consistency_status is not None:
            predicates.append(ImplementationRunRecord.consistency_status == query.consistency_status.value)
        if query.component_id is not None:
            predicates.append(exists(select(1).where(ComponentReferenceRecord.implementation_run_id == ImplementationRunRecord.implementation_run_id, ComponentReferenceRecord.component_id == query.component_id)))
        if query.adr_id is not None:
            predicates.append(exists(select(1).where(ArchitectureDecisionReferenceRecord.implementation_run_id == ImplementationRunRecord.implementation_run_id, ArchitectureDecisionReferenceRecord.adr_id == query.adr_id)))
        if query.file_path is not None:
            predicates.append(exists(select(1).where(ChangedFileRecord.implementation_run_id == ImplementationRunRecord.implementation_run_id, or_(ChangedFileRecord.path == query.file_path, ChangedFileRecord.previous_path == query.file_path))))
        if query.started_from is not None:
            predicates.append(ImplementationRunRecord.started_at >= query.started_from)
        if query.started_to is not None:
            predicates.append(ImplementationRunRecord.started_at <= query.started_to)
        return predicates

    async def list_runs(self, query: RunQuery) -> Page[ImplementationRun]:
        predicates = self._run_predicates(query)
        total = (await self._execute(select(func.count()).select_from(ImplementationRunRecord).where(*predicates))).scalar_one()
        ordering = (ImplementationRunRecord.started_at, ImplementationRunRecord.implementation_run_id)
        if query.sort_order is SortOrder.DESC:
            ordering = tuple(column.desc() for column in ordering)
        records = (await self._execute(select(ImplementationRunRecord).where(*predicates).order_by(*ordering).limit(query.limit).offset(query.offset))).scalars().all()
        items = [self._mapped(implementation_run_from_record, record, "run", record.implementation_run_id) for record in records]
        return Page.from_items(items, total=total, limit=query.limit, offset=query.offset)

    @staticmethod
    def _run_identity(run: ImplementationRun) -> tuple[object, ...]:
        return (
            run.implementation_run_id, run.task_id, run.repository_root, run.branch,
            run.base_commit, run.workspace_dirty_before, run.started_at, run.agent_type,
            run.manifest_schema_version, run.manifest_path, run.report_path,
        )

    async def _conditional_run_update(self, run_id: str, expected_version: int, values: dict[str, Any]) -> ImplementationRun:
        statement = (
            update(ImplementationRunRecord)
            .where(ImplementationRunRecord.implementation_run_id == run_id, ImplementationRunRecord.version == expected_version)
            .values(**values, version=ImplementationRunRecord.version + 1)
            .returning(ImplementationRunRecord)
        )
        record = (await self._execute(statement)).scalar_one_or_none()
        if record is None:
            latest = await self.get_run_version(run_id)
            raise OptimisticConcurrencyError(entity_type="run", entity_id=run_id, expected_version=expected_version, actual_version=latest)
        return self._mapped(implementation_run_from_record, record, "run", run_id)

    async def finalize_run(self, run_id: str, terminal_run: ImplementationRun, expected_version: int) -> ImplementationRun:
        self._writable()
        normalized = validate_identifier(run_id, field="run_id")
        current = await self.require_run(normalized)
        actual = await self.get_run_version(normalized)
        self._validate_expected("run", normalized, expected_version, actual)
        if current.task_status is not ImplementationRunStatus.RUNNING:
            raise InvalidStateTransitionError("only a running run may be finalized", entity_type="run", entity_id=normalized)
        if terminal_run.task_status is ImplementationRunStatus.RUNNING:
            raise InvalidStateTransitionError("terminal_run must have a terminal status", entity_type="run", entity_id=normalized)
        if self._run_identity(current) != self._run_identity(terminal_run):
            raise ImmutableEntityConflictError("finalization changes immutable run identity", entity_type="run", entity_id=normalized)
        if terminal_run.canonical_status is not current.canonical_status:
            raise InvalidStateTransitionError("finalize_run cannot change canonical status", entity_type="run", entity_id=normalized)
        values = {
            "result_commit": terminal_run.result_commit,
            "task_status": terminal_run.task_status.value,
            "completion_level": terminal_run.completion_level.value,
            "verification_level": terminal_run.verification_level.value,
            "workspace_dirty_after": terminal_run.workspace_dirty_after,
            "completed_at": terminal_run.completed_at,
            "manifest_hash": terminal_run.manifest_hash,
            "report_hash": terminal_run.report_hash,
            "source_bundle_hash": terminal_run.source_bundle_hash,
            "git_diff_hash": terminal_run.git_diff_hash,
            "consistency_status": terminal_run.consistency_status.value,
        }
        return await self._conditional_run_update(normalized, expected_version, values)

    async def set_consistency_status(self, run_id: str, status: ConsistencyStatus, expected_version: int) -> ImplementationRun:
        self._writable()
        normalized = validate_identifier(run_id, field="run_id")
        current = await self.require_run(normalized)
        actual = await self.get_run_version(normalized)
        self._validate_expected("run", normalized, expected_version, actual)
        try:
            value = ConsistencyStatus(status)
        except (TypeError, ValueError) as exc:
            raise InvalidStateTransitionError("consistency status is unsupported", entity_type="run", entity_id=normalized) from exc
        if value is current.consistency_status:
            return current
        try:
            replace(current, consistency_status=value)
        except ValueError as exc:
            raise InvalidStateTransitionError("consistency transition violates run invariants", entity_type="run", entity_id=normalized) from exc
        return await self._conditional_run_update(normalized, expected_version, {"consistency_status": value.value})

    async def set_canonical_status(self, run_id: str, status: CanonicalStatus, expected_version: int) -> ImplementationRun:
        self._writable()
        normalized = validate_identifier(run_id, field="run_id")
        current = await self.require_run(normalized)
        actual = await self.get_run_version(normalized)
        self._validate_expected("run", normalized, expected_version, actual)
        try:
            value = CanonicalStatus(status)
        except (TypeError, ValueError) as exc:
            raise InvalidStateTransitionError("canonical status is unsupported", entity_type="run", entity_id=normalized) from exc
        if value is current.canonical_status:
            return current
        if value not in _CANONICAL_TRANSITIONS[current.canonical_status]:
            raise InvalidStateTransitionError("canonical status transition is forbidden", entity_type="run", entity_id=normalized)
        try:
            replace(current, canonical_status=value)
        except ValueError as exc:
            raise InvalidStateTransitionError("canonical transition violates run invariants", entity_type="run", entity_id=normalized) from exc
        return await self._conditional_run_update(normalized, expected_version, {"canonical_status": value.value})

    async def get_relationship(self, relationship_id: str) -> RunRelationship | None:
        normalized = validate_identifier(relationship_id, field="relationship_id")
        record = await self._scalar_record(select(RunRelationshipRecord).where(RunRelationshipRecord.relationship_id == normalized))
        return None if record is None else self._mapped(run_relationship_from_record, record, "relationship", normalized)

    async def require_relationship(self, relationship_id: str) -> RunRelationship:
        normalized = validate_identifier(relationship_id, field="relationship_id")
        item = await self.get_relationship(normalized)
        if item is None:
            raise RelationshipNotFoundError("relationship does not exist", entity_type="relationship", entity_id=normalized)
        return item

    async def relationship_exists(self, source_run_id: str, target_run_id: str, relationship_type: RunRelationshipType) -> bool:
        source = validate_identifier(source_run_id, field="source_run_id")
        target = validate_identifier(target_run_id, field="target_run_id")
        kind = RunRelationshipType(relationship_type)
        statement = select(exists(select(1).where(RunRelationshipRecord.source_run_id == source, RunRelationshipRecord.target_run_id == target, RunRelationshipRecord.relationship_type == kind.value)))
        return bool((await self._execute(statement)).scalar_one())

    async def would_create_cycle(self, source_run_id: str, target_run_id: str) -> bool:
        source = validate_identifier(source_run_id, field="source_run_id")
        target = validate_identifier(target_run_id, field="target_run_id")
        if source == target:
            return True
        reachable = select(RunRelationshipRecord.target_run_id.label("node")).where(RunRelationshipRecord.source_run_id == target).cte("reachable", recursive=True)
        reachable = reachable.union(select(RunRelationshipRecord.target_run_id.label("node")).join(reachable, RunRelationshipRecord.source_run_id == reachable.c.node))
        return bool((await self._execute(select(exists(select(1).select_from(reachable).where(reachable.c.node == source))))).scalar_one())

    async def add_relationship(self, relationship: RunRelationship) -> RunRelationship:
        self._writable()
        await self.require_run(relationship.source_run_id)
        await self.require_run(relationship.target_run_id)
        await self._execute(select(func.pg_advisory_xact_lock(GRAPH_ADVISORY_LOCK_KEY)))
        existing = await self.get_relationship(relationship.relationship_id)
        if existing is not None:
            if existing == relationship:
                return existing
            raise ImmutableEntityConflictError("relationship ID has different immutable content", entity_type="relationship", entity_id=relationship.relationship_id)
        natural = await self._scalar_record(select(RunRelationshipRecord).where(RunRelationshipRecord.source_run_id == relationship.source_run_id, RunRelationshipRecord.target_run_id == relationship.target_run_id, RunRelationshipRecord.relationship_type == relationship.relationship_type.value))
        if natural is not None:
            existing = self._mapped(run_relationship_from_record, natural, "relationship", natural.relationship_id)
            if existing == relationship:
                return existing
            raise DuplicateChildEntityError("relationship natural key already exists", entity_type="relationship", entity_id=relationship.relationship_id)
        if await self.would_create_cycle(relationship.source_run_id, relationship.target_run_id):
            raise RunRelationshipCycleError("relationship creates a cycle", entity_type="relationship", entity_id=relationship.relationship_id)
        try:
            async with self._session.begin_nested():
                self._session.add(run_relationship_to_record(relationship))
                await self._session.flush()
        except IntegrityError as exc:
            constraint = _constraint_name(exc)
            if constraint == "uq_qm2_rels_source_target_type":
                raise DuplicateChildEntityError("relationship natural key already exists", entity_type="relationship", entity_id=relationship.relationship_id) from exc
            if constraint == "pk_qm2_rels":
                stored = await self.get_relationship(relationship.relationship_id)
                if stored == relationship:
                    return stored
                raise ImmutableEntityConflictError("relationship ID has different immutable content", entity_type="relationship", entity_id=relationship.relationship_id) from exc
            raise LedgerConstraintViolationError("database constraint rejected relationship", entity_type="relationship", entity_id=relationship.relationship_id) from exc
        return relationship

    async def _list_relationships(self, run_id: str, *, outgoing: bool) -> tuple[RunRelationship, ...]:
        normalized = (await self.require_run(run_id)).implementation_run_id
        column = RunRelationshipRecord.source_run_id if outgoing else RunRelationshipRecord.target_run_id
        records = (await self._execute(select(RunRelationshipRecord).where(column == normalized).order_by(RunRelationshipRecord.created_at, RunRelationshipRecord.relationship_id))).scalars().all()
        return tuple(self._mapped(run_relationship_from_record, record, "relationship", record.relationship_id) for record in records)

    async def list_outgoing_relationships(self, run_id: str) -> tuple[RunRelationship, ...]:
        return await self._list_relationships(run_id, outgoing=True)

    async def list_incoming_relationships(self, run_id: str) -> tuple[RunRelationship, ...]:
        return await self._list_relationships(run_id, outgoing=False)

    async def _append_child(self, *, item: _T, record: Any, model: Any, predicate: Any, mapper: Callable[[Any], _T], entity_type: str, entity_id: str, constraints: set[str]) -> _T:
        self._writable()
        await self.require_run(getattr(item, "implementation_run_id"))
        return await self._insert_immutable(item=item, record=record, lookup=select(model).where(predicate), mapper=mapper, entity_type=entity_type, entity_id=entity_id, identity_constraints=constraints)

    async def append_changed_file(self, item: ChangedFile) -> ChangedFile:
        return await self._append_child(item=item, record=changed_file_to_record(item.implementation_run_id, item), model=ChangedFileRecord, predicate=and_(ChangedFileRecord.implementation_run_id == item.implementation_run_id, ChangedFileRecord.path == item.path, ChangedFileRecord.change_type == item.change_type.value), mapper=changed_file_from_record, entity_type="changed_file", entity_id=item.path, constraints={"pk_qm2_files", "uq_qm2_files_run_path_type"})

    async def append_changed_symbol(self, item: ChangedSymbol) -> ChangedSymbol:
        return await self._append_child(item=item, record=changed_symbol_to_record(item.implementation_run_id, item), model=ChangedSymbolRecord, predicate=and_(ChangedSymbolRecord.implementation_run_id == item.implementation_run_id, ChangedSymbolRecord.file_path == item.file_path, ChangedSymbolRecord.qualified_name == item.qualified_name), mapper=changed_symbol_from_record, entity_type="changed_symbol", entity_id=item.qualified_name, constraints={"pk_qm2_symbols", "uq_qm2_symbols_run_file_name"})

    async def append_test_execution(self, item: TestExecution) -> TestExecution:
        return await self._append_child(item=item, record=test_execution_to_record(item.implementation_run_id, item), model=TestExecutionRecord, predicate=and_(TestExecutionRecord.implementation_run_id == item.implementation_run_id, TestExecutionRecord.test_execution_id == item.test_execution_id), mapper=test_execution_from_record, entity_type="test_execution", entity_id=item.test_execution_id, constraints={"pk_qm2_tests", "uq_qm2_tests_run_id"})

    async def append_artifact(self, item: ImplementationArtifact) -> ImplementationArtifact:
        return await self._append_child(item=item, record=implementation_artifact_to_record(item.implementation_run_id, item), model=ImplementationArtifactRecord, predicate=and_(ImplementationArtifactRecord.implementation_run_id == item.implementation_run_id, ImplementationArtifactRecord.artifact_id == item.artifact_id), mapper=implementation_artifact_from_record, entity_type="artifact", entity_id=item.artifact_id, constraints={"pk_qm2_artifacts", "uq_qm2_artifacts_run_id"})

    async def append_component_reference(self, item: ComponentReference) -> ComponentReference:
        return await self._append_child(item=item, record=component_reference_to_record(item.implementation_run_id, item), model=ComponentReferenceRecord, predicate=and_(ComponentReferenceRecord.implementation_run_id == item.implementation_run_id, ComponentReferenceRecord.component_id == item.component_id), mapper=component_reference_from_record, entity_type="component_reference", entity_id=item.component_id, constraints={"pk_qm2_component_refs"})

    async def append_adr_reference(self, item: ArchitectureDecisionReference) -> ArchitectureDecisionReference:
        return await self._append_child(item=item, record=architecture_decision_reference_to_record(item.implementation_run_id, item), model=ArchitectureDecisionReferenceRecord, predicate=and_(ArchitectureDecisionReferenceRecord.implementation_run_id == item.implementation_run_id, ArchitectureDecisionReferenceRecord.adr_id == item.adr_id), mapper=architecture_decision_reference_from_record, entity_type="adr_reference", entity_id=item.adr_id, constraints={"pk_qm2_adr_refs"})

    async def append_limitation(self, item: Limitation) -> Limitation:
        return await self._append_child(item=item, record=limitation_to_record(item.implementation_run_id, item), model=LimitationRecord, predicate=and_(LimitationRecord.implementation_run_id == item.implementation_run_id, LimitationRecord.limitation_id == item.limitation_id), mapper=limitation_from_record, entity_type="limitation", entity_id=item.limitation_id, constraints={"pk_qm2_limitations", "uq_qm2_limitations_run_id"})

    async def append_recommended_task(self, item: RecommendedTask) -> RecommendedTask:
        return await self._append_child(item=item, record=recommended_task_to_record(item.implementation_run_id, item), model=RecommendedTaskRecord, predicate=and_(RecommendedTaskRecord.implementation_run_id == item.implementation_run_id, RecommendedTaskRecord.recommendation_id == item.recommendation_id), mapper=recommended_task_from_record, entity_type="recommended_task", entity_id=item.recommendation_id, constraints={"pk_qm2_recommendations", "uq_qm2_recommendations_run_id"})

    async def _list_children(self, run_id: str, model: Any, mapper: Callable[[Any], _T], ordering: tuple[Any, ...], entity_type: str) -> tuple[_T, ...]:
        normalized = (await self.require_run(run_id)).implementation_run_id
        records = (await self._execute(select(model).where(model.implementation_run_id == normalized).order_by(*ordering))).scalars().all()
        return tuple(self._mapped(mapper, record, entity_type, normalized) for record in records)

    async def list_changed_files(self, run_id: str) -> tuple[ChangedFile, ...]:
        return await self._list_children(run_id, ChangedFileRecord, changed_file_from_record, (ChangedFileRecord.path, ChangedFileRecord.change_type, ChangedFileRecord.changed_file_id), "changed_file")

    async def list_changed_symbols(self, run_id: str) -> tuple[ChangedSymbol, ...]:
        return await self._list_children(run_id, ChangedSymbolRecord, changed_symbol_from_record, (ChangedSymbolRecord.file_path, ChangedSymbolRecord.qualified_name, ChangedSymbolRecord.changed_symbol_id), "changed_symbol")

    async def list_test_executions(self, run_id: str) -> tuple[TestExecution, ...]:
        return await self._list_children(run_id, TestExecutionRecord, test_execution_from_record, (TestExecutionRecord.test_execution_id,), "test_execution")

    async def list_artifacts(self, run_id: str) -> tuple[ImplementationArtifact, ...]:
        return await self._list_children(run_id, ImplementationArtifactRecord, implementation_artifact_from_record, (ImplementationArtifactRecord.artifact_id,), "artifact")

    async def list_component_references(self, run_id: str) -> tuple[ComponentReference, ...]:
        return await self._list_children(run_id, ComponentReferenceRecord, component_reference_from_record, (ComponentReferenceRecord.component_id,), "component_reference")

    async def list_adr_references(self, run_id: str) -> tuple[ArchitectureDecisionReference, ...]:
        return await self._list_children(run_id, ArchitectureDecisionReferenceRecord, architecture_decision_reference_from_record, (ArchitectureDecisionReferenceRecord.adr_id,), "adr_reference")

    async def list_limitations(self, run_id: str) -> tuple[Limitation, ...]:
        return await self._list_children(run_id, LimitationRecord, limitation_from_record, (LimitationRecord.limitation_id,), "limitation")

    async def list_recommended_tasks(self, run_id: str) -> tuple[RecommendedTask, ...]:
        return await self._list_children(run_id, RecommendedTaskRecord, recommended_task_from_record, (RecommendedTaskRecord.recommendation_id,), "recommended_task")

    async def list_run_history(self, query: HistoryQuery) -> Page[ImplementationRun]:
        if query.path is not None:
            predicate = exists(select(1).where(ChangedFileRecord.implementation_run_id == ImplementationRunRecord.implementation_run_id, or_(ChangedFileRecord.path == query.path, ChangedFileRecord.previous_path == query.path)))
        elif query.component_id is not None:
            predicate = exists(select(1).where(ComponentReferenceRecord.implementation_run_id == ImplementationRunRecord.implementation_run_id, ComponentReferenceRecord.component_id == query.component_id))
        else:
            predicate = exists(select(1).where(ArchitectureDecisionReferenceRecord.implementation_run_id == ImplementationRunRecord.implementation_run_id, ArchitectureDecisionReferenceRecord.adr_id == query.adr_id))
        total = (await self._execute(select(func.count()).select_from(ImplementationRunRecord).where(predicate))).scalar_one()
        records = (await self._execute(select(ImplementationRunRecord).where(predicate).order_by(ImplementationRunRecord.started_at, ImplementationRunRecord.implementation_run_id).limit(query.limit).offset(query.offset))).scalars().all()
        items = [self._mapped(implementation_run_from_record, record, "run", record.implementation_run_id) for record in records]
        return Page.from_items(items, total=total, limit=query.limit, offset=query.offset)

    async def record_run_details_atomic(
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
        self._writable()
        async with self._session.begin_nested():
            stored = await self.create_run(run)
            operations = (
                (self.append_changed_file, changed_files),
                (self.append_changed_symbol, changed_symbols),
                (self.append_test_execution, tests),
                (self.append_artifact, artifacts),
                (self.append_component_reference, component_refs),
                (self.append_adr_reference, adr_refs),
                (self.append_limitation, limitations),
                (self.append_recommended_task, recommended_tasks),
            )
            for operation, items in operations:
                for item in items:
                    await operation(item)
        return stored
