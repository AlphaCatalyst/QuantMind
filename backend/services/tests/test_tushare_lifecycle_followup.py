from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.tushare_agent_experiment.evaluation import fixed100_benchmark
from backend.services.engine.tushare_lifecycle_followup.policy import (
    FixedUniverseLifecyclePolicyV1,
    active_on,
    audit_lifecycles,
    daily_member_counts,
    normalize_symbol,
)


def test_policy_freezes_capacity_and_no_fill_or_replacement():
    policy = FixedUniverseLifecyclePolicyV1()
    assert policy.locked_member_count == 100
    assert policy.minimum_observable_instruments == 25
    assert policy.payload()["capacity_derivation"] == "topk + n_drop"
    assert policy.replacement_rule == policy.market_fill_rule == policy.signal_fill_rule == "forbidden"
    assert policy.policy_id.startswith("fulp_")


@pytest.mark.parametrize(
    ("row", "date", "expected"),
    [
        ({"list_date": "20200102", "delist_date": ""}, "2020-01-01", False),
        ({"list_date": "20200102", "delist_date": ""}, "2020-01-02", True),
        ({"list_date": "20100101", "delist_date": "20250304"}, "2025-03-04", True),
        ({"list_date": "20100101", "delist_date": "20250304"}, "2025-03-05", False),
    ],
)
def test_active_boundaries(row, date, expected):
    assert active_on(row, pd.Timestamp(date)) is expected


def test_symbol_mapping():
    assert normalize_symbol("600837.SH") == "SH600837"
    assert normalize_symbol("000001.SZ") == "SZ000001"


def _fixtures(tmp_path: Path):
    universe = pd.DataFrame([
        {"rank": 1, "ts_code": "600001.SH"},
        {"rank": 2, "ts_code": "600002.SH"},
        {"rank": 3, "ts_code": "600003.SH"},
    ])
    basic = pd.DataFrame([
        {"ts_code": "600001.SH", "name": "one", "list_status": "L", "list_date": "20100101", "delist_date": ""},
        {"ts_code": "600002.SH", "name": "two", "list_status": "D", "list_date": "20100101", "delist_date": "20251231"},
        {"ts_code": "600003.SH", "name": "three", "list_status": "L", "list_date": "20270101", "delist_date": ""},
    ])
    normalized = pd.DataFrame([
        {"ts_code": "600001.SH", "symbol": "SH600001", "trade_date": pd.Timestamp("2026-01-05"), "adjusted_close": 10.0, "tradable": True},
        {"ts_code": "600001.SH", "symbol": "SH600001", "trade_date": pd.Timestamp("2026-01-06"), "adjusted_close": 11.0, "tradable": False},
    ])
    raw = pd.DataFrame([{"ts_code": "600001.SH", "trade_date": "20260106"}])
    instruments = tmp_path / "all.txt"
    instruments.write_text("SH600001\t2026-01-05\t2026-01-06\nSH600002\t2019-01-02\t2025-12-30\nSH600003\t2027-01-04\t2027-12-31\n")
    return universe, basic, normalized, raw, instruments


def test_audit_distinguishes_delisting_from_source_or_mapping(tmp_path):
    universe, basic, normalized, raw, instruments = _fixtures(tmp_path)
    audits, contract = audit_lifecycles(
        universe, basic, raw, raw, raw, normalized, instruments,
        period_start="2026-01-05",
    )
    by_code = {row["ts_code"]: row for row in audits}
    assert by_code["600002.SH"]["absence_reason"] == "DELISTED_BEFORE_PERIOD"
    assert by_code["600003.SH"]["absence_reason"] == "TUSHARE_SOURCE_ABSENCE"
    assert contract["membership_exact"] is True
    assert contract["instrument_member_count"] == 3


def test_daily_counts_separate_active_observable_tradable_and_signal_nan(tmp_path):
    universe, basic, normalized, _, _ = _fixtures(tmp_path)
    signals = {"factor": pd.DataFrame([
        {"trade_date": pd.Timestamp("2026-01-05"), "symbol": "SH600001", "pred": 1.0},
        {"trade_date": pd.Timestamp("2026-01-06"), "symbol": "SH600001", "pred": np.nan},
    ])}
    result = daily_member_counts(universe, basic, normalized, signals, start="2026-01-05", end="2026-01-06")
    assert result.locked_member_count.tolist() == [3, 3]
    assert result.active_member_count.tolist() == [1, 1]
    assert result.observable_member_count.tolist() == [1, 1]
    assert result.tradable_member_count.tolist() == [1, 0]
    assert result["factor__signal_nan_count"].tolist() == [0, 1]
    assert result.structurally_inactive_count.tolist() == [2, 2]


def test_fixed100_benchmark_dynamic_denominator_without_zero_fill():
    frame = pd.DataFrame([
        {"symbol": "A", "trade_date": "2026-01-01", "adjusted_close": 10.0},
        {"symbol": "B", "trade_date": "2026-01-01", "adjusted_close": 20.0},
        {"symbol": "A", "trade_date": "2026-01-02", "adjusted_close": 11.0},
    ])
    result = fixed100_benchmark(frame)
    assert np.isnan(result.loc[pd.Timestamp("2026-01-01")])
    assert result.loc[pd.Timestamp("2026-01-02")] == pytest.approx(0.1)


def test_artifact_kind_and_required_inventory_contract():
    from backend.services.engine.artifact_store.enums import ArtifactKind
    from backend.services.engine.tushare_agent_experiment.artifact import PREFIXES

    kind = ArtifactKind.TUSHARE_HISTORICAL_EXPERIMENT_LIFECYCLE_FOLLOWUP.value
    assert PREFIXES[kind] == ("historical_experiment_lifecycle_followup_id", "thf_")


def test_qlib_quality_gate_requires_explicit_lifecycle_contract(monkeypatch):
    from backend.services.engine.qlib_app.schemas.backtest import QlibBacktestRequest
    from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService

    monkeypatch.delenv("QLIB_SIGNAL_MIN_INSTRUMENTS", raising=False)
    service = QlibBacktestService.__new__(QlibBacktestService)
    meta = {"source": "pred_pkl", "rows_in_range": 1000, "date_count": 100,
            "instrument_count": 98, "score_nan_ratio": 0.0}
    ordinary = QlibBacktestRequest(strategy_type="TopkDropout", strategy_params={"topk": 20, "n_drop": 5},
                                   start_date="2026-01-05", end_date="2026-06-23")
    with pytest.raises(ValueError, match="98 < 100"):
        service._enforce_signal_quality(meta, ordinary)
    lifecycle = QlibBacktestRequest(
        strategy_type="TopkDropout",
        strategy_params={"topk": 20, "n_drop": 5,
                         "fixed_universe_lifecycle_policy_id": "fulp_test",
                         "locked_member_count": 100,
                         "minimum_observable_instruments": 25},
        start_date="2026-01-05", end_date="2026-06-23",
    )
    service._enforce_signal_quality(meta, lifecycle)


def test_qlib_lifecycle_capacity_cannot_be_weaker_than_topk_plus_drop():
    from backend.services.engine.qlib_app.schemas.backtest import QlibBacktestRequest
    from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService

    service = QlibBacktestService.__new__(QlibBacktestService)
    request = QlibBacktestRequest(
        strategy_type="TopkDropout",
        strategy_params={"topk": 20, "n_drop": 5,
                         "fixed_universe_lifecycle_policy_id": "fulp_test",
                         "locked_member_count": 100,
                         "minimum_observable_instruments": 24},
        start_date="2026-01-05", end_date="2026-06-23",
    )
    with pytest.raises(ValueError, match="容量门不合法"):
        service._enforce_signal_quality(
            {"source": "pred_pkl", "rows_in_range": 1000, "date_count": 100,
             "instrument_count": 98, "score_nan_ratio": 0.0}, request,
        )
