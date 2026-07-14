"""Side-effect-free validators for Implementation Ledger values."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from .errors import (
    InvalidGitCommitError,
    InvalidHashError,
    InvalidIdentifierError,
    InvalidRepositoryPathError,
    InvalidTimeRangeError,
    SecretLikeValueRejectedError,
)


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_FULL_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHORT_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,12}$")
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE)
_CREDENTIAL_URI_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|private[_-]?key)\b"
    r"\s*(?:=|:)\s*[^\s]+"
)
_BEARER_RE = re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[^\s]+")


def validate_identifier(value: str, *, field: str = "identifier", max_length: int = 255) -> str:
    if not isinstance(value, str):
        raise InvalidIdentifierError("must be a string", field=field)
    normalized = value.strip()
    if not normalized:
        raise InvalidIdentifierError("must not be empty", field=field)
    if len(normalized) > max_length:
        raise InvalidIdentifierError("exceeds maximum length", field=field)
    if "/" in normalized or "\\" in normalized or _CONTROL_RE.search(normalized):
        raise InvalidIdentifierError("contains a path separator or control character", field=field)
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise InvalidIdentifierError("contains unsupported characters", field=field)
    return normalized


def validate_sha256(value: str, *, field: str = "hash") -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise InvalidHashError("must be a 64-character hexadecimal SHA-256", field=field)
    return value.lower()


def validate_optional_sha256(value: str | None, *, field: str = "hash") -> str | None:
    if value is None:
        return None
    if value == "":
        raise InvalidHashError("unknown hashes must use None, not an empty string", field=field)
    return validate_sha256(value, field=field)


def validate_full_git_commit(value: str, *, field: str = "git_commit") -> str:
    if not isinstance(value, str) or not _FULL_GIT_COMMIT_RE.fullmatch(value):
        raise InvalidGitCommitError("must be a full 40-character hexadecimal commit", field=field)
    return value.lower()


def validate_optional_full_git_commit(
    value: str | None, *, field: str = "git_commit"
) -> str | None:
    if value is None:
        return None
    return validate_full_git_commit(value, field=field)


def validate_short_git_commit(value: str, *, field: str = "short_git_commit") -> str:
    if not isinstance(value, str) or not _SHORT_GIT_COMMIT_RE.fullmatch(value):
        raise InvalidGitCommitError("must be a 7-12 character hexadecimal short commit", field=field)
    return value.lower()


def validate_repository_path(value: str, *, field: str = "path") -> str:
    if not isinstance(value, str):
        raise InvalidRepositoryPathError("must be a string", field=field)
    if not value or value != value.strip() or "\x00" in value or "\\" in value:
        raise InvalidRepositoryPathError("must be a non-empty normalized POSIX path", field=field)
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise InvalidRepositoryPathError("must be repository-relative", field=field)
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InvalidRepositoryPathError("must not contain traversal or empty segments", field=field)
    normalized = path.as_posix()
    if normalized != value or normalized in {"", "."}:
        raise InvalidRepositoryPathError("must already be normalized", field=field)
    return normalized


def validate_uri(value: str, *, field: str = "uri") -> str:
    if not isinstance(value, str) or not value or value != value.strip() or _CONTROL_RE.search(value):
        raise InvalidRepositoryPathError("must be a non-empty URI without control characters", field=field)
    parts = urlsplit(value)
    if not parts.scheme or not _URI_SCHEME_RE.fullmatch(parts.scheme):
        raise InvalidRepositoryPathError("must contain a valid URI scheme", field=field)
    if parts.username is not None or parts.password is not None:
        raise SecretLikeValueRejectedError("credential-bearing URI is forbidden", field=field)
    if not parts.netloc and not parts.path:
        raise InvalidRepositoryPathError("must contain a URI authority or path", field=field)
    return value


def validate_aware_datetime(value: datetime, *, field: str = "datetime") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidTimeRangeError("must be timezone-aware", field=field)
    return value.astimezone(timezone.utc)


def validate_time_range(started_at: datetime, completed_at: datetime | None) -> tuple[datetime, datetime | None]:
    start_utc = validate_aware_datetime(started_at, field="started_at")
    complete_utc = (
        validate_aware_datetime(completed_at, field="completed_at")
        if completed_at is not None
        else None
    )
    if complete_utc is not None and start_utc > complete_utc:
        raise InvalidTimeRangeError("started_at must not be after completed_at", field="completed_at")
    return start_utc, complete_utc


def validate_no_secret_like(value: str, *, field: str = "value") -> str:
    if not isinstance(value, str):
        raise SecretLikeValueRejectedError("must be a string", field=field)
    if any(
        pattern.search(value)
        for pattern in (
            _PRIVATE_KEY_RE,
            _CREDENTIAL_URI_RE,
            _SECRET_ASSIGNMENT_RE,
            _BEARER_RE,
        )
    ):
        raise SecretLikeValueRejectedError("contains an obvious secret-like pattern", field=field)
    return value


def validate_required_text(
    value: str,
    *,
    field: str,
    max_length: int = 4096,
    reject_secret_like: bool = False,
) -> str:
    if not isinstance(value, str):
        raise InvalidIdentifierError("must be a string", field=field)
    normalized = value.strip()
    if not normalized:
        raise InvalidIdentifierError("must not be empty", field=field)
    if len(normalized) > max_length or _CONTROL_RE.search(normalized):
        raise InvalidIdentifierError("is too long or contains control characters", field=field)
    if reject_secret_like:
        validate_no_secret_like(normalized, field=field)
    return normalized


def validate_non_negative(value: int, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidIdentifierError("must be a non-negative integer", field=field)
    return value
