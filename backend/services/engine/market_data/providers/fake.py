from __future__ import annotations

from datetime import date, timedelta

from ..models import DailyBarsBatch, DailyBarsRequest, ProviderProbeResult


class FakeMarketDataProvider:
    """Explicit deterministic test provider; never selected implicitly."""

    provider_id = "fake"
    provider_version = "fake-daily-v1"

    def __init__(self, fault: str | None = None) -> None:
        self.fault = fault

    def probe(self) -> ProviderProbeResult:
        return ProviderProbeResult(
            self.provider_id, self.provider_version, True, "deterministic_fixture",
            ("none", "forward", "backward"),
        )

    def fetch_daily_bars(self, request: DailyBarsRequest) -> DailyBarsBatch:
        rows = []
        day = request.start_date
        while day <= request.end_date:
            if day.weekday() < 5:
                for index, symbol in enumerate(request.symbols):
                    if self.fault == "missing_symbol" and symbol == request.symbols[-1]:
                        continue
                    ordinal = (day - date(2020, 1, 1)).days
                    base = 10.0 + index * 5 + (ordinal % 31) / 10
                    row = {
                        "symbol": symbol,
                        "trade_date": day.isoformat(),
                        "open": base,
                        "high": base + 0.8,
                        "low": base - 0.6,
                        "close": base + 0.2,
                        "volume": float(100000 + index * 1000 + ordinal),
                        "amount": float((100000 + index * 1000 + ordinal) * (base + 0.2)),
                    }
                    if self.fault == "invalid_ohlc" and not rows:
                        row["high"] = row["low"] - 1
                    if self.fault == "negative_volume" and not rows:
                        row["volume"] = -1.0
                    rows.append(row)
            day += timedelta(days=1)
        if self.fault == "duplicate" and rows:
            rows.append(dict(rows[0]))
        fields = tuple(rows[0]) if rows else request.fields
        if self.fault == "schema_drift":
            fields = fields + ("unexpected",)
        return DailyBarsBatch(
            self.provider_id, self.provider_version, request, tuple(rows), fields,
            {"price": "CNY/share", "volume": "share", "amount": "CNY"},
            source_metadata={"fixture": True, "fault": self.fault},
        )
