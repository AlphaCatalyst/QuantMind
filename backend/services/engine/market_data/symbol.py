from __future__ import annotations

import re

from .errors import InvalidMarketDataRequest


_PREFIX = re.compile(r"^(SH|SZ|BJ)(\d{6})$")
_SUFFIX = re.compile(r"^(\d{6})\.(SH|SZ|BJ)$")


def normalize_symbol(value: str) -> str:
    """Return the repository-authoritative uppercase prefix form, e.g. SH600000."""
    text = str(value or "").strip().upper()
    match = _PREFIX.fullmatch(text)
    if match:
        return text
    match = _SUFFIX.fullmatch(text)
    if match:
        return f"{match.group(2)}{match.group(1)}"
    if text.isdigit() and len(text) == 6:
        if text.startswith(("6", "9")):
            return f"SH{text}"
        if text.startswith(("0", "2", "3")):
            return f"SZ{text}"
        if text.startswith(("4", "8")):
            return f"BJ{text}"
    raise InvalidMarketDataRequest("invalid A-share symbol")


def to_tdx_symbol(value: str) -> str:
    symbol = normalize_symbol(value)
    return f"{symbol[2:]}.{symbol[:2]}"
