from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from backend.services.engine.factor_dsl import parse_template, snapshot_contract
from backend.services.engine.factor_optimization import execute_study, parse_optimization_spec, plan_study
from backend.services.engine.factor_validation.metrics import calculate_split_metrics, metrics_payload
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError, ResearchCampaignError
from backend.services.engine.research_campaign.models import (
    ResearchAgentRequest, ResearchCampaignBudget, ResearchGoal,
)
from backend.services.engine.research_campaign.novelty import structural_fingerprint
from backend.services.engine.research_campaign.orchestrator import (
    _feature_names, _operator_names, _optimization_payload, _request,
)

from .artifact import publish_historical_artifact
from .canonical import hash_payload
from .memory import build_as_of_memory, validate_as_of_memory
from .protocol import BUDGET, ROUNDS, fixed_protocol


ALLOWED_OPERATORS = (
    "add", "subtract", "multiply", "divide", "negate", "absolute", "cs_rank", "cs_zscore",
    "rolling_mean", "rolling_std", "rolling_min", "rolling_max", "delta",
)


def _subset(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    dates = pd.to_datetime(frame["trade_date"])
    return frame[(dates >= start) & (dates <= end)].copy()


def _values(root: Path, factor_values_id: str) -> pd.DataFrame:
    return pd.read_parquet(Path(root) / factor_values_id / "values.parquet", engine="pyarrow")


def _selection_metrics(values: pd.DataFrame, labels: pd.DataFrame) -> tuple[int, dict, dict]:
    raw = calculate_split_metrics(values, labels, orientation=1)
    orientation = 1 if (raw.mean_rank_ic or 0.0) >= 0 else -1
    oriented = calculate_split_metrics(values, labels, orientation=orientation)
    return orientation, metrics_payload(raw), metrics_payload(oriented)


def _trial_key(row: dict) -> tuple:
    metrics = row["research_oriented_metrics"]
    return (metrics.get("mean_rank_ic") or -999.0, metrics.get("rank_icir") or -999.0,
            metrics.get("factor_finite_coverage") or 0.0, row["trial_id"])


def _band(value: float | None) -> str:
    value = value or 0.0
    if value >= 0.03: return "strong_positive"
    if value >= 0.005: return "weak_positive"
    if value > -0.005: return "neutral"
    if value > -0.03: return "weak_negative"
    return "strong_negative"


def _agent_decision(agent, goal, budget, memory) -> tuple[dict, list[dict]]:
    request = _request(goal, memory, budget, 1)
    calls = []
    error = None
    for attempt in range(BUDGET["max_agent_calls"]):
        if error is not None:
            request = ResearchAgentRequest(request.goal, request.sanitized_memory,
                {**request.contract, "repair_instruction": {
                    "error_code": type(error).__name__, "safe_summary": str(error)[:160],
                    "allowed_fix_actions": ["return contract-valid replacement JSON", "reduce search-space values"],
                }})
        response = agent.propose(request)
        calls.append(dict(response.usage_summary or {}))
        try:
            return parse_decision(response.raw_response, iteration=1, goal=goal, budget=budget,
                                  provider_id=response.provider_id, model_id=response.model_id), calls
        except AgentContractError as exc:
            error = exc
    raise ResearchCampaignError(f"Agent contract failed after bounded repair: {error}")


def run_historical_experiment(*, dataset_root: Path, dataset_id: str, snapshot_root: Path,
                              snapshot_id: str, factor_values_root: Path, optimization_root: Path,
                              artifact_root: Path, agent=None) -> dict:
    dataset_path = Path(dataset_root) / "fixed_universe_historical_dataset" / dataset_id
    manifest = json.loads((dataset_path / "manifest.json").read_text())
    matrix = pd.read_parquet(dataset_path / "historical_matrix.parquet", engine="pyarrow")
    labels = matrix[["symbol", "trade_date", "model_label"]]
    contract = snapshot_contract(snapshot_root, snapshot_id)
    features = tuple(manifest["feature_columns"])
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    protocol = fixed_protocol()
    prior_templates: list[dict] = []
    feedback: list[dict] = []
    fingerprints: set[str] = set()
    all_candidates: list[dict] = []
    round_outputs = []
    total_calls = total_trials = 0
    for window in ROUNDS:
        memory = build_as_of_memory(
            round_number=window.round_number, research_end=window.research_end,
            allowed_features=features, prior_templates=prior_templates,
            prior_feedback=feedback, structure_fingerprints=fingerprints,
        )
        validate_as_of_memory(memory, expected_round=window.round_number,
                              expected_research_end=window.research_end)
        goal_id = "rg_" + hash_payload({"experiment": protocol["protocol_id"], "round": window.round_number})
        goal = ResearchGoal(
            goal_id, f"fixed100_round_{window.round_number}",
            "Propose economically interpretable cross-sectional factor structures that address only prior aggregate failures.",
            contract.dataset_kind, features, ALLOWED_OPERATORS,
            ("lookback_window", "factor_internal_weight"), 2, 6, 1,
            "structure must differ from every fingerprint supplied in historical as-of memory",
            ("no label access", "no daily series", "no future year", "no portfolio parameter authority"),
        )
        budget = ResearchCampaignBudget(
            max_iterations=1, max_agent_calls=2, max_proposals_per_iteration=3,
            max_total_admitted_templates=2, max_total_trials=12, max_failed_proposals=3,
            max_failed_trials=12, max_agent_repair_attempts_per_call=1,
        )
        decision, calls = _agent_decision(agent, goal, budget, memory)
        total_calls += len(calls)
        admitted = []
        rejected = []
        round_trials = 0
        research_labels = _subset(labels, window.research_start, window.research_end)
        for proposal in decision["proposals"]:
            if len(admitted) >= BUDGET["max_admitted_templates"]:
                rejected.append({"proposal_id": proposal["proposal_id"], "reason": "admission_budget"}); continue
            try:
                template = parse_template(proposal["template"])
                if set(_feature_names(proposal["template"]["expression"])) - set(features):
                    raise ResearchCampaignError("feature_outside_historical_contract")
                if set(_operator_names(proposal["template"]["expression"])) - set(ALLOWED_OPERATORS):
                    raise ResearchCampaignError("operator_outside_historical_contract")
                fingerprint = structural_fingerprint(template)
                if fingerprint in fingerprints:
                    raise ResearchCampaignError("duplicate_structure")
                remaining = BUDGET["max_total_trials"] - round_trials
                spec_payload = _optimization_payload(proposal, snapshot_id, remaining)
                spec = parse_optimization_spec(spec_payload)
                study = plan_study(spec, contract)
                if len(study.trials) > BUDGET["max_trials_per_template"]:
                    raise ResearchCampaignError("template_trial_budget_exceeded")
                result = execute_study(study, contract, snapshot_root, factor_values_root, optimization_root)
                round_trials += len(study.trials); total_trials += len(study.trials)
                trial_rows = []
                for trial in result.trials:
                    if trial.factor_values_id is None or not trial.eligible_for_validation:
                        continue
                    orientation, raw_metrics, oriented_metrics = _selection_metrics(
                        _values(factor_values_root, trial.factor_values_id), research_labels,
                    )
                    trial_rows.append({
                        "trial_id": trial.trial_id, "factor_instance_id": trial.factor_instance_id,
                        "factor_values_id": trial.factor_values_id, "parameters": dict(trial.parameters),
                        "orientation": orientation, "research_raw_metrics": raw_metrics,
                        "research_oriented_metrics": oriented_metrics,
                    })
                if not trial_rows:
                    raise ResearchCampaignError("no_successful_eligible_trial")
                selected = max(trial_rows, key=_trial_key)
                row = {
                    "proposal_id": proposal["proposal_id"], "template": proposal["template"],
                    "template_id": study.template_id, "structure_fingerprint": fingerprint,
                    "study_id": study.study_id, "trial_count": len(study.trials),
                    "selected_trial": selected, "rationale": proposal["rationale"],
                    "risks": proposal["risks"],
                }
                admitted.append(row); fingerprints.add(fingerprint)
            except Exception as exc:
                rejected.append({"proposal_id": proposal["proposal_id"],
                                 "reason": f"{type(exc).__name__}:{str(exc)[:120]}"})
        lock_identity = {
            "schema_version": "historical-round-candidate-lock-v1",
            "protocol_id": protocol["protocol_id"], "round_number": window.round_number,
            "dataset_id": dataset_id, "feature_snapshot_id": snapshot_id,
            "research_period": [window.research_start, window.research_end],
            "next_year_evaluation_period": [window.evaluation_start, window.evaluation_end],
            "memory_id": memory["memory_id"], "decision_id": decision["decision_id"],
            "candidates": admitted, "rejected_proposals": rejected,
            "portfolio_protocol": protocol["portfolio"], "locked_before_evaluation": True,
            "orientation_source": "research_period_only", "parameter_source": "research_period_only",
        }
        lock = publish_historical_artifact(artifact_root, "historical_round_lock", lock_identity)
        evaluation_labels = _subset(labels, window.evaluation_start, window.evaluation_end)
        evaluations = []
        for candidate in admitted:
            selected = candidate["selected_trial"]
            oriented = calculate_split_metrics(
                _values(factor_values_root, selected["factor_values_id"]), evaluation_labels,
                orientation=selected["orientation"],
            )
            evaluations.append({
                "factor_instance_id": selected["factor_instance_id"],
                "factor_values_id": selected["factor_values_id"], "metrics": metrics_payload(oriented),
                "qlib_backtest": None, "qlib_status": "pending_formal_execution",
            })
            all_candidates.append({**candidate, "origin_round": window.round_number,
                                   "next_year_metrics": metrics_payload(oriented)})
        evaluation_identity = {
            "schema_version": "historical-round-evaluation-v1",
            "protocol_id": protocol["protocol_id"], "round_number": window.round_number,
            "round_lock_id": lock["round_lock_id"], "evaluation_year": window.evaluation_label,
            "results": evaluations, "daily_series_disclosed_to_agent": False,
        }
        evaluation = publish_historical_artifact(
            artifact_root, "historical_round_evaluation", evaluation_identity,
        )
        round_feedback = [{
            "round_number": window.round_number, "evaluation_year": window.evaluation_label,
            "factor_instance_id": row["factor_instance_id"],
            "rank_ic": row["metrics"]["mean_rank_ic"],
            "rank_ic_band": _band(row["metrics"]["mean_rank_ic"]),
            "qlib_net_excess_band": "unavailable_until_formal_qlib_execution",
            "daily_series_included": False,
        } for row in evaluations]
        feedback.extend(round_feedback)
        prior_templates.extend({"round_number": window.round_number, "template": row["template"],
                                "selected_parameters": row["selected_trial"]["parameters"]}
                               for row in admitted)
        round_outputs.append({
            "round": window.round_number, "memory": memory, "decision": decision,
            "provider_calls": calls, "lock": lock, "evaluation": evaluation,
            "feedback": round_feedback, "proposed": len(decision["proposals"]),
            "admitted": len(admitted), "trials": round_trials,
        })
    experiment_identity = {
        "schema_version": "historical-agent-experiment-v1",
        "protocol": protocol, "dataset_id": dataset_id, "feature_snapshot_id": snapshot_id,
        "rounds": round_outputs, "all_candidates": all_candidates,
        "execution_counts": {"agent_calls": total_calls, "optimization_trials": total_trials,
                             "qlib_backtest_calls": 0},
        "status": "partial_pending_formal_qlib",
        "production_registry_writes": 0, "promotion_writes": 0,
        "fresh_artifacts_accessed": False, "frozen_artifacts_accessed": False,
    }
    experiment = publish_historical_artifact(
        artifact_root, "historical_agent_experiment", experiment_identity,
    )
    return {**experiment, "rounds": round_outputs, "all_candidates": all_candidates,
            "execution_counts": experiment_identity["execution_counts"]}
