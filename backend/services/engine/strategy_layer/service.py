from __future__ import annotations

import json
import math
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .artifact import validate_strategy_domain_artifact
from .errors import StrategyLayerError
from .models import StrategySpec

STRATEGY_ENGINE_VERSION = "1.0.0"


def parse_strategy_spec(value: Mapping[str, Any]) -> StrategySpec:
    fields = {
        "schema_version", "name", "description", "unified_signal_id", "universe_id", "qlib_view_id",
        "start_date", "end_date", "selection", "rebalance", "weighting", "execution", "costs",
        "benchmark", "quality_gates", "evidence_policy", "data_authority",
    }
    if set(value) != fields:
        raise StrategyLayerError(f"StrategySpec fields invalid: unknown={sorted(set(value)-fields)} missing={sorted(fields-set(value))}")
    if value["data_authority"] != "tushare-pro-v1":
        raise StrategyLayerError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    selection = dict(value["selection"])
    if set(selection) != {"type", "topk", "n_drop"} or selection["type"] != "topk_dropout":
        raise StrategyLayerError("v1 only supports topk_dropout")
    topk, n_drop = int(selection["topk"]), int(selection["n_drop"])
    if topk <= 0 or not 0 <= n_drop <= topk:
        raise StrategyLayerError("topk/n_drop contract is invalid")
    rebalance = dict(value["rebalance"])
    if set(rebalance) != {"frequency", "interval_sessions", "rebalance_day"} or rebalance != {
        "frequency": "weekly", "interval_sessions": 5, "rebalance_day": "first_available_session"
    }:
        raise StrategyLayerError("v1 formal strategy requires weekly five-session rebalance")
    if value["weighting"] != {"type": "equal_weight"}:
        raise StrategyLayerError("v1 only supports equal weight")
    execution = dict(value["execution"])
    if execution.get("chain") != ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"]:
        raise StrategyLayerError("formal Qlib execution chain is required")
    benchmark = dict(value["benchmark"])
    if benchmark.get("symbol") != "SH000300" or benchmark.get("canonicality") != "canonical":
        raise StrategyLayerError("canonical CSI300 benchmark is required")
    evidence = dict(value["evidence_policy"])
    if evidence.get("signal_evidence_class") not in {"research_diagnostic", "validation_evidence", "frozen_evidence", "approved"}:
        raise StrategyLayerError("signal evidence class is invalid")
    if evidence.get("usable_for_parameter_optimization") is not False or evidence.get("usable_for_promotion") is not False:
        raise StrategyLayerError("v1 diagnostic strategy cannot optimize or promote")
    return StrategySpec(**{**value, "selection": selection, "rebalance": rebalance, "execution": execution, "benchmark": benchmark, "evidence_policy": evidence})


def strategy_spec_id(spec: StrategySpec) -> str:
    return "sts_" + hash_payload({**spec.to_dict(), "engine_version": STRATEGY_ENGINE_VERSION})


def build_execution_plan(spec: StrategySpec, *, signal_artifact_id: str, lifecycle_policy_id: str,
                         termination_policy_id: str) -> dict[str, Any]:
    if spec.unified_signal_id != signal_artifact_id:
        raise StrategyLayerError("StrategySpec signal reference mismatch")
    return {
        "schema_version": "strategy-execution-plan-v1", "strategy_spec_id": strategy_spec_id(spec),
        "unified_signal_artifact_id": signal_artifact_id, "universe_id": spec.universe_id,
        "qlib_view_id": spec.qlib_view_id, "start_date": spec.start_date, "end_date": spec.end_date,
        "execution": spec.execution, "costs": spec.costs, "benchmark": spec.benchmark,
        "lifecycle_policy_id": lifecycle_policy_id, "termination_policy_id": termination_policy_id,
        "agent_calls": 0, "factor_optimization_trials": 0, "strategy_optimization_trials": 0,
        "promotion_writes": 0,
    }


def _tradable(row: pd.Series) -> bool:
    return bool(row.get("active", True)) and bool(row.get("tradable", True))


def build_portfolio_target(signal: pd.DataFrame, spec: StrategySpec, output_root: Path,
                           *, lifecycle: pd.DataFrame | None = None) -> dict[str, Any]:
    required = {"symbol", "trade_date", "score"}
    if set(signal.columns) != required or signal.duplicated(["symbol", "trade_date"]).any():
        raise StrategyLayerError("unified signal schema or key contract failed")
    frame = signal.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    if lifecycle is not None:
        life = lifecycle.copy()
        life["trade_date"] = pd.to_datetime(life["trade_date"])
        frame = frame.merge(life, on=["symbol", "trade_date"], how="left", validate="one_to_one")
        frame = frame[frame.apply(_tradable, axis=1)]
    dates = sorted(frame["trade_date"].drop_duplicates())
    rebalance_dates = dates[:: int(spec.rebalance["interval_sessions"])]
    held: set[str] = set()
    rows: list[dict[str, Any]] = []
    topk, n_drop = int(spec.selection["topk"]), int(spec.selection["n_drop"])
    for date in rebalance_dates:
        daily = frame[frame["trade_date"] == date].dropna(subset=["score"]).sort_values(
            ["score", "symbol"], ascending=[False, True]
        )
        ranked = list(daily["symbol"])
        score_by = dict(zip(daily["symbol"], daily["score"]))
        eligible_held = [symbol for symbol in held if symbol in score_by]
        drop = set(sorted(eligible_held, key=lambda x: (score_by[x], x))[: min(n_drop, len(eligible_held))])
        retained = [symbol for symbol in eligible_held if symbol not in drop]
        selected = retained[:topk]
        for symbol in ranked:
            if symbol not in selected and len(selected) < topk:
                selected.append(symbol)
        held = set(selected)
        weight = 1.0 / len(selected) if selected else 0.0
        rank_by = {symbol: ordinal for ordinal, symbol in enumerate(ranked, 1)}
        for symbol in sorted(selected):
            rows.append({"trade_date": date, "symbol": symbol, "target_weight": weight,
                         "signal_rank": rank_by[symbol], "selection_reason": "retained" if symbol in retained else "topk_entry"})
    output = pd.DataFrame(rows, columns=["trade_date", "symbol", "target_weight", "signal_rank", "selection_reason"])
    if len(output) and any(not math.isclose(float(x), 1.0, abs_tol=1e-12) for x in output.groupby("trade_date")["target_weight"].sum()):
        raise StrategyLayerError("target weights do not sum to one")
    identity = {
        "strategy_spec_id": strategy_spec_id(spec), "unified_signal_artifact_id": spec.unified_signal_id,
        "universe_id": spec.universe_id, "date_range": [spec.start_date, spec.end_date],
        "selection": spec.selection, "rebalance": spec.rebalance, "weighting": spec.weighting,
        "engine_version": STRATEGY_ENGINE_VERSION, "data_authority": "tushare-pro-v1",
    }
    target_id = "pta_" + hash_payload(identity)
    root = Path(output_root) / target_id
    if root.exists():
        validate_strategy_domain_artifact(root, target_id, "portfolio_target")
        return {**json.loads((root / "manifest.json").read_text()), "path": str(root), "exact_existing": True}
    staging = Path(output_root) / f".{target_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    output.to_parquet(staging / "portfolio_target.parquet", index=False, compression="zstd", engine="pyarrow")
    quality = {"rebalance_date_count": len(rebalance_dates), "row_count": len(output),
               "maximum_position_count": int(output.groupby("trade_date")["symbol"].count().max()) if len(output) else 0,
               "weight_sum_tolerance": 1e-12, "actual_execution_data": False}
    write_json(staging / "spec.json", spec.to_dict())
    write_json(staging / "quality.json", quality)
    hashes = {name: hash_file(staging / name) for name in ("portfolio_target.parquet", "spec.json", "quality.json")}
    manifest = {"schema_version": "portfolio-target-artifact-v1", "artifact_kind": "portfolio_target",
                "portfolio_target_artifact_id": target_id, "identity": identity, "file_hashes": hashes}
    write_json(staging / "manifest.json", manifest)
    Path(output_root).mkdir(parents=True, exist_ok=True)
    os.replace(staging, root)
    validate_strategy_domain_artifact(root, target_id, "portfolio_target")
    return {**manifest, "path": str(root), "exact_existing": False}
