"""Pure value conversions shared by explicitly scoped Ledger mappers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar

from .errors import (
    InvalidMapperValueError,
    RecordToDomainError,
    UnknownEnumValueError,
)


MAPPER_CONTRACT_VERSION = "1.0.0"
_E = TypeVar("_E", bound=Enum)


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
