from __future__ import annotations

from datetime import date

import pytest

from backend.services.engine.market_data.errors import InvalidMarketDataRequest, ProviderUnavailableError
from backend.services.engine.market_data.models import AdjustmentMode, DailyBarsRequest
from backend.services.engine.market_data.providers import FakeMarketDataProvider, TongDaXinProvider
from backend.services.engine.market_data.symbol import normalize_symbol


def request(**changes) -> DailyBarsRequest:  # noqa: ANN003
    values = {
        "symbols": ("600000.SH", "SZ000001"),
        "start_date": date(2026, 1, 5), "end_date": date(2026, 1, 9),
        "adjustment_mode": AdjustmentMode.NONE,
    }
    values.update(changes)
    return DailyBarsRequest(**values)


def test_request_normalizes_symbols_and_fake_probe_is_explicit() -> None:
    item = request()
    assert item.symbols == ("SH600000", "SZ000001")
    assert normalize_symbol("000001.sz") == "SZ000001"
    probe = FakeMarketDataProvider().probe()
    assert probe.available and probe.provider_id == "fake"


@pytest.mark.parametrize("symbol", ["", "123", "XX600000", "600000.US"])
def test_invalid_symbol_is_rejected(symbol: str) -> None:
    with pytest.raises(InvalidMarketDataRequest):
        request(symbols=(symbol,))


def test_invalid_range_frequency_fields_are_rejected() -> None:
    with pytest.raises(InvalidMarketDataRequest):
        request(start_date=date(2026, 2, 1), end_date=date(2026, 1, 1))
    with pytest.raises(InvalidMarketDataRequest):
        request(frequency="1m")
    with pytest.raises(InvalidMarketDataRequest):
        request(fields=("symbol",))


def test_fake_is_deterministic_and_filters_symbols_and_dates() -> None:
    provider = FakeMarketDataProvider()
    first = provider.fetch_daily_bars(request(symbols=("SH600000",)))
    second = provider.fetch_daily_bars(request(symbols=("SH600000",)))
    assert first.rows == second.rows
    assert {row["symbol"] for row in first.rows} == {"SH600000"}
    assert {row["trade_date"] for row in first.rows} == {
        "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"
    }


@pytest.mark.parametrize("fault", ["duplicate", "invalid_ohlc", "negative_volume", "missing_symbol", "schema_drift"])
def test_fake_can_produce_declared_faults(fault: str) -> None:
    batch = FakeMarketDataProvider(fault).fetch_daily_bars(request())
    assert batch.source_metadata["fault"] == fault


def test_tongdaxin_probe_and_fetch_fail_safely_without_client(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("QUANTMIND_TDX_VOLUME_UNIT", raising=False)
    monkeypatch.delenv("QUANTMIND_TDX_AMOUNT_UNIT", raising=False)
    provider = TongDaXinProvider()
    probe = provider.probe()
    assert not probe.available
    assert "tqcenter_client" in probe.missing_configuration
    assert all("password" not in item.lower() for item in probe.missing_configuration)
    with pytest.raises(ProviderUnavailableError, match="unavailable"):
        provider.fetch_daily_bars(request())


def test_tongdaxin_backward_adjustment_is_not_claimed(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("QUANTMIND_TDX_VOLUME_UNIT", "share")
    monkeypatch.setenv("QUANTMIND_TDX_AMOUNT_UNIT", "CNY")
    provider = TongDaXinProvider(client=object())
    with pytest.raises(ProviderUnavailableError, match="backward"):
        provider.fetch_daily_bars(request(adjustment_mode=AdjustmentMode.BACKWARD))
