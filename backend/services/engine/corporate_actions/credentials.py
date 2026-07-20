from __future__ import annotations

import os

from .errors import CorporateActionCredentialError


def token_from_environment() -> str:
    """Return the runtime credential without exposing a public value property."""
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise CorporateActionCredentialError("TUSHARE_TOKEN is not present")
    return token

