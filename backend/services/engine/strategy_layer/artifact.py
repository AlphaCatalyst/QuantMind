from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

KINDS = {
    "unified_signal": ("unified_signal_artifact_id", "usa_", {"spec.json", "quality.json", "signal.parquet"}),
    "portfolio_target": ("portfolio_target_artifact_id", "pta_", {"spec.json", "quality.json", "portfolio_target.parquet"}),
    "strategy_backtest_result": ("strategy_backtest_result_id", "sbr_", {
        "strategy_spec.json", "execution_plan.json", "portfolio_target.parquet", "positions.parquet",
        "orders.parquet", "trades.parquet", "daily_nav.parquet", "metrics.json", "benchmark.json",
        "canonicality.json", "target_execution_comparison.json",
    }),
    "strategy_research_registry": ("strategy_research_registry_id", "srr_", {"registry.json"}),
}


def validate_strategy_domain_artifact(root: Path, expected_id: str, expected_kind: str) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if expected_kind not in KINDS or manifest.get("artifact_kind") != expected_kind:
        raise ValueError("strategy artifact kind mismatch")
    id_field, prefix, required = KINDS[expected_kind]
    identity = manifest.get("identity")
    if manifest.get(id_field) != expected_id or not expected_id.startswith(prefix) or expected_id != prefix + hash_payload(identity):
        raise ValueError("strategy artifact identity mismatch")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or set(hashes) != required or "manifest.json" in hashes:
        raise ValueError("strategy artifact file inventory mismatch")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != required or any(hash_file(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("strategy artifact hash inventory mismatch")
    if identity.get("data_authority", identity.get("spec", {}).get("data_authority")) != "tushare-pro-v1":
        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    if expected_kind == "unified_signal":
        frame = pd.read_parquet(root / "signal.parquet")
        if list(frame.columns) != ["symbol", "trade_date", "score"] or frame.duplicated(["symbol", "trade_date"]).any() or np.isinf(frame["score"].to_numpy()).any():
            raise ValueError("unified signal data contract failed")
    elif expected_kind == "portfolio_target":
        frame = pd.read_parquet(root / "portfolio_target.parquet")
        if frame.duplicated(["trade_date", "symbol"]).any() or (frame["target_weight"] < 0).any():
            raise ValueError("portfolio target data contract failed")
    elif expected_kind == "strategy_backtest_result":
        canonicality = json.loads((root / "canonicality.json").read_text())
        if canonicality.get("usable_for_parameter_optimization") is not False or canonicality.get("usable_for_promotion") is not False:
            raise ValueError("diagnostic strategy result governance failed")
    elif expected_kind == "strategy_research_registry":
        registry = json.loads((root / "registry.json").read_text())
        allowed = {"strategy_registered", "backtest_completed", "backtest_noncanonical"}
        if any(item.get("status") not in allowed for item in registry.get("entries", [])):
            raise ValueError("strategy registry contains forbidden lifecycle state")
    return {"status": "valid", "artifact_kind": expected_kind, "artifact_id": expected_id, "file_count": len(actual)}
