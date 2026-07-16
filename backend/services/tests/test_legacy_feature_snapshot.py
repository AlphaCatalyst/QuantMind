from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from backend.services.engine.market_data.errors import (
    DataQualityError,
    LegacyFeatureAccessError,
    SnapshotValidationError,
)
from backend.services.engine.market_data.feature_quality import evaluate_feature_matrix
from backend.services.engine.market_data.feature_snapshot import (
    LEGACY_DATASET_KIND,
    LegacyFeatureSnapshotService,
    load_feature_matrix,
    load_labels,
)
from backend.services.engine.market_data.legacy_models import LegacyFeatureRequest
from backend.services.tests.test_legacy_feature_provider import build_source, request


def test_snapshot_identity_exact_existing_manifest_inventory_reload_and_filters(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    first = service.create(provider, request())
    second = service.create(provider, request())
    assert first["status"] == "created" and second["status"] == "existing"
    assert first["snapshot_id"] == second["snapshot_id"]
    root = tmp_path / "output" / "snapshots" / first["snapshot_id"]
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["dataset_kind"] == LEGACY_DATASET_KIND
    assert manifest["feature_count"] == 2 and manifest["label_count"] == 0
    assert manifest["source_files"][0]["file_relative_path"] == "model_features_2025.parquet"
    assert (root / "source_inventory.json").is_file()
    assert service.validate(first["snapshot_id"], provider.binding)["source_lineage"] == "valid"
    loaded = load_feature_matrix(
        tmp_path / "output", first["snapshot_id"],
        symbols=("SH600000",), date_range=(date(2025, 1, 2), date(2025, 1, 3)),
        feature_columns=("feature_a",),
    )
    assert list(loaded.columns) == ["symbol", "trade_date", "feature_a"] and len(loaded) == 2


def test_different_filter_and_source_content_change_identity(tmp_path: Path) -> None:
    provider, source = build_source(tmp_path / "source")
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    base = service.create(provider, request())["snapshot_id"]
    changed_filter = service.create(provider, request(columns=("feature_a",)))["snapshot_id"]
    frame = pd.read_parquet(source)
    frame.loc[0, "feature_a"] += 1
    frame.to_parquet(source, index=False)
    changed_source = service.create(provider, request())["snapshot_id"]
    assert len({base, changed_filter, changed_source}) == 3
    assert (tmp_path / "output" / "snapshots" / base).is_dir()


def test_source_drift_detection(tmp_path: Path) -> None:
    provider, source = build_source(tmp_path / "source")
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    snapshot_id = service.create(provider, request())["snapshot_id"]
    source.write_bytes(source.read_bytes() + b"drift")
    with pytest.raises(SnapshotValidationError, match="source file drift"):
        service.validate(snapshot_id, provider.binding)
    assert service.validate(snapshot_id)["status"] == "valid"


def test_label_reader_is_explicit_and_default_reader_cannot_bypass(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    no_labels = service.create(provider, request())["snapshot_id"]
    with pytest.raises(LegacyFeatureAccessError, match="no explicitly"):
        load_labels(tmp_path / "output", no_labels)
    with pytest.raises(LegacyFeatureAccessError):
        load_feature_matrix(tmp_path / "output", no_labels, feature_columns=("label",))
    with_labels = service.create(provider, request(include_labels=True))["snapshot_id"]
    assert "label" in load_labels(tmp_path / "output", with_labels)
    assert "label" not in load_feature_matrix(tmp_path / "output", with_labels)


def test_quality_duplicate_infinity_constant_nan_and_label_leakage(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    batch = provider.read(request())
    frame = batch.frame.copy()
    frame.loc[0, "feature_a"] = float("inf")
    frame["feature_b"] = 1.0
    object.__setattr__(batch, "frame", pd.concat([frame, frame.iloc[[0]]], ignore_index=True))
    quality = evaluate_feature_matrix(batch)
    codes = {item["code"] for item in quality["issues"]}
    assert {"DUPLICATE_KEY", "INFINITY", "CONSTANT_FEATURE"} <= codes
    labeled = provider.read(request(include_labels=True))
    object.__setattr__(labeled.request, "include_labels", False)
    assert "LABEL_LEAKAGE" in {item["code"] for item in evaluate_feature_matrix(labeled)["issues"]}


def test_quality_error_blocks_snapshot_and_staging_is_cleaned(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    empty_request = request(start_date=date(2025, 2, 1), end_date=date(2025, 2, 2))
    with pytest.raises(DataQualityError):
        LegacyFeatureSnapshotService(tmp_path / "output").create(provider, empty_request)
    assert not list((tmp_path / "output").glob(".snapshot-staging-*"))


def test_snapshot_corrupt_hash_and_row_count_are_rejected(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    snapshot_id = service.create(provider, request())["snapshot_id"]
    parquet = tmp_path / "output" / "snapshots" / snapshot_id / "partitions/feature_matrix/part-00000.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"corrupt")
    with pytest.raises(SnapshotValidationError, match="hash"):
        service.validate(snapshot_id)


def test_snapshot_source_provider_and_reload_values_are_exact(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    selected = provider.read(request()).frame
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    snapshot_id = service.create(provider, request())["snapshot_id"]
    reloaded = load_feature_matrix(tmp_path / "output", snapshot_id)
    pd.testing.assert_frame_equal(selected, reloaded, check_exact=True, check_dtype=True)


def test_consumer_does_not_access_source_after_snapshot(tmp_path: Path) -> None:
    provider, source = build_source(tmp_path / "source")
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    snapshot_id = service.create(provider, request())["snapshot_id"]
    source.unlink()
    assert len(load_feature_matrix(tmp_path / "output", snapshot_id)) == 8


def test_atomic_staging_cleanup_on_parquet_failure(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    provider, _ = build_source(tmp_path / "source")

    def fail(*args, **kwargs):  # noqa: ANN002,ANN003
        raise OSError("injected legacy parquet failure")

    monkeypatch.setattr("backend.services.engine.market_data.feature_snapshot.pq.write_table", fail)
    with pytest.raises(OSError, match="injected"):
        LegacyFeatureSnapshotService(tmp_path / "output").create(provider, request())
    assert not list((tmp_path / "output").glob(".snapshot-staging-*"))


def test_legacy_cli_probe_audit_snapshot_validate_and_inspect(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    root = Path(__file__).resolve().parents[3]
    tool = root / "tools/quantmind2/market_data.py"
    base = [
        "--source-id", provider.binding.source_id,
        "--source-root", str(provider.binding.local_root),
        "--catalog-path", str(provider.catalog_path),
    ]

    def run(*args: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(tool), *args], cwd=root,
            text=True, capture_output=True, check=True,
        )
        return json.loads(completed.stdout)

    assert run("legacy-probe", *base)["available"]
    assert run("legacy-audit", *base, "--years", "2025")["feature_count"] == 2
    created = run(
        "legacy-snapshot", *base, "--years", "2025",
        "--start", "2025-01-02", "--end", "2025-01-07",
        "--symbol-limit", "2", "--output-root", str(tmp_path / "output"),
    )
    validated = run(
        "legacy-validate", *base, "--snapshot-id", created["snapshot_id"],
        "--output-root", str(tmp_path / "output"),
    )
    assert validated["source_lineage"] == "valid"
    inspected = run(
        "legacy-inspect", "--snapshot-id", created["snapshot_id"],
        "--output-root", str(tmp_path / "output"),
    )
    assert inspected["dataset_kind"] == LEGACY_DATASET_KIND and inspected["labels"] == 0
