from datetime import date

from backend.services.engine.research.factor_signal_adapter import (
    build_factor_signal_events,
)
from backend.services.engine.research.schemas import FactorSignalConfig, FactorValueRow


def test_build_factor_signal_events_uses_latest_date_and_prefix_symbols():
    rows = [
        FactorValueRow(date(2026, 1, 1), "SH600519", 0.2),
        FactorValueRow(date(2026, 1, 2), "SH600519", 0.1),
        FactorValueRow(date(2026, 1, 2), "SZ000001", 0.9),
        FactorValueRow(date(2026, 1, 2), "SH600000", 0.3),
    ]
    config = FactorSignalConfig(
        tenant_id="default",
        user_id="u1",
        run_id="run-qgpt-1",
        top_n=2,
        quantity=200,
    )

    signals = build_factor_signal_events(
        rows,
        config,
        price_by_symbol={"SZ000001": 12.3, "SH600000": 10.1},
    )

    assert [signal["symbol"] for signal in signals] == ["SZ000001", "SH600000"]
    assert all(signal["run_id"] == "run-qgpt-1" for signal in signals)
    assert all(signal["side"] == "BUY" for signal in signals)
    assert all(signal["signal_source"] == "quantgpt_factor" for signal in signals)
    assert signals[0]["quantity"] == 200
    assert signals[0]["price"] == 12.3


def test_build_factor_signal_events_adds_short_fields_for_long_short():
    rows = [
        FactorValueRow(date(2026, 1, 2), "SH600519", 0.8),
        FactorValueRow(date(2026, 1, 2), "SZ000001", -0.7),
        FactorValueRow(date(2026, 1, 2), "SH600000", -0.1),
    ]
    config = FactorSignalConfig(
        tenant_id="default",
        user_id="u1",
        run_id="run-qgpt-ls",
        top_n=1,
        bottom_n=1,
        long_short=True,
    )

    signals = build_factor_signal_events(rows, config)

    assert len(signals) == 2
    assert signals[0]["symbol"] == "SH600519"
    assert signals[0]["side"] == "BUY"
    assert signals[0]["trade_action"] == "buy_to_open"
    assert signals[0]["position_side"] == "long"
    assert signals[0]["is_margin_trade"] is False
    assert signals[1]["symbol"] == "SZ000001"
    assert signals[1]["side"] == "SELL"
    assert signals[1]["trade_action"] == "sell_to_open"
    assert signals[1]["position_side"] == "short"
    assert signals[1]["is_margin_trade"] is True
    assert signals[1]["score"] < 0
