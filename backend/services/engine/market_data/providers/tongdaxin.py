from __future__ import annotations

import importlib
import os
from typing import Any

from ..errors import ProviderUnavailableError
from ..models import AdjustmentMode, DailyBarsBatch, DailyBarsRequest, ProviderProbeResult
from ..symbol import to_tdx_symbol


class TongDaXinProvider:
    """Lazy adapter for the proprietary `tqcenter.tq` client found in legacy scripts."""

    provider_id = "tongdaxin-tqcenter"
    provider_version = "tqcenter-adapter-v1"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self.volume_unit = os.getenv("QUANTMIND_TDX_VOLUME_UNIT", "").strip()
        self.amount_unit = os.getenv("QUANTMIND_TDX_AMOUNT_UNIT", "").strip()

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client
        return importlib.import_module("tqcenter").tq

    def probe(self) -> ProviderProbeResult:
        missing = []
        try:
            self._load_client()
        except Exception:
            missing.append("tqcenter_client")
        if self.volume_unit != "share":
            missing.append("QUANTMIND_TDX_VOLUME_UNIT=share")
        if self.amount_unit != "CNY":
            missing.append("QUANTMIND_TDX_AMOUNT_UNIT=CNY")
        return ProviderProbeResult(
            self.provider_id, self.provider_version, not missing,
            "proprietary_tqcenter_python_client", ("none", "forward"), tuple(missing),
            None if not missing else "TongDaXin client or explicit unit semantics unavailable",
        )

    def fetch_daily_bars(self, request: DailyBarsRequest) -> DailyBarsBatch:
        probe = self.probe()
        if not probe.available:
            raise ProviderUnavailableError(probe.safe_error or "TongDaXin unavailable")
        if request.adjustment_mode is AdjustmentMode.BACKWARD:
            raise ProviderUnavailableError("backward adjustment is not evidenced by tqcenter scripts")
        client = self._load_client()
        dividend_type = "front" if request.adjustment_mode is AdjustmentMode.FORWARD else "none"
        symbols = [to_tdx_symbol(item) for item in request.symbols]
        try:
            client.initialize(__file__)
            response = client.get_market_data(
                stock_list=symbols, period="1d",
                start_time=request.start_date.strftime("%Y%m%d"),
                end_time=request.end_date.strftime("%Y%m%d"),
                dividend_type=dividend_type, fill_data=False,
            )
        except Exception as exc:
            raise ProviderUnavailableError("TongDaXin daily-bar request failed") from exc
        finally:
            try:
                client.close()
            except Exception:
                pass
        required = {"Open", "High", "Low", "Close", "Volume", "Amount"}
        if not isinstance(response, dict) or not required.issubset(response):
            raise ProviderUnavailableError("TongDaXin response schema is unsupported")
        rows = []
        reverse = {to_tdx_symbol(item): item for item in request.symbols}
        for source_symbol, symbol in reverse.items():
            close = response["Close"].get(source_symbol)
            if close is None:
                continue
            for when, value in close.items():
                rows.append({
                    "symbol": symbol, "trade_date": str(when)[:10],
                    "open": response["Open"][source_symbol].loc[when],
                    "high": response["High"][source_symbol].loc[when],
                    "low": response["Low"][source_symbol].loc[when],
                    "close": value,
                    "volume": response["Volume"][source_symbol].loc[when],
                    "amount": response["Amount"][source_symbol].loc[when],
                })
        return DailyBarsBatch(
            self.provider_id, self.provider_version, request, tuple(rows), request.fields,
            {"price": "CNY/share", "volume": self.volume_unit, "amount": self.amount_unit},
            source_metadata={"data_mode": probe.data_mode, "dividend_type": dividend_type, "fill_data": False},
        )
