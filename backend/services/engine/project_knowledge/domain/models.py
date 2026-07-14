"""Immutable, persistence-agnostic Implementation Ledger domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TypeVar

from .enums import (
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
from .errors import (
    ForbiddenCanonicalStateError,
    InvalidIdentifierError,
    InvalidRunRelationshipError,
    InvalidStateCombinationError,
    InvalidTestExecutionError,
)
from .validators import (
    validate_aware_datetime,
    validate_full_git_commit,
    validate_identifier,
    validate_no_secret_like,
    validate_non_negative,
    validate_optional_full_git_commit,
    validate_optional_sha256,
    validate_repository_path,
    validate_required_text,
    validate_time_range,
    validate_uri,
)


_E = TypeVar("_E", bound=Enum)
_ADR_ID_RE = re.compile(r"^ADR-[0-9]{4,}$")
_URI_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _enum(value, enum_type: type[_E], *, field: str) -> _E:  # noqa: ANN001
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise InvalidStateCombinationError("contains an unsupported enum value", field=field) from exc


def _text_tuple(values, *, field: str) -> tuple[str, ...]:  # noqa: ANN001
    if isinstance(values, str):
        raise InvalidIdentifierError("must be a sequence of strings", field=field)
    try:
        return tuple(
            validate_required_text(value, field=f"{field}[{index}]")
            for index, value in enumerate(values)
        )
    except TypeError as exc:
        raise InvalidIdentifierError("must be a sequence of strings", field=field) from exc


@dataclass(frozen=True)
class ImplementationTask:
    task_id: str
    parent_task_id: str | None
    title: str
    objective: str
    scope: tuple[str, ...]
    explicit_non_goals: tuple[str, ...]
    status: ImplementationTaskStatus
    created_at: datetime

    def __post_init__(self) -> None:
        task_id = validate_identifier(self.task_id, field="task_id")
        parent = (
            validate_identifier(self.parent_task_id, field="parent_task_id")
            if self.parent_task_id is not None
            else None
        )
        if parent == task_id:
            raise InvalidStateCombinationError("parent task must differ from task", field="parent_task_id")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "parent_task_id", parent)
        object.__setattr__(self, "title", validate_required_text(self.title, field="title"))
        object.__setattr__(self, "objective", validate_required_text(self.objective, field="objective"))
        object.__setattr__(self, "scope", _text_tuple(self.scope, field="scope"))
        object.__setattr__(
            self,
            "explicit_non_goals",
            _text_tuple(self.explicit_non_goals, field="explicit_non_goals"),
        )
        object.__setattr__(self, "status", _enum(self.status, ImplementationTaskStatus, field="status"))
        object.__setattr__(
            self,
            "created_at",
            validate_aware_datetime(self.created_at, field="created_at"),
        )


@dataclass(frozen=True)
class ImplementationRun:
    implementation_run_id: str
    task_id: str
    repository_root: str
    branch: str
    base_commit: str
    result_commit: str | None
    task_status: ImplementationRunStatus
    completion_level: CompletionLevel
    verification_level: VerificationLevel
    workspace_dirty_before: bool
    workspace_dirty_after: bool
    started_at: datetime
    completed_at: datetime | None
    agent_type: str
    manifest_schema_version: str
    manifest_path: str
    manifest_hash: str | None
    report_path: str
    report_hash: str | None
    source_bundle_hash: str | None
    git_diff_hash: str | None
    consistency_status: ConsistencyStatus = ConsistencyStatus.UNVERIFIED
    canonical_status: CanonicalStatus = CanonicalStatus.NONCANONICAL

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        object.__setattr__(self, "task_id", validate_identifier(self.task_id, field="task_id"))
        object.__setattr__(
            self,
            "repository_root",
            validate_identifier(self.repository_root, field="repository_root"),
        )
        object.__setattr__(
            self,
            "branch",
            validate_required_text(self.branch, field="branch", max_length=255),
        )
        object.__setattr__(
            self,
            "base_commit",
            validate_full_git_commit(self.base_commit, field="base_commit"),
        )
        object.__setattr__(
            self,
            "result_commit",
            validate_optional_full_git_commit(self.result_commit, field="result_commit"),
        )
        status = _enum(self.task_status, ImplementationRunStatus, field="task_status")
        completion = _enum(self.completion_level, CompletionLevel, field="completion_level")
        verification = _enum(self.verification_level, VerificationLevel, field="verification_level")
        consistency = _enum(self.consistency_status, ConsistencyStatus, field="consistency_status")
        canonical = _enum(self.canonical_status, CanonicalStatus, field="canonical_status")
        object.__setattr__(self, "task_status", status)
        object.__setattr__(self, "completion_level", completion)
        object.__setattr__(self, "verification_level", verification)
        object.__setattr__(self, "consistency_status", consistency)
        object.__setattr__(self, "canonical_status", canonical)

        if not isinstance(self.workspace_dirty_before, bool) or not isinstance(
            self.workspace_dirty_after, bool
        ):
            raise InvalidStateCombinationError("workspace dirty flags must be boolean")

        started_at, completed_at = validate_time_range(self.started_at, self.completed_at)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "completed_at", completed_at)
        object.__setattr__(
            self,
            "agent_type",
            validate_identifier(self.agent_type, field="agent_type"),
        )
        object.__setattr__(
            self,
            "manifest_schema_version",
            validate_identifier(self.manifest_schema_version, field="manifest_schema_version"),
        )
        object.__setattr__(
            self,
            "manifest_path",
            validate_repository_path(self.manifest_path, field="manifest_path"),
        )
        object.__setattr__(
            self,
            "report_path",
            validate_repository_path(self.report_path, field="report_path"),
        )
        for field_name in (
            "manifest_hash",
            "report_hash",
            "source_bundle_hash",
            "git_diff_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                validate_optional_sha256(getattr(self, field_name), field=field_name),
            )

        committed = {
            ImplementationRunStatus.COMPLETED_COMMITTED,
            ImplementationRunStatus.PARTIAL_COMMITTED,
        }
        uncommitted = {
            ImplementationRunStatus.COMPLETED_UNCOMMITTED,
            ImplementationRunStatus.PARTIAL_UNCOMMITTED,
        }
        terminal = set(ImplementationRunStatus) - {ImplementationRunStatus.RUNNING}

        if status in committed and self.result_commit is None:
            raise InvalidStateCombinationError("committed status requires result_commit", field="result_commit")
        if status in uncommitted and self.result_commit is not None:
            raise InvalidStateCombinationError("uncommitted status forbids result_commit", field="result_commit")
        if status is ImplementationRunStatus.RUNNING and completed_at is not None:
            raise InvalidStateCombinationError("running status forbids completed_at", field="completed_at")
        if status in terminal and completed_at is None:
            raise InvalidStateCombinationError("terminal status requires completed_at", field="completed_at")
        if status in {
            ImplementationRunStatus.COMPLETED_COMMITTED,
            ImplementationRunStatus.COMPLETED_UNCOMMITTED,
        } and completion is not CompletionLevel.COMPLETE:
            raise InvalidStateCombinationError("completed status requires complete level", field="completion_level")
        if status in {
            ImplementationRunStatus.PARTIAL_COMMITTED,
            ImplementationRunStatus.PARTIAL_UNCOMMITTED,
        } and completion is not CompletionLevel.PARTIAL:
            raise InvalidStateCombinationError("partial status requires partial level", field="completion_level")

        if canonical is CanonicalStatus.CANONICAL:
            if status not in committed:
                raise ForbiddenCanonicalStateError("canonical run must be committed", field="canonical_status")
            if self.result_commit is None:
                raise ForbiddenCanonicalStateError("canonical run requires result_commit", field="canonical_status")
            if consistency is not ConsistencyStatus.CONSISTENT:
                raise ForbiddenCanonicalStateError("canonical run must be consistent", field="consistency_status")
            if completion is not CompletionLevel.COMPLETE:
                raise ForbiddenCanonicalStateError("canonical run must be complete", field="completion_level")
        if status in {
            ImplementationRunStatus.FAILED,
            ImplementationRunStatus.BLOCKED,
            ImplementationRunStatus.CANCELLED,
        } and canonical is CanonicalStatus.CANONICAL:
            raise ForbiddenCanonicalStateError("terminal failure state cannot be canonical", field="canonical_status")
        if status in uncommitted and self.workspace_dirty_after and canonical is CanonicalStatus.CANONICAL:
            raise ForbiddenCanonicalStateError("dirty uncommitted run cannot be canonical", field="canonical_status")


@dataclass(frozen=True)
class RunRelationship:
    relationship_id: str
    source_run_id: str
    target_run_id: str
    relationship_type: RunRelationshipType
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        source = validate_identifier(self.source_run_id, field="source_run_id")
        target = validate_identifier(self.target_run_id, field="target_run_id")
        if source == target:
            raise InvalidRunRelationshipError("source and target runs must differ", field="target_run_id")
        object.__setattr__(
            self,
            "relationship_id",
            validate_identifier(self.relationship_id, field="relationship_id"),
        )
        object.__setattr__(self, "source_run_id", source)
        object.__setattr__(self, "target_run_id", target)
        object.__setattr__(
            self,
            "relationship_type",
            _enum(self.relationship_type, RunRelationshipType, field="relationship_type"),
        )
        object.__setattr__(
            self,
            "reason",
            validate_required_text(self.reason, field="reason", reject_secret_like=True),
        )
        object.__setattr__(
            self,
            "created_at",
            validate_aware_datetime(self.created_at, field="created_at"),
        )


@dataclass(frozen=True)
class ChangedFile:
    implementation_run_id: str
    path: str
    change_type: FileChangeType
    before_hash: str | None = None
    after_hash: str | None = None
    previous_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        path = validate_repository_path(self.path, field="path")
        change_type = _enum(self.change_type, FileChangeType, field="change_type")
        before_hash = validate_optional_sha256(self.before_hash, field="before_hash")
        after_hash = validate_optional_sha256(self.after_hash, field="after_hash")
        previous_path = (
            validate_repository_path(self.previous_path, field="previous_path")
            if self.previous_path is not None
            else None
        )
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "change_type", change_type)
        object.__setattr__(self, "before_hash", before_hash)
        object.__setattr__(self, "after_hash", after_hash)
        object.__setattr__(self, "previous_path", previous_path)

        if change_type is FileChangeType.ADDED and (before_hash is not None or after_hash is None):
            raise InvalidStateCombinationError("added file requires only after_hash", field="change_type")
        if change_type is FileChangeType.DELETED and (before_hash is None or after_hash is not None):
            raise InvalidStateCombinationError("deleted file requires only before_hash", field="change_type")
        if change_type is FileChangeType.MODIFIED:
            if before_hash is None or after_hash is None:
                raise InvalidStateCombinationError("modified file requires both hashes", field="change_type")
            if before_hash == after_hash:
                raise InvalidStateCombinationError("modified file hashes must differ", field="change_type")
        if change_type is FileChangeType.RENAMED:
            if previous_path is None:
                raise InvalidStateCombinationError("renamed file requires previous_path", field="previous_path")
            if previous_path == path:
                raise InvalidStateCombinationError("renamed paths must differ", field="previous_path")
        elif previous_path is not None:
            raise InvalidStateCombinationError("previous_path is only valid for renamed files", field="previous_path")
        if change_type is FileChangeType.UNCHANGED:
            if before_hash is None or after_hash is None or before_hash != after_hash:
                raise InvalidStateCombinationError("unchanged file requires equal hashes", field="change_type")


@dataclass(frozen=True)
class ChangedSymbol:
    implementation_run_id: str
    file_path: str
    qualified_name: str
    symbol_type: SymbolType
    change_type: SymbolChangeType

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        object.__setattr__(
            self,
            "file_path",
            validate_repository_path(self.file_path, field="file_path"),
        )
        object.__setattr__(
            self,
            "qualified_name",
            validate_required_text(self.qualified_name, field="qualified_name", max_length=512),
        )
        object.__setattr__(self, "symbol_type", _enum(self.symbol_type, SymbolType, field="symbol_type"))
        object.__setattr__(
            self,
            "change_type",
            _enum(self.change_type, SymbolChangeType, field="change_type"),
        )


@dataclass(frozen=True)
class TestExecution:
    test_execution_id: str
    implementation_run_id: str
    command: str
    purpose: str
    status: TestExecutionStatus
    passed_count: int
    failed_count: int
    skipped_count: int
    not_run_reason: str | None = None
    artifact_uri: str | None = None
    artifact_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "test_execution_id",
            validate_identifier(self.test_execution_id, field="test_execution_id"),
        )
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        command = validate_required_text(
            self.command,
            field="command",
            max_length=8192,
            reject_secret_like=True,
        )
        purpose = validate_required_text(self.purpose, field="purpose")
        status = _enum(self.status, TestExecutionStatus, field="status")
        passed = validate_non_negative(self.passed_count, field="passed_count")
        failed = validate_non_negative(self.failed_count, field="failed_count")
        skipped = validate_non_negative(self.skipped_count, field="skipped_count")
        reason = (
            validate_required_text(
                self.not_run_reason,
                field="not_run_reason",
                reject_secret_like=True,
            )
            if self.not_run_reason is not None
            else None
        )
        artifact_uri = validate_uri(self.artifact_uri, field="artifact_uri") if self.artifact_uri else None
        artifact_hash = validate_optional_sha256(self.artifact_hash, field="artifact_hash")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "passed_count", passed)
        object.__setattr__(self, "failed_count", failed)
        object.__setattr__(self, "skipped_count", skipped)
        object.__setattr__(self, "not_run_reason", reason)
        object.__setattr__(self, "artifact_uri", artifact_uri)
        object.__setattr__(self, "artifact_hash", artifact_hash)

        if status is TestExecutionStatus.PASSED and failed != 0:
            raise InvalidTestExecutionError("passed status requires zero failures", field="failed_count")
        if status is TestExecutionStatus.FAILED and failed == 0:
            raise InvalidTestExecutionError("failed status requires at least one failure", field="failed_count")
        if status is TestExecutionStatus.NOT_RUN and reason is None:
            raise InvalidTestExecutionError("not_run status requires a reason", field="not_run_reason")
        if status is not TestExecutionStatus.NOT_RUN and reason is not None:
            raise InvalidTestExecutionError("not_run_reason is forbidden after execution", field="not_run_reason")


@dataclass(frozen=True)
class ImplementationArtifact:
    artifact_id: str
    implementation_run_id: str
    artifact_type: str
    path_or_uri: str
    content_hash: str | None
    schema_version: str | None
    size_bytes: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", validate_identifier(self.artifact_id, field="artifact_id"))
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        object.__setattr__(
            self,
            "artifact_type",
            validate_identifier(self.artifact_type, field="artifact_type"),
        )
        if not self.path_or_uri:
            raise InvalidStateCombinationError("artifact path_or_uri is required", field="path_or_uri")
        location = (
            validate_uri(self.path_or_uri, field="path_or_uri")
            if _URI_PREFIX_RE.match(self.path_or_uri)
            else validate_repository_path(self.path_or_uri, field="path_or_uri")
        )
        object.__setattr__(self, "path_or_uri", location)
        object.__setattr__(
            self,
            "content_hash",
            validate_optional_sha256(self.content_hash, field="content_hash"),
        )
        if self.schema_version is not None:
            object.__setattr__(
                self,
                "schema_version",
                validate_identifier(self.schema_version, field="schema_version"),
            )
        if self.size_bytes is not None:
            object.__setattr__(
                self,
                "size_bytes",
                validate_non_negative(self.size_bytes, field="size_bytes"),
            )


@dataclass(frozen=True)
class ComponentReference:
    implementation_run_id: str
    component_id: str
    impact_type: ImpactType

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        object.__setattr__(
            self,
            "component_id",
            validate_identifier(self.component_id, field="component_id"),
        )
        object.__setattr__(self, "impact_type", _enum(self.impact_type, ImpactType, field="impact_type"))


@dataclass(frozen=True)
class ArchitectureDecisionReference:
    implementation_run_id: str
    adr_id: str
    relation: ADRReferenceRelation

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        adr_id = validate_identifier(self.adr_id, field="adr_id")
        if not _ADR_ID_RE.fullmatch(adr_id):
            raise InvalidIdentifierError("must use ADR-NNNN format", field="adr_id")
        object.__setattr__(self, "adr_id", adr_id)
        object.__setattr__(
            self,
            "relation",
            _enum(self.relation, ADRReferenceRelation, field="relation"),
        )


@dataclass(frozen=True)
class Limitation:
    limitation_id: str
    implementation_run_id: str
    severity: LimitationSeverity
    component_id: str | None
    description: str
    status: LimitationStatus

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "limitation_id",
            validate_identifier(self.limitation_id, field="limitation_id"),
        )
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        if self.component_id is not None:
            object.__setattr__(
                self,
                "component_id",
                validate_identifier(self.component_id, field="component_id"),
            )
        object.__setattr__(self, "severity", _enum(self.severity, LimitationSeverity, field="severity"))
        object.__setattr__(
            self,
            "description",
            validate_required_text(
                self.description,
                field="description",
                reject_secret_like=True,
            ),
        )
        object.__setattr__(self, "status", _enum(self.status, LimitationStatus, field="status"))


@dataclass(frozen=True)
class RecommendedTask:
    recommendation_id: str
    implementation_run_id: str
    next_task_id: str
    priority: RecommendationPriority
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recommendation_id",
            validate_identifier(self.recommendation_id, field="recommendation_id"),
        )
        object.__setattr__(
            self,
            "implementation_run_id",
            validate_identifier(self.implementation_run_id, field="implementation_run_id"),
        )
        object.__setattr__(
            self,
            "next_task_id",
            validate_identifier(self.next_task_id, field="next_task_id"),
        )
        object.__setattr__(
            self,
            "priority",
            _enum(self.priority, RecommendationPriority, field="priority"),
        )
        object.__setattr__(
            self,
            "reason",
            validate_required_text(self.reason, field="reason", reject_secret_like=True),
        )
