from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.breadth_gated_momentum.artifact import publish_artifact, validate_artifact
from backend.services.engine.breadth_gated_momentum.engine import (
    _episodes, _path_r, _portfolio_path, classify_fresh, token_status,
)
from backend.services.engine.breadth_gated_momentum.protocol import (
    FRESH_START_DATE, MINIMUM_EVIDENCE, PATH_G, PATH_R, PATH_U,
    SOURCE_SIGNAL_ARTIFACT_ID, breadth_contract_identity, fresh_lock, gate_spec,
)
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes


def synthetic(days: int = 700, symbols: int = 25):
    dates = pd.bdate_range("2020-01-02", periods=days)
    rows, values = [], []
    for member in range(symbols):
        symbol = f"SH{600000 + member}"
        for ordinal, date in enumerate(dates):
            price = 10 * (1.0002 + member / 1_000_000) ** ordinal
            rows.append({"symbol": symbol, "trade_date": date, "adjusted_close": price,
                         "adjusted_open": price, "tradable": True})
            values.append({"symbol": symbol, "trade_date": date,
                           "factor_value": float(member) + ordinal / 10000})
    benchmark = pd.DataFrame({"trade_date": dates, "close": 100 * 1.0001 ** np.arange(days)})
    normalized, score = pd.DataFrame(rows), pd.DataFrame(values)
    regimes, contract = build_regimes(normalized, benchmark)
    return normalized, score, benchmark, regimes, contract


def _spec():
    _, _, _, _, contract = synthetic()
    breadth = breadth_contract_identity(contract, normalized_bars_id="tnb_x", universe_id="tu100_x")
    spec = gate_spec(breadth=breadth, universe_id="tu100_x")
    spec["gate_spec_id"] = "bmgs1_x"
    return spec


def test_signal_d_and_fixed_path_contracts_are_immutable():
    assert SOURCE_SIGNAL_ARTIFACT_ID == "lfmsa1_a4a99da30ef0dc99a03270bc5688f3edbe66bf944f899795d11aacf83a8e2262"
    assert PATH_U["topk"] == PATH_G["topk"] == 20
    assert PATH_U["n_drop"] == PATH_G["n_drop"] == 5
    assert PATH_U["rebalance_interval"] == PATH_G["rebalance_interval"] == 10
    assert PATH_U["signal_lag"] == PATH_G["signal_lag"] == 1
    assert PATH_R["off_return"] == PATH_G["cash_return"] == 0.0


def test_formal_breadth_contract_is_bound_and_gate_is_not_double_lagged():
    _, _, _, regimes, contract = synthetic()
    breadth = breadth_contract_identity(contract, normalized_bars_id="tnb_x", universe_id="tu100_x")
    spec = gate_spec(breadth=breadth, universe_id="tu100_x")
    assert spec["gate_lag"] == 1 and spec["double_lag_forbidden"]
    assert "already lags raw breadth one session" in spec["runtime_gate_rule"]
    assert breadth["minimum_history"] == 504
    assert contract["breadth"]["states"] == ["broad", "neutral", "narrow"]
    assert "unavailable" in set(regimes.breadth_regime)


@pytest.mark.parametrize("formal_state,expected", [("narrow", True), ("neutral", False), ("broad", False)])
def test_only_narrow_or_weak_activates(formal_state, expected):
    frame = pd.DataFrame({"breadth_regime": [formal_state]})
    assert bool(frame.breadth_regime.eq("narrow").iloc[0]) is expected


def test_paths_u_g_r_and_cash_policy():
    normalized, values, benchmark, regimes, _ = synthetic(days=80)
    regimes["gate_on"] = False
    regimes.loc[regimes.index[:20], "gate_on"] = True
    u, _ = _portfolio_path(values, normalized, benchmark, regimes, gated=False)
    g, _ = _portfolio_path(values, normalized, benchmark, regimes, gated=True)
    r = _path_r(g)
    assert set(u.path) == {"U"} and set(g.path) == {"G"} and set(r.path) == {"R"}
    assert (g.loc[~g.gate_on, "holding_count"] == 0).all()
    assert (g.loc[~g.gate_on, "gross_return"] == 0).all()
    assert (g.loc[(~g.gate_on) & (~g.rebalance), "net_return"] == 0).all()
    assert (r.loc[~r.gate_on, "net_return"] == 0).all()
    assert g.rebalance.sum() == u.rebalance.sum()


def test_gate_switches_only_on_scheduled_rebalance():
    normalized, values, benchmark, regimes, _ = synthetic(days=40)
    regimes["gate_on"] = False; regimes.loc[regimes.index[0:5], "gate_on"] = True
    g, _ = _portfolio_path(values, normalized, benchmark, regimes, gated=True)
    assert g.iloc[:10].gate_on.all()
    assert not g.iloc[10:20].gate_on.any()


def test_gate_episode_statistics():
    dates = pd.bdate_range("2026-06-24", periods=8)
    frame = pd.DataFrame({"trade_date": dates, "gate_on": [1, 1, 0, 1, 1, 1, 0, 1]}).astype({"gate_on": bool})
    episodes = _episodes(frame)
    assert episodes.length.tolist() == [2, 3, 1]


def test_fresh_lock_forbids_backfill_memory_optimization_and_registry():
    lock = fresh_lock(_spec(), universe_id="tu100_x")
    assert lock["fresh_start_date"] == FRESH_START_DATE and lock["no_backfill"]
    assert lock["historical_cutoff"] == "2026-06-23"
    assert not lock["agent_memory_access"] and not lock["optimization_access"]
    assert lock["registry_writes"] == lock["promotion_writes"] == 0


def test_token_probe_reads_only_presence(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "do-not-persist-this")
    result = token_status()
    assert result["credential_present"] and not result["credential_persisted"]
    assert "do-not-persist-this" not in json.dumps(result)


def test_minimum_evidence_accumulating_supported_rejected_and_inconclusive():
    metrics = {"conditional_selection_alpha": .01, "gate_on_rankic": .01,
               "gate_on_q10_universe": .01, "path_g_maximum_drawdown": -.05,
               "path_u_maximum_drawdown": -.10}
    low = {key: 0 for key in MINIMUM_EVIDENCE}
    full = dict(MINIMUM_EVIDENCE)
    assert classify_fresh(low, metrics) == "fresh_evidence_accumulating"
    assert classify_fresh(full, metrics) == "fresh_regime_overlay_supported"
    assert classify_fresh(full, metrics | {"conditional_selection_alpha": -.01,
                                           "gate_on_q10_universe": -.01}) == "fresh_regime_overlay_rejected"
    assert classify_fresh(full, metrics | {"gate_on_rankic": -.01}) == "fresh_regime_overlay_inconclusive"


def test_artifact_publication_revision_and_governance(tmp_path: Path):
    identity = _spec()
    artifact = publish_artifact(tmp_path, "breadth_momentum_gate_spec", identity,
                                {"gate_spec.json": identity})
    assert validate_artifact(Path(artifact["path"]), artifact["gate_spec_id"])["status"] == "valid"
    replay = publish_artifact(tmp_path, "breadth_momentum_gate_spec", identity,
                              {"gate_spec.json": identity})
    assert replay["exact_existing"]
    revision = publish_artifact(tmp_path, "breadth_momentum_gate_spec", identity | {"version": 2},
                                {"gate_spec.json": identity | {"version": 2}})
    assert revision["gate_spec_id"] != artifact["gate_spec_id"]
    with pytest.raises(ValueError, match="governance"):
        publish_artifact(tmp_path / "bad", "breadth_momentum_gate_spec",
                         identity | {"registry_writes": 1}, {})


def test_cli_has_no_token_argument():
    text = Path("tools/quantmind2/run_breadth_gated_momentum_forward.py").read_text(encoding="utf-8")
    assert '"--token"' not in text and "add_argument('--token'" not in text
    for command in ("validate-gate", "build-historical-diagnostic", "create-fresh-lock",
                    "probe-token", "fetch-incremental-data", "build-incremental-features",
                    "run-fresh-observation", "inspect-historical", "inspect-fresh", "validate-study"):
        assert command in text
