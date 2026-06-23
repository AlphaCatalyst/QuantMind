from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from backend.services.engine.research.schemas import FactorSignalConfig, FactorValueRow


def build_factor_signal_events(
    rows: list[FactorValueRow],
    config: FactorSignalConfig,
    *,
    trade_date: date | None = None,
    price_by_symbol: Mapping[str, float] | None = None,
) -> list[dict[str, object]]:
    if not rows:
        return []

    selected_date = trade_date or max(row.trade_date for row in rows)
    day_rows = [row for row in rows if row.trade_date == selected_date]
    if not day_rows:
        return []

    price_by_symbol = price_by_symbol or {}
    ordered = sorted(day_rows, key=lambda row: row.factor_value, reverse=True)
    top_rows = ordered[: max(config.top_n, 0)]
    bottom_rows: list[FactorValueRow] = []
    if config.long_short and config.bottom_n > 0:
        bottom_rows = list(reversed(ordered[-config.bottom_n :]))

    events: list[dict[str, object]] = []

    def _append(row: FactorValueRow, idx: int, side: str, score: float) -> None:
        signal_id = f"{config.run_id}-{idx:04d}"
        event: dict[str, object] = {
            "event_type": "signal_created",
            "tenant_id": config.tenant_id,
            "user_id": config.user_id,
            "run_id": config.run_id,
            "signal_id": signal_id,
            "client_order_id": f"coid-{signal_id}",
            "symbol": row.symbol,
            "side": side,
            "quantity": config.quantity,
            "price": float(price_by_symbol.get(row.symbol, 0.0)),
            "score": score,
            "signal_source": config.signal_source,
            "trade_date": selected_date.isoformat(),
        }
        if config.long_short:
            is_short = side == "SELL"
            event["position_side"] = "short" if is_short else "long"
            event["trade_action"] = "sell_to_open" if is_short else "buy_to_open"
            event["is_margin_trade"] = is_short
        events.append(event)

    for row in top_rows:
        _append(row, len(events), "BUY", float(row.factor_value))
    for row in bottom_rows:
        _append(row, len(events), "SELL", -abs(float(row.factor_value)))

    return events
