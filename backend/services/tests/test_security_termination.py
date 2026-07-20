from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.security_termination.policy import (
    EVENT_TYPES,
    SecurityTerminationEvent,
    SecurityTerminationPolicyV1,
)
from backend.services.engine.tushare_agent_experiment.artifact import (
    PREFIXES,
    publish_experiment_artifact,
    validate_experiment_artifact,
)


def _event(event_type: str = "delisting", **changes) -> SecurityTerminationEvent:
    values = {
        "symbol": "SH600001",
        "event_type": event_type,
        "last_tradable_date": "2025-01-10",
        "effective_date": "2025-01-13",
        "settlement_date": None,
        "settlement_currency": None,
        "cash_per_share": None,
        "replacement_symbol": None,
        "conversion_ratio": None,
        "source_artifact": "t500_test",
        "evidence_hash": "a" * 64,
    }
    values.update(changes)
    return SecurityTerminationEvent(**values)


def test_policy_supports_required_events_and_forbids_implicit_settlement():
    policy = SecurityTerminationPolicyV1()
    assert EVENT_TYPES == {
        "delisting", "cash_settlement", "stock_conversion", "merger_exchange",
        "write_off", "unknown_termination",
    }
    assert policy.policy_id.startswith("stp_")
    assert policy.payload()["implicit_last_price_sale_rule"] == "forbidden"
    assert policy.payload()["unsupported_zero_return_rule"] == "forbidden"


def test_no_exposure_and_formal_exit_are_canonical():
    policy = SecurityTerminationPolicyV1()
    assert policy.classify_strategy_exposure(
        symbol="SH600001", last_tradable_date="2025-01-10",
        positions=[], orders=[], events=[_event()],
    )["classification"] == "NO_PORTFOLIO_IMPACT"
    result = policy.classify_strategy_exposure(
        symbol="SH600001", last_tradable_date="2025-01-10",
        positions=[{"symbol": "SH600001", "date": "2025-01-03"}],
        orders=[
            {"symbol": "SH600001", "action": "buy", "dealt_amount": 100,
             "start_time": "2025-01-02"},
            {"symbol": "SH600001", "action": "sell", "dealt_amount": 100,
             "start_time": "2025-01-09"},
        ],
        events=[_event()],
    )
    assert result["classification"] == "EXITED_BEFORE_TERMINATION"
    assert result["canonical"] is True


def test_crossing_without_settlement_is_noncanonical():
    result = SecurityTerminationPolicyV1().classify_strategy_exposure(
        symbol="SH600001", last_tradable_date="2025-01-10",
        positions=[{"symbol": "SH600001", "date": "2025-01-14"}],
        orders=[{"symbol": "SH600001", "action": "buy", "dealt_amount": 100,
                 "start_time": "2025-01-09"}],
        events=[_event()],
    )
    assert result["classification"] == "UNRESOLVED_TERMINATION_POSITION"
    assert result["settlement_status"] == "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED"
    assert result["canonical"] is False


@pytest.mark.parametrize(
    ("event", "method"),
    [
        (_event("cash_settlement", settlement_date="2025-01-20",
                settlement_currency="CNY", cash_per_share=2.5), "cash_settlement"),
        (_event("stock_conversion", settlement_date="2025-01-20",
                replacement_symbol="SH600002", conversion_ratio=0.5), "stock_conversion"),
        (_event("merger_exchange", settlement_date="2025-01-20",
                replacement_symbol="SH600002", conversion_ratio=1.2), "merger_exchange"),
        (_event("write_off", settlement_date="2025-01-20"), "write_off"),
    ],
)
def test_formal_settlement_evidence_resolves_crossing(event, method):
    status = SecurityTerminationPolicyV1.settlement_status([event])
    assert status["status"] == "resolved"
    assert status["method"] == method


def test_termination_artifact_contract(tmp_path: Path):
    policy = SecurityTerminationPolicyV1()
    timeline = tmp_path / "timeline.parquet"
    pd.DataFrame([{"symbol": "SH600001", "trade_date": "2025-01-10"}]).to_parquet(timeline)
    kind = ArtifactKind.HISTORICAL_BACKTEST_TERMINATION_FOLLOWUP.value
    assert PREFIXES[kind] == ("termination_followup_id", "htf_")
    artifact = publish_experiment_artifact(
        tmp_path / "artifacts", kind,
        {"provider_id": "tushare-pro-v1", "promotion_writes": 0},
        {
            "policy.json": policy.payload(),
            "symbol_events.json": {"events": [_event().payload()]},
            "strategy_exposure.json": {},
            "benchmark_exposure.json": {},
            "position_timeline.parquet": timeline,
            "impact_summary.json": {
                "promotion_writes": 0, "agent_calls": 0, "optimization_trials": 0,
            },
            "canonicality.json": {
                "2025": {"fixed_100_benchmark_return": "noncanonical",
                         "strategy_fixed_100_excess": "noncanonical"},
            },
        },
    )
    assert validate_experiment_artifact(
        Path(artifact["path"]), artifact["termination_followup_id"], expected_kind=kind,
    )["status"] == "valid"
    canonicality = Path(artifact["path"]) / "canonicality.json"
    payload = json.loads(canonicality.read_text())
    payload["2025"]["fixed_100_benchmark_return"] = "canonical"
    canonicality.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="file hash mismatch"):
        validate_experiment_artifact(
            Path(artifact["path"]), artifact["termination_followup_id"], expected_kind=kind,
        )
