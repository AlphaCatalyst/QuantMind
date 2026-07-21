from __future__ import annotations

import hashlib
import itertools
import json
import shutil
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.expanded_factor_iteration.audit import _dsl
from backend.services.engine.expanded_factor_iteration.redundancy import assess_template, equivalence_fingerprint
from backend.services.engine.factor_dsl import factor_template_id, parse_template
from backend.services.engine.momentum_factor_iteration.engine import (
    LIFECYCLE_POLICY,
    OPERATORS,
    _ast_stats,
    _clean_result,
    _correlations,
    _existing_four,
    _nearest_neighbor,
    _rank_key,
    _regime_for_result,
    _snapshot_contract,
    _summary,
    _trial_key,
)
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError
from backend.services.engine.research_campaign.models import ResearchAgentRequest, ResearchCampaignBudget, ResearchGoal
from backend.services.engine.research_campaign.orchestrator import _operator_names, _request
from backend.services.engine.factor_optimization.search_space import parse_search_space
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner,
    equal_weight_signal,
    factor_values,
    group_diagnostics,
    oriented_signal,
    split_metrics,
)
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

from .artifact import KINDS, assert_complete, publish_artifact, validate_artifact
from .protocol import (
    BUDGET,
    DATASET_KIND,
    ELIGIBILITY,
    FEATURES,
    FOLDS,
    FORMAL_STRATEGY,
    REPORT_PERIODS,
    SOURCE_CATALOG_ID,
    SOURCE_DATASET_ID,
    SOURCE_EXPERIMENT_ID,
    SUBFAMILIES,
    TASK_ID,
    UNRECOVERABLE_FACTOR_ID,
)


def _publish_store(bundle: AuthorityBundle, artifact: dict, kind: str, lineage: tuple[str, ...]) -> dict:
    field = KINDS[kind][0]
    artifact_id = artifact[field]
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), artifact_id, lineage=lineage)
    return {"artifact_kind": kind, "artifact_id": artifact_id, "descriptor_id": receipt.descriptor_id,
            "exact_existing": receipt.exact_existing, "new_blob_count": receipt.new_blob_count}


def _cold_restore(bundle: AuthorityBundle, artifact_id: str, kind: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None or descriptor.artifact_kind != kind:
        raise RuntimeError("ARTIFACT_COMPLETENESS_FAILED:published artifact unavailable")
    destination = root / kind / artifact_id
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    return validate_artifact(destination, artifact_id, kind)


def _materialize_identity(bundle: AuthorityBundle, artifact_id: str, root: Path) -> tuple[Path, dict]:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required Artifact missing: {artifact_id}")
    destination = root / descriptor.artifact_kind / artifact_id
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    return destination, manifest["identity"]


def _source_dataset(bundle: AuthorityBundle, root: Path) -> tuple[pd.DataFrame, dict]:
    destination, identity = _materialize_identity(bundle, SOURCE_DATASET_ID, root)
    if identity.get("catalog_id") != SOURCE_CATALOG_ID:
        raise RuntimeError("momentum Feature Dataset lineage mismatch")
    frame = pd.read_parquet(destination / "features.parquet")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    labels = bundle.matrix[["symbol", "trade_date", "raw_label", "model_label"]]
    matrix = frame.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    return matrix.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True), identity


def _spec(authority: dict) -> dict[str, Any]:
    stable = {
        "schema_version": "skip-recent-momentum-experiment-spec-v1", "task_id": TASK_ID,
        "provider_id": "tushare-pro-v1", "authority_record_id": authority["authority_record_id"],
        "source_experiment_id": SOURCE_EXPERIMENT_ID, "catalog_id": SOURCE_CATALOG_ID,
        "feature_dataset_id": SOURCE_DATASET_ID, "subfamilies": SUBFAMILIES, "features": FEATURES,
        "folds": list(FOLDS), "strategy": FORMAL_STRATEGY, "eligibility": ELIGIBILITY,
        "budget": BUDGET.__dict__, "final_reporting_parameter_policy": "fold_4_research_period_selected_parameters",
        "selection_period": ["2019-01-02", "2024-12-31"], "report_periods": REPORT_PERIODS,
        "runtime_mode": "store_required", "predictive_claim": False, "fresh_validation": False,
        "frozen_evidence": False, "usable_for_promotion": False, "eligible_for_production": False,
        "original_formula_and_parameters_unrecoverable": True, "previous_candidate_not_reusable": True,
    }
    return stable | {"spec_id": "srms1_" + hash_payload(stable)}


def candidate_policy(eligible: list[dict], *, maximum: int = 3) -> list[dict]:
    """Lock independently eligible structures; diversity is not a lock prerequisite."""
    selected, fingerprints = [], set()
    for item in sorted(eligible, key=_rank_key):
        fingerprint = item["structural_fingerprint"]
        if fingerprint in fingerprints: continue
        selected.append(item); fingerprints.add(fingerprint)
        if len(selected) == maximum: break
    return selected


def ensemble_allowed(locks: list[dict]) -> bool:
    return len(locks) >= 2 and len({item["subfamily"] for item in locks}) >= 2


def _agent_round(agent, goal: ResearchGoal, memory: dict, round_number: int) -> tuple[Any, Any, list[dict]]:
    budget = ResearchCampaignBudget(max_iterations=1, max_agent_calls=2, max_proposals_per_iteration=4,
        max_total_admitted_templates=3, max_total_trials=24, max_failed_proposals=4,
        max_failed_trials=16, max_agent_repair_attempts_per_call=1)
    request = _request(goal, memory, budget, 1)
    failures = []
    for attempt in range(2):
        try:
            response = agent.propose(request)
            decision = parse_decision(response.raw_response, iteration=1, goal=goal, budget=budget,
                                      provider_id=response.provider_id, model_id=response.model_id)
            return request, response, decision
        except AgentContractError as exc:
            failures.append({"attempt": attempt + 1, "error_code": type(exc).__name__, "safe_summary": str(exc)[:180]})
            if "response" in locals():
                return request, response, {"parse_failure": failures}
            request = ResearchAgentRequest(request.goal, request.sanitized_memory, request.contract | {
                "repair_instruction": {"error_code": type(exc).__name__, "safe_summary": str(exc)[:160],
                    "allowed_fix_actions": ["return complete strict JSON", "use only allowed skip-recent features",
                                            "use at most eight explicit parameter combinations"]}})
    return request, None, {"parse_failure": failures}


def _parameter_rows(proposal: dict) -> list[dict[str, float | int]]:
    spaces = proposal["parameter_search"]["search_space"]
    definitions = {item.name: item for item in parse_template(proposal["template"]).parameters}
    names = sorted(spaces)
    values = [parse_search_space(spaces[name], definitions[name]).values for name in names]
    return [dict(zip(names, row)) for row in itertools.product(*values)] or [{}]


def _trial_identity(*, spec_id: str, template_id: str, fold: dict, trial: dict, metrics: dict,
                    selected: bool, factor_value_id: str) -> dict:
    return {
        "schema_version": "factor-optimization-trial-detail-v1", "provider_id": "tushare-pro-v1",
        "spec_id": spec_id, "trial_id": trial["trial_id"], "factor_template_id": template_id,
        "research_fold": fold["fold"], "research_period": list(fold["research"]),
        "parameters": trial["parameters"], "factor_instance_id": trial["factor_instance_id"],
        "factor_value_artifact_id": factor_value_id, "trial_metrics": metrics,
        "failure_reason": None, "selected": selected, "promotion_writes": 0,
    }


def _candidate_summary(candidate: dict) -> dict:
    candidate["summary"] = _summary(candidate)
    return candidate


def _clean_report(metrics: dict, qlib: dict, regimes: dict, period: str) -> dict:
    return {
        "period": period, "metrics": metrics, "qlib": _clean_result(qlib), "regime_metrics": regimes,
        "retrospective_report_only": True, "not_used_for_selection": True, "not_fresh_validation": True,
        "fixed_100_relative_metrics_used": False,
    }


def _find_existing(bundle: AuthorityBundle, root: Path) -> tuple[Any, dict] | None:
    matches = []
    for descriptor in bundle.store.list_by_kind("skip_recent_momentum_experiment"):
        destination = root / descriptor.artifact_id
        if destination.exists(): shutil.rmtree(destination)
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        manifest = json.loads((destination / "manifest.json").read_text())
        identity = manifest["identity"]
        if identity.get("task_id") == TASK_ID and identity.get("source_experiment_id") == SOURCE_EXPERIMENT_ID:
            matches.append((descriptor, destination, identity))
    if len(matches) > 1:
        raise RuntimeError("multiple canonical skip-recent experiments")
    return None if not matches else (matches[0][0], matches[0][2])


def _prior_attempt_artifacts(bundle: AuthorityBundle, root: Path, spec_id: str) -> tuple[list[str], int, set[str], set[str]]:
    """Recover immutable artifacts from an interrupted attempt with the same spec."""
    artifact_ids, agent_calls, trial_ids, template_ids = [], 0, set(), set()
    for kind in KINDS:
        if kind in {"skip_recent_momentum_experiment", "skip_recent_momentum_candidate_lock",
                    "skip_recent_momentum_report", "skip_recent_momentum_assessment"}:
            continue
        for descriptor in bundle.store.list_by_kind(kind):
            destination = root / descriptor.artifact_id
            if destination.exists(): shutil.rmtree(destination)
            bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            if manifest["identity"].get("spec_id") == spec_id:
                validate_artifact(destination, descriptor.artifact_id, kind)
                artifact_ids.append(descriptor.artifact_id)
                agent_calls += int(kind == "research_agent_raw_response")
                if kind == "factor_optimization_trial_detail":
                    trial_ids.add(manifest["identity"]["trial_id"])
                if kind == "factor_template_definition":
                    template_ids.add(manifest["identity"]["factor_template_id"])
    return sorted(set(artifact_ids)), agent_calls, trial_ids, template_ids


def _prior_decisions(bundle: AuthorityBundle, root: Path, spec_id: str) -> dict[int, dict]:
    groups: dict[tuple[int, str], list[tuple[dict, str]]] = {}
    template_proposals = set()
    for descriptor in bundle.store.list_by_kind("factor_template_definition"):
        destination = root / "templates" / descriptor.artifact_id
        destination.parent.mkdir(parents=True, exist_ok=True)
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
        if identity.get("spec_id") == spec_id:
            template_proposals.add(identity["source_proposal_id"])
    for descriptor in bundle.store.list_by_kind("research_proposal"):
        destination = root / "proposals" / descriptor.artifact_id
        destination.parent.mkdir(parents=True, exist_ok=True)
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
        if identity.get("spec_id") != spec_id:
            continue
        key = (int(identity["round_number"]), identity["research_decision_id"])
        groups.setdefault(key, []).append((identity, descriptor.artifact_id))
    recovered = {}
    for round_number in range(1, 7):
        choices = [(sum(item[0]["proposal_id"] in template_proposals for item in rows), len(rows), decision_id, rows)
                   for (number, decision_id), rows in groups.items() if number == round_number]
        if not choices:
            continue
        _, _, decision_id, rows = max(choices, key=lambda item: (item[0], item[1], item[2]))
        recovered[round_number] = {"decision_id": decision_id,
            "proposals": [item[0]["proposal_payload"] for item in sorted(rows, key=lambda item: item[0]["proposal_id"])],
            "raw_artifact_id": rows[0][0]["source_raw_response_artifact_id"]}
    return recovered


def replay_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = load_authority_bundle(authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=Path(work_root) / "authority", store_root=store_root)
    found = _find_existing(bundle, Path(work_root) / "experiment-replay")
    if found is None: raise RuntimeError("skip-recent experiment not found")
    descriptor, identity = found
    artifact_ids = identity["artifact_ids"]
    recovered = []
    for artifact_id in artifact_ids:
        child = bundle.store.find_by_artifact_id(artifact_id)
        if child is None: raise RuntimeError("ARTIFACT_COMPLETENESS_FAILED:lineage artifact missing")
        _cold_restore(bundle, artifact_id, child.artifact_kind, Path(work_root) / "cold-replay")
        recovered.append(artifact_id)
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "experiment_id": descriptor.artifact_id, "recovered_artifact_count": len(recovered),
            "candidate_lock_ids": identity["candidate_lock_ids"], "report_ids": identity["report_ids"],
            "agent_calls": 0, "optimization_calls": 0, "qlib_calls": 0, "network_calls": 0,
            "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
            "store_integrity": integrity.status,
            "missing": sum(item.code in {"MISSING_BLOB", "CORRUPT_BLOB"} for item in integrity.issues),
            "unreferenced": len(integrity.unreferenced_blobs)}


def execute_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None,
                       agent=None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = load_authority_bundle(authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=work_root / "authority", store_root=store_root)
    existing = _find_existing(bundle, work_root / "existing")
    if existing is not None:
        return replay_experiment(repository_root=repository_root, work_root=work_root / "exact-replay", store_root=store_root) | {"exact_existing": True}
    if bundle.store.find_by_artifact_id(SOURCE_EXPERIMENT_ID) is None:
        raise RuntimeError("source momentum experiment missing")
    matrix, dataset_identity = _source_dataset(bundle, work_root / "source")
    spec = _spec(bundle.authority)
    contract = _snapshot_contract(SOURCE_DATASET_ID, sorted({f for values in FEATURES.values() for f in values}), matrix["trade_date"].nunique())
    regimes, regime_contract = build_regimes(bundle.normalized, bundle.benchmark)
    old_four, existing_evidence, old_three = _existing_four(bundle, work_root / "comparison")
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    # The repository's Qlib/MLflow stack still imports pkg_resources.  The
    # compatibility module is process-local, so keep Qlib feature loading in
    # this process instead of spawning workers that cannot inherit sys.modules.
    qlib.service.initialize()
    from qlib.config import C
    C.kernels = 1
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    artifact_root, cold_root = work_root / "domain", work_root / "stage-cold"
    prior_artifact_ids, prior_agent_calls, prior_trial_ids, prior_template_ids = _prior_attempt_artifacts(
        bundle, work_root / "prior-attempt", spec["spec_id"])
    prior_decisions = _prior_decisions(bundle, work_root / "prior-decisions", spec["spec_id"])
    published, all_artifact_ids, all_candidates, round_results = [], list(prior_artifact_ids), [], []
    known_structural, known_equivalent, prior_feedback = set(), set(), []
    total_calls, total_trials, total_templates = prior_agent_calls, len(prior_trial_ids), len(prior_template_ids)

    historical_memory = {"family": "skip_recent_momentum", "standalone_eligibility_previously_observed": True,
        "parameter_stability_previously_observed": 1.0, "median_turnover_approx": 28.19,
        "median_best_10_days_contribution_approx": 0.324, "maximum_old_factor_correlation_approx": 0.098,
        "original_formula_and_parameters_unrecoverable": True, "previous_candidate_not_reusable": True}

    for round_number in range(1, 7):
        if total_calls >= BUDGET.max_total_agent_calls:
            raise RuntimeError("Agent call budget exhausted by persisted attempts")
        subfamily, allowed = SUBFAMILIES[round_number], FEATURES[round_number]
        memory = {"schema_version": "skip-recent-agent-memory-v1", "visibility_cutoff": "2024-12-31",
                  "historical_summary": historical_memory, "prior_round_aggregate_feedback": prior_feedback,
                  "daily_labels_included": False, "daily_ic_included": False,
                  "later_period_feedback_included": False, "fixed_100_relative_metrics_included": False}
        goal = ResearchGoal("srg1_" + hash_payload({"spec": spec["spec_id"], "round": round_number}),
            f"skip_recent_{subfamily}",
            f"Propose structurally distinct {subfamily} factors. Every proposal must use at least one momentum_20_5, momentum_60_5, momentum_60_10, momentum_120_20 or momentum_180_20 terminal when available; combine only with assigned features. Optimize factor parameters, not strategy settings.",
            DATASET_KIND, tuple(allowed), OPERATORS, ("lookback_window", "factor_internal_weight"),
            3, 24, 1, "not a name-only or window-only duplicate",
            ("one to three terminals", "at most three parameters and AST depth seven",
             "no labels, financial data, regime input, strategy parameter or later-period evidence",
             "use explicit_values with no more than eight Cartesian combinations"))
        if round_number in prior_decisions:
            decision = prior_decisions[round_number]
            decision_id, raw_id = decision["decision_id"], decision["raw_artifact_id"]
        else:
            request, response, decision = _agent_round(agent, goal, memory, round_number)
            if response is None: raise RuntimeError("Agent failed before producing a persistable response")
            total_calls += 1
            request_bytes = json.dumps({"goal": request.goal, "memory": request.sanitized_memory, "contract": request.contract},
                                       ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
            raw_bytes = response.raw_response.encode("utf-8")
            decision_id = decision.get("decision_id") if isinstance(decision, dict) else None
            call_id = "sac1_" + hash_payload({"spec_id": spec["spec_id"], "round": round_number, "prompt_hash": hashlib.sha256(request_bytes).hexdigest(), "response_hash": hashlib.sha256(raw_bytes).hexdigest()})
            raw_identity = {"schema_version": "research-agent-raw-response-v1", "provider_id": "tushare-pro-v1",
                "spec_id": spec["spec_id"], "round_number": round_number, "agent_call_id": call_id,
                "provider": response.provider_id, "model": response.model_id,
                "prompt_hash": hashlib.sha256(request_bytes).hexdigest(), "raw_response_blob_id": "blob_sha256_" + hashlib.sha256(raw_bytes).hexdigest(),
                "raw_response_hash": hashlib.sha256(raw_bytes).hexdigest(), "response_size_bytes": len(raw_bytes),
                "research_decision_id": decision_id, "usage_summary": response.usage_summary,
                "secrets_persisted": False, "promotion_writes": 0}
            assert_complete("research_agent_raw_response", raw_identity)
            raw_artifact = publish_artifact(artifact_root, "research_agent_raw_response", raw_identity, {"raw_response.json": raw_bytes})
            published.append(_publish_store(bundle, raw_artifact, "research_agent_raw_response", (SOURCE_EXPERIMENT_ID,)))
            raw_id = raw_artifact["raw_response_artifact_id"]; all_artifact_ids.append(raw_id)
            _cold_restore(bundle, raw_id, "research_agent_raw_response", cold_root)
        if "parse_failure" in decision:
            round_results.append({"round": round_number, "subfamily": subfamily, "agent_calls": 1, "proposals": 0, "admitted": 0, "trials": 0, "failure": decision["parse_failure"]})
            prior_feedback.append(round_results[-1]); continue

        admitted, rejected, round_trials = [], [], 0
        for proposal in decision["proposals"]:
            proposal_identity = {"schema_version": "research-proposal-v1", "provider_id": "tushare-pro-v1",
                "spec_id": spec["spec_id"], "round_number": round_number, "subfamily": subfamily,
                "research_decision_id": decision_id, "source_raw_response_artifact_id": raw_id,
                "proposal_id": proposal["proposal_id"], "proposal_payload": proposal,
                "rationale": proposal["rationale"], "promotion_writes": 0}
            proposal_artifact = publish_artifact(artifact_root, "research_proposal", proposal_identity, {"proposal.json": proposal_identity})
            published.append(_publish_store(bundle, proposal_artifact, "research_proposal", (raw_id,)))
            proposal_artifact_id = proposal_artifact["proposal_artifact_id"]; all_artifact_ids.append(proposal_artifact_id)
            _cold_restore(bundle, proposal_artifact_id, "research_proposal", cold_root)
            try:
                if len(admitted) >= 3: raise ValueError("round_admission_budget")
                template = parse_template(proposal["template"])
                template_id = factor_template_id(template)
                template_is_prior = template_id in prior_template_ids
                if not template_is_prior and total_templates >= BUDGET.max_total_templates:
                    raise ValueError("total_template_budget_exceeded")
                depth, input_features, parameters = _ast_stats(proposal["template"]["expression"])
                skip_features = {"momentum_20_5", "momentum_60_5", "momentum_60_10", "momentum_120_20", "momentum_180_20"}
                if not (input_features & skip_features) or input_features - set(allowed): raise ValueError("skip_recent_feature_contract")
                if len(input_features) > 3 or depth > 7 or len(parameters) > 3: raise ValueError("proposal_complexity_gate")
                if set(_operator_names(proposal["template"]["expression"])) - set(OPERATORS): raise ValueError("operator_outside_contract")
                redundancy = assess_template(proposal["template"], known_structural=known_structural, known_equivalent=known_equivalent)
                if not redundancy["admitted"]: raise ValueError(redundancy["rejection_reason"])
                rows = _parameter_rows(proposal)
                additional_trial_count = 0 if template_is_prior else len(rows)
                if len(rows) > 8 or round_trials + additional_trial_count > 24 or total_trials + additional_trial_count > 144: raise ValueError("trial_budget_exceeded")
                template_identity = {"schema_version": "factor-template-definition-v1", "provider_id": "tushare-pro-v1",
                    "spec_id": spec["spec_id"], "factor_template_id": template_id,
                    "template_name": proposal["template"]["name"], "canonical_dsl": _dsl(proposal["template"]["expression"]),
                    "canonical_ast": proposal["template"]["expression"], "input_features": sorted(input_features),
                    "parameter_schema": proposal["template"]["parameters"], "orientation_policy": "research_period_mean_rankic_sign",
                    "structural_fingerprint": redundancy["structural_fingerprint"], "economic_hypothesis": proposal["rationale"],
                    "source_proposal_id": proposal["proposal_id"], "source_proposal_artifact_id": proposal_artifact_id,
                    "subfamily": subfamily, "promotion_writes": 0}
                template_artifact = publish_artifact(artifact_root, "factor_template_definition", template_identity, {"template.json": template_identity})
                published.append(_publish_store(bundle, template_artifact, "factor_template_definition", (proposal_artifact_id,)))
                template_definition_id = template_artifact["template_definition_id"]; all_artifact_ids.append(template_definition_id)
                _cold_restore(bundle, template_definition_id, "factor_template_definition", cold_root)
                trials, values_by_instance = [], {}
                for ordinal, parameters_row in enumerate(rows, 1):
                    compiled, values = factor_values(template, contract, parameters_row, matrix)
                    values_by_instance[compiled.factor_instance_id] = values
                    trials.append({"trial_id": "srmt1_" + hash_payload({"spec": spec["spec_id"], "template": compiled.template_id, "parameters": parameters_row}),
                                   "ordinal": ordinal, "factor_instance_id": compiled.factor_instance_id, "parameters": parameters_row})
                folds, neighborhood_rows, trial_detail_ids, fold_lock_ids = [], [], [], []
                for fold in FOLDS:
                    researched = []
                    for trial in trials:
                        raw = split_metrics(values_by_instance[trial["factor_instance_id"]], matrix, fold["research"][0], fold["research"][1], 1)
                        orientation = 1 if (raw.get("mean_rank_ic") or 0) >= 0 else -1
                        metrics = split_metrics(values_by_instance[trial["factor_instance_id"]], matrix, fold["research"][0], fold["research"][1], orientation)
                        researched.append(trial | {"orientation": orientation, "research_metrics": metrics})
                    selected = max(researched, key=_trial_key)
                    for trial in researched:
                        values = values_by_instance[trial["factor_instance_id"]]
                        value_path = work_root / "trial-values" / f"fold-{fold['fold']}" / f"{trial['trial_id']}.parquet"
                        value_path.parent.mkdir(parents=True, exist_ok=True); values.to_parquet(value_path, index=False, compression="zstd")
                        factor_value_id = "sfv1_" + hash_payload({"instance": trial["factor_instance_id"], "dataset": SOURCE_DATASET_ID, "sha256": hash_file(value_path)})
                        identity = _trial_identity(spec_id=spec["spec_id"], template_id=factor_template_id(template), fold=fold,
                                                   trial=trial, metrics=trial["research_metrics"], selected=trial["trial_id"] == selected["trial_id"],
                                                   factor_value_id=factor_value_id)
                        artifact = publish_artifact(artifact_root, "factor_optimization_trial_detail", identity,
                                                   {"trial.json": identity, "factor_values.parquet": value_path})
                        published.append(_publish_store(bundle, artifact, "factor_optimization_trial_detail", (template_definition_id, SOURCE_DATASET_ID)))
                        detail_id = artifact["trial_detail_id"]; trial_detail_ids.append(detail_id); all_artifact_ids.append(detail_id)
                        _cold_restore(bundle, detail_id, "factor_optimization_trial_detail", cold_root)
                        trial["factor_value_artifact_id"] = factor_value_id
                        trial["trial_detail_id"] = detail_id
                        original_trial = next(item for item in trials if item["trial_id"] == trial["trial_id"])
                        original_trial["factor_value_artifact_id"] = factor_value_id
                        original_trial["trial_detail_id"] = detail_id
                    selected_values = values_by_instance[selected["factor_instance_id"]]
                    signal_path = oriented_signal(selected_values, selected["orientation"], work_root / "fold-signals" / f"{selected['trial_id']}-fold{fold['fold']}.parquet")
                    unified_signal_id = "susi1_" + hash_payload({"factor_instance_id": selected["factor_instance_id"], "orientation": selected["orientation"], "signal_sha256": hash_file(signal_path)})
                    selected_trial = next(item for item in trials if item["trial_id"] == selected["trial_id"])
                    fold_identity = {"schema_version": "factor-fold-candidate-lock-v1", "provider_id": "tushare-pro-v1",
                        "spec_id": spec["spec_id"], "fold_id": f"fold-{fold['fold']}", "research_period": list(fold["research"]),
                        "evaluation_period": list(fold["evaluation"]), "selected_trial_id": selected["trial_id"],
                        "selected_trial_detail_id": selected_trial["trial_detail_id"], "selected_parameters": selected["parameters"],
                        "factor_instance_id": selected["factor_instance_id"], "factor_value_artifact_id": selected_trial["factor_value_artifact_id"],
                        "orientation": selected["orientation"], "unified_signal_id": unified_signal_id,
                        "selection_metrics": selected["research_metrics"], "selection_locked_before_evaluation": True,
                        "promotion_writes": 0}
                    fold_artifact = publish_artifact(artifact_root, "factor_fold_candidate_lock", fold_identity,
                        {"fold_lock.json": fold_identity, "signal.parquet": signal_path})
                    published.append(_publish_store(bundle, fold_artifact, "factor_fold_candidate_lock", (selected_trial["trial_detail_id"],)))
                    fold_lock_id = fold_artifact["fold_lock_id"]; fold_lock_ids.append(fold_lock_id); all_artifact_ids.append(fold_lock_id)
                    _cold_restore(bundle, fold_lock_id, "factor_fold_candidate_lock", cold_root)
                    evaluation_metrics = split_metrics(selected_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"])
                    diagnostics = group_diagnostics(selected_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"])
                    raw_qlib = qlib.run(signal_path, fold["evaluation"][0], fold["evaluation"][1], lifecycle_policy=LIFECYCLE_POLICY)
                    neighbor_details = []
                    for neighbor in researched:
                        if neighbor["trial_id"] == selected["trial_id"]: continue
                        differing = sum(neighbor["parameters"].get(name) != selected["parameters"].get(name) for name in set(neighbor["parameters"]) | set(selected["parameters"]))
                        if differing != 1: continue
                        neighbor_values = values_by_instance[neighbor["factor_instance_id"]]
                        neighbor_metrics = split_metrics(neighbor_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"])
                        neighbor_signal = oriented_signal(neighbor_values, selected["orientation"], work_root / "neighbor-signals" / f"{neighbor['trial_id']}-fold{fold['fold']}.parquet")
                        neighbor_qlib = qlib.run(neighbor_signal, fold["evaluation"][0], fold["evaluation"][1], lifecycle_policy=LIFECYCLE_POLICY)
                        direction_same = neighbor_metrics.get("mean_rank_ic") is not None and evaluation_metrics.get("mean_rank_ic") is not None and neighbor_metrics["mean_rank_ic"] * evaluation_metrics["mean_rank_ic"] >= 0
                        excess_ok = neighbor_qlib.get("net_excess_csi300") is not None and raw_qlib.get("net_excess_csi300") is not None and neighbor_qlib["net_excess_csi300"] >= raw_qlib["net_excess_csi300"] - 0.15
                        neighbor_details.append({"neighbor_trial_id": neighbor["trial_id"], "neighbor_parameters": neighbor["parameters"],
                            "neighbor_rank_ic": neighbor_metrics.get("mean_rank_ic"), "neighbor_csi300_excess": neighbor_qlib.get("net_excess_csi300"),
                            "neighbor_turnover": neighbor_qlib.get("turnover"), "neighbor_gate_result": bool(direction_same and excess_ok)})
                    if not neighbor_details:
                        neighbor_details.append({"neighbor_trial_id": None, "neighbor_parameters": None, "neighbor_rank_ic": None,
                            "neighbor_csi300_excess": None, "neighbor_turnover": None, "neighbor_gate_result": False,
                            "reason": "no_direct_neighbor"})
                    neighborhood_rows.append({"fold": fold["fold"], "selected_trial_id": selected["trial_id"], "neighbors": neighbor_details,
                                              "stable": all(row["neighbor_gate_result"] for row in neighbor_details)})
                    folds.append({"fold_number": fold["fold"], "research_period": list(fold["research"]), "evaluation_period": list(fold["evaluation"]),
                        "fold_lock_id": fold_lock_id, "selected_trial_id": selected["trial_id"], "factor_instance_id": selected["factor_instance_id"],
                        "selected_parameters": selected["parameters"], "orientation": selected["orientation"],
                        "metrics": evaluation_metrics | diagnostics, "qlib": _clean_result(raw_qlib),
                        "regime_metrics": _regime_for_result(selected_values, matrix, fold["evaluation"][0], fold["evaluation"][1], selected["orientation"], raw_qlib, regimes)})
                final = folds[-1]; final_values = values_by_instance[final["factor_instance_id"]]
                final_signal = oriented_signal(final_values, final["orientation"], work_root / "candidate-signals" / f"{final['factor_instance_id']}.parquet")
                maximum_correlation, correlations = _correlations(pd.read_parquet(final_signal), old_four)
                finite = pd.to_numeric(final_values["factor_value"], errors="coerce")
                valid_neighbors = [n for row in neighborhood_rows for n in row["neighbors"] if n["neighbor_trial_id"] is not None]
                stable_neighbors = [n for n in valid_neighbors if n["neighbor_gate_result"]]
                candidate = {"round_number": round_number, "proposal_id": proposal["proposal_id"], "subfamily": subfamily,
                    "factor_family": "skip_recent_momentum", "families": ["skip_recent_momentum"],
                    "factor_template_id": factor_template_id(template), "template_definition_id": template_definition_id,
                    "template_name": proposal["template"]["name"], "template": proposal["template"],
                    "canonical_dsl": template_identity["canonical_dsl"], "canonical_ast": template_identity["canonical_ast"],
                    "input_features": sorted(input_features), "parameter_schema": proposal["template"]["parameters"],
                    "factor_instance_id": final["factor_instance_id"], "selected_trial_id": final["selected_trial_id"],
                    "final_reporting_parameters": final["selected_parameters"], "orientation": final["orientation"], "values_are_oriented": False,
                    "factor_value_artifact_id": next(t["factor_value_artifact_id"] for t in trials if t["trial_id"] == final["selected_trial_id"]),
                    "unified_signal_id": "susi1_" + hash_payload({"factor_instance_id": final["factor_instance_id"], "orientation": final["orientation"], "signal_sha256": hash_file(final_signal)}),
                    "signal_path": str(final_signal), "folds": folds, "fold_lock_ids": fold_lock_ids, "trial_detail_ids": trial_detail_ids,
                    "finite_coverage": float(finite.notna().mean()), "infinity_count": int(np.isinf(finite.to_numpy(dtype=float, na_value=np.nan)).sum()),
                    "pit_violation_count": 0, "maximum_existing_factor_correlation": maximum_correlation,
                    "existing_factor_correlations": correlations,
                    "parameter_neighborhood": {"evaluated_neighbor_count": len(valid_neighbors),
                        "stable_neighbor_count": len(stable_neighbors),
                        "stability_rate": len(stable_neighbors) / len(valid_neighbors) if valid_neighbors else 0.0,
                        "folds": neighborhood_rows},
                    "structural_fingerprint": redundancy["structural_fingerprint"], "equivalence_fingerprint": redundancy["equivalence_fingerprint"],
                    "ast_depth": depth, "economic_hypothesis": proposal["rationale"]}
                _candidate_summary(candidate)
                evidence_identity = {"schema_version": "factor-candidate-eligibility-evidence-v1", "provider_id": "tushare-pro-v1",
                    "spec_id": spec["spec_id"], "factor_template_id": factor_template_id(template), "factor_instance_id": candidate["factor_instance_id"],
                    "four_fold_metrics": folds, "parameter_neighborhood_results": neighborhood_rows,
                    "turnover": candidate["summary"]["median_turnover"], "transaction_cost": candidate["summary"]["median_transaction_cost"],
                    "best_10_days_contribution": candidate["summary"]["median_best10_contribution"],
                    "return_without_best_10_days": candidate["summary"]["median_return_without_best10"],
                    "old_factor_correlations": correlations, "regime_metrics": [f["regime_metrics"] for f in folds],
                    "gate_results": candidate["summary"]["eligibility_checks"], "gate_failure_reasons": candidate["summary"]["eligibility_failures"],
                    "standalone_eligible": candidate["summary"]["eligible"], "promotion_writes": 0}
                evidence_artifact = publish_artifact(artifact_root, "factor_candidate_eligibility_evidence", evidence_identity,
                                                     {"eligibility.json": evidence_identity})
                published.append(_publish_store(bundle, evidence_artifact, "factor_candidate_eligibility_evidence", tuple(fold_lock_ids)))
                evidence_id = evidence_artifact["eligibility_evidence_id"]; all_artifact_ids.append(evidence_id)
                _cold_restore(bundle, evidence_id, "factor_candidate_eligibility_evidence", cold_root)
                candidate["eligibility_evidence_id"] = evidence_id
                admitted.append(candidate); all_candidates.append(candidate)
                known_structural.add(redundancy["structural_fingerprint"]); known_equivalent.add(redundancy["equivalence_fingerprint"])
                total_trials += additional_trial_count; round_trials += additional_trial_count
                total_templates += int(not template_is_prior)
            except Exception as exc:
                rejected.append({"proposal_id": proposal["proposal_id"], "reason": f"{type(exc).__name__}:{str(exc)[:180]}"})
        ranked_round = sorted(admitted, key=_rank_key)
        feedback = {"round": round_number, "subfamily": subfamily, "agent_calls": 1, "proposals": len(decision["proposals"]),
                    "admitted": len(admitted), "trials": round_trials, "rejected": rejected,
                    "eligible": sum(c["summary"]["eligible"] for c in admitted),
                    "best": None if not ranked_round else {"factor_instance_id": ranked_round[0]["factor_instance_id"], **ranked_round[0]["summary"]}}
        round_results.append(feedback); prior_feedback.append(feedback)

    eligible = [candidate for candidate in all_candidates if candidate["summary"]["eligible"]]
    selected = candidate_policy(eligible)
    locks, lock_ids = [], []
    for candidate in selected:
        lock_identity = {"schema_version": "skip-recent-momentum-candidate-lock-v1", "provider_id": "tushare-pro-v1",
            "spec_id": spec["spec_id"], "factor_template_id": candidate["factor_template_id"],
            "factor_instance_id": candidate["factor_instance_id"], "template_name": candidate["template_name"],
            "subfamily": candidate["subfamily"], "canonical_dsl": candidate["canonical_dsl"], "canonical_ast": candidate["canonical_ast"],
            "input_features": candidate["input_features"], "parameter_schema": candidate["parameter_schema"],
            "fold_selected_trials": [f["selected_trial_id"] for f in candidate["folds"]],
            "fold_selected_parameters": [f["selected_parameters"] for f in candidate["folds"]],
            "final_reporting_parameters": candidate["final_reporting_parameters"], "final_reporting_parameter_policy": "fold_4_research_period_selected_parameters",
            "orientation": candidate["orientation"], "values_are_oriented": False,
            "factor_value_artifact_id": candidate["factor_value_artifact_id"], "unified_signal_id": candidate["unified_signal_id"],
            "four_fold_metrics": candidate["folds"], "parameter_neighborhood_results": candidate["parameter_neighborhood"]["folds"],
            "turnover": candidate["summary"]["median_turnover"], "cost": candidate["summary"]["median_transaction_cost"],
            "concentration": candidate["summary"]["median_best10_contribution"], "old_factor_correlations": candidate["existing_factor_correlations"],
            "structural_fingerprint": candidate["structural_fingerprint"], "economic_hypothesis": candidate["economic_hypothesis"],
            "eligibility_evidence_id": candidate["eligibility_evidence_id"], "fixed_strategy_contract": FORMAL_STRATEGY,
            "status": "research_registered", "predictive_claim": False, "fresh_validation": False,
            "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0}
        lock_artifact = publish_artifact(artifact_root, "skip_recent_momentum_candidate_lock", lock_identity,
                                         {"candidate.json": lock_identity, "signal.parquet": Path(candidate["signal_path"])})
        published.append(_publish_store(bundle, lock_artifact, "skip_recent_momentum_candidate_lock", (candidate["eligibility_evidence_id"],)))
        lock_id = lock_artifact["candidate_lock_id"]; all_artifact_ids.append(lock_id); lock_ids.append(lock_id)
        _cold_restore(bundle, lock_id, "skip_recent_momentum_candidate_lock", cold_root)
        locks.append({"candidate_lock_id": lock_id, "subfamily": candidate["subfamily"], "candidate": candidate})

    reports, report_ids = {}, []
    for locked in locks:
        candidate = locked["candidate"]; values = pd.read_parquet(candidate["signal_path"]).rename(columns={"pred": "factor_value"})
        values["factor_value"] = values["factor_value"] / candidate["orientation"]
        reports[locked["candidate_lock_id"]] = {}
        for label, period in REPORT_PERIODS.items():
            signal_path = Path(candidate["signal_path"])
            metrics = split_metrics(values, matrix, period[0], period[1], candidate["orientation"])
            qlib_result = qlib.run(signal_path, period[0], period[1], lifecycle_policy=LIFECYCLE_POLICY)
            regime = _regime_for_result(values, matrix, period[0], period[1], candidate["orientation"], qlib_result, regimes)
            report = _clean_report(metrics, qlib_result, regime, label)
            report_identity = {"schema_version": "skip-recent-momentum-report-v1", "provider_id": "tushare-pro-v1",
                "spec_id": spec["spec_id"], "candidate_lock_id": locked["candidate_lock_id"], "factor_instance_id": candidate["factor_instance_id"],
                "period": label, "date_range": list(period), "report": report, "selection_data_end": "2024-12-31",
                "retrospective_report_only": True, "not_used_for_selection": True, "not_fresh_validation": True,
                "predictive_claim": False, "promotion_writes": 0}
            artifact = publish_artifact(artifact_root, "skip_recent_momentum_report", report_identity, {"report.json": report_identity})
            published.append(_publish_store(bundle, artifact, "skip_recent_momentum_report", (locked["candidate_lock_id"],)))
            report_id = artifact["report_id"]; report_ids.append(report_id); all_artifact_ids.append(report_id)
            _cold_restore(bundle, report_id, "skip_recent_momentum_report", cold_root)
            reports[locked["candidate_lock_id"]][label] = {"report_id": report_id, **report}

    ensemble = {"ensemble_eligible": ensemble_allowed(locks), "ensemble_id": None, "results": {}}
    if ensemble["ensemble_eligible"]:
        paths = {item["candidate_lock_id"]: Path(item["candidate"]["signal_path"]) for item in locks}
        ensemble_path = equal_weight_signal(paths, work_root / "ensemble" / "signal.parquet")
        ensemble["ensemble_id"] = "srmen1_" + hash_payload({"locks": lock_ids, "signal_sha256": hash_file(ensemble_path)})
        for label, period in REPORT_PERIODS.items():
            ensemble["results"][label] = _clean_result(qlib.run(ensemble_path, period[0], period[1], lifecycle_policy=LIFECYCLE_POLICY))

    comparison = {"source_unrecoverable_candidate": {"factor_instance_id": UNRECOVERABLE_FACTOR_ID,
        "definition_status": "definition_unrecoverable", "replay_status": "not_replayable",
        "summary": {"median_turnover": 28.18944634585454, "median_best10_contribution": 0.3239726918487068,
                    "maximum_old_factor_correlation": 0.09840578675715633}},
        "old_three_source_artifact_id": existing_evidence["old_three_source"], "r1_experiment_id": existing_evidence["r1_experiment_id"],
        "r1_candidate_lock_id": existing_evidence["r1_candidate_lock_id"],
        "old_three_annual_backtests": {name: values for name, values in existing_evidence["old_results"].get("annual_backtests", {}).items() if name in {*old_three, "equal_weight_combo"}},
        "new_candidates": {item["candidate_lock_id"]: {"four_fold": item["candidate"]["folds"], "reports": reports[item["candidate_lock_id"]]} for item in locks},
        "strategy_contract": FORMAL_STRATEGY, "fixed_100_relative_metrics_used": False}
    assessment_identity = {"schema_version": "skip-recent-momentum-assessment-v1", "provider_id": "tushare-pro-v1",
        "spec_id": spec["spec_id"], "round_results": round_results, "explored_subfamilies": sorted({c["subfamily"] for c in all_candidates}),
        "candidate_count": len(all_candidates), "eligible_candidate_count": len(eligible), "candidate_lock_ids": lock_ids,
        "ensemble": ensemble, "agent_calls": total_calls, "optimization_trials": total_trials, "qlib_calls": qlib.calls,
        "network_calls": 0, "strategy_optimization_calls": 0, "promotion_writes": 0}
    assessment_artifact = publish_artifact(artifact_root, "skip_recent_momentum_assessment", assessment_identity,
                                           {"assessment.json": assessment_identity, "comparison.json": comparison})
    published.append(_publish_store(bundle, assessment_artifact, "skip_recent_momentum_assessment", tuple(lock_ids + report_ids)))
    assessment_id = assessment_artifact["assessment_id"]; all_artifact_ids.append(assessment_id)
    _cold_restore(bundle, assessment_id, "skip_recent_momentum_assessment", cold_root)
    experiment_identity = {"schema_version": "skip-recent-momentum-experiment-v1", "task_id": TASK_ID, "provider_id": "tushare-pro-v1",
        "spec_id": spec["spec_id"], "source_experiment_id": SOURCE_EXPERIMENT_ID, "catalog_id": SOURCE_CATALOG_ID,
        "feature_dataset_id": SOURCE_DATASET_ID, "artifact_ids": all_artifact_ids, "candidate_lock_ids": lock_ids,
        "report_ids": report_ids, "assessment_id": assessment_id,
        "execution_counts": {"agent_calls": total_calls, "optimization_trials": total_trials, "qlib_calls": qlib.calls,
                             "network_calls": 0, "strategy_optimization_calls": 0},
        "original_experiment_final_locks": 0, "original_experiment_unchanged": True,
        "prior_interrupted_attempt_artifact_ids": prior_artifact_ids,
        "predictive_claim": False, "fresh_validation": False, "usable_for_promotion": False,
        "eligible_for_production": False, "promotion_writes": 0}
    experiment_artifact = publish_artifact(artifact_root, "skip_recent_momentum_experiment", experiment_identity,
        {"spec.json": spec, "summary.json": {"round_results": round_results, "candidate_lock_ids": lock_ids,
          "report_ids": report_ids, "ensemble": ensemble, "registry": {"entries": [{"candidate_lock_id": i, "status": "research_registered"} for i in lock_ids],
          "promotion_candidates": [], "approved": [], "active": []}, "comparison": comparison}})
    published.append(_publish_store(bundle, experiment_artifact, "skip_recent_momentum_experiment", tuple(all_artifact_ids)))
    experiment_id = experiment_artifact["experiment_id"]
    _cold_restore(bundle, experiment_id, "skip_recent_momentum_experiment", cold_root)
    all_artifact_ids.append(experiment_id)
    integrity = scan_store_integrity(bundle.store)
    inventory = publish_inventory(bundle.store)
    return {"status": "completed", "experiment_id": experiment_id, "spec_id": spec["spec_id"],
        "round_results": round_results, "candidate_lock_ids": lock_ids, "report_ids": report_ids,
        "eligible_candidate_count": len(eligible), "ensemble": ensemble, "assessment_id": assessment_id,
        "agent_calls": total_calls, "admitted_templates": total_templates, "factor_optimization_trials": total_trials,
        "qlib_calls": qlib.calls, "network_calls": 0, "strategy_optimization_calls": 0, "promotion_writes": 0,
        "artifact_count": len(bundle.store.list_all()), "blob_count": sum(1 for p in bundle.store.config.root.joinpath("objects", "sha256").rglob("*") if p.is_file()),
        "store_integrity": integrity.status,
        "missing": sum(item.code in {"MISSING_BLOB", "CORRUPT_BLOB"} for item in integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs),
        "inventory_id": inventory.inventory_id, "published": published, "exact_existing": False}
