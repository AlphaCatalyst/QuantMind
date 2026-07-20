from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from backend.services.engine.artifact_runtime import publish_domain_artifact
from backend.services.engine.artifact_runtime.models import ArtifactRuntimeContext
from backend.services.engine.strategy_layer.result import publish_strategy_registry
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner, YEAR_WINDOWS
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .artifact import publish_formal_strategy_result, publish_json_artifact
from .metrics import aggregate_metrics, segment_metrics
from .models import StrategyOptimizationSpec
from .ordering import parameter_sensitivity, rank_trials
from .planner import plan_trials, study_id


def _materialize(context: ArtifactRuntimeContext, artifact_id: str, destination: Path) -> tuple[Path, str]:
    descriptor = context.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise ValueError(f"Store artifact is missing: {artifact_id}")
    if destination.exists():
        shutil.rmtree(destination)
    context.store.materialize_artifact(descriptor.descriptor_id, destination)
    return destination, descriptor.artifact_kind


def _publish(context: ArtifactRuntimeContext, kind: str, artifact: dict[str, Any], lineage: tuple[str, ...]):
    id_field = {
        "strategy_backtest_result": "strategy_backtest_result_id",
        "strategy_optimization_trial": "strategy_optimization_trial_id",
        "strategy_parameter_candidate_lock": "strategy_parameter_candidate_lock_id",
        "strategy_optimization_result": "strategy_optimization_result_id",
        "strategy_optimization_study": "strategy_optimization_study_id",
        "strategy_research_registry": "strategy_research_registry_id",
    }[kind]
    return publish_domain_artifact(context, kind, artifact[id_field], artifact["path"], lineage=lineage)


def _signal_path(root: Path, signal_id: str) -> Path:
    manifest = json.loads((root / "manifest.json").read_text())
    identity = manifest.get("identity", {})
    signal_spec = identity.get("spec", {})
    inputs = signal_spec.get("inputs", [])
    expected_universe = "tu100_078e6609ef84c58e4c9db53fe8ee194a4b8b7b31d4990a61fbddb9022c02c526"
    if signal_spec.get("data_authority") != "tushare-pro-v1" or not inputs or any(
        item.get("universe_id") != expected_universe or item.get("dataset_id") != signal_spec.get("dataset_id")
        for item in inputs
    ):
        raise ValueError("Unified Signals must share the canonical Tushare Fixed-100 authority")
    frame = pd.read_parquet(root / "signal.parquet")
    if list(frame.columns) != ["symbol", "trade_date", "score"]:
        raise ValueError("Unified Signal contract changed")
    path = root / "qlib_score.parquet"
    frame.rename(columns={"score": "pred"}).to_parquet(path, index=False, compression="zstd")
    return path


def _run_trial(runner: FormalQlibRunner, signal_path: Path, trial: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    kwargs = {"topk": trial["topk"], "n_drop": trial["n_drop"], "rebalance_days": trial["rebalance_interval"]}
    full_raw = runner.run(signal_path, "2019-01-02", "2024-12-31", **kwargs)
    full = segment_metrics(full_raw, topk=trial["topk"])
    annual = {}
    for year in range(2019, 2025):
        start, end = YEAR_WINDOWS[str(year)]
        annual[str(year)] = segment_metrics(runner.run(signal_path, start, end, **kwargs), topk=trial["topk"])
    if any(item.get("status") != "completed" for item in annual.values()) or full.get("status") != "completed":
        metrics = {"full_period": full, "annual": annual, "eligible": False, "eligibility_reason": "qlib_execution_failed"}
    else:
        metrics = aggregate_metrics(full, annual, topk=trial["topk"])
    return full_raw, metrics


def _candidate_lock(spec: StrategyOptimizationSpec, selected: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    identity = {
        "unified_signal_id": selected["unified_signal_id"], "strategy_optimization_study_id": selected["study_id"],
        "selected_trial_id": selected["trial_id"], "topk": selected["topk"], "n_drop": selected["n_drop"],
        "rebalance_interval": selected["rebalance_interval"], "weighting": "equal_weight",
        "signal_lag": 1, "execution_price": "open", "cost_contract": "existing_formal_cn_exchange",
        "benchmark": "SH000300", "selection_period": spec.research_period,
        "ordering_policy": list(spec.ordering), "data_authority": "tushare-pro-v1",
    }
    candidate_id = "spcl_" + hash_payload(identity)
    return candidate_id, {
        **identity, "strategy_parameter_candidate_lock_id": candidate_id,
        "status": "parameter_candidate_locked", "predictive_claim": False,
        "usable_for_research": True, "usable_for_promotion": False,
        "eligible_for_production": False,
    }


def execute_study(
    spec: StrategyOptimizationSpec, context: ArtifactRuntimeContext, work_root: Path,
    *, normalized_bars_id: str, source_registry_id: str,
) -> dict[str, Any]:
    sid = study_id(spec)
    existing = context.store.find_by_artifact_id(sid)
    if existing is not None:
        study_root = Path(work_root) / "replay-study"
        if study_root.exists():
            shutil.rmtree(study_root)
        context.store.materialize_artifact(existing.descriptor_id, study_root)
        summary = json.loads((study_root / "summary.json").read_text())
        return {**summary, "exact_existing": True, "qlib_calls": 0, "agent_calls": 0, "factor_optimization_calls": 0, "new_artifacts": 0, "new_blobs": 0}

    work_root = Path(work_root)
    materialized = work_root / "inputs"
    qlib_root, qlib_kind = _materialize(context, spec.qlib_view_id, materialized / spec.qlib_view_id)
    if qlib_kind != "tushare_100_qlib_view":
        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    normalized_root, normalized_kind = _materialize(context, normalized_bars_id, materialized / normalized_bars_id)
    if normalized_kind != "tushare_normalized_bars":
        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    normalized = pd.read_parquet(normalized_root / "normalized_bars.parquet")
    runner = FormalQlibRunner(qlib_root, normalized, work_root / "qlib-cache")
    staging = work_root / "domain"
    trials_by_signal: dict[str, list[dict[str, Any]]] = {signal: [] for signal in spec.unified_signal_ids}
    published_ids: list[str] = []
    for planned in plan_trials(spec):
        signal_root, signal_kind = _materialize(context, planned.unified_signal_id, materialized / planned.unified_signal_id)
        if signal_kind != "unified_signal":
            raise ValueError("Unified Signal Store kind mismatch")
        signal_path = _signal_path(signal_root, planned.unified_signal_id)
        trial = planned.to_dict()
        full_raw, metrics = _run_trial(runner, signal_path, trial)
        qlib_artifact = publish_formal_strategy_result(
            staging / "strategy-results", trial=trial, qlib_result=full_raw, metrics=metrics,
            qlib_view_id=spec.qlib_view_id, signal_id=planned.unified_signal_id,
        )
        if qlib_artifact["strategy_backtest_result_id"] != planned.qlib_result_id:
            raise ValueError("planned Qlib Result identity mismatch")
        _publish(context, "strategy_backtest_result", qlib_artifact, (planned.unified_signal_id, spec.qlib_view_id))
        trial_payload = {
            **trial, "strategy_backtest_result_id": planned.qlib_result_id, "descriptor_id": context.store.find_by_artifact_id(planned.qlib_result_id).descriptor_id,
            "metrics_hash": hash_payload(metrics), "metrics": metrics,
            "execution_evidence": {"formal_chain": full_raw.get("formal_chain"), "qlib_execution_succeeded": full_raw.get("status") == "completed"},
            "agent_calls": 0, "factor_optimization_calls": 0, "promotion_writes": 0,
        }
        identity = {key: trial_payload[key] for key in ("study_id", "unified_signal_id", "topk", "n_drop", "rebalance_interval", "strategy_spec_id")}
        if planned.trial_id != "sot_" + hash_payload({**identity, "qlib_result_id": planned.qlib_result_id, "engine_version": "1.0.0", "data_authority": "tushare-pro-v1"}):
            raise ValueError("Trial identity mismatch")
        trial_artifact = publish_json_artifact(staging / "trials", "strategy_optimization_trial", planned.trial_id, {"study_id": sid, "unified_signal_id": planned.unified_signal_id, "topk": planned.topk, "n_drop": planned.n_drop, "rebalance_interval": planned.rebalance_interval, "strategy_spec_id": planned.strategy_spec_id, "qlib_result_id": planned.qlib_result_id, "engine_version": "1.0.0", "data_authority": "tushare-pro-v1"}, {"trial.json": trial_payload})
        _publish(context, "strategy_optimization_trial", trial_artifact, (sid, planned.qlib_result_id, planned.unified_signal_id))
        trials_by_signal[planned.unified_signal_id].append(trial_payload)
        published_ids.extend([planned.qlib_result_id, planned.trial_id])

    candidates = []
    holdout_reports = {}
    comparisons = {}
    sensitivities = {}
    for signal_id, trials in trials_by_signal.items():
        ranked = rank_trials(trials)
        if not ranked:
            continue
        selected = ranked[0]
        candidate_id, candidate = _candidate_lock(spec, selected)
        signal_path = _signal_path(materialized / signal_id, signal_id)
        holdout = {}
        for label, period in spec.retrospective_holdout_periods.items():
            lifecycle_policy = {
                "policy_id": "fulp_60672b83e8fc37c84e0eb749162845d246b2fa3365d9d4740d1fe183a6a632a",
                "locked_member_count": 100,
                "minimum_observable_instruments": selected["topk"] + selected["n_drop"],
            }
            raw = runner.run(
                signal_path, period["start"], period["end"], topk=selected["topk"],
                n_drop=selected["n_drop"], rebalance_days=selected["rebalance_interval"],
                lifecycle_policy=lifecycle_policy,
            )
            holdout[label] = segment_metrics(raw, topk=selected["topk"])
            holdout[label]["evidence_class"] = "retrospective_report_only"
            holdout[label]["usable_for_selection"] = False
            holdout[label]["lifecycle_policy_id"] = lifecycle_policy["policy_id"]
        sensitivity = parameter_sensitivity(trials, selected)
        candidate.update({"retrospective_reports": holdout, "parameter_sensitivity": sensitivity})
        candidate_artifact = publish_json_artifact(staging / "candidates", "strategy_parameter_candidate_lock", candidate_id, {**{key: candidate[key] for key in ("unified_signal_id", "strategy_optimization_study_id", "selected_trial_id", "topk", "n_drop", "rebalance_interval", "weighting", "signal_lag", "execution_price", "cost_contract", "benchmark", "selection_period", "ordering_policy")}, "data_authority": "tushare-pro-v1"}, {"candidate.json": candidate})
        _publish(context, "strategy_parameter_candidate_lock", candidate_artifact, (sid, selected["trial_id"], signal_id))
        baseline = next(item for item in trials if item["topk"] == 20 and item["n_drop"] == 5 and item["rebalance_interval"] == 5)
        comparisons[signal_id] = {"baseline": baseline["metrics"], "candidate": selected["metrics"], "candidate_lock_id": candidate_id}
        holdout_reports[signal_id] = holdout
        sensitivities[signal_id] = sensitivity
        candidates.append(candidate)
        published_ids.append(candidate_id)

    result_identity = {"study_id": sid, "trial_ids": sorted(item["trial_id"] for values in trials_by_signal.values() for item in values), "candidate_lock_ids": sorted(item["strategy_parameter_candidate_lock_id"] for item in candidates), "ordering": list(spec.ordering), "data_authority": "tushare-pro-v1", "engine_version": "1.0.0"}
    result_id = "sor_" + hash_payload(result_identity)
    result_payload = {
        "strategy_optimization_result_id": result_id, "study_id": sid,
        "trial_count": sum(map(len, trials_by_signal.values())), "eligible_trial_count": sum(item["metrics"].get("eligible", False) for values in trials_by_signal.values() for item in values),
        "candidate_locks": candidates, "baseline_comparisons": comparisons,
        "retrospective_reports": holdout_reports, "parameter_sensitivity": sensitivities,
        "evidence_policy": spec.evidence_policy, "selection_used_2025": False,
        "selection_used_2026H1": False, "agent_calls": 0, "factor_optimization_calls": 0,
        "promotion_writes": 0,
    }
    result_artifact = publish_json_artifact(staging / "results", "strategy_optimization_result", result_id, result_identity, {"result.json": result_payload})
    _publish(context, "strategy_optimization_result", result_artifact, tuple(sorted(published_ids)))
    source_registry_root, _ = _materialize(context, source_registry_id, materialized / source_registry_id)
    old_registry = json.loads((source_registry_root / "registry.json").read_text())
    entries = list(old_registry["entries"]) + [{
        "strategy_spec_id": item["selected_trial_id"], "unified_signal_artifact_id": item["unified_signal_id"],
        "strategy_parameter_candidate_lock_id": item["strategy_parameter_candidate_lock_id"],
        "status": "parameter_candidate_locked", "active": False, "approved": False,
        "evidence_class": "retrospective_contaminated_strategy_parameter_diagnostic",
    } for item in candidates]
    registry_artifact = publish_strategy_registry(staging / "registry", entries, [source_registry_id, result_id])
    _publish(context, "strategy_research_registry", registry_artifact, (source_registry_id, result_id))
    summary = {
        "strategy_optimization_study_id": sid, "strategy_optimization_result_id": result_id,
        "strategy_research_registry_id": registry_artifact["strategy_research_registry_id"],
        "trial_count": 96, "candidate_lock_ids": [item["strategy_parameter_candidate_lock_id"] for item in candidates],
        "qlib_calls": runner.calls, "agent_calls": 0, "factor_optimization_calls": 0,
        "promotion_writes": 0, "exact_existing": False,
    }
    study_identity = {"spec": spec.to_dict(), "engine_version": "1.0.0"}
    study_artifact = publish_json_artifact(staging / "studies", "strategy_optimization_study", sid, study_identity, {
        "spec.json": spec.to_dict(), "summary.json": summary,
        "trial_index.json": {"trial_ids": sorted(item["trial_id"] for values in trials_by_signal.values() for item in values)},
    })
    _publish(context, "strategy_optimization_study", study_artifact, (result_id, registry_artifact["strategy_research_registry_id"], *spec.unified_signal_ids))
    return summary
