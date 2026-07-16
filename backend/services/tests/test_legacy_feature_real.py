from __future__ import annotations

from datetime import date
import importlib.util
import os
from pathlib import Path
import sys
import types

import pandas as pd
import pytest

from backend.services.engine.market_data.feature_snapshot import (
    LegacyFeatureSnapshotService,
    load_feature_matrix,
)
from backend.services.engine.market_data.legacy_models import (
    LegacyFeatureRequest,
    LegacyFeatureSourceBinding,
)
from backend.services.engine.market_data.providers import LegacyFeatureProvider


REAL_ROOT = os.getenv("QM2_LEGACY_REAL_ROOT")
pytestmark = pytest.mark.skipif(not REAL_ROOT, reason="QM2_LEGACY_REAL_ROOT is not configured")


def _load_actual_production_reader(repository_root: Path):  # noqa: ANN202
    previous = sys.modules.get("lightgbm")
    sys.modules["lightgbm"] = types.ModuleType("lightgbm")
    try:
        path = repository_root / "docker" / "training" / "train.py"
        spec = importlib.util.spec_from_file_location("qm2_actual_training_reader", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._load_local_parquet
    finally:
        if previous is None:
            sys.modules.pop("lightgbm", None)
        else:
            sys.modules["lightgbm"] = previous


def test_real_2025_snapshot_and_actual_training_loader_parity(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[3]
    source_root = Path(str(REAL_ROOT)).resolve()
    binding = LegacyFeatureSourceBinding(
        "quantmind-production-feature-snapshots-v1",
        source_root,
        "docker-training-load-local-parquet-v1",
    )
    provider = LegacyFeatureProvider(
        binding,
        repository_root / "config/features/model_training_feature_catalog_v1.json",
    )
    request = LegacyFeatureRequest(
        source_id=binding.source_id,
        years=(2025,),
        start_date=date(2025, 1, 2),
        end_date=date(2025, 4, 3),
        symbol_limit=100,
    )
    selected = provider.read(request)
    assert len(selected.inventory.schema.research_feature_columns) == 152
    assert selected.inventory.schema.label_columns == ()
    assert selected.inventory.schema.unknown_columns == ("ind_ret_60d",)
    assert len(selected.selected_symbols) == 100
    service = LegacyFeatureSnapshotService(tmp_path / "output")
    first = service.create(provider, request)
    second = service.create(provider, request)
    assert second["status"] == "existing" and first["snapshot_id"] == second["snapshot_id"]
    validation = service.validate(first["snapshot_id"], binding)
    assert validation["source_lineage"] == "valid"
    reloaded = load_feature_matrix(tmp_path / "output", first["snapshot_id"])
    pd.testing.assert_frame_equal(selected.frame, reloaded, check_exact=True, check_dtype=True)

    parity_features = ["open", "close", "mom_ret_20d", "style_bp", "ind_strength_20"]
    actual_reader = _load_actual_production_reader(repository_root)
    production = actual_reader(
        source_root,
        2025,
        ["symbol", "trade_date", *parity_features],
        clip_start=pd.Timestamp(request.start_date),
        clip_end=pd.Timestamp(request.end_date),
    )
    assert production is not None
    production = production[production["symbol"].isin(selected.selected_symbols)]
    production = production.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
    provider_subset = selected.frame[["symbol", "trade_date", *parity_features]].copy()
    for name in parity_features:
        provider_subset[name] = provider_subset[name].astype("float32")
    pd.testing.assert_frame_equal(production, provider_subset, check_exact=True, check_dtype=True)

    different = LegacyFeatureRequest(
        source_id=binding.source_id,
        years=(2025,), start_date=request.start_date, end_date=request.end_date,
        columns=("open", "close"), symbol_limit=100,
    )
    assert service.create(provider, different)["snapshot_id"] != first["snapshot_id"]
