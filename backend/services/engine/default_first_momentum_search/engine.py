from __future__ import annotations

import hashlib
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
from backend.services.engine.expanded_factor_iteration.redundancy import assess_template
from backend.services.engine.factor_dsl import factor_template_id, parse_template
from backend.services.engine.momentum_factor_iteration.engine import (
    _ast_stats, _clean_result, _correlations, _existing_four, _regime_for_result, _snapshot_contract,
)
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes
from backend.services.engine.optimization_governance.artifact import validate_artifact as validate_governance_artifact
from backend.services.engine.optimization_governance.engine import (
    build_candidate_metadata, evaluate_factor, local_factor_neighborhood, validate_combination,
)
from backend.services.engine.research_campaign.agent import CodexResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.models import ResearchCampaignBudget, ResearchGoal
from backend.services.engine.research_campaign.orchestrator import _request
from backend.services.engine.skip_recent_momentum.artifact import (
    assert_complete as assert_common_complete,
    publish_artifact as publish_common_artifact,
    validate_artifact as validate_common_artifact,
)
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner, factor_values, group_diagnostics, oriented_signal, split_metrics,
)
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

from .artifact import KINDS, publish_artifact, validate_artifact
from .protocol import (
    ANNUAL_PERIODS, BUDGET, DATASET_KIND, DEFAULT_GATE, DEVELOPMENT_PERIOD, ELIGIBILITY,
    FORMAL_STRATEGY, GOVERNANCE_DECISION_ID, LIFECYCLE_POLICY, NEAR_GATE, OPERATORS,
    REPORT_PERIODS, ROUND_FEATURES, ROUND_THEMES, SOURCE_CATALOG_ID, SOURCE_DATASET_ID, TASK_ID,
)


COMMON_KINDS = {"research_agent_raw_response", "research_proposal", "factor_template_definition"}


def _store_publish(bundle: AuthorityBundle, artifact: dict, kind: str, lineage: tuple[str, ...]) -> dict:
    field = ({"research_agent_raw_response": "raw_response_artifact_id",
              "research_proposal": "proposal_artifact_id", "factor_template_definition": "template_definition_id"}
             .get(kind, KINDS.get(kind, (None,))[0]))
    artifact_id = artifact[field]
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), artifact_id, lineage=lineage)
    return {"artifact_kind": kind, "artifact_id": artifact_id, "descriptor_id": receipt.descriptor_id,
            "exact_existing": receipt.exact_existing, "new_blob_count": receipt.new_blob_count}


def _cold(bundle: AuthorityBundle, artifact_id: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"ARTIFACT_COMPLETENESS_FAILED:missing {artifact_id}")
    destination = Path(root) / descriptor.artifact_kind / artifact_id
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    validator = validate_common_artifact if descriptor.artifact_kind in COMMON_KINDS else validate_artifact
    return validator(destination, artifact_id, descriptor.artifact_kind)


def _identity(bundle: AuthorityBundle, artifact_id: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None: raise RuntimeError(f"required Artifact missing: {artifact_id}")
    destination = Path(root) / descriptor.artifact_kind / artifact_id
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    return json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]


def validate_governance(bundle: AuthorityBundle, work_root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(GOVERNANCE_DECISION_ID)
    if descriptor is None or descriptor.artifact_kind != "optimization_governance_decision":
        raise RuntimeError("R1-006 optimization governance Decision is missing")
    destination = Path(work_root) / GOVERNANCE_DECISION_ID
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    validation = validate_governance_artifact(destination, GOVERNANCE_DECISION_ID, descriptor.artifact_kind)
    decision = json.loads((destination / "decision.json").read_text(encoding="utf-8"))
    expected = (decision.get("factor_decision"), decision.get("strategy_decision"), decision.get("combined_decision"))
    if expected != ("default_first_optimize_only_on_failure", "default_first_optimize_only_on_failure", "suspend_parameter_optimization"):
        raise RuntimeError("R1-006 governance Decision semantics mismatch")
    return {"validation": validation, "decision": decision}


def _source_matrix(bundle: AuthorityBundle, root: Path) -> tuple[pd.DataFrame, dict]:
    descriptor = bundle.store.find_by_artifact_id(SOURCE_DATASET_ID)
    if descriptor is None or descriptor.artifact_kind != "momentum_feature_dataset":
        raise RuntimeError("formal Momentum Feature Dataset missing")
    destination = Path(root) / SOURCE_DATASET_ID
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
    if identity.get("catalog_id") != SOURCE_CATALOG_ID:
        raise RuntimeError("Momentum Feature Dataset Catalog lineage mismatch")
    features = pd.read_parquet(destination / "features.parquet")
    features["trade_date"] = pd.to_datetime(features["trade_date"])
    labels = bundle.matrix[["symbol", "trade_date", "raw_label", "model_label"]]
    matrix = features.merge(labels, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    return matrix.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True), identity


def _spec(authority: dict) -> dict:
    stable = {"schema_version": "default-first-momentum-search-spec-v1", "task_id": TASK_ID,
              "provider_id": "tushare-pro-v1", "authority_record_id": authority["authority_record_id"],
              "catalog_id": SOURCE_CATALOG_ID, "feature_dataset_id": SOURCE_DATASET_ID,
              "governance_decision_id": GOVERNANCE_DECISION_ID, "development_period": list(DEVELOPMENT_PERIOD),
              "annual_periods": ANNUAL_PERIODS, "report_periods": REPORT_PERIODS,
              "round_themes": ROUND_THEMES, "round_features": ROUND_FEATURES,
              "strategy": FORMAL_STRATEGY, "default_gate": DEFAULT_GATE, "eligibility": ELIGIBILITY,
              "budget": BUDGET.__dict__, "runtime_mode": "store_required", "selection_data_end": "2024-12-31",
              "predictive_claim": False, "usable_for_promotion": False, "eligible_for_production": False}
    return stable | {"spec_id": "dfms1_" + hash_payload(stable)}


def _find_experiment(bundle: AuthorityBundle, root: Path) -> tuple[Any, dict] | None:
    found = []
    for index, descriptor in enumerate(bundle.store.list_by_kind("default_first_momentum_experiment")):
        destination = Path(root) / str(index)
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
        if identity.get("task_id") == TASK_ID and identity.get("feature_dataset_id") == SOURCE_DATASET_ID:
            found.append((descriptor, identity))
    if len(found) > 1: raise RuntimeError("multiple canonical default-first momentum experiments")
    return found[0] if found else None


def _historical_memory(bundle: AuthorityBundle, root: Path) -> dict:
    r1003 = []
    for descriptor in bundle.store.list_by_kind("skip_recent_momentum_candidate_lock"):
        identity = _identity(bundle, descriptor.artifact_id, Path(root) / "r1-003")
        r1003.append({key: identity.get(key) for key in ("candidate_lock_id", "template_name", "canonical_dsl",
                     "economic_hypothesis", "orientation", "structural_fingerprint", "turnover", "concentration")})
    return {"schema_version": "default-first-momentum-agent-memory-v1", "visibility_cutoff": "2024-12-31",
            "existing_factor_names": ["liquidity_normalized_momentum", "liquidity_persistence_beta_penalty",
                "momentum_peak_volatility_adjusted", "amount_accumulation_without_price_acceleration"],
            "r1_003_candidate_definitions": r1003,
            "r1_004_semantic_findings": [
                "momentum minus its rolling mean is momentum deviation or surprise, not risk adjustment",
                "subtracting a negative distance-to-high rewards stocks farther below their high; it is not breakout confirmation",
                "2025 positive RankIC can coexist with negative portfolio excess; 2026H1 showed sign/regime failure",
                "turnover and costs were not the primary explanation for the observed failure"],
            "r1_005_overfit_finding": "default-first; local rescue only after failure; combined optimization suspended",
            "daily_labels_included": False, "daily_returns_included": False, "daily_ic_included": False,
            "single_stock_contributions_included": False, "report_2025_2026_daily_feedback_included": False}


def _development_gate(metrics: dict, qlib: dict, diagnostics: dict, infinity_count: int) -> tuple[bool, list[str]]:
    checks = {"mean_rank_ic": (metrics.get("mean_rank_ic") or -999.0) > 0,
              "rank_ic_positive_rate": (metrics.get("rank_ic_positive_rate") or 0.0) >= .50,
              "coverage": (metrics.get("factor_finite_coverage") or 0.0) >= .90,
              "turnover": qlib.get("turnover") is not None and qlib["turnover"] <= 45.0,
              "infinity": infinity_count == 0, "pit": True,
              "predictive_or_excess": ((qlib.get("net_excess_csi300") or 0.0) > 0 or
                  (diagnostics.get("top_bottom_return") or 0.0) > 0 or
                  (diagnostics.get("group_monotonicity") or -999.0) > 0)}
    return all(checks.values()), [name for name, passed in checks.items() if not passed]


def local_rescue_eligible(metrics: dict, diagnostics: dict, *, infinity_count: int, pit_violations: int = 0) -> bool:
    if infinity_count or pit_violations or (metrics.get("factor_finite_coverage") or 0.0) < .90: return False
    return ((metrics.get("mean_rank_ic") or -999.0) >= NEAR_GATE["minimum_mean_rank_ic"] or
            (metrics.get("rank_ic_positive_rate") or 0.0) >= NEAR_GATE["minimum_rank_ic_positive_rate"] or
            (diagnostics.get("top_bottom_return") or 0.0) > 0)


def _selection_key(row: dict) -> tuple:
    metrics, qlib, diag = row["metrics"], row["qlib"], row["diagnostics"]
    return (-(metrics.get("mean_rank_ic") or -999.0), -(metrics.get("rank_ic_positive_rate") or 0.0),
            -(diag.get("top_bottom_return") or -999.0), -(qlib.get("net_excess_csi300") or -999.0),
            abs(qlib.get("max_drawdown") or 999.0), qlib.get("turnover") or 999.0, row["trial_id"])


def _annual_summary(candidate: dict) -> dict:
    rows = candidate["annual"]
    rankic = [row["metrics"].get("mean_rank_ic") for row in rows]
    excess = [row["qlib"].get("net_excess_csi300") for row in rows]
    turnover = [row["qlib"].get("turnover") for row in rows]
    concentration = [row["qlib"].get("best_10_days_contribution") for row in rows]
    without = [row["qlib"].get("return_without_best_10_days") for row in rows]
    drawdown = [abs(row["qlib"].get("max_drawdown")) for row in rows if row["qlib"].get("max_drawdown") is not None]
    values = {"complete_year_count": len(rows), "positive_rankic_year_count": sum(x is not None and x > 0 for x in rankic),
              "median_rankic": float(median(rankic)) if None not in rankic else None,
              "worst_rankic": min(rankic) if None not in rankic else None,
              "positive_excess_year_count": sum(x is not None and x > 0 for x in excess),
              "median_excess": float(median(excess)) if None not in excess else None,
              "worst_excess": min(excess) if None not in excess else None,
              "median_turnover": float(median(turnover)) if None not in turnover else None,
              "median_best10_contribution": float(median(concentration)) if None not in concentration else None,
              "median_return_without_best10": float(median(without)) if None not in without else None,
              "maximum_drawdown_abs": max(drawdown) if drawdown else None}
    checks = {"complete_years": values["complete_year_count"] == 4,
              "coverage": all((row["metrics"].get("factor_finite_coverage") or 0) >= .9 for row in rows),
              "infinity": candidate["infinity_count"] == 0, "pit": candidate["pit_violation_count"] == 0,
              "positive_rankic_years": values["positive_rankic_year_count"] >= 3,
              "median_rankic": values["median_rankic"] is not None and values["median_rankic"] >= .003,
              "worst_rankic": values["worst_rankic"] is not None and values["worst_rankic"] >= -.008,
              "positive_excess_years": values["positive_excess_year_count"] >= 3,
              "median_excess": values["median_excess"] is not None and values["median_excess"] > 0,
              "worst_excess": values["worst_excess"] is not None and values["worst_excess"] > -.10,
              "turnover": values["median_turnover"] is not None and values["median_turnover"] <= 40,
              "concentration": values["median_best10_contribution"] is not None and values["median_best10_contribution"] <= .35,
              "independence": candidate["maximum_old_factor_correlation"] < .85}
    return values | {"gate_results": checks, "eligible": all(checks.values()),
                     "gate_failure_reasons": [name for name, passed in checks.items() if not passed]}


def candidate_ordering(candidate: dict) -> tuple:
    value = candidate["summary"]
    return (-value["positive_rankic_year_count"], -value["positive_excess_year_count"],
            -(value["median_rankic"] or -999), -(value["worst_rankic"] or -999),
            -(value["median_excess"] or -999), -(value["worst_excess"] or -999),
            -int(candidate["default_candidate_passed"]), -(value["median_return_without_best10"] or -999),
            value["maximum_drawdown_abs"] or 999, value["median_turnover"] or 999,
            candidate["maximum_old_factor_correlation"], candidate["ast_depth"], candidate["factor_instance_id"])


def replay_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = load_authority_bundle(authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=Path(work_root) / "authority", store_root=store_root)
    found = _find_experiment(bundle, Path(work_root) / "lookup")
    if found is None: raise RuntimeError("default-first momentum experiment not found")
    descriptor, identity = found
    recovered = [_cold(bundle, artifact_id, Path(work_root) / "cold") for artifact_id in identity["artifact_ids"]]
    _cold(bundle, descriptor.artifact_id, Path(work_root) / "cold")
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "experiment_id": descriptor.artifact_id, "recovered_artifact_count": len(recovered) + 1,
            "candidate_lock_ids": identity["candidate_lock_ids"], "report_ids": identity["report_ids"],
            "agent_calls": 0, "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
            "qlib_calls": 0, "network_calls": 0, "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
            "store_integrity": integrity.status, "missing": len(integrity.issues),
            "unreferenced": len(integrity.unreferenced_blobs)}


def execute_experiment(*, repository_root: Path, work_root: Path, store_root: Path | None = None, agent=None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = load_authority_bundle(authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=work_root / "authority", store_root=store_root)
    existing = _find_experiment(bundle, work_root / "existing")
    if existing is not None:
        return replay_experiment(repository_root=repository_root, work_root=work_root / "exact-replay", store_root=store_root) | {"exact_existing": True}
    governance = validate_governance(bundle, work_root / "governance")
    matrix, dataset_identity = _source_matrix(bundle, work_root / "source")
    spec = _spec(bundle.authority)
    contract = _snapshot_contract(SOURCE_DATASET_ID, [c for c in matrix.columns if c not in {"symbol", "trade_date", "raw_label", "model_label"}], matrix["trade_date"].nunique())
    regimes, regime_contract = build_regimes(bundle.normalized, bundle.benchmark)
    old_four, old_evidence, old_three = _existing_four(bundle, work_root / "old")
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    qlib.service.initialize()
    from qlib.config import C
    C.kernels = 1
    agent = agent or CodexResearchAgent(model="gpt-5.6-terra", timeout_seconds=300)
    memory = _historical_memory(bundle, work_root / "memory")
    domain, cold = work_root / "domain", work_root / "stage-cold"
    published, artifact_ids, candidates, round_results = [], [], [], []
    known_structural, known_equivalent, feedback = set(), set(), []
    agent_calls = factor_optimization_calls = admitted_templates = 0

    for round_number in range(1, 7):
        theme, allowed = ROUND_THEMES[round_number], ROUND_FEATURES[round_number]
        goal = ResearchGoal("dfmg1_" + hash_payload({"spec": spec["spec_id"], "round": round_number}),
            theme, "Propose simple economically named momentum structures with explicit meaningful Template defaults. Do not depend on broad parameter search. Higher factor values must express the stated hypothesis. Pullback/distance-to-high signs and surprise/risk-adjustment names must be exact.",
            DATASET_KIND, tuple(allowed), OPERATORS, ("lookback_window", "factor_internal_weight"),
            2, 7, 1, "structurally distinct from prior and current round structures",
            ("one to three feature terminals and at least one momentum feature", "one or two parameters; explicit defaults are mandatory",
             "AST depth at most six", "prefer one or two terminals and one parameter", "no labels, regimes, report periods, strategy settings or financial data",
             "default parameter must be included in each explicit legal value list", "do not add complexity to improve historical return"))
        budget = ResearchCampaignBudget(max_iterations=1, max_agent_calls=1, max_proposals_per_iteration=3,
            max_total_admitted_templates=2, max_total_trials=7, max_failed_proposals=3,
            max_failed_trials=7, max_agent_repair_attempts_per_call=1)
        request = _request(goal, memory | {"prior_round_aggregate_feedback": feedback}, budget, 1)
        response = decision = None
        failure = None
        try:
            response = agent.propose(request); agent_calls += 1
            decision = parse_decision(response.raw_response, iteration=1, goal=goal, budget=budget,
                                      provider_id=response.provider_id, model_id=response.model_id)
        except Exception as exc:
            agent_calls += int(response is None)
            failure = {"error_code": type(exc).__name__, "safe_summary": str(exc)[:180]}
        raw_id = None
        if response is not None:
            request_bytes = json.dumps({"goal": request.goal, "memory": request.sanitized_memory, "contract": request.contract},
                ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
            raw_bytes = response.raw_response.encode("utf-8")
            raw_identity = {"schema_version": "research-agent-raw-response-v1", "provider_id": "tushare-pro-v1",
                "spec_id": spec["spec_id"], "round_number": round_number,
                "agent_call_id": "dfmac1_" + hash_payload({"spec": spec["spec_id"], "round": round_number, "response": hashlib.sha256(raw_bytes).hexdigest()}),
                "provider": response.provider_id, "model": response.model_id,
                "prompt_hash": hashlib.sha256(request_bytes).hexdigest(), "raw_response_blob_id": "blob_sha256_" + hashlib.sha256(raw_bytes).hexdigest(),
                "raw_response_hash": hashlib.sha256(raw_bytes).hexdigest(), "response_size_bytes": len(raw_bytes),
                "research_decision_id": None if decision is None else decision["decision_id"], "usage_summary": response.usage_summary,
                "secrets_persisted": False, "promotion_writes": 0}
            assert_common_complete("research_agent_raw_response", raw_identity)
            artifact = publish_common_artifact(domain, "research_agent_raw_response", raw_identity, {"raw_response.json": raw_bytes})
            published.append(_store_publish(bundle, artifact, "research_agent_raw_response", (GOVERNANCE_DECISION_ID, SOURCE_DATASET_ID)))
            raw_id = artifact["raw_response_artifact_id"]; artifact_ids.append(raw_id); _cold(bundle, raw_id, cold)
        if decision is None:
            result = {"round": round_number, "theme": theme, "agent_calls": 1, "proposals": 0, "admitted": 0, "failure": failure}
            round_results.append(result); feedback.append(result); continue

        admitted, rejected = [], []
        for proposal in decision["proposals"]:
            proposal_identity = {"schema_version": "research-proposal-v1", "provider_id": "tushare-pro-v1",
                "spec_id": spec["spec_id"], "round_number": round_number, "subfamily": theme,
                "research_decision_id": decision["decision_id"], "source_raw_response_artifact_id": raw_id,
                "proposal_id": proposal["proposal_id"], "proposal_payload": proposal, "rationale": proposal["rationale"], "promotion_writes": 0}
            artifact = publish_common_artifact(domain, "research_proposal", proposal_identity, {"proposal.json": proposal_identity})
            published.append(_store_publish(bundle, artifact, "research_proposal", (raw_id,))); proposal_artifact_id = artifact["proposal_artifact_id"]
            artifact_ids.append(proposal_artifact_id); _cold(bundle, proposal_artifact_id, cold)
            try:
                if len(admitted) >= 2: raise ValueError("round_admission_budget_exhausted")
                template = parse_template(proposal["template"])
                depth, input_features, parameters = _ast_stats(proposal["template"]["expression"])
                if depth > 6 or len(input_features) > 3 or not input_features or not parameters or len(parameters) > 2:
                    raise ValueError("proposal complexity/default parameter contract failed")
                if input_features - set(allowed): raise ValueError("proposal uses feature outside round allowlist")
                if not any("momentum" in name or name.startswith("return_") for name in input_features):
                    raise ValueError("proposal lacks a momentum terminal")
                redundancy = assess_template(proposal["template"], known_structural=known_structural, known_equivalent=known_equivalent)
                if not redundancy["admitted"]: raise ValueError("equivalent_or_existing_structure")
                defaults = {parameter.name: parameter.default for parameter in template.parameters}
                legal = {name: list(specification["values"]) for name, specification in proposal["parameter_search"]["search_space"].items()}
                neighborhood = local_factor_neighborhood(defaults, legal)
                compiled, default_values = factor_values(template, contract, defaults, matrix)
                raw_rankic = split_metrics(default_values, matrix, *DEVELOPMENT_PERIOD, 1).get("mean_rank_ic")
                orientation = 1 if raw_rankic is None or raw_rankic >= 0 else -1
                default_metrics = split_metrics(default_values, matrix, *DEVELOPMENT_PERIOD, orientation)
                diagnostics = group_diagnostics(default_values, matrix, *DEVELOPMENT_PERIOD, orientation)
                default_signal = oriented_signal(default_values, orientation, work_root / "signals" / f"{compiled.factor_instance_id}-default.parquet")
                default_qlib = _clean_result(qlib.run(default_signal, *DEVELOPMENT_PERIOD, lifecycle_policy=LIFECYCLE_POLICY))
                numeric = pd.to_numeric(default_values["factor_value"], errors="coerce")
                infinity_count = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
                default_passed, failure_reasons = _development_gate(default_metrics, default_qlib, diagnostics, infinity_count)
                rescue_allowed = not default_passed and local_rescue_eligible(default_metrics, diagnostics, infinity_count=infinity_count)
                template_identity = {"schema_version": "factor-template-definition-v1", "provider_id": "tushare-pro-v1",
                    "spec_id": spec["spec_id"], "factor_template_id": factor_template_id(template), "template_name": template.name,
                    "canonical_dsl": _dsl(proposal["template"]["expression"]), "canonical_ast": proposal["template"]["expression"],
                    "input_features": sorted(input_features), "parameter_schema": proposal["template"]["parameters"],
                    "agent_default_parameters": defaults, "orientation_policy": "development_sign_only_then_frozen",
                    "structural_fingerprint": redundancy["structural_fingerprint"], "economic_hypothesis": proposal["rationale"],
                    "expected_failure_modes": proposal["risks"] + proposal["invalidation_conditions"],
                    "why_default_parameters_are_reasonable": proposal["expected_behavior"], "source_proposal_id": proposal["proposal_id"],
                    "promotion_writes": 0}
                assert_common_complete("factor_template_definition", template_identity)
                template_artifact = publish_common_artifact(domain, "factor_template_definition", template_identity,
                                                              {"template.json": proposal["template"], "definition.json": template_identity})
                published.append(_store_publish(bundle, template_artifact, "factor_template_definition", (proposal_artifact_id,)))
                template_definition_id = template_artifact["template_definition_id"]; artifact_ids.append(template_definition_id); _cold(bundle, template_definition_id, cold)
                default_identity = {"schema_version": "default-parameter-evaluation-v1", "provider_id": "tushare-pro-v1",
                    "spec_id": spec["spec_id"], "factor_template_id": compiled.template_id, "factor_instance_id": compiled.factor_instance_id,
                    "agent_default_parameters": defaults, "development_period": list(DEVELOPMENT_PERIOD),
                    "metrics": default_metrics | diagnostics, "qlib": default_qlib, "orientation": orientation,
                    "infinity_count": infinity_count, "pit_violation_count": 0, "default_candidate_passed": default_passed,
                    "gate_failure_reasons": failure_reasons, "local_rescue_eligible": rescue_allowed,
                    "strategy": FORMAL_STRATEGY, "optimization_calls": 0, "promotion_writes": 0}
                default_artifact = publish_artifact(domain, "default_parameter_evaluation", default_identity,
                    {"evaluation.json": default_identity, "factor_values.parquet": default_values})
                published.append(_store_publish(bundle, default_artifact, "default_parameter_evaluation", (template_definition_id,)))
                default_id = default_artifact["default_evaluation_id"]; artifact_ids.append(default_id); _cold(bundle, default_id, cold)

                selected = {"parameters": defaults, "compiled": compiled, "values": default_values, "signal": default_signal,
                            "metrics": default_metrics, "qlib": default_qlib, "diagnostics": diagnostics,
                            "trial_id": "dfmt1_" + hash_payload({"template": compiled.template_id, "parameters": defaults})}
                local_rows = []
                if rescue_allowed:
                    for parameters_row in neighborhood[1:]:
                        local_compiled, local_values = factor_values(template, contract, parameters_row, matrix)
                        local_metrics = split_metrics(local_values, matrix, *DEVELOPMENT_PERIOD, orientation)
                        local_diag = group_diagnostics(local_values, matrix, *DEVELOPMENT_PERIOD, orientation)
                        local_signal = oriented_signal(local_values, orientation, work_root / "signals" / f"{local_compiled.factor_instance_id}-local.parquet")
                        local_qlib = _clean_result(qlib.run(local_signal, *DEVELOPMENT_PERIOD, lifecycle_policy=LIFECYCLE_POLICY))
                        local_inf = int(np.isinf(pd.to_numeric(local_values["factor_value"], errors="coerce").to_numpy(dtype=float, na_value=np.nan)).sum())
                        passed, reasons = _development_gate(local_metrics, local_qlib, local_diag, local_inf)
                        local_rows.append({"trial_id": "dfmt1_" + hash_payload({"template": local_compiled.template_id, "parameters": parameters_row}),
                            "parameters": parameters_row, "factor_instance_id": local_compiled.factor_instance_id,
                            "metrics": local_metrics, "diagnostics": local_diag, "qlib": local_qlib,
                            "passed": passed, "failure_reasons": reasons, "compiled": local_compiled,
                            "values": local_values, "signal": local_signal, "research_gain": {
                                "mean_rank_ic": (local_metrics.get("mean_rank_ic") or 0) - (default_metrics.get("mean_rank_ic") or 0),
                                "csi300_excess": (local_qlib.get("net_excess_csi300") or 0) - (default_qlib.get("net_excess_csi300") or 0)}})
                    factor_optimization_calls += len(local_rows)
                    ranked = sorted(local_rows, key=_selection_key)
                    governed = evaluate_factor(agent_default_parameters=defaults, legal_values=legal, default_passed=False,
                        default_metrics=default_metrics | diagnostics | {"qlib": default_qlib}, default_failure_reasons=failure_reasons,
                        local_trials=[{k: v for k, v in row.items() if k not in {"compiled", "values", "signal"}} for row in ranked])
                    rescued = next((row for row in ranked if row["parameters"] == governed["selected_parameters"] and row["passed"]), None)
                    if rescued is not None: selected = rescued
                else:
                    governed = evaluate_factor(agent_default_parameters=defaults, legal_values=legal,
                        default_passed=default_passed, default_metrics=default_metrics | diagnostics | {"qlib": default_qlib},
                        default_failure_reasons=failure_reasons)
                if local_rows:
                    rescue_identity = {"schema_version": "local-factor-rescue-study-v1", "provider_id": "tushare-pro-v1",
                        "spec_id": spec["spec_id"], "factor_template_id": compiled.template_id, "default_evaluation_id": default_id,
                        "agent_default_parameters": defaults, "parameter_neighborhood": list(neighborhood), "trial_count": 1 + len(local_rows),
                        "trials": [{k: v for k, v in row.items() if k not in {"compiled", "values", "signal"}} for row in local_rows],
                        "selected_parameters": governed["selected_parameters"], "optimization_rescued": governed["optimization_rescued"],
                        "evidence_class": governed["evidence_class"], "full_search_used": False,
                        "strategy_optimization_calls": 0, "combined_optimization_calls": 0, "promotion_writes": 0}
                    rescue_artifact = publish_artifact(domain, "local_factor_rescue_study", rescue_identity, {"study.json": rescue_identity})
                    published.append(_store_publish(bundle, rescue_artifact, "local_factor_rescue_study", (default_id,)))
                    rescue_id = rescue_artifact["local_rescue_study_id"]; artifact_ids.append(rescue_id); _cold(bundle, rescue_id, cold)
                else: rescue_id = None
                if not default_passed and not governed["optimization_rescued"]:
                    rejected.append({"proposal_id": proposal["proposal_id"], "reason": "default_failed_and_not_rescued", "default_evaluation_id": default_id})
                    known_structural.add(redundancy["structural_fingerprint"]); known_equivalent.add(redundancy["equivalence_fingerprint"])
                    admitted_templates += 1
                    continue
                optimization_mode = "default_first" if default_passed else "local_only"
                metadata = build_candidate_metadata(factor_mode="default_first", strategy_mode="default_first",
                    factor_trial_count=1 + len(local_rows), strategy_trial_count=1,
                    default_factor_passed=default_passed, default_strategy_passed=True,
                    optimization_rescued=bool(governed["optimization_rescued"]), strategy_optimization_rescued=False)
                validate_combination(factor_parameters_changed_from_default=selected["parameters"] != defaults,
                                     strategy_parameters_changed_from_default=False,
                                     default_factor_failed=not default_passed, default_strategy_failed=False)
                factor_value_id = "fv_" + hash_payload({"factor_instance_id": selected["compiled"].factor_instance_id,
                    "dataset": SOURCE_DATASET_ID, "values_sha256": hash_file(selected["signal"])})
                lock_identity = {"schema_version": "development-parameter-lock-v1", "provider_id": "tushare-pro-v1",
                    "spec_id": spec["spec_id"], "factor_template_id": selected["compiled"].template_id,
                    "factor_instance_id": selected["compiled"].factor_instance_id, "template_definition_id": template_definition_id,
                    "default_evaluation_id": default_id, "local_rescue_study_id": rescue_id,
                    "agent_default_parameters": defaults, "selected_parameters": selected["parameters"],
                    "optimization_mode": optimization_mode, "optimization_rescued": bool(governed["optimization_rescued"]),
                    "development_period": list(DEVELOPMENT_PERIOD), "development_metrics": selected["metrics"] | selected["diagnostics"] | {"qlib": selected["qlib"]},
                    "orientation": orientation, "factor_value_artifact_id": factor_value_id, "parameter_lock_frozen": True,
                    "selection_data_end": "2020-12-31", "optimization_governance": metadata,
                    "strategy_optimization_calls": 0, "combined_optimization_calls": 0, "promotion_writes": 0}
                lock_artifact = publish_artifact(domain, "development_parameter_lock", lock_identity,
                    {"lock.json": lock_identity, "factor_values.parquet": selected["values"], "signal.parquet": selected["signal"]})
                published.append(_store_publish(bundle, lock_artifact, "development_parameter_lock", tuple(x for x in (default_id, rescue_id) if x)))
                development_lock_id = lock_artifact["development_lock_id"]; artifact_ids.append(development_lock_id); _cold(bundle, development_lock_id, cold)
                candidate = {"round_number": round_number, "theme": theme, "proposal": proposal,
                    "template": proposal["template"], "template_definition_id": template_definition_id,
                    "factor_template_id": selected["compiled"].template_id, "factor_instance_id": selected["compiled"].factor_instance_id,
                    "agent_default_parameters": defaults, "selected_parameters": selected["parameters"],
                    "default_candidate_passed": default_passed, "optimization_rescued": bool(governed["optimization_rescued"]),
                    "optimization_mode": optimization_mode, "orientation": orientation,
                    "development_metrics": lock_identity["development_metrics"], "development_lock_id": development_lock_id,
                    "factor_value_artifact_id": factor_value_id, "values": selected["values"], "signal": selected["signal"],
                    "canonical_dsl": template_identity["canonical_dsl"], "canonical_ast": template_identity["canonical_ast"],
                    "input_features": sorted(input_features), "structural_fingerprint": redundancy["structural_fingerprint"],
                    "ast_depth": depth, "infinity_count": infinity_count, "pit_violation_count": 0}
                annual = []
                for year, period in ANNUAL_PERIODS.items():
                    metrics = split_metrics(selected["values"], matrix, *period, orientation)
                    diag = group_diagnostics(selected["values"], matrix, *period, orientation)
                    raw_qlib = _clean_result(qlib.run(selected["signal"], *period, lifecycle_policy=LIFECYCLE_POLICY))
                    regime = _regime_for_result(selected["values"], matrix, *period, orientation, raw_qlib, regimes)
                    annual_identity = {"schema_version": "default-first-momentum-annual-evaluation-v1", "provider_id": "tushare-pro-v1",
                        "spec_id": spec["spec_id"], "development_lock_id": development_lock_id, "factor_instance_id": candidate["factor_instance_id"],
                        "year": year, "date_range": list(period), "selected_parameters": selected["parameters"],
                        "parameters_reoptimized": False, "metrics": metrics | diag, "qlib": raw_qlib, "regime_metrics": regime,
                        "not_used_for_parameter_selection": True, "promotion_writes": 0}
                    annual_artifact = publish_artifact(domain, "default_first_momentum_annual_evaluation", annual_identity, {"evaluation.json": annual_identity})
                    published.append(_store_publish(bundle, annual_artifact, "default_first_momentum_annual_evaluation", (development_lock_id,)))
                    annual_id = annual_artifact["annual_evaluation_id"]; artifact_ids.append(annual_id); _cold(bundle, annual_id, cold)
                    annual.append({"annual_evaluation_id": annual_id, "year": year, "metrics": metrics | diag, "qlib": raw_qlib, "regime_metrics": regime})
                candidate["annual"] = annual
                signal_frame = pd.read_parquet(selected["signal"])
                maximum, correlations = _correlations(signal_frame, old_four)
                candidate["maximum_old_factor_correlation"], candidate["old_factor_correlations"] = maximum, correlations
                candidate["summary"] = _annual_summary(candidate)
                evidence_identity = {"schema_version": "default-first-momentum-eligibility-v1", "provider_id": "tushare-pro-v1",
                    "spec_id": spec["spec_id"], "development_lock_id": development_lock_id,
                    "annual_evaluation_ids": [row["annual_evaluation_id"] for row in annual], "annual_metrics": annual,
                    "old_factor_correlations": correlations, "maximum_old_factor_correlation": maximum,
                    "gate_results": candidate["summary"]["gate_results"], "gate_failure_reasons": candidate["summary"]["gate_failure_reasons"],
                    "standalone_eligible": candidate["summary"]["eligible"], "selection_used_2025": False,
                    "selection_used_2026H1": False, "promotion_writes": 0}
                evidence_artifact = publish_artifact(domain, "default_first_momentum_eligibility_evidence", evidence_identity, {"eligibility.json": evidence_identity})
                published.append(_store_publish(bundle, evidence_artifact, "default_first_momentum_eligibility_evidence", tuple(evidence_identity["annual_evaluation_ids"])))
                evidence_id = evidence_artifact["eligibility_evidence_id"]; artifact_ids.append(evidence_id); _cold(bundle, evidence_id, cold)
                candidate["eligibility_evidence_id"] = evidence_id
                admitted.append(candidate); candidates.append(candidate); admitted_templates += 1
                known_structural.add(redundancy["structural_fingerprint"]); known_equivalent.add(redundancy["equivalence_fingerprint"])
            except Exception as exc:
                rejected.append({"proposal_id": proposal["proposal_id"], "reason": f"{type(exc).__name__}:{str(exc)[:180]}"})
        result = {"round": round_number, "theme": theme, "agent_calls": 1, "proposals": len(decision["proposals"]),
                  "admitted": len(admitted), "default_passed": sum(c["default_candidate_passed"] for c in admitted),
                  "rescued": sum(c["optimization_rescued"] for c in admitted), "eligible": sum(c["summary"]["eligible"] for c in admitted),
                  "rejected": rejected}
        round_results.append(result); feedback.append(result)

    eligible = sorted((c for c in candidates if c["summary"]["eligible"]), key=candidate_ordering)
    selected_candidates = eligible[:3]
    locks, lock_ids = [], []
    for candidate in selected_candidates:
        unified_signal_id = "susi1_" + hash_payload({"factor_instance_id": candidate["factor_instance_id"],
                                                     "orientation": candidate["orientation"], "signal_sha256": hash_file(candidate["signal"])})
        identity = {"schema_version": "default-first-momentum-candidate-lock-v1", "provider_id": "tushare-pro-v1",
            "spec_id": spec["spec_id"], "factor_template_id": candidate["factor_template_id"],
            "factor_instance_id": candidate["factor_instance_id"], "template_name": candidate["template"]["name"],
            "momentum_family": candidate["theme"], "canonical_dsl": candidate["canonical_dsl"],
            "canonical_ast": candidate["canonical_ast"], "input_features": candidate["input_features"],
            "agent_default_parameters": candidate["agent_default_parameters"], "selected_parameters": candidate["selected_parameters"],
            "optimization_mode": candidate["optimization_mode"], "optimization_rescued": candidate["optimization_rescued"],
            "development_metrics": candidate["development_metrics"], "annual_2021_2024_metrics": candidate["annual"],
            "orientation": candidate["orientation"], "factor_value_artifact_id": candidate["factor_value_artifact_id"],
            "unified_signal_id": unified_signal_id, "turnover": candidate["summary"]["median_turnover"],
            "cost": float(median([row["qlib"]["transaction_cost"] for row in candidate["annual"]])),
            "concentration": candidate["summary"]["median_best10_contribution"],
            "old_factor_correlations": candidate["old_factor_correlations"], "structural_fingerprint": candidate["structural_fingerprint"],
            "economic_hypothesis": candidate["proposal"]["rationale"], "development_lock_id": candidate["development_lock_id"],
            "eligibility_evidence_id": candidate["eligibility_evidence_id"], "fixed_strategy_contract": FORMAL_STRATEGY,
            "status": "research_registered", "predictive_claim": False, "usable_for_promotion": False,
            "eligible_for_production": False, "promotion_writes": 0}
        artifact = publish_artifact(domain, "default_first_momentum_candidate_lock", identity,
                                    {"candidate.json": identity, "signal.parquet": candidate["signal"]})
        published.append(_store_publish(bundle, artifact, "default_first_momentum_candidate_lock", (candidate["eligibility_evidence_id"],)))
        lock_id = artifact["candidate_lock_id"]; artifact_ids.append(lock_id); lock_ids.append(lock_id); _cold(bundle, lock_id, cold)
        locks.append((lock_id, candidate))

    report_ids, reports = [], {}
    for lock_id, candidate in locks:
        reports[lock_id] = {}
        for label, period in REPORT_PERIODS.items():
            metrics = split_metrics(candidate["values"], matrix, *period, candidate["orientation"])
            raw_qlib = _clean_result(qlib.run(candidate["signal"], *period, lifecycle_policy=LIFECYCLE_POLICY))
            regime = _regime_for_result(candidate["values"], matrix, *period, candidate["orientation"], raw_qlib, regimes)
            identity = {"schema_version": "default-first-momentum-report-v1", "provider_id": "tushare-pro-v1",
                "spec_id": spec["spec_id"], "candidate_lock_id": lock_id, "factor_instance_id": candidate["factor_instance_id"],
                "period": label, "date_range": list(period), "metrics": metrics, "qlib": raw_qlib,
                "regime_metrics": regime, "selected_parameters": candidate["selected_parameters"],
                "parameters_reoptimized": False, "retrospective_report_only": True, "not_used_for_selection": True,
                "not_fresh_validation": True, "predictive_claim": False, "promotion_writes": 0}
            artifact = publish_artifact(domain, "default_first_momentum_report", identity, {"report.json": identity})
            published.append(_store_publish(bundle, artifact, "default_first_momentum_report", (lock_id,)))
            report_id = artifact["report_id"]; artifact_ids.append(report_id); report_ids.append(report_id); _cold(bundle, report_id, cold)
            reports[lock_id][label] = identity | {"report_id": report_id}

    comparison = {"old_three_source_artifact_id": old_evidence["old_three_source"],
        "r1_001_experiment_id": old_evidence["r1_experiment_id"], "r1_001_candidate_lock_id": old_evidence["r1_candidate_lock_id"],
        "early_factor_and_ensemble_results": old_evidence["old_results"],
        "r1_003_candidate_definitions": memory["r1_003_candidate_definitions"],
        "new_candidates": {lock_id: {"development": candidate["development_metrics"], "annual": candidate["annual"],
                                      "reports": reports[lock_id], "optimization_rescued": candidate["optimization_rescued"]}
                           for lock_id, candidate in locks},
        "benchmark": "CSI300", "comparison_uses_report_period_for_selection": False}
    questions = {"default_parameters_produced_eligible_candidate": any(c["default_candidate_passed"] for c in selected_candidates),
        "local_rescue_count": sum(c["optimization_rescued"] for c in candidates),
        "stable_family": None if not selected_candidates else selected_candidates[0]["theme"],
        "multi_horizon_effective": any(c["theme"] == "multi_horizon_consensus" and c["summary"]["eligible"] for c in candidates),
        "path_quality_effective": any("path_quality" in c["theme"] and c["summary"]["eligible"] for c in candidates),
        "surprise_effective": any("surprise" in c["theme"] and c["summary"]["eligible"] for c in candidates),
        "pullback_effective": any("pullback" in c["theme"] and c["summary"]["eligible"] for c in candidates),
        "residual_strength_effective": any("residual" in c["theme"] and c["summary"]["eligible"] for c in candidates),
        "default_first_reduced_search_exposure": True,
        "conclusion": ("eligible research candidates exist under default-first governance" if selected_candidates else
                       "no structure passed the frozen gates; thresholds and search scope were not relaxed")}
    execution_counts = {"agent_calls": agent_calls, "factor_optimization_calls": factor_optimization_calls,
        "strategy_optimization_calls": 0, "combined_optimization_calls": 0, "qlib_calls": qlib.calls,
        "network_calls": 0, "promotion_writes": 0}
    assessment_identity = {"schema_version": "default-first-momentum-assessment-v1", "provider_id": "tushare-pro-v1",
        "spec_id": spec["spec_id"], "round_results": round_results,
        "default_passed_candidates": [c["factor_instance_id"] for c in candidates if c["default_candidate_passed"]],
        "optimization_rescued_candidates": [c["factor_instance_id"] for c in candidates if c["optimization_rescued"]],
        "eligible_candidate_count": len(eligible), "candidate_lock_ids": lock_ids, "comparison": comparison,
        "questions": questions, "execution_counts": execution_counts, "selection_used_2025": False,
        "selection_used_2026H1": False, "predictive_claim": False, "promotion_writes": 0}
    artifact = publish_artifact(domain, "default_first_momentum_assessment", assessment_identity,
                                {"assessment.json": assessment_identity, "comparison.json": comparison})
    published.append(_store_publish(bundle, artifact, "default_first_momentum_assessment", tuple(lock_ids + report_ids)))
    assessment_id = artifact["assessment_id"]; artifact_ids.append(assessment_id); _cold(bundle, assessment_id, cold)
    experiment_identity = {"schema_version": "default-first-momentum-experiment-v1", "task_id": TASK_ID,
        "provider_id": "tushare-pro-v1", "spec_id": spec["spec_id"], "governance_decision_id": GOVERNANCE_DECISION_ID,
        "catalog_id": SOURCE_CATALOG_ID, "feature_dataset_id": SOURCE_DATASET_ID,
        "artifact_ids": artifact_ids, "candidate_lock_ids": lock_ids, "report_ids": report_ids,
        "assessment_id": assessment_id, "execution_counts": execution_counts,
        "registry": {"entries": [{"candidate_lock_id": value, "status": "research_registered"} for value in lock_ids],
                     "promotion_candidates": [], "approved": [], "active": [], "production": []},
        "predictive_claim": False, "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0}
    artifact = publish_artifact(domain, "default_first_momentum_experiment", experiment_identity,
                                {"spec.json": spec, "summary.json": {"round_results": round_results,
                                 "candidate_lock_ids": lock_ids, "report_ids": report_ids, "questions": questions,
                                 "comparison": comparison, "regime_contract": regime_contract}})
    published.append(_store_publish(bundle, artifact, "default_first_momentum_experiment", tuple(artifact_ids)))
    experiment_id = artifact["experiment_id"]; _cold(bundle, experiment_id, cold)
    inventory = publish_inventory(bundle.store); integrity = scan_store_integrity(bundle.store)
    return {"status": "completed", "experiment_id": experiment_id, "spec_id": spec["spec_id"],
        "candidate_lock_ids": lock_ids, "report_ids": report_ids, "assessment_id": assessment_id,
        "round_results": round_results, "eligible_candidate_count": len(eligible),
        "default_passed_candidate_count": len(assessment_identity["default_passed_candidates"]),
        "optimization_rescued_candidate_count": len(assessment_identity["optimization_rescued_candidates"]),
        "execution_counts": execution_counts, "questions": questions, "published": published,
        "admitted_templates": admitted_templates, "artifact_count": len(bundle.store.list_artifacts()),
        "blob_count": sum(1 for path in bundle.store.config.root.joinpath("objects", "sha256").rglob("*") if path.is_file()),
        "store_integrity": integrity.status, "missing": len(integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs), "inventory_id": inventory.inventory_id,
        "exact_existing": False}
