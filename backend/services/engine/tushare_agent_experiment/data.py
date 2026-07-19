from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


PROVIDER_ID = "tushare-pro-v1"
FORBIDDEN_PROVIDER_ID = "quantmind-production-feature-snapshots-v1"
REQUIRED_KINDS = {
    "universe_100": "tushare_100_experiment_universe_lock",
    "feature": "tushare_feature_dataset",
    "label": "tushare_label_dataset",
    "qlib": "tushare_100_qlib_view",
    "registry": "tushare_research_registry_genesis",
    "memory": "sanitized_research_memory",
    "normalized": "tushare_normalized_bars",
    "benchmark": "tushare_market_benchmark",
}


@dataclass(frozen=True)
class AuthorityBundle:
    authority: dict
    universe: pd.DataFrame
    matrix: pd.DataFrame
    normalized: pd.DataFrame
    benchmark: pd.DataFrame
    qlib_view: Path
    sanitized_memory: dict
    registry: dict
    materialized: dict[str, Path]
    store: FileSystemResearchArtifactStore


def _materialize(store, artifact_id: str, expected_kind: str, root: Path) -> Path:
    descriptor = store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required Tushare Artifact missing: {artifact_id}")
    if descriptor.artifact_kind != expected_kind:
        raise RuntimeError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    if any(FORBIDDEN_PROVIDER_ID in item for item in descriptor.lineage):
        raise RuntimeError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    target = root / expected_kind / artifact_id
    if target.exists():
        # The task runtime is Store-required. Recreate verified materialization rather
        # than trusting an arbitrary pre-existing local path.
        import shutil

        shutil.rmtree(target)
    store.materialize_artifact(descriptor.descriptor_id, target)
    return target


def load_authority_bundle(
    *, authority_path: Path, work_root: Path, store_root: Path | None = None
) -> AuthorityBundle:
    authority = json.loads(Path(authority_path).read_text(encoding="utf-8"))
    if authority.get("provider_id") != PROVIDER_ID or authority.get("authority_status") != "active":
        raise RuntimeError("Tushare authority is not active")
    legacy = authority.get("legacy_provider", {})
    if legacy.get("runtime_read_allowed") is not False or legacy.get("authority_status") != "retired_and_purged":
        raise RuntimeError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    store = FileSystemResearchArtifactStore(resolve_config(store_root))
    store.validate_format()
    identities = {
        "universe_100": authority["universe_100"]["universe_lock_id"],
        "feature": authority["feature_dataset_id"],
        "label": authority["label_dataset_id"],
        "qlib": authority["qlib_view_id"],
        "registry": authority["registry_genesis_id"],
        "memory": authority["sanitized_memory_id"],
        "normalized": authority["normalized_bars_id"],
        "benchmark": next(
            item
            for item in store.get_descriptor(authority["authority_record_id"]).lineage
            if item.startswith("tmb_")
        ),
    }
    inputs = Path(work_root) / "store-inputs"
    materialized = {
        name: _materialize(store, artifact_id, REQUIRED_KINDS[name], inputs)
        for name, artifact_id in identities.items()
    }
    universe = pd.read_parquet(materialized["universe_100"] / "universe.parquet")
    manifest = json.loads((materialized["universe_100"] / "manifest.json").read_text())
    identity = manifest["identity"]
    if (
        len(universe) != 100
        or universe["ts_code"].nunique() != 100
        or universe["rank"].tolist() != list(range(1, 101))
        or identity["parent_ranks"] != list(range(1, 101))
        or identity["parent_universe_lock_id"] != authority["universe_500"]["universe_lock_id"]
    ):
        raise RuntimeError("Tushare Fixed-100 lock invariant failed")
    symbols = set(identity["symbols"])
    normalized_symbols = {
        ("SH" if code.endswith(".SH") else "SZ") + code.split(".")[0]
        for code in symbols
    }
    features = pd.read_parquet(materialized["feature"] / "features.parquet")
    labels = pd.read_parquet(materialized["label"] / "labels.parquet")
    features = features[features["symbol"].isin(normalized_symbols)].copy()
    labels = labels[labels["symbol"].isin(normalized_symbols)].copy()
    matrix = features.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    matrix["trade_date"] = pd.to_datetime(matrix["trade_date"])
    matrix = matrix.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
    if matrix["symbol"].nunique() != 100 or matrix.duplicated(["symbol", "trade_date"]).any():
        raise RuntimeError("Tushare Fixed-100 matrix invariant failed")
    normalized = pd.read_parquet(materialized["normalized"] / "normalized_bars.parquet")
    normalized = normalized[normalized["symbol"].isin(normalized_symbols)].copy()
    benchmark = pd.read_parquet(materialized["benchmark"] / "index_daily.parquet")
    memory = json.loads((materialized["memory"] / "memory.json").read_text())
    registry = json.loads((materialized["registry"] / "registry.json").read_text())
    if memory.get("historical_metrics_invalidated_by_data_authority_cutover") is not True:
        raise RuntimeError("old research metrics were not invalidated")
    if any(registry.get(key) for key in ("entries", "promotion_candidates", "approved", "active")):
        raise RuntimeError("Tushare Registry genesis is not empty")
    return AuthorityBundle(
        authority,
        universe,
        matrix,
        normalized,
        benchmark,
        materialized["qlib"],
        memory,
        registry,
        materialized,
        store,
    )
