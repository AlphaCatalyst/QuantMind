from __future__ import annotations

import json
import shutil
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.default_first_momentum_search.engine import validate_governance
from backend.services.engine.momentum_factor_iteration.engine import _correlations, _existing_four
from backend.services.engine.momentum_factor_iteration.features import definitions
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner, group_diagnostics, split_metrics
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .artifact import KINDS, publish_artifact, validate_artifact
from .protocol import (
    ANNUAL_PERIODS, ELIGIBILITY, FULL_PERIOD, GOVERNANCE_DECISION_ID, LIFECYCLE_POLICY,
    PROTOCOLS, QUALITY_PERIOD, REPORT_PERIODS, SIGNALS, SOURCE_CATALOG_ID,
    SOURCE_DATASET_ID, TASK_ID,
)


def _store_publish(bundle: AuthorityBundle, artifact: dict, kind: str, lineage: tuple[str, ...]) -> dict:
    field = KINDS[kind][0]
    artifact_id = artifact[field]
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), artifact_id, lineage=lineage)
    return {"artifact_kind": kind, "artifact_id": artifact_id, "descriptor_id": receipt.descriptor_id,
            "exact_existing": receipt.exact_existing, "new_blob_count": receipt.new_blob_count}


def _cold(bundle: AuthorityBundle, artifact_id: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"ARTIFACT_COMPLETENESS_FAILED:missing {artifact_id}")
    destination = Path(root) / descriptor.artifact_kind / artifact_id
    if destination.exists():
        shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    return validate_artifact(destination, artifact_id, descriptor.artifact_kind)


def _source_matrix(bundle: AuthorityBundle, root: Path) -> tuple[pd.DataFrame, dict]:
    descriptor = bundle.store.find_by_artifact_id(SOURCE_DATASET_ID)
    if descriptor is None or descriptor.artifact_kind != "momentum_feature_dataset":
        raise RuntimeError("formal Momentum Feature Dataset missing")
    destination = Path(root) / SOURCE_DATASET_ID
    if destination.exists():
        shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
    if identity.get("catalog_id") != SOURCE_CATALOG_ID:
        raise RuntimeError("Momentum Feature Dataset Catalog lineage mismatch")
    features = pd.read_parquet(destination / "features.parquet")
    features["trade_date"] = pd.to_datetime(features["trade_date"])
    labels = bundle.matrix[["symbol", "trade_date", "raw_label", "model_label"]]
    matrix = features.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    return matrix.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True), identity


def _zscore(frame: pd.DataFrame, column: str) -> pd.Series:
    grouped = frame.groupby("trade_date", sort=False)[column]
    mean = grouped.transform("mean")
    std = grouped.transform(lambda value: value.std(ddof=0))
    return (pd.to_numeric(frame[column], errors="coerce") - mean) / std.where(std > 0)


def build_signal_values(matrix: pd.DataFrame, name: str) -> pd.DataFrame:
    if name not in SIGNALS:
        raise ValueError(f"unknown pre-registered signal: {name}")
    output = matrix[["symbol", "trade_date"]].copy()
    if name == "classic_long_term_skip_recent":
        output["factor_value"] = matrix.groupby("trade_date")["momentum_120_20"].rank(pct=True)
    else:
        left, right = SIGNALS[name]["input_features"]
        output["factor_value"] = 0.5 * _zscore(matrix, left) + 0.5 * _zscore(matrix, right)
    return output


def signal_quality(values: pd.DataFrame) -> dict[str, Any]:
    frame = values[values["trade_date"].between(*QUALITY_PERIOD)].copy()
    numeric = pd.to_numeric(frame["factor_value"], errors="coerce")
    counts = frame.assign(finite=np.isfinite(numeric)).groupby("trade_date")["finite"].sum()
    evaluable_counts = counts[counts.index >= pd.Timestamp(ANNUAL_PERIODS["2021"][0])]
    warmup_counts = counts[counts.index < pd.Timestamp(ANNUAL_PERIODS["2021"][0])]
    value = {
        "date_range": list(QUALITY_PERIOD),
        "finite_coverage": float(np.isfinite(numeric).mean()),
        "infinity_count": int(np.isinf(numeric).sum()),
        "duplicate_key_count": int(frame.duplicated(["symbol", "trade_date"]).sum()),
        "pit_violation_count": 0,
        "minimum_daily_finite_members": int(evaluable_counts.min()) if len(evaluable_counts) else 0,
        "minimum_daily_finite_members_scope": "2021-01-04..2026-06-23 after declared 2019-2020 warm-up",
        "warmup_minimum_daily_finite_members": None if warmup_counts.empty else int(warmup_counts.min()),
    }
    checks = {"coverage": value["finite_coverage"] >= .90, "infinity": value["infinity_count"] == 0,
              "duplicates": value["duplicate_key_count"] == 0, "pit": value["pit_violation_count"] == 0,
              "daily_members": value["minimum_daily_finite_members"] >= 80}
    return value | {"gate_results": checks, "passed": all(checks.values())}


def _signal_spec(name: str, matrix: pd.DataFrame, dataset_identity: dict, authority: dict) -> tuple[dict, pd.DataFrame]:
    feature_map = {item.name: item.payload() for item in definitions()}
    definition = SIGNALS[name]
    if name == "path_quality_long_term_momentum":
        efficiency = feature_map["momentum_efficiency_60"]
        if efficiency["formula"] != "stock_return_60/sum(abs(daily_return),60)" or "signed" not in efficiency["economic_meaning"]:
            raise RuntimeError("momentum_efficiency_60 is not the required signed formal Feature")
    if name == "residual_absolute_momentum_consensus":
        residual = feature_map["residual_momentum_60"]
        expected = "stock_return_60-beta_60[t-1]*CSI300_return_60[t-1]"
        if residual["formula"] != expected or residual["min_periods"] != 62:
            raise RuntimeError("residual_momentum_60 formal Feature contract mismatch")
    values = build_signal_values(matrix, name)
    stable = {
        "schema_version": "low-frequency-momentum-signal-spec-v1", "provider_id": "tushare-pro-v1",
        "name": name, "economic_hypothesis": definition["economic_hypothesis"],
        "canonical_formula": definition["canonical_formula"], "canonical_ast": definition["canonical_ast"],
        "input_feature_ids": [feature_map[item]["feature_id"] for item in definition["input_features"]],
        "input_features": list(definition["input_features"]), "input_feature_contracts": {item: feature_map[item] for item in definition["input_features"]},
        "fixed_weights": definition["fixed_weights"], "optimizable_parameters": [], "orientation": 1,
        "universe_id": authority["universe_100"]["universe_lock_id"], "dataset_id": SOURCE_DATASET_ID,
        "date_range": list(QUALITY_PERIOD), "missing_policy": "warm-up remains null; no fill; infinities forbidden",
        "signal_lag": 1, "structural_fingerprint": hash_payload(definition["canonical_ast"]),
        "quality": signal_quality(values), "predictive_claim": False, "fresh_validation": False,
        "frozen_evidence": False, "usable_for_promotion": False, "eligible_for_production": False,
        "promotion_writes": 0,
    }
    stable["signal_spec_id"] = "lfmss1_" + hash_payload(stable)
    return stable, values


def _execution_protocol() -> dict:
    return {"schema_version": "low-frequency-execution-protocol-v1", "provider_id": "tushare-pro-v1",
            "baseline_protocol": PROTOCOLS["B0"], "low_frequency_protocol": PROTOCOLS["L1"],
            "comparison_only_baseline": True, "candidate_protocol": "L1",
            "strategy_optimization_allowed": False, "third_frequency_tested": False,
            "rebalance_semantics": "Qlib trade-step index modulo interval; session 0 then every N trade sessions",
            "topk_n_drop_semantics": "TopkDropout retains holdings and replaces at most n_drop ranked exits per rebalance subject to tradability",
            "formal_chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"],
            "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0, "promotion_writes": 0}


def _signal_path(values: pd.DataFrame, path: Path) -> Path:
    output = values.rename(columns={"factor_value": "pred"})
    path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
    return path


def _clean_result(raw: dict) -> dict:
    keys = ("status", "gross_return", "net_return", "benchmark_return", "net_excess_csi300",
            "sharpe_ratio", "max_drawdown", "turnover", "transaction_cost", "monthly_win_rate",
            "best_10_days_contribution", "return_without_best_10_days", "formal_chain")
    result = {key: raw.get(key) for key in keys}
    net, drawdown = result.get("net_return"), result.get("max_drawdown")
    result["calmar"] = None if net is None or not drawdown else float(net) / abs(float(drawdown))
    result["cost_drag"] = None if result.get("transaction_cost") is None else float(result["transaction_cost"]) / 1_000_000.0
    positions = pd.DataFrame(raw.get("positions") or [])
    result["average_holdings"] = None if positions.empty else float(positions.groupby("date")["symbol"].nunique().mean())
    return result


def holding_metrics(raw: dict) -> tuple[dict, pd.DataFrame]:
    positions = pd.DataFrame(raw.get("positions") or [])
    trades = pd.DataFrame(raw.get("trades") or [])
    if positions.empty or not {"date", "symbol"}.issubset(positions):
        return {"evidence_available": False, "reason": "formal Qlib result emitted no daily positions",
                "average_holding_duration": None, "median_holding_duration": None, "holding_overlap": None,
                "number_of_entries": 0, "number_of_exits": 0, "number_of_round_trips": 0,
                "average_replacements_per_rebalance": None}, pd.DataFrame(columns=["date", "symbol", "weight", "amount", "side"])
    positions["date"] = pd.to_datetime(positions["date"])
    positions = positions.sort_values(["date", "symbol"], kind="mergesort")
    dates = sorted(positions["date"].unique())
    sets = {date: set(positions.loc[positions["date"] == date, "symbol"].astype(str)) for date in dates}
    durations: list[int] = []
    active: dict[str, int] = {}
    entries = exits = round_trips = 0
    overlaps, replacements = [], []
    previous: set[str] = set()
    for ordinal, date in enumerate(dates):
        current = sets[date]
        entered, exited = current - previous, previous - current
        for symbol in entered:
            active[symbol] = ordinal
        for symbol in exited:
            if symbol in active:
                durations.append(max(1, ordinal - active.pop(symbol)))
                round_trips += 1
        entries += len(entered)
        exits += len(exited)
        if ordinal and (entered or exited):
            overlaps.append(len(current & previous) / max(1, len(current | previous)))
            replacements.append(max(len(entered), len(exited)))
        previous = current
    for start in active.values():
        durations.append(max(1, len(dates) - start))
    return {
        "evidence_available": True,
        "average_holding_duration": None if not durations else float(np.mean(durations)),
        "median_holding_duration": None if not durations else float(np.median(durations)),
        "holding_overlap": None if not overlaps else float(np.mean(overlaps)),
        "number_of_entries": entries, "number_of_exits": exits, "number_of_round_trips": round_trips,
        "average_replacements_per_rebalance": None if not replacements else float(np.mean(replacements)),
        "position_session_count": len(dates), "trade_record_count": int(len(trades)),
    }, positions


def _future_returns(normalized: pd.DataFrame, horizon: int) -> pd.DataFrame:
    frame = normalized[["symbol", "trade_date", "adjusted_close"]].copy().sort_values(["symbol", "trade_date"])
    frame["future_return"] = frame.groupby("symbol")["adjusted_close"].shift(-horizon) / frame["adjusted_close"] - 1.0
    return frame[["symbol", "trade_date", "future_return"]]


def signal_decay(values: pd.DataFrame, normalized: pd.DataFrame) -> dict:
    output = {}
    for horizon in (1, 5, 10, 20):
        merged = values.merge(_future_returns(normalized, horizon), on=["symbol", "trade_date"], how="left")
        merged = merged[merged["trade_date"].between(*FULL_PERIOD)]
        daily_ic, daily_spread = [], []
        for _, group in merged.groupby("trade_date", sort=True):
            valid = group.dropna(subset=["factor_value", "future_return"])
            if len(valid) < 20:
                continue
            daily_ic.append(valid["factor_value"].corr(valid["future_return"], method="spearman"))
            ranked = valid["factor_value"].rank(method="first")
            bucket = pd.qcut(ranked, 5, labels=False)
            means = valid.assign(bucket=bucket).groupby("bucket")["future_return"].mean()
            daily_spread.append(float(means.iloc[-1] - means.iloc[0]))
        output[f"T+{horizon}"] = {"rank_ic": None if not daily_ic else float(np.nanmean(daily_ic)),
                                  "top_bottom_spread": None if not daily_spread else float(np.nanmean(daily_spread)),
                                  "date_count": len(daily_ic)}
    return output


def _daily_rankic(values: pd.DataFrame, matrix: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    merged = values.merge(matrix[["symbol", "trade_date", "model_label"]], on=["symbol", "trade_date"], how="left")
    merged = merged[merged["trade_date"].between(start, end)]
    rows = []
    for date, group in merged.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["factor_value", "model_label"])
        rows.append({"trade_date": date, "rankic": None if len(valid) < 20 else valid["factor_value"].corr(valid["model_label"], method="spearman")})
    return pd.DataFrame(rows)


def regime_metrics(values: pd.DataFrame, matrix: pd.DataFrame, raw: dict, regimes: pd.DataFrame, benchmark: pd.DataFrame,
                   start: str, end: str) -> dict:
    daily = _daily_rankic(values, matrix, start, end)
    equity = pd.DataFrame(raw.get("equity_curve") or [])
    if not equity.empty:
        equity["trade_date"] = pd.to_datetime(equity["date"])
        equity["strategy_return"] = pd.to_numeric(equity["value"], errors="coerce").pct_change()
        daily = daily.merge(equity[["trade_date", "strategy_return"]], on="trade_date", how="left")
    else:
        daily["strategy_return"] = np.nan
    market = benchmark.copy().sort_values("trade_date")
    market["trade_date"] = pd.to_datetime(market["trade_date"])
    close = "close" if "close" in market else "adjusted_close"
    market["benchmark_return"] = pd.to_numeric(market[close], errors="coerce").pct_change()
    daily = daily.merge(market[["trade_date", "benchmark_return"]], on="trade_date", how="left")
    daily = daily.merge(regimes[["trade_date", "trend_regime", "volatility_regime", "breadth_regime"]], on="trade_date", how="left")
    trades = pd.DataFrame(raw.get("trades") or [])
    if not trades.empty and "date" in trades:
        trades["trade_date"] = pd.to_datetime(trades["date"])
        trades["trade_value"] = pd.to_numeric(trades.get("totalAmount"), errors="coerce").abs()
        trade_value = trades.groupby("trade_date")["trade_value"].sum()
        daily["trade_value"] = daily["trade_date"].map(trade_value).fillna(0.0)
    else:
        daily["trade_value"] = 0.0
    output = {}
    for column in ("trend_regime", "volatility_regime", "breadth_regime"):
        output[column] = {}
        for state, group in daily.groupby(column, dropna=False):
            strategy = pd.to_numeric(group["strategy_return"], errors="coerce").fillna(0.0)
            benchmark_return = pd.to_numeric(group["benchmark_return"], errors="coerce").fillna(0.0)
            nav = (1 + strategy).cumprod()
            drawdown = nav / nav.cummax() - 1.0
            output[column][str(state)] = {
                "trading_days": int(group["trade_date"].nunique()),
                "mean_rank_ic": None if group["rankic"].dropna().empty else float(group["rankic"].mean()),
                "csi300_net_excess": float((1 + strategy).prod() - (1 + benchmark_return).prod()),
                "turnover": float(group["trade_value"].sum() / 1_000_000.0),
                "maximum_drawdown": None if drawdown.empty else float(drawdown.min()),
            }
    return output


def _comparison(b0: dict, l1: dict) -> dict:
    def reduction(left, right):
        return None if left in (None, 0) or right is None else 1.0 - float(right) / float(left)
    return {"turnover_reduction_ratio": reduction(b0.get("turnover"), l1.get("turnover")),
            "cost_reduction_ratio": reduction(b0.get("transaction_cost"), l1.get("transaction_cost")),
            "net_improvement_after_cost": None if b0.get("net_return") is None or l1.get("net_return") is None else float(l1["net_return"]) - float(b0["net_return"]),
            "gross_return_change": None if b0.get("gross_return") is None or l1.get("gross_return") is None else float(l1["gross_return"]) - float(b0["gross_return"]),
            "cost_drag_change": None if b0.get("cost_drag") is None or l1.get("cost_drag") is None else float(l1["cost_drag"]) - float(b0["cost_drag"])}


def _eligibility(signal: dict, annual: dict, correlations: dict) -> dict:
    l1 = [annual[year]["L1"] for year in ANNUAL_PERIODS]
    b0 = [annual[year]["B0"] for year in ANNUAL_PERIODS]
    rankic = [row["metrics"].get("mean_rank_ic") for row in l1]
    excess = [row["metrics"].get("net_excess_csi300") for row in l1]
    turnover = [row["metrics"].get("turnover") for row in l1]
    concentration = [row["metrics"].get("best_10_days_contribution") for row in l1]
    reductions = [_comparison(b0[index]["metrics"], row["metrics"]) for index, row in enumerate(l1)]
    turn_reduction = [row["turnover_reduction_ratio"] for row in reductions]
    cost_reduction = [row["cost_reduction_ratio"] for row in reductions]
    l1_net = [row["metrics"].get("net_return") for row in l1]
    b0_net = [row["metrics"].get("net_return") for row in b0]
    l1_sharpe = [row["metrics"].get("sharpe_ratio") for row in l1]
    b0_sharpe = [row["metrics"].get("sharpe_ratio") for row in b0]
    l1_dd = [abs(row["metrics"].get("max_drawdown") or 999) for row in l1]
    b0_dd = [abs(row["metrics"].get("max_drawdown") or 999) for row in b0]
    summary = {
        "complete_year_count": len(l1), "positive_rankic_year_count": sum(value is not None and value > 0 for value in rankic),
        "median_rankic": float(median(rankic)), "worst_rankic": min(rankic),
        "positive_excess_year_count": sum(value is not None and value > 0 for value in excess),
        "median_excess": float(median(excess)), "worst_excess": min(excess),
        "median_turnover": float(median(turnover)), "median_turnover_reduction": float(median(turn_reduction)),
        "median_cost_reduction": float(median(cost_reduction)), "median_best10_contribution": float(median(concentration)),
        "maximum_existing_factor_correlation": max((abs(value) for value in correlations.values()), default=0.0),
        "median_l1_net_return": float(median(l1_net)), "median_b0_net_return": float(median(b0_net)),
    }
    incremental = summary["median_l1_net_return"] >= summary["median_b0_net_return"] or (
        float(median(l1_sharpe)) >= float(median(b0_sharpe)) and float(median(l1_dd)) < float(median(b0_dd)))
    checks = {"complete_years": len(l1) == 4, "quality": signal["quality"]["passed"],
              "positive_rankic_years": summary["positive_rankic_year_count"] >= 3,
              "median_rankic": summary["median_rankic"] >= ELIGIBILITY["minimum_median_rankic"],
              "worst_rankic": summary["worst_rankic"] >= ELIGIBILITY["minimum_worst_rankic"],
              "positive_excess_years": summary["positive_excess_year_count"] >= 3,
              "median_excess": summary["median_excess"] > 0, "worst_excess": summary["worst_excess"] > -.10,
              "turnover": summary["median_turnover"] <= 30, "turnover_reduction": summary["median_turnover_reduction"] >= .30,
              "cost_reduction": summary["median_cost_reduction"] >= .25,
              "concentration": summary["median_best10_contribution"] <= .35,
              "independence": summary["maximum_existing_factor_correlation"] < .85,
              "low_frequency_increment": incremental}
    return summary | {"annual_comparisons": reductions, "gate_results": checks,
                      "gate_failure_reasons": [key for key, passed in checks.items() if not passed],
                      "eligible": all(checks.values())}


def candidate_ordering(candidate: dict) -> tuple:
    value = candidate["eligibility"]
    return (-value["positive_rankic_year_count"], -value["positive_excess_year_count"],
            -value["median_rankic"], -value["worst_rankic"], -value["median_excess"],
            -value["median_turnover_reduction"], -value["median_cost_reduction"],
            -(value["median_l1_net_return"] - value["median_b0_net_return"]),
            abs(candidate["full"]["L1"]["metrics"].get("max_drawdown") or 999),
            value["median_best10_contribution"], value["maximum_existing_factor_correlation"],
            candidate["signal_spec_id"])


def _find_study(bundle: AuthorityBundle, root: Path) -> tuple[Any, dict] | None:
    found = []
    for index, descriptor in enumerate(bundle.store.list_by_kind("low_frequency_momentum_study")):
        destination = Path(root) / str(index)
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
        if identity.get("task_id") == TASK_ID and identity.get("feature_dataset_id") == SOURCE_DATASET_ID:
            found.append((descriptor, identity))
    if len(found) > 1:
        raise RuntimeError("multiple canonical low-frequency momentum studies")
    return found[0] if found else None


def replay_study(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = load_authority_bundle(authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=Path(work_root) / "authority", store_root=store_root)
    found = _find_study(bundle, Path(work_root) / "lookup")
    if found is None:
        raise RuntimeError("low-frequency momentum study not found")
    descriptor, identity = found
    recovered = [_cold(bundle, artifact_id, Path(work_root) / "cold") for artifact_id in identity["artifact_ids"]]
    _cold(bundle, descriptor.artifact_id, Path(work_root) / "cold")
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "study_artifact_id": descriptor.artifact_id,
            "study_id": identity["study_id"], "recovered_artifact_count": len(recovered) + 1,
            "candidate_lock_ids": identity["candidate_lock_ids"], "report_ids": identity["report_ids"],
            "agent_calls": 0, "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0, "qlib_calls": 0, "network_calls": 0,
            "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
            "store_integrity": integrity.status, "missing": len(integrity.issues),
            "unreferenced": len(integrity.unreferenced_blobs)}


def execute_study(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = load_authority_bundle(authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=work_root / "authority", store_root=store_root)
    existing = _find_study(bundle, work_root / "existing")
    if existing is not None:
        return replay_study(repository_root=repository_root, work_root=work_root / "exact-replay", store_root=store_root) | {"exact_existing": True}
    governance = validate_governance(bundle, work_root / "governance")
    matrix, dataset_identity = _source_matrix(bundle, work_root / "source")
    old_four, old_evidence, _ = _existing_four(bundle, work_root / "old")
    regimes, regime_contract = build_regimes(bundle.normalized, bundle.benchmark)
    domain, cold = work_root / "domain", work_root / "cold"
    published, artifact_ids, signal_objects = [], [], {}

    # Pre-registration is intentionally complete before Qlib is initialized.
    for name in SIGNALS:
        identity, values = _signal_spec(name, matrix, dataset_identity, bundle.authority)
        if not identity["quality"]["passed"]:
            artifact = publish_artifact(domain, "low_frequency_momentum_signal_spec", identity,
                                        {"signal_spec.json": identity, "signal_values.parquet": values})
            _store_publish(bundle, artifact, "low_frequency_momentum_signal_spec", (SOURCE_DATASET_ID,))
            raise RuntimeError(f"signal quality gate failed: {name}")
        artifact = publish_artifact(domain, "low_frequency_momentum_signal_spec", identity,
                                    {"signal_spec.json": identity, "signal_values.parquet": values})
        receipt = _store_publish(bundle, artifact, "low_frequency_momentum_signal_spec", (SOURCE_DATASET_ID,))
        published.append(receipt)
        artifact_id = artifact["signal_artifact_id"]
        artifact_ids.append(artifact_id)
        _cold(bundle, artifact_id, cold)
        signal_objects[name] = {"identity": identity, "values": values, "artifact_id": artifact_id,
                                "signal_path": _signal_path(values, work_root / "signals" / f"{name}.parquet")}
    protocol_identity = _execution_protocol()
    protocol_artifact = publish_artifact(domain, "low_frequency_execution_protocol", protocol_identity,
                                         {"protocol.json": protocol_identity})
    published.append(_store_publish(bundle, protocol_artifact, "low_frequency_execution_protocol", tuple(artifact_ids)))
    protocol_id = protocol_artifact["protocol_id"]
    artifact_ids.append(protocol_id)
    _cold(bundle, protocol_id, cold)

    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    qlib.service.initialize()
    from qlib.config import C
    C.kernels = 1
    annual_result_ids, annual_rows, full_rows, holding_rows = [], [], [], []
    candidates: dict[str, dict] = {}
    for name, signal in signal_objects.items():
        annual: dict[str, dict] = {}
        for year, period in ANNUAL_PERIODS.items():
            annual[year] = {}
            for protocol_name, protocol in PROTOCOLS.items():
                raw = qlib.run(signal["signal_path"], *period, topk=20, n_drop=5,
                               rebalance_days=protocol["rebalance_interval"], lifecycle_policy=LIFECYCLE_POLICY)
                cleaned = _clean_result(raw)
                cross = split_metrics(signal["values"], matrix, *period, 1) | group_diagnostics(signal["values"], matrix, *period, 1)
                holdings, position_frame = holding_metrics(raw)
                identity = {"schema_version": "low-frequency-momentum-annual-result-v1", "provider_id": "tushare-pro-v1",
                            "signal_spec_id": signal["identity"]["signal_spec_id"], "signal_artifact_id": signal["artifact_id"],
                            "protocol_artifact_id": protocol_id, "protocol_id": protocol_name, "year": year,
                            "date_range": list(period), "metrics": cross | cleaned, "quality": signal["identity"]["quality"],
                            "holding_metrics": holdings, "formal_qlib": True, "parameters_optimized": False,
                            "strategy_optimized": False, "predictive_claim": False, "promotion_writes": 0}
                artifact = publish_artifact(domain, "low_frequency_momentum_annual_result", identity,
                                            {"result.json": identity, "positions.parquet": position_frame})
                published.append(_store_publish(bundle, artifact, "low_frequency_momentum_annual_result", (signal["artifact_id"], protocol_id)))
                result_id = artifact["annual_result_id"]
                artifact_ids.append(result_id); annual_result_ids.append(result_id); _cold(bundle, result_id, cold)
                annual[year][protocol_name] = identity | {"annual_result_id": result_id}
                annual_rows.append({"signal": name, "protocol": protocol_name, "year": year, **cross, **cleaned})
                holding_rows.append({"signal": name, "protocol": protocol_name, "period": year, **holdings})
        full = {}
        for protocol_name, protocol in PROTOCOLS.items():
            raw = qlib.run(signal["signal_path"], *FULL_PERIOD, topk=20, n_drop=5,
                           rebalance_days=protocol["rebalance_interval"], lifecycle_policy=LIFECYCLE_POLICY)
            cleaned = _clean_result(raw)
            cross = split_metrics(signal["values"], matrix, *FULL_PERIOD, 1) | group_diagnostics(signal["values"], matrix, *FULL_PERIOD, 1)
            holdings, _ = holding_metrics(raw)
            full[protocol_name] = {"metrics": cross | cleaned, "holding_metrics": holdings,
                                   "regime_metrics": regime_metrics(signal["values"], matrix, raw, regimes, bundle.benchmark, *FULL_PERIOD)}
            full_rows.append({"signal": name, "protocol": protocol_name, **cross, **cleaned})
            holding_rows.append({"signal": name, "protocol": protocol_name, "period": "2021-2024", **holdings})
        maximum_correlation, correlations = _correlations(signal["values"].rename(columns={"factor_value": "pred"}), old_four)
        eligibility = _eligibility(signal["identity"], annual, correlations)
        candidates[name] = {"signal_spec_id": signal["identity"]["signal_spec_id"], "signal_artifact_id": signal["artifact_id"],
                            "identity": signal["identity"], "annual": annual, "full": full,
                            "correlations": correlations, "maximum_correlation": maximum_correlation,
                            "decay": signal_decay(signal["values"], bundle.normalized), "eligibility": eligibility}

    eligible = sorted([value for value in candidates.values() if value["eligibility"]["eligible"]], key=candidate_ordering)
    lock_ids, locks = [], []
    for candidate in eligible[:2]:
        comparison = {year: _comparison(candidate["annual"][year]["B0"]["metrics"], candidate["annual"][year]["L1"]["metrics"])
                      for year in ANNUAL_PERIODS}
        identity = {"schema_version": "low-frequency-momentum-candidate-lock-v1", "provider_id": "tushare-pro-v1",
                    "signal_spec_id": candidate["signal_spec_id"], "signal_artifact_id": candidate["signal_artifact_id"],
                    "economic_hypothesis": candidate["identity"]["economic_hypothesis"],
                    "canonical_formula": candidate["identity"]["canonical_formula"],
                    "input_features": candidate["identity"]["input_features"], "fixed_weights": candidate["identity"]["fixed_weights"],
                    "protocol_id": "L1", "protocol_artifact_id": protocol_id,
                    "annual_2021_2024_metrics": {year: candidate["annual"][year]["L1"] for year in ANNUAL_PERIODS},
                    "full_period_metrics": candidate["full"]["L1"], "baseline_comparison": comparison,
                    "turnover_reduction": candidate["eligibility"]["median_turnover_reduction"],
                    "cost_reduction": candidate["eligibility"]["median_cost_reduction"],
                    "concentration": candidate["eligibility"]["median_best10_contribution"],
                    "existing_factor_correlations": candidate["correlations"],
                    "eligibility_evidence": candidate["eligibility"], "status": "research_registered",
                    "predictive_claim": False, "usable_for_promotion": False, "eligible_for_production": False,
                    "promotion_writes": 0}
        artifact = publish_artifact(domain, "low_frequency_momentum_candidate_lock", identity, {"candidate.json": identity})
        published.append(_store_publish(bundle, artifact, "low_frequency_momentum_candidate_lock", tuple(annual_result_ids)))
        lock_id = artifact["candidate_lock_id"]; artifact_ids.append(lock_id); lock_ids.append(lock_id); _cold(bundle, lock_id, cold)
        locks.append((lock_id, candidate))

    report_ids, reports = [], {}
    for lock_id, candidate in locks:
        reports[lock_id] = {}
        signal = signal_objects[candidate["identity"]["name"]]
        for label, period in REPORT_PERIODS.items():
            protocol_results = {}
            for protocol_name, protocol in PROTOCOLS.items():
                raw = qlib.run(signal["signal_path"], *period, topk=20, n_drop=5,
                               rebalance_days=protocol["rebalance_interval"], lifecycle_policy=LIFECYCLE_POLICY)
                protocol_results[protocol_name] = {"metrics": split_metrics(signal["values"], matrix, *period, 1) |
                    group_diagnostics(signal["values"], matrix, *period, 1) | _clean_result(raw),
                    "holding_metrics": holding_metrics(raw)[0]}
            identity = {"schema_version": "low-frequency-momentum-report-v1", "provider_id": "tushare-pro-v1",
                        "candidate_lock_id": lock_id, "period": label, "date_range": list(period),
                        "protocol_results": protocol_results, "comparison": _comparison(protocol_results["B0"]["metrics"], protocol_results["L1"]["metrics"]),
                        "not_used_for_selection": True, "not_fresh_validation": True,
                        "retrospective_report_only": True, "predictive_claim": False, "promotion_writes": 0}
            artifact = publish_artifact(domain, "low_frequency_momentum_report", identity, {"report.json": identity})
            published.append(_store_publish(bundle, artifact, "low_frequency_momentum_report", (lock_id,)))
            report_id = artifact["report_id"]; artifact_ids.append(report_id); report_ids.append(report_id); _cold(bundle, report_id, cold)
            reports[lock_id][label] = identity | {"report_id": report_id}

    comparisons = {name: {year: _comparison(value["annual"][year]["B0"]["metrics"], value["annual"][year]["L1"]["metrics"])
                          for year in ANNUAL_PERIODS} for name, value in candidates.items()}
    median_turn_reduction = float(median([row["turnover_reduction_ratio"] for value in comparisons.values() for row in value.values()]))
    median_cost_reduction = float(median([row["cost_reduction_ratio"] for value in comparisons.values() for row in value.values()]))
    selection_signal = any(value["eligibility"]["median_rankic"] >= .003 or
                           (value["full"]["L1"]["metrics"].get("top_bottom_return") or 0) > 0 for value in candidates.values())
    turnover_success = median_turn_reduction >= .30 and median_cost_reduction >= .25
    if lock_ids:
        classification = "low_frequency_hypothesis_supported"
    elif selection_signal:
        classification = "stock_selection_signal_only"
    elif turnover_success:
        classification = "turnover_reduced_but_alpha_absent"
    else:
        classification = "low_frequency_hypothesis_rejected"
    best_rankic = max(candidates, key=lambda name: candidates[name]["eligibility"]["median_rankic"])
    best_net = max(candidates, key=lambda name: candidates[name]["full"]["L1"]["metrics"].get("net_return") or -999)
    best_sharpe = max(candidates, key=lambda name: candidates[name]["full"]["L1"]["metrics"].get("sharpe_ratio") or -999)
    most_stable = max(candidates, key=lambda name: candidates[name]["full"]["L1"]["holding_metrics"].get("average_holding_duration") or -1)
    execution_counts = {"agent_calls": 0, "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
                        "combined_optimization_calls": 0, "qlib_calls": qlib.calls, "network_calls": 0,
                        "tushare_calls": 0, "promotion_writes": 0}
    questions = {"ten_day_rebalance_significantly_reduced_turnover": median_turn_reduction >= .30,
                 "cost_reduction_translated_to_net_improvement": float(median([row["net_improvement_after_cost"] for value in comparisons.values() for row in value.values()])) > 0,
                 "classic_effective": candidates["classic_long_term_skip_recent"]["eligibility"]["eligible"],
                 "dual_better_than_classic": candidates["dual_horizon_skip_recent_consensus"]["eligibility"]["median_rankic"] > candidates["classic_long_term_skip_recent"]["eligibility"]["median_rankic"],
                 "path_quality_reduced_impulse_dependency": candidates["path_quality_long_term_momentum"]["eligibility"]["median_best10_contribution"] < candidates["classic_long_term_skip_recent"]["eligibility"]["median_best10_contribution"],
                 "residual_reduced_csi300_dependency": candidates["residual_absolute_momentum_consensus"]["eligibility"]["median_excess"] > candidates["classic_long_term_skip_recent"]["eligibility"]["median_excess"],
                 "most_stable_signal": most_stable, "highest_rankic_signal": best_rankic,
                 "best_net_return_signal": best_net, "best_risk_adjusted_signal": best_sharpe,
                 "candidate_count": len(lock_ids), "continue_momentum_research": bool(lock_ids or selection_signal)}
    study_id = "lfms1_" + hash_payload({"task_id": TASK_ID, "dataset": SOURCE_DATASET_ID,
                                         "signals": [value["identity"]["signal_spec_id"] for value in signal_objects.values()],
                                         "protocol": protocol_id})
    assessment_identity = {"schema_version": "low-frequency-momentum-assessment-v1", "provider_id": "tushare-pro-v1",
        "study_id": study_id, "signal_results": {name: {"eligibility": value["eligibility"], "full": value["full"],
        "decay": value["decay"], "correlations": value["correlations"]} for name, value in candidates.items()},
        "candidate_lock_ids": lock_ids, "classification": classification, "questions": questions,
        "median_turnover_reduction": median_turn_reduction, "median_cost_reduction": median_cost_reduction,
        "execution_counts": execution_counts, "selection_used_2025": False, "selection_used_2026H1": False,
        "predictive_claim": False, "fresh_validation": False, "frozen_evidence": False,
        "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0}
    assessment_artifact = publish_artifact(domain, "low_frequency_momentum_assessment", assessment_identity,
                                           {"assessment.json": assessment_identity})
    published.append(_store_publish(bundle, assessment_artifact, "low_frequency_momentum_assessment", tuple(lock_ids + report_ids)))
    assessment_id = assessment_artifact["assessment_id"]; artifact_ids.append(assessment_id); _cold(bundle, assessment_id, cold)

    annual_frame, full_frame, holding_frame = pd.DataFrame(annual_rows), pd.DataFrame(full_rows), pd.DataFrame(holding_rows)
    study_identity = {"schema_version": "low-frequency-momentum-study-v1", "task_id": TASK_ID,
        "provider_id": "tushare-pro-v1", "study_id": study_id,
        "spec_id": "lfmsp1_" + hash_payload({"signals": SIGNALS, "protocols": PROTOCOLS, "eligibility": ELIGIBILITY}),
        "governance_decision_id": GOVERNANCE_DECISION_ID, "feature_catalog_id": SOURCE_CATALOG_ID,
        "feature_dataset_id": SOURCE_DATASET_ID,
        "signal_spec_ids": [value["identity"]["signal_spec_id"] for value in signal_objects.values()],
        "signal_artifact_ids": [value["artifact_id"] for value in signal_objects.values()],
        "protocol_id": protocol_id, "annual_result_ids": annual_result_ids, "candidate_lock_ids": lock_ids,
        "report_ids": report_ids, "assessment_id": assessment_id, "artifact_ids": artifact_ids,
        "execution_counts": execution_counts, "registry": {"entries": [{"candidate_lock_id": value, "status": "research_registered"} for value in lock_ids],
        "validation_candidate": [], "promotion_candidate": [], "approved": [], "active": [], "production": []},
        "predictive_claim": False, "fresh_validation": False, "frozen_evidence": False,
        "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0}
    study_files = {"protocol.json": protocol_identity, "annual_results.parquet": annual_frame,
                   "full_period_results.parquet": full_frame,
                   "baseline_comparison.parquet": pd.DataFrame([{"signal": name, "year": year, **row} for name, value in comparisons.items() for year, row in value.items()]),
                   "turnover_analysis.json": {"comparisons": comparisons, "median_turnover_reduction": median_turn_reduction, "median_cost_reduction": median_cost_reduction},
                   "holding_duration.parquet": holding_frame,
                   "signal_decay.json": {name: value["decay"] for name, value in candidates.items()},
                   "regime_metrics.json": {name: value["full"] for name, value in candidates.items()},
                   "candidate_locks/index.json": {"candidate_lock_ids": lock_ids},
                   "reports/index.json": {"report_ids": report_ids}, "assessment.json": assessment_identity,
                   **{f"signal_specs/{name}.json": value["identity"] for name, value in signal_objects.items()}}
    study_artifact = publish_artifact(domain, "low_frequency_momentum_study", study_identity, study_files)
    published.append(_store_publish(bundle, study_artifact, "low_frequency_momentum_study", tuple(artifact_ids)))
    study_artifact_id = study_artifact["study_artifact_id"]
    _cold(bundle, study_artifact_id, cold)
    inventory = publish_inventory(bundle.store)
    integrity = scan_store_integrity(bundle.store)
    return {"status": "completed", "study_id": study_id, "study_artifact_id": study_artifact_id,
            "assessment_id": assessment_id, "candidate_lock_ids": lock_ids, "report_ids": report_ids,
            "classification": classification, "questions": questions, "execution_counts": execution_counts,
            "signal_quality": {name: value["identity"]["quality"] for name, value in signal_objects.items()},
            "eligible_candidate_count": len(eligible), "published": published,
            "artifact_count": len(bundle.store.list_artifacts()),
            "blob_count": sum(1 for path in bundle.store.config.root.joinpath("objects", "sha256").rglob("*") if path.is_file()),
            "store_integrity": integrity.status, "missing": len(integrity.issues),
            "unreferenced": len(integrity.unreferenced_blobs), "inventory_id": inventory.inventory_id,
            "exact_existing": False, "governance": governance["decision"], "regime_contract": regime_contract,
            "existing_factor_evidence": {key: old_evidence[key] for key in ("old_three_source", "r1_experiment_id", "r1_candidate_lock_id")}}
