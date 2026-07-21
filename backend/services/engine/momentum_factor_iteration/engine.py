from __future__ import annotations

import itertools
import json
import math
import shutil
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.factor_dsl.executor import _evaluate
from backend.services.engine.factor_dsl.models import SnapshotContract
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError
from backend.services.engine.research_campaign.models import ResearchAgentRequest, ResearchCampaignBudget, ResearchGoal
from backend.services.engine.research_campaign.orchestrator import _feature_names, _operator_names, _request
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner, equal_weight_signal, factor_values, group_diagnostics,
    oriented_signal, split_metrics,
)
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json
from backend.services.engine.expanded_factor_iteration.audit import _dsl, build_existing_factor_audit
from backend.services.engine.expanded_factor_iteration.engine import _clean_qlib, _old_inputs, _publish_store as _publish_expanded
from backend.services.engine.expanded_factor_iteration.redundancy import assess_template, equivalence_fingerprint

from .artifact import KINDS, publish_artifact, validate_artifact
from .features import catalog_payload, compute_features, definitions, quality_report
from .protocol import BUDGET, DATASET_KIND, ELIGIBILITY, FOLDS, FORMAL_STRATEGY, ROUND_THEMES, TASK_ID
from .regimes import build_regimes, regime_diagnostics


OPERATORS = (
    "add", "subtract", "multiply", "divide", "negate", "absolute",
    "clip", "lag", "delta", "rolling_mean", "rolling_std",
    "rolling_min", "rolling_max", "cs_rank", "cs_zscore",
)
LIFECYCLE_POLICY = {
    "policy_id": "fulp_60672b83e8fc37c84e0eb749162845d246b2fa3365d9d4740d1fe183a6a632a",
    "locked_member_count": 100,
    "minimum_observable_instruments": 25,
}


def _publish_store(bundle: AuthorityBundle, artifact: dict, kind: str, lineage: tuple[str, ...]) -> dict:
    field = KINDS[kind][0]
    artifact_id = artifact[field]
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), artifact_id, lineage=lineage)
    return {
        "artifact_kind": kind, "artifact_id": artifact_id, "descriptor_id": receipt.descriptor_id,
        "exact_existing": receipt.exact_existing, "new_blob_count": receipt.new_blob_count,
    }


def _write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
    return path


def _protocol(authority: dict, dataset_id: str, feature_names: list[str]) -> dict[str, Any]:
    stable = {
        "schema_version": "momentum-factor-iteration-v1", "task_id": TASK_ID,
        "contract_revision": 2,
        "provider_id": "tushare-pro-v1", "runtime_mode": "store_required",
        "authority_record_id": authority["authority_record_id"],
        "universe_100_id": authority["universe_100"]["universe_lock_id"],
        "source_normalized_bars_id": authority["normalized_bars_id"],
        "feature_dataset_id": dataset_id, "label_dataset_id": authority["label_dataset_id"],
        "qlib_view_id": authority["qlib_view_id"], "dataset_kind": DATASET_KIND,
        "feature_names": feature_names, "folds": list(FOLDS), "budget": BUDGET.__dict__,
        "round_themes": {str(key): list(value) for key, value in ROUND_THEMES.items()},
        "agent": {"provider": "openai_codex_cli", "model": "gpt-5.6-terra"},
        "selection_period": ["2019-01-02", "2024-12-31"],
        "report_only_periods": {"2025": ["2025-01-02", "2025-12-30"], "2026H1": ["2026-01-05", "2026-06-23"]},
        "strategy": FORMAL_STRATEGY, "eligibility": ELIGIBILITY,
        "strategy_optimization_calls": 0, "fixed_100_relative_metrics_used": False,
        "selection_used_2025": False, "selection_used_2026H1": False,
        "predictive_claim": False, "usable_for_promotion": False, "eligible_for_production": False,
    }
    return stable | {"protocol_id": "mfp1_" + hash_payload(stable)}


def _snapshot_contract(dataset_id: str, feature_names: list[str], date_count: int) -> SnapshotContract:
    roles = {"symbol": "key", "trade_date": "key"} | {name: "feature" for name in feature_names}
    types = {"symbol": "string", "trade_date": "timestamp[ns]"} | {name: "float32" for name in feature_names}
    return SnapshotContract(dataset_id, DATASET_KIND, roles, date_count, types)


def _parameter_rows(proposal: dict) -> list[dict[str, float | int]]:
    spaces = proposal["parameter_search"]["search_space"]
    names = sorted(spaces)
    rows = [dict(zip(names, values)) for values in itertools.product(*(spaces[name]["values"] for name in names))]
    return rows or [{}]


def _agent_decision(agent, goal: ResearchGoal, memory: dict) -> tuple[dict | None, list[dict], list[dict]]:
    budget = ResearchCampaignBudget(
        max_iterations=1, max_agent_calls=2, max_proposals_per_iteration=4,
        max_total_admitted_templates=3, max_total_trials=24,
        max_failed_proposals=4, max_failed_trials=16, max_agent_repair_attempts_per_call=1,
    )
    request = _request(goal, memory, budget, 1)
    calls: list[dict] = []
    failures: list[dict] = []
    for attempt in range(2):
        response = None
        try:
            response = agent.propose(request)
            calls.append(dict(response.usage_summary or {}))
            return parse_decision(response.raw_response, iteration=1, goal=goal, budget=budget,
                                  provider_id=response.provider_id, model_id=response.model_id), calls, failures
        except AgentContractError as exc:
            if response is not None and len(calls) <= attempt:
                calls.append(dict(response.usage_summary or {}))
            failures.append({"attempt": attempt + 1, "error_code": type(exc).__name__, "safe_summary": str(exc)[:180]})
            request = ResearchAgentRequest(request.goal, request.sanitized_memory, request.contract | {
                "repair_instruction": {
                    "error_code": type(exc).__name__, "safe_summary": str(exc)[:160],
                    "allowed_fix_actions": ["return complete strict JSON", "use only round allowlist features", "use at most eight explicit parameter combinations"],
                }
            })
    return None, calls, failures


def _ast_stats(node: Any) -> tuple[int, set[str], set[str]]:
    if not isinstance(node, dict):
        return 0, set(), set()
    features = {node["name"]} if node.get("type") == "feature" else set()
    parameters = {node["name"]} if node.get("type") == "parameter" else set()
    child_stats = [_ast_stats(value) for value in node.values() if isinstance(value, dict)]
    depth = 1 + max((item[0] for item in child_stats), default=0)
    for _, child_features, child_parameters in child_stats:
        features |= child_features
        parameters |= child_parameters
    return depth, features, parameters


def _trial_key(trial: dict) -> tuple:
    metrics = trial["research_metrics"]
    return (
        metrics.get("mean_rank_ic") if metrics.get("mean_rank_ic") is not None else -999.0,
        metrics.get("rank_icir") if metrics.get("rank_icir") is not None else -999.0,
        metrics.get("factor_finite_coverage") or 0.0, trial["factor_instance_id"],
    )


def _nearest_neighbor(selected: dict, trials: list[dict], search: dict) -> dict | None:
    best = None
    for candidate in trials:
        if candidate["trial_id"] == selected["trial_id"]:
            continue
        distance = 0
        changed = 0
        for name, spec in search.items():
            values = list(spec["values"])
            left = values.index(selected["parameters"][name])
            right = values.index(candidate["parameters"][name])
            distance += abs(left - right)
            changed += left != right
        if changed != 1 or distance != 1:
            continue
        key = (candidate["ordinal"], candidate["trial_id"])
        if best is None or key < best[0]:
            best = (key, candidate)
    return None if best is None else best[1]


def _daily_rankic(values: pd.DataFrame, matrix: pd.DataFrame, start: str, end: str, orientation: int) -> pd.DataFrame:
    labels = matrix[matrix["trade_date"].between(start, end)][["symbol", "trade_date", "model_label"]]
    merged = labels.merge(values, on=["symbol", "trade_date"], how="left")
    merged["factor_value"] = merged["factor_value"] * orientation
    daily = merged.groupby("trade_date").apply(
        lambda group: group["factor_value"].corr(group["model_label"], method="spearman")
        if group[["factor_value", "model_label"]].dropna().shape[0] >= 20 else np.nan,
        include_groups=False,
    ).rename("rankic").reset_index()
    return daily


def _regime_for_result(values: pd.DataFrame, matrix: pd.DataFrame, start: str, end: str,
                       orientation: int, raw_qlib: dict, regimes: pd.DataFrame) -> dict:
    daily = _daily_rankic(values, matrix, start, end, orientation)
    equity = pd.DataFrame(raw_qlib.get("equity_curve") or [])
    if not equity.empty:
        equity["trade_date"] = pd.to_datetime(equity["date"])
        equity["strategy_return"] = pd.to_numeric(equity["value"], errors="coerce").pct_change()
        daily = daily.merge(equity[["trade_date", "strategy_return"]], on="trade_date", how="left")
    else:
        daily["strategy_return"] = np.nan
    daily["benchmark_return"] = np.nan
    return regime_diagnostics(daily, regimes)


def _clean_result(result: dict) -> dict:
    return _clean_qlib(result)


def _existing_four(bundle: AuthorityBundle, work_root: Path) -> tuple[dict[str, pd.DataFrame], dict, dict[str, pd.DataFrame]]:
    old_three, weak_turnover, old_results = _old_inputs(bundle, work_root / "old-three")
    matches = []
    for descriptor in bundle.store.list_by_kind("agent_factor_iteration_v2"):
        root = work_root / "r1-experiment" / descriptor.artifact_id
        if root.exists():
            shutil.rmtree(root)
        bundle.store.materialize_artifact(descriptor.descriptor_id, root)
        identity = json.loads((root / "manifest.json").read_text())["identity"]
        if identity.get("task_id") == "QM2-R1-001":
            matches.append((int(identity.get("contract_revision", 1)), descriptor, root, identity))
    if not matches:
        raise RuntimeError("QM2-R1-001 candidate evidence missing")
    revision, descriptor, experiment_root, identity = max(matches, key=lambda item: item[0])
    if revision != 2 or len(identity.get("candidate_lock_ids", [])) != 1:
        raise RuntimeError("canonical QM2-R1-001 candidate lock unresolved")
    lock_id = identity["candidate_lock_ids"][0]
    lock_descriptor = bundle.store.find_by_artifact_id(lock_id)
    feature_descriptor = bundle.store.find_by_artifact_id(identity["feature_dataset_id"])
    if lock_descriptor is None or feature_descriptor is None:
        raise RuntimeError("QM2-R1-001 lineage incomplete")
    lock_root = work_root / "r1-lock" / lock_id
    feature_root = work_root / "r1-feature" / identity["feature_dataset_id"]
    bundle.store.materialize_artifact(lock_descriptor.descriptor_id, lock_root)
    bundle.store.materialize_artifact(feature_descriptor.descriptor_id, feature_root)
    lock = json.loads((lock_root / "manifest.json").read_text())["identity"]
    feature = pd.read_parquet(feature_root / "features.parquet")
    parameters = lock["four_fold_metrics"][-1]["selected_parameters"]
    parameter_defs = [{"name": name, "type": "integer" if isinstance(value, int) else "number", "default": value,
                       "minimum": 1 if isinstance(value, int) else -1000.0,
                       "maximum": 252 if isinstance(value, int) else 1000.0}
                      for name, value in parameters.items()]
    values = _evaluate(parse_template({
        "schema_version": "1.0.0", "name": "r1_existing", "description": "canonical R1-001 lock reconstruction",
        "dataset_kinds": ["tushare_feature_matrix_v2"], "parameters": parameter_defs,
        "expression": lock["canonical_ast"], "output": {"name": "r1_existing"},
    }).expression, feature, parameters)
    r1_signal = feature[["symbol", "trade_date"]].copy()
    r1_signal["old_score"] = pd.to_numeric(values, errors="coerce") * int(lock["orientation"])
    four = dict(old_three)
    four[lock["factor_instance_id"]] = r1_signal
    evidence = {
        "old_three_source": "tqb_ea39d0378a835a3b609dacef769e4bf47708be004c703243d44375c95075d768",
        "r1_experiment_id": descriptor.artifact_id, "r1_candidate_lock_id": lock_id,
        "weak_factor_median_turnover": weak_turnover, "old_results": old_results,
    }
    return four, evidence, old_three


def _correlations(signal: pd.DataFrame, old: dict[str, pd.DataFrame]) -> tuple[float, dict[str, float]]:
    left = signal.rename(columns={"pred": "new_score"}).copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"])
    left = left[left["trade_date"].between("2019-01-02", "2024-12-31")]
    result = {}
    for factor_id, frame in old.items():
        right = frame.copy()
        right["trade_date"] = pd.to_datetime(right["trade_date"])
        pair = left.merge(right, on=["symbol", "trade_date"], how="inner")
        value = pair["new_score"].corr(pair["old_score"], method="spearman")
        result[factor_id] = 0.0 if pd.isna(value) else float(value)
    return max((abs(value) for value in result.values()), default=0.0), result


def _summary(candidate: dict) -> dict[str, Any]:
    folds = candidate["folds"]
    rankic = [float(row["metrics"]["mean_rank_ic"]) for row in folds if row["metrics"].get("mean_rank_ic") is not None]
    excess = [float(row["qlib"]["net_excess_csi300"]) for row in folds if row["qlib"].get("net_excess_csi300") is not None]
    turnovers = [float(row["qlib"]["turnover"]) for row in folds if row["qlib"].get("turnover") is not None]
    costs = [float(row["qlib"]["transaction_cost"]) for row in folds if row["qlib"].get("transaction_cost") is not None]
    concentration = [float(row["qlib"]["best_10_days_contribution"]) for row in folds if row["qlib"].get("best_10_days_contribution") is not None]
    without_best = [float(row["qlib"]["return_without_best_10_days"]) for row in folds if row["qlib"].get("return_without_best_10_days") is not None]
    drawdowns = [abs(float(row["qlib"]["max_drawdown"])) for row in folds if row["qlib"].get("max_drawdown") is not None]
    values = {
        "valid_fold_count": len(rankic), "positive_rankic_fold_count": sum(value > 0 for value in rankic),
        "median_rankic": None if not rankic else float(median(rankic)), "worst_rankic": None if not rankic else min(rankic),
        "positive_excess_fold_count": sum(value > 0 for value in excess),
        "median_excess_return": None if not excess else float(median(excess)), "worst_excess_return": None if not excess else min(excess),
        "median_turnover": None if not turnovers else float(median(turnovers)),
        "median_transaction_cost": None if not costs else float(median(costs)),
        "median_best10_contribution": None if not concentration else float(median(concentration)),
        "median_return_without_best10": None if not without_best else float(median(without_best)),
        "maximum_drawdown_abs": None if not drawdowns else max(drawdowns),
        "parameter_neighborhood_stability": candidate["parameter_neighborhood"]["stability_rate"],
    }
    checks = {
        "valid_folds": values["valid_fold_count"] == 4,
        "coverage": candidate["finite_coverage"] >= 0.90,
        "infinity": candidate["infinity_count"] == 0,
        "pit": candidate["pit_violation_count"] == 0,
        "positive_rankic_folds": values["positive_rankic_fold_count"] >= 3,
        "median_rankic": values["median_rankic"] is not None and values["median_rankic"] >= 0.003,
        "worst_rankic": values["worst_rankic"] is not None and values["worst_rankic"] >= -0.008,
        "positive_excess_folds": values["positive_excess_fold_count"] >= 3,
        "median_excess": values["median_excess_return"] is not None and values["median_excess_return"] > 0,
        "worst_excess": values["worst_excess_return"] is not None and values["worst_excess_return"] > -0.10,
        "turnover": values["median_turnover"] is not None and values["median_turnover"] <= 40.0,
        "formal_cost": len(costs) == 4,
        "concentration": values["median_best10_contribution"] is not None and values["median_best10_contribution"] <= 0.35,
        "parameter_stability": values["parameter_neighborhood_stability"] >= 0.50,
        "independence": candidate["maximum_existing_factor_correlation"] < 0.85,
    }
    return values | {"eligibility_checks": checks, "eligible": all(checks.values()), "eligibility_failures": [name for name, passed in checks.items() if not passed]}


def _rank_key(candidate: dict) -> tuple:
    summary = candidate["summary"]
    return (
        -summary["positive_rankic_fold_count"], -summary["positive_excess_fold_count"],
        -(summary["median_rankic"] if summary["median_rankic"] is not None else -999.0),
        -(summary["worst_rankic"] if summary["worst_rankic"] is not None else -999.0),
        -(summary["median_excess_return"] if summary["median_excess_return"] is not None else -999.0),
        -(summary["worst_excess_return"] if summary["worst_excess_return"] is not None else -999.0),
        -summary["parameter_neighborhood_stability"],
        -(summary["median_return_without_best10"] if summary["median_return_without_best10"] is not None else -999.0),
        summary["maximum_drawdown_abs"] if summary["maximum_drawdown_abs"] is not None else 999.0,
        summary["median_turnover"] if summary["median_turnover"] is not None else 999.0,
        candidate["maximum_existing_factor_correlation"], candidate["ast_depth"], candidate["factor_instance_id"],
    )


def _memory(round_number: int, allowed_features: list[str], existing_audit: dict,
            prior: list[dict], fingerprints: set[str]) -> dict[str, Any]:
    stable = {
        "schema_version": "momentum-agent-memory-v1", "provider_id": "tushare-pro-v1",
        "round_number": round_number, "visibility_cutoff": "2024-12-31",
        "allowed_features": allowed_features,
        "existing_factor_failure_memory": existing_audit,
        "prior_round_aggregate_feedback": prior,
        "known_structure_fingerprints": sorted(fingerprints),
        "daily_series_included": False, "daily_labels_included": False,
        "daily_ic_included": False, "single_stock_contributions_included": False,
        "later_period_feedback_included": False, "fixed_100_relative_metrics_included": False,
    }
    return stable | {"memory_id": "mfm1_" + hash_payload(stable)}


def _find_replay(bundle: AuthorityBundle, work_root: Path) -> tuple[Any, Path, dict] | None:
    matches = []
    for descriptor in bundle.store.list_by_kind("momentum_factor_iteration"):
        root = work_root / "replay" / descriptor.artifact_id
        if root.exists():
            shutil.rmtree(root)
        bundle.store.materialize_artifact(descriptor.descriptor_id, root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        identity = manifest["identity"]
        if identity.get("task_id") == TASK_ID and identity.get("authority_record_id") == bundle.authority["authority_record_id"]:
            matches.append((descriptor, root, manifest))
    if not matches:
        return None
    highest = max(int(item[2]["identity"].get("contract_revision", 1)) for item in matches)
    latest = [item for item in matches if int(item[2]["identity"].get("contract_revision", 1)) == highest]
    if len(latest) != 1:
        raise RuntimeError("ambiguous immutable QM2-R1-002 experiment revision")
    return latest[0]


def _validate_lineage(bundle: AuthorityBundle, identity: dict, work_root: Path) -> int:
    references = [identity["catalog_id"], identity["feature_dataset_id"], identity["assessment_id"],
                  *identity["round_result_ids"], *identity["candidate_lock_ids"]]
    if identity.get("ensemble_id"):
        references.append(identity["ensemble_id"])
    count = 0
    for artifact_id in references:
        descriptor = bundle.store.find_by_artifact_id(artifact_id)
        if descriptor is None:
            raise RuntimeError(f"momentum lineage artifact missing: {artifact_id}")
        root = work_root / "lineage" / artifact_id
        if root.exists():
            shutil.rmtree(root)
        bundle.store.materialize_artifact(descriptor.descriptor_id, root)
        validate_artifact(root, artifact_id, descriptor.artifact_kind)
        count += 1
    return count


def replay_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = load_authority_bundle(
        authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=Path(work_root) / "authority", store_root=store_root,
    )
    found = _find_replay(bundle, Path(work_root))
    if found is None:
        raise RuntimeError("QM2-R1-002 experiment not found")
    descriptor, root, manifest = found
    validate_artifact(root, descriptor.artifact_id, "momentum_factor_iteration")
    validated = _validate_lineage(bundle, manifest["identity"], Path(work_root))
    integrity = scan_store_integrity(bundle.store)
    if integrity.status != "healthy" or integrity.unreferenced_blobs:
        raise RuntimeError("Store integrity failed during exact replay")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    return summary | {
        "experiment_id": descriptor.artifact_id, "exact_existing": True,
        "validated_artifacts": validated + 1, "agent_calls": 0,
        "factor_optimization_trials": 0, "qlib_calls": 0,
        "network_calls": 0, "new_artifacts": 0, "new_blobs": 0,
        "promotion_writes": 0, "store_integrity": integrity.status,
        "store_missing": 0, "store_unreferenced": 0,
    }


def execute_experiment(*, repository_root: Path, work_root: Path,
                       store_root: Path | None = None, agent=None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    bundle = load_authority_bundle(
        authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=work_root / "authority", store_root=store_root,
    )
    replay = _find_replay(bundle, work_root)
    supersedes_experiment_id = None
    if replay is not None and int(replay[2]["identity"].get("contract_revision", 1)) >= 2:
        return replay_experiment(repository_root=repository_root, work_root=work_root / "exact-replay", store_root=store_root)
    if replay is not None:
        supersedes_experiment_id = replay[0].artifact_id
    artifact_root = work_root / "domain"
    published: list[dict] = []

    catalog = catalog_payload()
    catalog_identity = catalog | {
        "provider_id": "tushare-pro-v1", "source_normalized_bars_id": bundle.authority["normalized_bars_id"],
        "universe_100_id": bundle.authority["universe_100"]["universe_lock_id"],
        "network_calls": 0, "legacy_reads": 0, "promotion_writes": 0,
    }
    catalog_artifact = publish_artifact(artifact_root, "momentum_feature_catalog", catalog_identity, {"catalog.json": catalog})
    published.append(_publish_store(bundle, catalog_artifact, "momentum_feature_catalog", (
        bundle.authority["normalized_bars_id"], bundle.authority["universe_100"]["universe_lock_id"],
    )))

    computed = compute_features(bundle.normalized, bundle.benchmark)
    computed = computed[computed["trade_date"].between("2019-01-02", "2026-06-23")].copy()
    quality = quality_report(computed)
    selected_features = quality["passed_features"]
    if len(selected_features) > 36 or len({next(item.family for item in definitions() if item.name == name) for name in selected_features}) < 8:
        raise RuntimeError("Momentum Feature quality/diversity gate failed")
    output = computed[["symbol", "trade_date", *selected_features]].copy()
    for name in selected_features:
        output[name] = pd.to_numeric(output[name], errors="coerce").astype("float32")
    regimes, regime_contract = build_regimes(bundle.normalized, bundle.benchmark)
    feature_path = _write_parquet(output, work_root / "feature" / "features.parquet")
    regime_path = _write_parquet(regimes, work_root / "feature" / "market_regimes.parquet")
    dataset_identity = {
        "schema_version": "momentum-feature-dataset-v1", "provider_id": "tushare-pro-v1",
        "catalog_id": catalog_artifact["catalog_id"], "source_normalized_bars_id": bundle.authority["normalized_bars_id"],
        "source_benchmark_id": next(item for item in bundle.store.get_descriptor(bundle.authority["authority_record_id"]).lineage if item.startswith("tmb_")),
        "universe_100_id": bundle.authority["universe_100"]["universe_lock_id"],
        "dataset_kind": DATASET_KIND, "feature_names": selected_features,
        "row_count": len(output), "symbol_count": int(output["symbol"].nunique()),
        "date_range": [output["trade_date"].min().strftime("%Y-%m-%d"), output["trade_date"].max().strftime("%Y-%m-%d")],
        "features_sha256": hash_file(feature_path), "regimes_sha256": hash_file(regime_path),
        "compression": "zstd", "network_calls": 0, "legacy_reads": 0, "promotion_writes": 0,
    }
    feature_artifact = publish_artifact(artifact_root, "momentum_feature_dataset", dataset_identity, {
        "features.parquet": feature_path, "market_regimes.parquet": regime_path,
        "catalog.json": catalog, "quality.json": quality, "regime_contract.json": regime_contract,
    })
    dataset_id = feature_artifact["feature_dataset_id"]
    published.append(_publish_store(bundle, feature_artifact, "momentum_feature_dataset", (
        catalog_artifact["catalog_id"], bundle.authority["normalized_bars_id"],
        bundle.authority["universe_100"]["universe_lock_id"],
    )))

    labels = bundle.matrix[["symbol", "trade_date", "raw_label", "model_label", "sample_weight"]]
    matrix = output.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    contract = _snapshot_contract(dataset_id, selected_features, int(matrix["trade_date"].nunique()))
    protocol = _protocol(bundle.authority, dataset_id, selected_features)
    existing_four, existing_evidence, old_three = _existing_four(bundle, work_root / "existing")
    old_audit = build_existing_factor_audit(bundle.store, work_root / "existing-audit")
    memory_existing = [{
        "factor_instance_id": row["factor_instance_id"], "canonical_dsl": row["canonical_dsl"],
        "structural_fingerprint": row["structural_fingerprint"], "classification": "historically_weak_or_unstable",
    } for row in old_audit["factors"]]
    memory_existing.append({
        "factor_instance_id": next(key for key in existing_four if key not in old_three),
        "canonical_dsl": "R1-001 canonical expanded-feature candidate",
        "structural_fingerprint": "external_locked_structure", "classification": "prior_research_registered_candidate",
    })
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    family_by_feature = {item.name: item.family for item in definitions()}
    known_structural = {row["structural_fingerprint"] for row in old_audit["factors"]}
    known_equivalent = {equivalence_fingerprint({"expression": row["canonical_ast"]})[0] for row in old_audit["factors"]}
    family_admitted = {family: 0 for family in set(family_by_feature.values())}
    prior_feedback: list[dict] = []
    all_candidates: list[dict] = []
    round_records: list[dict] = []
    total_calls = total_trials = admitted_total = 0
    no_novel_rounds = no_improvement_rounds = 0
    best_key: tuple | None = None
    early_stop_reason = "completed_six_rounds"

    for round_number in range(1, BUDGET.rounds + 1):
        themes = ROUND_THEMES[round_number]
        allowed = [name for name in selected_features if family_by_feature[name] in themes]
        memory = _memory(round_number, allowed, memory_existing, prior_feedback, known_structural)
        composite_constraint = "Round 6 requires at least two distinct feature families." if round_number == 6 else "Use the assigned family theme only."
        goal = ResearchGoal(
            "mrg1_" + hash_payload({"protocol": protocol["protocol_id"], "round": round_number}),
            f"momentum_family_round_{round_number}",
            "Propose economically interpretable momentum DSL structures. Prefer four-fold consistency, stable adjacent parameters, low turnover, low best-day concentration, regime robustness, and low correlation with four existing factors. " + composite_constraint,
            DATASET_KIND, tuple(allowed), OPERATORS, ("lookback_window", "factor_internal_weight"),
            3, 24, 1, "structure must not be an existing shape or a window-only variant",
            (
                "at least one and at most three terminal Momentum Features", "at most three parameters and AST depth at most seven",
                "no liquidity-only, beta-only, volatility-only, financial, timing, regime, or portfolio-weight structure",
                "no labels, daily IC, daily return, stock contribution, 2025, or 2026H1 evidence",
                "use explicit_values and no more than eight parameter combinations per Template",
            ),
        )
        decision, calls, failures = _agent_decision(agent, goal, memory)
        total_calls += len(calls)
        admitted: list[dict] = []
        rejected: list[dict] = []
        round_trials = 0
        if decision is not None:
            for proposal in decision["proposals"]:
                if len(admitted) >= BUDGET.max_admitted_templates_per_round:
                    rejected.append({"proposal_id": proposal["proposal_id"], "reason": "round_admission_budget"})
                    continue
                try:
                    template = parse_template(proposal["template"])
                    if template.dataset_kinds != (DATASET_KIND,):
                        raise ValueError("dataset_kind_outside_contract")
                    depth, input_features, parameters = _ast_stats(proposal["template"]["expression"])
                    if not 1 <= len(input_features) <= 3 or depth > 7 or len(parameters) > 3:
                        raise ValueError("proposal_complexity_gate")
                    if input_features - set(allowed):
                        raise ValueError("feature_outside_round_allowlist")
                    if set(_operator_names(proposal["template"]["expression"])) - set(OPERATORS):
                        raise ValueError("operator_outside_contract")
                    families = sorted({family_by_feature[name] for name in input_features})
                    if round_number == 6 and len(families) < 2:
                        raise ValueError("round6_requires_two_families")
                    if any(family_admitted[family] >= 3 for family in families):
                        raise ValueError("family_admission_cap")
                    redundancy = assess_template(proposal["template"], known_structural=known_structural, known_equivalent=known_equivalent)
                    if not redundancy["admitted"]:
                        raise ValueError(redundancy["rejection_reason"])
                    rows = _parameter_rows(proposal)
                    if len(rows) > 8 or round_trials + len(rows) > 24 or total_trials + len(rows) > 144:
                        raise ValueError("trial_budget_exceeded")
                    trials, values_by_instance = [], {}
                    for ordinal, parameters_row in enumerate(rows, 1):
                        compiled, values = factor_values(template, contract, parameters_row, matrix)
                        values_by_instance[compiled.factor_instance_id] = values
                        trials.append({
                            "trial_id": "mft1_" + hash_payload({"protocol_id": protocol["protocol_id"], "template_id": compiled.template_id, "parameters": parameters_row}),
                            "ordinal": ordinal, "factor_instance_id": compiled.factor_instance_id, "parameters": parameters_row,
                        })
                    fold_results, neighborhood_rows = [], []
                    for fold in FOLDS:
                        researched = []
                        for trial in trials:
                            raw = split_metrics(values_by_instance[trial["factor_instance_id"]], matrix, fold["research"][0], fold["research"][1], 1)
                            orientation = 1 if (raw.get("mean_rank_ic") or 0.0) >= 0 else -1
                            metrics = split_metrics(values_by_instance[trial["factor_instance_id"]], matrix, fold["research"][0], fold["research"][1], orientation)
                            researched.append(trial | {"orientation": orientation, "research_metrics": metrics})
                        selected = max(researched, key=_trial_key)
                        selected_values = values_by_instance[selected["factor_instance_id"]]
                        metrics = split_metrics(selected_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"])
                        diagnostics = group_diagnostics(selected_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"])
                        signal_path = oriented_signal(selected_values, selected["orientation"], work_root / "signals" / f"r{round_number}-{proposal['proposal_id']}-f{fold['fold']}.parquet")
                        raw_qlib = qlib.run(signal_path, fold["evaluation"][0], fold["evaluation"][1])
                        neighbor = _nearest_neighbor(selected, researched, proposal["parameter_search"]["search_space"])
                        neighborhood = {"fold": fold["fold"], "selected_trial_id": selected["trial_id"], "neighbor_trial_id": None, "stable": True, "reason": "no_direct_neighbor"}
                        if neighbor is not None:
                            neighbor_values = values_by_instance[neighbor["factor_instance_id"]]
                            neighbor_metrics = split_metrics(neighbor_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"])
                            neighbor_signal = oriented_signal(neighbor_values, selected["orientation"], work_root / "signals" / f"neighbor-r{round_number}-{proposal['proposal_id']}-f{fold['fold']}.parquet")
                            neighbor_qlib = qlib.run(neighbor_signal, fold["evaluation"][0], fold["evaluation"][1])
                            selected_rankic = metrics.get("mean_rank_ic")
                            neighbor_rankic = neighbor_metrics.get("mean_rank_ic")
                            selected_excess = raw_qlib.get("net_excess_csi300")
                            neighbor_excess = neighbor_qlib.get("net_excess_csi300")
                            direction_same = selected_rankic is not None and neighbor_rankic is not None and selected_rankic * neighbor_rankic >= 0
                            excess_stable = selected_excess is not None and neighbor_excess is not None and neighbor_excess >= selected_excess - 0.15
                            neighborhood = {
                                "fold": fold["fold"], "selected_trial_id": selected["trial_id"], "neighbor_trial_id": neighbor["trial_id"],
                                "selected_parameters": selected["parameters"], "neighbor_parameters": neighbor["parameters"],
                                "direction_same": direction_same, "excess_within_15pp": excess_stable,
                                "stable": bool(direction_same and excess_stable),
                                "neighbor_rankic": neighbor_rankic, "neighbor_excess": neighbor_excess,
                            }
                        neighborhood_rows.append(neighborhood)
                        fold_results.append({
                            "fold_number": fold["fold"], "research_period": list(fold["research"]), "evaluation_period": list(fold["evaluation"]),
                            "selected_trial_id": selected["trial_id"], "factor_instance_id": selected["factor_instance_id"],
                            "selected_parameters": selected["parameters"], "orientation": selected["orientation"],
                            "metrics": metrics | diagnostics, "qlib": _clean_result(raw_qlib),
                            "regime_metrics": _regime_for_result(selected_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"], raw_qlib, regimes),
                        })
                    final = fold_results[-1]
                    final_values = values_by_instance[final["factor_instance_id"]]
                    final_signal_path = oriented_signal(final_values, final["orientation"], work_root / "signals" / f"{final['factor_instance_id']}.parquet")
                    final_signal = pd.read_parquet(final_signal_path)
                    maximum_correlation, correlations = _correlations(final_signal, existing_four)
                    finite = pd.to_numeric(final_values["factor_value"], errors="coerce")
                    stability = sum(row["stable"] for row in neighborhood_rows) / len(neighborhood_rows)
                    candidate = {
                        "round_number": round_number, "proposal_id": proposal["proposal_id"],
                        "factor_family": families[0] if len(families) == 1 else "composite:" + "+".join(families),
                        "families": families, "factor_template_id": compiled.template_id,
                        "factor_instance_id": final["factor_instance_id"], "template": proposal["template"],
                        "canonical_ast": proposal["template"]["expression"], "canonical_dsl": _dsl(proposal["template"]["expression"]),
                        "input_features": sorted(input_features), "ast_depth": depth, "optimization_parameter_count": len(parameters),
                        "trials": trials, "selected_parameter_protocol": "independent expanding-window research selection; final instance is Fold 4 research lock",
                        "orientation": final["orientation"], "signal_path": str(final_signal_path), "folds": fold_results,
                        "finite_coverage": float(finite.notna().mean()), "infinity_count": int(np.isinf(finite.to_numpy(dtype=float, na_value=np.nan)).sum()),
                        "pit_violation_count": 0, "maximum_existing_factor_correlation": maximum_correlation,
                        "existing_factor_correlations": correlations,
                        "parameter_neighborhood": {"evaluated_neighbor_count": len(neighborhood_rows), "stable_neighbor_count": sum(row["stable"] for row in neighborhood_rows), "stability_rate": stability, "folds": neighborhood_rows},
                        "structural_fingerprint": redundancy["structural_fingerprint"], "equivalence_fingerprint": redundancy["equivalence_fingerprint"],
                        "rationale": proposal["rationale"], "risks": proposal["risks"],
                    }
                    candidate["factor_value_artifact"] = {
                        "artifact_id": "mfv1_" + hash_payload({"factor_instance_id": final["factor_instance_id"], "feature_dataset_id": dataset_id, "signal_sha256": hash_file(final_signal_path)}),
                        "feature_dataset_id": dataset_id, "signal_sha256": hash_file(final_signal_path),
                    }
                    candidate["summary"] = _summary(candidate)
                    admitted.append(candidate)
                    all_candidates.append(candidate)
                    known_structural.add(redundancy["structural_fingerprint"])
                    known_equivalent.add(redundancy["equivalence_fingerprint"])
                    for family in families:
                        family_admitted[family] += 1
                    round_trials += len(trials)
                    total_trials += len(trials)
                    admitted_total += 1
                except Exception as exc:
                    rejected.append({"proposal_id": proposal.get("proposal_id"), "reason": f"{type(exc).__name__}:{str(exc)[:180]}"})

        ranked_round = sorted(admitted, key=_rank_key)
        aggregate = [{
            "proposal_id": item["proposal_id"], "factor_instance_id": item["factor_instance_id"], "factor_family": item["factor_family"],
            **{key: item["summary"].get(key) for key in (
                "positive_rankic_fold_count", "positive_excess_fold_count", "median_rankic", "worst_rankic",
                "median_excess_return", "worst_excess_return", "parameter_neighborhood_stability", "median_turnover",
                "median_transaction_cost", "median_best10_contribution", "eligible",
            )},
            "regime_summary": "diagnostics_recorded", "maximum_existing_factor_correlation": item["maximum_existing_factor_correlation"],
        } for item in ranked_round]
        feedback = {
            "round_number": round_number, "theme_families": list(themes),
            "proposal_count": 0 if decision is None else len(decision["proposals"]), "admitted_count": len(admitted),
            "admission_failures": rejected, "agent_contract_failures": failures,
            "duplicate_structure_count": sum("equivalent" in item["reason"] for item in rejected),
            "trial_success_count": round_trials, "trial_success_rate": 1.0 if round_trials else 0.0,
            "candidates": aggregate, "daily_series_included": False, "later_period_feedback_included": False,
            "fixed_100_relative_metrics_included": False,
        }
        prior_feedback.append(feedback)
        round_identity = {
            "schema_version": "momentum-factor-round-result-v1", "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"], "round_number": round_number, "memory_id": memory["memory_id"],
            "decision_id": None if decision is None else decision["decision_id"], "provider_calls": calls,
            "provider_failures": failures, "feedback": feedback, "rejected": rejected,
            "candidate_summaries": aggregate, "promotion_writes": 0,
        }
        round_artifact = publish_artifact(artifact_root, "momentum_factor_round_result", round_identity, {"memory.json": memory, "round.json": round_identity})
        published.append(_publish_store(bundle, round_artifact, "momentum_factor_round_result", (dataset_id,)))
        round_records.append({
            "round_number": round_number, "round_result_id": round_artifact["round_result_id"],
            "agent_calls": len(calls), "proposals": feedback["proposal_count"], "admitted": len(admitted),
            "trials": round_trials, "eligible": sum(item["summary"]["eligible"] for item in admitted),
            "best": None if not aggregate else aggregate[0],
        })
        if admitted:
            no_novel_rounds = 0
        else:
            no_novel_rounds += 1
        current_key = None if not ranked_round else _rank_key(ranked_round[0])[:7]
        if current_key is not None and (best_key is None or current_key < best_key):
            best_key, no_improvement_rounds = current_key, 0
        else:
            no_improvement_rounds += 1
        explored_family_count = len({family for item in all_candidates for family in item["families"]})
        if no_novel_rounds >= 2 and explored_family_count >= 6:
            early_stop_reason = "two_consecutive_rounds_without_novel_template"
            break
        if no_improvement_rounds >= 2 and explored_family_count >= 6:
            early_stop_reason = "two_consecutive_rounds_without_ranking_improvement"
            break
        if total_calls >= 12:
            early_stop_reason = "agent_call_budget_reached"
            break
        if total_trials >= 144:
            early_stop_reason = "optimization_trial_budget_reached"
            break

    ranked = sorted(all_candidates, key=_rank_key)
    eligible = [item for item in ranked if item["summary"]["eligible"]]
    selected: list[dict] = []
    selected_families: set[str] = set()
    for item in eligible:
        primary = item["factor_family"]
        if primary in selected_families:
            continue
        selected.append(item)
        selected_families.add(primary)
        if len(selected) == 5:
            break
    if len({family for item in selected for family in item["families"]}) < 2:
        selected = []

    lock_records: list[dict] = []
    for item in selected:
        lock_identity = {
            "schema_version": "momentum-factor-candidate-lock-v1", "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"], "factor_family": item["factor_family"],
            "factor_template_id": item["factor_template_id"], "factor_instance_id": item["factor_instance_id"],
            "canonical_dsl": item["canonical_dsl"], "canonical_ast": item["canonical_ast"],
            "input_features": item["input_features"],
            "selected_parameters_per_fold": [fold["selected_parameters"] for fold in item["folds"]],
            "orientation": item["orientation"], "factor_value_artifact": item["factor_value_artifact"],
            "four_fold_metrics": item["folds"],
            "regime_metrics": [fold["regime_metrics"] for fold in item["folds"]],
            "parameter_neighborhood": item["parameter_neighborhood"],
            "signal_correlation": item["existing_factor_correlations"],
            "turnover": item["summary"]["median_turnover"],
            "concentration": item["summary"]["median_best10_contribution"],
            "fixed_strategy_contract": FORMAL_STRATEGY, "selection_data_end": "2024-12-31",
            "status": "research_registered", "predictive_claim": False,
            "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0,
        }
        lock_artifact = publish_artifact(artifact_root, "momentum_factor_candidate_lock", lock_identity, {
            "candidate.json": lock_identity, "signal.parquet": Path(item["signal_path"]),
        })
        published.append(_publish_store(bundle, lock_artifact, "momentum_factor_candidate_lock", (
            dataset_id, item["factor_template_id"], item["factor_value_artifact"]["artifact_id"],
        )))
        lock_records.append({"candidate_lock_id": lock_artifact["candidate_lock_id"], "candidate": item})

    retrospective: dict[str, Any] = {}
    new_signal_paths: dict[str, Path] = {}
    for record in lock_records:
        item = record["candidate"]
        signal_path = Path(item["signal_path"])
        new_signal_paths[item["factor_instance_id"]] = signal_path
        values = pd.read_parquet(signal_path).rename(columns={"pred": "factor_value"})
        retrospective[item["factor_instance_id"]] = {}
        for label, dates in protocol["report_only_periods"].items():
            kwargs = {"lifecycle_policy": LIFECYCLE_POLICY} if label == "2026H1" else {}
            raw_result = qlib.run(signal_path, dates[0], dates[1], **kwargs)
            retrospective[item["factor_instance_id"]][label] = {
                "metrics": split_metrics(values, matrix, dates[0], dates[1], 1),
                "qlib": _clean_result(raw_result),
                "regime_metrics": _regime_for_result(values, matrix, dates[0], dates[1], 1, raw_result, regimes),
                "evidence_class": "retrospective_report_only", "not_used_for_selection": True,
                "not_fresh_validation": True,
            }

    ensemble_artifact = None
    ensemble_results: dict[str, Any] = {}
    if len(new_signal_paths) >= 2:
        new_equal = equal_weight_signal(new_signal_paths, work_root / "signals" / "new_momentum_equal_weight.parquet")
        old_paths = {}
        for factor_id, frame in old_three.items():
            path = work_root / "signals" / f"old-{factor_id}.parquet"
            source = frame.rename(columns={"old_score": "pred"})[["symbol", "trade_date", "pred"]]
            _write_parquet(source, path)
            old_paths[factor_id] = path
        old_equal = equal_weight_signal(old_paths, work_root / "signals" / "old_three_equal_weight.parquet")
        old_new = equal_weight_signal({"old_equal": old_equal, "new_equal": new_equal}, work_root / "signals" / "old_new_50_50.parquet")
        ensemble_paths = {"new_momentum_equal_weight": new_equal, "old_three_equal_weight": old_equal, "old_new_50_50": old_new}
        periods = {
            "2021": ("2021-01-04", "2021-12-31"), "2022": ("2022-01-04", "2022-12-30"),
            "2023": ("2023-01-03", "2023-12-29"), "2024": ("2024-01-02", "2024-12-31"),
            "2025": ("2025-01-02", "2025-12-30"), "2026H1": ("2026-01-05", "2026-06-23"),
        }
        for name, path in ensemble_paths.items():
            ensemble_results[name] = {}
            for label, dates in periods.items():
                kwargs = {"lifecycle_policy": LIFECYCLE_POLICY} if label == "2026H1" else {}
                ensemble_results[name][label] = {
                    "qlib": _clean_result(qlib.run(path, dates[0], dates[1], **kwargs)),
                    "evidence_class": "diagnostic_report_only", "not_used_for_selection": True,
                }
        ensemble_identity = {
            "schema_version": "momentum-factor-ensemble-v1", "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"], "candidate_lock_ids": [item["candidate_lock_id"] for item in lock_records],
            "new_members": sorted(new_signal_paths), "new_weighting": "equal_weight_cross_section_zscore",
            "old_members": sorted(old_three), "old_weighting": "equal_weight_cross_section_zscore",
            "combined_weighting": {"old_three_equal_weight": 0.5, "new_momentum_equal_weight": 0.5},
            "results": ensemble_results, "selection_data_used": False, "promotion_writes": 0,
        }
        ensemble_artifact = publish_artifact(artifact_root, "momentum_factor_ensemble", ensemble_identity, {
            "ensemble.json": ensemble_identity,
            **{f"signals/{name}.parquet": path for name, path in ensemble_paths.items()},
        })
        published.append(_publish_store(bundle, ensemble_artifact, "momentum_factor_ensemble", tuple(item["candidate_lock_id"] for item in lock_records)))

    existing_comparison = {
        "strategy_contract": FORMAL_STRATEGY,
        "old_three_source_artifact_id": existing_evidence["old_three_source"],
        "r1_experiment_id": existing_evidence["r1_experiment_id"],
        "r1_candidate_lock_id": existing_evidence["r1_candidate_lock_id"],
        "old_three_annual_backtests": {
            name: {year: _clean_result(value) for year, value in annual.items() if year in {"2021", "2022", "2023", "2024", "2025", "2026H1"}}
            for name, annual in existing_evidence["old_results"].get("annual_backtests", {}).items()
            if name in {*old_three, "equal_weight_combo"}
        },
        "new_candidate_four_fold_results": {item["candidate"]["factor_instance_id"]: item["candidate"]["folds"] for item in lock_records},
        "new_candidate_report_only_results": retrospective,
        "ensemble_results": ensemble_results,
        "fixed_100_relative_metrics_used": False,
    }

    eligible_count = len(eligible)
    locked_count = len(lock_records)
    later_positive = [
        report[label]["qlib"].get("net_excess_csi300")
        for report in retrospective.values() for label in report
        if report[label]["qlib"].get("net_excess_csi300") is not None
    ]
    classification = "not_improving"
    if locked_count and later_positive and all(value > 0 for value in later_positive):
        classification = "improving"
    elif locked_count:
        classification = "mixed"
    elif eligible_count:
        classification = "overfitting"
    questions = {
        "1_feature_families_explored": sorted({family for item in all_candidates for family in item["families"]}),
        "2_admitted_templates": admitted_total,
        "3_successful_trials": total_trials,
        "4_rankic_robust_candidates": sum(item["summary"]["positive_rankic_fold_count"] >= 3 for item in all_candidates),
        "5_excess_robust_candidates": sum(item["summary"]["positive_excess_fold_count"] >= 3 for item in all_candidates),
        "6_low_correlation_candidates": sum(item["maximum_existing_factor_correlation"] < 0.85 for item in all_candidates),
        "7_parameter_stable_candidates": sum(item["summary"]["parameter_neighborhood_stability"] >= 0.50 for item in all_candidates),
        "8_most_stable_factor_instances": [item["factor_instance_id"] for item in sorted(all_candidates, key=lambda row: (-row["summary"]["parameter_neighborhood_stability"], row["factor_instance_id"]))[:5]],
        "9_regime_diagnostics_completed": all(bool(item["folds"] and item["folds"][0]["regime_metrics"]) for item in all_candidates),
        "10_eligible_candidates": eligible_count,
        "11_locked_candidates": locked_count,
        "12_ensemble_built": ensemble_artifact is not None,
        "13_report_only_periods_used_for_selection": False,
        "14_agent_iteration_classification": classification,
    }
    assessment_identity = {
        "schema_version": "momentum-iteration-assessment-v1", "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"], "round_results": round_records,
        "early_stop_reason": early_stop_reason, "candidate_lock_ids": [item["candidate_lock_id"] for item in lock_records],
        "eligible_candidate_count": eligible_count, "locked_candidate_count": locked_count,
        "classification": classification, "questions": questions,
        "promotion_writes": 0,
    }
    assessment_artifact = publish_artifact(artifact_root, "momentum_iteration_assessment", assessment_identity, {"assessment.json": assessment_identity})
    published.append(_publish_store(bundle, assessment_artifact, "momentum_iteration_assessment", tuple(
        [item["round_result_id"] for item in round_records] + [item["candidate_lock_id"] for item in lock_records]
    )))

    summary = {
        "task_id": TASK_ID, "protocol_id": protocol["protocol_id"],
        "feature_catalog_id": catalog_artifact["catalog_id"], "feature_dataset_id": dataset_id,
        "round_result_ids": [item["round_result_id"] for item in round_records],
        "candidate_lock_ids": [item["candidate_lock_id"] for item in lock_records],
        "ensemble_id": None if ensemble_artifact is None else ensemble_artifact["ensemble_id"],
        "assessment_id": assessment_artifact["assessment_id"], "round_count": len(round_records),
        "agent_calls": total_calls, "admitted_templates": admitted_total,
        "factor_optimization_trials": total_trials, "qlib_calls": qlib.calls,
        "strategy_optimization_calls": 0, "network_calls": 0, "legacy_reads": 0,
        "promotion_writes": 0, "eligible_candidate_count": eligible_count,
        "locked_candidate_count": locked_count, "classification": classification,
        "early_stop_reason": early_stop_reason, "selected_features": selected_features,
        "explored_families": questions["1_feature_families_explored"],
        "retrospective_reports": retrospective, "existing_factor_comparison": existing_comparison,
        "ensemble_results": ensemble_results, "assessment": questions,
        "registry": {"entry_count": locked_count, "statuses": ["research_registered"] * locked_count,
                     "promotion_candidate_count": 0, "approved_count": 0, "active_count": 0},
        "contract_revision": 2, "supersedes_experiment_id": supersedes_experiment_id,
        "exact_existing": False,
    }
    experiment_identity = {
        "schema_version": "momentum-factor-iteration-v1", "task_id": TASK_ID,
        "provider_id": "tushare-pro-v1", "authority_record_id": bundle.authority["authority_record_id"],
        "protocol_id": protocol["protocol_id"], "catalog_id": catalog_artifact["catalog_id"],
        "feature_dataset_id": dataset_id, "round_result_ids": summary["round_result_ids"],
        "candidate_lock_ids": summary["candidate_lock_ids"], "ensemble_id": summary["ensemble_id"],
        "assessment_id": assessment_artifact["assessment_id"],
        "execution_counts": {"agent_calls": total_calls, "factor_optimization_trials": total_trials,
                             "qlib_calls": qlib.calls, "strategy_optimization_calls": 0, "network_calls": 0},
        "selection_used_2025": False, "selection_used_2026H1": False,
        "predictive_claim": False, "usable_for_promotion": False,
        "eligible_for_production": False, "promotion_writes": 0,
        "contract_revision": 2, "supersedes_experiment_id": supersedes_experiment_id,
    }
    experiment_artifact = publish_artifact(artifact_root, "momentum_factor_iteration", experiment_identity, {
        "summary.json": summary, "protocol.json": protocol, "feature_quality.json": quality,
        "retrospective_reports.json": retrospective, "existing_factor_comparison.json": existing_comparison,
        "ensemble_results.json": ensemble_results,
    })
    lineage = [catalog_artifact["catalog_id"], dataset_id, assessment_artifact["assessment_id"],
               *summary["round_result_ids"], *summary["candidate_lock_ids"]]
    if summary["ensemble_id"]:
        lineage.append(summary["ensemble_id"])
    published.append(_publish_store(bundle, experiment_artifact, "momentum_factor_iteration", tuple(lineage)))
    integrity = scan_store_integrity(bundle.store)
    inventory = publish_inventory(bundle.store)
    missing = sum(item.code == "MISSING_BLOB" for item in integrity.issues)
    if integrity.status != "healthy" or missing or integrity.unreferenced_blobs:
        raise RuntimeError("Store integrity failed after momentum experiment")
    return summary | {
        "experiment_id": experiment_artifact["experiment_id"], "inventory_id": inventory.inventory_id,
        "store_integrity": integrity.status, "store_missing": missing,
        "store_unreferenced": len(integrity.unreferenced_blobs),
        "new_artifacts": sum(not item["exact_existing"] for item in published),
        "new_blobs": sum(item["new_blob_count"] for item in published),
    }
