from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.services.engine.market_data.models import AdjustmentMode, DailyBarsRequest
from backend.services.engine.market_data.providers import TongDaXinProvider
from backend.services.engine.market_data.snapshot import DatasetSnapshotService, load_daily_bars


class Client:
    def __init__(self) -> None:
        self.kwargs = None
        self.closed = False

    def initialize(self, source: str) -> None:
        assert source

    def get_market_data(self, **kwargs):  # noqa: ANN003,ANN201
        self.kwargs = kwargs
        index = pd.to_datetime(["2026-01-05", "2026-01-06"])
        symbols = kwargs["stock_list"]
        def frame(values):  # noqa: ANN001,ANN202
            return pd.DataFrame({symbol: values for symbol in symbols}, index=index)
        return {"Open": frame([10.0, 10.2]), "High": frame([10.8, 10.9]), "Low": frame([9.8, 10.0]), "Close": frame([10.4, 10.6]), "Volume": frame([100.0, 120.0]), "Amount": frame([1040.0, 1272.0])}

    def close(self) -> None:
        self.closed = True


def test_evidenced_tqcenter_mapping_without_network(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("QUANTMIND_TDX_VOLUME_UNIT", "share")
    monkeypatch.setenv("QUANTMIND_TDX_AMOUNT_UNIT", "CNY")
    client = Client()
    provider = TongDaXinProvider(client)
    request = DailyBarsRequest(("SH600000", "SZ000001"), date(2026, 1, 5), date(2026, 1, 6), adjustment_mode=AdjustmentMode.FORWARD)
    batch = provider.fetch_daily_bars(request)
    assert len(batch.rows) == 4
    assert client.kwargs["dividend_type"] == "front"
    assert client.kwargs["fill_data"] is False
    assert client.closed


_REAL_PROVIDER = TongDaXinProvider()
_REAL_PROBE = _REAL_PROVIDER.probe()


@pytest.mark.skipif(not _REAL_PROBE.available, reason="real tqcenter client and explicit units unavailable")
def test_real_tongdaxin_vertical_slice(tmp_path) -> None:  # noqa: ANN001
    request = DailyBarsRequest(
        ("SH600000", "SZ000001"), date(2026, 4, 1), date(2026, 5, 15),
        adjustment_mode=AdjustmentMode.NONE,
    )
    service = DatasetSnapshotService(tmp_path)
    first = service.create(_REAL_PROVIDER, request)
    second = service.create(_REAL_PROVIDER, request)
    assert first["snapshot_id"] == second["snapshot_id"] and second["status"] == "existing"
    assert len(load_daily_bars(tmp_path, first["snapshot_id"])) >= 40
