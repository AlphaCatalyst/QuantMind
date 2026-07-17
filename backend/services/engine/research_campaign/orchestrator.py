import json
from dataclasses import asdict
from pathlib import Path

from backend.services.engine.factor_dsl import parse_template, snapshot_contract
from backend.services.engine.factor_optimization import execute_study, parse_optimization_spec, plan_study
from backend.services.engine.factor_registry import RegistryStatus, load_registry_snapshot, publish_snapshot
from backend.services.engine.factor_registry.models import RegistryEntry

from .artifact import CampaignJournal, campaign_id, validate_campaign
from .canonical import hash_payload
from .decision import parse_decision
from .development import evaluate_development
from .errors import AgentContractError, ResearchCampaignError
from .memory import sanitize_memory
from .models import CampaignConfig, ResearchAgentRequest, ResearchCampaignBudget, ResearchGoal
from .novelty import structural_fingerprint


def _goal_payload(goal): return asdict(goal) | {"allowed_features": list(goal.allowed_features),
    "allowed_operators": list(goal.allowed_operators), "allowed_parameter_roles": list(goal.allowed_parameter_roles),
    "constraints": list(goal.constraints)}


def _request(goal, memory, budget, iteration):
    safe_goal = {"goal_id": goal.goal_id, "name": goal.name, "objective": goal.objective,
                 "allowed_features": list(goal.allowed_features), "allowed_operators": list(goal.allowed_operators),
                 "allowed_parameter_roles": list(goal.allowed_parameter_roles), "dataset_kind": goal.dataset_kind,
                 "novelty_requirement": goal.novelty_requirement, "constraints": list(goal.constraints)}
    contract = {"schema_version": "research-decision-v1", "iteration": iteration,
                "maximum_proposals": budget.max_proposals_per_iteration,
                "parameter_roles": ["lookback_window", "factor_internal_weight", "signal_threshold"],
                "template_contract": {"schema_version": "1.0.0", "dataset_kinds": [goal.dataset_kind],
                    "parameter_fields": ["name", "type", "default", "minimum", "maximum"],
                    "feature_node": {"type": "feature", "name": "ALLOWED_FEATURE"},
                    "parameter_node": {"type": "parameter", "name": "DECLARED_PARAMETER"},
                    "constant_node": {"type": "constant", "value": 0.000001},
                    "unary_fields": ["type", "operand"], "binary_fields": ["type", "left", "right"],
                    "rolling_fields": ["type", "operand", "window"],
                    "delta_fields": ["type", "operand", "periods"]},
                "optimization": "explicit_values only; total campaign trial budget is enforced by Control",
                "authority": "structure proposal only; no Registry status, Validation, or execution authority"}
    return ResearchAgentRequest(safe_goal, memory, contract)


def _optimization_payload(proposal, snapshot_id, remaining_trials):
    proposed_count = 1
    search = proposal["parameter_search"]
    for space in search["search_space"].values():
        if not isinstance(space, dict) or set(space) != {"kind", "values"} or space["kind"] != "explicit_values":
            raise ResearchCampaignError("Agent search space must use explicit_values")
        proposed_count *= len(space["values"])
    if proposed_count > remaining_trials:
        raise ResearchCampaignError("Proposal exceeds remaining trial budget")
    return {"schema_version": "1.0.0", "name": proposal["template"]["name"] + "_campaign_search",
            "description": "Mechanical bounded search admitted by Research Campaign control.",
            "template": proposal["template"], "snapshot_id": snapshot_id,
            "parameter_roles": search["parameter_roles"], "search_space": search["search_space"],
            "budget": {"max_trials": proposed_count, "max_failed_trials": min(proposed_count, 16),
                       "stop_on_first_error": False}, "quality_gate": {},
            "candidate_ordering": "mechanical_validation_readiness_v1"}


def _existing_fingerprints(snapshot, optimization_root):
    result = set()
    if not optimization_root: return result
    for entry in snapshot.entries:
        path = Path(optimization_root) / entry.optimization_study_id / "spec.json"
        if path.is_file():
            try: result.add(structural_fingerprint(parse_template(json.loads(path.read_text())["template"])))
            except Exception: continue
    return result


def _registry_entry(trial, study, proposal, decision, development, campaign_id_value):
    evidence = {"campaign_id": campaign_id_value, "research_goal_id": decision["goal_id"],
                "research_decision_id": decision["decision_id"],
                "development_evaluation_id": development["development_evaluation_id"],
                "development_is_contaminated": True, "is_validation_evidence": False, "is_frozen_evidence": False}
    return RegistryEntry(trial.factor_instance_id, study.template_id, proposal["template"]["name"],
        dict(trial.parameters), study.snapshot_id, (trial.factor_values_id,), study.study_id, trial.trial_id,
        None, None, None, None, development["orientation"], RegistryStatus.RESEARCH_REGISTERED,
        ("agent_research_development_only", "requires_fresh_validation"), None, None,
        {"development_evaluation": hash_payload(development), "research_decision": hash_payload(decision)},
        study.template_id, ("research-campaign-v1", "adaptive-development-2025-v1"), None, evidence)


def run_campaign(goal: ResearchGoal, budget: ResearchCampaignBudget, agent, config: CampaignConfig):
    budget.validate()
    contract = snapshot_contract(config.snapshot_root, config.snapshot_id)
    if (goal.dataset_kind != contract.dataset_kind or goal.maximum_trials > budget.max_total_trials or
            goal.maximum_iterations > budget.max_iterations or goal.maximum_templates > budget.max_total_admitted_templates):
        raise ResearchCampaignError("ResearchGoal exceeds Campaign budget or dataset contract")
    if set(goal.allowed_features) - set(contract.feature_roles):
        raise ResearchCampaignError("ResearchGoal references unavailable features")
    before = load_registry_snapshot(config.registry_root, config.registry_snapshot_id)
    cid = campaign_id(goal, budget, config, agent.provider_id, agent.model_id)
    existing = Path(config.campaign_root) / "campaigns" / cid
    if existing.exists(): return validate_campaign(config.campaign_root, cid, exact_existing=True)
    journal = CampaignJournal(config.campaign_root, cid); journal.event("created", goal_id=goal.goal_id)
    files = {"goal.json": _goal_payload(goal)}; events = journal.events
    registry_fingerprints = _existing_fingerprints(before, config.existing_optimization_root)
    fingerprints = set(registry_fingerprints); entries = list(before.entries); decisions = []; admitted = failed_proposals = total_trials = failed_trials = agent_calls = 0
    stop_reason = "iteration_budget_exhausted"
    for iteration in range(1, min(goal.maximum_iterations, budget.max_iterations) + 1):
        memory = sanitize_memory(events, fingerprints); files["sanitized_memory.json"] = memory
        journal.event("iteration_started", iteration=iteration)
        request = _request(goal, memory, budget, iteration)
        response = None
        for attempt in range(budget.max_agent_repair_attempts_per_call + 1):
            if agent_calls >= budget.max_agent_calls: break
            agent_calls += 1; journal.event("agent_called", iteration=iteration, attempt=attempt)
            try:
                response = None
                response = agent.propose(request)
                decision = parse_decision(response.raw_response, iteration=iteration, goal=goal, budget=budget,
                                          provider_id=response.provider_id, model_id=response.model_id)
                break
            except AgentContractError as exc:
                evidence = {"provider_id": getattr(response, "provider_id", agent.provider_id),
                    "model_id": getattr(response, "model_id", agent.model_id),
                    "request_hash": hash_payload({"goal": request.goal, "memory": request.sanitized_memory,
                                                  "contract": request.contract})}
                if response is not None:
                    evidence["response_hash"] = hash_payload(response.raw_response)
                    evidence["usage_summary"] = response.usage_summary
                journal.event("agent_response_rejected", iteration=iteration, attempt=attempt,
                              reason=f"{type(exc).__name__}: {str(exc)[:160]}", **evidence)
                request = ResearchAgentRequest(request.goal, request.sanitized_memory,
                    {**request.contract, "repair_instruction": str(exc)[:160]})
                decision = None
        if decision is None:
            stop_reason = "agent_contract_failure"; break
        files[f"iterations/{iteration:04d}/decision.json"] = {**decision,
            "request_hash": hash_payload({"goal": request.goal, "memory": request.sanitized_memory, "contract": request.contract}),
            "response_hash": hash_payload(response.raw_response), "usage_summary": response.usage_summary}
        journal.event("decision_accepted", iteration=iteration, decision_id=decision["decision_id"])
        iteration_admitted = 0; validation_rows = []
        for proposal in decision["proposals"]:
            if admitted >= min(budget.max_total_admitted_templates, goal.maximum_templates) or failed_proposals >= budget.max_failed_proposals: break
            try:
                template = parse_template(proposal["template"])
                required = {node for node in _feature_names(proposal["template"]["expression"])}
                if required - set(goal.allowed_features): raise ResearchCampaignError("Proposal feature outside ResearchGoal")
                operators = set(_operator_names(proposal["template"]["expression"]))
                if operators - set(goal.allowed_operators): raise ResearchCampaignError("Proposal operator outside ResearchGoal")
                fingerprint = structural_fingerprint(template)
                if fingerprint in fingerprints: raise ResearchCampaignError("duplicate_structure")
                if set(proposal["parameter_search"]["parameter_roles"].values()) - set(goal.allowed_parameter_roles):
                    raise ResearchCampaignError("Proposal parameter role outside ResearchGoal")
                remaining_trials = min(budget.max_total_trials, goal.maximum_trials) - total_trials
                spec = parse_optimization_spec(_optimization_payload(proposal, config.snapshot_id, remaining_trials))
                study = plan_study(spec, contract); fingerprints.add(fingerprint); admitted += 1; iteration_admitted += 1
                total_trials += len(study.trials)
                journal.event("proposal_admitted", iteration=iteration, proposal_id=proposal["proposal_id"],
                              study_id=study.study_id, trial_count=len(study.trials))
                result = execute_study(study, contract, config.snapshot_root, config.factor_values_root, config.optimization_root)
                failed_trials += sum(trial.status.value == "failed" for trial in result.trials)
                if failed_trials > budget.max_failed_trials: raise ResearchCampaignError("failed trial budget exceeded")
                best = None; best_key = None; best_development = None
                for trial in result.trials:
                    if not trial.eligible_for_validation: continue
                    development = evaluate_development(validation_root=config.validation_root,
                        validation_dataset_id=config.validation_dataset_id, factor_values_root=config.factor_values_root,
                        factor_values_id=trial.factor_values_id)
                    metric = (development.get("development_metrics") or {}).get("mean_rank_ic")
                    key = (metric is not None, abs(metric or 0.0), -trial.ordinal)
                    if best is None or key > best_key: best, best_key, best_development = trial, key, development
                if best is None: raise ResearchCampaignError("no mechanically eligible trial")
                journal.event("development_evaluating", iteration=iteration, proposal_id=proposal["proposal_id"])
                entries.append(_registry_entry(best, study, proposal, decision, best_development, cid))
                row = {"proposal_id": proposal["proposal_id"], "status": "completed", "fingerprint": fingerprint,
                       "template_id": study.template_id, "study_id": study.study_id, "selected_trial_id": best.trial_id,
                       "factor_instance_id": best.factor_instance_id, "factor_values_id": best.factor_values_id,
                       "development": best_development}
                validation_rows.append(row); journal.event("proposal_completed", iteration=iteration,
                    proposal_id=proposal["proposal_id"],
                    development_mean_rank_ic=(best_development["development_metrics"] or {}).get("mean_rank_ic"),
                    development_rank_icir=(best_development["development_metrics"] or {}).get("rank_icir"))
            except Exception as exc:
                failed_proposals += 1; reason = str(exc)[:160]
                validation_rows.append({"proposal_id": proposal.get("proposal_id"), "status": "rejected", "reason": reason})
                journal.event("proposal_rejected", proposal_id=proposal.get("proposal_id"), reason=reason)
        files[f"iterations/{iteration:04d}/result.json"] = {"iteration": iteration, "proposals": validation_rows}
        files[f"iterations/{iteration:04d}/validation.json"] = {"iteration": iteration,
            "accepted_proposal_ids": [row["proposal_id"] for row in validation_rows if row["status"] == "completed"],
            "rejected": [{"proposal_id": row["proposal_id"], "reason": row["reason"]}
                         for row in validation_rows if row["status"] == "rejected"]}
        if decision["stop_recommendation"]: stop_reason = "agent_stop"; break
        if iteration_admitted == 0: stop_reason = "no_novelty"; break
    new_entries = entries[len(before.entries):]
    if new_entries:
        after = publish_snapshot(config.registry_output_root or config.registry_root, before.policy, entries,
                                 tuple(before.decisions), before.registry_snapshot_id)
        journal.event("registry_snapshot_published", registry_snapshot_id=after.registry_snapshot_id,
                      research_registered_added=len(new_entries))
    else:
        after = before
    campaign_status = "partial" if stop_reason == "agent_contract_failure" else "completed"
    completion_event = "partial" if campaign_status == "partial" else ("stopped_no_novelty" if stop_reason == "no_novelty" else "completed")
    journal.event(completion_event, stop_reason=stop_reason)
    result_payload = {"schema_version": "research-campaign-result-v1", "campaign_id": cid,
        "goal_id": goal.goal_id, "provider_id": agent.provider_id, "model_id": agent.model_id,
        "status": campaign_status, "stop_reason": stop_reason, "iterations": len([e for e in events if e["event_type"] == "iteration_started"]),
        "agent_calls": agent_calls, "admitted_proposals": admitted, "failed_proposals": failed_proposals,
        "total_trials": total_trials, "failed_trials": failed_trials,
        "registry_snapshot_before": before.registry_snapshot_id, "registry_snapshot_after": after.registry_snapshot_id,
        "research_registered_added": len(new_entries), "promotion_candidate_added": 0, "approved_added": 0, "active_added": 0,
        "development_is_contaminated": True, "validation_evidence_created": False, "frozen_evidence_created": False}
    files["result.json"] = {**result_payload, "result_id": "rcr_" + hash_payload(result_payload)}
    iteration_results = [value for key, value in files.items() if key.endswith("/result.json")]
    files["memory.json"] = {"schema_version": "research-campaign-memory-v1", "campaign_id": cid,
        "goal": _goal_payload(goal), "iterations": iteration_results,
        "decisions": [value["decision_id"] for key, value in files.items() if key.endswith("/decision.json")],
        "accepted_proposals": [row["proposal_id"] for result in iteration_results for row in result["proposals"] if row["status"] == "completed"],
        "rejected_proposals": [{"proposal_id": row["proposal_id"], "reason": row["reason"]}
            for result in iteration_results for row in result["proposals"] if row["status"] == "rejected"],
        "templates": [row["template_id"] for result in iteration_results for row in result["proposals"] if row["status"] == "completed"],
        "optimization_studies": [row.get("study_id") for result in iteration_results for row in result["proposals"] if row["status"] == "completed"],
        "development_results": [row["development"] for result in iteration_results for row in result["proposals"] if row["status"] == "completed"],
        "registry_snapshot_before": before.registry_snapshot_id, "registry_snapshot_after": after.registry_snapshot_id,
        "limitations": ["2025 feedback is contaminated adaptive research only", "fresh formal validation is required"],
        "stop_reason": stop_reason}
    return journal.publish(files)


def _feature_names(node):
    if isinstance(node, dict):
        if node.get("type") == "feature": yield node["name"]
        for value in node.values(): yield from _feature_names(value)
    elif isinstance(node, list):
        for value in node: yield from _feature_names(value)


def _operator_names(node):
    if isinstance(node, dict):
        kind = node.get("type")
        if kind not in {None, "feature", "parameter", "constant"}: yield kind
        for value in node.values(): yield from _operator_names(value)
    elif isinstance(node, list):
        for value in node: yield from _operator_names(value)


__all__ = ["CampaignConfig", "run_campaign", "validate_campaign"]
