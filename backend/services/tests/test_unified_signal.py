from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.artifact_runtime.config import resolve_runtime_context
from backend.services.engine.artifact_runtime.publisher import publish_domain_artifact
from backend.services.engine.artifact_runtime.resolver import resolve_artifact
from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config
from backend.services.engine.unified_signal.errors import UnifiedSignalError
from backend.services.engine.unified_signal.service import build_unified_signal, parse_spec, signal_spec_id


def payload(inputs=1, **overrides):
    rows = [{
        "template_id": f"ft_{i}", "factor_instance_id": f"fi_{i}", "factor_values_id": f"tfv_{i}",
        "source_artifact_kind": "tushare_historical_round_lock", "source_artifact_id": f"thl_{i}",
        "source_relative_path": f"factor_values/fi_{i}.parquet", "orientation": -1 if i == 1 else 1,
        "values_are_oriented": False,
        "dataset_id": "tfd_x", "universe_id": "tu100_x", "evidence_class": "research_diagnostic",
        "canonicality": "research_diagnostic",
    } for i in range(inputs)]
    value = {
        "schema_version": "1.0.0", "name": "test", "description": "test", "inputs": rows,
        "transformation": "cs_zscore", "combination": "single_factor" if inputs == 1 else "equal_weight",
        "weights": [1.0] if inputs == 1 else [], "missing_policy": "require_all_factors",
        "universe_id": "tu100_x", "dataset_id": "tfd_x", "start_date": "2020-01-01", "end_date": "2020-01-03",
        "data_authority": "tushare-pro-v1", "predictive_claim": False, "eligible_for_production": False,
    }
    value.update(overrides)
    return value


def sources(tmp_path: Path, inputs=1, duplicate=False, infinity=False):
    result = {}
    for i in range(inputs):
        root = tmp_path / f"thl_{i}"
        path = root / "factor_values" / f"fi_{i}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"symbol": s, "trade_date": d, "pred": float(v + i)} for d in pd.date_range("2020-01-01", periods=3) for s, v in (("A", 1), ("B", 2), ("C", 3))]
        if i == 1:
            rows[0]["pred"] = np.nan
        if duplicate:
            rows.append(dict(rows[0]))
        if infinity:
            rows[0]["pred"] = np.inf
        pd.DataFrame(rows).to_parquet(path, index=False)
        result[f"thl_{i}"] = root
    return result


def test_single_factor_orientation_zscore_and_deterministic_identity(tmp_path):
    spec = parse_spec(payload())
    first = build_unified_signal(spec, sources(tmp_path), tmp_path / "out")
    second = build_unified_signal(spec, sources(tmp_path), tmp_path / "out")
    assert first["unified_signal_artifact_id"] == second["unified_signal_artifact_id"]
    assert second["exact_existing"] is True
    frame = pd.read_parquet(Path(first["path"]) / "signal.parquet")
    assert frame.groupby("trade_date")["score"].mean().abs().max() < 1e-12
    assert signal_spec_id(spec).startswith("uss_")


def test_multi_factor_equal_weight_require_all_and_orientation(tmp_path):
    spec = parse_spec(payload(2))
    result = build_unified_signal(spec, sources(tmp_path, 2), tmp_path / "out")
    frame = pd.read_parquet(Path(result["path"]) / "signal.parquet")
    assert pd.isna(frame.loc[(frame.symbol == "A") & (frame.trade_date == pd.Timestamp("2020-01-01")), "score"]).all()
    quality = json.loads((Path(result["path"]) / "quality.json").read_text())
    assert quality["nan_cells"] == 1


@pytest.mark.parametrize("kind", ["duplicate", "infinity"])
def test_rejects_duplicate_or_infinity(tmp_path, kind):
    spec = parse_spec(payload())
    with pytest.raises(UnifiedSignalError):
        build_unified_signal(spec, sources(tmp_path, duplicate=kind == "duplicate", infinity=kind == "infinity"), tmp_path / "out")


def test_fixed_weight_and_winsor_contract():
    spec = parse_spec(payload(2, combination="fixed_weight_sum", weights=[0.25, 0.75]))
    assert spec.weights == (0.25, 0.75)
    with pytest.raises(UnifiedSignalError):
        parse_spec(payload(transformation="winsorized_cs_zscore"))


def test_forbids_legacy_authority_and_unknown_fields():
    with pytest.raises(UnifiedSignalError, match="LEGACY"):
        parse_spec(payload(data_authority="legacy-qlib"))
    with pytest.raises(UnifiedSignalError):
        parse_spec(payload(extra=True))


def test_store_publication_cold_recovery_and_exact_replay(tmp_path):
    spec = parse_spec(payload())
    built = build_unified_signal(spec, sources(tmp_path), tmp_path / "staging")
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store")); store.initialize()
    context = resolve_runtime_context(explicit_store_root=tmp_path / "store", explicit_cache_root=tmp_path / "cache")
    published = publish_domain_artifact(context, "unified_signal", built["unified_signal_artifact_id"], built["path"], lineage=("tfd_x", "tu100_x"))
    first = resolve_artifact(context, "unified_signal", built["unified_signal_artifact_id"])
    second = resolve_artifact(context, "unified_signal", built["unified_signal_artifact_id"])
    replay = publish_domain_artifact(context, "unified_signal", built["unified_signal_artifact_id"], built["path"], lineage=("tfd_x", "tu100_x"))
    assert published.verified and first.verified and not first.cache_hit and second.cache_hit
    assert replay.exact_existing and replay.new_blob_count == 0
