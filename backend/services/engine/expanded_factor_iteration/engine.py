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
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError
from backend.services.engine.research_campaign.models import ResearchAgentRequest, ResearchCampaignBudget, ResearchGoal
from backend.services.engine.research_campaign.orchestrator import _feature_names, _operator_names, _request
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner,
    equal_weight_signal,
    factor_values,
    group_diagnostics,
    oriented_signal,
    split_metrics,
)
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json

from .artifact import KINDS, publish_artifact, validate_artifact
from .audit import SIGNALS, _dsl, build_existing_factor_audit
from .features import compute_feature_candidates, feature_contract, quality_and_selection, snapshot_contract
from .protocol import BUDGET, FOLDS, OPERATORS, fixed_protocol
from .redundancy import assess_template, equivalence_fingerprint


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
        "artifact_kind": kind,
        "artifact_id": artifact_id,
        "descriptor_id": receipt.descriptor_id,
        "exact_existing": receipt.exact_existing,
        "new_blob_count": receipt.new_blob_count,
    }


def _write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
    return path


def _parameter_rows(proposal: dict) -> list[dict[str, float | int]]:
    search = proposal["parameter_search"]["search_space"]
    names = sorted(search)
    rows = [dict(zip(names, values)) for values in itertools.product(*(search[name]["values"] for name in names))]
    return rows or [{}]


def _agent_decision(agent, goal: ResearchGoal, memory: dict, round_number: int) -> tuple[dict | None, list[dict], list[dict]]:
    budget = ResearchCampaignBudget(
        max_iterations=1,
        max_agent_calls=2,
        max_proposals_per_iteration=3,
        max_total_admitted_templates=2,
        max_total_trials=16,
        max_failed_proposals=3,
        max_failed_trials=16,
        max_agent_repair_attempts_per_call=1,
    )
    request = _request(goal, memory, budget, 1)
    calls: list[dict] = []
    failures: list[dict] = []
    for attempt in range(2):
        response = None
        try:
            response = agent.propose(request)
            calls.append(dict(response.usage_summary or {}))
            return parse_decision(
                response.raw_response,
                iteration=1,
                goal=goal,
                budget=budget,
                provider_id=response.provider_id,
                model_id=response.model_id,
            ), calls, failures
        except AgentContractError as exc:
            if response is not None and len(calls) <= attempt:
                calls.append(dict(response.usage_summary or {}))
            failures.append({
                "attempt": attempt + 1,
                "error_code": type(exc).__name__,
                "safe_summary": str(exc)[:180],
            })
            request = ResearchAgentRequest(
                request.goal,
                request.sanitized_memory,
                request.contract | {
                    "repair_instruction": {
                        "error_code": type(exc).__name__,
                        "safe_summary": str(exc)[:160],
                        "allowed_fix_actions": [
                            "return a complete contract-valid replacement",
                            "use only allowed Feature and operator names",
                            "use explicit_values and at most eight trials per Template",
                        ],
                    }
                },
            )
    return None, calls, failures


def _old_inputs(bundle: AuthorityBundle, work_root: Path) -> tuple[dict[str, pd.DataFrame], float, dict]:
    descriptor = bundle.store.find_by_artifact_id("tqb_ea39d0378a835a3b609dacef769e4bf47708be004c703243d44375c95075d768")
    if descriptor is None or descriptor.artifact_kind != "tushare_qlib_backtest_result":
        raise RuntimeError("existing weak-factor formal evidence missing")
    root = work_root / "existing-formal-results"
    if root.exists():
        shutil.rmtree(root)
    bundle.store.materialize_artifact(descriptor.descriptor_id, root)
    results = json.loads((root / "results.json").read_text(encoding="utf-8"))
    signals = {
        factor_id: pd.read_parquet(root / "signals" / f"{factor_id}.parquet").rename(columns={"pred": "old_score"})
        for factor_id in (
            "fi_d8772fac40ca5e6c3842e8c9893de4b6f921f5fa63f87ca19cc132f116dc5c2c",
            "fi_e0fb2284915373745808c62d27104a1aafed6958b917e41edf8a46402d5c4664",
            "fi_8f557ea04929c391828ae892e029a166936e1082247283dada7a8ec3d83318b2",
        )
    }
    turnovers = []
    annual = results.get("annual_backtests", {})
    for factor_id in signals:
        for year in ("2021", "2022", "2023", "2024"):
            value = annual.get(factor_id, {}).get(year, {}).get("turnover")
            if value is not None and math.isfinite(float(value)):
                turnovers.append(float(value))
    if not turnovers:
        raise RuntimeError("existing weak-factor turnover baseline unresolved")
    return signals, float(median(turnovers)), results


def _memory(round_number: int, allowed_features: tuple[str, ...], audit: dict, prior: list[dict], fingerprints: set[str]) -> dict:
    old = [{
        "factor_instance_id": row["factor_instance_id"],
        "template_name": row["template_name"],
        "canonical_dsl": row["canonical_dsl"],
        "structural_fingerprint": row["structural_fingerprint"],
        "parameter_stability": "unstable",
        "2025_csi300_excess": "negative",
        "2026h1_csi300_excess": "negative",
        "promotion_status": "not_promoted",
        "strategy_parameter_optimization_did_not_restore_robustness": True,
    } for row in audit["factors"]]
    stable = {
        "schema_version": "expanded-feature-agent-memory-v2",
        "provider_id": "tushare-pro-v1",
        "round_number": round_number,
        "visibility_cutoff": "2024-12-31",
        "allowed_features": list(allowed_features),
        "existing_factor_failure_memory": old,
        "prior_round_aggregate_feedback": prior,
        "known_structure_fingerprints": sorted(fingerprints),
        "daily_series_included": False,
        "daily_labels_included": False,
        "daily_ic_included": False,
        "single_stock_contributions_included": False,
        "later_period_feedback_included": False,
        "fixed_100_relative_metrics_included": False,
    }
    return stable | {"memory_id": "afm2_" + hash_payload(stable)}


def _selection_key(trial: dict) -> tuple:
    metrics = trial["research_metrics"]
    return (
        metrics.get("mean_rank_ic") if metrics.get("mean_rank_ic") is not None else -999.0,
        metrics.get("rank_icir") if metrics.get("rank_icir") is not None else -999.0,
        metrics.get("factor_finite_coverage") or 0.0,
        trial["factor_instance_id"],
    )


def _clean_qlib(result: dict) -> dict:
    return {
        key: value for key, value in result.items()
        if key in {
            "status", "gross_return", "net_return", "benchmark_return", "net_excess_csi300",
            "sharpe_ratio", "max_drawdown", "turnover", "transaction_cost", "monthly_win_rate",
            "best_10_days_contribution", "return_without_best_10_days", "formal_chain",
        }
    }


def _old_correlation(signal: pd.DataFrame, old_signals: dict[str, pd.DataFrame]) -> tuple[float, dict[str, float]]:
    left = signal.rename(columns={"pred": "new_score"}).copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"])
    left = left[left["trade_date"].between("2019-01-02", "2024-12-31")]
    values = {}
    for factor_id, old in old_signals.items():
        right = old.copy()
        right["trade_date"] = pd.to_datetime(right["trade_date"])
        pair = left.merge(right, on=["symbol", "trade_date"], how="inner")
        correlation = pair["new_score"].corr(pair["old_score"], method="spearman")
        values[factor_id] = 0.0 if pd.isna(correlation) else float(correlation)
    return max((abs(value) for value in values.values()), default=0.0), values


def _candidate_summary(candidate: dict, weak_turnover: float) -> dict:
    folds = candidate["folds"]
    rank = [row["metrics"].get("mean_rank_ic") for row in folds]
    rank = [float(value) for value in rank if value is not None]
    excess = [row["qlib"].get("net_excess_csi300") for row in folds]
    excess = [float(value) for value in excess if value is not None]
    turnovers = [float(row["qlib"]["turnover"]) for row in folds if row["qlib"].get("turnover") is not None]
    costs = [float(row["qlib"]["transaction_cost"]) for row in folds if row["qlib"].get("transaction_cost") is not None]
    without_best = [float(row["qlib"]["return_without_best_10_days"]) for row in folds if row["qlib"].get("return_without_best_10_days") is not None]
    drawdowns = [abs(float(row["qlib"]["max_drawdown"])) for row in folds if row["qlib"].get("max_drawdown") is not None]
    positive_rank = sum(value > 0 for value in rank)
    positive_excess = sum(value > 0 for value in excess)
    median_rank = float(median(rank)) if rank else None
    worst_rank = min(rank) if rank else None
    median_excess = float(median(excess)) if excess else None
    worst_excess = min(excess) if excess else None
    turnover = float(median(turnovers)) if turnovers else None
    eligible = bool(
        len(rank) == 4
        and candidate["finite_coverage"] >= 0.90
        and candidate["infinity_count"] == 0
        and positive_rank >= 3
        and (median_rank or 0.0) > 0
        and (worst_rank if worst_rank is not None else -999.0) > -0.01
        and positive_excess >= 2
        and (median_excess or 0.0) > 0
        and turnover is not None
        and turnover < weak_turnover
        and all(value is not None for value in costs)
        and candidate["maximum_old_factor_correlation"] < 0.90
    )
    return {
        "valid_fold_count": len(rank),
        "positive_rankic_fold_count": positive_rank,
        "positive_excess_fold_count": positive_excess,
        "median_fold_rankic": median_rank,
        "worst_fold_rankic": worst_rank,
        "median_csi300_excess": median_excess,
        "worst_csi300_excess": worst_excess,
        "median_turnover": turnover,
        "median_transaction_cost": None if not costs else float(median(costs)),
        "median_return_without_best_10_days": None if not without_best else float(median(without_best)),
        "maximum_drawdown_abs": None if not drawdowns else max(drawdowns),
        "weak_factor_median_turnover": weak_turnover,
        "eligible": eligible,
        "eligibility_failures": [
            name for name, passed in (
                ("valid_folds", len(rank) == 4),
                ("finite_coverage", candidate["finite_coverage"] >= 0.90),
                ("positive_rankic_folds", positive_rank >= 3),
                ("median_rankic", (median_rank or 0.0) > 0),
                ("worst_rankic", (worst_rank if worst_rank is not None else -999.0) > -0.01),
                ("positive_csi300_excess_folds", positive_excess >= 2),
                ("median_csi300_excess", (median_excess or 0.0) > 0),
                ("turnover", turnover is not None and turnover < weak_turnover),
                ("signal_correlation", candidate["maximum_old_factor_correlation"] < 0.90),
            ) if not passed
        ],
    }


def _rank_key(candidate: dict) -> tuple:
    summary = candidate["summary"]
    return (
        -summary["positive_rankic_fold_count"],
        -summary["positive_excess_fold_count"],
        -(summary["median_fold_rankic"] if summary["median_fold_rankic"] is not None else -999.0),
        -(summary["worst_fold_rankic"] if summary["worst_fold_rankic"] is not None else -999.0),
        -(summary["median_csi300_excess"] if summary["median_csi300_excess"] is not None else -999.0),
        -(summary["worst_csi300_excess"] if summary["worst_csi300_excess"] is not None else -999.0),
        -(summary["median_return_without_best_10_days"] if summary["median_return_without_best_10_days"] is not None else -999.0),
        summary["maximum_drawdown_abs"] if summary["maximum_drawdown_abs"] is not None else 999.0,
        summary["median_turnover"] if summary["median_turnover"] is not None else 999.0,
        candidate["maximum_old_factor_correlation"],
        1 if candidate["redundancy_risk"] == "high" else 0,
        candidate["factor_instance_id"],
    )


def _find_replay(bundle: AuthorityBundle, work_root: Path) -> tuple[Any, Path, dict] | None:
    matches = []
    for descriptor in bundle.store.list_by_kind("agent_factor_iteration_v2"):
        root = work_root / "replay" / descriptor.artifact_id
        if root.exists():
            shutil.rmtree(root)
        bundle.store.materialize_artifact(descriptor.descriptor_id, root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        identity = manifest["identity"]
        if identity.get("task_id") == "QM2-R1-001" and identity.get("authority_record_id") == bundle.authority["authority_record_id"]:
            matches.append((descriptor, root, manifest))
    if not matches:
        return None
    highest_revision = max(int(item[2]["identity"].get("contract_revision", 1)) for item in matches)
    latest = [item for item in matches if int(item[2]["identity"].get("contract_revision", 1)) == highest_revision]
    if len(latest) > 1:
        raise RuntimeError("ambiguous immutable QM2-R1-001 experiment revision")
    return latest[0]


def _upgrade_contract_revision(bundle: AuthorityBundle, work_root: Path, replay: tuple[Any, Path, dict]) -> dict:
    descriptor, experiment_root, experiment_manifest = replay
    old_experiment_identity = experiment_manifest["identity"]
    artifact_root = work_root / "domain-contract-revision"
    published: list[dict] = []
    corrected_lock_ids: list[str] = []
    for old_lock_id in old_experiment_identity["candidate_lock_ids"]:
        old_descriptor = bundle.store.find_by_artifact_id(old_lock_id)
        if old_descriptor is None or old_descriptor.artifact_kind != "agent_factor_candidate_lock":
            raise RuntimeError("candidate lock missing during contract revision")
        source = work_root / "contract-revision-input" / old_lock_id
        if source.exists():
            shutil.rmtree(source)
        bundle.store.materialize_artifact(old_descriptor.descriptor_id, source)
        old_identity = json.loads((source / "manifest.json").read_text(encoding="utf-8"))["identity"]
        revised_identity = old_identity | {
            "canonical_dsl": _dsl(old_identity["canonical_ast"]),
            "contract_revision": 2,
            "supersedes_candidate_lock_id": old_lock_id,
        }
        artifact = publish_artifact(
            artifact_root, "agent_factor_candidate_lock", revised_identity,
            {"candidate.json": revised_identity},
        )
        published.append(_publish_store(bundle, artifact, "agent_factor_candidate_lock", (old_lock_id,)))
        corrected_lock_ids.append(artifact["candidate_lock_id"])

    old_assessment_id = old_experiment_identity["assessment_id"]
    old_assessment_descriptor = bundle.store.find_by_artifact_id(old_assessment_id)
    if old_assessment_descriptor is None:
        raise RuntimeError("assessment missing during contract revision")
    assessment_source = work_root / "contract-revision-input" / old_assessment_id
    bundle.store.materialize_artifact(old_assessment_descriptor.descriptor_id, assessment_source)
    old_assessment_identity = json.loads((assessment_source / "manifest.json").read_text(encoding="utf-8"))["identity"]
    revised_assessment_identity = old_assessment_identity | {
        "candidate_lock_ids": corrected_lock_ids,
        "contract_revision": 2,
        "supersedes_assessment_id": old_assessment_id,
    }
    assessment = publish_artifact(
        artifact_root, "agent_factor_iteration_assessment", revised_assessment_identity,
        {"assessment.json": revised_assessment_identity},
    )
    published.append(_publish_store(bundle, assessment, "agent_factor_iteration_assessment", (
        old_assessment_id, *corrected_lock_ids,
    )))

    summary = json.loads((experiment_root / "summary.json").read_text(encoding="utf-8")) | {
        "candidate_lock_ids": corrected_lock_ids,
        "assessment_id": assessment["assessment_id"],
        "contract_revision": 2,
        "supersedes_experiment_id": descriptor.artifact_id,
    }
    revised_experiment_identity = old_experiment_identity | {
        "candidate_lock_ids": corrected_lock_ids,
        "assessment_id": assessment["assessment_id"],
        "contract_revision": 2,
        "supersedes_experiment_id": descriptor.artifact_id,
    }
    experiment = publish_artifact(
        artifact_root, "agent_factor_iteration_v2", revised_experiment_identity,
        {
            "summary.json": summary,
            "protocol.json": experiment_root / "protocol.json",
            "retrospective_reports.json": experiment_root / "retrospective_reports.json",
            "existing_factor_comparison.json": experiment_root / "existing_factor_comparison.json",
        },
    )
    published.append(_publish_store(bundle, experiment, "agent_factor_iteration_v2", (
        descriptor.artifact_id, assessment["assessment_id"], *corrected_lock_ids,
    )))
    integrity = scan_store_integrity(bundle.store)
    if integrity.status != "healthy" or integrity.unreferenced_blobs:
        raise RuntimeError("Store integrity failed after contract revision")
    publish_inventory(bundle.store)
    return summary | {
        "experiment_id": experiment["experiment_id"],
        "exact_existing": False,
        "contract_revision_artifacts": len(published),
        "agent_calls": 0,
        "factor_optimization_calls": 0,
        "qlib_calls": 0,
        "network_calls": 0,
        "promotion_writes": 0,
    }


def replay_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict:
    bundle = load_authority_bundle(
        authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=Path(work_root) / "authority-replay",
        store_root=store_root,
    )
    found = _find_replay(bundle, Path(work_root))
    if found is None:
        raise RuntimeError("expanded feature Agent experiment not found")
    descriptor, root, manifest = found
    validate_artifact(root, descriptor.artifact_id, "agent_factor_iteration_v2")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    return summary | {
        "experiment_id": descriptor.artifact_id,
        "exact_existing": True,
        "agent_calls": 0,
        "factor_optimization_calls": 0,
        "qlib_calls": 0,
        "network_calls": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
        "promotion_writes": 0,
    }


def run_experiment(
    *,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
    agent=None,
) -> dict:
    repository_root = Path(repository_root)
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    bundle = load_authority_bundle(
        authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=work_root / "authority",
        store_root=store_root,
    )
    replay = _find_replay(bundle, work_root)
    if replay is not None:
        if int(replay[2]["identity"].get("contract_revision", 1)) < 2:
            return _upgrade_contract_revision(bundle, work_root, replay)
        return replay_experiment(repository_root=repository_root, work_root=work_root, store_root=store_root)

    artifact_root = work_root / "domain"
    published: list[dict] = []
    audit = build_existing_factor_audit(bundle.store, work_root / "audit")
    audit_artifact = publish_artifact(
        artifact_root,
        "existing_factor_definition_audit",
        {**audit, "promotion_writes": 0},
        {"audit.json": audit},
    )
    published.append(_publish_store(bundle, audit_artifact, "existing_factor_definition_audit", tuple(SIGNALS)))

    candidates = compute_feature_candidates(bundle.normalized, bundle.benchmark)
    quality, selected_features = quality_and_selection(candidates, 24)
    catalog = feature_contract(selected_features)
    catalog_artifact = publish_artifact(
        artifact_root,
        "tushare_feature_catalog_v2",
        catalog,
        {"catalog.json": catalog, "quality.json": quality},
    )
    published.append(_publish_store(bundle, catalog_artifact, "tushare_feature_catalog_v2", (
        bundle.authority["normalized_bars_id"], bundle.authority["universe_100"]["universe_lock_id"],
    )))

    output = candidates[candidates["trade_date"].between("2019-01-02", "2026-06-23")][["symbol", "trade_date", *selected_features]].copy()
    for name in selected_features:
        output[name] = pd.to_numeric(output[name], errors="coerce").astype("float32")
    feature_file = _write_parquet(output, work_root / "feature-v2" / "features.parquet")
    dataset_identity = {
        "schema_version": "tushare-feature-dataset-v2",
        "provider_id": "tushare-pro-v1",
        "catalog_id": catalog_artifact["catalog_id"],
        "source_normalized_bars_id": bundle.authority["normalized_bars_id"],
        "universe_100_id": bundle.authority["universe_100"]["universe_lock_id"],
        "feature_names": list(selected_features),
        "row_count": len(output),
        "symbol_count": int(output["symbol"].nunique()),
        "date_range": [output["trade_date"].min().strftime("%Y-%m-%d"), output["trade_date"].max().strftime("%Y-%m-%d")],
        "parquet_sha256": hash_file(feature_file),
        "compression": "zstd",
        "network_calls": 0,
        "legacy_reads": 0,
        "promotion_writes": 0,
    }
    feature_dataset_artifact = publish_artifact(
        artifact_root,
        "tushare_feature_dataset_v2",
        dataset_identity,
        {"features.parquet": feature_file, "catalog.json": catalog, "quality.json": quality},
    )
    published.append(_publish_store(bundle, feature_dataset_artifact, "tushare_feature_dataset_v2", (
        catalog_artifact["catalog_id"], bundle.authority["normalized_bars_id"], bundle.authority["universe_100"]["universe_lock_id"],
    )))
    dataset_id = feature_dataset_artifact["feature_dataset_id"]
    protocol = fixed_protocol(bundle.authority, dataset_id, selected_features)
    labels = bundle.matrix[["symbol", "trade_date", "raw_label", "model_label", "sample_weight"]]
    matrix = output.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    contract = snapshot_contract(dataset_id, selected_features, int(matrix["trade_date"].nunique()))
    old_signals, weak_turnover, old_results = _old_inputs(bundle, work_root)
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)

    known_structural = {row["structural_fingerprint"] for row in audit["factors"]}
    known_equivalent = {equivalence_fingerprint({"expression": row["canonical_ast"]})[0] for row in audit["factors"]}
    prior_feedback: list[dict] = []
    all_candidates: list[dict] = []
    round_records: list[dict] = []
    total_calls = total_trials = admitted_total = 0
    consecutive_no_novel = consecutive_no_improvement = 0
    best_first_six: tuple | None = None
    early_stop = "completed_six_rounds"

    for round_number in range(1, BUDGET["max_rounds"] + 1):
        memory = _memory(round_number, selected_features, audit, prior_feedback, known_structural)
        goal = ResearchGoal(
            "rg2_" + hash_payload({"protocol": protocol["protocol_id"], "round": round_number}),
            f"expanded_feature_round_{round_number}",
            "Do not maximize one-year return. Propose economically interpretable canonical DSL factors prioritizing consistent cross-year RankIC direction, lower turnover, less best-day concentration, low correlation with existing factors, and parameter-neighborhood stability.",
            "tushare_feature_matrix_v2",
            selected_features,
            OPERATORS,
            ("lookback_window", "factor_internal_weight"),
            2,
            16,
            1,
            "structure must differ from every supplied existing and prior-round fingerprint",
            (
                "no labels, daily IC, daily return or single-stock contribution",
                "no 2025 or 2026H1 evidence",
                "no strategy, universe, benchmark, cost, lag or portfolio weight authority",
                "use explicit_values and at most eight parameter combinations per Template",
            ),
        )
        decision, calls, failures = _agent_decision(agent, goal, memory, round_number)
        total_calls += len(calls)
        admitted: list[dict] = []
        rejected: list[dict] = []
        round_trials = 0
        if decision is not None:
            for proposal in decision["proposals"]:
                if len(admitted) >= 2:
                    rejected.append({"proposal_id": proposal["proposal_id"], "reason": "admission_budget"})
                    continue
                try:
                    template = parse_template(proposal["template"])
                    if template.dataset_kinds != ("tushare_feature_matrix_v2",):
                        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
                    if set(_feature_names(proposal["template"]["expression"])) - set(selected_features):
                        raise ValueError("feature_outside_catalog_v2")
                    if set(_operator_names(proposal["template"]["expression"])) - set(OPERATORS):
                        raise ValueError("operator_outside_contract")
                    redundancy = assess_template(
                        proposal["template"], known_structural=known_structural, known_equivalent=known_equivalent
                    )
                    if not redundancy["admitted"]:
                        raise ValueError(redundancy["rejection_reason"])
                    parameter_rows = _parameter_rows(proposal)
                    if len(parameter_rows) > 8 or round_trials + len(parameter_rows) > 16 or total_trials + len(parameter_rows) > 96:
                        raise ValueError("trial_budget_exceeded")
                    trials = []
                    values_by_instance: dict[str, pd.DataFrame] = {}
                    for ordinal, parameters in enumerate(parameter_rows, 1):
                        compiled, values = factor_values(template, contract, parameters, matrix)
                        values_by_instance[compiled.factor_instance_id] = values
                        trials.append({
                            "trial_id": "aft2_" + hash_payload({
                                "protocol_id": protocol["protocol_id"], "template_id": compiled.template_id,
                                "parameters": parameters,
                            }),
                            "ordinal": ordinal,
                            "factor_instance_id": compiled.factor_instance_id,
                            "parameters": parameters,
                        })
                    fold_results = []
                    for fold in FOLDS:
                        fold_trials = []
                        for trial in trials:
                            raw = split_metrics(
                                values_by_instance[trial["factor_instance_id"]], matrix,
                                fold.research_start, fold.research_end, 1,
                            )
                            orientation = 1 if (raw.get("mean_rank_ic") or 0.0) >= 0 else -1
                            oriented = split_metrics(
                                values_by_instance[trial["factor_instance_id"]], matrix,
                                fold.research_start, fold.research_end, orientation,
                            )
                            fold_trials.append(trial | {"orientation": orientation, "research_metrics": oriented})
                        selected = max(fold_trials, key=_selection_key)
                        values = values_by_instance[selected["factor_instance_id"]]
                        metrics = split_metrics(values, matrix, fold.evaluation_start, fold.evaluation_end, selected["orientation"])
                        diagnostics = group_diagnostics(values, matrix, fold.evaluation_start, fold.evaluation_end, selected["orientation"])
                        signal_path = oriented_signal(
                            values,
                            selected["orientation"],
                            work_root / "signals" / f"r{round_number}-{proposal['proposal_id']}-f{fold.number}.parquet",
                        )
                        qlib_result = qlib.run(signal_path, fold.evaluation_start, fold.evaluation_end)
                        fold_results.append({
                            "fold_number": fold.number,
                            "research_period": [fold.research_start, fold.research_end],
                            "evaluation_period": [fold.evaluation_start, fold.evaluation_end],
                            "evaluation_year": fold.evaluation_year,
                            "selected_trial_id": selected["trial_id"],
                            "factor_instance_id": selected["factor_instance_id"],
                            "selected_parameters": selected["parameters"],
                            "orientation": selected["orientation"],
                            "metrics": metrics | diagnostics,
                            "qlib": _clean_qlib(qlib_result),
                        })
                    final = fold_results[-1]
                    final_values = values_by_instance[final["factor_instance_id"]]
                    final_signal_path = oriented_signal(
                        final_values,
                        final["orientation"],
                        work_root / "signals" / f"{final['factor_instance_id']}.parquet",
                    )
                    final_signal = pd.read_parquet(final_signal_path)
                    max_correlation, correlations = _old_correlation(final_signal, old_signals)
                    finite = pd.to_numeric(final_values["factor_value"], errors="coerce")
                    input_features = sorted(set(_feature_names(proposal["template"]["expression"])))
                    catalog_corr = quality["correlation_matrix"]
                    maximum_feature_corr = max((
                        abs(catalog_corr[left][right])
                        for left, right in itertools.combinations(input_features, 2)
                        if catalog_corr[left][right] is not None
                    ), default=0.0)
                    candidate = {
                        "round_number": round_number,
                        "proposal_id": proposal["proposal_id"],
                        "factor_template_id": compiled.template_id,
                        "factor_instance_id": final["factor_instance_id"],
                        "template": proposal["template"],
                        "canonical_ast": proposal["template"]["expression"],
                        "input_features": input_features,
                        "trials": trials,
                        "selected_parameter_protocol": "independent expanding-window selection; final instance equals Fold 4 research lock",
                        "orientation": final["orientation"],
                        "factor_value_artifact_id": "afvv2_" + hash_payload({
                            "factor_instance_id": final["factor_instance_id"], "dataset_id": dataset_id,
                            "signal_sha256": hash_file(final_signal_path),
                        }),
                        "signal_path": str(final_signal_path),
                        "folds": fold_results,
                        "finite_coverage": float(finite.notna().mean()),
                        "infinity_count": int(np.isinf(finite).sum()),
                        "maximum_old_factor_correlation": max_correlation,
                        "old_factor_correlations": correlations,
                        "redundancy_risk": "high" if maximum_feature_corr > 0.95 or max_correlation >= 0.80 else "normal",
                        "maximum_input_feature_correlation": maximum_feature_corr,
                        "structural_fingerprint": redundancy["structural_fingerprint"],
                        "equivalence_fingerprint": redundancy["equivalence_fingerprint"],
                        "rationale": proposal["rationale"],
                        "risks": proposal["risks"],
                    }
                    candidate["summary"] = _candidate_summary(candidate, weak_turnover)
                    admitted.append(candidate)
                    all_candidates.append(candidate)
                    known_structural.add(redundancy["structural_fingerprint"])
                    known_equivalent.add(redundancy["equivalence_fingerprint"])
                    round_trials += len(trials)
                    total_trials += len(trials)
                    admitted_total += 1
                except Exception as exc:
                    rejected.append({
                        "proposal_id": proposal["proposal_id"],
                        "reason": f"{type(exc).__name__}:{str(exc)[:180]}",
                    })
        ranked_round = sorted(admitted, key=_rank_key)
        aggregate = [{
            "proposal_id": row["proposal_id"],
            "factor_instance_id": row["factor_instance_id"],
            "positive_rankic_fold_count": row["summary"]["positive_rankic_fold_count"],
            "positive_excess_fold_count": row["summary"]["positive_excess_fold_count"],
            "median_fold_rankic": row["summary"]["median_fold_rankic"],
            "worst_fold_rankic": row["summary"]["worst_fold_rankic"],
            "median_csi300_excess": row["summary"]["median_csi300_excess"],
            "worst_csi300_excess": row["summary"]["worst_csi300_excess"],
            "maximum_drawdown": row["summary"]["maximum_drawdown_abs"],
            "turnover": row["summary"]["median_turnover"],
            "transaction_cost": row["summary"]["median_transaction_cost"],
            "best_10_days_dependency": None if not row["folds"] else float(median([
                fold["qlib"].get("best_10_days_contribution") or 0.0 for fold in row["folds"]
            ])),
            "maximum_old_factor_correlation": row["maximum_old_factor_correlation"],
            "eligible": row["summary"]["eligible"],
        } for row in ranked_round]
        feedback = {
            "round_number": round_number,
            "proposal_count": 0 if decision is None else len(decision["proposals"]),
            "admitted_count": len(admitted),
            "rejected_contract_count": len(failures),
            "rejected_redundancy_count": sum("equivalent_or_existing" in row["reason"] for row in rejected),
            "trial_success_count": round_trials,
            "candidates": aggregate,
            "daily_series_included": False,
            "later_period_feedback_included": False,
            "fixed_100_relative_metrics_included": False,
        }
        prior_feedback.append(feedback)
        round_identity = {
            "schema_version": "agent-factor-round-result-v2",
            "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"],
            "round_number": round_number,
            "memory_id": memory["memory_id"],
            "decision_id": None if decision is None else decision["decision_id"],
            "provider_calls": calls,
            "provider_failures": failures,
            "feedback": feedback,
            "rejected": rejected,
            "candidate_summaries": aggregate,
            "promotion_writes": 0,
        }
        round_artifact = publish_artifact(
            artifact_root,
            "agent_factor_round_result",
            round_identity,
            {"memory.json": memory, "round.json": round_identity},
        )
        published.append(_publish_store(bundle, round_artifact, "agent_factor_round_result", (
            audit_artifact["audit_id"], dataset_id,
        )))
        round_records.append({
            "round_number": round_number,
            "round_result_id": round_artifact["round_result_id"],
            "agent_calls": len(calls),
            "proposals": feedback["proposal_count"],
            "admitted": len(admitted),
            "trials": round_trials,
            "eligible": sum(row["summary"]["eligible"] for row in admitted),
            "best": None if not ranked_round else aggregate[0],
        })
        if not admitted:
            consecutive_no_novel += 1
        else:
            consecutive_no_novel = 0
        current_first_six = None if not ranked_round else _rank_key(ranked_round[0])[:6]
        if current_first_six is None or (best_first_six is not None and current_first_six >= best_first_six):
            consecutive_no_improvement += 1
        else:
            consecutive_no_improvement = 0
            best_first_six = current_first_six
        if consecutive_no_novel >= 2:
            early_stop = "two_consecutive_rounds_without_novel_template"
            break
        if consecutive_no_improvement >= 2:
            early_stop = "two_consecutive_rounds_without_candidate_improvement"
            break
        if total_calls >= 12:
            early_stop = "agent_call_budget_reached"
            break
        if total_trials >= 96:
            early_stop = "trial_budget_reached"
            break

    ranked = sorted(all_candidates, key=_rank_key)
    selected = [row for row in ranked if row["summary"]["eligible"]][:3]
    lock_records = []
    for row in selected:
        lock_identity = {
            "schema_version": "agent-factor-candidate-lock-v2",
            "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"],
            "factor_template_id": row["factor_template_id"],
            "factor_instance_id": row["factor_instance_id"],
            "canonical_dsl": _dsl(row["canonical_ast"]),
            "canonical_ast": row["canonical_ast"],
            "input_features": row["input_features"],
            "selected_parameter_protocol": row["selected_parameter_protocol"],
            "orientation": row["orientation"],
            "factor_value_artifact_id": row["factor_value_artifact_id"],
            "four_fold_metrics": row["folds"],
            "signal_correlation": row["old_factor_correlations"],
            "redundancy_class": row["redundancy_risk"],
            "fixed_strategy_contract": protocol["strategy"],
            "selection_data_end": "2024-12-31",
            "status": "research_registered",
            "predictive_claim": False,
            "usable_for_promotion": False,
            "eligible_for_production": False,
            "promotion_writes": 0,
            "contract_revision": 2,
        }
        lock_artifact = publish_artifact(
            artifact_root,
            "agent_factor_candidate_lock",
            lock_identity,
            {"candidate.json": lock_identity},
        )
        published.append(_publish_store(bundle, lock_artifact, "agent_factor_candidate_lock", (
            dataset_id, row["factor_template_id"], row["factor_value_artifact_id"],
        )))
        lock_records.append({"candidate_lock_id": lock_artifact["candidate_lock_id"], "candidate": row})

    retrospective = {}
    new_signals: dict[str, Path] = {}
    for item in lock_records:
        row = item["candidate"]
        signal_path = Path(row["signal_path"])
        new_signals[row["factor_instance_id"]] = signal_path
        retrospective[row["factor_instance_id"]] = {}
        for label, dates in protocol["report_only_periods"].items():
            kwargs = {"lifecycle_policy": LIFECYCLE_POLICY} if label == "2026H1" else {}
            result = qlib.run(signal_path, dates[0], dates[1], **kwargs)
            values = pd.read_parquet(signal_path).rename(columns={"pred": "factor_value"})
            metrics = split_metrics(values, matrix, dates[0], dates[1], 1)
            retrospective[row["factor_instance_id"]][label] = {
                "metrics": metrics,
                "qlib": _clean_qlib(result),
                "evidence_class": "retrospective_report_only",
                "not_fresh_validation": True,
                "not_used_for_selection": True,
            }
    if len(new_signals) >= 2:
        new_signals["new_equal_weight"] = equal_weight_signal(new_signals, work_root / "signals" / "new_equal_weight.parquet")
        retrospective["new_equal_weight"] = {}
        for label, dates in protocol["report_only_periods"].items():
            kwargs = {"lifecycle_policy": LIFECYCLE_POLICY} if label == "2026H1" else {}
            retrospective["new_equal_weight"][label] = {
                "qlib": _clean_qlib(qlib.run(new_signals["new_equal_weight"], dates[0], dates[1], **kwargs)),
                "evidence_class": "retrospective_report_only",
                "not_fresh_validation": True,
                "not_used_for_selection": True,
            }

    existing_comparison = {
        "strategy_contract": protocol["strategy"],
        "source_artifact_id": "tqb_ea39d0378a835a3b609dacef769e4bf47708be004c703243d44375c95075d768",
        "annual_backtests": {
            name: {
                year: _clean_qlib(value)
                for year, value in annual.items()
                if year in {"2021", "2022", "2023", "2024", "2025", "2026H1"}
            }
            for name, annual in old_results.get("annual_backtests", {}).items()
            if name in {*old_signals, "equal_weight_combo"}
        },
        "fixed_100_metrics_used": False,
    }
    classifications = [row["summary"]["eligible"] for row in all_candidates]
    if selected and all(
        report[label]["qlib"].get("net_excess_csi300", -1) > 0
        for report in retrospective.values()
        for label in report
    ):
        classification = "improving"
    elif selected:
        classification = "mixed"
    elif any(classifications):
        classification = "overfitting"
    else:
        classification = "not_improving"
    assessment_identity = {
        "schema_version": "agent-factor-iteration-assessment-v2",
        "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"],
        "round_results": round_records,
        "early_stop_reason": early_stop,
        "candidate_lock_ids": [item["candidate_lock_id"] for item in lock_records],
        "eligible_candidate_count": len(selected),
        "classification": classification,
        "agent_rounds_continuously_improved": bool(
            len(round_records) > 1 and all(
                right["best"] is not None and left["best"] is not None
                and right["best"]["median_fold_rankic"] > left["best"]["median_fold_rankic"]
                for left, right in zip(round_records, round_records[1:])
            )
        ),
        "promotion_writes": 0,
        "contract_revision": 2,
    }
    assessment_artifact = publish_artifact(
        artifact_root,
        "agent_factor_iteration_assessment",
        assessment_identity,
        {"assessment.json": assessment_identity},
    )
    published.append(_publish_store(bundle, assessment_artifact, "agent_factor_iteration_assessment", tuple(
        [row["round_result_id"] for row in round_records] + [item["candidate_lock_id"] for item in lock_records]
    )))
    summary = {
        "task_id": "QM2-R1-001",
        "protocol_id": protocol["protocol_id"],
        "existing_factor_definition_audit_id": audit_artifact["audit_id"],
        "feature_catalog_id": catalog_artifact["catalog_id"],
        "feature_dataset_id": dataset_id,
        "round_result_ids": [row["round_result_id"] for row in round_records],
        "candidate_lock_ids": [item["candidate_lock_id"] for item in lock_records],
        "assessment_id": assessment_artifact["assessment_id"],
        "round_count": len(round_records),
        "agent_calls": total_calls,
        "admitted_templates": admitted_total,
        "factor_optimization_trials": total_trials,
        "qlib_calls": qlib.calls,
        "network_calls": 0,
        "promotion_writes": 0,
        "contract_revision": 2,
        "eligible_candidate_count": len(selected),
        "classification": classification,
        "early_stop_reason": early_stop,
        "selected_features": list(selected_features),
        "retrospective_reports": retrospective,
        "existing_factor_comparison": existing_comparison,
        "registry": {
            "entry_count": len(selected),
            "statuses": ["research_registered"] * len(selected),
            "promotion_candidate_count": 0,
            "approved_count": 0,
            "active_count": 0,
        },
        "exact_existing": False,
    }
    experiment_identity = {
        "schema_version": "agent-factor-iteration-v2",
        "task_id": "QM2-R1-001",
        "provider_id": "tushare-pro-v1",
        "authority_record_id": bundle.authority["authority_record_id"],
        "protocol_id": protocol["protocol_id"],
        "audit_id": audit_artifact["audit_id"],
        "catalog_id": catalog_artifact["catalog_id"],
        "feature_dataset_id": dataset_id,
        "round_result_ids": summary["round_result_ids"],
        "candidate_lock_ids": summary["candidate_lock_ids"],
        "assessment_id": assessment_artifact["assessment_id"],
        "execution_counts": {
            "agent_calls": total_calls,
            "factor_optimization_trials": total_trials,
            "qlib_calls": qlib.calls,
            "network_calls": 0,
        },
        "selection_used_2025": False,
        "selection_used_2026H1": False,
        "predictive_claim": False,
        "usable_for_promotion": False,
        "eligible_for_production": False,
        "promotion_writes": 0,
        "contract_revision": 2,
    }
    experiment_artifact = publish_artifact(
        artifact_root,
        "agent_factor_iteration_v2",
        experiment_identity,
        {
            "summary.json": summary,
            "protocol.json": protocol,
            "retrospective_reports.json": retrospective,
            "existing_factor_comparison.json": existing_comparison,
        },
    )
    published.append(_publish_store(bundle, experiment_artifact, "agent_factor_iteration_v2", tuple(
        [audit_artifact["audit_id"], catalog_artifact["catalog_id"], dataset_id, assessment_artifact["assessment_id"]]
        + summary["round_result_ids"] + summary["candidate_lock_ids"]
    )))
    integrity = scan_store_integrity(bundle.store)
    inventory = publish_inventory(bundle.store)
    missing_count = sum(item.code == "MISSING_BLOB" for item in integrity.issues)
    summary.update({
        "experiment_id": experiment_artifact["experiment_id"],
        "inventory_id": inventory.inventory_id,
        "store_integrity": integrity.status,
        "store_missing": missing_count,
        "store_unreferenced": len(integrity.unreferenced_blobs),
        "new_artifacts": sum(not row["exact_existing"] for row in published),
        "new_blobs": sum(row["new_blob_count"] for row in published),
    })
    # The immutable Experiment already contains the pre-inventory summary.  The
    # returned runtime summary adds Store inventory evidence without rewriting it.
    return summary
