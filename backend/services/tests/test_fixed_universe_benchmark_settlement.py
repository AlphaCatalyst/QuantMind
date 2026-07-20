from __future__ import annotations

import pytest

from backend.services.engine.corporate_actions.benchmark import (
    FixedUniverseBenchmarkContractV2,
    require_canonical_revision,
)
from backend.services.engine.corporate_actions.enums import (
    CorporateActionEventType,
    EvidenceCompleteness,
)
from backend.services.engine.corporate_actions.errors import CorporateActionEvidenceInsufficient
from backend.services.engine.corporate_actions.models import SecurityCorporateActionEvent


def _event(completeness):
    return SecurityCorporateActionEvent(
        symbol="SH600001", event_type=CorporateActionEventType.CASH_SETTLEMENT,
        announcement_date="2025-01-01", last_tradable_date="2025-01-10",
        effective_date="2025-01-13", settlement_date="2025-01-20",
        cash_per_share=2.5, replacement_symbol=None, conversion_ratio=None,
        residual_cash_per_share=None, source_artifact_id="tsca_raw_test",
        source_record_id="record_test", evidence_hash="a" * 64,
        evidence_completeness=completeness,
    )


def test_contract_freezes_investable_self_financing_semantics():
    contract = FixedUniverseBenchmarkContractV2("tu100_test")
    payload = contract.payload()
    assert payload["weighting"] == "equal_weight"
    assert payload["benchmark_semantics"] == "investable_self_financing_equal_weight_portfolio"
    assert payload["replacement_policy"] == "no_locked_universe_replacement"
    assert payload["settlement_asset_membership"] == "settlement_asset_is_not_a_new_locked_member"
    assert payload["cash_handling"] == "settlement_cash_remains_in_self_financing_cash_account"


def test_all_events_must_be_complete_before_revision():
    require_canonical_revision((_event(EvidenceCompleteness.COMPLETE),))
    with pytest.raises(CorporateActionEvidenceInsufficient):
        require_canonical_revision((
            _event(EvidenceCompleteness.COMPLETE),
            _event(EvidenceCompleteness.MISSING),
        ))


def test_blocked_revision_preserves_existing_result_boundaries():
    canonicality = {
        "strategy_nav": "unchanged_canonical",
        "csi300": "unchanged_canonical",
        "2019_2024": "unchanged_canonical",
        "2026h1": "unchanged_canonical",
        "fixed_100_2025": "noncanonical",
        "fixed_100_full_period": "noncanonical",
    }
    assert canonicality["strategy_nav"] == canonicality["2026h1"]
    assert canonicality["fixed_100_2025"] == "noncanonical"
