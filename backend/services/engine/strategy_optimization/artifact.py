from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json


KINDS = {
    "strategy_optimization_study": ("strategy_optimization_study_id", "sos_", {"spec.json", "summary.json", "trial_index.json"}),
    "strategy_optimization_trial": ("strategy_optimization_trial_id", "sot_", {"trial.json"}),
    "strategy_parameter_candidate_lock": ("strategy_parameter_candidate_lock_id", "spcl_", {"candidate.json"}),
    "strategy_optimization_result": ("strategy_optimization_result_id", "sor_", {"result.json"}),
}


def publish_json_artifact(root: Path, kind: str, artifact_id: str, identity: dict[str, Any], files: dict[str, Any]) -> dict[str, Any]:
    target = Path(root) / artifact_id
    if target.exists():
        validate_strategy_optimization_artifact(target, artifact_id, kind)
        return {**json.loads((target / "manifest.json").read_text()), "path": str(target), "exact_existing": True}
    staging = Path(root) / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    for name, payload in files.items():
        write_json(staging / name, payload)
    hashes = {name: hash_file(staging / name) for name in sorted(files)}
    id_field = KINDS[kind][0]
    manifest = {
        "schema_version": f"{kind.replace('_', '-')}-v1", "artifact_kind": kind,
        id_field: artifact_id, "identity": identity, "file_hashes": hashes,
    }
    write_json(staging / "manifest.json", manifest)
    Path(root).mkdir(parents=True, exist_ok=True)
    os.replace(staging, target)
    validate_strategy_optimization_artifact(target, artifact_id, kind)
    return {**manifest, "path": str(target), "exact_existing": False}


def publish_formal_strategy_result(
    root: Path, *, trial: dict[str, Any], qlib_result: dict[str, Any],
    metrics: dict[str, Any], qlib_view_id: str, signal_id: str,
) -> dict[str, Any]:
    identity = {
        "strategy_spec_id": trial["strategy_spec_id"], "unified_signal_artifact_id": signal_id,
        "qlib_view_id": qlib_view_id,
        "date_range": ["2019-01-02", "2024-12-31"], "parameters": {
            "topk": trial["topk"], "n_drop": trial["n_drop"],
            "rebalance_interval": trial["rebalance_interval"],
        }, "data_authority": "tushare-pro-v1", "engine_version": "1.0.0",
        "result_contract_version": "strategy-optimization-result-v1",
    }
    result_id = "sbr_" + hash_payload(identity)
    target = Path(root) / result_id
    if target.exists():
        from backend.services.engine.strategy_layer.artifact import validate_strategy_domain_artifact
        validate_strategy_domain_artifact(target, result_id, "strategy_backtest_result")
        return {**json.loads((target / "manifest.json").read_text()), "path": str(target), "exact_existing": True}
    staging = Path(root) / f".{result_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    strategy_spec = {
        "schema_version": "strategy-optimization-execution-v1", "strategy_spec_id": trial["strategy_spec_id"],
        "unified_signal_id": signal_id, "selection": {"type": "topk_dropout", "topk": trial["topk"], "n_drop": trial["n_drop"]},
        "rebalance": {"interval_sessions": trial["rebalance_interval"]}, "weighting": {"type": "equal_weight"},
        "execution": {"deal_price": "open", "signal_lag_days": 1}, "benchmark": {"symbol": "SH000300", "canonicality": "canonical"},
        "data_authority": "tushare-pro-v1",
    }
    plan = {
        "strategy_spec_id": trial["strategy_spec_id"], "strategy_optimization_trial_id": trial["trial_id"],
        "unified_signal_artifact_id": signal_id, "qlib_view_id": qlib_view_id,
        "execution": {"chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"], "deal_price": "open", "signal_lag_days": 1},
        "costs": "existing_formal_cn_exchange", "benchmark": "SH000300",
    }
    write_json(staging / "strategy_spec.json", strategy_spec)
    write_json(staging / "execution_plan.json", plan)
    pd.DataFrame(columns=["trade_date", "symbol", "target_weight", "signal_rank", "selection_reason"]).to_parquet(staging / "portfolio_target.parquet", index=False)
    pd.DataFrame(qlib_result.get("positions") or [], columns=["date", "symbol", "amount", "weight", "side"]).to_parquet(staging / "positions.parquet", index=False)
    pd.DataFrame(qlib_result.get("orders") or []).to_parquet(staging / "orders.parquet", index=False)
    pd.DataFrame(qlib_result.get("trades") or []).to_parquet(staging / "trades.parquet", index=False)
    pd.DataFrame(qlib_result.get("equity_curve") or [], columns=["date", "value"]).to_parquet(staging / "daily_nav.parquet", index=False)
    write_json(staging / "metrics.json", metrics)
    write_json(staging / "benchmark.json", {"official": {"name": "CSI300", "symbol": "SH000300", "canonicality": "canonical", "usable_for_selection": True}, "diagnostic": {"name": "Tushare Fixed-100", "canonicality": "noncanonical", "usable_for_selection": False}})
    write_json(staging / "canonicality.json", {
        "evidence_class": "retrospective_contaminated_strategy_parameter_diagnostic",
        "data_authority": "tushare-pro-v1", "benchmark_canonicality": "canonical",
        "termination_canonicality": "canonical", "usable_for_research": True,
        "usable_for_parameter_optimization": True, "usable_for_promotion": False,
        "predictive_claim": False, "eligible_for_production": False,
    })
    write_json(staging / "target_execution_comparison.json", {"status": "not_emitted_by_formal_topk_dropout", "portfolio_target_is_actual_execution": False})
    required = {p.name for p in staging.iterdir()}
    hashes = {name: hash_file(staging / name) for name in sorted(required)}
    manifest = {"schema_version": "strategy-backtest-result-v1", "artifact_kind": "strategy_backtest_result", "strategy_backtest_result_id": result_id, "identity": identity, "file_hashes": hashes}
    write_json(staging / "manifest.json", manifest)
    Path(root).mkdir(parents=True, exist_ok=True)
    os.replace(staging, target)
    from backend.services.engine.strategy_layer.artifact import validate_strategy_domain_artifact
    validate_strategy_domain_artifact(target, result_id, "strategy_backtest_result")
    return {**manifest, "path": str(target), "exact_existing": False}


def validate_strategy_optimization_artifact(root: Path, expected_id: str, kind: str) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("strategy optimization artifact kind is unsupported")
    manifest = json.loads((Path(root) / "manifest.json").read_text())
    id_field, prefix, required = KINDS[kind]
    if manifest.get("artifact_kind") != kind or manifest.get(id_field) != expected_id or not expected_id.startswith(prefix):
        raise ValueError("strategy optimization artifact identity mismatch")
    if expected_id != prefix + hash_payload(manifest["identity"]):
        raise ValueError("strategy optimization content identity mismatch")
    hashes = manifest.get("file_hashes")
    actual = {p.name for p in Path(root).iterdir() if p.is_file() and p.name != "manifest.json"}
    if set(hashes or {}) != required or actual != required or any(hash_file(Path(root) / name) != digest for name, digest in hashes.items()):
        raise ValueError("strategy optimization artifact inventory mismatch")
    rendered = json.dumps(manifest["identity"])
    if "tushare-pro-v1" not in rendered or "quantmind-production-feature-snapshots-v1" in rendered:
        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id}
