from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.tushare_agent_experiment.artifact import publish_experiment_artifact
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .policy import SecurityTerminationEvent, SecurityTerminationPolicyV1


ORIGINAL_EXPERIMENT_ID = "tha_2b3676218af9693cf6bfcf0ab47d102db0cc865f94f0e5b54de6fba26d76383b"
LIFECYCLE_FOLLOWUP_ID = "thf_9f38986394640cab4ca7362ed0f876e02e408fe65c5b941a4c3667c4cd7307b2"
PARITY_FIELDS = (
    "gross_return", "net_return", "benchmark_return", "fixed_100_benchmark_return",
    "net_excess_csi300", "net_excess_fixed_100", "turnover", "transaction_cost",
    "max_drawdown", "sharpe_ratio",
)


def _materialize(store, artifact_id: str, root: Path) -> Path:
    descriptor = store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required Artifact missing: {artifact_id}")
    target = root / artifact_id
    if target.exists():
        shutil.rmtree(target)
    store.materialize_artifact(descriptor.descriptor_id, target)
    return target


def _equal(left, right) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return abs(float(left) - float(right)) <= 1e-12
    except (TypeError, ValueError):
        return left == right


def _positions_equal(left: dict, right: dict) -> bool:
    key = lambda row: (row["date"], row["symbol"], row["side"])
    first, second = sorted(left.get("positions") or [], key=key), sorted(right.get("positions") or [], key=key)
    return len(first) == len(second) and all(
        key(a) == key(b)
        and _equal(a.get("amount"), b.get("amount"))
        and _equal(a.get("weight"), b.get("weight"))
        for a, b in zip(first, second)
    )


def _event_from_audit(row: dict, *, source_artifact: str) -> SecurityTerminationEvent:
    evidence = {
        key: row.get(key)
        for key in (
            "symbol", "ts_code", "list_status", "list_date", "delist_date",
            "last_market_date", "last_daily_row", "last_adj_factor_row",
            "last_daily_basic_row", "qlib_end_date",
        )
    }
    return SecurityTerminationEvent(
        symbol=row["symbol"], event_type="delisting",
        last_tradable_date=row["last_market_date"], effective_date=row["delist_date"],
        settlement_date=None, settlement_currency=None, cash_per_share=None,
        replacement_symbol=None, conversion_ratio=None, source_artifact=source_artifact,
        evidence_hash=hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
    )


def _position_timeline(
    *, strategies: dict, events: list[SecurityTerminationEvent], normalized: pd.DataFrame,
    fixed_symbols: set[str],
) -> pd.DataFrame:
    market = normalized[normalized.symbol.isin(fixed_symbols)].copy()
    market["trade_date"] = pd.to_datetime(market.trade_date)
    dates = sorted(market.loc[
        (market.trade_date >= "2025-01-02") & (market.trade_date <= "2025-12-30"),
        "trade_date",
    ].unique())
    rows = []
    for event in events:
        last_day, effective = pd.Timestamp(event.last_tradable_date), pd.Timestamp(event.effective_date)
        before = [pd.Timestamp(day) for day in dates if pd.Timestamp(day) <= last_day][-60:]
        after = [pd.Timestamp(day) for day in dates if pd.Timestamp(day) > effective][:20]
        window = sorted(set(before + [pd.Timestamp(day) for day in dates if last_day < pd.Timestamp(day) <= effective] + after))
        quotes = market[market.symbol == event.symbol].set_index("trade_date")
        for strategy_id, result in strategies.items():
            positions = {
                pd.Timestamp(item["date"]): item
                for item in result.get("positions", []) if item.get("symbol") == event.symbol
            }
            equity = {
                pd.Timestamp(item["date"]): item.get("value")
                for item in result.get("equity_curve", [])
            }
            for day in window:
                position = positions.get(day)
                quote = quotes.loc[day] if day in quotes.index else None
                amount = 0.0 if position is None else float(position.get("amount") or 0.0)
                adjusted_close = None if quote is None else float(quote.adjusted_close)
                rows.append({
                    "strategy_id": strategy_id, "symbol": event.symbol, "trade_date": day,
                    "target_weight": None,
                    "target_weight_status": "not_emitted_by_topk_dropout",
                    "actual_position_amount": amount,
                    "actual_position_weight": 0.0 if position is None else float(position.get("weight") or 0.0),
                    "position_market_value": 0.0 if position is None else amount * adjusted_close,
                    "account_value": equity.get(day), "observable": quote is not None,
                    "tradable": False if quote is None else bool(quote.tradable),
                    "adjusted_close": adjusted_close,
                    "valuation_state": "flat" if position is None else "authoritative_qlib_position",
                })
        for day in window:
            day_market = market[market.trade_date == day]
            quote = quotes.loc[day] if day in quotes.index else None
            observable_count = int(day_market.symbol.nunique())
            observable = quote is not None
            weight = (1.0 / observable_count) if observable and observable_count else 0.0
            unresolved = day > last_day
            rows.append({
                "strategy_id": "fixed_100_equal_weight_benchmark", "symbol": event.symbol,
                "trade_date": day, "target_weight": weight,
                "target_weight_status": "daily_observable_equal_weight",
                "actual_position_amount": None,
                "actual_position_weight": None if unresolved else weight,
                "position_market_value": None if unresolved else weight,
                "account_value": 1.0, "observable": observable,
                "tradable": False if quote is None else bool(quote.tradable),
                "adjusted_close": None if quote is None else float(quote.adjusted_close),
                "valuation_state": (
                    "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED" if unresolved
                    else "unit_notional_observable_benchmark_position"
                ),
            })
    return pd.DataFrame(rows).sort_values(["symbol", "strategy_id", "trade_date"], kind="mergesort")


def run_termination_audit(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = load_authority_bundle(
        authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=work_root / "authority", store_root=store_root,
    )
    store = bundle.store
    lifecycle_path = _materialize(store, LIFECYCLE_FOLLOWUP_ID, work_root / "source")
    lifecycle_audit = json.loads((lifecycle_path / "symbol_lifecycle_audit.json").read_text())
    target_rows = sorted(lifecycle_audit["absent_2026h1"], key=lambda row: row["symbol"])
    target_symbols = tuple(row["symbol"] for row in target_rows)
    policy = SecurityTerminationPolicyV1()
    identity = {
        "provider_id": "tushare-pro-v1", "policy_id": policy.policy_id,
        "original_experiment_id": ORIGINAL_EXPERIMENT_ID,
        "lifecycle_followup_id": LIFECYCLE_FOLLOWUP_ID,
        "target_symbols": list(target_symbols), "audit_period": ["2025-01-02", "2025-12-30"],
        "promotion_writes": 0,
    }
    intended_id = "htf_" + hash_payload(identity)
    existing = store.find_by_artifact_id(intended_id)
    if existing is not None:
        with tempfile.TemporaryDirectory() as cold:
            store.materialize_artifact(existing.descriptor_id, Path(cold) / intended_id)
        integrity = scan_store_integrity(store)
        return {"status": "exact_replay", "artifact_id": intended_id, "qlib_calls": 0,
                "new_artifacts": 0, "new_blobs": 0, "integrity": integrity.status}

    experiment_path = _materialize(store, ORIGINAL_EXPERIMENT_ID, work_root / "source")
    experiment = json.loads((experiment_path / "experiment.json").read_text())
    qlib_id = experiment["qlib_backtest_result_id"]
    qlib_path = _materialize(store, qlib_id, work_root / "source")
    source_results = json.loads((qlib_path / "results.json").read_text())
    signal_paths = {path.stem: path for path in sorted((qlib_path / "signals").glob("*.parquet"))}
    universe500_id = bundle.authority["universe_500"]["universe_lock_id"]
    events = [_event_from_audit(row, source_artifact=universe500_id) for row in target_rows]

    runner = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    reruns, parity = {}, {}
    for strategy_id, signal_path in signal_paths.items():
        rerun = runner.run(
            signal_path, "2025-01-02", "2025-12-30",
            lifecycle_policy={
                "policy_id": "fulp_60672b83992c16796af70683eafa9607a8d7ab3cc4cc6438059f8f25100a632a",
                "locked_member_count": 100, "minimum_observable_instruments": 25,
            },
            execution_audit_symbols=target_symbols,
        )
        original = source_results["annual_backtests"][strategy_id]["2025"]
        checks = {field: _equal(original.get(field), rerun.get(field)) for field in PARITY_FIELDS}
        parity[strategy_id] = {
            "passed": rerun.get("status") == "completed" and all(checks.values()) and _positions_equal(original, rerun),
            "metric_equality": checks, "positions_equal": _positions_equal(original, rerun),
        }
        reruns[strategy_id] = rerun
    if not all(item["passed"] for item in parity.values()):
        raise RuntimeError("2025 termination audit rerun differs from immutable source")

    normalized = bundle.normalized.copy()
    normalized["trade_date"] = pd.to_datetime(normalized.trade_date)
    strategy_exposure = {}
    for strategy_id, result in reruns.items():
        strategy_exposure[strategy_id] = {}
        orders = result["execution_audit"]["orders"]
        original = source_results["annual_backtests"][strategy_id]["2025"]
        for event in events:
            positions = [row for row in original.get("positions", []) if row.get("symbol") == event.symbol]
            classification = policy.classify_strategy_exposure(
                symbol=event.symbol, last_tradable_date=event.last_tradable_date,
                positions=positions, orders=orders, events=[event],
            )
            buys = [row for row in orders if row["symbol"] == event.symbol and row["action"] == "buy"]
            sells = [row for row in orders if row["symbol"] == event.symbol and row["action"] == "sell"]
            last_position = max(positions, key=lambda row: row["date"]) if positions else None
            market_value = None
            if last_position:
                quote = normalized[
                    (normalized.symbol == event.symbol)
                    & (normalized.trade_date == pd.Timestamp(last_position["date"]))
                ]
                market_value = float(last_position["amount"] * quote.iloc[0].adjusted_close)
            strategy_exposure[strategy_id][event.symbol] = classification | {
                "daily_target_weight_status": "not_emitted_by_topk_dropout",
                "position_day_count": len(positions), "buy_trade_count": len(buys),
                "sell_trade_count": len(sells),
                "last_buy": max(buys, key=lambda row: row["start_time"]) if buys else None,
                "last_sell": max(sells, key=lambda row: row["start_time"]) if sells else None,
                "last_position": last_position, "last_recorded_market_value": market_value,
                "position_after_last_tradable_date": any(row["date"] > event.last_tradable_date for row in positions),
                "position_after_effective_date": any(row["date"] > event.effective_date for row in positions),
                "affected_dates": [], "affected_positions": 0, "affected_shares": 0.0,
                "stale_valuation_days": 0, "portfolio_weight_at_last_trade": 0.0,
                "maximum_possible_metric_impact": 0.0,
            }

    fixed_symbols = set(bundle.matrix.symbol.unique())
    market = normalized[normalized.symbol.isin(fixed_symbols)]
    audit_dates = sorted(market.loc[
        (market.trade_date >= "2025-01-02") & (market.trade_date <= "2025-12-30"),
        "trade_date",
    ].unique())
    benchmark_exposure = {}
    for event in events:
        day = pd.Timestamp(event.last_tradable_date)
        observable_count = int(market.loc[market.trade_date == day, "symbol"].nunique())
        weight = 1.0 / observable_count
        affected = [pd.Timestamp(item).strftime("%Y-%m-%d") for item in audit_dates if pd.Timestamp(item) > day]
        benchmark_exposure[event.symbol] = {
            "classification": "BENCHMARK_EXPOSURE_ONLY",
            "settlement_status": "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED",
            "canonical": False, "last_tradable_date": event.last_tradable_date,
            "effective_date": event.effective_date, "affected_dates": affected,
            "affected_positions": 1, "affected_shares": None,
            "last_recorded_market_value": weight, "unit_notional": 1.0,
            "stale_valuation_days": None,
            "stale_valuation_status": "implementation_removes_member_instead_of_carrying_a_formal_valuation",
            "portfolio_weight_at_last_trade": None,
            "benchmark_weight_at_last_trade": weight,
            "maximum_possible_metric_impact": None,
            "metric_impact_status": "unbounded_without_cash_conversion_or_writeoff_evidence",
        }

    timeline = _position_timeline(
        strategies={key: source_results["annual_backtests"][key]["2025"] for key in signal_paths},
        events=events, normalized=normalized, fixed_symbols=fixed_symbols,
    )
    canonicality = {
        "schema_version": "security-termination-canonicality-v1",
        "2019_2024": {"portfolio_results": "canonical", "reason": "before audited terminations"},
        "2025": {
            "strategy_absolute_returns": "canonical",
            "strategy_csi300_excess": "canonical",
            "fixed_100_benchmark_return": "noncanonical",
            "strategy_fixed_100_excess": "noncanonical",
            "reason": "benchmark termination settlement evidence absent",
        },
        "2026h1": {"portfolio_results": "canonical", "reason": "both members inactive before period"},
        "2019_2026_full_period": {
            "strategy_absolute_returns": "canonical",
            "strategy_csi300_excess": "canonical",
            "fixed_100_benchmark_return": "noncanonical",
            "strategy_fixed_100_excess": "noncanonical",
        },
        "forbidden_decision_uses": [
            "promotion based on affected fixed-100 metrics",
            "agent feedback based on affected fixed-100 metrics",
            "factor ranking or parameter selection based on affected fixed-100 metrics",
        ],
        "corporate_action_provider_required": True,
        "task_outcome": "partial",
    }
    impact = {
        "schema_version": "security-termination-impact-summary-v1",
        "strategy_crossing_position_count": sum(
            item["classification"] == "UNRESOLVED_TERMINATION_POSITION"
            for result in strategy_exposure.values() for item in result.values()
        ),
        "benchmark_unresolved_position_count": 2,
        "settlement_evidence_available": False,
        "corrected_return_published": False,
        "reason": "no governed cash, conversion, merger exchange or write-off artifact",
        "parity": {
            "2019_2024": "source artifact unchanged; P0-015F parity retained",
            "2025": parity,
            "2026h1": "P0-015F artifact unchanged",
        },
        "agent_calls": 0, "optimization_trials": 0, "promotion_writes": 0,
        "tushare_network_calls": 0, "legacy_reads": 0,
    }

    artifact_root = work_root / "artifacts"
    timeline_path = work_root / "position_timeline.parquet"
    timeline.to_parquet(timeline_path, index=False, compression="zstd")
    artifact = publish_experiment_artifact(
        artifact_root, "historical_backtest_termination_followup", identity,
        {
            "policy.json": policy.payload(),
            "symbol_events.json": {"events": [event.payload() for event in events]},
            "strategy_exposure.json": strategy_exposure,
            "benchmark_exposure.json": benchmark_exposure,
            "position_timeline.parquet": timeline_path,
            "impact_summary.json": impact,
            "canonicality.json": canonicality,
        },
    )
    before_artifacts = len(store.list_artifacts())
    before_blobs = len({item.sha256 for descriptor in store.list_artifacts() for item in descriptor.files})
    receipt = store.import_artifact(
        "historical_backtest_termination_followup", Path(artifact["path"]),
        expected_artifact_id=artifact["termination_followup_id"],
        lineage=(ORIGINAL_EXPERIMENT_ID, LIFECYCLE_FOLLOWUP_ID, qlib_id, universe500_id),
    )
    inventory = publish_inventory(store)
    integrity = scan_store_integrity(store)
    with tempfile.TemporaryDirectory() as cold:
        store.materialize_artifact(receipt.descriptor_id, Path(cold) / receipt.artifact_id)
    return {
        "status": "partial", "artifact_id": receipt.artifact_id,
        "descriptor_id": receipt.descriptor_id, "policy_id": policy.policy_id,
        "qlib_calls": runner.calls, "strategy_exposure": strategy_exposure,
        "benchmark_exposure": benchmark_exposure, "canonicality": canonicality,
        "inventory_id": inventory.inventory_id, "artifact_count": inventory.artifact_count,
        "blob_count": inventory.unique_blob_count,
        "new_artifacts": len(store.list_artifacts()) - before_artifacts,
        "new_blobs": len({item.sha256 for descriptor in store.list_artifacts() for item in descriptor.files}) - before_blobs,
        "integrity": integrity.status, "integrity_issues": len(integrity.issues),
    }
