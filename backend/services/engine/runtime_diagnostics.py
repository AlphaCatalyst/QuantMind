from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_file


REDACTED = "[REDACTED]"
LAUNCHCTL_WHITELIST = (
    "label",
    "loaded",
    "enabled",
    "state",
    "runs",
    "last_exit_code",
    "pid",
    "last_run_at",
    "last_success_at",
    "next_expected_run",
    "program_path_checksum",
    "plist_checksum",
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redaction_count: int
    categories: tuple[str, ...]


class RuntimeDiagnosticRedactionGuardV1:
    """Fail-closed redaction for text crossing an operational boundary."""

    _patterns = (
        (
            "credential_assignment",
            re.compile(
                r"(?im)\b(?:TUSHARE_TOKEN|ACCESS_TOKEN|API_KEY|PRIVATE_KEY|PASSWORD)"
                r"\s*[:=]\s*[^\s,;}\]]+"
            ),
        ),
        (
            "authorization_header",
            re.compile(r"(?im)\bAuthorization\s*:\s*[^\r\n]+"),
        ),
        (
            "bearer_value",
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
        ),
        (
            "launchd_environment",
            re.compile(r"(?is)\benvironment(?:variables)?\s*=\s*\{.*?\}"),
        ),
        (
            "environment_assignment",
            re.compile(r"(?m)^[A-Z][A-Z0-9_]{2,}\s*=\s*[^\r\n]+$"),
        ),
    )
    _token_pattern = re.compile(
        r"(?<![A-Za-z0-9])[A-Za-z0-9+/=_-]{40,}(?![A-Za-z0-9])"
    )
    _public_identity = re.compile(
        r"^(?:[a-z][a-z0-9]{1,12}\d?_)[0-9a-f]{32,64}$"
    )

    def redact(self, value: str | None) -> RedactionResult:
        text = value or ""
        count = 0
        categories: set[str] = set()
        for category, pattern in self._patterns:
            text, replacements = pattern.subn(REDACTED, text)
            if replacements:
                count += replacements
                categories.add(category)
        def replace_token(match: re.Match[str]) -> str:
            nonlocal count
            candidate = match.group(0)
            if re.fullmatch(r"[0-9a-fA-F]{40,64}", candidate):
                return candidate
            if self._public_identity.fullmatch(candidate):
                return candidate
            count += 1
            categories.add("token_like_value")
            return REDACTED

        text = self._token_pattern.sub(replace_token, text)
        return RedactionResult(text, count, tuple(sorted(categories)))


def safe_launchctl_status(
    *,
    raw: str,
    returncode: int,
    label: str,
    plist_path: Path,
    program_path: Path | None,
    last_run_at: str | None = None,
    last_success_at: str | None = None,
    next_expected_run: str | None = None,
) -> dict[str, Any]:
    """Parse launchctl output in memory and emit only the frozen whitelist."""

    base: dict[str, Any] = {
        "label": label,
        "loaded": returncode == 0,
        "enabled": returncode == 0,
        "state": None,
        "runs": None,
        "last_exit_code": None,
        "pid": None,
        "last_run_at": last_run_at,
        "last_success_at": last_success_at,
        "next_expected_run": next_expected_run,
        "program_path_checksum": (
            hash_file(program_path) if program_path and program_path.is_file() else None
        ),
        "plist_checksum": hash_file(plist_path) if plist_path.is_file() else None,
    }
    if returncode != 0:
        return base | {"status": "not_loaded"}
    patterns = {
        "state": re.compile(r"(?m)^\s*state\s*=\s*(.+?)\s*$"),
        "runs": re.compile(r"(?m)^\s*runs\s*=\s*(\d+)\s*$"),
        "last_exit_code": re.compile(
            r"(?m)^\s*last exit code\s*=\s*(-?\d+)\s*$"
        ),
        "pid": re.compile(r"(?m)^\s*pid\s*=\s*(\d+)\s*$"),
    }
    parsed = 0
    for field, pattern in patterns.items():
        match = pattern.search(raw)
        if not match:
            continue
        parsed += 1
        value: Any = match.group(1)
        if field != "state":
            value = int(value)
        base[field] = value
    if not parsed:
        return base | {"status": "diagnostic_parse_failed"}
    return base | {"status": "ok"}


def whitelist_only(value: dict[str, Any]) -> dict[str, Any]:
    return {name: value.get(name) for name in LAUNCHCTL_WHITELIST}
