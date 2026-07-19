from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.tushare_cutover.client import TushareClient, TushareError
from backend.services.engine.tushare_cutover.pipeline import (
    ARTIFACT_PREFIXES,
    TushareCutoverPipeline,
    _artifact_id,
    _publish_directory,
    validate_tushare_artifact,
)
from tools.quantmind2.tushare_data_cutover import parser


class _Response:
    status = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_client_uses_environment_and_redacts_upstream_error(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "unit-test-only-secret")
    client = TushareClient(
        minimum_interval_seconds=0,
        opener=lambda *_args, **_kwargs: _Response({"code": -1, "msg": "request carried unit-test-only-secret"}),
    )
    with pytest.raises(TushareError) as captured:
        client.query("daily", fields=("ts_code",), ts_code="000001.SZ")
    assert "unit-test-only-secret" not in str(captured.value)
    assert client.credential_present is True


def test_cli_has_no_token_argument():
    help_text = parser().format_help()
    assert "--token" not in help_text
    with pytest.raises(SystemExit):
        parser().parse_args(["--token", "forbidden", "probe"])


def test_tushare_artifact_identity_and_hash_validation(tmp_path):
    artifact = _publish_directory(
        tmp_path,
        "tushare_trade_calendar",
        {"schema_version": "test-v1", "provider_id": "tushare-pro-v1", "row_count": 1},
        {"trade_calendar.parquet": pd.DataFrame([{"cal_date": "20190102", "is_open": 1}]), "quality.json": {"valid": True}},
    )
    result = validate_tushare_artifact(Path(artifact["path"]), _artifact_id(artifact), expected_kind="tushare_trade_calendar")
    assert result["status"] == "valid"
    assert _artifact_id(artifact).startswith(ARTIFACT_PREFIXES["tushare_trade_calendar"])
    (Path(artifact["path"]) / "quality.json").write_text("{}\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_tushare_artifact(Path(artifact["path"]), _artifact_id(artifact))


def test_features_are_computed_across_year_boundary(tmp_path):
    dates = pd.bdate_range("2018-10-01", periods=90)
    rows = []
    for offset, symbol in enumerate(("SH600000", "SZ000001"), 1):
        returns = 0.001 * np.sin(np.arange(len(dates)) / 4 + offset) + 0.0002 * offset
        prices = 10 * np.cumprod(1 + returns)
        for index, date in enumerate(dates):
            rows.append({"symbol": symbol, "ts_code": (symbol[2:] + "." + symbol[:2]), "trade_date": date, "adjusted_close": prices[index], "vol": 1000 + index, "open": prices[index], "high": prices[index], "low": prices[index], "close": prices[index], "pre_close": prices[index - 1] if index else prices[index], "amount": 10000, "adj_factor": 1.0, "turnover_rate": 1.0, "circ_mv": 1.0, "total_mv": 1.0, "adjusted_open": prices[index], "adjusted_high": prices[index], "adjusted_low": prices[index], "tradable": True})
    bars = pd.DataFrame(rows)
    benchmark = pd.DataFrame({"ts_code": "000300.SH", "trade_date": dates.strftime("%Y%m%d"), "close": 100 * np.cumprod(1 + 0.001 * np.cos(np.arange(len(dates)) / 5)), "pre_close": np.r_[100.0, (100 * np.cumprod(1 + 0.001 * np.cos(np.arange(len(dates)) / 5)))[:-1]]})
    normalized = _publish_directory(tmp_path, "tushare_normalized_bars", {"schema_version": "test", "row_count": len(bars)}, {"normalized_bars.parquet": bars})
    market = _publish_directory(tmp_path, "tushare_market_benchmark", {"schema_version": "test", "row_count": len(benchmark)}, {"index_daily.parquet": benchmark})
    pipeline = TushareCutoverPipeline(tmp_path / "work", store_root=tmp_path / "store")
    result = pipeline.build_features(normalized, market)
    features = pd.read_parquet(Path(result["path"]) / "features.parquet")
    january = features[features.trade_date.dt.year == 2019]
    assert not january.empty
    assert january.groupby("symbol").head(1).style_idio_vol_20.notna().all()


def test_purge_rejects_overbroad_root(tmp_path):
    pipeline = TushareCutoverPipeline(tmp_path / "work", store_root=tmp_path / "store")
    with pytest.raises(ValueError, match="overbroad"):
        pipeline.plan_purge([Path.home()])
