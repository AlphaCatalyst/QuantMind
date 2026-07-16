from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from backend.services.engine.market_data.errors import (
    InvalidMarketDataRequest,
    LegacyFeatureAccessError,
    LegacyFeatureBindingError,
    LegacyFeatureSchemaError,
    ProviderUnavailableError,
)
from backend.services.engine.market_data.legacy_models import (
    ColumnRole,
    FeatureAccessPolicy,
    LegacyFeatureRequest,
    LegacyFeatureSourceBinding,
)
from backend.services.engine.market_data.providers import LegacyFeatureProvider


def build_source(root: Path, *, year: int = 2025, drift: bool = False) -> tuple[LegacyFeatureProvider, Path]:
    root.mkdir(parents=True, exist_ok=True)
    catalog = root.parent / "catalog.json"
    catalog.write_text(json.dumps({"categories": [{"features": [
        {"key": "feature_a", "enabled": True},
        {"key": "feature_b", "enabled": True},
    ]}]}), encoding="utf-8")
    rows = []
    for day in pd.date_range(f"{year}-01-02", periods=4, freq="B"):
        for index, symbol in enumerate(("SH600000", "SZ000001", "SZ000002")):
            rows.append({
                "symbol": symbol,
                "trade_date": day,
                "feature_a": float(index + day.day),
                "feature_b": float("nan") if index == 2 else float(index),
                "label": float(index) / 10,
                "weight": 1.0,
                "future_return": 0.1,
                "mystery": 7.0,
            })
    frame = pd.DataFrame(rows)
    if drift:
        frame["feature_b"] = frame["feature_b"].astype("float32")
    path = root / f"model_features_{year}.parquet"
    frame.to_parquet(path, index=False, engine="pyarrow")
    binding = LegacyFeatureSourceBinding(
        "quantmind-production-feature-snapshots-v1",
        root,
        "docker-training-load-local-parquet-v1",
    )
    return LegacyFeatureProvider(binding, catalog), path


def request(**changes) -> LegacyFeatureRequest:  # noqa: ANN003
    values = {
        "source_id": "quantmind-production-feature-snapshots-v1",
        "years": (2025,),
        "start_date": date(2025, 1, 2),
        "end_date": date(2025, 1, 7),
        "symbol_limit": 2,
    }
    values.update(changes)
    return LegacyFeatureRequest(**values)


def test_explicit_binding_probe_inventory_hash_and_read_only(tmp_path: Path) -> None:
    provider, source = build_source(tmp_path / "source")
    before = source.read_bytes()
    assert provider.probe().available
    inventory = provider.discover((2025,))
    assert inventory.files[0]["file_relative_path"] == "model_features_2025.parquet"
    assert inventory.files[0]["sha256"]
    assert inventory.files[0]["row_count"] == 12
    batch = provider.read(request())
    assert source.read_bytes() == before
    assert batch.selected_symbols == ("SH600000", "SZ000001")
    assert list(batch.frame.columns) == ["symbol", "trade_date", "feature_a", "feature_b"]


def test_missing_root_missing_year_and_source_id_fail_safely(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"categories":[{"features":[{"key":"x"}]}]}')
    binding = LegacyFeatureSourceBinding("source-v1", tmp_path / "missing", "loader-v1")
    provider = LegacyFeatureProvider(binding, catalog)
    assert not provider.probe().available
    with pytest.raises(ProviderUnavailableError):
        provider.discover((2025,))
    provider, _ = build_source(tmp_path / "source")
    with pytest.raises(ProviderUnavailableError):
        provider.discover((2024,))
    with pytest.raises(LegacyFeatureBindingError):
        provider.read(request(source_id="different-source"))


def test_binding_path_escape_is_rejected(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    outside = tmp_path / "outside.parquet"
    pd.DataFrame({"symbol": [], "trade_date": []}).to_parquet(outside, index=False)
    (tmp_path / "source" / "model_features_2024.parquet").symlink_to(outside)
    with pytest.raises(LegacyFeatureBindingError, match="escapes"):
        provider.discover((2024,))


def test_duplicate_year_invalid_range_and_mutually_exclusive_selection_fail() -> None:
    with pytest.raises(InvalidMarketDataRequest, match="duplicates"):
        request(years=(2025, 2025))
    with pytest.raises(InvalidMarketDataRequest, match="start_date"):
        request(start_date=date(2025, 2, 1), end_date=date(2025, 1, 1))
    with pytest.raises(InvalidMarketDataRequest, match="mutually"):
        request(symbols=("SH600000",), symbol_limit=1)


def test_schema_roles_policy_and_label_isolation(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    schema = provider.discover((2025,)).schema
    roles = schema.role_map()
    assert roles["symbol"] == ColumnRole.KEY.value
    assert roles["feature_a"] == ColumnRole.FEATURE.value
    assert roles["label"] == ColumnRole.LABEL.value
    assert roles["weight"] == ColumnRole.WEIGHT.value
    assert roles["future_return"] == ColumnRole.FORBIDDEN.value
    assert roles["mystery"] == ColumnRole.UNKNOWN.value
    policy = FeatureAccessPolicy.from_schema(schema)
    assert "feature_a" in policy.research_features and "label" in policy.labels
    assert "future_return" in policy.forbidden and "mystery" in policy.unknown
    default = provider.read(request())
    assert "label" not in default.frame and "future_return" not in default.frame
    with_labels = provider.read(request(include_labels=True))
    assert "label" in with_labels.frame and "weight" not in with_labels.frame


@pytest.mark.parametrize("column", ["label", "weight", "future_return", "mystery", "missing"])
def test_non_feature_columns_cannot_bypass_access_policy(tmp_path: Path, column: str) -> None:
    provider, _ = build_source(tmp_path / "source")
    with pytest.raises(LegacyFeatureAccessError):
        provider.read(request(columns=(column,)))


def test_year_date_symbol_columns_and_deterministic_limit_filters(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    batch = provider.read(request(
        start_date=date(2025, 1, 3),
        end_date=date(2025, 1, 6),
        columns=("feature_b",),
    ))
    assert list(batch.frame.columns) == ["symbol", "trade_date", "feature_b"]
    assert len(batch.frame) == 4
    explicit = provider.read(request(symbol_limit=None, symbols=("SZ000002",)))
    assert set(explicit.frame["symbol"]) == {"SZ000002"}


def test_empty_result_is_returned_for_quality_gate(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source")
    batch = provider.read(request(start_date=date(2025, 2, 1), end_date=date(2025, 2, 2)))
    assert batch.frame.empty


def test_multi_year_schema_and_dtype_drift_is_rejected(tmp_path: Path) -> None:
    provider, _ = build_source(tmp_path / "source", year=2024)
    build_source(tmp_path / "source", year=2025, drift=True)
    with pytest.raises(LegacyFeatureSchemaError, match="drift"):
        provider.discover((2024, 2025))
