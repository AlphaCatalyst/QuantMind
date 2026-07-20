from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.services.engine.tushare_cutover.client import TushareClient, TushareError

from .credentials import token_from_environment
from .enums import PermissionStatus


@dataclass(frozen=True)
class SafeTushareResult:
    endpoint: str
    params: dict[str, Any]
    requested_fields: tuple[str, ...]
    status: PermissionStatus
    available_fields: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    safe_error_code: str | None


class CorporateActionTushareClient:
    """Environment-only, redacted adapter with explicit network accounting."""

    def __init__(self, transport: TushareClient | None = None) -> None:
        self._transport = transport or TushareClient(token=token_from_environment())
        self.network_calls = 0

    def query(self, endpoint: str, fields: tuple[str, ...], **params: Any) -> SafeTushareResult:
        self.network_calls += 1
        try:
            response = self._transport.query(endpoint, fields=fields, **params)
            return SafeTushareResult(
                endpoint, dict(params), fields, PermissionStatus.AVAILABLE,
                response.fields, response.rows, None,
            )
        except TushareError:
            return SafeTushareResult(
                endpoint, dict(params), fields,
                PermissionStatus.PERMISSION_OR_PARAMETER_ERROR,
                (), (), "TUSHARE_PERMISSION_OR_PARAMETER_ERROR",
            )

