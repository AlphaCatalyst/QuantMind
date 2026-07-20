from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .enums import PermissionStatus
from .models import CapabilityResult
from .tushare_client import CorporateActionTushareClient, SafeTushareResult


@dataclass(frozen=True)
class CapabilityProbe:
    endpoint: str
    fields: tuple[str, ...]
    params: dict[str, Any]
    event_coverage: tuple[str, ...] = ()
    settlement_fields: tuple[str, ...] = ()
    raw_announcement: bool = False


def probe_capabilities(
    client: CorporateActionTushareClient,
    probes: Iterable[CapabilityProbe],
) -> tuple[tuple[CapabilityResult, ...], tuple[SafeTushareResult, ...]]:
    """Probe supplied catalog entries; no endpoint is presumed to exist."""
    capabilities, responses = [], []
    for probe in probes:
        response = client.query(probe.endpoint, probe.fields, **probe.params)
        responses.append(response)
        symbol = probe.params.get("ts_code")
        coverage = (str(symbol),) if symbol and response.rows else ()
        available = set(response.available_fields)
        settlement = tuple(field for field in probe.settlement_fields if field in available)
        capabilities.append(CapabilityResult(
            endpoint=probe.endpoint,
            permission_status=response.status,
            available_fields=response.available_fields,
            target_symbol_coverage=coverage,
            target_event_coverage=probe.event_coverage if response.rows else (),
            structured_settlement_fields=settlement,
            raw_announcement_available=(
                probe.raw_announcement and response.status is PermissionStatus.AVAILABLE
            ),
            safe_error_code=response.safe_error_code,
            row_count=len(response.rows),
        ))
    return tuple(capabilities), tuple(responses)
