"""Stable SQL persistence helpers derived from Ledger domain enums."""

from __future__ import annotations

from enum import Enum
from typing import Type

from backend.services.engine.project_knowledge.domain.enums import (
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    FileChangeType,
    ImplementationRunStatus,
    ImplementationTaskStatus,
    RunRelationshipType,
    SymbolChangeType,
    SymbolType,
    TestExecutionStatus,
    VerificationLevel,
)


IDENTIFIER_LENGTH = 255
GIT_COMMIT_LENGTH = 40
SHA256_LENGTH = 64
POSTGRESQL_IDENTIFIER_LIMIT = 63


def enum_values(enum_type: Type[Enum]) -> tuple[str, ...]:
    """Return domain enum values in their declared, stable order."""
    return tuple(str(item.value) for item in enum_type)


def enum_check_sql(column_name: str, enum_type: Type[Enum]) -> str:
    """Build a CHECK expression while keeping the domain enum authoritative."""
    values = ", ".join("'{}'".format(value.replace("'", "''")) for value in enum_values(enum_type))
    return f"{column_name} IN ({values})"


TASK_STATUS_VALUES = enum_values(ImplementationTaskStatus)
RUN_STATUS_VALUES = enum_values(ImplementationRunStatus)
COMPLETION_LEVEL_VALUES = enum_values(CompletionLevel)
VERIFICATION_LEVEL_VALUES = enum_values(VerificationLevel)
CONSISTENCY_STATUS_VALUES = enum_values(ConsistencyStatus)
CANONICAL_STATUS_VALUES = enum_values(CanonicalStatus)
RUN_RELATIONSHIP_TYPE_VALUES = enum_values(RunRelationshipType)
FILE_CHANGE_TYPE_VALUES = enum_values(FileChangeType)
SYMBOL_TYPE_VALUES = enum_values(SymbolType)
SYMBOL_CHANGE_TYPE_VALUES = enum_values(SymbolChangeType)
TEST_EXECUTION_STATUS_VALUES = enum_values(TestExecutionStatus)
