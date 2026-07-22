from __future__ import annotations

from typing import Any

from backend.services.engine.low_frequency_momentum.protocol import PROTOCOLS
from backend.services.engine.momentum_tail_alpha.protocol import SOURCE_FORMULA, SOURCE_SIGNAL_NAME
from backend.services.engine.tushare_cutover.canonical import hash_payload


TASK_ID = "QM2-R1-010"
SOURCE_SIGNAL_ARTIFACT_ID = "lfmsa1_a4a99da30ef0dc99a03270bc5688f3edbe66bf944f899795d11aacf83a8e2262"
SOURCE_DIAGNOSTIC_ID = "mtad1_308b26283cc78b37428b5527e69fd97f21c246746d5a0a908ff1c85571951951"
SOURCE_CLASSIFICATION_ID = "mtsc1_bc4dac928dcfc8e0cd309f88808653b5faa4d420fd014419d4651bf7550cbff7"
FRESH_START_DATE = "2026-06-24"
PERIODS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-30"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}
MINIMUM_EVIDENCE = {
    "fresh_trading_days": 60,
    "completed_10_day_holding_windows": 5,
    "gate_on_trading_days": 20,
    "gate_on_rebalance_dates": 3,
}
PATH_U = dict(PROTOCOLS["L1"]) | {
    "path": "U", "role": "unconditional_signal_baseline", "gate": "always_on",
}
PATH_G = dict(PROTOCOLS["L1"]) | {
    "path": "G", "role": "conditioned_investable_sleeve",
    "gate": "narrow_or_weak_only_at_scheduled_rebalances",
    "off_policy": "clear_risk_holdings_at_scheduled_rebalance", "cash_return": 0.0,
}
PATH_R = {
    "path": "R", "role": "regime_timing_diagnostic", "benchmark": "CSI300",
    "gate": "same_scheduled_gate_intervals_as_path_G", "off_return": 0.0,
    "investable_portfolio": False,
}


def breadth_contract_identity(contract: dict[str, Any], *, normalized_bars_id: str,
                              universe_id: str) -> dict[str, Any]:
    value = {
        "schema_version": "breadth-contract-binding-v1",
        "provider_id": "tushare-pro-v1",
        "normalized_bars_id": normalized_bars_id,
        "universe_id": universe_id,
        "formal_regime_contract": contract,
        "raw_metric": "share of Fixed-100 symbols above own 20-session moving average",
        "thresholds": "expanding past-only 1/3 and 2/3 quantiles",
        "historical_quantile_window": "expanding",
        "minimum_history": 504,
        "gate_lag_trade_sessions": 1,
        "runtime_semantics": "build_regimes state at t already represents t-1 raw breadth; consume directly and never shift twice",
        "active_state_mapping": {"narrow": "narrow_or_weak"},
        "quality_rules": ["PIT only", "no fill", "unavailable warm-up stays unavailable"],
    }
    value["breadth_contract_id"] = "bmc1_" + hash_payload(value)
    value["breadth_dataset_id"] = "bmd1_" + hash_payload({
        "normalized_bars_id": normalized_bars_id,
        "universe_id": universe_id,
        "breadth_contract_id": value["breadth_contract_id"],
    })
    return value


def gate_spec(*, breadth: dict[str, Any], universe_id: str) -> dict[str, Any]:
    strategy = {
        "schema_version": "breadth-gated-strategy-protocol-v1",
        "paths": {"U": PATH_U, "G": PATH_G, "R": PATH_R},
    }
    strategy_id = "bgmsp1_" + hash_payload(strategy)
    return {
        "schema_version": "breadth-momentum-gate-spec-v1",
        "provider_id": "tushare-pro-v1", "task_id": TASK_ID,
        "signal_artifact_id": SOURCE_SIGNAL_ARTIFACT_ID,
        "signal_name": SOURCE_SIGNAL_NAME, "canonical_formula": SOURCE_FORMULA,
        "source_diagnostic_id": SOURCE_DIAGNOSTIC_ID,
        "source_classification_id": SOURCE_CLASSIFICATION_ID,
        "source_classification": "regime_specific_factor",
        "breadth_dataset_id": breadth["breadth_dataset_id"],
        "breadth_contract_id": breadth["breadth_contract_id"],
        "breadth_contract": breadth,
        "active_regime": "narrow_or_weak", "formal_source_state": "narrow",
        "gate_lag": 1, "gate_expression": "breadth_regime[t-1] == narrow_or_weak",
        "runtime_gate_rule": "gate_on[t] = (build_regimes(...).breadth_regime[t] == 'narrow') because the formal builder already lags raw breadth one session",
        "double_lag_forbidden": True, "fresh_start_date": FRESH_START_DATE,
        "universe_id": universe_id, "strategy_protocol_id": strategy_id,
        "paths": strategy["paths"], "cash_policy": "zero_return_no_interest",
        "threshold_search_allowed": False, "gate_state_search_allowed": False,
        "parameter_optimization_allowed": False, "registry_writes": 0,
        "promotion_writes": 0, "version": 1,
    }


def fresh_lock(spec: dict[str, Any], *, universe_id: str) -> dict[str, Any]:
    return {
        "schema_version": "breadth-gated-momentum-fresh-lock-v1",
        "provider_id": "tushare-pro-v1", "task_id": TASK_ID,
        "signal_artifact_id": SOURCE_SIGNAL_ARTIFACT_ID,
        "gate_spec_id": spec["gate_spec_id"], "universe_id": universe_id,
        "dataset_authority": "TUSHARE_AUTHORITY_V1",
        "fresh_start_date": FRESH_START_DATE, "paths": spec["paths"],
        "metrics_contract": {
            "required": ["path_u_net_return", "path_g_net_return", "path_r_return",
                         "conditional_selection_alpha", "path_g_maximum_drawdown",
                         "path_g_turnover", "path_g_transaction_cost", "gate_on_rankic",
                         "gate_on_q10_universe", "gate_on_hit_rate"],
            "success": "alpha>0 and RankIC>0 and Q10-universe>0 and G drawdown<=U drawdown",
            "rejection": "alpha<=0 and Q10-universe<=0",
        },
        "minimum_evidence_policy": MINIMUM_EVIDENCE,
        "no_backfill": True, "historical_cutoff": "2026-06-23",
        "status": "locked_awaiting_fresh_data", "fresh_results_are_report_only": True,
        "agent_memory_access": False, "optimization_access": False,
        "candidate_selection_access": False, "registry_writes": 0, "promotion_writes": 0,
    }
