from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.tushare_agent_experiment.artifact import (
    publish_experiment_artifact,
    validate_experiment_artifact,
)
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner,
    equal_weight_signal,
    factor_values,
    snapshot_contract,
)
from backend.services.engine.tushare_agent_experiment.memory import (
    build_memory,
    validate_memory,
)
from backend.services.engine.tushare_agent_experiment.protocol import (
    BUDGET,
    FEATURES,
    ROUNDS,
    fixed_protocol,
)


ROOT = Path(__file__).resolve().parents[3]
AUTHORITY_PATH = ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json"


def _authority() -> dict:
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def test_protocol_freezes_four_rounds_agent_budget_and_formal_portfolio() -> None:
    protocol = fixed_protocol(_authority())
    assert len(ROUNDS) == 4
    assert [row.evaluation_year for row in ROUNDS] == ["2021", "2022", "2023", "2024"]
    assert BUDGET == {
        "max_agent_calls": 2, "max_proposals": 3, "max_admitted_templates": 2,
        "max_trials_per_template": 6, "max_total_trials": 12, "max_repair_attempts": 1,
    }
    assert protocol["agent"] == {"provider": "openai_codex_cli", "model": "gpt-5.6-terra"}
    assert protocol["portfolio"]["topk"] == 20
    assert protocol["portfolio"]["n_drop"] == 5
    assert protocol["portfolio"]["rebalance_days"] == 5
    assert protocol["portfolio"]["benchmark"] == "CSI300"
    assert protocol["promotion_authority"] == "none"


def test_store_authority_bundle_is_exact_fixed100_and_has_no_legacy_read(tmp_path: Path) -> None:
    bundle = load_authority_bundle(authority_path=AUTHORITY_PATH, work_root=tmp_path)
    assert len(bundle.universe) == 100
    assert bundle.universe["rank"].tolist() == list(range(1, 101))
    assert bundle.matrix["symbol"].nunique() == 100
    assert tuple(column for column in bundle.matrix if column in FEATURES) == FEATURES
    assert bundle.matrix.trade_date.min() < pd.Timestamp("2019-01-02")
    assert bundle.matrix.trade_date.max() == pd.Timestamp("2026-06-23")
    assert bundle.sanitized_memory["historical_metrics_invalidated_by_data_authority_cutover"] is True
    assert bundle.registry["entry_count"] == 0
    assert bundle.registry["promotion_count"] == 0
    assert bundle.registry["approved_count"] == 0
    assert bundle.registry["active_count"] == 0


def test_legacy_provider_is_rejected_before_store_access(tmp_path: Path) -> None:
    authority = _authority()
    authority["provider_id"] = "quantmind-production-feature-snapshots-v1"
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(RuntimeError, match="authority"):
        load_authority_bundle(authority_path=path, work_root=tmp_path / "work")


@pytest.mark.parametrize(
    ("round_number", "research_end"),
    [(1, "2020-12-31"), (2, "2021-12-31"), (3, "2022-12-30"), (4, "2023-12-29")],
)
def test_historical_memory_field_isolation(round_number: int, research_end: str) -> None:
    memory = build_memory(
        round_number=round_number,
        research_end=research_end,
        sanitized_source={
            "historical_metrics_invalidated_by_data_authority_cutover": True,
            "retained_categories": ["template_structure", "novelty"],
        },
        prior_templates=[],
        prior_feedback=[],
        fingerprints=set(),
    )
    assert validate_memory(memory, round_number, research_end)
    rendered = json.dumps(memory).lower()
    assert "2025-" not in rendered and "2026-" not in rendered
    assert memory["daily_series_included"] is False
    for field in ("daily_ic", "holdout_2025", "holdout_2026h1", "future_qlib_result"):
        damaged = dict(memory)
        damaged[field] = []
        with pytest.raises(ValueError):
            validate_memory(damaged, round_number, research_end)


def test_dsl_uses_only_tushare_features_and_past_rows() -> None:
    dates = pd.date_range("2020-01-01", periods=8, freq="B")
    matrix = pd.DataFrame({
        "symbol": ["SH600000"] * 8 + ["SH600001"] * 8,
        "trade_date": list(dates) * 2,
        "mom_ret_1d": list(range(8)) + list(range(8, 16)),
        "liq_volume_ratio_5": 1.0,
        "style_beta_20": 1.0,
        "style_idio_vol_20": 0.1,
    }).sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    payload = {
        "schema_version": "1.0.0", "name": "past_mean", "description": "past-only rolling mean",
        "dataset_kinds": ["tushare_feature_matrix_v1"],
        "parameters": [{"name": "window", "type": "integer", "default": 2, "minimum": 2, "maximum": 4}],
        "expression": {"type": "rolling_mean", "operand": {"type": "feature", "name": "mom_ret_1d"}, "window": {"type": "parameter", "name": "window"}},
        "output": {"name": "past_mean"},
    }
    template = parse_template(payload)
    contract = snapshot_contract("tfd_test", 8)
    _, before = factor_values(template, contract, {"window": 2}, matrix)
    changed = matrix.copy()
    changed.loc[changed.trade_date == dates[-1], "mom_ret_1d"] = 1_000_000
    _, after = factor_values(template, contract, {"window": 2}, changed)
    cutoff = before.trade_date < dates[-1]
    pd.testing.assert_series_equal(before.loc[cutoff, "factor_value"], after.loc[cutoff, "factor_value"])


def test_compiled_factor_uses_public_template_id_contract() -> None:
    matrix = pd.DataFrame({
        "symbol": ["SH1", "SH2"] * 3,
        "trade_date": pd.to_datetime(["2020-01-01"] * 2 + ["2020-01-02"] * 2 + ["2020-01-03"] * 2),
        "mom_ret_1d": [1.0, 2.0, 2.0, 3.0, 3.0, 4.0],
        "liq_volume_ratio_5": 1.0,
        "style_beta_20": 1.0,
        "style_idio_vol_20": 0.1,
    })
    template = parse_template({
        "schema_version": "1.0.0", "name": "public_contract", "description": "compiled field contract",
        "dataset_kinds": ["tushare_feature_matrix_v1"],
        "parameters": [{"name": "window", "type": "integer", "default": 2, "minimum": 2, "maximum": 3}],
        "expression": {"type": "rolling_mean", "operand": {"type": "feature", "name": "mom_ret_1d"}, "window": {"type": "parameter", "name": "window"}},
        "output": {"name": "public_contract"},
    })
    compiled, _ = factor_values(template, snapshot_contract("tfd_test", 3), {"window": 2}, matrix)
    assert compiled.template_id.startswith("ft_")
    assert compiled.factor_instance_id.startswith("fi_")


def test_equal_weight_combo_has_no_weight_optimization(tmp_path: Path) -> None:
    keys = pd.DataFrame({"symbol": ["SH1", "SH2", "SH1", "SH2"], "trade_date": pd.to_datetime(["2026-01-05", "2026-01-05", "2026-01-06", "2026-01-06"])})
    first = keys.assign(pred=[1.0, 2.0, 2.0, 3.0])
    second = keys.assign(pred=[3.0, 1.0, 4.0, 2.0])
    p1, p2 = tmp_path / "one.parquet", tmp_path / "two.parquet"
    first.to_parquet(p1, index=False); second.to_parquet(p2, index=False)
    output = equal_weight_signal({"one": p1, "two": p2}, tmp_path / "combo.parquet")
    result = pd.read_parquet(output)
    assert result.pred.notna().all()
    assert np.allclose(result.groupby("trade_date").pred.mean(), 0.0)


def test_formal_qlib_quality_rejection_is_evidence_not_a_gate_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.services.engine.historical_agent_experiment.qlib_runner as qlib_runner

    monkeypatch.setattr(
        qlib_runner,
        "run_formal_backtest_sync",
        lambda *args, **kwargs: {
            "status": "failed",
            "error_message": "signal quality precheck: valid symbols insufficient (98 < 100)",
        },
    )

    class Exchange:
        @staticmethod
        def deal_order(*args, **kwargs):
            return 0.0, 0.0, 0.0

    runner = object.__new__(FormalQlibRunner)
    runner.service = object()
    runner.cn_exchange = SimpleNamespace(CnExchange=Exchange)
    runner.cache_root = tmp_path / "cache"
    runner.benchmark = pd.Series(dtype=float)
    runner.calls = 0
    signal = tmp_path / "signal.parquet"
    signal.write_bytes(b"immutable-signal-evidence")

    first = runner.run(signal, "2026-01-05", "2026-06-23")
    second = runner.run(signal, "2026-01-05", "2026-06-23")

    assert first == second
    assert first["status"] == "rejected"
    assert first["error_code"] == "FORMAL_QLIB_SIGNAL_QUALITY_REJECTED"
    assert "98 < 100" in first["error_message"]
    assert first["net_return"] is None
    assert first["formal_chain"][-1] == "CnExchange"
    assert runner.calls == 1


def test_artifacts_enforce_lock_holdout_registry_and_authority(tmp_path: Path) -> None:
    lock = publish_experiment_artifact(tmp_path, "tushare_historical_round_lock", {
        "provider_id": "tushare-pro-v1", "protocol_id": "thp_test", "locked_before_evaluation": True,
        "promotion_writes": 0,
    })
    assert validate_experiment_artifact(Path(lock["path"]), lock["round_lock_id"])["status"] == "valid"
    bad = Path(lock["path"]) / "manifest.json"
    payload = json.loads(bad.read_text()); payload["identity"]["locked_before_evaluation"] = False
    bad.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        validate_experiment_artifact(Path(lock["path"]), lock["round_lock_id"])


def test_cli_has_no_token_argument() -> None:
    source = (ROOT / "tools/quantmind2/tushare_agent_experiment.py").read_text(encoding="utf-8")
    assert "--token" not in source
    assert "TUSHARE_TOKEN" not in source
