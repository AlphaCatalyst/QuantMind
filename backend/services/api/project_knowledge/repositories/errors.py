"""Stable persistence errors for the PostgreSQL Ledger adapter."""

from backend.services.engine.project_knowledge.domain.repository_errors import (
    LedgerRepositoryError,
)


class LedgerPersistenceUnavailableError(LedgerRepositoryError):
    error_code = "LEDGER_PERSISTENCE_UNAVAILABLE"


class LedgerTransactionError(LedgerRepositoryError):
    error_code = "LEDGER_TRANSACTION_ERROR"


class LedgerConstraintViolationError(LedgerRepositoryError):
    error_code = "LEDGER_CONSTRAINT_VIOLATION"

    def __init__(
        self,
        message: str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        mapper_error_code: str | None = None,
    ) -> None:
        self.mapper_error_code = mapper_error_code
        super().__init__(message, entity_type=entity_type, entity_id=entity_id)
