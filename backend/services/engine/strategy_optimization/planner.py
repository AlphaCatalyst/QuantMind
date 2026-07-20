from __future__ import annotations

from backend.services.engine.tushare_cutover.canonical import hash_payload

from .models import PlannedStrategyTrial, StrategyOptimizationSpec

ENGINE_VERSION = "1.0.0"


def study_id(spec: StrategyOptimizationSpec) -> str:
    return "sos_" + hash_payload({"spec": spec.to_dict(), "engine_version": ENGINE_VERSION})


def _strategy_spec_id(spec: StrategyOptimizationSpec, signal_id: str, topk: int, n_drop: int, interval: int) -> str:
    return "sts_" + hash_payload({
        "unified_signal_id": signal_id, "universe_id": spec.universe_id, "qlib_view_id": spec.qlib_view_id,
        "research_period": spec.research_period, "topk": topk, "n_drop": n_drop,
        "rebalance_interval": interval, "execution_contract": spec.execution_contract,
        "benchmark_policy": spec.benchmark_policy, "data_authority": spec.data_authority,
    })


def plan_trials(spec: StrategyOptimizationSpec) -> tuple[PlannedStrategyTrial, ...]:
    sid = study_id(spec)
    result = []
    for signal_id in spec.unified_signal_ids:
        for topk in spec.search_space["topk"]:
            for n_drop in spec.search_space["n_drop"]:
                if n_drop >= topk:
                    continue
                for interval in spec.search_space["rebalance_interval"]:
                    strategy_id = _strategy_spec_id(spec, signal_id, topk, n_drop, interval)
                    qlib_identity = {
                        "strategy_spec_id": strategy_id, "unified_signal_artifact_id": signal_id,
                        "qlib_view_id": spec.qlib_view_id, "date_range": ["2019-01-02", "2024-12-31"],
                        "parameters": {"topk": topk, "n_drop": n_drop, "rebalance_interval": interval},
                        "data_authority": "tushare-pro-v1", "engine_version": ENGINE_VERSION,
                        "result_contract_version": "strategy-optimization-result-v1",
                    }
                    qlib_result_id = "sbr_" + hash_payload(qlib_identity)
                    identity = {
                        "study_id": sid, "unified_signal_id": signal_id, "topk": topk,
                        "n_drop": n_drop, "rebalance_interval": interval,
                        "strategy_spec_id": strategy_id, "qlib_result_id": qlib_result_id,
                        "engine_version": ENGINE_VERSION, "data_authority": "tushare-pro-v1",
                    }
                    result.append(PlannedStrategyTrial(
                        sid, signal_id, topk, n_drop, interval, strategy_id, qlib_result_id,
                        "sot_" + hash_payload(identity),
                    ))
    assert len(result) == 96
    return tuple(result)
