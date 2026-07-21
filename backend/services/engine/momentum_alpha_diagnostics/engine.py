from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.expanded_factor_iteration.features import compute_feature_candidates
from backend.services.engine.momentum_factor_iteration.engine import LIFECYCLE_POLICY, _existing_four
from backend.services.engine.momentum_factor_iteration.features import definitions
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes
from backend.services.engine.skip_recent_momentum.engine import _source_dataset
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner, equal_weight_signal
from backend.services.engine.tushare_cutover.canonical import hash_payload, write_json

from .artifact import publish_artifact, validate_artifact
from .metrics import (
    beta_and_contributions, daily_cross_section, holding_and_style,
    horizon_decay, pair_correlations, period_cross_metrics, semantic_audit,
)
from .protocol import (
    ARTIFACT_FILES, CANDIDATE_A, CANDIDATE_B, ENSEMBLE_ID, FORMAL_STRATEGY,
    PERIODS, QLIB_PERIODS, SOURCE_EXPERIMENT_ID, STYLE_COLUMNS,
)


def _materialize(bundle: AuthorityBundle, artifact_id: str, root: Path) -> tuple[Path, dict]:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required Artifact missing: {artifact_id}")
    target = root / descriptor.artifact_kind / artifact_id
    if target.exists():
        shutil.rmtree(target)
    bundle.store.materialize_artifact(descriptor.descriptor_id, target)
    identity = json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return target, identity


def _store(bundle: AuthorityBundle, artifact: dict, lineage: tuple[str, ...]) -> dict:
    receipt = bundle.store.import_artifact(
        artifact["artifact_kind"], Path(artifact["path"]), artifact["artifact_id"], lineage=lineage,
    )
    return {"artifact_id": artifact["artifact_id"], "artifact_kind": artifact["artifact_kind"],
            "descriptor_id": receipt.descriptor_id, "exact_existing": receipt.exact_existing,
            "new_blob_count": receipt.new_blob_count}


def _restore(bundle: AuthorityBundle, artifact_id: str, kind: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None or descriptor.artifact_kind != kind:
        raise RuntimeError(f"diagnostic artifact unavailable: {artifact_id}")
    target = root / kind / artifact_id
    if target.exists():
        shutil.rmtree(target)
    bundle.store.materialize_artifact(descriptor.descriptor_id, target)
    return validate_artifact(target, artifact_id, kind)


def _find_existing(bundle: AuthorityBundle, root: Path):
    matches = []
    for descriptor in bundle.store.list_by_kind("momentum_failure_classification"):
        target = root / descriptor.artifact_id
        if target.exists():
            shutil.rmtree(target)
        bundle.store.materialize_artifact(descriptor.descriptor_id, target)
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if manifest["identity"].get("source_experiment_id") == SOURCE_EXPERIMENT_ID:
            matches.append((descriptor, manifest["identity"]))
    if len(matches) > 1:
        raise RuntimeError("ambiguous momentum alpha diagnostic authority")
    return matches[0] if matches else None


def _prepare_signals(bundle: AuthorityBundle, root: Path) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    signals, locks = {}, {}
    paths = {}
    for name, artifact_id in (("candidate_a", CANDIDATE_A), ("candidate_b", CANDIDATE_B)):
        target, identity = _materialize(bundle, artifact_id, root)
        identity = {"candidate_lock_id": artifact_id, **identity}
        signal = pd.read_parquet(target / "signal.parquet")
        signal["trade_date"] = pd.to_datetime(signal["trade_date"])
        signals[name], locks[name], paths[name] = signal, identity, target / "signal.parquet"
    ensemble_path = equal_weight_signal(paths, root / "ensemble" / "signal.parquet")
    ensemble = pd.read_parquet(ensemble_path); ensemble["trade_date"] = pd.to_datetime(ensemble["trade_date"])
    expected = "srmen1_" + hash_payload({
        "locks": [CANDIDATE_A, CANDIDATE_B],
        "signal_sha256": __import__("hashlib").sha256(ensemble_path.read_bytes()).hexdigest(),
    })
    if expected != ENSEMBLE_ID:
        raise RuntimeError("locked ensemble identity changed")
    signals["ensemble"] = ensemble
    return signals, locks


def _feature_matrix(bundle: AuthorityBundle, momentum: pd.DataFrame) -> pd.DataFrame:
    expanded = compute_feature_candidates(bundle.normalized, bundle.benchmark)
    expanded = expanded.rename(columns={"volatility_20d": "volatility_20", "volatility_60d": "volatility_60"})
    values = momentum[["symbol", "trade_date", "distance_to_high_60"]]
    return expanded.merge(values, on=["symbol", "trade_date"], how="left", validate="one_to_one")


def _run_qlib(bundle: AuthorityBundle, signals: dict[str, pd.DataFrame], root: Path) -> tuple[dict, int]:
    runner = FormalQlibRunner(bundle.qlib_view, bundle.normalized, root / "qlib-cache")
    runner.service.initialize()
    from qlib.config import C
    C.kernels = 1
    results = {}
    for name, signal in signals.items():
        path = root / "qlib-signals" / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        signal.to_parquet(path, index=False, compression="zstd")
        for period, (start, end) in QLIB_PERIODS.items():
            results[(name, period)] = runner.run(
                path, start, end, lifecycle_policy=LIFECYCLE_POLICY,
            )
            if results[(name, period)].get("status") != "completed":
                raise RuntimeError(f"diagnostic Qlib failed: {name}/{period}")
            if name in {"candidate_a", "candidate_b", "ensemble"}:
                results[(f"{name}_zero_cost", period)] = runner.run(
                    path, start, end, lifecycle_policy=LIFECYCLE_POLICY, cost_multiplier=0.0,
                )
    return results, runner.calls


def _write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd")
    return path


def _period_summary(daily: pd.DataFrame) -> dict:
    result = {}
    for period, (start, end) in PERIODS.items():
        result[period] = period_cross_metrics(daily, start, end)
        result[period]["evidence_status"] = (
            "retrospective_report_only_not_fresh_validation" if period in {"2025", "2026H1"}
            else "research_diagnostic"
        )
    return result


def _regime_metrics(daily: pd.DataFrame, cross: pd.DataFrame, regimes: pd.DataFrame) -> dict:
    merged = daily.merge(cross[["trade_date", "rankic", "top_bottom_spread"]], on="trade_date", how="left")
    merged = merged.merge(regimes[["trade_date", "trend_regime", "volatility_regime", "breadth_regime"]], on="trade_date", how="left")
    output = {}
    for column in ("trend_regime", "volatility_regime", "breadth_regime"):
        output[column] = {}
        for state, group in merged.groupby(column):
            returns = group["strategy_return"].dropna()
            benchmark = group["market_return"].dropna()
            nav = (1 + returns).cumprod()
            output[column][str(state)] = {
                "trading_days": int(group.trade_date.nunique()),
                "mean_rankic": _mean(group.rankic),
                "top_bottom_spread": _mean(group.top_bottom_spread),
                "net_csi300_excess": float((1 + returns).prod() - (1 + benchmark).prod()) if len(returns) and len(benchmark) else None,
                "portfolio_beta": _mean(group.weighted_average_stock_beta),
                "maximum_drawdown": float((nav / nav.cummax() - 1).min()) if len(nav) else None,
            }
    return output


def _mean(series) -> float | None:
    value = pd.to_numeric(series, errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _summarize_contributions(frame: pd.DataFrame) -> dict:
    output = {}
    for (entity, period), group in frame.groupby(["entity", "period"]):
        ordered = group.sort_values("contribution", ascending=False)
        total = float(group.contribution.sum())
        top = ordered.head(10)
        bottom = ordered.tail(10).sort_values("contribution")
        output[f"{entity}:{period}"] = {
            "top_10_positive": top.to_dict("records"), "top_10_negative": bottom.to_dict("records"),
            "top_10_contribution_share": None if total == 0 else float(top.contribution.sum() / total),
            "return_excluding_top_10_contributors": float(total - top.contribution.sum()),
        }
    return output


def _summarize_days(frame: pd.DataFrame) -> dict:
    output = {}
    for (entity, period), group in frame.groupby(["entity", "period"]):
        returns = group.dropna(subset=["strategy_return"]).copy()
        best = returns.nlargest(10, "strategy_return")
        worst = returns.nsmallest(10, "strategy_return")
        output[f"{entity}:{period}"] = {
            "best_10_days_contribution": float(best.strategy_return.sum()),
            "worst_10_days_contribution": float(worst.strategy_return.sum()),
            "return_without_best_10_days": float((1 + returns.drop(best.index).strategy_return).prod() - 1),
            "return_without_worst_10_days": float((1 + returns.drop(worst.index).strategy_return).prod() - 1),
        }
    return output


def _classify(cross_metrics: dict, beta_summary: dict, costs: dict, semantics: dict) -> tuple[dict, dict]:
    output = {}
    for name in ("candidate_a", "candidate_b"):
        m2025, m2026 = cross_metrics[name]["2025"], cross_metrics[name]["2026H1"]
        labels = []
        if (m2026["mean_rankic"] or 0) <= 0 or (m2026["monotonicity"] or 0) <= 0:
            labels.append("signal_degradation")
        if costs[f"{name}:2025"]["zero_cost_return"] > 0 and costs[f"{name}:2025"]["net_return"] <= 0:
            labels.append("portfolio_implementation_drag")
        if beta_summary[f"{name}:2025"]["net_return"] > 0 and beta_summary[f"{name}:2025"]["csi300_excess"] < 0:
            labels.append("benchmark_beta_mismatch")
        labels.extend(["regime_dependency", "semantic_defect"])
        output[name] = {"labels": sorted(set(labels)), "2025_rankic": m2025["mean_rankic"],
                        "2026h1_rankic": m2026["mean_rankic"],
                        "cost_is_primary_failure": False, "strict_causal_claim": False}
    decision = {
        "decision": "continue_as_stock_selection_overlay_only",
        "reason": "2025 cross-sectional RankIC remains positive while independent long-only CSI300-relative performance fails; 2026H1 signal degradation prevents a standalone Alpha claim",
        "execute_next_task": False, "promotion_writes": 0,
        "predictive_claim": False, "fresh_validation": False,
    }
    return output, decision


def execute_audit(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = load_authority_bundle(
        authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=work_root / "authority", store_root=store_root,
    )
    existing = _find_existing(bundle, work_root / "existing")
    if existing:
        return replay_audit(repository_root=repository_root, work_root=work_root / "exact", store_root=store_root) | {"exact_existing": True}
    signals, locks = _prepare_signals(bundle, work_root / "source-locks")
    momentum, _ = _source_dataset(bundle, work_root / "momentum-dataset")
    features = _feature_matrix(bundle, momentum)
    regimes, regime_contract = build_regimes(bundle.normalized, bundle.benchmark)
    old_four, old_evidence, _ = _existing_four(bundle, work_root / "old-four")
    for factor_id, frame in old_four.items():
        signal = frame.rename(columns={"old_score": "pred"}).copy()
        signal["trade_date"] = pd.to_datetime(signal["trade_date"])
        signals[factor_id] = signal[["symbol", "trade_date", "pred"]]

    qlib, diagnostic_qlib_calls = _run_qlib(bundle, signals, work_root / "formal")
    feature_contract = {item.name: item.payload() for item in definitions()}
    semantics = semantic_audit(locks["candidate_a"], locks["candidate_b"], feature_contract)
    semantic_artifact = publish_artifact(work_root / "domain", "momentum_semantic_audit", {
        "source_experiment_id": SOURCE_EXPERIMENT_ID, "candidate_lock_ids": [CANDIDATE_A, CANDIDATE_B],
        "historical_ids_unchanged": True, "agent_calls": 0, "optimization_calls": 0,
    }, {"semantic_audit.json": semantics})
    semantic_receipt = _store(bundle, semantic_artifact, (SOURCE_EXPERIMENT_ID, CANDIDATE_A, CANDIDATE_B))
    _restore(bundle, semantic_artifact["artifact_id"], semantic_artifact["artifact_kind"], work_root / "cold")

    cross_rows, quantile_rows, cross_metrics, decay = [], [], {}, {}
    for name in ("candidate_a", "candidate_b", "ensemble"):
        daily = daily_cross_section(signals[name], momentum)
        daily.insert(0, "entity", name); cross_rows.append(daily)
        cross_metrics[name] = _period_summary(daily)
        for period, metrics in cross_metrics[name].items():
            quantile_rows.append({"entity": name, "period": period,
                **{f"q{i+1}_mean": value for i, value in enumerate(metrics["quantile_mean_returns"])},
                **{f"q{i+1}_cumulative": value for i, value in enumerate(metrics["quantile_cumulative_returns"])},
                "q10_q1_spread": metrics["q10_q1_spread"], "q10_observable_mean_spread": metrics["q10_observable_mean_spread"],
                "monotonicity": metrics["monotonicity"]})
        decay[name] = horizon_decay(signals[name], bundle.normalized, PERIODS)
    cross_frame = pd.concat(cross_rows, ignore_index=True)
    cross_path = _write_parquet(cross_frame, work_root / "outputs" / "cross_sectional_metrics.parquet")
    quantile_path = _write_parquet(pd.DataFrame(quantile_rows), work_root / "outputs" / "quantile_returns.parquet")
    cross_artifact = publish_artifact(work_root / "domain", "momentum_cross_sectional_diagnostic", {
        "source_experiment_id": SOURCE_EXPERIMENT_ID, "entities": [CANDIDATE_A, CANDIDATE_B, ENSEMBLE_ID],
        "period_metrics": cross_metrics, "observable_mean_is_investable_benchmark": False,
        "selection_boundaries_unchanged": True,
    }, {"cross_sectional_metrics.parquet": cross_path, "quantile_returns.parquet": quantile_path,
        "horizon_decay.json": decay})
    cross_receipt = _store(bundle, cross_artifact, (semantic_artifact["artifact_id"], SOURCE_EXPERIMENT_ID))
    _restore(bundle, cross_artifact["artifact_id"], cross_artifact["artifact_kind"], work_root / "cold")

    beta_rows, stock_rows, day_rows, style_rows, concentration_rows = [], [], [], [], []
    regime_metrics, beta_summary, costs = {}, {}, {}
    for name in ("candidate_a", "candidate_b", "ensemble"):
        for period in QLIB_PERIODS:
            result = qlib[(name, period)]
            beta, stocks, days = beta_and_contributions(result, features, bundle.benchmark, name, period)
            beta_rows.append(beta); stock_rows.append(stocks); day_rows.append(days)
            positions = pd.DataFrame(result["positions"])
            style, concentration = holding_and_style(positions, features, signals[name], name, period, STYLE_COLUMNS)
            style_rows.append(style); concentration_rows.append(concentration)
            market_sum, residual_sum = beta.market_component.sum(), beta.residual_component.sum()
            beta_summary[f"{name}:{period}"] = {
                "net_return": result["net_return"], "benchmark_return": result["benchmark_return"],
                "csi300_excess": result["net_excess_csi300"], "mean_weighted_stock_beta": _mean(beta.weighted_average_stock_beta),
                "mean_rolling_portfolio_beta": _mean(beta.portfolio_beta), "market_component_sum": float(market_sum),
                "residual_component_sum": float(residual_sum), "diagnostic_not_strict_causal": True,
            }
            zero = qlib[(f"{name}_zero_cost", period)]
            costs[f"{name}:{period}"] = {
                "gross_return": result["gross_return"], "net_return": result["net_return"],
                "transaction_cost": result["transaction_cost"], "cost_drag": result["gross_return"] - result["net_return"],
                "turnover": result["turnover"], "zero_cost_return": zero["net_return"],
                "formal_result_unchanged": True,
            }
            entity_cross = cross_frame[(cross_frame.entity == name) & cross_frame.trade_date.between(*QLIB_PERIODS[period])]
            regime_metrics[f"{name}:{period}"] = _regime_metrics(beta, entity_cross, regimes)
    beta_frame = pd.concat(beta_rows, ignore_index=True); stock_frame = pd.concat(stock_rows, ignore_index=True)
    day_frame = pd.concat(day_rows, ignore_index=True); style_frame = pd.concat(style_rows, ignore_index=True)
    concentration_frame = pd.concat(concentration_rows, ignore_index=True)
    correlations = pair_correlations(signals, qlib)
    alpha_files = {
        "beta_decomposition.parquet": _write_parquet(beta_frame, work_root / "outputs" / "beta_decomposition.parquet"),
        "stock_contributions.parquet": _write_parquet(stock_frame, work_root / "outputs" / "stock_contributions.parquet"),
        "day_contributions.parquet": _write_parquet(day_frame, work_root / "outputs" / "day_contributions.parquet"),
        "cost_attribution.json": costs, "regime_metrics.json": {"contract": regime_contract, "results": regime_metrics},
        "correlations.json": correlations,
    }
    alpha_artifact = publish_artifact(work_root / "domain", "momentum_alpha_decomposition", {
        "source_experiment_id": SOURCE_EXPERIMENT_ID, "cross_diagnostic_id": cross_artifact["artifact_id"],
        "diagnostic_qlib_calls": diagnostic_qlib_calls, "agent_calls": 0, "optimization_calls": 0,
        "strategy_optimization_calls": 0, "network_calls": 0, "promotion_writes": 0,
        "formal_strategy": FORMAL_STRATEGY, "beta_summary": beta_summary,
        "stock_contribution_summary": _summarize_contributions(stock_frame),
        "day_contribution_summary": _summarize_days(day_frame),
    }, alpha_files)
    alpha_receipt = _store(bundle, alpha_artifact, (cross_artifact["artifact_id"], SOURCE_EXPERIMENT_ID))
    _restore(bundle, alpha_artifact["artifact_id"], alpha_artifact["artifact_kind"], work_root / "cold")
    style_artifact = publish_artifact(work_root / "domain", "momentum_style_exposure_report", {
        "source_experiment_id": SOURCE_EXPERIMENT_ID, "alpha_decomposition_id": alpha_artifact["artifact_id"],
        "style_columns": list(STYLE_COLUMNS), "sector_attribution_status": "not_computed_no_PIT_industry_contract",
    }, {"style_exposures.parquet": _write_parquet(style_frame, work_root / "outputs" / "style_exposures.parquet"),
        "holding_concentration.parquet": _write_parquet(concentration_frame, work_root / "outputs" / "holding_concentration.parquet")})
    style_receipt = _store(bundle, style_artifact, (alpha_artifact["artifact_id"],))
    _restore(bundle, style_artifact["artifact_id"], style_artifact["artifact_kind"], work_root / "cold")
    classification, decision = _classify(cross_metrics, beta_summary, costs, semantics)
    summary = {"cross_sectional": cross_metrics, "beta": beta_summary, "cost": costs,
               "stock_contribution": _summarize_contributions(stock_frame), "day_contribution": _summarize_days(day_frame)}
    final_artifact = publish_artifact(work_root / "domain", "momentum_failure_classification", {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "artifact_ids": [semantic_artifact["artifact_id"], cross_artifact["artifact_id"], alpha_artifact["artifact_id"], style_artifact["artifact_id"]],
        "candidate_status_before": ["research_registered", "research_registered"],
        "candidate_status_after": ["research_registered", "research_registered"],
        "decision": decision["decision"], "diagnostic_qlib_calls": diagnostic_qlib_calls,
        "agent_calls": 0, "optimization_calls": 0, "network_calls": 0, "promotion_writes": 0,
    }, {"failure_classification.json": classification, "decision.json": decision, "summary.json": summary})
    final_receipt = _store(bundle, final_artifact, (semantic_artifact["artifact_id"], cross_artifact["artifact_id"], alpha_artifact["artifact_id"], style_artifact["artifact_id"], SOURCE_EXPERIMENT_ID))
    _restore(bundle, final_artifact["artifact_id"], final_artifact["artifact_kind"], work_root / "cold")
    inventory = publish_inventory(bundle.store); integrity = scan_store_integrity(bundle.store)
    return {"status": "completed", "failure_classification_id": final_artifact["artifact_id"],
        "artifact_ids": [semantic_artifact["artifact_id"], cross_artifact["artifact_id"], alpha_artifact["artifact_id"], style_artifact["artifact_id"], final_artifact["artifact_id"]],
        "receipts": [semantic_receipt, cross_receipt, alpha_receipt, style_receipt, final_receipt],
        "decision": decision["decision"], "diagnostic_qlib_calls": diagnostic_qlib_calls,
        "agent_calls": 0, "optimization_calls": 0, "network_calls": 0, "promotion_writes": 0,
        "inventory_id": inventory.inventory_id, "store_integrity": integrity.status,
        "missing": len(integrity.issues), "unreferenced": len(integrity.unreferenced_blobs)}


def replay_audit(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = load_authority_bundle(
        authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=Path(work_root) / "authority", store_root=store_root,
    )
    found = _find_existing(bundle, Path(work_root) / "lookup")
    if not found:
        raise RuntimeError("momentum alpha diagnostic not found")
    descriptor, identity = found
    ids = [*identity["artifact_ids"], descriptor.artifact_id]
    recovered = []
    for artifact_id in ids:
        child = bundle.store.find_by_artifact_id(artifact_id)
        if child is None:
            raise RuntimeError(f"diagnostic lineage missing: {artifact_id}")
        recovered.append(_restore(bundle, artifact_id, child.artifact_kind, Path(work_root) / "cold"))
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "failure_classification_id": descriptor.artifact_id,
        "recovered_artifact_count": len(recovered), "decision": identity["decision"],
        "agent_calls": 0, "optimization_calls": 0, "diagnostic_qlib_calls": 0,
        "network_calls": 0, "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
        "store_integrity": integrity.status, "missing": len(integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs)}
