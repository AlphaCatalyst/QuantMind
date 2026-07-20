from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .artifact import validate_strategy_domain_artifact


METRIC_KEYS = (
    "gross_return", "net_return", "annual_return", "volatility", "sharpe_ratio",
    "max_drawdown", "turnover", "transaction_cost", "benchmark_return",
    "net_excess_csi300", "monthly_win_rate",
)


def _frame(rows: Any, columns: list[str]) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)


def publish_backtest_result(
    output_root: Path, *, strategy_spec: Mapping[str, Any], execution_plan: Mapping[str, Any],
    portfolio_target_path: Path, qlib_results_root: Path, qlib_strategy_key: str,
    source_qlib_artifact_id: str, portfolio_target_artifact_id: str,
    termination_canonicality: str = "canonical",
) -> dict[str, Any]:
    source = json.loads((Path(qlib_results_root) / "results.json").read_text(encoding="utf-8"))
    result = source["annual_backtests"][qlib_strategy_key]["2019-2026H1"]
    if result.get("status") != "completed" or result.get("formal_chain") != [
        "QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"
    ]:
        raise ValueError("source Qlib result is not a completed formal-chain result")
    metrics = {key: result.get(key) for key in METRIC_KEYS}
    net = metrics.get("net_return")
    metrics["calmar"] = None if not net or not metrics.get("max_drawdown") else float(result.get("annual_return") or 0) / abs(float(metrics["max_drawdown"]))
    benchmark = {
        "official": {"name": "CSI300", "symbol": "SH000300", "canonicality": "canonical",
                     "return": result.get("benchmark_return"), "net_excess": result.get("net_excess_csi300"),
                     "usable_for_decision": True},
        "diagnostic": {"name": "Tushare Fixed-100", "canonicality": "noncanonical",
                       "return": result.get("fixed_100_benchmark_return"),
                       "net_excess": result.get("net_excess_fixed_100"), "usable_for_decision": False,
                       "reason": "corporate-action and termination settlement evidence remains incomplete"},
    }
    canonicality = {
        "signal_evidence_class": strategy_spec["evidence_policy"]["signal_evidence_class"],
        "benchmark_canonicality": "canonical", "termination_canonicality": termination_canonicality,
        "data_authority": "tushare-pro-v1", "strategy_result_canonicality": "canonical" if termination_canonicality == "canonical" else "noncanonical",
        "usable_for_research": True, "usable_for_parameter_optimization": False, "usable_for_promotion": False,
        "predictive_claim": False, "eligible_for_production": False,
    }
    target_comparison = {
        "status": "not_verifiable_from_source_qlib_result",
        "portfolio_target_is_actual_execution": False,
        "source_positions_available": bool(result.get("positions")),
        "source_orders_available": bool(result.get("orders")),
        "source_trades_available": bool(result.get("trades")),
        "reason": "RedisRecordingStrategy source result persisted positions but did not emit pre-trade target weights",
    }
    identity = {
        "strategy_spec_id": execution_plan["strategy_spec_id"], "unified_signal_artifact_id": execution_plan["unified_signal_artifact_id"],
        "portfolio_target_artifact_id": portfolio_target_artifact_id, "source_qlib_artifact_id": source_qlib_artifact_id,
        "source_result_key": qlib_strategy_key, "qlib_view_id": execution_plan["qlib_view_id"],
        "date_range": [execution_plan["start_date"], execution_plan["end_date"]],
        "data_authority": "tushare-pro-v1", "engine_version": "1.0.0",
        "result_contract_version": "1.0.0",
    }
    result_id = "sbr_" + hash_payload(identity)
    target = Path(output_root) / result_id
    if target.exists():
        validate_strategy_domain_artifact(target, result_id, "strategy_backtest_result")
        return {**json.loads((target / "manifest.json").read_text()), "path": str(target), "exact_existing": True}
    staging = Path(output_root) / f".{result_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    write_json(staging / "strategy_spec.json", strategy_spec)
    write_json(staging / "execution_plan.json", execution_plan)
    shutil.copyfile(portfolio_target_path, staging / "portfolio_target.parquet")
    _frame(result.get("positions"), ["date", "symbol", "amount", "weight", "side"]).to_parquet(staging / "positions.parquet", index=False)
    _frame(result.get("orders"), ["date", "symbol", "amount", "price", "direction"]).to_parquet(staging / "orders.parquet", index=False)
    _frame(result.get("trades"), ["date", "symbol", "amount", "price", "direction", "cost"]).to_parquet(staging / "trades.parquet", index=False)
    _frame(result.get("equity_curve"), ["date", "value"]).to_parquet(staging / "daily_nav.parquet", index=False)
    write_json(staging / "metrics.json", metrics)
    write_json(staging / "benchmark.json", benchmark)
    write_json(staging / "canonicality.json", canonicality)
    write_json(staging / "target_execution_comparison.json", target_comparison)
    required = {
        "strategy_spec.json", "execution_plan.json", "portfolio_target.parquet", "positions.parquet",
        "orders.parquet", "trades.parquet", "daily_nav.parquet", "metrics.json", "benchmark.json",
        "canonicality.json", "target_execution_comparison.json",
    }
    hashes = {name: hash_file(staging / name) for name in sorted(required)}
    manifest = {"schema_version": "strategy-backtest-result-v1", "artifact_kind": "strategy_backtest_result",
                "strategy_backtest_result_id": result_id, "identity": identity, "file_hashes": hashes}
    write_json(staging / "manifest.json", manifest)
    Path(output_root).mkdir(parents=True, exist_ok=True)
    os.replace(staging, target)
    validate_strategy_domain_artifact(target, result_id, "strategy_backtest_result")
    return {**manifest, "path": str(target), "exact_existing": False}


def publish_strategy_registry(output_root: Path, entries: list[dict[str, Any]], lineage: list[str]) -> dict[str, Any]:
    forbidden = {"validation_candidate", "approved", "active", "retired", "invalidated"}
    if any(item.get("status") in forbidden for item in entries):
        raise ValueError("QM2-P0-016 cannot promote strategy lifecycle state")
    registry = {"schema_version": "strategy-research-registry-v1", "entries": entries,
                "approved_count": 0, "active_count": 0, "promotion_writes": 0}
    identity = {"registry": registry, "lineage": sorted(lineage), "data_authority": "tushare-pro-v1"}
    registry_id = "srr_" + hash_payload(identity)
    target = Path(output_root) / registry_id
    if target.exists():
        validate_strategy_domain_artifact(target, registry_id, "strategy_research_registry")
        return {**json.loads((target / "manifest.json").read_text()), "path": str(target), "exact_existing": True}
    staging = Path(output_root) / f".{registry_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    write_json(staging / "registry.json", registry)
    hashes = {"registry.json": hash_file(staging / "registry.json")}
    manifest = {"schema_version": "strategy-research-registry-artifact-v1", "artifact_kind": "strategy_research_registry",
                "strategy_research_registry_id": registry_id, "identity": identity, "file_hashes": hashes}
    write_json(staging / "manifest.json", manifest)
    Path(output_root).mkdir(parents=True, exist_ok=True)
    os.replace(staging, target)
    validate_strategy_domain_artifact(target, registry_id, "strategy_research_registry")
    return {**manifest, "path": str(target), "exact_existing": False}
