from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .errors import InvalidMarketDataRequest
from .symbol import normalize_symbol


DAILY_FIELDS = ("symbol", "trade_date", "open", "high", "low", "close", "volume", "amount")


class AdjustmentMode(str, Enum):
    NONE = "none"
    FORWARD = "forward"
    BACKWARD = "backward"


@dataclass(frozen=True)
class DailyBarsRequest:
    symbols: tuple[str, ...]
    start_date: date
    end_date: date
    frequency: str = "1d"
    adjustment_mode: AdjustmentMode = AdjustmentMode.NONE
    fields: tuple[str, ...] = DAILY_FIELDS

    def __post_init__(self) -> None:
        if self.frequency != "1d":
            raise InvalidMarketDataRequest("only 1d frequency is supported")
        if self.start_date > self.end_date:
            raise InvalidMarketDataRequest("start_date must not exceed end_date")
        symbols = tuple(sorted({normalize_symbol(item) for item in self.symbols}))
        if not symbols:
            raise InvalidMarketDataRequest("at least one symbol is required")
        if tuple(self.fields) != DAILY_FIELDS:
            raise InvalidMarketDataRequest("v1 daily field schema is fixed")
        object.__setattr__(self, "symbols", symbols)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": list(self.symbols),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "frequency": self.frequency,
            "adjustment_mode": self.adjustment_mode.value,
            "fields": list(self.fields),
        }


@dataclass(frozen=True)
class ProviderProbeResult:
    provider_id: str
    provider_version: str
    available: bool
    data_mode: str
    supported_adjustments: tuple[str, ...]
    missing_configuration: tuple[str, ...] = ()
    safe_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "available": self.available,
            "data_mode": self.data_mode,
            "supported_adjustments": list(self.supported_adjustments),
            "missing_configuration": list(self.missing_configuration),
            "safe_error": self.safe_error,
        }


@dataclass(frozen=True)
class DailyBarsBatch:
    provider_id: str
    provider_version: str
    request: DailyBarsRequest
    rows: tuple[Mapping[str, Any], ...]
    source_fields: tuple[str, ...]
    units: Mapping[str, str]
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
