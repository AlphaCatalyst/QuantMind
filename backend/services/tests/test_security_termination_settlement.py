from __future__ import annotations

import pytest

from backend.services.engine.corporate_actions.enums import (
    CorporateActionEventType,
    EvidenceCompleteness,
)
from backend.services.engine.corporate_actions.errors import CorporateActionEvidenceInsufficient
from backend.services.engine.corporate_actions.models import SecurityCorporateActionEvent
from backend.services.engine.corporate_actions.settlement import settle_position


def event(event_type, completeness=EvidenceCompleteness.COMPLETE, **changes):
    values = dict(
        symbol="SH600001", event_type=event_type, announcement_date="2025-01-01",
        last_tradable_date="2025-01-10", effective_date="2025-01-13",
        settlement_date="2025-01-20", cash_per_share=None, replacement_symbol=None,
        conversion_ratio=None, residual_cash_per_share=None,
        source_artifact_id="tsca_raw_test", source_record_id="record_test",
        evidence_hash="a" * 64, evidence_completeness=completeness,
    )
    values.update(changes)
    return SecurityCorporateActionEvent(**values)


def test_cash_settlement():
    result = settle_position(event(CorporateActionEventType.CASH_SETTLEMENT,
                                   cash_per_share=2.5), 100)
    assert result.cash_credit == 250
    assert result.ending_shares == 0


@pytest.mark.parametrize("kind", [
    CorporateActionEventType.STOCK_CONVERSION,
    CorporateActionEventType.MERGER_EXCHANGE,
])
def test_conversion_and_residual_cash(kind):
    result = settle_position(event(
        kind, replacement_symbol="SH600002", conversion_ratio=0.5,
        residual_cash_per_share=0.1,
    ), 101)
    assert result.replacement_shares == 50.5
    assert result.residual_cash_credit == pytest.approx(10.1)


def test_write_off_requires_formal_evidence():
    result = settle_position(event(CorporateActionEventType.WRITE_OFF), 100)
    assert result.ending_shares == 0
    with pytest.raises(CorporateActionEvidenceInsufficient):
        settle_position(event(
            CorporateActionEventType.WRITE_OFF,
            EvidenceCompleteness.MISSING,
            settlement_date=None,
        ), 100)


def test_unknown_or_partial_settlement_hard_fails():
    with pytest.raises(CorporateActionEvidenceInsufficient, match="SETTLEMENT_UNRESOLVED"):
        settle_position(event(
            CorporateActionEventType.UNKNOWN_TERMINATION,
            EvidenceCompleteness.PARTIAL,
        ), 100)

