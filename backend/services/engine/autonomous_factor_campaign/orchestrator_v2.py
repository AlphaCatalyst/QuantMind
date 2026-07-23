from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import DATASET_KIND, OPERATORS, SOURCE_DATASET_ID
from backend.services.engine.momentum_factor_iteration.engine import _snapshot_contract
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.orchestrator import _request
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

from .admission import admit_proposal
from .evaluation import CampaignEvaluator
from .evaluation_v2 import DISCOVERY_PERIODS, evaluate_holdout, evaluate_reports
from .failure_memory import initial_memory, update_memory
from .models_v2 import (
    V2_STATES, V2_TERMINAL_STATES, AutonomousFactorCampaignSpecV2,
    empty_budget_usage_v2, evidence_partitions,
)
from .orchestrator import _agent_budget, _research_goal, _runtime
from .planner_v2 import early_stop_reason_v2, plan_next_round_v2


V1_SPEC_ID = "afc1_5bae780edd8024e08220196a07d38c321ec6851204b16c30d75af92ac3fa8034"
V1_REPORT_ID = "afcr1_e5eea677f1dc1b953740c740a4acd40d5c4d4d7c151680370c138ae77e8460f4"


class LockedHoldoutAccessControllerV1:
    def __init__(self, state: dict):
        self.state = state

    def open(self) -> None:
        required = (
            self.state.get("rounds_stopped"),
            self.state.get("shortlist_lock_id"),
            self.state.get("memory_freeze_id"),
            self.state.get("agent_closed"),
            self.state.get("planner_closed"),
            self.state.get("parameters_frozen"),
        )
        if not all(required):
            raise ValueError("LOCKED_HOLDOUT_EVIDENCE_CONTAMINATION")
        if self.state["budget_usage"]["locked_holdout_reads"] != 0:
            raise ValueError("LOCKED_HOLDOUT_ALREADY_OPENED")
        self.state["holdout_opened"] = True


def _publish_contracts(repository, campaign_id: str) -> tuple[str, str, str]:
    partition = evidence_partitions() | {"campaign_spec_id": campaign_id}
    partition_receipt = repository.publish(
        "campaign_evidence_partition", partition,
        {"evidence_partitions.json": partition}, lineage=(campaign_id,),
    )
    seed = {
        "schema_version": "clean-room-campaign-seed-memory-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
        "allowed_sources": {
            "structure_fingerprints": True, "family_names": True,
            "operator_feature_statistics": True, "aggregate_2019_2022_failures": True,
        },
        "forbidden_sources": {
            "metrics_2023": True, "metrics_2024": True, "metrics_2025": True,
            "metrics_2026": True, "v1_candidate_status_or_ranking": True,
            "fresh_forward_results": True,
        },
        "seeded_families": [
            "drawdown_recovery", "residual_relative_strength", "momentum_acceleration",
            "path_quality", "multi_horizon_trend", "pullback_continuation",
        ],
        "selection_evidence_end": "2022-12-30", "promotion_writes": 0,
    }
    seed_receipt = repository.publish(
        "clean_room_campaign_seed_memory", seed,
        {"clean_room_seed_memory.json": seed}, lineage=(campaign_id, partition_receipt["artifact_id"]),
    )
    assessment = {
        "schema_version": "autonomous-campaign-v1-generalization-assessment-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
        "assessed_campaign_spec_id": V1_SPEC_ID, "assessed_campaign_report_id": V1_REPORT_ID,
        "v1_candidate_creation_valid": True, "v1_fresh_or_predictive_validation": False,
        "report_period_degradation": True,
        "candidate_semantics": "research_registered/retrospective_v1_candidate",
        "usable_by_v2_agent": False, "usable_by_v2_planner": False,
        "usable_by_v2_failure_memory": False, "promotion_writes": 0,
    }
    assessment_receipt = repository.publish(
        "autonomous_campaign_v1_generalization_assessment", assessment,
        {"v1_generalization_assessment.json": assessment}, lineage=(campaign_id, V1_SPEC_ID, V1_REPORT_ID),
    )
    return (
        partition_receipt["artifact_id"], seed_receipt["artifact_id"],
        assessment_receipt["artifact_id"],
    )


def create_campaign_spec_v2(*, repository_root: Path, work_root: Path,
                            store_root: Path | None = None,
                            spec: AutonomousFactorCampaignSpecV2 | None = None) -> dict:
    payload = (spec or AutonomousFactorCampaignSpecV2()).payload()
    _, repository = _runtime(repository_root, work_root, store_root)
    receipt = repository.publish(
        "autonomous_factor_campaign_spec_v2", payload,
        {"campaign_spec_v2.json": payload}, lineage=(SOURCE_DATASET_ID,),
    )
    repository.find_spec_v2(payload["campaign_spec_id"])
    partition_id, seed_id, assessment_id = _publish_contracts(repository, payload["campaign_spec_id"])
    return payload | {
        "store_receipt": receipt, "evidence_partition_id": partition_id,
        "clean_room_seed_memory_id": seed_id, "v1_assessment_id": assessment_id,
    }


def _initial_state(spec_id: str, repository) -> dict:
    partitions = repository.identities_by_kind("campaign_evidence_partition", spec_id)
    seeds = repository.identities_by_kind("clean_room_campaign_seed_memory", spec_id)
    assessments = repository.identities_by_kind("autonomous_campaign_v1_generalization_assessment", spec_id)
    return {
        "campaign_spec_id": spec_id, "campaign_version": 2, "state": "planned",
        "checkpoint_sequence": 0, "budget_usage": empty_budget_usage_v2(),
        "round_artifact_ids": [], "known_fingerprints": [], "discovery_candidate_refs": [],
        "search_exposure_ids": [], "holdout_evaluation_ids": [], "holdout_failure_ids": [],
        "candidate_lock_ids": [], "fresh_lock_ids": [], "near_miss_ids": [],
        "memory": initial_memory(), "memory_id": None, "memory_freeze_id": None,
        "shortlist_lock_id": None, "report_id": None,
        "evidence_partition_id": partitions[-1]["artifact_id"],
        "clean_room_seed_memory_id": seeds[-1]["artifact_id"],
        "v1_assessment_id": assessments[-1]["artifact_id"],
        "rounds_stopped": False, "agent_closed": False, "planner_closed": False,
        "parameters_frozen": False, "holdout_opened": False,
        "holdout_opened_at": None, "stop_reason": None,
        "manual_intervention_count": 0, "manual_round_planning_count": 0,
    }


def _checkpoint(repository, state: dict) -> None:
    identity = {
        "schema_version": "autonomous-factor-campaign-state-v2",
        "provider_id": "tushare-pro-v1", **state, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "autonomous_factor_campaign", identity,
        {"campaign_state.json": identity, "budget_state.json": state["budget_usage"]},
        lineage=tuple(
            item for item in (
                state["campaign_spec_id"], state.get("evidence_partition_id"),
                state.get("clean_room_seed_memory_id"), *state["round_artifact_ids"],
                state.get("memory_id"), state.get("memory_freeze_id"),
                state.get("shortlist_lock_id"), *state["holdout_evaluation_ids"],
                *state["candidate_lock_ids"], *state["fresh_lock_ids"], state.get("report_id"),
            ) if item
        ),
    )
    state["checkpoint_artifact_id"] = receipt["artifact_id"]


def _public(value: dict) -> dict:
    return {key: item for key, item in value.items() if key != "values"}


def _exposure(state: dict, proposal: dict) -> dict:
    usage = state["budget_usage"]
    family_count = state["memory"].get("families_attempted", []).count(proposal["factor_family"])
    candidate_count = (
        usage["proposals"] + usage["admitted_templates"] + usage["local_rescue_trials"]
    )
    risk = "low_search_exposure" if candidate_count <= 10 else (
        "medium_search_exposure" if candidate_count <= 25 else "high_search_exposure"
    )
    return {
        "schema_version": "candidate-search-exposure-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
        "factor_template_id": proposal["factor_template_id"],
        "campaign_agent_calls_before_candidate": usage["agent_calls"],
        "campaign_proposals_before_candidate": usage["proposals"],
        "admitted_templates_before_candidate": usage["admitted_templates"],
        "default_trials_before_candidate": usage["default_evaluations"],
        "local_rescue_trials_before_candidate": usage["local_rescue_trials"],
        "development_locks_before_candidate": usage["development_locks"],
        "discovery_candidates_before_candidate": usage["discovery_candidates"],
        "family_attempt_count": family_count,
        "structural_neighbors_attempted": usage["proposals"],
        "signal_neighbors_attempted": usage["admitted_templates"],
        "candidate_effective_search_count": candidate_count,
        "campaign_effective_search_count": candidate_count,
        "search_risk_class": risk, "promotion_writes": 0,
    }


def _ordering(row: dict) -> tuple:
    evaluation, proposal, exposure = row["evaluation"], row["proposal"], row["search_exposure"]
    summary = evaluation["summary"]
    risk = {"low_search_exposure": 0, "medium_search_exposure": 1, "high_search_exposure": 2}
    return (
        -summary["positive_rankic_year_count"], -summary["positive_excess_year_count"],
        -summary["median_rankic"], -summary["median_excess"],
        -int(evaluation["development_lock"]["optimization_mode"] == "default_parameters"),
        risk[exposure["search_risk_class"]],
        proposal["complexity_statement"]["ast_depth"],
        summary["maximum_old_factor_correlation"],
        evaluation["development_lock"]["factor_instance_id"],
    )


def _load_discovery_rows(repository, state: dict) -> list[dict]:
    rows = []
    exposure_by_template = {
        item["factor_template_id"]: item
        for item in repository.identities_by_kind("candidate_search_exposure", state["campaign_spec_id"])
    }
    for reference in state["discovery_candidate_refs"]:
        root = repository.materialize(reference["round_artifact_id"])
        identity = json.loads((root / "manifest.json").read_text())["identity"]
        row = identity["evaluations"][reference["evaluation_index"]]
        row["values"] = pd.read_parquet(root / row["factor_values_file"])
        row["round_artifact_id"] = reference["round_artifact_id"]
        row["search_exposure"] = exposure_by_template[row["proposal"]["factor_template_id"]]
        rows.append(row)
    return rows


def _freeze_and_lock(repository, state: dict, budget: dict) -> list[dict]:
    if state.get("shortlist_lock_id"):
        lock = repository.identity(state["shortlist_lock_id"])
        rows = _load_discovery_rows(repository, state)
        wanted = {item["factor_instance_id"] for item in lock["shortlist"]}
        return [row for row in rows if row["evaluation"]["development_lock"]["factor_instance_id"] in wanted]
    freeze = {
        "schema_version": "campaign-failure-memory-freeze-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
        "failure_memory_id": state["memory_id"], "rounds_stopped": True,
        "frozen_before_holdout": True, "append_allowed": False, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "campaign_failure_memory_freeze", freeze,
        {"failure_memory_freeze.json": freeze},
        lineage=(state["campaign_spec_id"], state["memory_id"]),
    )
    state["memory_freeze_id"] = receipt["artifact_id"]
    state["state"] = "memory_frozen"
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    rows = sorted(_load_discovery_rows(repository, state), key=_ordering)[
        :budget["maximum_discovery_shortlist"]
    ]
    shortlist = []
    for rank, row in enumerate(rows, 1):
        evaluation, proposal = row["evaluation"], row["proposal"]
        shortlist.append({
            "discovery_ranking": rank,
            "factor_template_id": proposal["factor_template_id"],
            "factor_instance_id": evaluation["development_lock"]["factor_instance_id"],
            "template": proposal["template"],
            "canonical_dsl": proposal["canonical_dsl"], "canonical_ast": proposal["canonical_ast"],
            "orientation": evaluation["development_lock"]["orientation"],
            "default_parameters": proposal["default_parameters"],
            "selected_parameters": evaluation["development_lock"]["selected_parameters"],
            "optimization_rescued": evaluation["development_lock"]["optimization_rescued"],
            "development_metrics": evaluation["development_lock"]["development_metrics"],
            "discovery_metrics": evaluation["annual"],
            "discovery_summary": evaluation["summary"],
            "search_exposure": row["search_exposure"],
            "correlations": evaluation["signal_correlations"],
            "structural_fingerprint": proposal["structural_fingerprint"],
            "round_artifact_id": row["round_artifact_id"],
        })
    lock = {
        "schema_version": "autonomous-campaign-shortlist-lock-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
        "campaign_terminal_state_before_holdout": "rounds_stopped",
        "locked_holdout_reads_before_publish": state["budget_usage"]["locked_holdout_reads"],
        "failure_memory_freeze_id": state["memory_freeze_id"],
        "shortlist": shortlist, "shortlist_count": len(shortlist),
        "parameters_frozen": True, "orientation_frozen": True,
        "ranking_frozen": True, "promotion_writes": 0,
    }
    lock_receipt = repository.publish(
        "autonomous_campaign_shortlist_lock", lock, {"shortlist_lock.json": lock},
        lineage=(state["campaign_spec_id"], state["memory_freeze_id"],
                 *(row["round_artifact_id"] for row in rows)),
    )
    state["shortlist_lock_id"] = lock_receipt["artifact_id"]
    state["budget_usage"]["discovery_shortlist"] = len(rows)
    state["parameters_frozen"] = True
    state["state"] = "shortlist_locked"
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    return rows


def _latest_trade_date_and_fresh_start(bundle, matrix: pd.DataFrame) -> tuple[str, str]:
    latest = pd.Timestamp(matrix["trade_date"].max()).strftime("%Y-%m-%d")
    calendar = Path(bundle.qlib_view) / "calendars" / "day.txt"
    dates = [line.strip()[:10] for line in calendar.read_text().splitlines() if line.strip()]
    future = next((date for date in dates if date > latest), None)
    if future is None:
        raise ValueError("formal Qlib calendar has no trade date after latest market data")
    return latest, future


def _open_holdout_and_finalize(repository, state: dict, bundle, full_matrix: pd.DataFrame,
                               contract, work_root: Path, budget: dict) -> None:
    shortlist_lock = repository.identity(state["shortlist_lock_id"])
    if not shortlist_lock["shortlist"]:
        state["state"] = "completed_no_discovery_shortlist"
        return
    controller = LockedHoldoutAccessControllerV1(state)
    controller.open()
    state["state"] = "holdout_open"
    state["holdout_opened_at"] = pd.Timestamp.utcnow().isoformat()
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    evaluator = CampaignEvaluator(bundle=bundle, matrix=full_matrix, contract=contract, work_root=work_root / "holdout")
    survivors = []
    for locked in shortlist_lock["shortlist"]:
        existing = [
            item for item in repository.identities_by_kind("locked_holdout_evaluation", state["campaign_spec_id"])
            if item["factor_instance_id"] == locked["factor_instance_id"]
        ]
        if existing:
            result = existing[-1]
        else:
            proposal = {
                "template": locked["template"], "factor_template_id": locked["factor_template_id"],
            }
            development_lock = {
                "factor_instance_id": locked["factor_instance_id"],
                "selected_parameters": locked["selected_parameters"],
                "orientation": locked["orientation"],
                "discovery_summary": locked["discovery_summary"],
            }
            before = evaluator.qlib.calls
            runtime = evaluate_holdout(
                evaluator, proposal, development_lock,
                expected_parameters=locked["selected_parameters"],
                expected_orientation=locked["orientation"],
            )
            delta = evaluator.qlib.calls - before
            state["budget_usage"]["holdout_qlib_calls"] += delta
            state["budget_usage"]["locked_holdout_reads"] += delta
            result = _public(runtime) | {
                "schema_version": "locked-holdout-evaluation-v1",
                "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
                "shortlist_lock_id": state["shortlist_lock_id"],
                "discovery_ranking": locked["discovery_ranking"],
                "parameters_unchanged": True, "orientation_unchanged": True,
                "feedback_to_agent": False, "feedback_to_planner": False,
                "feedback_to_failure_memory": False, "promotion_writes": 0,
            }
            receipt = repository.publish(
                "locked_holdout_evaluation", result, {"holdout_evaluation.json": result},
                lineage=(state["campaign_spec_id"], state["shortlist_lock_id"],
                         state["memory_freeze_id"], locked["factor_instance_id"]),
            )
            result["artifact_id"] = receipt["artifact_id"]
            state["holdout_evaluation_ids"].append(receipt["artifact_id"])
            state["checkpoint_sequence"] += 1
            _checkpoint(repository, state)
        if result["passed"]:
            survivors.append((locked, result))
        else:
            failure = {
                "schema_version": "autonomous-holdout-failure-report-v1",
                "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
                "shortlist_lock_id": state["shortlist_lock_id"],
                "factor_instance_id": locked["factor_instance_id"],
                "failed_gates": result["failed_gates"],
                "discovery_metrics": locked["discovery_metrics"],
                "holdout_metrics": result["annual"],
                "generalization_gap": {
                    "rankic": result["summary"]["median_rankic"] - locked["discovery_summary"]["median_rankic"],
                    "excess": result["summary"]["median_excess"] - locked["discovery_summary"]["median_excess"],
                },
                "search_exposure": locked["search_exposure"],
                "optimization_rescued": locked["optimization_rescued"],
                "parameter_stability": True,
                "largest_risk": result["failed_gates"][0],
                "failed_locked_holdout": True, "registry_write": False, "promotion_writes": 0,
            }
            receipt = repository.publish(
                "autonomous_holdout_failure_report", failure,
                {"holdout_failure.json": failure},
                lineage=(state["campaign_spec_id"], result["artifact_id"]),
            )
            state["holdout_failure_ids"].append(receipt["artifact_id"])
    # Capacity ordering remains the already frozen Discovery order.
    survivors = sorted(survivors, key=lambda pair: pair[0]["discovery_ranking"])[
        :budget["maximum_final_candidate_locks"]
    ]
    for locked, result in survivors:
        from backend.services.engine.factor_dsl import parse_template
        from backend.services.engine.tushare_agent_experiment.evaluation import factor_values
        compiled, values = factor_values(
            parse_template(locked["template"]), contract,
            locked["selected_parameters"], full_matrix,
        )
        value_path = work_root / "candidate-values" / f"{compiled.factor_instance_id}.parquet"
        value_path.parent.mkdir(parents=True, exist_ok=True)
        values.to_parquet(value_path, index=False, compression="zstd", engine="pyarrow")
        value_identity = {
            "schema_version": "autonomous-factor-value-materialization-v2",
            "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
            "factor_template_id": locked["factor_template_id"],
            "factor_instance_id": compiled.factor_instance_id,
            "dataset_id": SOURCE_DATASET_ID, "values_sha256": hash_file(value_path),
            "row_count": len(values), "promotion_writes": 0,
        }
        value_receipt = repository.publish(
            "autonomous_factor_value_materialization", value_identity,
            {"factor_values.parquet": value_path},
            lineage=(state["campaign_spec_id"], result["artifact_id"]),
        )
        before = evaluator.qlib.calls
        reports = evaluate_reports(evaluator, values, compiled.factor_instance_id, locked["orientation"])
        state["budget_usage"]["report_qlib_calls"] += evaluator.qlib.calls - before
        lock = {
            "schema_version": "autonomous-factor-candidate-lock-v2",
            "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
            "campaign_version": 2, "factor_template_id": locked["factor_template_id"],
            "factor_instance_id": compiled.factor_instance_id,
            "canonical_dsl": locked["canonical_dsl"], "canonical_ast": locked["canonical_ast"],
            "selected_parameters": locked["selected_parameters"],
            "orientation": locked["orientation"], "status": "research_registered",
            "discovery_shortlist_lock_id": state["shortlist_lock_id"],
            "locked_holdout_passed": True,
            "holdout_evaluation_id": result["artifact_id"],
            "search_risk_class": locked["search_exposure"]["search_risk_class"],
            "not_fresh_validated": True, "retrospective_v1_candidate": False,
            "factor_value_artifact_id": value_receipt["artifact_id"],
            "contaminated_report_periods": reports,
            "report_periods_used_for_selection": False, "predictive_claim": False,
            "fresh_validation": False, "usable_for_production": False, "promotion_writes": 0,
        }
        receipt = repository.publish(
            "autonomous_factor_candidate_lock", lock, {"candidate_lock.json": lock},
            lineage=(state["campaign_spec_id"], state["shortlist_lock_id"],
                     result["artifact_id"], value_receipt["artifact_id"]),
        )
        state["candidate_lock_ids"].append(receipt["artifact_id"])
        latest, fresh_start = _latest_trade_date_and_fresh_start(bundle, full_matrix)
        fresh = {
            "schema_version": "autonomous-candidate-fresh-lock-v1",
            "provider_id": "tushare-pro-v1", "campaign_spec_id": state["campaign_spec_id"],
            "candidate_id": receipt["artifact_id"], "shortlist_lock_id": state["shortlist_lock_id"],
            "signal_definition": locked["canonical_dsl"],
            "parameters": locked["selected_parameters"], "orientation": locked["orientation"],
            "strategy_protocol": {
                "topk": 20, "n_drop": 5, "rebalance_interval": 10,
                "weighting": "equal_weight", "signal_lag": 1, "execution": "open",
            },
            "universe_id": "Tushare Fixed-100", "benchmark": "CSI300",
            "latest_market_data_date_used": latest, "fresh_start_date": fresh_start,
            "no_backfill": True,
            "minimum_evidence_policy": {
                "fresh_trading_days": 60, "completed_holding_windows": 5,
                "independent_rebalance_cycles": 3,
            },
            "status": "locked_awaiting_fresh_data", "promotion_writes": 0,
        }
        fresh_receipt = repository.publish(
            "autonomous_candidate_fresh_lock", fresh, {"fresh_lock.json": fresh},
            lineage=(state["campaign_spec_id"], receipt["artifact_id"], state["shortlist_lock_id"]),
        )
        state["fresh_lock_ids"].append(fresh_receipt["artifact_id"])
    state["budget_usage"]["final_candidate_locks"] = len(state["candidate_lock_ids"])
    state["state"] = (
        "completed_with_holdout_survivors" if state["candidate_lock_ids"]
        else "completed_no_holdout_survivor"
    )


def execute_campaign_v2(*, campaign_id: str, repository_root: Path, work_root: Path,
                        store_root: Path | None = None, agent=None,
                        stop_after_round: int | None = None) -> dict:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.find_spec_v2(campaign_id)
    state = repository.latest_state(campaign_id) or _initial_state(campaign_id, repository)
    if state["state"] in V2_TERMINAL_STATES:
        return replay_campaign_v2(
            campaign_id=campaign_id, repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay", store_root=store_root,
        ) | {"exact_existing": True}
    full_matrix, _ = _source_matrix(bundle, Path(work_root) / "source")
    feature_names = [c for c in full_matrix if c not in {"symbol", "trade_date", "raw_label", "model_label"}]
    contract = _snapshot_contract(SOURCE_DATASET_ID, feature_names, full_matrix["trade_date"].nunique())
    discovery_matrix = full_matrix[full_matrix["trade_date"] <= "2022-12-30"].copy()
    if pd.Timestamp(discovery_matrix["trade_date"].max()).strftime("%Y-%m-%d") != "2022-12-30":
        raise ValueError("adaptive Discovery physical cutoff is incomplete")
    evaluator = CampaignEvaluator(
        bundle=bundle, matrix=discovery_matrix, contract=contract,
        work_root=Path(work_root) / "discovery",
    )
    evaluator.known_values = [
        (name, values[values["trade_date"] <= "2022-12-30"].copy())
        for name, values in evaluator.known_values
    ]
    for round_id in state["round_artifact_ids"]:
        root = repository.materialize(round_id)
        identity = json.loads((root / "manifest.json").read_text())["identity"]
        for row in identity.get("evaluations", []):
            if row.get("factor_values_file"):
                evaluator.known_values.append((
                    row["evaluation"]["development_lock"]["factor_instance_id"],
                    pd.read_parquet(root / row["factor_values_file"]),
                ))
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    budget = spec["budgets"]
    state["state"] = "running"
    _checkpoint(repository, state)
    while state["state"] == "running":
        reason = early_stop_reason_v2(state["memory"], state["budget_usage"], budget)
        if reason:
            state["stop_reason"] = reason
            break
        round_number = state["budget_usage"]["rounds"] + 1
        plan = plan_next_round_v2(state["memory"], round_number)
        if plan["status"] != "planned":
            state["stop_reason"] = "search_space_exhausted"
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
            "schema_version": "autonomous-round-plan-v2", "provider_id": "tushare-pro-v1",
            "campaign_spec_id": campaign_id, **plan, "promotion_writes": 0,
        }
        plan_receipt = repository.publish(
            "autonomous_factor_round_plan", plan_identity, {"round_plan.json": plan_identity},
            lineage=(campaign_id, state.get("memory_id"), state["evidence_partition_id"]),
        )
        goal, call_budget = _research_goal(campaign_id, plan), _agent_budget()
        request_memory = {
            key: value for key, value in state["memory"].items()
            if not any(year in key.lower() for year in ("2023", "2024", "2025", "2026", "fresh"))
        }
        request = _request(goal, request_memory, call_budget, 1)
        state["budget_usage"]["agent_calls"] += 1
        response = agent.propose(request)
        response_hash = hashlib.sha256(response.raw_response.encode()).hexdigest()
        response_identity = {
            "schema_version": "autonomous-factor-agent-response-v2",
            "record_type": "agent_response", "provider_id": "tushare-pro-v1",
            "campaign_spec_id": campaign_id, "round_number": round_number,
            "agent_provider": response.provider_id, "agent_model": response.model_id,
            "response_sha256": response_hash, "usage_summary": response.usage_summary,
            "evidence_partitions": ["development", "adaptive_discovery"],
            "promotion_writes": 0,
        }
        response_receipt = repository.publish(
            "autonomous_factor_proposal", response_identity,
            {"agent_response.json": response.raw_response.encode()},
            lineage=(campaign_id, plan_receipt["artifact_id"]),
        )
        decision = parse_decision(
            response.raw_response, iteration=1, goal=goal, budget=call_budget,
            provider_id=response.provider_id, model_id=response.model_id,
        )
        evaluations, proposal_ids, failures = [], [], []
        admitted_count = 0
        for source in decision["proposals"][:3]:
            state["budget_usage"]["proposals"] += 1
            enriched = dict(source) | {"_round_number": round_number, "_factor_family": plan["theme"]}
            admission = admit_proposal(
                enriched, allowed_features=set(plan["allowed_features"]),
                allowed_operators=set(OPERATORS), known_fingerprints=set(state["known_fingerprints"]),
            )
            proposal_identity = {
                "schema_version": "autonomous-factor-proposal-v2",
                "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
                "round_number": round_number, "source_response_sha256": response_hash,
                "proposal": admission.get("proposal") or {"proposal_id": source.get("proposal_id")},
                "admission": {k: v for k, v in admission.items() if k != "proposal"},
                "promotion_writes": 0,
            }
            proposal_receipt = repository.publish(
                "autonomous_factor_proposal", proposal_identity,
                {"proposal.json": proposal_identity},
                lineage=(campaign_id, plan_receipt["artifact_id"], response_receipt["artifact_id"]),
            )
            proposal_ids.append(proposal_receipt["artifact_id"])
            if not admission["admitted"] or admitted_count >= 2:
                failures.append(admission.get("failure_code") or "semantic_mismatch")
                continue
            admitted_count += 1
            state["budget_usage"]["admitted_templates"] += 1
            proposal = admission["proposal"]
            state["known_fingerprints"].append(proposal["structural_fingerprint"])
            remaining = budget["maximum_local_rescue_trials"] - state["budget_usage"]["local_rescue_trials"]
            before = evaluator.qlib.calls
            evaluation = evaluator.evaluate(
                proposal, maximum_local_trials=min(6, remaining),
                annual_periods=DISCOVERY_PERIODS, summary_mode="v2_discovery",
            )
            state["budget_usage"]["discovery_qlib_calls"] += evaluator.qlib.calls - before
            state["budget_usage"]["default_evaluations"] += int(evaluator.qlib.calls > before)
            local = len(evaluation.get("local_trials", []))
            state["budget_usage"]["local_rescue_trials"] += local
            state["budget_usage"]["development_locks"] += int(bool(evaluation.get("development_lock")))
            failures += evaluation["failure_codes"]
            evaluations.append({"proposal": proposal, "evaluation": evaluation})
            if evaluation["passed"]:
                state["budget_usage"]["discovery_candidates"] += 1
                exposure = _exposure(state, proposal)
                exposure_receipt = repository.publish(
                    "candidate_search_exposure", exposure,
                    {"search_exposure.json": exposure}, lineage=(campaign_id, proposal["factor_template_id"]),
                )
                state["search_exposure_ids"].append(exposure_receipt["artifact_id"])
        files: dict[str, Any] = {}
        public_rows = []
        for index, row in enumerate(evaluations):
            relative = f"discovery_2021_2022/{index:02d}-{row['proposal']['proposal_id']}.parquet"
            path = Path(work_root) / "round-values" / f"{round_number:04d}-{index:02d}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            values = row["evaluation"]["values"]
            if pd.Timestamp(values["trade_date"].max()) > pd.Timestamp("2022-12-30"):
                raise ValueError("LOCKED_HOLDOUT_EVIDENCE_CONTAMINATION")
            values.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
            files[relative] = path
            public_rows.append({
                "proposal": row["proposal"], "evaluation": _public(row["evaluation"]),
                "factor_values_file": relative,
            })
        round_identity = {
            "schema_version": "autonomous-factor-round-v2", "provider_id": "tushare-pro-v1",
            "campaign_spec_id": campaign_id, "round_number": round_number, "theme": plan["theme"],
            "round_plan_id": plan_receipt["artifact_id"],
            "agent_response_artifact_id": response_receipt["artifact_id"],
            "proposal_artifact_ids": proposal_ids, "proposal_count": len(decision["proposals"]),
            "admitted_count": admitted_count, "evaluations": public_rows,
            "failure_codes": failures, "selection_evidence_end": "2022-12-30",
            "input_evidence_partitions": ["development", "adaptive_discovery"],
            "locked_holdout_reads": 0, "report_period_feedback_used": False,
            "fresh_forward_evidence_used": False, "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0, "network_data_calls": 0,
            "tushare_calls": 0, "promotion_writes": 0,
        }
        round_receipt = repository.publish(
            "autonomous_factor_round", round_identity, {"round.json": round_identity} | files,
            lineage=(campaign_id, plan_receipt["artifact_id"], response_receipt["artifact_id"], *proposal_ids),
        )
        state["round_artifact_ids"].append(round_receipt["artifact_id"])
        for index, row in enumerate(evaluations):
            if row["evaluation"]["passed"]:
                state["discovery_candidate_refs"].append({
                    "round_artifact_id": round_receipt["artifact_id"], "evaluation_index": index,
                })
        state["budget_usage"]["rounds"] += 1
        state["memory"] = update_memory(state["memory"], round_identity, state["budget_usage"])
        memory_identity = dict(state["memory"]) | {
            "schema_version": "autonomous-factor-failure-memory-v2",
            "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
            "maximum_evidence_date": "2022-12-30",
            "forbidden_partitions_absent": True, "promotion_writes": 0,
        }
        memory_receipt = repository.publish(
            "autonomous_factor_failure_memory", memory_identity,
            {"failure_memory.json": memory_identity},
            lineage=(campaign_id, *state["round_artifact_ids"], state["clean_room_seed_memory_id"]),
        )
        state["memory_id"] = memory_receipt["artifact_id"]
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
        if stop_after_round and round_number >= stop_after_round:
            state["state"] = "paused_recoverable_error"
            state["stop_reason"] = "test_interrupt"
            return _result(state, repository)
    state["rounds_stopped"] = True
    state["agent_closed"] = True
    state["planner_closed"] = True
    state["state"] = "rounds_stopped"
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    _freeze_and_lock(repository, state, budget)
    _open_holdout_and_finalize(
        repository, state, bundle, full_matrix, contract, Path(work_root), budget,
    )
    report = {
        "schema_version": "autonomous-factor-campaign-report-v2",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": campaign_id,
        "terminal_state": state["state"], "stop_reason": state["stop_reason"],
        "evidence_partition_id": state["evidence_partition_id"],
        "clean_room_seed_memory_id": state["clean_room_seed_memory_id"],
        "v1_generalization_assessment_id": state["v1_assessment_id"],
        "round_artifact_ids": state["round_artifact_ids"],
        "failure_memory_id": state["memory_id"], "memory_freeze_id": state["memory_freeze_id"],
        "shortlist_lock_id": state["shortlist_lock_id"],
        "holdout_evaluation_ids": state["holdout_evaluation_ids"],
        "holdout_failure_ids": state["holdout_failure_ids"],
        "candidate_lock_ids": state["candidate_lock_ids"],
        "fresh_lock_ids": state["fresh_lock_ids"], "budget_usage": state["budget_usage"],
        "manual_intervention_count": 0, "manual_round_planning_count": 0,
        "holdout_used_for_ranking": False, "contaminated_reports_used_for_selection": False,
        "fresh_forward_evidence_used": False, "predictive_claim": False,
        "fresh_validation": False, "usable_for_production": False, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "autonomous_factor_campaign_report_v2", report, {"campaign_report_v2.json": report},
        lineage=(campaign_id, state["shortlist_lock_id"], *state["holdout_evaluation_ids"],
                 *state["candidate_lock_ids"], *state["fresh_lock_ids"]),
    )
    state["report_id"] = receipt["artifact_id"]
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    return _result(state, repository)


def _result(state: dict, repository) -> dict:
    return {
        "status": state["state"], "campaign_spec_id": state["campaign_spec_id"],
        "checkpoint_artifact_id": state.get("checkpoint_artifact_id"),
        "report_id": state.get("report_id"), "shortlist_lock_id": state.get("shortlist_lock_id"),
        "holdout_evaluation_ids": state["holdout_evaluation_ids"],
        "holdout_failure_ids": state["holdout_failure_ids"],
        "candidate_lock_ids": state["candidate_lock_ids"], "fresh_lock_ids": state["fresh_lock_ids"],
        "budget_usage": state["budget_usage"], "stop_reason": state["stop_reason"],
        "manual_intervention_count": 0, "manual_round_planning_count": 0,
        "store_integrity": repository.integrity(),
    }


def inspect_campaign_v2(*, campaign_id: str, repository_root: Path, work_root: Path,
                        store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    repository.find_spec_v2(campaign_id)
    return repository.latest_state(campaign_id) or _initial_state(campaign_id, repository)


def resume_campaign_v2(**kwargs) -> dict:
    return execute_campaign_v2(**kwargs)


def validate_campaign_v2(*, campaign_id: str, repository_root: Path, work_root: Path,
                         store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    repository.find_spec_v2(campaign_id)
    state = repository.latest_state(campaign_id)
    if state is None or state["state"] not in V2_STATES:
        raise ValueError("Campaign v2 state invalid")
    usage = state["budget_usage"]
    forbidden = (
        "strategy_optimization_calls", "combined_optimization_calls",
        "tushare_calls", "network_data_calls", "promotion_writes",
    )
    if any(usage[name] for name in forbidden):
        raise ValueError("Campaign v2 forbidden call recorded")
    for round_id in state["round_artifact_ids"]:
        row = repository.identity(round_id)
        if row["selection_evidence_end"] != "2022-12-30" or row["locked_holdout_reads"]:
            raise ValueError("LOCKED_HOLDOUT_EVIDENCE_CONTAMINATION")
    if state.get("shortlist_lock_id"):
        lock = repository.identity(state["shortlist_lock_id"])
        if lock["locked_holdout_reads_before_publish"] != 0:
            raise ValueError("holdout read preceded Shortlist Lock")
    required = [
        state.get("evidence_partition_id"), state.get("clean_room_seed_memory_id"),
        state.get("v1_assessment_id"), *state["round_artifact_ids"], state.get("memory_id"),
        state.get("memory_freeze_id"), state.get("shortlist_lock_id"),
        *state["search_exposure_ids"], *state["holdout_evaluation_ids"],
        *state["holdout_failure_ids"], *state["candidate_lock_ids"],
        *state["fresh_lock_ids"], state.get("report_id"),
    ]
    for artifact_id in [item for item in required if item]:
        repository.identity(artifact_id)
    return {
        "status": "valid", "campaign_spec_id": campaign_id,
        "campaign_state": state["state"], "evidence_gap_count": 0,
        "store_integrity": repository.integrity(),
    }


def replay_campaign_v2(*, campaign_id: str, repository_root: Path, work_root: Path,
                       store_root: Path | None = None) -> dict:
    validation = validate_campaign_v2(
        campaign_id=campaign_id, repository_root=repository_root,
        work_root=work_root, store_root=store_root,
    )
    return validation | {
        "agent_calls": 0, "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
        "qlib_calls": 0, "tushare_calls": 0, "network_data_calls": 0,
        "registry_writes": 0, "fresh_lock_writes": 0,
        "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
        "replay_cache_hit_rate": 1.0,
    }
