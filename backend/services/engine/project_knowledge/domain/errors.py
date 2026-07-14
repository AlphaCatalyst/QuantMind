"""Structured, transport-agnostic errors for Ledger domain validation."""

from __future__ import annotations


class LedgerDomainError(ValueError):
    """Base error with a stable code and no rejected value disclosure."""

    error_code = "LEDGER_DOMAIN_ERROR"

    def __init__(self, message: str, *, field: str | None = None):
        self.field = field
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        prefix = f"{self.error_code}"
        if self.field:
            prefix += f"[{self.field}]"
        return f"{prefix}: {self.message}"


class InvalidIdentifierError(LedgerDomainError):
    error_code = "INVALID_IDENTIFIER"


class InvalidStateCombinationError(LedgerDomainError):
    error_code = "INVALID_STATE_COMBINATION"


class InvalidHashError(LedgerDomainError):
    error_code = "INVALID_HASH"


class InvalidGitCommitError(LedgerDomainError):
    error_code = "INVALID_GIT_COMMIT"


class InvalidRepositoryPathError(LedgerDomainError):
    error_code = "INVALID_REPOSITORY_PATH"


class InvalidTimeRangeError(LedgerDomainError):
    error_code = "INVALID_TIME_RANGE"


class InvalidTestExecutionError(LedgerDomainError):
    error_code = "INVALID_TEST_EXECUTION"


class InvalidRunRelationshipError(LedgerDomainError):
    error_code = "INVALID_RUN_RELATIONSHIP"


class ForbiddenCanonicalStateError(LedgerDomainError):
    error_code = "FORBIDDEN_CANONICAL_STATE"


class SecretLikeValueRejectedError(LedgerDomainError):
    error_code = "SECRET_LIKE_VALUE_REJECTED"
