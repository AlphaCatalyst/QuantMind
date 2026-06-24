from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


EXTERNAL_SUBMIT_ENV = "QUANTMIND_FACTOR_RESEARCH_ALLOW_EXTERNAL_SUBMIT"
EXTERNAL_SUBMIT_TARGETS = frozenset({"wq_brain", "cloud_submit"})

_TRUTHY = frozenset({"1", "true", "yes", "on", "enabled", "allow"})
_FALSY = frozenset({"", "0", "false", "no", "off", "disabled", "deny"})


class ExternalSubmitDisabledError(PermissionError):
    """Raised when factor research attempts an external submit path."""


@dataclass(frozen=True)
class ExternalSubmitPolicy:
    enabled: bool
    env_key: str
    raw_value: str | None
    allowed_targets: tuple[str, ...]


def _env_value(env: Mapping[str, str] | None, key: str) -> str | None:
    source = os.environ if env is None else env
    value = source.get(key)
    return str(value).strip() if value is not None else None


def _flag_enabled(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return False


def get_external_submit_policy(
    env: Mapping[str, str] | None = None,
) -> ExternalSubmitPolicy:
    raw_value = _env_value(env, EXTERNAL_SUBMIT_ENV)
    enabled = _flag_enabled(raw_value)
    return ExternalSubmitPolicy(
        enabled=enabled,
        env_key=EXTERNAL_SUBMIT_ENV,
        raw_value=raw_value,
        allowed_targets=tuple(sorted(EXTERNAL_SUBMIT_TARGETS)) if enabled else (),
    )


def assert_external_submit_allowed(
    target: str,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    normalized_target = str(target or "").strip().lower().replace("-", "_")
    if normalized_target not in EXTERNAL_SUBMIT_TARGETS:
        raise ValueError(f"unknown external submit target: {target}")

    policy = get_external_submit_policy(env)
    if policy.enabled:
        return

    raise ExternalSubmitDisabledError(
        "factor research external submit is disabled by default; "
        f"set {EXTERNAL_SUBMIT_ENV}=true only after production approval "
        f"to enable {normalized_target}"
    )


def assert_quantgpt_endpoint_allowed(
    path: str,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    normalized = "/" + str(path or "").strip().lower().lstrip("/")
    if "/wq-brain" in normalized or normalized.endswith("/submit-alpha"):
        assert_external_submit_allowed("wq_brain", env=env)
    if "cloud-submit" in normalized or "/cloud/submit" in normalized:
        assert_external_submit_allowed("cloud_submit", env=env)
