from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_payload


EVENT_TYPES = frozenset({
    "delisting", "cash_settlement", "stock_conversion", "merger_exchange",
    "write_off", "unknown_termination",
})


@dataclass(frozen=True)
class SecurityTerminationEvent:
    symbol: str
    event_type: str
    last_tradable_date: str | None
    effective_date: str | None
    settlement_date: str | None
    settlement_currency: str | None
    cash_per_share: float | None
    replacement_symbol: str | None
    conversion_ratio: float | None
    source_artifact: str
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise ValueError("unsupported security termination event type")
        if not self.symbol or not self.source_artifact or len(self.evidence_hash) != 64:
            raise ValueError("termination event requires symbol and immutable evidence")

    def payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SecurityTerminationPolicyV1:
    schema_version: str = "security-termination-policy-v1"
    no_exposure_rule: str = "inactive after lifecycle end; no portfolio settlement action"
    exited_rule: str = "no settlement action when a formally executed full exit precedes termination"
    crossing_rule: str = "a position crossing last tradable date requires immutable settlement evidence"
    stale_valuation_rule: str = "forbidden"
    implicit_last_price_sale_rule: str = "forbidden"
    unsupported_zero_return_rule: str = "forbidden"
    implicit_cash_rule: str = "forbidden"
    implicit_conversion_rule: str = "forbidden"

    @property
    def policy_id(self) -> str:
        return "stp_" + hash_payload(self.payload(include_id=False))

    def payload(self, *, include_id: bool = True) -> dict:
        value = asdict(self) | {
            "supported_event_types": sorted(EVENT_TYPES),
            "unresolved_code": "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED",
            "affected_backtest_status": "noncanonical",
        }
        if include_id:
            value["policy_id"] = self.policy_id
        return value

    @staticmethod
    def settlement_status(events: Iterable[SecurityTerminationEvent]) -> dict:
        events = tuple(events)
        if any(item.event_type == "unknown_termination" for item in events):
            return {"status": "unresolved", "reason": "unknown_termination"}
        for event in events:
            if event.event_type == "cash_settlement" and all((
                event.settlement_date, event.settlement_currency,
                event.cash_per_share is not None,
            )):
                return {"status": "resolved", "method": "cash_settlement", "event": event.payload()}
            if event.event_type in {"stock_conversion", "merger_exchange"} and all((
                event.settlement_date, event.replacement_symbol,
                event.conversion_ratio is not None,
            )):
                return {"status": "resolved", "method": event.event_type, "event": event.payload()}
            if event.event_type == "write_off" and event.settlement_date:
                return {"status": "resolved", "method": "write_off", "event": event.payload()}
        return {"status": "unresolved", "reason": "settlement_evidence_absent"}

    def classify_strategy_exposure(
        self,
        *,
        symbol: str,
        last_tradable_date: str,
        positions: Iterable[Mapping],
        orders: Iterable[Mapping],
        events: Iterable[SecurityTerminationEvent],
    ) -> dict:
        positions = tuple(row for row in positions if row.get("symbol") == symbol)
        orders = tuple(row for row in orders if row.get("symbol") == symbol)
        if not positions and not orders:
            return {"classification": "NO_PORTFOLIO_IMPACT", "canonical": True,
                    "settlement_status": "not_required"}
        net_amount = sum(
            float(row.get("dealt_amount") or 0.0) * (1.0 if row.get("action") == "buy" else -1.0)
            for row in orders
        )
        last_sell = max(
            (str(row.get("start_time", ""))[:10] for row in orders if row.get("action") == "sell"),
            default=None,
        )
        position_after = any(str(row.get("date", ""))[:10] > last_tradable_date for row in positions)
        if abs(net_amount) <= 1e-8 and last_sell is not None and last_sell <= last_tradable_date and not position_after:
            return {"classification": "EXITED_BEFORE_TERMINATION", "canonical": True,
                    "settlement_status": "not_required", "last_sell_date": last_sell}
        settlement = self.settlement_status(events)
        if settlement["status"] == "resolved":
            return {"classification": "POSITION_CROSSES_TERMINATION", "canonical": True,
                    "settlement_status": "resolved", "settlement": settlement}
        return {
            "classification": "UNRESOLVED_TERMINATION_POSITION", "canonical": False,
            "settlement_status": "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED",
            "net_unsettled_amount": net_amount,
        }
