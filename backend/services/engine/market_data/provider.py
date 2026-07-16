from typing import Protocol

from .models import DailyBarsBatch, DailyBarsRequest, ProviderProbeResult


class MarketDataProvider(Protocol):
    provider_id: str
    provider_version: str

    def probe(self) -> ProviderProbeResult: ...

    def fetch_daily_bars(self, request: DailyBarsRequest) -> DailyBarsBatch: ...
