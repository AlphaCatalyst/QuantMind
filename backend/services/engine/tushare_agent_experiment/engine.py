from __future__ import annotations

import itertools
import json
import math
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError
from backend.services.engine.research_campaign.models import (
    ResearchAgentRequest,
    ResearchCampaignBudget,
    ResearchGoal,
)
from backend.services.engine.research_campaign.novelty import structural_fingerprint
from backend.services.engine.research_campaign.orchestrator import _request
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .artifact import publish_experiment_artifact, validate_experiment_artifact
from .data import AuthorityBundle, load_authority_bundle
from .evaluation import (
    FormalQlibRunner,
    YEAR_WINDOWS,
    equal_weight_signal,
    factor_values,
    group_diagnostics,
    oriented_signal,
    snapshot_contract,
    split_metrics,
)
from .memory import build_memory, validate_memory
from .protocol import BUDGET, FEATURES, OPERATORS, ROUNDS, fixed_protocol


def _subset(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return frame[frame["trade_date"].between(start, end)]


def _safe_dataset_contract(value: Any, dataset_kind: str) -> Any:
    if isinstance(value, dict):
        return {
            key: ([dataset_kind] if key == "dataset_kinds" else _safe_dataset_contract(item, dataset_kind))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_dataset_contract(item, dataset_kind) for item in value]
    return value


def _agent_decision(agent, goal, memory) -> tuple[dict | None, list[dict], list[str]]:
    budget = ResearchCampaignBudget(
        max_iterations=1,
        max_agent_calls=2,
        max_proposals_per_iteration=3,
        max_total_admitted_templates=2,
        max_total_trials=12,
        max_failed_proposals=3,
        max_failed_trials=12,
        max_agent_repair_attempts_per_call=1,
    )
    request = _request(goal, memory, budget, 1)
    request = ResearchAgentRequest(
        request.goal,
        request.sanitized_memory,
        _safe_dataset_contract(request.contract, goal.dataset_kind),
    )
    calls: list[dict] = []
    failures: list[str] = []
    for attempt in range(BUDGET["max_agent_calls"]):
        response = None
        try:
            response = agent.propose(request)
            calls.append(response.usage_summary or {})
            decision = parse_decision(
                response.raw_response,
                iteration=1,
                goal=goal,
                budget=budget,
                provider_id=response.provider_id,
                model_id=response.model_id,
            )
            return decision, calls, failures
        except AgentContractError as exc:
            if response is not None:
                calls.append(response.usage_summary or {})
            failures.append(f"{type(exc).__name__}:{str(exc)[:180]}")
            request = ResearchAgentRequest(
                request.goal,
                request.sanitized_memory,
                request.contract
                | {
                    "repair_instruction": {
                        "error_code": type(exc).__name__,
                        "safe_summary": str(exc)[:160],
                        "allowed_fix_actions": [
                            "return contract-valid replacement JSON",
                            "correct dataset_kinds to tushare_feature_matrix_v1",
                            "reduce explicit search-space values",
                        ],
                    }
                },
            )
    return None, calls, failures


def _parameter_rows(proposal: dict) -> list[dict[str, float | int]]:
    search = proposal["parameter_search"]["search_space"]
    names = sorted(search)
    values = [search[name]["values"] for name in names]
    rows = [dict(zip(names, combination)) for combination in itertools.product(*values)]
    if not rows:
        rows = [{}]
    return rows


def _metric_key(row: dict) -> tuple:
    metrics = row["research_oriented_metrics"]
    return (
        metrics.get("mean_rank_ic") if metrics.get("mean_rank_ic") is not None else -999.0,
        metrics.get("rank_icir") if metrics.get("rank_icir") is not None else -999.0,
        metrics.get("factor_finite_coverage") or 0.0,
        row["trial_id"],
    )


def _feedback_band(value: float | None) -> str:
    value = value or 0.0
    if value >= 0.03:
        return "strong_positive"
    if value >= 0.005:
        return "weak_positive"
    if value > -0.005:
        return "neutral"
    if value > -0.03:
        return "weak_negative"
    return "strong_negative"


def _publish_to_store(bundle: AuthorityBundle, artifact: dict, kind: str, lineage: tuple[str, ...]) -> dict:
    identity = next(
        artifact[field]
        for field in (
            "experiment_id",
            "round_lock_id",
            "evaluation_id",
            "backtest_result_id",
            "holdout_result_id",
            "assessment_id",
            "historical_experiment_registry_id",
        )
        if isinstance(artifact.get(field), str)
    )
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), identity, lineage=lineage)
    return {
        "artifact_kind": kind,
        "artifact_id": identity,
        "descriptor_id": receipt.descriptor_id,
        "exact_existing": receipt.exact_existing,
        "new_blob_count": receipt.new_blob_count,
    }


def _annual_metrics(values: pd.DataFrame, matrix: pd.DataFrame, orientation: int, years: list[str]) -> dict:
    return {
        year: split_metrics(values, matrix, *YEAR_WINDOWS[year], orientation)
        | group_diagnostics(values, matrix, *YEAR_WINDOWS[year], orientation)
        for year in years
    }


def _select_final(candidates: list[dict], annual: dict, backtests: dict) -> dict:
    ranked = []
    for candidate in candidates:
        factor_id = candidate["factor_instance_id"]
        first = 2020 + candidate["origin_round"]
        years = [str(year) for year in range(first, 2025)]
        rank_values = [annual[factor_id][year]["mean_rank_ic"] for year in years]
        rank_values = [value for value in rank_values if value is not None]
        excess = [backtests[factor_id][year].get("net_excess_fixed_100") for year in years]
        excess = [value for value in excess if value is not None]
        positive_rank = sum(value > 0 for value in rank_values)
        mean_rank = float(np.mean(rank_values)) if rank_values else None
        positive_ratio = positive_rank / len(rank_values) if rank_values else 0.0
        positive_excess = sum(value > 0 for value in excess)
        concentration = max((abs(value) for value in excess), default=0.0) / max(
            sum(abs(value) for value in excess), 1e-12
        )
        eligible = (
            len(rank_values) >= 2
            and positive_rank >= 2
            and (mean_rank or 0.0) > 0
            and positive_ratio > 0.5
            and positive_excess >= 1
            and concentration < 0.8
        )
        ranked.append({
            "factor_instance_id": factor_id,
            "origin_round": candidate["origin_round"],
            "evaluation_years": years,
            "mean_rank_ic": mean_rank,
            "positive_rank_ic_years": positive_rank,
            "rank_ic_positive_year_ratio": positive_ratio,
            "positive_net_excess_years": positive_excess,
            "largest_absolute_excess_share": concentration,
            "eligible": eligible,
        })
    ranked.sort(
        key=lambda row: (
            row["eligible"],
            row["mean_rank_ic"] or -999.0,
            row["positive_rank_ic_years"],
            row["positive_net_excess_years"],
            row["factor_instance_id"],
        ),
        reverse=True,
    )
    selected = [row["factor_instance_id"] for row in ranked if row["eligible"]][:3]
    return {
        "selection_data_end": "2024-12-31",
        "holdout_metrics_used": False,
        "maximum_candidates": 3,
        "ranked_candidates": ranked,
        "selected_factor_instance_ids": selected,
    }


def _improvement(rounds: list[dict]) -> dict:
    successful = [row for row in rounds if row["evaluation_summary"].get("mean_rank_ic") is not None]
    rank = [row["evaluation_summary"]["mean_rank_ic"] for row in successful]
    excess = [row["evaluation_summary"].get("net_excess_fixed_100") for row in successful]
    rank_improves = len(rank) >= 2 and all(right > left for left, right in zip(rank, rank[1:]))
    excess_values = [value for value in excess if value is not None]
    excess_improves = len(excess_values) >= 2 and all(
        right > left for left, right in zip(excess_values, excess_values[1:])
    )
    if rank_improves and excess_improves:
        classification = "improving"
    elif rank and rank[-1] > 0 and any(value < 0 for value in rank[:-1]):
        classification = "mixed"
    elif rank and rank[-1] > max(rank[:-1] or [-math.inf]) and rank[-1] > 0 and not excess_improves:
        classification = "overfitting"
    else:
        classification = "not_improving"
    return {
        "classification": classification,
        "rounds_2_to_4_continuously_better_than_round_1": bool(
            len(rank) == 4 and all(value > rank[0] for value in rank[1:])
        ),
        "rank_ic_strictly_improving": rank_improves,
        "net_excess_strictly_improving": excess_improves,
        "round_metrics": rounds,
    }


def _matching_artifacts(bundle: AuthorityBundle, kind: str, protocol_id: str, root: Path) -> list[tuple[Any, Path, dict]]:
    matches = []
    for descriptor in bundle.store.list_by_kind(kind):
        target = root / kind / descriptor.artifact_id
        if target.exists():
            shutil.rmtree(target)
        bundle.store.materialize_artifact(descriptor.descriptor_id, target)
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if manifest["identity"].get("protocol_id") == protocol_id:
            matches.append((descriptor, target, manifest))
    return matches


def _recover_locked_rounds(
    *,
    bundle: AuthorityBundle,
    protocol: dict,
    work_root: Path,
    matrix: pd.DataFrame,
    contract: Any,
    signals_root: Path,
) -> dict | None:
    """Recover a complete pre-holdout checkpoint without reopening Agent access."""

    recovery_root = work_root / "round-recovery"
    locks = _matching_artifacts(
        bundle,
        "tushare_historical_round_lock",
        protocol["protocol_id"],
        recovery_root,
    )
    evaluations = _matching_artifacts(
        bundle,
        "tushare_historical_round_evaluation",
        protocol["protocol_id"],
        recovery_root,
    )
    if not locks and not evaluations:
        return None
    lock_by_round = {item[2]["identity"]["round_number"]: item for item in locks}
    evaluation_by_round = {item[2]["identity"]["round_number"]: item for item in evaluations}
    expected_rounds = {window.round_number for window in ROUNDS}
    if set(lock_by_round) != expected_rounds or set(evaluation_by_round) != expected_rounds:
        raise RuntimeError("incomplete or ambiguous immutable round checkpoint")

    candidates: list[dict] = []
    values_by_factor: dict[str, pd.DataFrame] = {}
    signal_by_factor: dict[str, Path] = {}
    annual: dict[str, dict] = {}
    backtests: dict[str, dict] = {}
    round_records: list[dict] = []
    published: list[dict] = []
    total_trials = 0
    total_agent_calls = 0
    signals_root.mkdir(parents=True, exist_ok=True)

    for window in ROUNDS:
        lock_descriptor, lock_path, lock_manifest = lock_by_round[window.round_number]
        evaluation_descriptor, evaluation_path, evaluation_manifest = evaluation_by_round[window.round_number]
        identity = lock_manifest["identity"]
        evaluation_payload = json.loads((evaluation_path / "evaluation.json").read_text(encoding="utf-8"))
        if evaluation_manifest["identity"].get("round_lock_id") != lock_descriptor.artifact_id:
            raise RuntimeError("round evaluation does not reference its immutable lock")
        result_by_factor = {row["factor_instance_id"]: row for row in evaluation_payload["results"]}
        round_trials = sum(len(row.get("trials", [])) for row in identity["candidates"])
        total_trials += round_trials
        # A non-null decision with no repair failure proves one successful call.
        round_agent_calls = 1 if identity.get("decision_id") is not None else len(identity.get("agent_failures", []))
        total_agent_calls += round_agent_calls
        for row in identity["candidates"]:
            selected = row["selected_trial"]
            factor_id = selected["factor_instance_id"]
            template = parse_template(row["template"])
            compiled, values = factor_values(template, contract, selected["parameters"], matrix)
            if compiled.factor_instance_id != factor_id or compiled.template_id != row["template_id"]:
                raise RuntimeError("recovered Factor identity does not match immutable round lock")
            values_by_factor[factor_id] = values
            stored_signal = lock_path / "factor_values" / f"{factor_id}.parquet"
            signal = signals_root / f"{factor_id}.parquet"
            shutil.copyfile(stored_signal, signal)
            signal_by_factor[factor_id] = signal
            result = result_by_factor.get(factor_id)
            if result is None:
                raise RuntimeError("immutable round evaluation is incomplete")
            annual.setdefault(factor_id, {})[window.evaluation_year] = result["metrics"]
            backtests.setdefault(factor_id, {})[window.evaluation_year] = result["qlib"]
            candidates.append({
                "factor_instance_id": factor_id,
                "origin_round": window.round_number,
                "template_id": row["template_id"],
                "template": row["template"],
                "selected_trial": selected,
                "signal_path": str(signal),
            })
        summary_rank = [
            row["metrics"].get("mean_rank_ic")
            for row in evaluation_payload["results"]
            if row["metrics"].get("mean_rank_ic") is not None
        ]
        summary_excess = [
            row["qlib"].get("net_excess_fixed_100")
            for row in evaluation_payload["results"]
            if row["qlib"].get("net_excess_fixed_100") is not None
        ]
        round_records.append({
            "round_number": window.round_number,
            "research_period": [window.research_start, window.research_end],
            "evaluation_year": window.evaluation_year,
            "proposed": len(identity["candidates"]) + len(identity["rejected"]),
            "admitted": len(identity["candidates"]),
            "trials": round_trials,
            "agent_calls": round_agent_calls,
            "contract_failures": len(identity.get("agent_failures", [])),
            "duplicate_count": sum("duplicate_structure" in item["reason"] for item in identity["rejected"]),
            "lock_id": lock_descriptor.artifact_id,
            "evaluation_id": evaluation_descriptor.artifact_id,
            "evaluation_summary": {
                "mean_rank_ic": None if not summary_rank else float(np.mean(summary_rank)),
                "net_excess_fixed_100": None if not summary_excess else float(np.mean(summary_excess)),
                "maximum_drawdown": None if not evaluation_payload["results"] else float(np.mean([
                    row["qlib"].get("max_drawdown") or 0 for row in evaluation_payload["results"]
                ])),
            },
        })
        published.extend([
            {
                "artifact_kind": lock_descriptor.artifact_kind,
                "artifact_id": lock_descriptor.artifact_id,
                "descriptor_id": lock_descriptor.descriptor_id,
                "exact_existing": True,
                "new_blob_count": 0,
            },
            {
                "artifact_kind": evaluation_descriptor.artifact_kind,
                "artifact_id": evaluation_descriptor.artifact_id,
                "descriptor_id": evaluation_descriptor.descriptor_id,
                "exact_existing": True,
                "new_blob_count": 0,
            },
        ])
    return {
        "candidates": candidates,
        "values_by_factor": values_by_factor,
        "signal_by_factor": signal_by_factor,
        "annual": annual,
        "backtests": backtests,
        "round_records": round_records,
        "published": published,
        "total_trials": total_trials,
        "total_agent_calls": total_agent_calls,
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
    authority_path = repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json"
    bundle = load_authority_bundle(authority_path=authority_path, work_root=work_root, store_root=store_root)
    protocol = fixed_protocol(bundle.authority)
    existing = bundle.store.list_by_kind("tushare_historical_agent_experiment")
    for descriptor in existing:
        target = work_root / "replay" / descriptor.artifact_id
        if target.exists():
            shutil.rmtree(target)
        bundle.store.materialize_artifact(descriptor.descriptor_id, target)
        manifest = json.loads((target / "manifest.json").read_text())
        if manifest["identity"].get("protocol_id") == protocol["protocol_id"]:
            return replay_experiment(repository_root=repository_root, work_root=work_root, store_root=store_root)

    matrix = bundle.matrix
    contract = snapshot_contract(
        bundle.authority["feature_dataset_id"], int(matrix["trade_date"].nunique())
    )
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    artifact_root = work_root / "artifacts"
    signals_root = work_root / "signals"
    prior_templates: list[dict] = []
    prior_feedback: list[dict] = []
    fingerprints: set[str] = set()
    candidates: list[dict] = []
    values_by_factor: dict[str, pd.DataFrame] = {}
    signal_by_factor: dict[str, Path] = {}
    annual: dict[str, dict] = {}
    backtests: dict[str, dict] = {}
    round_records: list[dict] = []
    published: list[dict] = []
    total_agent_calls = total_trials = 0

    recovery = _recover_locked_rounds(
        bundle=bundle,
        protocol=protocol,
        work_root=work_root,
        matrix=matrix,
        contract=contract,
        signals_root=signals_root,
    )
    if recovery is not None:
        candidates = recovery["candidates"]
        values_by_factor = recovery["values_by_factor"]
        signal_by_factor = recovery["signal_by_factor"]
        annual = recovery["annual"]
        backtests = recovery["backtests"]
        round_records = recovery["round_records"]
        published = recovery["published"]
        total_trials = recovery["total_trials"]
        total_agent_calls = recovery["total_agent_calls"]

    for window in ROUNDS:
        if recovery is not None:
            continue
        memory = build_memory(
            round_number=window.round_number,
            research_end=window.research_end,
            sanitized_source=bundle.sanitized_memory,
            prior_templates=prior_templates,
            prior_feedback=prior_feedback,
            fingerprints=fingerprints,
        )
        validate_memory(memory, window.round_number, window.research_end)
        goal = ResearchGoal(
            "trg_" + hash_payload({"protocol": protocol["protocol_id"], "round": window.round_number}),
            f"tushare_fixed100_round_{window.round_number}",
            "Propose economically interpretable canonical DSL structures that respond only to visible aggregate prior-round evidence.",
            "tushare_feature_matrix_v1",
            FEATURES,
            OPERATORS,
            ("lookback_window", "factor_internal_weight"),
            2,
            6,
            1,
            "structure must differ from all supplied structural fingerprints",
            (
                "no labels or daily series",
                "no future evaluation or holdout",
                "no portfolio parameter authority",
                "use only Tushare Feature Contract fields",
            ),
        )
        decision, calls, agent_failures = _agent_decision(agent, goal, memory)
        total_agent_calls += len(calls)
        admitted: list[dict] = []
        rejected: list[dict] = []
        round_trials = 0
        if decision is not None:
            for proposal in decision["proposals"]:
                if len(admitted) >= BUDGET["max_admitted_templates"]:
                    rejected.append({"proposal_id": proposal["proposal_id"], "reason": "admission_budget"})
                    continue
                try:
                    template = parse_template(proposal["template"])
                    if template.dataset_kinds != ("tushare_feature_matrix_v1",):
                        raise ValueError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
                    fingerprint = structural_fingerprint(template)
                    if fingerprint in fingerprints:
                        raise ValueError("duplicate_structure")
                    parameter_rows = _parameter_rows(proposal)
                    if len(parameter_rows) > BUDGET["max_trials_per_template"] or round_trials + len(parameter_rows) > BUDGET["max_total_trials"]:
                        raise ValueError("trial_budget_exceeded")
                    trials = []
                    for ordinal, parameters in enumerate(parameter_rows, 1):
                        compiled, values = factor_values(template, contract, parameters, matrix)
                        raw = split_metrics(values, matrix, window.research_start, window.research_end, 1)
                        orientation = 1 if (raw.get("mean_rank_ic") or 0.0) >= 0 else -1
                        oriented = split_metrics(values, matrix, window.research_start, window.research_end, orientation)
                        trial_id = "tht_" + hash_payload({
                            "round": window.round_number,
                            "template_id": compiled.template_id,
                            "parameters": parameters,
                            "feature_dataset_id": bundle.authority["feature_dataset_id"],
                        })
                        trials.append({
                            "trial_id": trial_id,
                            "ordinal": ordinal,
                            "factor_instance_id": compiled.factor_instance_id,
                            "parameters": parameters,
                            "orientation": orientation,
                            "research_raw_metrics": raw,
                            "research_oriented_metrics": oriented,
                            "values": values,
                        })
                    selected = max(trials, key=_metric_key)
                    factor_id = selected["factor_instance_id"]
                    values_by_factor[factor_id] = selected.pop("values")
                    for row in trials:
                        row.pop("values", None)
                    signal = oriented_signal(
                        values_by_factor[factor_id], selected["orientation"], signals_root / f"{factor_id}.parquet"
                    )
                    signal_by_factor[factor_id] = signal
                    admitted.append({
                        "proposal_id": proposal["proposal_id"],
                        "template": proposal["template"],
                        "template_id": compiled.template_id,
                        "structure_fingerprint": fingerprint,
                        "rationale": proposal["rationale"],
                        "risks": proposal["risks"],
                        "study_id": "ths_" + hash_payload({"round": window.round_number, "proposal": proposal}),
                        "trials": trials,
                        "selected_trial": selected,
                    })
                    fingerprints.add(fingerprint)
                    round_trials += len(trials)
                    total_trials += len(trials)
                except Exception as exc:
                    rejected.append({"proposal_id": proposal["proposal_id"], "reason": f"{type(exc).__name__}:{str(exc)[:160]}"})
        lock_identity = {
            "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"],
            "round_number": window.round_number,
            "research_period": [window.research_start, window.research_end],
            "evaluation_period": [window.evaluation_start, window.evaluation_end],
            "universe_100_id": bundle.authority["universe_100"]["universe_lock_id"],
            "feature_dataset_id": bundle.authority["feature_dataset_id"],
            "label_dataset_id": bundle.authority["label_dataset_id"],
            "memory_id": memory["memory_id"],
            "decision_id": None if decision is None else decision["decision_id"],
            "candidates": [
                {key: value for key, value in row.items() if key != "trials"} | {"trials": row["trials"]}
                for row in admitted
            ],
            "rejected": rejected,
            "agent_failures": agent_failures,
            "portfolio_protocol": protocol["portfolio"],
            "locked_before_evaluation": True,
            "orientation_source": "research_period_only",
            "parameter_source": "research_period_only",
            "promotion_writes": 0,
        }
        lock_files = {
            f"factor_values/{row['selected_trial']['factor_instance_id']}.parquet": signal_by_factor[row["selected_trial"]["factor_instance_id"]]
            for row in admitted
        }
        lock = publish_experiment_artifact(artifact_root, "tushare_historical_round_lock", lock_identity, lock_files)
        published.append(_publish_to_store(bundle, lock, "tushare_historical_round_lock", (
            bundle.authority["universe_100"]["universe_lock_id"],
            bundle.authority["feature_dataset_id"],
            bundle.authority["label_dataset_id"],
        )))

        evaluations = []
        for row in admitted:
            selected = row["selected_trial"]
            factor_id = selected["factor_instance_id"]
            metrics = split_metrics(values_by_factor[factor_id], matrix, window.evaluation_start, window.evaluation_end, selected["orientation"])
            diagnostics = group_diagnostics(values_by_factor[factor_id], matrix, window.evaluation_start, window.evaluation_end, selected["orientation"])
            qlib_result = qlib.run(signal_by_factor[factor_id], window.evaluation_start, window.evaluation_end)
            annual.setdefault(factor_id, {})[window.evaluation_year] = metrics | diagnostics
            backtests.setdefault(factor_id, {})[window.evaluation_year] = qlib_result
            evaluations.append({"factor_instance_id": factor_id, "metrics": metrics | diagnostics, "qlib": qlib_result})
            candidates.append({
                "factor_instance_id": factor_id,
                "origin_round": window.round_number,
                "template_id": row["template_id"],
                "template": row["template"],
                "selected_trial": selected,
                "signal_path": str(signal_by_factor[factor_id]),
            })
        evaluation_payload = {
            "round_number": window.round_number,
            "evaluation_year": window.evaluation_year,
            "round_lock_id": lock["round_lock_id"],
            "results": evaluations,
            "daily_series_disclosed_to_agent": False,
        }
        evaluation_identity = {
            "provider_id": "tushare-pro-v1",
            "protocol_id": protocol["protocol_id"],
            "round_number": window.round_number,
            "round_lock_id": lock["round_lock_id"],
            "evaluation_year": window.evaluation_year,
            "payload_hash": hash_payload(evaluation_payload),
            "promotion_writes": 0,
        }
        evaluation = publish_experiment_artifact(
            artifact_root,
            "tushare_historical_round_evaluation",
            evaluation_identity,
            {"evaluation.json": evaluation_payload},
        )
        published.append(_publish_to_store(bundle, evaluation, "tushare_historical_round_evaluation", (lock["round_lock_id"],)))
        feedback = [{
            "round_number": window.round_number,
            "evaluation_year": window.evaluation_year,
            "factor_instance_id": item["factor_instance_id"],
            "mean_rank_ic": item["metrics"].get("mean_rank_ic"),
            "rank_icir": item["metrics"].get("rank_icir"),
            "net_excess": item["qlib"].get("net_excess_fixed_100"),
            "maximum_drawdown": item["qlib"].get("max_drawdown"),
            "turnover": item["qlib"].get("turnover"),
            "group_monotonicity": item["metrics"].get("group_monotonicity"),
            "rank_ic_band": _feedback_band(item["metrics"].get("mean_rank_ic")),
            "daily_series_included": False,
        } for item in evaluations]
        prior_feedback.extend(feedback)
        prior_templates.extend({
            "round_number": window.round_number,
            "template_id": row["template_id"],
            "template": row["template"],
            "selected_parameters": row["selected_trial"]["parameters"],
        } for row in admitted)
        summary_rank = [item["metrics"].get("mean_rank_ic") for item in evaluations if item["metrics"].get("mean_rank_ic") is not None]
        summary_excess = [item["qlib"].get("net_excess_fixed_100") for item in evaluations if item["qlib"].get("net_excess_fixed_100") is not None]
        round_records.append({
            "round_number": window.round_number,
            "research_period": [window.research_start, window.research_end],
            "evaluation_year": window.evaluation_year,
            "proposed": 0 if decision is None else len(decision["proposals"]),
            "admitted": len(admitted),
            "trials": round_trials,
            "agent_calls": len(calls),
            "contract_failures": len(agent_failures),
            "duplicate_count": sum("duplicate_structure" in item["reason"] for item in rejected),
            "lock_id": lock["round_lock_id"],
            "evaluation_id": evaluation["evaluation_id"],
            "evaluation_summary": {
                "mean_rank_ic": None if not summary_rank else float(np.mean(summary_rank)),
                "net_excess_fixed_100": None if not summary_excess else float(np.mean(summary_excess)),
                "maximum_drawdown": None if not evaluations else float(np.mean([item["qlib"].get("max_drawdown") or 0 for item in evaluations])),
            },
        })

    # Agent access is now closed. Evaluate only pre-holdout years required for the
    # immutable final-candidate lock.
    for candidate in candidates:
        factor_id = candidate["factor_instance_id"]
        first = 2020 + candidate["origin_round"]
        years = [str(year) for year in range(first, 2025)]
        annual.setdefault(factor_id, {}).update({
            year: value for year, value in _annual_metrics(values_by_factor[factor_id], matrix, candidate["selected_trial"]["orientation"], years).items()
            if year not in annual[factor_id]
        })
        backtests.setdefault(factor_id, {})
        for year in years:
            if year not in backtests[factor_id]:
                backtests[factor_id][year] = qlib.run(signal_by_factor[factor_id], *YEAR_WINDOWS[year])
    final_lock = _select_final(candidates, annual, backtests)
    selected_ids = final_lock["selected_factor_instance_ids"]

    final_signals = {factor_id: signal_by_factor[factor_id] for factor_id in selected_ids}
    if len(final_signals) >= 2:
        final_signals["equal_weight_combo"] = equal_weight_signal(final_signals, signals_root / "equal_weight_combo.parquet")
    nan_gate = {}
    for name, signal in final_signals.items():
        frame = pd.read_parquet(signal)
        period = frame[pd.to_datetime(frame["trade_date"]).between("2026-01-05", "2026-06-23")]
        nan_gate[name] = float(pd.to_numeric(period["pred"], errors="coerce").isna().mean())
        if nan_gate[name] > 0.2:
            raise RuntimeError("2026H1_SIGNAL_NAN_GATE_FAILED")
    final_annual: dict[str, dict] = {}
    final_backtests: dict[str, dict] = {}
    holdout: dict[str, dict] = {}
    for name, signal in final_signals.items():
        final_backtests[name] = {}
        if name != "equal_weight_combo":
            candidate = next(item for item in candidates if item["factor_instance_id"] == name)
            final_annual[name] = _annual_metrics(values_by_factor[name], matrix, candidate["selected_trial"]["orientation"], list(YEAR_WINDOWS))
        for year, dates in YEAR_WINDOWS.items():
            result = qlib.run(signal, *dates)
            final_backtests[name][year] = result
            if year in {"2025", "2026H1"}:
                holdout.setdefault(name, {})[year] = result
        final_backtests[name]["2019-2026H1"] = qlib.run(signal, "2019-01-02", "2026-06-23")

    robustness = {}
    if final_signals:
        diagnostic_name = "equal_weight_combo" if "equal_weight_combo" in final_signals else selected_ids[0]
        diagnostic_signal = final_signals[diagnostic_name]
        for topk in (10, 20, 30):
            for rebalance_days in (1, 5):
                for cost_multiplier in (1.0, 2.0):
                    key = f"topk{topk}_rebalance{rebalance_days}_cost{cost_multiplier:g}x"
                    robustness[key] = qlib.run(
                        diagnostic_signal,
                        "2019-01-02",
                        "2026-06-23",
                        topk=topk,
                        n_drop=5,
                        rebalance_days=rebalance_days,
                        cost_multiplier=cost_multiplier,
                    )

    factor_correlations = {}
    for left, right in itertools.combinations(selected_ids, 2):
        pair = values_by_factor[left].merge(values_by_factor[right], on=["symbol", "trade_date"], suffixes=("_left", "_right"))
        factor_correlations[f"{left}:{right}"] = float(pair["factor_value_left"].corr(pair["factor_value_right"], method="spearman"))

    assessment_payload = _improvement(round_records)
    assessment_identity = {
        "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"],
        "classification": assessment_payload["classification"],
        "payload_hash": hash_payload(assessment_payload),
        "promotion_writes": 0,
    }
    assessment = publish_experiment_artifact(
        artifact_root,
        "tushare_agent_iteration_assessment",
        assessment_identity,
        {"assessment.json": assessment_payload},
    )
    published.append(_publish_to_store(bundle, assessment, "tushare_agent_iteration_assessment", tuple(row["evaluation_id"] for row in round_records)))

    qlib_payload = {
        "selection": final_lock,
        "annual_factor_metrics": final_annual,
        "annual_backtests": final_backtests,
        "robustness": robustness,
        "factor_correlations": factor_correlations,
        "nan_gate": nan_gate,
        "formal_qlib_calls": qlib.calls,
    }
    qlib_identity = {
        "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"],
        "selection_data_end": "2024-12-31",
        "payload_hash": hash_payload(qlib_payload),
        "promotion_writes": 0,
    }
    qlib_artifact = publish_experiment_artifact(
        artifact_root,
        "tushare_qlib_backtest_result",
        qlib_identity,
        {"results.json": qlib_payload, **{f"signals/{name}.parquet": path for name, path in final_signals.items()}},
    )
    published.append(_publish_to_store(bundle, qlib_artifact, "tushare_qlib_backtest_result", tuple(selected_ids) + (bundle.authority["qlib_view_id"],)))

    holdout_identity = {
        "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"],
        "candidate_lock": final_lock,
        "candidate_count": len(selected_ids),
        "holdout_feedback_to_agent": False,
        "nan_gate": nan_gate,
        "payload_hash": hash_payload(holdout),
        "promotion_writes": 0,
    }
    holdout_artifact = publish_experiment_artifact(
        artifact_root,
        "tushare_historical_holdout_result",
        holdout_identity,
        {"holdout.json": holdout},
    )
    published.append(_publish_to_store(bundle, holdout_artifact, "tushare_historical_holdout_result", (qlib_artifact["backtest_result_id"],)))

    registry_payload = {
        "schema_version": "tushare-historical-agent-experiment-registry-v1",
        "parent_genesis_registry_id": bundle.authority["registry_genesis_id"],
        "entries": [
            {
                "factor_instance_id": candidate["factor_instance_id"],
                "template_id": candidate["template_id"],
                "origin_round": candidate["origin_round"],
                "status": "research_registered",
                "selected_for_holdout": candidate["factor_instance_id"] in selected_ids,
            }
            for candidate in candidates
        ],
        "promotion_candidate_count": 0,
        "approved_count": 0,
        "active_count": 0,
    }
    registry_identity = {
        "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"],
        "parent_genesis_registry_id": bundle.authority["registry_genesis_id"],
        "payload_hash": hash_payload(registry_payload),
        "promotion_writes": 0,
    }
    registry = publish_experiment_artifact(
        artifact_root,
        "tushare_historical_experiment_registry",
        registry_identity,
        {"registry.json": registry_payload},
    )
    published.append(_publish_to_store(bundle, registry, "tushare_historical_experiment_registry", (bundle.authority["registry_genesis_id"],)))

    experiment_payload = {
        "protocol": protocol,
        "rounds": round_records,
        "candidate_lock": final_lock,
        "assessment_id": assessment["assessment_id"],
        "qlib_backtest_result_id": qlib_artifact["backtest_result_id"],
        "holdout_result_id": holdout_artifact["holdout_result_id"],
        "historical_experiment_registry_id": registry["historical_experiment_registry_id"],
        "execution_counts": {
            "agent_calls": total_agent_calls,
            "optimization_trials": total_trials,
            "qlib_backtest_calls": qlib.calls,
            "production_registry_writes": 0,
            "promotion_writes": 0,
        },
        "legacy_reads": 0,
        "tushare_network_calls": 0,
        "status": "completed",
    }
    experiment_identity = {
        "provider_id": "tushare-pro-v1",
        "protocol_id": protocol["protocol_id"],
        "payload_hash": hash_payload(experiment_payload),
        "promotion_writes": 0,
    }
    experiment = publish_experiment_artifact(
        artifact_root,
        "tushare_historical_agent_experiment",
        experiment_identity,
        {"experiment.json": experiment_payload},
    )
    published.append(_publish_to_store(bundle, experiment, "tushare_historical_agent_experiment", (
        assessment["assessment_id"],
        qlib_artifact["backtest_result_id"],
        holdout_artifact["holdout_result_id"],
        registry["historical_experiment_registry_id"],
    )))

    # Empty-cache recovery of every artifact created by this run.
    cold_root = work_root / "cold-recovery"
    if cold_root.exists():
        shutil.rmtree(cold_root)
    for item in published:
        descriptor = bundle.store.find_by_artifact_id(item["artifact_id"])
        destination = cold_root / item["artifact_kind"] / item["artifact_id"]
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        validate_experiment_artifact(destination, item["artifact_id"], expected_kind=item["artifact_kind"])
    replay = replay_experiment(repository_root=repository_root, work_root=work_root / "replay-check", store_root=store_root)
    inventory = publish_inventory(bundle.store)
    integrity = scan_store_integrity(bundle.store)
    return {
        "experiment_id": experiment["experiment_id"],
        "protocol_id": protocol["protocol_id"],
        "rounds": round_records,
        "selection": final_lock,
        "assessment": assessment_payload,
        "qlib": qlib_payload,
        "registry": registry_payload,
        "execution_counts": experiment_payload["execution_counts"],
        "published": published,
        "inventory": asdict(inventory),
        "integrity": {
            "status": integrity.status,
            "missing": len(integrity.issues),
            "unreferenced": len(integrity.unreferenced_blobs),
        },
        "cold_restored": len(published),
        "replay": replay,
    }


def replay_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict:
    bundle = load_authority_bundle(
        authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=Path(work_root),
        store_root=store_root,
    )
    protocol_id = fixed_protocol(bundle.authority)["protocol_id"]
    matches = []
    for descriptor in bundle.store.list_by_kind("tushare_historical_agent_experiment"):
        target = Path(work_root) / "experiment-replay" / descriptor.artifact_id
        if target.exists():
            shutil.rmtree(target)
        bundle.store.materialize_artifact(descriptor.descriptor_id, target)
        manifest = json.loads((target / "manifest.json").read_text())
        if manifest["identity"].get("protocol_id") == protocol_id:
            matches.append((descriptor, target))
    if len(matches) != 1:
        raise RuntimeError("exact experiment replay identity is absent or ambiguous")
    descriptor, target = matches[0]
    validate_experiment_artifact(target, descriptor.artifact_id, expected_kind=descriptor.artifact_kind)
    return {
        "exact_existing": True,
        "experiment_id": descriptor.artifact_id,
        "agent_calls": 0,
        "optimization_calls": 0,
        "qlib_backtest_calls": 0,
        "registry_writes": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
        "tushare_network_calls": 0,
        "legacy_reads": 0,
    }
