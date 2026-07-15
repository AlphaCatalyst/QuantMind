"""Frozen deterministic technical identities for Ledger detail records."""

from __future__ import annotations

import hashlib
import unicodedata

from backend.services.engine.project_knowledge.domain.enums import FileChangeType
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.validators import (
    validate_identifier,
    validate_repository_path,
    validate_required_text,
)

from .errors import DomainToRecordError


def _validate_qualified_name(value: object, *, field: str) -> str:
    return validate_required_text(value, field=field, max_length=512)


def _validated_identity_part(value: object, *, field_name: str, validator) -> str:  # noqa: ANN001
    try:
        validated = validator(value, field=field_name)
    except LedgerDomainError as exc:
        raise DomainToRecordError(
            "technical identity input failed Domain validation",
            object_type="LedgerTechnicalIdentity",
            field_name=exc.field,
            underlying_error_type=type(exc).__name__,
            error_code=exc.error_code,
        ) from exc
    return unicodedata.normalize("NFC", validated)


def _technical_id(prefix: str, parts: tuple[str, ...]) -> str:
    payload = "\n".join(unicodedata.normalize("NFC", part) for part in parts)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def changed_file_record_id(
    *,
    implementation_run_id: str,
    path: str,
    change_type: FileChangeType,
) -> str:
    """Return the frozen changed-file-v1 identity."""
    if not isinstance(change_type, FileChangeType):
        raise DomainToRecordError(
            "technical identity requires FileChangeType",
            object_type="ChangedFile",
            field_name="change_type",
            underlying_error_type=type(change_type).__name__,
            error_code="INVALID_ENUM_TYPE",
        )
    run_id = _validated_identity_part(
        implementation_run_id,
        field_name="implementation_run_id",
        validator=validate_identifier,
    )
    normalized_path = _validated_identity_part(
        path,
        field_name="path",
        validator=validate_repository_path,
    )
    return _technical_id(
        "cf",
        ("changed-file-v1", run_id, normalized_path, change_type.value),
    )


def changed_symbol_record_id(
    *,
    implementation_run_id: str,
    file_path: str,
    qualified_name: str,
) -> str:
    """Return the frozen changed-symbol-v1 identity."""
    run_id = _validated_identity_part(
        implementation_run_id,
        field_name="implementation_run_id",
        validator=validate_identifier,
    )
    normalized_path = _validated_identity_part(
        file_path,
        field_name="file_path",
        validator=validate_repository_path,
    )
    normalized_name = _validated_identity_part(
        qualified_name,
        field_name="qualified_name",
        validator=_validate_qualified_name,
    )
    return _technical_id(
        "cs",
        ("changed-symbol-v1", run_id, normalized_path, normalized_name),
    )
