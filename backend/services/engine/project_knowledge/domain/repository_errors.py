"""Stable, persistence-agnostic errors for Ledger repository contracts."""

from __future__ import annotations


class LedgerRepositoryError(RuntimeError):
    """Base repository error carrying only safe structured context."""

    error_code = "LEDGER_REPOSITORY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        self.message = message
        self.entity_type = entity_type
        self.entity_id = entity_id
        context = ""
        if entity_type is not None:
            context = f"[{entity_type}"
            if entity_id is not None:
                context += f":{entity_id}"
            context += "]"
        super().__init__(f"{self.error_code}{context}: {message}")


class TaskAlreadyExistsError(LedgerRepositoryError):
    error_code = "TASK_ALREADY_EXISTS"


class TaskNotFoundError(LedgerRepositoryError):
    error_code = "TASK_NOT_FOUND"


class RunAlreadyExistsError(LedgerRepositoryError):
    error_code = "RUN_ALREADY_EXISTS"


class RunNotFoundError(LedgerRepositoryError):
    error_code = "RUN_NOT_FOUND"


class RelationshipAlreadyExistsError(LedgerRepositoryError):
    error_code = "RELATIONSHIP_ALREADY_EXISTS"


class RelationshipNotFoundError(LedgerRepositoryError):
    error_code = "RELATIONSHIP_NOT_FOUND"


class ImmutableEntityConflictError(LedgerRepositoryError):
    error_code = "IMMUTABLE_ENTITY_CONFLICT"


class OptimisticConcurrencyError(LedgerRepositoryError):
    error_code = "OPTIMISTIC_CONCURRENCY_ERROR"

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        expected_version: int | None,
        actual_version: int,
    ) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        message = (
            f"expected version {expected_version}, actual version {actual_version}"
            if expected_version is not None
            else f"expected version must be an integer; actual version {actual_version}"
        )
        super().__init__(
            message,
            entity_type=entity_type,
            entity_id=entity_id,
        )


class RunRelationshipCycleError(LedgerRepositoryError):
    error_code = "RUN_RELATIONSHIP_CYCLE"


class InvalidStateTransitionError(LedgerRepositoryError):
    error_code = "INVALID_STATE_TRANSITION"


class DuplicateChildEntityError(LedgerRepositoryError):
    error_code = "DUPLICATE_CHILD_ENTITY"


class RepositoryQueryError(LedgerRepositoryError):
    error_code = "REPOSITORY_QUERY_ERROR"
