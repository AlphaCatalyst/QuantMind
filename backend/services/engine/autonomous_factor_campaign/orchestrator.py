from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import (
    DATASET_KIND, OPERATORS, SOURCE_DATASET_ID,
)
from backend.services.engine.momentum_factor_iteration.engine import _snapshot_contract
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.models import ResearchCampaignBudget, ResearchGoal
from backend.services.engine.research_campaign.orchestrator import _request
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle
from backend.services.engine.tushare_cutover.canonical import hash_payload
from backend.services.engine.tushare_cutover.canonical import hash_file

from .admission import admit_proposal
from .evaluation import CampaignEvaluator
from .failure_memory import initial_memory, update_memory
from .models import (
    CAMPAIGN_STATES, TERMINAL_STATES, AutonomousFactorCampaignSpecV1,
    CampaignBudget, empty_budget_usage,
)
from .planner import early_stop_reason, plan_next_round
from .repository import CampaignRepository


AUTHORITY = "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json"


def _runtime(repository_root: Path, work_root: Path, store_root: Path | None):
    bundle = load_authority_bundle(
        authority_path=Path(repository_root) / AUTHORITY,
        work_root=Path(work_root) / "authority", store_root=store_root,
    )
    repository = CampaignRepository(
        bundle.store, Path(work_root) / "domain", Path(work_root) / "recovery"
    )
    return bundle, repository


def create_campaign_spec(*, repository_root: Path, work_root: Path,
                         store_root: Path | None = None,
                         spec: AutonomousFactorCampaignSpecV1 | None = None) -> dict:
    spec = spec or AutonomousFactorCampaignSpecV1()
    payload = spec.payload()
    _, repository = _runtime(repository_root, work_root, store_root)
    receipt = repository.publish(
        "autonomous_factor_campaign_spec", payload,
        {"campaign_spec.json": payload},
        lineage=(SOURCE_DATASET_ID,),
    )
    # This verified Store lookup is deliberately before any Agent boundary.
    repository.find_spec(payload["campaign_spec_id"])
    return payload | {"store_receipt": receipt}


def _public_evaluation(value: dict) -> dict:
    return {key: item for key, item in value.items() if key != "values"}


def _research_goal(spec_id: str, plan: dict) -> ResearchGoal:
    return ResearchGoal(
        goal_id="afg1_" + hash_payload({"spec": spec_id, "round": plan["round_number"]}),
        name=plan["theme"],
        objective=(
            "Propose a simple PIT-safe technical factor structure. Higher values must exactly express "
            "the economic hypothesis. Explicit defaults are mandatory; no strategy controls."
        ),
        dataset_kind=DATASET_KIND,
        allowed_features=tuple(plan["allowed_features"]), allowed_operators=OPERATORS,
        allowed_parameter_roles=("lookback_window", "factor_internal_weight"),
        maximum_templates=2, maximum_trials=7, maximum_iterations=1,
        novelty_requirement="distinct canonical structure and development signal",
        constraints=(
            "one to three terminals; at least one price, momentum, trend, residual, drawdown, or recovery terminal",
            "at most two parameters and AST depth six", "explicit defaults must be in legal values",
            "no labels, report periods, Fresh Forward evidence, strategy settings, Promotion, financial data, or new terminals",
        ),
    )


def _agent_budget() -> ResearchCampaignBudget:
    return ResearchCampaignBudget(
        max_iterations=1, max_agent_calls=1, max_proposals_per_iteration=3,
        max_total_admitted_templates=2, max_total_trials=7, max_failed_proposals=3,
        max_failed_trials=7, max_agent_repair_attempts_per_call=0,
    )


def _state_identity(state: dict) -> dict:
    return {
        "schema_version": "autonomous-factor-campaign-state-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
        "state": state["state"], "checkpoint_sequence": state["checkpoint_sequence"],
        "budget_usage": state["budget_usage"], "round_artifact_ids": state["round_artifact_ids"],
        "candidate_lock_ids": state["candidate_lock_ids"], "near_miss_ids": state["near_miss_ids"],
        "memory_id": state.get("memory_id"), "report_id": state.get("report_id"),
        "known_fingerprints": state["known_fingerprints"], "memory": state["memory"],
        "eligible_candidate_refs": state["eligible_candidate_refs"],
        "manual_intervention_count": state["manual_intervention_count"],
        "manual_round_planning_count": state["manual_round_planning_count"],
        "stop_reason": state.get("stop_reason"), "promotion_writes": 0,
    }


def _checkpoint(repository: CampaignRepository, state: dict) -> dict:
    identity = _state_identity(state)
    receipt = repository.publish(
        "autonomous_factor_campaign", identity,
        {"campaign_state.json": identity, "budget_state.json": state["budget_usage"]},
        lineage=(state["campaign_spec_id"], *state["round_artifact_ids"], state.get("memory_id")),
    )
    state["checkpoint_artifact_id"] = receipt["artifact_id"]
    return state


def _initial_state(spec_id: str) -> dict:
    return {
        "campaign_spec_id": spec_id, "state": "planned", "checkpoint_sequence": 0,
        "budget_usage": empty_budget_usage(), "round_artifact_ids": [],
        "candidate_lock_ids": [], "near_miss_ids": [], "known_fingerprints": [],
        "eligible_candidate_refs": [],
        "memory": initial_memory(), "memory_id": None, "report_id": None,
        "stop_reason": None, "manual_intervention_count": 0,
        "manual_round_planning_count": 0,
    }


def _recover_interrupted_agent_round(repository: CampaignRepository, state: dict) -> None:
    """Close a post-Agent/pre-round checkpoint without repeating the external call."""
    usage = state["budget_usage"]
    if usage["agent_calls"] <= usage["rounds"]:
        if state.get("state") == "paused_recoverable_error" and "CodexProviderError" in str(state.get("stop_reason")):
            usage["agent_calls"] += 1
        else:
            return
    round_number = usage["rounds"] + 1
    plans = [
        row for row in repository.identities_by_kind("autonomous_factor_round_plan", state["campaign_spec_id"])
        if row.get("round_number") == round_number
    ]
    theme = plans[-1]["theme"] if plans else "cross_family_simple_hybrid"
    proposals = [
        row for row in repository.identities_by_kind("autonomous_factor_proposal", state["campaign_spec_id"])
        if row.get("round_number") == round_number and row.get("record_type") != "agent_response"
    ]
    failure_code = (
        "AGENT_DEFAULT_PARAMETERS_MISSING"
        if "AGENT_DEFAULT_PARAMETERS_MISSING" in str(state.get("stop_reason"))
        else ("agent_provider_failure" if "CodexProviderError" in str(state.get("stop_reason")) else "missing_feature")
    )
    identity = {
        "schema_version": "autonomous-factor-round-v1", "provider_id": "tushare-pro-v1",
        "campaign_spec_id": state["campaign_spec_id"], "round_number": round_number,
        "theme": theme, "round_plan_id": plans[-1]["artifact_id"] if plans else None,
        "agent_call": {"recovered_from_checkpoint": True, "call_repeated": False},
        "proposal_artifact_ids": [row["artifact_id"] for row in proposals],
        "proposal_count": len(proposals), "admitted_count": 0, "development_lock_count": 0,
        "structural_fingerprints": [], "failure_codes": [failure_code],
        "admission_failure_codes": [failure_code], "development_failure_codes": [],
        "annual_failure_codes": [], "evaluations": [],
        "selection_evidence_end": "2024-12-31", "report_period_feedback_used": False,
        "fresh_forward_evidence_used": False, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "network_data_calls": 0, "tushare_calls": 0,
        "promotion_writes": 0, "recovery_note": "Agent response preserved as Proposal Artifacts; invalid Terminal closed without re-call",
    }
    receipt = repository.publish(
        "autonomous_factor_round", identity, {"round.json": identity},
        lineage=(state["campaign_spec_id"], identity["round_plan_id"], *identity["proposal_artifact_ids"]),
    )
    state["round_artifact_ids"].append(receipt["artifact_id"])
    usage["rounds"] += 1
    state["memory"] = update_memory(state["memory"], identity, usage)
    memory_identity = dict(state["memory"]) | {
        "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
        "promotion_writes": 0,
    }
    memory_receipt = repository.publish(
        "autonomous_factor_failure_memory", memory_identity,
        {"failure_memory.json": memory_identity},
        lineage=(state["campaign_spec_id"], *state["round_artifact_ids"]),
    )
    state["memory_id"] = memory_receipt["artifact_id"]
    state["checkpoint_sequence"] += 1
    state["state"] = "running"
    state["stop_reason"] = None
    _checkpoint(repository, state)


def execute_campaign(*, campaign_id: str, repository_root: Path, work_root: Path,
                     store_root: Path | None = None, agent=None,
                     stop_after_round: int | None = None) -> dict:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.find_spec(campaign_id)
    state = repository.latest_state(campaign_id) or _initial_state(campaign_id)
    if state["state"] in TERMINAL_STATES:
        return replay_campaign(
            campaign_id=campaign_id, repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay", store_root=store_root,
        ) | {"exact_existing": True}
    _recover_interrupted_agent_round(repository, state)
    matrix, _ = _source_matrix(bundle, Path(work_root) / "source")
    contract = _snapshot_contract(
        SOURCE_DATASET_ID,
        [column for column in matrix.columns if column not in {"symbol", "trade_date", "raw_label", "model_label"}],
        matrix["trade_date"].nunique(),
    )
    evaluator = CampaignEvaluator(bundle=bundle, matrix=matrix, contract=contract, work_root=Path(work_root))
    for round_artifact_id in state["round_artifact_ids"]:
        recovered_round = repository.materialize(round_artifact_id)
        round_identity = json.loads((recovered_round / "manifest.json").read_text())["identity"]
        for row in round_identity.get("evaluations", []):
            relative = row.get("factor_values_file")
            factor_instance_id = (
                row.get("evaluation", {}).get("development_lock", {}) or {}
            ).get("factor_instance_id") or row.get("proposal", {}).get("factor_template_id")
            if relative and factor_instance_id and (recovered_round / relative).is_file():
                evaluator.known_values.append((factor_instance_id, pd.read_parquet(recovered_round / relative)))
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    budget = spec["budgets"]
    state["state"] = "running"
    _checkpoint(repository, state)
    try:
        while state["state"] == "running":
            pause_marker = Path(work_root) / "pause" / campaign_id
            if pause_marker.exists():
                state["state"] = "paused_recoverable_error"
                state["stop_reason"] = "manual_pause_requested"
                break
            reason = early_stop_reason(state["memory"], state["budget_usage"], budget)
            if reason:
                state["stop_reason"] = reason
                state["state"] = "paused_budget" if reason == "budget_exhausted" else "completed_early_stop"
                break
            round_number = state["budget_usage"]["rounds"] + 1
            plan = plan_next_round(state["memory"], round_number)
            if plan["status"] != "planned":
                state["memory"]["search_space_exhausted"] = True
                state["stop_reason"] = "search_space_exhausted"
                state["state"] = "completed_early_stop"
                break
            available = set(contract.feature_roles)
            plan["allowed_features"] = [
                name for name in plan["allowed_features"]
                if name in available and contract.feature_roles[name] == "feature"
            ]
            if not plan["allowed_features"]:
                state["memory"]["temporarily_frozen_families"] = sorted(
                    set(state["memory"].get("temporarily_frozen_families", [])) | {plan["theme"]}
                )
                continue
            plan_identity = {
                "schema_version": "autonomous-round-plan-v1", "provider_id": "tushare-pro-v1",
                "campaign_spec_id": campaign_id, **plan, "promotion_writes": 0,
            }
            plan_receipt = repository.publish(
                "autonomous_factor_round_plan", plan_identity, {"round_plan.json": plan_identity},
                lineage=(campaign_id, state.get("memory_id")),
            )
            goal, call_budget = _research_goal(campaign_id, plan), _agent_budget()
            request = _request(goal, state["memory"], call_budget, 1)
            state["budget_usage"]["agent_calls"] += 1
            state["checkpoint_sequence"] += 1
            _checkpoint(repository, state)
            response = agent.propose(request)
            response_hash = hashlib.sha256(response.raw_response.encode("utf-8")).hexdigest()
            response_identity = {
                "schema_version": "autonomous-factor-agent-response-v1",
                "record_type": "agent_response", "provider_id": "tushare-pro-v1",
                "campaign_spec_id": campaign_id, "round_number": round_number,
                "agent_provider": response.provider_id, "agent_model": response.model_id,
                "response_sha256": response_hash,
                "response_size_bytes": len(response.raw_response.encode("utf-8")),
                "usage_summary": response.usage_summary, "promotion_writes": 0,
            }
            response_receipt = repository.publish(
                "autonomous_factor_proposal", response_identity,
                {"agent_response.json": response.raw_response.encode("utf-8")},
                lineage=(campaign_id, plan_receipt["artifact_id"]),
            )
            decision = parse_decision(
                response.raw_response, iteration=1, goal=goal, budget=call_budget,
                provider_id=response.provider_id, model_id=response.model_id,
            )
            admitted_count = development_lock_count = 0
            failure_codes: list[str] = []
            admission_codes: list[str] = []
            development_codes: list[str] = []
            annual_codes: list[str] = []
            evaluations = []
            proposal_artifact_ids = []
            for source in decision["proposals"][:3]:
                state["budget_usage"]["proposals"] += 1
                enriched = dict(source) | {"_round_number": round_number, "_factor_family": plan["theme"]}
                admission = admit_proposal(
                    enriched, allowed_features=set(plan["allowed_features"]),
                    allowed_operators=set(OPERATORS),
                    known_fingerprints=set(state["known_fingerprints"]),
                )
                proposal_identity = {
                    "schema_version": "autonomous-factor-proposal-v1",
                    "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
                    "round_number": round_number, "source_response_sha256": response_hash,
                    "proposal": admission.get("proposal") or {"proposal_id": source.get("proposal_id")},
                    "admission": {key: value for key, value in admission.items() if key != "proposal"},
                    "promotion_writes": 0,
                }
                proposal_receipt = repository.publish(
                    "autonomous_factor_proposal", proposal_identity,
                    {"proposal.json": proposal_identity},
                    lineage=(campaign_id, plan_receipt["artifact_id"], response_receipt["artifact_id"]),
                )
                proposal_artifact_ids.append(proposal_receipt["artifact_id"])
                if not admission["admitted"] or admitted_count >= 2:
                    code = admission.get("failure_code") or "semantic_mismatch"
                    failure_codes.append(code)
                    admission_codes.append(code)
                    if code in {"duplicate_structure", "duplicate_signal"}:
                        state["budget_usage"]["duplicate_rejections"] += 1
                    continue
                admitted_count += 1
                state["budget_usage"]["admitted_templates"] += 1
                proposal = admission["proposal"]
                state["known_fingerprints"].append(proposal["structural_fingerprint"])
                reserved_report_calls = 2 * len(state["eligible_candidate_refs"])
                qlib_remaining = (
                    budget["maximum_formal_qlib_calls"]
                    - state["budget_usage"]["formal_qlib_calls"]
                    - reserved_report_calls
                )
                local_remaining = budget["maximum_local_rescue_trials"] - state["budget_usage"]["local_rescue_trials"]
                if qlib_remaining < 7:
                    failure_codes.append("campaign_qlib_budget_insufficient")
                    development_codes.append("campaign_qlib_budget_insufficient")
                    continue
                maximum_local_trials = min(6, local_remaining, qlib_remaining - 7)
                before_qlib = evaluator.qlib.calls
                evaluation = evaluator.evaluate(proposal, maximum_local_trials=maximum_local_trials)
                qlib_delta = evaluator.qlib.calls - before_qlib
                state["budget_usage"]["formal_qlib_calls"] += qlib_delta
                if qlib_delta:
                    state["budget_usage"]["default_evaluations"] += 1
                state["budget_usage"]["annual_evaluations"] += len(evaluation.get("annual", []))
                local_count = len(evaluation.get("local_trials", []))
                state["budget_usage"]["local_rescue_trials"] += local_count
                if evaluation.get("development_lock", {}).get("optimization_rescued"):
                    state["budget_usage"]["local_rescues"] += 1
                if evaluation["stage"] == "cheap_screen":
                    state["budget_usage"]["cheap_screen_rejections"] += 1
                if evaluation["stage"] == "signal_duplicate":
                    state["budget_usage"]["duplicate_rejections"] += 1
                failure_codes += evaluation["failure_codes"]
                if evaluation["stage"] == "development":
                    development_codes += evaluation["failure_codes"]
                elif evaluation["stage"] == "eligibility" and not evaluation["passed"]:
                    annual_codes += evaluation["failure_codes"]
                if evaluation.get("development_lock"):
                    development_lock_count += 1
                evaluations.append({"proposal": proposal, "evaluation": evaluation})
            public_evaluations = []
            round_files: dict[str, Any] = {}
            for index, row in enumerate(evaluations):
                relative = f"factor_values/{index:02d}-{row['proposal']['proposal_id']}.parquet"
                path = Path(work_root) / "round-values" / f"{round_number:04d}-{index:02d}.parquet"
                path.parent.mkdir(parents=True, exist_ok=True)
                row["evaluation"]["values"].to_parquet(path, index=False, compression="zstd", engine="pyarrow")
                round_files[relative] = path
                public_evaluations.append({
                    "proposal": row["proposal"], "evaluation": _public_evaluation(row["evaluation"]),
                    "factor_values_file": relative,
                })
            round_public = {
                "schema_version": "autonomous-factor-round-v1", "provider_id": "tushare-pro-v1",
                "campaign_spec_id": campaign_id, "round_number": round_number,
                "theme": plan["theme"], "round_plan_id": plan_receipt["artifact_id"],
                "agent_response_artifact_id": response_receipt["artifact_id"],
                "agent_call": {"provider": response.provider_id, "model": response.model_id,
                               "response_sha256": response_hash, "usage_summary": response.usage_summary},
                "proposal_artifact_ids": proposal_artifact_ids,
                "proposal_count": len(decision["proposals"]), "admitted_count": admitted_count,
                "development_lock_count": development_lock_count,
                "structural_fingerprints": [row["proposal"]["structural_fingerprint"] for row in evaluations],
                "failure_codes": failure_codes, "admission_failure_codes": admission_codes,
                "development_failure_codes": development_codes, "annual_failure_codes": annual_codes,
                "evaluations": public_evaluations,
                "selection_evidence_end": "2024-12-31",
                "report_period_feedback_used": False, "fresh_forward_evidence_used": False,
                "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
                "network_data_calls": 0, "tushare_calls": 0, "promotion_writes": 0,
            }
            round_receipt = repository.publish(
                "autonomous_factor_round", round_public, {"round.json": round_public} | round_files,
                lineage=(campaign_id, plan_receipt["artifact_id"], response_receipt["artifact_id"], *proposal_artifact_ids),
            )
            state["round_artifact_ids"].append(round_receipt["artifact_id"])
            state["budget_usage"]["rounds"] += 1
            state["memory"] = update_memory(state["memory"], round_public, state["budget_usage"])
            memory_identity = dict(state["memory"]) | {
                "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
                "promotion_writes": 0,
            }
            memory_receipt = repository.publish(
                "autonomous_factor_failure_memory", memory_identity,
                {"failure_memory.json": memory_identity},
                lineage=(campaign_id, *state["round_artifact_ids"]),
            )
            state["memory_id"] = memory_receipt["artifact_id"]
            eligible = [row for row in evaluations if row["evaluation"]["passed"]]
            for row in eligible:
                index = evaluations.index(row)
                reference = {"round_artifact_id": round_receipt["artifact_id"], "evaluation_index": index}
                if reference not in state["eligible_candidate_refs"]:
                    state["eligible_candidate_refs"].append(reference)
            state["budget_usage"]["eligible_candidates"] = len(state["eligible_candidate_refs"])
            near_candidates = [
                row for row in evaluations
                if not row["evaluation"]["passed"]
                and row["evaluation"]["stage"] in {"development", "eligibility"}
            ]
            for row in near_candidates:
                if state["budget_usage"]["near_miss_reports"] >= budget["maximum_near_miss_reports"]:
                    break
                evaluation, proposal = row["evaluation"], row["proposal"]
                failed = (
                    evaluation.get("summary", {}).get("gate_failure_reasons")
                    or evaluation.get("default_failure_reasons")
                    or evaluation["failure_codes"]
                )
                identity = {
                    "schema_version": "autonomous-factor-near-miss-v1",
                    "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
                    "round_id": round_receipt["artifact_id"], "proposal_id": proposal["proposal_id"],
                    "factor_template_id": proposal["factor_template_id"],
                    "failed_gates": failed,
                    "distance_to_gate": {
                        "mean_rank_ic": evaluation.get("cheap_screen", {}).get("metrics", {}).get("mean_rank_ic"),
                        "turnover": evaluation.get("default_qlib", {}).get("turnover"),
                    },
                    "strongest_evidence": evaluation.get("cheap_screen", {}).get("metrics", {}),
                    "largest_risk": failed[0] if failed else "unclassified",
                    "why_not_registered": "frozen Candidate eligibility was not fully satisfied",
                    "registry_write": False, "promotion_writes": 0,
                }
                receipt = repository.publish(
                    "autonomous_factor_near_miss", identity, {"near_miss.json": identity},
                    lineage=(campaign_id, round_receipt["artifact_id"], proposal["factor_template_id"]),
                )
                if receipt["artifact_id"] not in state["near_miss_ids"]:
                    state["near_miss_ids"].append(receipt["artifact_id"])
                    state["budget_usage"]["near_miss_reports"] += 1
            state["checkpoint_sequence"] += 1
            _checkpoint(repository, state)
            if stop_after_round and round_number >= stop_after_round:
                state["state"] = "paused_recoverable_error"
                state["stop_reason"] = "test_interrupt"
                break
        if state["state"] in {"running", "paused_budget"}:
            state["state"] = "completed_with_candidates" if state["eligible_candidate_refs"] else "completed_no_candidate"
            state["stop_reason"] = state["stop_reason"] or "legal_completion"
        if state["state"] in TERMINAL_STATES:
            terminal_reason_state = state["state"]
            _finalize_candidates(
                state=state, repository=repository, evaluator=evaluator,
                work_root=Path(work_root), budget=budget,
            )
            if terminal_reason_state != "completed_early_stop":
                state["state"] = "completed_with_candidates" if state["candidate_lock_ids"] else "completed_no_candidate"
            report = _build_report(state, repository)
            state["report_id"] = report["artifact_id"]
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
        return _result(state, repository)
    except Exception as exc:
        state["state"] = "paused_recoverable_error"
        state["stop_reason"] = f"{type(exc).__name__}:{str(exc)[:180]}"
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
        raise


def _candidate_ordering(row: dict) -> tuple:
    evaluation, proposal = row["evaluation"], row["proposal"]
    summary = evaluation["summary"]
    annual = evaluation["annual"]
    without_best = [
        item["qlib"].get("return_without_best_10_days")
        for item in annual if item["qlib"].get("return_without_best_10_days") is not None
    ]
    drawdowns = [
        abs(item["qlib"]["max_drawdown"])
        for item in annual if item["qlib"].get("max_drawdown") is not None
    ]
    return (
        -summary["positive_rankic_year_count"], -summary["positive_excess_year_count"],
        -summary["median_rankic"], -summary["worst_rankic"],
        -summary["median_excess"], -summary["worst_excess"],
        -int(evaluation["development_lock"]["optimization_mode"] == "default_parameters"),
        -(sum(without_best) / len(without_best) if without_best else -999.0),
        max(drawdowns) if drawdowns else 999.0, summary["median_turnover"],
        summary["maximum_old_factor_correlation"],
        proposal["complexity_statement"]["ast_depth"],
        evaluation["development_lock"]["factor_instance_id"],
    )


def _finalize_candidates(*, state: dict, repository: CampaignRepository,
                         evaluator: CampaignEvaluator, work_root: Path, budget: dict) -> None:
    if state["candidate_lock_ids"] or not state["eligible_candidate_refs"]:
        return
    rows = []
    for reference in state["eligible_candidate_refs"]:
        root = repository.materialize(reference["round_artifact_id"])
        identity = json.loads((root / "manifest.json").read_text())["identity"]
        row = identity["evaluations"][reference["evaluation_index"]]
        row["values"] = pd.read_parquet(root / row["factor_values_file"])
        row["round_artifact_id"] = reference["round_artifact_id"]
        rows.append(row)
    selected = sorted(rows, key=_candidate_ordering)[:budget["maximum_candidate_locks"]]
    for row in selected:
        evaluation, proposal, values = row["evaluation"], row["proposal"], row["values"]
        runtime_evaluation = dict(evaluation) | {"values": values}
        before = evaluator.qlib.calls
        reports = evaluator.report(runtime_evaluation)
        state["budget_usage"]["formal_qlib_calls"] += evaluator.qlib.calls - before
        factor_values_path = (
            work_root / "candidate-values"
            / f"{evaluation['development_lock']['factor_instance_id']}.parquet"
        )
        factor_values_path.parent.mkdir(parents=True, exist_ok=True)
        values.to_parquet(factor_values_path, index=False, compression="zstd", engine="pyarrow")
        factor_values_identity = {
            "schema_version": "autonomous-factor-value-materialization-v1",
            "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
            "factor_template_id": proposal["factor_template_id"],
            "factor_instance_id": evaluation["development_lock"]["factor_instance_id"],
            "dataset_id": SOURCE_DATASET_ID, "values_sha256": hash_file(factor_values_path),
            "row_count": len(values), "promotion_writes": 0,
        }
        factor_values_receipt = repository.publish(
            "autonomous_factor_value_materialization", factor_values_identity,
            {"factor_values.parquet": factor_values_path},
            lineage=(state["campaign_spec_id"], row["round_artifact_id"], proposal["factor_template_id"]),
        )
        lock_identity = {
            "schema_version": "autonomous-factor-candidate-lock-v1",
            "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
            "proposal_id": proposal["proposal_id"], "round_id": row["round_artifact_id"],
            "factor_template_id": proposal["factor_template_id"],
            "factor_instance_id": evaluation["development_lock"]["factor_instance_id"],
            "factor_family": proposal["factor_family"],
            "economic_hypothesis": proposal["economic_hypothesis"],
            "canonical_dsl": proposal["canonical_dsl"], "canonical_ast": proposal["canonical_ast"],
            "input_features": proposal["input_features"],
            "agent_default_parameters": proposal["default_parameters"],
            "selected_parameters": evaluation["development_lock"]["selected_parameters"],
            "optimization_mode": evaluation["development_lock"]["optimization_mode"],
            "optimization_rescued": evaluation["development_lock"]["optimization_rescued"],
            "development_metrics": evaluation["development_lock"]["development_metrics"],
            "annual_2021_2024_metrics": evaluation["annual"],
            "orientation": evaluation["development_lock"]["orientation"],
            "factor_value_artifact_id": factor_values_receipt["artifact_id"],
            "unified_signal_id": "research_signal_" + evaluation["development_lock"]["factor_instance_id"],
            "turnover": evaluation["summary"]["median_turnover"],
            "cost": [annual["qlib"].get("transaction_cost") for annual in evaluation["annual"]],
            "concentration": evaluation["summary"]["median_best10_contribution"],
            "correlation_matrix": evaluation["signal_correlations"],
            "structural_fingerprint": proposal["structural_fingerprint"],
            "failure_memory_context": state["memory_id"], "status": "research_registered",
            "contaminated_report_periods": reports, "report_periods_used_for_selection": False,
            "predictive_claim": False, "fresh_validation": False,
            "usable_for_production": False, "promotion_writes": 0,
        }
        receipt = repository.publish(
            "autonomous_factor_candidate_lock", lock_identity,
            {"candidate_lock.json": lock_identity},
            lineage=(state["campaign_spec_id"], row["round_artifact_id"], state["memory_id"],
                     factor_values_receipt["artifact_id"]),
        )
        state["candidate_lock_ids"].append(receipt["artifact_id"])
    state["budget_usage"]["candidate_locks"] = len(state["candidate_lock_ids"])


def _build_report(state: dict, repository: CampaignRepository) -> dict:
    usage = state["budget_usage"]
    proposals = usage["proposals"]
    identity = {
        "schema_version": "autonomous-factor-campaign-report-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
        "terminal_state": state["state"], "stop_reason": state["stop_reason"],
        "candidate_lock_ids": state["candidate_lock_ids"], "near_miss_ids": state["near_miss_ids"],
        "round_artifact_ids": state["round_artifact_ids"], "failure_memory_id": state["memory_id"],
        "budget_usage": usage, "research_efficiency": {
            "agent_calls": usage["agent_calls"],
            "proposals_per_agent_call": proposals / max(1, usage["agent_calls"]),
            "admission_rate": usage["admitted_templates"] / max(1, proposals),
            "duplicate_rejection_rate": usage["duplicate_rejections"] / max(1, proposals),
            "cheap_screen_rejection_rate": usage["cheap_screen_rejections"] / max(1, usage["admitted_templates"]),
            "development_lock_rate": (
                max(0, usage["admitted_templates"] - state["memory"].get("repeated_failures", {}).get("weak_predictive_signal", 0))
                / max(1, usage["admitted_templates"])
            ),
            "local_rescue_rate": usage["local_rescues"] / max(1, usage["admitted_templates"]),
            "annual_evaluation_rate": usage["annual_evaluations"] / max(1, usage["admitted_templates"] * 4),
            "candidate_lock_rate": usage["candidate_locks"] / max(1, usage["admitted_templates"]),
            "qlib_calls_per_candidate": usage["formal_qlib_calls"] / max(1, usage["candidate_locks"]),
            "artifact_cache_hit_rate": 0.0, "replay_cache_hit_rate": 1.0,
            "manual_intervention_count": 0, "manual_round_planning_count": 0,
        },
        "selection_data_end": "2024-12-31", "report_period_used_for_selection": False,
        "fresh_forward_evidence_used": False, "predictive_claim": False,
        "fresh_validation": False, "frozen_test": False, "usable_for_production": False,
        "promotion_writes": 0,
    }
    return repository.publish(
        "autonomous_factor_campaign_report", identity, {"campaign_report.json": identity},
        lineage=(state["campaign_spec_id"], *state["round_artifact_ids"],
                 *state["candidate_lock_ids"], *state["near_miss_ids"], state["memory_id"]),
    )


def _result(state: dict, repository: CampaignRepository) -> dict:
    return {
        "status": state["state"], "campaign_spec_id": state["campaign_spec_id"],
        "checkpoint_artifact_id": state["checkpoint_artifact_id"],
        "report_id": state.get("report_id"), "candidate_lock_ids": state["candidate_lock_ids"],
        "near_miss_ids": state["near_miss_ids"], "budget_usage": state["budget_usage"],
        "stop_reason": state["stop_reason"], "manual_intervention_count": 0,
        "manual_round_planning_count": 0, "store_integrity": repository.integrity(),
    }


def resume_campaign(**kwargs) -> dict:
    marker = Path(kwargs["work_root"]) / "pause" / kwargs["campaign_id"]
    marker.unlink(missing_ok=True)
    return execute_campaign(**kwargs)


def inspect_campaign(*, campaign_id: str, repository_root: Path, work_root: Path,
                     store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    repository.find_spec(campaign_id)
    state = repository.latest_state(campaign_id)
    if state is None:
        return _initial_state(campaign_id)
    return state


def validate_campaign(*, campaign_id: str, repository_root: Path, work_root: Path,
                      store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.find_spec(campaign_id)
    state = repository.latest_state(campaign_id)
    if state is None:
        raise ValueError("Campaign has no checkpoint")
    if state["state"] not in CAMPAIGN_STATES:
        raise ValueError("Campaign state invalid")
    if state["budget_usage"]["strategy_optimization_calls"] or state["budget_usage"]["combined_optimization_calls"]:
        raise ValueError("forbidden optimization call recorded")
    if state["budget_usage"]["tushare_calls"] or state["budget_usage"]["network_data_calls"]:
        raise ValueError("market data network call recorded")
    if state["budget_usage"]["promotion_writes"]:
        raise ValueError("Promotion write recorded")
    required = [
        *state["round_artifact_ids"], *state["candidate_lock_ids"], *state["near_miss_ids"],
        state.get("memory_id"), state.get("report_id"),
    ]
    for artifact_id in [item for item in required if item]:
        identity = repository.identity(artifact_id)
        if artifact_id in state["round_artifact_ids"]:
            for reference in (
                identity.get("round_plan_id"), identity.get("agent_response_artifact_id"),
                *identity.get("proposal_artifact_ids", []),
            ):
                if reference:
                    repository.identity(reference)
        if artifact_id in state["candidate_lock_ids"]:
            repository.identity(identity["factor_value_artifact_id"])
    return {"status": "valid", "campaign_spec_id": spec["campaign_spec_id"],
            "campaign_state": state["state"], "evidence_gap_count": 0,
            "store_integrity": repository.integrity()}


def replay_campaign(*, campaign_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None) -> dict:
    validation = validate_campaign(
        campaign_id=campaign_id, repository_root=repository_root,
        work_root=work_root, store_root=store_root,
    )
    state = inspect_campaign(
        campaign_id=campaign_id, repository_root=repository_root,
        work_root=Path(work_root) / "inspect", store_root=store_root,
    )
    return validation | {
        "campaign_state": state["state"], "agent_calls": 0,
        "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "qlib_calls": 0, "network_calls": 0,
        "tushare_calls": 0, "new_artifacts": 0, "new_blobs": 0,
        "registry_writes": 0, "promotion_writes": 0, "replay_cache_hit_rate": 1.0,
    }
