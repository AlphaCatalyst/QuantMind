"""Immutable query and page values for Ledger repository contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generic, Iterable, TypeVar

from .enums import (
    CanonicalStatus,
    ConsistencyStatus,
    ImplementationRunStatus,
    ImplementationTaskStatus,
)
from .repository_errors import RepositoryQueryError
from .validators import (
    validate_aware_datetime,
    validate_identifier,
    validate_repository_path,
)


MAX_PAGE_LIMIT = 200
DEFAULT_PAGE_LIMIT = 50
_T = TypeVar("_T")


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


def _validate_pagination(limit: int, offset: int) -> tuple[int, int]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_PAGE_LIMIT:
        raise RepositoryQueryError(
            f"limit must be between 1 and {MAX_PAGE_LIMIT}", entity_type="query"
        )
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise RepositoryQueryError("offset must be non-negative", entity_type="query")
    return limit, offset


def _optional_identifier(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    try:
        return validate_identifier(value, field=field)
    except ValueError as exc:
        raise RepositoryQueryError(f"invalid {field}", entity_type="query") from exc


def _optional_enum(value, enum_type, field: str):  # noqa: ANN001
    if value is None:
        return None
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise RepositoryQueryError(f"invalid {field}", entity_type="query") from exc


@dataclass(frozen=True)
class TaskQuery:
    status: ImplementationTaskStatus | None = None
    parent_task_id: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        limit, offset = _validate_pagination(self.limit, self.offset)
        status = _optional_enum(self.status, ImplementationTaskStatus, "status")
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "parent_task_id",
            _optional_identifier(self.parent_task_id, "parent_task_id"),
        )
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "offset", offset)


@dataclass(frozen=True)
class RunQuery:
    task_id: str | None = None
    task_status: ImplementationRunStatus | None = None
    canonical_status: CanonicalStatus | None = None
    consistency_status: ConsistencyStatus | None = None
    component_id: str | None = None
    adr_id: str | None = None
    file_path: str | None = None
    started_from: datetime | None = None
    started_to: datetime | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0
    sort_order: SortOrder = SortOrder.ASC

    def __post_init__(self) -> None:
        limit, offset = _validate_pagination(self.limit, self.offset)
        object.__setattr__(self, "task_id", _optional_identifier(self.task_id, "task_id"))
        object.__setattr__(
            self,
            "component_id",
            _optional_identifier(self.component_id, "component_id"),
        )
        object.__setattr__(self, "adr_id", _optional_identifier(self.adr_id, "adr_id"))
        object.__setattr__(
            self,
            "task_status",
            _optional_enum(self.task_status, ImplementationRunStatus, "task_status"),
        )
        object.__setattr__(
            self,
            "canonical_status",
            _optional_enum(self.canonical_status, CanonicalStatus, "canonical_status"),
        )
        object.__setattr__(
            self,
            "consistency_status",
            _optional_enum(self.consistency_status, ConsistencyStatus, "consistency_status"),
        )
        if self.file_path is not None:
            try:
                object.__setattr__(
                    self,
                    "file_path",
                    validate_repository_path(self.file_path, field="file_path"),
                )
            except ValueError as exc:
                raise RepositoryQueryError("invalid file_path", entity_type="query") from exc
        try:
            started_from = (
                validate_aware_datetime(self.started_from, field="started_from")
                if self.started_from is not None
                else None
            )
            started_to = (
                validate_aware_datetime(self.started_to, field="started_to")
                if self.started_to is not None
                else None
            )
        except ValueError as exc:
            raise RepositoryQueryError("query time must be timezone-aware", entity_type="query") from exc
        if started_from is not None and started_to is not None and started_from > started_to:
            raise RepositoryQueryError(
                "started_from must not be after started_to", entity_type="query"
            )
        object.__setattr__(self, "started_from", started_from)
        object.__setattr__(self, "started_to", started_to)
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "offset", offset)
        try:
            object.__setattr__(self, "sort_order", SortOrder(self.sort_order))
        except ValueError as exc:
            raise RepositoryQueryError("invalid sort_order", entity_type="query") from exc


@dataclass(frozen=True)
class HistoryQuery:
    path: str | None = None
    component_id: str | None = None
    adr_id: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        limit, offset = _validate_pagination(self.limit, self.offset)
        criteria = sum(value is not None for value in (self.path, self.component_id, self.adr_id))
        if criteria != 1:
            raise RepositoryQueryError(
                "exactly one of path, component_id, or adr_id is required",
                entity_type="history_query",
            )
        if self.path is not None:
            try:
                object.__setattr__(
                    self,
                    "path",
                    validate_repository_path(self.path, field="path"),
                )
            except ValueError as exc:
                raise RepositoryQueryError("invalid history path", entity_type="history_query") from exc
        object.__setattr__(
            self,
            "component_id",
            _optional_identifier(self.component_id, "component_id"),
        )
        object.__setattr__(self, "adr_id", _optional_identifier(self.adr_id, "adr_id"))
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "offset", offset)


@dataclass(frozen=True)
class Page(Generic[_T]):
    items: tuple[_T, ...]
    total: int
    limit: int
    offset: int

    def __post_init__(self) -> None:
        limit, offset = _validate_pagination(self.limit, self.offset)
        if not isinstance(self.total, int) or isinstance(self.total, bool) or self.total < 0:
            raise RepositoryQueryError("total must be non-negative", entity_type="page")
        if not isinstance(self.items, tuple):
            object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "offset", offset)

    @classmethod
    def from_items(
        cls,
        items: Iterable[_T],
        *,
        total: int,
        limit: int,
        offset: int,
    ) -> "Page[_T]":
        return cls(tuple(items), total, limit, offset)
