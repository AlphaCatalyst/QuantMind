from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.admission import admit_proposal
from backend.services.engine.autonomous_factor_campaign.evaluation import (
    CampaignEvaluator, signal_similarity,
)
from backend.services.engine.autonomous_factor_campaign.evaluation_v2 import (
    REPORT_PERIODS_V2, _year_result,
)
from backend.services.engine.autonomous_factor_campaign.failure_memory import (
    initial_memory, update_memory,
)
from backend.services.engine.autonomous_factor_campaign.orchestrator import (
    _agent_budget, _research_goal, _runtime,
)
from backend.services.engine.autonomous_factor_campaign.planner import THEME_FEATURES
from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import OPERATORS, SOURCE_DATASET_ID
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.momentum_factor_iteration.engine import _snapshot_contract
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError
from backend.services.engine.research_campaign.orchestrator import _request
from backend.services.engine.tushare_agent_experiment.evaluation import factor_values
from backend.services.engine.tushare_cutover.canonical import hash_file

from .models import (
    LANES, PROGRAM_STATES, TERMINAL_STATES,
    AutonomousFactorResearchProgramSpecV1, empty_usage, evidence_partitions,
)
from .statistics import benjamini_hochberg, hac_mean_test


ADAPTIVE_YEARS = {
    "2019": ("2019-01-02", "2019-12-31"),
    "2020": ("2020-01-02", "2020-12-31"),
}
VALIDATION_YEARS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
}


def _publish_foundations(repository, program_id: str) -> tuple[str, str, str]:
    partition = evidence_partitions() | {"program_id": program_id}
    partition_receipt = repository.publish(
        "research_program_evidence_partition", partition,
        {"evidence_partitions.json": partition}, lineage=(program_id,),
    )
    seed = {
        "schema_version": "research-program-clean-room-seed-v1",
        "provider_id": "tushare-pro-v1", "program_id": program_id,
        "allowed": [
            "historical_dsl", "canonical_ast", "structural_fingerprint",
            "feature_operator_usage", "duplicate_structure", "pit_failure",
            "dsl_failure", "semantic_failure", "data_quality_failure",
        ],
        "forbidden": [
            "metrics_2021_2026", "historical_candidate_rank",
            "candidate_or_holdout_status", "fresh_forward_data",
        ],
        "maximum_metric_date": "2020-12-31",
        "campaign_002_failed_structure_fingerprint_only": True,
        "promotion_writes": 0,
    }
    seed_receipt = repository.publish(
        "research_program_clean_room_seed", seed,
        {"clean_room_seed.json": seed},
        lineage=(program_id, partition_receipt["artifact_id"]),
    )
    fingerprints: set[str] = set()
    for descriptor in repository.store.list_by_kind("autonomous_factor_proposal"):
        identity = repository.identity(descriptor.artifact_id)
        proposal = identity.get("proposal", {})
        fingerprint = proposal.get("structural_fingerprint")
        if fingerprint:
            fingerprints.add(fingerprint)
    novelty = {
        "schema_version": "global-research-novelty-index-v1",
        "provider_id": "tushare-pro-v1", "program_id": program_id,
        "source_scope": ["R1", "campaign_001", "campaign_002"],
        "structural_fingerprints": sorted(fingerprints),
        "performance_metadata_included": False,
        "signal_fingerprints": [], "promotion_writes": 0,
    }
    novelty_receipt = repository.publish(
        "global_research_novelty_index", novelty,
        {"global_novelty_index.json": novelty},
        lineage=(program_id, seed_receipt["artifact_id"]),
    )
    return (
        partition_receipt["artifact_id"], seed_receipt["artifact_id"],
        novelty_receipt["artifact_id"],
    )


def create_program_spec(*, repository_root: Path, work_root: Path,
                        store_root: Path | None = None,
                        spec: AutonomousFactorResearchProgramSpecV1 | None = None) -> dict:
    payload = (spec or AutonomousFactorResearchProgramSpecV1()).payload()
    _, repository = _runtime(repository_root, work_root, store_root)
    receipt = repository.publish(
        "autonomous_factor_research_program_spec", payload,
        {"program_spec.json": payload, "lane_specs.json": payload["lanes"]},
        lineage=(SOURCE_DATASET_ID,),
    )
    repository.identity(payload["program_spec_id"])
    partition_id, seed_id, novelty_id = _publish_foundations(
        repository, payload["program_spec_id"]
    )
    return payload | {
        "store_receipt": receipt, "evidence_partition_id": partition_id,
        "clean_room_seed_id": seed_id, "global_novelty_index_id": novelty_id,
    }


def _initial_state(program_id: str, repository) -> dict:
    def latest(kind: str) -> str:
        rows = repository.identities_by_kind(kind, program_id)
        return rows[-1]["artifact_id"]
    lanes = {
        lane_id: {
            "lane_id": lane_id, "status": "planned", "rounds": 0,
            "agent_calls": 0, "proposals": 0, "admissions": 0,
            "local_rescue_trials": 0, "adaptive_qlib_calls": 0,
            "memory": initial_memory(), "memory_id": None,
            "round_artifact_ids": [], "candidate_refs": [],
            "shortlist_lock_id": None, "planner_closed": False,
            "memory_frozen": False, "consecutive_no_lock": 0,
            "families_attempted": [], "stop_reason": None,
        }
        for lane_id in LANES
    }
    return {
        "program_id": program_id, "state": "planned", "checkpoint_sequence": 0,
        "budget_usage": empty_usage(), "lanes": lanes,
        "known_fingerprints": repository.identity(
            latest("global_research_novelty_index")
        )["structural_fingerprints"],
        "program_signal_refs": [], "search_exposure_ids": [],
        "lane_shortlist_lock_ids": [], "union_shortlist_lock_id": None,
        "validation_ids": [], "multiple_testing_id": None,
        "validation_failure_ids": [], "candidate_lock_ids": [],
        "fresh_lock_ids": [], "report_id": None, "inflight": None,
        "evidence_partition_id": latest("research_program_evidence_partition"),
        "clean_room_seed_id": latest("research_program_clean_room_seed"),
        "global_novelty_index_id": latest("global_research_novelty_index"),
        "adaptive_complete": False, "all_lane_planners_closed": False,
        "all_lane_memories_frozen": False, "all_parameters_frozen": False,
        "validation_opened": False, "stop_reason": None,
    }


def _latest_state(repository, program_id: str) -> dict | None:
    rows = repository.identities_by_kind("autonomous_factor_program", program_id)
    return max(rows, key=lambda row: row["checkpoint_sequence"], default=None)


def _checkpoint(repository, state: dict) -> None:
    identity = {
        "schema_version": "autonomous-factor-program-state-v1",
        "provider_id": "tushare-pro-v1", **state, "promotion_writes": 0,
    }
    lineage = [
        state["program_id"], state["evidence_partition_id"],
        state["clean_room_seed_id"], state["global_novelty_index_id"],
        *[rid for lane in state["lanes"].values() for rid in lane["round_artifact_ids"]],
        *state["lane_shortlist_lock_ids"], state.get("union_shortlist_lock_id"),
        *state["validation_ids"], state.get("multiple_testing_id"),
        *state["candidate_lock_ids"], *state["fresh_lock_ids"], state.get("report_id"),
    ]
    receipt = repository.publish(
        "autonomous_factor_program", identity,
        {"program_state.json": identity, "budget_state.json": state["budget_usage"]},
        lineage=tuple(item for item in lineage if item),
    )
    state["checkpoint_artifact_id"] = receipt["artifact_id"]


def _lane_plan(lane: dict) -> dict | None:
    allowed = LANES[lane["lane_id"]]["families"]
    counts = Counter(lane["families_attempted"])
    family = next((name for name in allowed if counts[name] < 4), None)
    if family is None:
        return None
    return {
        "status": "planned", "round_number": lane["rounds"] + 1,
        "lane_id": lane["lane_id"], "theme": family,
        "allowed_features": list(THEME_FEATURES[family]),
        "reason": "lane_family_coverage_and_isolated_failure_memory",
        "input_evidence_partitions": ["adaptive_research"],
        "manual_planning": False,
    }


def _select_lane(state: dict, budget: dict) -> tuple[dict, dict] | None:
    candidates = sorted(
        (
            lane for lane in state["lanes"].values()
            if lane["status"] not in {"stopped", "shortlist_locked"}
            and lane["agent_calls"] < budget["maximum_lane_agent_calls"]
        ),
        key=lambda lane: (lane["rounds"], lane["lane_id"]),
    )
    for lane in candidates:
        plan = _lane_plan(lane)
        if plan:
            return lane, plan
        lane["status"] = "stopped"
        lane["stop_reason"] = "lane_family_exhausted"
    return None


def _can_improvement_stop(state: dict, budget: dict) -> bool:
    usage = state["budget_usage"]
    families = {
        family for lane in state["lanes"].values()
        for family in lane["families_attempted"]
    }
    lanes_complete = sum(lane["rounds"] > 0 for lane in state["lanes"].values())
    no_lock = sum(lane["consecutive_no_lock"] for lane in state["lanes"].values())
    return (
        usage["rounds"] >= budget["minimum_rounds_before_improvement_stop"]
        and usage["agent_calls"] >= budget["minimum_agent_calls_before_improvement_stop"]
        and len(families) >= budget["minimum_distinct_families_before_improvement_stop"]
        and lanes_complete >= budget["minimum_lanes_with_completed_rounds"]
        and (
            usage["admissions"] >= budget["minimum_admissions_before_improvement_stop"]
            or all(_lane_plan(lane) is None for lane in state["lanes"].values())
        )
        and no_lock >= 6
    )


def _public(value: dict) -> dict:
    return {key: item for key, item in value.items() if key != "values"}


def _adaptive_order(row: dict) -> tuple:
    summary = row["evaluation"]["summary"]
    qlibs = [item["qlib"] for item in row["evaluation"]["annual"]]
    return (
        -summary["positive_rankic_year_count"], -summary["median_rankic"],
        -summary["worst_rankic"], -summary["positive_excess_year_count"],
        -summary["median_excess"],
        -int(row["evaluation"]["development_lock"]["optimization_mode"] == "default_parameters"),
        summary["median_turnover"], summary["median_best10_contribution"],
        summary["maximum_old_factor_correlation"],
        row["search_exposure"]["candidate_effective_search_count"],
        row["proposal"]["complexity_statement"]["ast_depth"],
        row["evaluation"]["development_lock"]["factor_instance_id"],
    )


def _search_exposure(state: dict, lane: dict, proposal: dict) -> dict:
    usage = state["budget_usage"]
    effective = usage["proposals"] + usage["admissions"] + usage["local_rescue_trials"]
    return {
        "schema_version": "program-search-exposure-v1",
        "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
        "lane_id": lane["lane_id"], "factor_template_id": proposal["factor_template_id"],
        "lane_agent_calls_before_candidate": lane["agent_calls"],
        "program_agent_calls_before_candidate": usage["agent_calls"],
        "lane_proposals_before_candidate": lane["proposals"],
        "program_proposals_before_candidate": usage["proposals"],
        "lane_admissions_before_candidate": lane["admissions"],
        "program_admissions_before_candidate": usage["admissions"],
        "local_rescue_trials_before_candidate": usage["local_rescue_trials"],
        "development_locks_before_candidate": sum(
            len(item["candidate_refs"]) for item in state["lanes"].values()
        ),
        "global_structural_neighbors": len(state["known_fingerprints"]),
        "global_signal_neighbors": len(state["program_signal_refs"]),
        "candidate_effective_search_count": effective,
        "program_effective_search_count": effective,
        "promotion_writes": 0,
    }


def _recover_program_values(repository, state: dict, evaluator) -> None:
    for lane in state["lanes"].values():
        for round_id in lane["round_artifact_ids"]:
            root = repository.materialize(round_id)
            identity = json.loads((root / "manifest.json").read_text())["identity"]
            for row in identity.get("evaluations", []):
                development_lock = row.get("evaluation", {}).get("development_lock")
                if row.get("factor_values_file") and development_lock:
                    values = pd.read_parquet(root / row["factor_values_file"])
                    evaluator.known_values.append((
                        development_lock["factor_instance_id"],
                        values,
                    ))


def _freeze_global_novelty_index(state: dict, repository) -> None:
    signal_fingerprints = []
    round_ids = [
        round_id
        for lane in state["lanes"].values()
        for round_id in lane["round_artifact_ids"]
    ]
    for round_id in round_ids:
        root = repository.materialize(round_id)
        identity = json.loads((root / "manifest.json").read_text())["identity"]
        for index, row in enumerate(identity.get("evaluations", [])):
            development_lock = row.get("evaluation", {}).get("development_lock")
            relative = row.get("factor_values_file")
            if not development_lock or not relative:
                continue
            signal_fingerprints.append({
                "signal_fingerprint": "sfp_" + hash_file(root / relative),
                "factor_instance_id": development_lock["factor_instance_id"],
                "round_artifact_id": round_id,
                "evaluation_index": index,
            })
    novelty = {
        "schema_version": "global-research-novelty-index-v1",
        "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
        "source_scope": ["R1", "campaign_001", "campaign_002", "current_program"],
        "structural_fingerprints": sorted(set(state["known_fingerprints"])),
        "signal_fingerprints": sorted(
            signal_fingerprints, key=lambda row: row["signal_fingerprint"]
        ),
        "performance_metadata_included": False,
        "current_program_included": True, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "global_research_novelty_index", novelty,
        {"global_novelty_index.json": novelty},
        lineage=(state["program_id"], state["global_novelty_index_id"], *round_ids),
    )
    state["global_novelty_index_id"] = receipt["artifact_id"]


def _process_round(*, state: dict, lane: dict, plan: dict, response_raw: str,
                   response_meta: dict, repository, evaluator, contract,
                   work_root: Path, budget: dict) -> None:
    goal, call_budget = _research_goal(state["program_id"], plan), _agent_budget()
    contract_diagnostic = None
    try:
        decision = parse_decision(
            response_raw, iteration=1, goal=goal, budget=call_budget,
            provider_id=response_meta["agent_provider"], model_id=response_meta["agent_model"],
        )
    except AgentContractError as exc:
        detail = getattr(exc, "detail", None)
        contract_diagnostic = detail if isinstance(detail, dict) else {
            "error_code": type(exc).__name__,
            "safe_summary": str(exc),
        }
        decision = {"proposals": []}
    evaluations, proposal_ids = [], []
    failures = [contract_diagnostic["error_code"]] if contract_diagnostic else []
    admitted_count = 0
    for source in decision["proposals"][:3]:
        state["budget_usage"]["proposals"] += 1
        lane["proposals"] += 1
        enriched = dict(source) | {
            "_round_number": plan["round_number"], "_factor_family": plan["theme"],
        }
        admission = admit_proposal(
            enriched, allowed_features=set(plan["allowed_features"]),
            allowed_operators=set(OPERATORS),
            known_fingerprints=set(state["known_fingerprints"]),
        )
        proposal = admission.get("proposal")
        if proposal:
            proposal = dict(proposal) | {
                "lane_id": lane["lane_id"], "round_id": plan["round_number"],
            }
        proposal_identity = {
            "schema_version": "autonomous-program-proposal-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            "lane_id": lane["lane_id"], "round_number": plan["round_number"],
            "proposal": proposal or {"proposal_id": source.get("proposal_id")},
            "admission": {k: v for k, v in admission.items() if k != "proposal"},
            "promotion_writes": 0,
        }
        receipt = repository.publish(
            "autonomous_factor_proposal", proposal_identity,
            {"proposal.json": proposal_identity},
            lineage=(state["program_id"], response_meta["artifact_id"]),
        )
        proposal_ids.append(receipt["artifact_id"])
        if not admission["admitted"] or admitted_count >= 2:
            failures.append(admission.get("failure_code") or "semantic_mismatch")
            continue
        admitted_count += 1
        state["budget_usage"]["admissions"] += 1
        lane["admissions"] += 1
        state["known_fingerprints"].append(proposal["structural_fingerprint"])
        remaining = budget["maximum_local_rescue_trials"] - state["budget_usage"]["local_rescue_trials"]
        before = evaluator.qlib.calls
        evaluation = evaluator.evaluate(
            proposal, maximum_local_trials=min(6, remaining),
            annual_periods=ADAPTIVE_YEARS, summary_mode="v2_discovery",
        )
        delta = evaluator.qlib.calls - before
        state["budget_usage"]["adaptive_qlib_calls"] += delta
        lane["adaptive_qlib_calls"] += delta
        local = len(evaluation.get("local_trials", []))
        state["budget_usage"]["local_rescue_trials"] += local
        lane["local_rescue_trials"] += local
        failures += evaluation["failure_codes"]
        evaluations.append({"proposal": proposal, "evaluation": evaluation})
    files: dict[str, Any] = {}
    public = []
    for index, row in enumerate(evaluations):
        values = row["evaluation"]["values"]
        if pd.Timestamp(values["trade_date"].max()) > pd.Timestamp("2020-12-31"):
            raise ValueError("PROGRAM_EVIDENCE_PARTITION_VIOLATION")
        relative = f"adaptive/{lane['lane_id']}/{plan['round_number']:02d}-{index:02d}.parquet"
        path = work_root / "adaptive-values" / lane["lane_id"] / f"{plan['round_number']:02d}-{index:02d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        values.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
        files[relative] = path
        public.append({
            "proposal": row["proposal"], "evaluation": _public(row["evaluation"]),
            "factor_values_file": relative,
        })
    identity = {
        "schema_version": "autonomous-factor-program-round-v1",
        "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
        "lane_id": lane["lane_id"], "round_number": plan["round_number"],
        "theme": plan["theme"], "agent_response_artifact_id": response_meta["artifact_id"],
        "proposal_artifact_ids": proposal_ids, "proposal_count": len(decision["proposals"]),
        "admitted_count": admitted_count, "evaluations": public,
        "failure_codes": failures, "selection_evidence_end": "2020-12-31",
        "agent_contract_diagnostic": contract_diagnostic,
        "input_evidence_partitions": ["adaptive_research"],
        "locked_validation_reads": 0, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "promotion_writes": 0,
    }
    round_receipt = repository.publish(
        "autonomous_factor_round", identity, {"round.json": identity} | files,
        lineage=(state["program_id"], response_meta["artifact_id"], *proposal_ids),
    )
    lane["round_artifact_ids"].append(round_receipt["artifact_id"])
    lane["rounds"] += 1
    lane["families_attempted"].append(plan["theme"])
    state["budget_usage"]["rounds"] += 1
    passed_count = 0
    for index, row in enumerate(evaluations):
        if row["evaluation"]["passed"]:
            passed_count += 1
            exposure = _search_exposure(state, lane, row["proposal"])
            exposure_receipt = repository.publish(
                "program_search_exposure", exposure,
                {"search_exposure.json": exposure},
                lineage=(state["program_id"], round_receipt["artifact_id"]),
            )
            state["search_exposure_ids"].append(exposure_receipt["artifact_id"])
            lane["candidate_refs"].append({
                "round_artifact_id": round_receipt["artifact_id"],
                "evaluation_index": index,
                "search_exposure_id": exposure_receipt["artifact_id"],
            })
            state["program_signal_refs"].append({
                "round_artifact_id": round_receipt["artifact_id"],
                "evaluation_index": index,
            })
    lane["consecutive_no_lock"] = 0 if passed_count else lane["consecutive_no_lock"] + 1
    lane["memory"] = update_memory(lane["memory"], identity, {
        "rounds": lane["rounds"], "agent_calls": lane["agent_calls"],
        "proposals": lane["proposals"], "admitted_templates": lane["admissions"],
        "local_rescue_trials": lane["local_rescue_trials"],
        "formal_qlib_calls": lane["adaptive_qlib_calls"], "candidate_locks": 0,
        "eligible_candidates": len(lane["candidate_refs"]),
    })
    memory_identity = dict(lane["memory"]) | {
        "schema_version": "autonomous-program-lane-memory-v1",
        "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
        "lane_id": lane["lane_id"], "maximum_evidence_date": "2020-12-31",
        "shared_performance_with_other_lanes": False, "promotion_writes": 0,
    }
    memory_receipt = repository.publish(
        "autonomous_factor_failure_memory", memory_identity,
        {"lane_failure_memory.json": memory_identity},
        lineage=(state["program_id"], *lane["round_artifact_ids"]),
    )
    lane["memory_id"] = memory_receipt["artifact_id"]


def _close_adaptive(state: dict, repository) -> None:
    _freeze_global_novelty_index(state, repository)
    for lane in state["lanes"].values():
        lane["status"] = "stopped"
        lane["planner_closed"] = True
        lane["memory_frozen"] = True
        lane["stop_reason"] = lane["stop_reason"] or "program_adaptive_complete"
        lane_identity = {
            "schema_version": "autonomous-factor-lane-state-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            **lane, "promotion_writes": 0,
        }
        repository.publish(
            "autonomous_factor_lane", lane_identity,
            {"lane_state.json": lane_identity},
            lineage=(state["program_id"], *lane["round_artifact_ids"], lane["memory_id"]),
        )
    state["adaptive_complete"] = True
    state["all_lane_planners_closed"] = True
    state["all_lane_memories_frozen"] = True
    state["all_parameters_frozen"] = True
    state["state"] = "adaptive_research_complete"


def _load_candidate(repository, reference: dict) -> dict:
    root = repository.materialize(reference["round_artifact_id"])
    identity = json.loads((root / "manifest.json").read_text())["identity"]
    row = identity["evaluations"][reference["evaluation_index"]]
    row["values"] = pd.read_parquet(root / row["factor_values_file"])
    row["round_artifact_id"] = reference["round_artifact_id"]
    row["search_exposure"] = repository.identity(reference["search_exposure_id"])
    return row


def _lock_lane_shortlists(state: dict, repository) -> list[dict]:
    all_rows = []
    for lane in state["lanes"].values():
        rows = sorted(
            (_load_candidate(repository, ref) for ref in lane["candidate_refs"]),
            key=_adaptive_order,
        )[:4]
        entries = []
        for rank, row in enumerate(rows, 1):
            proposal, evaluation = row["proposal"], row["evaluation"]
            entries.append({
                "lane_rank": rank, "lane_id": lane["lane_id"],
                "factor_template_id": proposal["factor_template_id"],
                "factor_instance_id": evaluation["development_lock"]["factor_instance_id"],
                "template": proposal["template"], "canonical_dsl": proposal["canonical_dsl"],
                "canonical_ast": proposal["canonical_ast"],
                "factor_family": proposal["factor_family"],
                "selected_parameters": evaluation["development_lock"]["selected_parameters"],
                "default_parameters": proposal["default_parameters"],
                "orientation": evaluation["development_lock"]["orientation"],
                "optimization_rescued": evaluation["development_lock"]["optimization_rescued"],
                "adaptive_metrics": evaluation["annual"],
                "adaptive_summary": evaluation["summary"],
                "search_exposure": row["search_exposure"],
                "structural_fingerprint": proposal["structural_fingerprint"],
                "round_artifact_id": row["round_artifact_id"],
                "_values": row["values"],
            })
        public = [{k: v for k, v in row.items() if k != "_values"} for row in entries]
        lock = {
            "schema_version": "autonomous-lane-shortlist-lock-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            "lane_id": lane["lane_id"], "maximum_evidence_date": "2020-12-31",
            "locked_validation_reads_before_publish": state["budget_usage"]["locked_validation_reads"],
            "planner_closed": True, "memory_frozen": True,
            "shortlist": public, "shortlist_count": len(public), "promotion_writes": 0,
        }
        receipt = repository.publish(
            "autonomous_lane_shortlist_lock", lock,
            {"lane_shortlist_lock.json": lock},
            lineage=(state["program_id"], lane["memory_id"], *lane["round_artifact_ids"]),
        )
        lane["shortlist_lock_id"] = receipt["artifact_id"]
        lane["status"] = "shortlist_locked"
        state["lane_shortlist_lock_ids"].append(receipt["artifact_id"])
        for row in entries:
            row["lane_shortlist_lock_id"] = receipt["artifact_id"]
        all_rows += entries
    return all_rows


def _union_order(rows: list[dict]) -> list[dict]:
    ordered = sorted(rows, key=lambda row: (
        row["lane_rank"], row["search_exposure"]["candidate_effective_search_count"],
        row["factor_instance_id"],
    ))
    selected, selected_ids, seen_families, seen_lanes = [], set(), set(), set()
    for pass_number in (0, 1):
        for row in ordered:
            if row["factor_instance_id"] in selected_ids:
                continue
            if pass_number == 0 and (
                row["lane_id"] in seen_lanes or row["factor_family"] in seen_families
            ):
                continue
            if any(
                abs(signal_similarity(row["_values"], prior["_values"])["spearman"] or 0) >= .95
                for prior in selected
            ):
                continue
            selected.append(row)
            selected_ids.add(row["factor_instance_id"])
            seen_lanes.add(row["lane_id"])
            seen_families.add(row["factor_family"])
            if len(selected) == 12:
                return selected
    return selected


def _lock_union(state: dict, repository, rows: list[dict]) -> list[dict]:
    if state["budget_usage"]["locked_validation_reads"] != 0:
        raise ValueError("PROGRAM_EVIDENCE_PARTITION_VIOLATION")
    selected = _union_order(rows)
    public = []
    for rank, row in enumerate(selected, 1):
        item = {k: v for k, v in row.items() if k != "_values"}
        item["union_adaptive_rank"] = rank
        public.append(item)
        row["union_adaptive_rank"] = rank
    lock = {
        "schema_version": "autonomous-program-union-shortlist-lock-v1",
        "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
        "all_lane_planners_closed": state["all_lane_planners_closed"],
        "all_lane_memories_frozen": state["all_lane_memories_frozen"],
        "all_parameters_frozen": state["all_parameters_frozen"],
        "locked_validation_reads_before_publish": 0,
        "selection_evidence_end": "2020-12-31",
        "shortlist": public, "shortlist_count": len(public),
        "ranking_frozen": True, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "autonomous_program_union_shortlist_lock", lock,
        {"union_shortlist_lock.json": lock},
        lineage=(state["program_id"], *state["lane_shortlist_lock_ids"]),
    )
    state["union_shortlist_lock_id"] = receipt["artifact_id"]
    state["state"] = "union_shortlist_locked"
    return selected


def _daily_rankic(values: pd.DataFrame, matrix: pd.DataFrame, orientation: int) -> list[float]:
    labels = matrix.loc[
        matrix["trade_date"].between("2021-01-04", "2024-12-31"),
        ["symbol", "trade_date", "model_label"],
    ]
    merged = labels.merge(values, on=["symbol", "trade_date"], how="left")
    merged["factor_value"] *= orientation
    rows = []
    for _, group in merged.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["factor_value", "model_label"])
        if len(valid) >= 2:
            value = valid["factor_value"].corr(valid["model_label"], method="spearman")
            if pd.notna(value):
                rows.append(float(value))
    return rows


def _validation_summary(rows: list[dict], max_existing: float) -> dict:
    rankic = [row["metrics"].get("mean_rank_ic") for row in rows]
    excess = [row["qlib"].get("net_excess_csi300") for row in rows]
    turnover = [row["qlib"].get("turnover") for row in rows]
    concentration = [row["qlib"].get("best_10_days_contribution") for row in rows]
    values = {
        "complete_year_count": len(rows),
        "positive_rankic_year_count": sum(x is not None and x > 0 for x in rankic),
        "median_rankic": float(median(rankic)) if None not in rankic else None,
        "worst_rankic": min(rankic) if None not in rankic else None,
        "positive_excess_year_count": sum(x is not None and x > 0 for x in excess),
        "median_excess": float(median(excess)) if None not in excess else None,
        "worst_excess": min(excess) if None not in excess else None,
        "median_turnover": float(median(turnover)) if None not in turnover else None,
        "median_best10_contribution": float(median(concentration)) if None not in concentration else None,
        "maximum_existing_factor_correlation": max_existing,
    }
    checks = {
        "complete_years": len(rows) == 4,
        "coverage": all((row["metrics"].get("factor_finite_coverage") or 0) >= .90 for row in rows),
        "infinity": all(row["infinity_count"] == 0 for row in rows),
        "pit": all(row["pit_violation_count"] == 0 for row in rows),
        "positive_rankic_years": values["positive_rankic_year_count"] >= 3,
        "median_rankic": values["median_rankic"] is not None and values["median_rankic"] >= .003,
        "worst_rankic": values["worst_rankic"] is not None and values["worst_rankic"] >= -.008,
        "positive_excess_years": values["positive_excess_year_count"] >= 3,
        "median_excess": values["median_excess"] is not None and values["median_excess"] > 0,
        "worst_excess": values["worst_excess"] is not None and values["worst_excess"] > -.10,
        "turnover": values["median_turnover"] is not None and values["median_turnover"] <= 30,
        "concentration": values["median_best10_contribution"] is not None and values["median_best10_contribution"] <= .35,
        "existing_factor_independence": max_existing < .85,
        "parameters_unchanged": True, "orientation_unchanged": True,
    }
    return values | {
        "gate_results": checks, "base_gate_passed": all(checks.values()),
        "failed_gates": [key for key, passed in checks.items() if not passed],
    }


def _validate_union(state: dict, repository, selected: list[dict], bundle,
                    full_matrix: pd.DataFrame, contract, work_root: Path,
                    budget: dict) -> list[tuple[dict, dict, pd.DataFrame]]:
    if not (
        state["union_shortlist_lock_id"] and state["all_lane_planners_closed"]
        and state["all_lane_memories_frozen"] and state["all_parameters_frozen"]
    ):
        raise ValueError("PROGRAM_EVIDENCE_PARTITION_VIOLATION")
    state["validation_opened"] = True
    state["state"] = "running_locked_validation"
    evaluator = CampaignEvaluator(
        bundle=bundle, matrix=full_matrix, contract=contract,
        work_root=work_root / "locked-validation",
    )
    results = []
    for locked in selected:
        compiled, values = factor_values(
            parse_template(locked["template"]), contract,
            locked["selected_parameters"], full_matrix,
        )
        before = evaluator.qlib.calls
        annual = [
            _year_result(
                evaluator, values, locked["orientation"], compiled.factor_instance_id,
                year, period, "locked_validation",
            )
            for year, period in VALIDATION_YEARS.items()
        ]
        calls = evaluator.qlib.calls - before
        state["budget_usage"]["validation_qlib_calls"] += calls
        state["budget_usage"]["locked_validation_reads"] += calls
        state["budget_usage"]["validation_objects"] += 1
        similarities = [
            signal_similarity(values, prior)
            for _, prior in evaluator.known_values
        ]
        max_existing = max(
            (abs(row["spearman"]) for row in similarities if row["spearman"] is not None),
            default=0.0,
        )
        summary = _validation_summary(annual, max_existing)
        statistical = hac_mean_test(
            _daily_rankic(values, full_matrix, locked["orientation"]), lag=10
        )
        identity = {
            "schema_version": "program-locked-validation-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            "union_shortlist_lock_id": state["union_shortlist_lock_id"],
            "lane_id": locked["lane_id"], "factor_template_id": locked["factor_template_id"],
            "factor_instance_id": compiled.factor_instance_id,
            "union_adaptive_rank": locked["union_adaptive_rank"],
            "parameters": locked["selected_parameters"], "orientation": locked["orientation"],
            "parameters_unchanged": True, "orientation_unchanged": True,
            "annual": annual, "summary": summary, "statistical_test": statistical,
            "feedback_to_agent": False, "feedback_to_planner": False,
            "used_for_ranking": False, "promotion_writes": 0,
        }
        receipt = repository.publish(
            "program_locked_validation", identity,
            {"locked_validation.json": identity},
            lineage=(state["program_id"], state["union_shortlist_lock_id"]),
        )
        state["validation_ids"].append(receipt["artifact_id"])
        results.append((locked, identity | {"artifact_id": receipt["artifact_id"]}, values))
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
    multiple_rows = benjamini_hochberg([
        {
            "validation_id": result["artifact_id"],
            "factor_instance_id": result["factor_instance_id"],
            **result["statistical_test"],
        }
        for _, result, _ in results
    ], q=.10)
    control = {
        "schema_version": "program-multiple-testing-control-v1",
        "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
        "union_shortlist_lock_id": state["union_shortlist_lock_id"],
        "method": "Benjamini-Hochberg", "fdr_q": .10,
        "hac_lag": 10, "normal_approximation": True,
        "results": multiple_rows, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "program_multiple_testing_control", control,
        {"multiple_testing.json": control},
        lineage=(state["program_id"], *state["validation_ids"]),
    )
    state["multiple_testing_id"] = receipt["artifact_id"]
    by_id = {row["validation_id"]: row for row in multiple_rows}
    return [
        (locked, result | {"multiple_testing": by_id[result["artifact_id"]]}, values)
        for locked, result, values in results
    ]


def _latest_and_fresh(bundle, matrix) -> tuple[str, str]:
    latest = pd.Timestamp(matrix["trade_date"].max()).strftime("%Y-%m-%d")
    dates = [
        line.strip()[:10]
        for line in (Path(bundle.qlib_view) / "calendars" / "day.txt").read_text().splitlines()
        if line.strip()
    ]
    future = next((date for date in dates if date > latest), None)
    if future is None:
        raise ValueError("formal calendar lacks a Fresh start date")
    return latest, future


def _finalize(state: dict, repository, validation_rows, bundle, full_matrix,
              contract, work_root: Path, budget: dict) -> None:
    provisional = []
    for locked, result, values in validation_rows:
        test = result["multiple_testing"]
        passed = (
            result["summary"]["base_gate_passed"]
            and test["multiple_testing_passed"]
            and (test["mean_rankic"] or 0) > 0
        )
        if passed:
            provisional.append((locked, result, values))
        else:
            failed = list(result["summary"]["failed_gates"])
            if not test["multiple_testing_passed"]:
                failed.append("benjamini_hochberg_fdr")
            if (test["mean_rankic"] or 0) <= 0:
                failed.append("combined_mean_rankic")
            identity = {
                "schema_version": "program-validation-failure-report-v1",
                "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
                "lane_id": locked["lane_id"], "factor_instance_id": result["factor_instance_id"],
                "failed_gates": failed, "adaptive_metrics": locked["adaptive_metrics"],
                "validation_metrics": result["annual"],
                "generalization_gap": {
                    "rankic": result["summary"]["median_rankic"] - locked["adaptive_summary"]["median_rankic"],
                    "excess": result["summary"]["median_excess"] - locked["adaptive_summary"]["median_excess"],
                },
                "raw_p_value": test["raw_p_value"],
                "adjusted_q_value": test["adjusted_q_value"],
                "search_exposure": locked["search_exposure"],
                "optimization_rescued": locked["optimization_rescued"],
                "correlation_risk": result["summary"]["maximum_existing_factor_correlation"],
                "largest_failure": failed[0], "registry_write": False,
                "promotion_writes": 0,
            }
            receipt = repository.publish(
                "program_validation_failure_report", identity,
                {"validation_failure.json": identity},
                lineage=(state["program_id"], result["artifact_id"], state["multiple_testing_id"]),
            )
            state["validation_failure_ids"].append(receipt["artifact_id"])
    # Survivor correlation is also Pass/Fail; frozen Adaptive order controls capacity.
    survivors = []
    for row in sorted(provisional, key=lambda item: item[0]["union_adaptive_rank"]):
        if any(
            abs(signal_similarity(row[2], prior[2])["spearman"] or 0) >= .85
            for prior in survivors
        ):
            continue
        survivors.append(row)
    survivors = survivors[:budget["maximum_final_survivors"]]
    if survivors:
        evaluator = CampaignEvaluator(
            bundle=bundle, matrix=full_matrix, contract=contract,
            work_root=work_root / "reports",
        )
    for locked, result, values in survivors:
        path = work_root / "survivor-values" / f"{result['factor_instance_id']}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        values.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
        value_identity = {
            "schema_version": "autonomous-program-factor-values-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            "factor_instance_id": result["factor_instance_id"],
            "factor_template_id": locked["factor_template_id"],
            "dataset_id": SOURCE_DATASET_ID, "values_sha256": hash_file(path),
            "row_count": len(values), "promotion_writes": 0,
        }
        value_receipt = repository.publish(
            "autonomous_factor_value_materialization", value_identity,
            {"factor_values.parquet": path},
            lineage=(state["program_id"], result["artifact_id"]),
        )
        before = evaluator.qlib.calls
        reports = [
            _year_result(
                evaluator, values, locked["orientation"], result["factor_instance_id"],
                name, period, "contaminated_report",
            ) | {
                "contaminated_report_only": True, "not_used_for_selection": True,
                "not_used_for_planning": True, "not_used_for_validation_gate": True,
                "not_fresh_validation": True,
            }
            for name, period in REPORT_PERIODS_V2.items()
        ]
        state["budget_usage"]["report_qlib_calls"] += evaluator.qlib.calls - before
        test = result["multiple_testing"]
        candidate = {
            "schema_version": "autonomous-program-candidate-lock-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            "lane_id": locked["lane_id"],
            "lane_shortlist_lock_id": locked["lane_shortlist_lock_id"],
            "union_shortlist_lock_id": state["union_shortlist_lock_id"],
            "campaign_version": "program_v1",
            "factor_template_id": locked["factor_template_id"],
            "factor_instance_id": result["factor_instance_id"],
            "canonical_dsl": locked["canonical_dsl"], "canonical_ast": locked["canonical_ast"],
            "selected_parameters": locked["selected_parameters"],
            "orientation": locked["orientation"], "status": "research_registered",
            "locked_validation_passed": True, "multiple_testing_passed": True,
            "adjusted_q_value": test["adjusted_q_value"],
            "candidate_search_exposure": locked["search_exposure"],
            "program_search_exposure": locked["search_exposure"],
            "not_fresh_validated": True, "factor_value_artifact_id": value_receipt["artifact_id"],
            "contaminated_report_periods": reports, "predictive_claim": False,
            "usable_for_production": False, "promotion_writes": 0,
        }
        receipt = repository.publish(
            "autonomous_factor_candidate_lock", candidate,
            {"candidate_lock.json": candidate},
            lineage=(state["program_id"], result["artifact_id"], value_receipt["artifact_id"]),
        )
        state["candidate_lock_ids"].append(receipt["artifact_id"])
        latest, fresh_start = _latest_and_fresh(bundle, full_matrix)
        fresh = {
            "schema_version": "autonomous-program-candidate-fresh-lock-v1",
            "provider_id": "tushare-pro-v1", "program_id": state["program_id"],
            "candidate_id": receipt["artifact_id"], "lane_id": locked["lane_id"],
            "union_shortlist_lock_id": state["union_shortlist_lock_id"],
            "formula": locked["canonical_dsl"], "parameters": locked["selected_parameters"],
            "orientation": locked["orientation"],
            "strategy_protocol": {
                "topk": 20, "n_drop": 5, "rebalance_interval": 10,
                "weighting": "equal_weight", "signal_lag": 1, "execution": "open",
            },
            "universe": "Tushare Fixed-100", "benchmark": "CSI300",
            "latest_market_data_date_used": latest, "fresh_start_date": fresh_start,
            "no_backfill": True, "minimum_fresh_trading_days": 60,
            "minimum_completed_holding_windows": 5,
            "minimum_rebalance_periods": 3,
            "status": "locked_awaiting_fresh_data", "promotion_writes": 0,
        }
        fresh_receipt = repository.publish(
            "autonomous_program_candidate_fresh_lock", fresh,
            {"fresh_lock.json": fresh},
            lineage=(state["program_id"], receipt["artifact_id"]),
        )
        state["fresh_lock_ids"].append(fresh_receipt["artifact_id"])
    state["budget_usage"]["final_survivors"] = len(state["candidate_lock_ids"])
    state["state"] = (
        "completed_with_survivors" if state["candidate_lock_ids"]
        else (
            "completed_no_lane_shortlist"
            if not state["union_shortlist_lock_id"]
            else "completed_no_validation_survivor"
        )
    )


def execute_program(*, program_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None, agent=None,
                    stop_after_round: int | None = None) -> dict:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(program_id)
    if spec.get("schema_version") != "autonomous-factor-research-program-spec-v1":
        raise ValueError("Program Spec is absent")
    state = _latest_state(repository, program_id) or _initial_state(program_id, repository)
    if state["state"] in TERMINAL_STATES:
        return replay_program(
            program_id=program_id, repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay", store_root=store_root,
        ) | {"exact_existing": True}
    full_matrix, _ = _source_matrix(bundle, Path(work_root) / "source")
    features = [c for c in full_matrix if c not in {"symbol", "trade_date", "raw_label", "model_label"}]
    contract = _snapshot_contract(SOURCE_DATASET_ID, features, full_matrix["trade_date"].nunique())
    adaptive = full_matrix[full_matrix["trade_date"] <= "2020-12-31"].copy()
    if pd.Timestamp(adaptive["trade_date"].max()).strftime("%Y-%m-%d") != "2020-12-31":
        raise ValueError("Adaptive Research physical cutoff is incomplete")
    adaptive_work_root = (
        Path(work_root) / "adaptive"
        / f"checkpoint-{state.get('checkpoint_sequence', 0):06d}"
    )
    if adaptive_work_root.exists():
        shutil.rmtree(adaptive_work_root)
    evaluator = CampaignEvaluator(
        bundle=bundle, matrix=adaptive, contract=contract,
        work_root=adaptive_work_root,
    )
    evaluator.known_values = [
        (name, values[values["trade_date"] <= "2020-12-31"].copy())
        for name, values in evaluator.known_values
    ]
    _recover_program_values(repository, state, evaluator)
    if state.get("inflight"):
        inflight = state["inflight"]
        lane = state["lanes"][inflight["lane_id"]]
        if inflight.get("response_artifact_id"):
            root = repository.materialize(inflight["response_artifact_id"])
            response_raw = (root / "agent_response.json").read_text(encoding="utf-8")
            response_identity = repository.identity(inflight["response_artifact_id"])
            _process_round(
                state=state, lane=lane, plan=inflight["plan"],
                response_raw=response_raw,
                response_meta=response_identity | {"artifact_id": inflight["response_artifact_id"]},
                repository=repository, evaluator=evaluator, contract=contract,
                work_root=Path(work_root), budget=spec["budgets"],
            )
        else:
            # The call counter was durably reserved but no response exists.
            # Close it without a repeat; a later independent Program may retry.
            lane["rounds"] += 1
            lane["families_attempted"].append(inflight["plan"]["theme"])
            lane["consecutive_no_lock"] += 1
            state["budget_usage"]["rounds"] += 1
            lane["stop_reason"] = "agent_call_interrupted_without_persisted_response"
        state["inflight"] = None
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    budget = spec["budgets"]
    state["state"] = "running_adaptive_research"
    _checkpoint(repository, state)
    while state["state"] == "running_adaptive_research":
        usage = state["budget_usage"]
        if (
            usage["rounds"] >= budget["maximum_total_rounds"]
            or usage["agent_calls"] >= budget["maximum_agent_calls"]
            or usage["proposals"] >= budget["maximum_proposals"]
            or usage["admissions"] >= budget["maximum_admissions"]
            or usage["adaptive_qlib_calls"] >= budget["maximum_adaptive_qlib_calls"]
        ):
            state["stop_reason"] = "program_budget_exhausted"
            break
        if _can_improvement_stop(state, budget):
            state["stop_reason"] = "program_improvement_exhausted_after_minimum_coverage"
            break
        selection = _select_lane(state, budget)
        if selection is None:
            state["stop_reason"] = "all_lanes_exhausted"
            break
        lane, plan = selection
        available = set(contract.feature_roles)
        plan["allowed_features"] = [
            name for name in plan["allowed_features"]
            if name in available and contract.feature_roles[name] == "feature"
        ]
        if not plan["allowed_features"]:
            lane["families_attempted"].append(plan["theme"])
            continue
        plan_identity = {
            "schema_version": "autonomous-program-round-plan-v1",
            "provider_id": "tushare-pro-v1", "program_id": program_id,
            **plan, "promotion_writes": 0,
        }
        plan_receipt = repository.publish(
            "autonomous_factor_round_plan", plan_identity,
            {"round_plan.json": plan_identity},
            lineage=(program_id, lane.get("memory_id")),
        )
        goal, call_budget = _research_goal(program_id, plan), _agent_budget()
        request = _request(goal, lane["memory"], call_budget, 1)
        lane["agent_calls"] += 1
        usage["agent_calls"] += 1
        state["inflight"] = {
            "lane_id": lane["lane_id"], "plan": plan,
            "plan_artifact_id": plan_receipt["artifact_id"],
            "phase": "agent_call_started", "response_artifact_id": None,
        }
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
        response = agent.propose(request)
        digest = hashlib.sha256(response.raw_response.encode()).hexdigest()
        response_identity = {
            "schema_version": "autonomous-program-agent-response-v1",
            "record_type": "agent_response", "provider_id": "tushare-pro-v1",
            "program_id": program_id, "lane_id": lane["lane_id"],
            "round_number": plan["round_number"],
            "agent_provider": response.provider_id, "agent_model": response.model_id,
            "response_sha256": digest, "usage_summary": response.usage_summary,
            "evidence_partitions": ["adaptive_research"], "promotion_writes": 0,
        }
        response_receipt = repository.publish(
            "autonomous_factor_proposal", response_identity,
            {"agent_response.json": response.raw_response.encode()},
            lineage=(program_id, plan_receipt["artifact_id"]),
        )
        state["inflight"]["phase"] = "agent_response_persisted"
        state["inflight"]["response_artifact_id"] = response_receipt["artifact_id"]
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
        _process_round(
            state=state, lane=lane, plan=plan, response_raw=response.raw_response,
            response_meta=response_identity | {"artifact_id": response_receipt["artifact_id"]},
            repository=repository, evaluator=evaluator, contract=contract,
            work_root=Path(work_root), budget=budget,
        )
        state["inflight"] = None
        state["checkpoint_sequence"] += 1
        _checkpoint(repository, state)
        if stop_after_round and usage["rounds"] >= stop_after_round:
            state["state"] = "paused_recoverable_error"
            state["stop_reason"] = "test_interrupt"
            state["checkpoint_sequence"] += 1
            _checkpoint(repository, state)
            return _result(state, repository)
    _close_adaptive(state, repository)
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    lane_rows = _lock_lane_shortlists(state, repository)
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    union = _lock_union(state, repository, lane_rows)
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    if not union:
        state["state"] = "completed_no_lane_shortlist"
    else:
        validated = _validate_union(
            state, repository, union, bundle, full_matrix, contract,
            Path(work_root), budget,
        )
        _finalize(
            state, repository, validated, bundle, full_matrix, contract,
            Path(work_root), budget,
        )
    report = {
        "schema_version": "autonomous-factor-program-report-v1",
        "provider_id": "tushare-pro-v1", "program_id": program_id,
        "terminal_state": state["state"], "stop_reason": state["stop_reason"],
        "budget_usage": state["budget_usage"], "lanes": {
            key: {
                field: value for field, value in lane.items()
                if field not in {"memory"}
            }
            for key, lane in state["lanes"].items()
        },
        "lane_shortlist_lock_ids": state["lane_shortlist_lock_ids"],
        "union_shortlist_lock_id": state["union_shortlist_lock_id"],
        "validation_ids": state["validation_ids"],
        "multiple_testing_id": state["multiple_testing_id"],
        "validation_failure_ids": state["validation_failure_ids"],
        "candidate_lock_ids": state["candidate_lock_ids"],
        "fresh_lock_ids": state["fresh_lock_ids"],
        "manual_intervention_count": 0, "manual_round_planning_count": 0,
        "manual_lane_switching_count": 0,
        "validation_used_for_ranking": False,
        "contaminated_reports_used_for_selection": False,
        "fresh_forward_evidence_used": False, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "autonomous_factor_program_report", report,
        {"program_report.json": report},
        lineage=(program_id, *state["lane_shortlist_lock_ids"],
                 state["union_shortlist_lock_id"], *state["validation_ids"],
                 state["multiple_testing_id"], *state["candidate_lock_ids"],
                 *state["fresh_lock_ids"]),
    )
    state["report_id"] = receipt["artifact_id"]
    state["checkpoint_sequence"] += 1
    _checkpoint(repository, state)
    return _result(state, repository)


def _result(state: dict, repository) -> dict:
    return {
        "status": state["state"], "program_id": state["program_id"],
        "checkpoint_artifact_id": state.get("checkpoint_artifact_id"),
        "report_id": state.get("report_id"),
        "lane_shortlist_lock_ids": state["lane_shortlist_lock_ids"],
        "union_shortlist_lock_id": state.get("union_shortlist_lock_id"),
        "validation_ids": state["validation_ids"],
        "multiple_testing_id": state.get("multiple_testing_id"),
        "validation_failure_ids": state["validation_failure_ids"],
        "candidate_lock_ids": state["candidate_lock_ids"],
        "fresh_lock_ids": state["fresh_lock_ids"],
        "budget_usage": state["budget_usage"], "stop_reason": state["stop_reason"],
        "store_integrity": repository.integrity(),
    }


def inspect_program(*, program_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    repository.identity(program_id)
    return _latest_state(repository, program_id) or _initial_state(program_id, repository)


def resume_program(**kwargs) -> dict:
    return execute_program(**kwargs)


def validate_program(*, program_id: str, repository_root: Path, work_root: Path,
                     store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(program_id)
    state = _latest_state(repository, program_id)
    if spec.get("schema_version") != "autonomous-factor-research-program-spec-v1":
        raise ValueError("Program Spec invalid")
    if state is None or state["state"] not in PROGRAM_STATES:
        raise ValueError("Program state invalid")
    usage = state["budget_usage"]
    for field in (
        "strategy_optimization_calls", "combined_optimization_calls",
        "tushare_calls", "network_data_calls", "promotion_writes",
    ):
        if usage[field]:
            raise ValueError("forbidden Program call recorded")
    if state.get("union_shortlist_lock_id"):
        lock = repository.identity(state["union_shortlist_lock_id"])
        if lock["locked_validation_reads_before_publish"] != 0:
            raise ValueError("Validation read preceded Union Lock")
    required = [
        state["evidence_partition_id"], state["clean_room_seed_id"],
        state["global_novelty_index_id"],
        *[rid for lane in state["lanes"].values() for rid in lane["round_artifact_ids"]],
        *state["lane_shortlist_lock_ids"], state.get("union_shortlist_lock_id"),
        *state["validation_ids"], state.get("multiple_testing_id"),
        *state["validation_failure_ids"], *state["candidate_lock_ids"],
        *state["fresh_lock_ids"], state.get("report_id"),
    ]
    for artifact_id in [item for item in required if item]:
        repository.identity(artifact_id)
    return {
        "status": "valid", "program_id": program_id,
        "program_state": state["state"], "evidence_gap_count": 0,
        "store_integrity": repository.integrity(),
    }


def replay_program(*, program_id: str, repository_root: Path, work_root: Path,
                   store_root: Path | None = None) -> dict:
    validation = validate_program(
        program_id=program_id, repository_root=repository_root,
        work_root=work_root, store_root=store_root,
    )
    return validation | {
        "agent_calls": 0, "factor_optimization_calls": 0,
        "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
        "qlib_calls": 0, "tushare_calls": 0, "network_data_calls": 0,
        "registry_writes": 0, "fresh_lock_writes": 0,
        "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
    }
