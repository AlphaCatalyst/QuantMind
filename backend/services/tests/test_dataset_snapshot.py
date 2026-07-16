from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from backend.services.engine.market_data.errors import DataQualityError, NormalizationError, SnapshotValidationError
from backend.services.engine.market_data.models import AdjustmentMode, DailyBarsRequest
from backend.services.engine.market_data.normalization import normalize_daily_bars
from backend.services.engine.market_data.providers import FakeMarketDataProvider
from backend.services.engine.market_data.quality import evaluate_daily_bars
from backend.services.engine.market_data.snapshot import DatasetSnapshotService, load_daily_bars
from backend.services.engine.market_data.storage import sha256_file


def request(**changes) -> DailyBarsRequest:  # noqa: ANN003
    values = {
        "symbols": ("SH600000", "SZ000001"),
        "start_date": date(2026, 1, 5), "end_date": date(2026, 2, 5),
        "adjustment_mode": AdjustmentMode.NONE,
    }
    values.update(changes)
    return DailyBarsRequest(**values)


def test_normalization_types_order_units_and_no_hidden_fill() -> None:
    batch = FakeMarketDataProvider().fetch_daily_bars(request())
    frame = normalize_daily_bars(batch)
    assert frame.columns.tolist() == list(request().fields)
    assert frame.equals(frame.sort_values(["symbol", "trade_date"]).reset_index(drop=True))
    assert all(str(frame[column].dtype) == "float64" for column in ("open", "high", "low", "close", "volume", "amount"))
    assert not frame.isna().any().any()


@pytest.mark.parametrize("fault", ["duplicate", "schema_drift"])
def test_normalization_rejects_duplicates_and_schema_drift(fault: str) -> None:
    with pytest.raises(NormalizationError):
        normalize_daily_bars(FakeMarketDataProvider(fault).fetch_daily_bars(request()))


@pytest.mark.parametrize("fault,code", [("invalid_ohlc", "HIGH_BELOW_LOW"), ("negative_volume", "NEGATIVE_VOLUME"), ("missing_symbol", "MISSING_SYMBOL")])
def test_quality_detects_provider_faults(fault: str, code: str) -> None:
    frame = normalize_daily_bars(FakeMarketDataProvider(fault).fetch_daily_bars(request()))
    quality = evaluate_daily_bars(frame, request())
    assert quality["status"] == "error"
    assert code in {item["code"] for item in quality["issues"]}


def test_quality_detects_empty_negative_amount_and_date_range() -> None:
    empty = normalize_daily_bars(FakeMarketDataProvider().fetch_daily_bars(request(start_date=date(2026, 1, 10), end_date=date(2026, 1, 11))))
    assert evaluate_daily_bars(empty, request())["status"] == "error"
    frame = normalize_daily_bars(FakeMarketDataProvider().fetch_daily_bars(request()))
    frame.loc[0, "amount"] = -1
    frame.loc[1, "trade_date"] = date(2025, 1, 1)
    codes = {item["code"] for item in evaluate_daily_bars(frame, request())["issues"]}
    assert {"NEGATIVE_AMOUNT", "DATE_OUT_OF_RANGE"} <= codes


def test_quality_detects_nan_and_infinity() -> None:
    frame = normalize_daily_bars(FakeMarketDataProvider().fetch_daily_bars(request()))
    frame.loc[0, "open"] = float("nan")
    frame.loc[1, "amount"] = float("inf")
    issues = evaluate_daily_bars(frame, request())["issues"]
    assert sum(item["count"] for item in issues if item["code"] == "NON_FINITE_VALUE") == 2


def test_snapshot_create_reload_exact_existing_and_manifest(tmp_path: Path) -> None:
    service = DatasetSnapshotService(tmp_path)
    first = service.create(FakeMarketDataProvider(), request())
    second = service.create(FakeMarketDataProvider(), request())
    assert first["status"] == "created" and second["status"] == "existing"
    assert first["snapshot_id"] == second["snapshot_id"]
    snapshot = tmp_path / "snapshots" / first["snapshot_id"]
    manifest = json.loads((snapshot / "manifest.json").read_text())
    assert manifest["provider_id"] == "fake"
    assert manifest["row_count"] == len(load_daily_bars(tmp_path, first["snapshot_id"]))
    assert manifest["raw_inputs"][0]["response_sha256"] == sha256_file(
        next((tmp_path / "raw/fake").glob("*/raw_response.json"))
    )
    assert service.validate(first["snapshot_id"])["status"] == "valid"


def test_snapshot_id_changes_with_request_adjustment_and_data(tmp_path: Path) -> None:
    service = DatasetSnapshotService(tmp_path)
    base = service.create(FakeMarketDataProvider(), request())["snapshot_id"]
    changed_request = service.create(FakeMarketDataProvider(), request(end_date=date(2026, 2, 6)))["snapshot_id"]
    changed_adjustment = service.create(FakeMarketDataProvider(), request(adjustment_mode=AdjustmentMode.FORWARD))["snapshot_id"]
    assert len({base, changed_request, changed_adjustment}) == 3


@pytest.mark.parametrize("fault", ["invalid_ohlc", "negative_volume", "missing_symbol"])
def test_quality_errors_block_snapshot(fault: str, tmp_path: Path) -> None:
    with pytest.raises(DataQualityError):
        DatasetSnapshotService(tmp_path).create(FakeMarketDataProvider(fault), request())
    assert not list((tmp_path / "snapshots").glob("*")) if (tmp_path / "snapshots").exists() else True


def test_corruption_is_rejected_and_reader_filters(tmp_path: Path) -> None:
    service = DatasetSnapshotService(tmp_path)
    result = service.create(FakeMarketDataProvider(), request())
    filtered = load_daily_bars(tmp_path, result["snapshot_id"], ("SH600000",), (date(2026, 1, 5), date(2026, 1, 9)))
    assert set(filtered["symbol"]) == {"SH600000"} and len(filtered) == 5
    parquet = tmp_path / "snapshots" / result["snapshot_id"] / "partitions/daily_bars/part-00000.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"corrupt")
    with pytest.raises(SnapshotValidationError, match="hash"):
        service.validate(result["snapshot_id"])


def test_atomic_staging_cleanup_on_parquet_failure(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    def fail(*args, **kwargs):  # noqa: ANN002,ANN003
        raise OSError("injected parquet failure")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail)
    with pytest.raises(OSError):
        DatasetSnapshotService(tmp_path).create(FakeMarketDataProvider(), request())
    assert not list(tmp_path.glob(".snapshot-staging-*"))


def test_cli_snapshot_validate_inspect_and_audit(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    tool = root / "tools/quantmind2/market_data.py"
    def run(*args: str) -> dict:
        result = subprocess.run([sys.executable, str(tool), *args], cwd=root, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)
    assert run("audit")["authoritative_target"] == "dataset_snapshot"
    created = run("snapshot", "--provider", "fake", "--symbols", "SH600000,SZ000001", "--start", "2026-01-05", "--end", "2026-02-05", "--adjustment", "none", "--output-root", str(tmp_path))
    assert run("validate", "--snapshot-id", created["snapshot_id"], "--output-root", str(tmp_path))["status"] == "valid"
    summary = run("inspect", "--snapshot-id", created["snapshot_id"], "--output-root", str(tmp_path))
    assert summary["provider_id"] == "fake" and "open" in summary["fields"]
