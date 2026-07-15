"""Pure value conversions shared by explicitly scoped Ledger mappers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import TypeVar

from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.validators import validate_identifier

from .errors import (
    DomainToRecordError,
    InvalidMapperValueError,
    RecordToDomainError,
    UnknownEnumValueError,
)


MAPPER_CONTRACT_VERSION = "1.0.0"
_E = TypeVar("_E", bound=Enum)
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_SECRET_ID_MARKERS = ("password", "passwd", "token", "secret", "api_key", "apikey")


def safe_record_identity(value: object) -> str | None:
    """Return an identifier safe for Mapper error metadata, never arbitrary content."""
    if (
        isinstance(value, str)
        and _SAFE_ID_RE.fullmatch(value)
        and not any(marker in value.lower() for marker in _SECRET_ID_MARKERS)
    ):
        return value
    return None


def loaded_column(
    values: dict[str, object],
    field_name: str,
    *,
    object_type: str,
    identity: str | None,
) -> object:
    """Read already-loaded SQLAlchemy state without invoking a descriptor load."""
    if field_name not in values:
        raise RecordToDomainError(
            "required ORM column is not loaded",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            error_code="MISSING_REQUIRED_VALUE",
        )
    return values[field_name]


def validate_parent_run_id(
    implementation_run_id: object,
    item_run_id: str,
    *,
    object_type: str,
) -> str:
    """Validate explicit parent context and require it to match the Domain value."""
    identity = safe_record_identity(item_run_id)
    try:
        validated = validate_identifier(
            implementation_run_id,
            field="implementation_run_id",
        )
    except LedgerDomainError as exc:
        raise DomainToRecordError(
            "parent run identity failed Domain validation",
            object_type=object_type,
            safe_identity=identity,
            field_name=exc.field,
            underlying_error_type=type(exc).__name__,
            error_code=exc.error_code,
        ) from exc
    if validated != item_run_id:
        raise DomainToRecordError(
            "parent run identity does not match the Domain object",
            object_type=object_type,
            safe_identity=identity,
            field_name="implementation_run_id",
            error_code="PARENT_RUN_ID_MISMATCH",
        )
    return validated


def enum_to_storage(
    value: Enum,
    *,
    field_name: str,
    object_type: str = "DomainObject",
    identity: str | None = None,
) -> str:
    """Return an exact Domain Enum value for VARCHAR persistence."""
    if not isinstance(value, Enum) or not isinstance(value.value, str):
        raise InvalidMapperValueError(
            "expected a string-valued Domain Enum",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            error_code="INVALID_ENUM_TYPE",
        )
    return value.value


def enum_from_storage(
    enum_type: type[_E],
    raw_value: object,
    *,
    object_type: str,
    identity: str | None,
    field_name: str,
) -> _E:
    """Build an exact Domain Enum without trim, case repair, or fallback."""
    if not isinstance(raw_value, str):
        raise UnknownEnumValueError(
            "stored enum must be an exact string value",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            underlying_error_type=type(raw_value).__name__,
        )
    try:
        return enum_type(raw_value)
    except ValueError as exc:
        raise UnknownEnumValueError(
            "stored enum is not supported",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            underlying_error_type=type(exc).__name__,
        ) from exc


def datetime_to_storage(
    value: object,
    *,
    field_name: str,
    object_type: str = "DomainObject",
    identity: str | None = None,
) -> datetime:
    """Normalize an aware Domain datetime to UTC without losing microseconds."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidMapperValueError(
            "datetime must be timezone-aware",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            underlying_error_type=type(value).__name__,
            error_code="INVALID_TIME",
        )
    return value.astimezone(timezone.utc)


def datetime_from_storage(
    value: object,
    *,
    object_type: str,
    identity: str | None,
    field_name: str,
) -> datetime:
    """Normalize an aware stored datetime to UTC or fail safely."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RecordToDomainError(
            "stored datetime must be timezone-aware",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            underlying_error_type=type(value).__name__,
            error_code="INVALID_TIME",
        )
    return value.astimezone(timezone.utc)


def string_tuple_to_json_array(
    value: object,
    *,
    field_name: str,
    object_type: str = "DomainObject",
    identity: str | None = None,
) -> list[str]:
    """Copy a Domain tuple of strings to a mutable JSON array value."""
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise InvalidMapperValueError(
            "expected a tuple containing only strings",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            underlying_error_type=type(value).__name__,
            error_code="INVALID_JSON_SHAPE",
        )
    return list(value)


def json_array_to_string_tuple(
    value: object,
    *,
    object_type: str,
    identity: str | None,
    field_name: str,
) -> tuple[str, ...]:
    """Copy a stored JSON list/tuple of strings to an immutable Domain tuple."""
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise RecordToDomainError(
            "stored JSON value must be an array containing only strings",
            object_type=object_type,
            safe_identity=identity,
            field_name=field_name,
            underlying_error_type=type(value).__name__,
            error_code="INVALID_JSON_SHAPE",
        )
    return tuple(item for item in value)
