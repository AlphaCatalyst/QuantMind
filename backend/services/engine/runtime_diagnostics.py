from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from backend.services.engine.autonomous_factor_campaign.artifact import KINDS
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
    """Context-aware redaction for text crossing an operational boundary."""

    _patterns = (
        (
            "authorization_header",
            re.compile(r"(?im)\bAuthorization\s*:\s*[^\r\n]+"),
        ),
        (
            "bearer_token",
            re.compile(r"(?i)\bBearer\s+[^\s,;}\]]+"),
        ),
        (
            "launchd_environment_block",
            re.compile(r"(?is)\benvironment(?:variables)?\s*=\s*\{.*?\}"),
        ),
        (
            "credential_assignment",
            re.compile(
                r"(?im)\b(?:token|secret|password|passwd|authorization|api_key|"
                r"apikey|credential|tushare_token|access_token|private_key)"
                r"\s*[:=]\s*(?!true\b|false\b|null\b)[^\s,;}\]]+"
            ),
        ),
    )
    _environment_assignment = re.compile(
        r"(?m)^[A-Z][A-Z0-9_]{2,}\s*=\s*[^\r\n]+$"
    )
    _safe_hex = re.compile(r"^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$")
    _safe_schema = re.compile(r"^[A-Za-z0-9_.:-]+$")
    _artifact_prefixes = tuple(sorted({prefix for _, prefix in KINDS.values()}))

    def __init__(self, *, known_secrets: Iterable[str] = ()) -> None:
        self._known_secrets = tuple(
            value for value in known_secrets if isinstance(value, str) and value
        )

    @classmethod
    def is_safe_public_value(cls, value: str) -> bool:
        if cls._safe_hex.fullmatch(value) or cls._safe_schema.fullmatch(value):
            return True
        return any(
            value.startswith(prefix)
            and re.fullmatch(r"[0-9a-f]{32,64}", value[len(prefix) :])
            for prefix in cls._artifact_prefixes
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
        environment_rows = self._environment_assignment.findall(text)
        if len(environment_rows) >= 3:
            text = self._environment_assignment.sub(REDACTED, text)
            count += len(environment_rows)
            categories.add("unsafe_environment_dump")
        for secret in self._known_secrets:
            replacements = text.count(secret)
            if replacements:
                text = text.replace(secret, REDACTED)
                count += replacements
                categories.add("known_secret_value")
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
