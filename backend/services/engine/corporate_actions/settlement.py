from __future__ import annotations

from dataclasses import dataclass

from .enums import CorporateActionEventType, EvidenceCompleteness
from .errors import CorporateActionEvidenceInsufficient
from .models import SecurityCorporateActionEvent


UNRESOLVED_CODE = "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED"


@dataclass(frozen=True)
class SettlementResult:
    original_shares: float
    ending_shares: float
    cash_credit: float
    replacement_symbol: str | None
    replacement_shares: float
    residual_cash_credit: float


def settle_position(event: SecurityCorporateActionEvent, held_shares: float) -> SettlementResult:
    if event.evidence_completeness is not EvidenceCompleteness.COMPLETE:
        raise CorporateActionEvidenceInsufficient(UNRESOLVED_CODE)
    if event.event_type is CorporateActionEventType.CASH_SETTLEMENT:
        if event.cash_per_share is None or event.settlement_date is None:
            raise CorporateActionEvidenceInsufficient(UNRESOLVED_CODE)
        return SettlementResult(held_shares, 0.0, held_shares * event.cash_per_share,
                                None, 0.0, 0.0)
    if event.event_type in {
        CorporateActionEventType.STOCK_CONVERSION,
        CorporateActionEventType.MERGER_EXCHANGE,
    }:
        if not event.replacement_symbol or event.conversion_ratio is None:
            raise CorporateActionEvidenceInsufficient(UNRESOLVED_CODE)
        residual = held_shares * float(event.residual_cash_per_share or 0.0)
        return SettlementResult(
            held_shares, 0.0, 0.0, event.replacement_symbol,
            held_shares * event.conversion_ratio, residual,
        )
    if event.event_type is CorporateActionEventType.WRITE_OFF and event.settlement_date:
        return SettlementResult(held_shares, 0.0, 0.0, None, 0.0, 0.0)
    raise CorporateActionEvidenceInsufficient(UNRESOLVED_CODE)
