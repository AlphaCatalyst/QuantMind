from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from backend.services.engine.autonomous_factor_campaign.admission import admit_proposal
from backend.services.engine.autonomous_factor_campaign.evaluation import CampaignEvaluator
from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.autonomous_factor_program.orchestrator import _latest_and_fresh
from backend.services.engine.autonomous_factor_program.statistics import benjamini_hochberg
from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import OPERATORS, SOURCE_DATASET_ID
from backend.services.engine.momentum_factor_iteration.engine import _snapshot_contract
from backend.services.engine.optimization_governance.engine import local_factor_neighborhood
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.research_campaign.parameter_contract import validate_proposal_parameter_contract
from backend.services.engine.tushare_agent_experiment.evaluation import factor_values
from backend.services.engine.tushare_cutover.canonical import hash_payload

from backend.services.engine.autonomous_technical_feature_factory.agent import call_structured_codex

from .evaluation import (
    ADAPTIVE_YEARS, VALIDATION_YEARS, choose_orientation, evaluate_locked,
)
from .models import (
    ARCHETYPES, LANES, AlphaArchetypeContractV1,
    ArchetypeAwareAlphaProgramSpecV1, empty_usage,
)
from .schemas import alpha_agent_schema


REPORT_PERIODS = {
    "2025": ("2025-01-02", "2025-12-31"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}
TERMINAL_STATES = {
    "completed_with_survivors", "completed_no_new_feature",
    "completed_no_union_shortlist", "completed_no_validation_survivor",
    "completed_with_retrospective_survivors",
}


def _identities(repository, kind: str, program_id: str) -> list[dict]:
    result = []
    for descriptor in repository.store.list_by_kind(kind):
        identity = repository.identity(descriptor.artifact_id)
        if identity.get("program_id") == program_id or identity.get("program_spec_id") == program_id:
            result.append(identity | {"artifact_id": descriptor.artifact_id})
    return result


def create_program_spec(*, feature_catalog_v2_id: str, repository_root: Path,
                        work_root: Path, store_root: Path | None = None,
                        spec: ArchetypeAwareAlphaProgramSpecV1 | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    catalog = repository.identity(feature_catalog_v2_id)
    if catalog.get("schema_version") not in {
        "technical-feature-catalog-v2", "technical-feature-catalog-v3",
    } or not catalog.get("frozen"):
        raise ValueError("Technical Feature Catalog v2/v3 must be frozen before Alpha Agent")
    contract = AlphaArchetypeContractV1().payload(feature_catalog_v2_id)
    contract_receipt = repository.publish(
        "alpha_archetype_contract", contract, {"alpha_archetype_contract.json": contract},
        lineage=(feature_catalog_v2_id,),
    )
    chosen = spec or ArchetypeAwareAlphaProgramSpecV1(feature_catalog_v2_id=feature_catalog_v2_id)
    payload = chosen.payload()
    payload["feature_catalog_version"] = catalog["schema_version"]
    payload["archetype_contract_id"] = contract_receipt["artifact_id"]
    # Program identity includes the immutable Contract reference.
    stable = {key: value for key, value in payload.items() if key != "program_spec_id"}
    payload["program_spec_id"] = "aap1_" + hash_payload(stable)
    receipt = repository.publish(
        "archetype_aware_program_spec", payload,
        {"program_spec.json": payload, "lane_specs.json": payload["lanes"]},
        lineage=(feature_catalog_v2_id, contract_receipt["artifact_id"]),
    )
    repository.identity(payload["program_spec_id"])
    return payload | {"store_receipt": receipt}


def _feature_matrix(repository, catalog: dict, bundle, work_root: Path) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    if work_root.exists():
        shutil.rmtree(work_root)
    matrix, _ = _source_matrix(bundle, work_root / "existing")
    matrix["trade_date"] = pd.to_datetime(matrix["trade_date"]).dt.strftime("%Y-%m-%d")
    family_features: dict[str, list[str]] = {name: [] for name in (
        "trend_geometry", "drawdown_recovery_geometry", "volatility_shape",
        "liquidity_amount_dynamics", "relative_strength", "path_asymmetry",
        "price_volume_lead_lag", "intraday_overnight_decomposition",
        "range_compression_expansion", "drawdown_age_recovery_timing",
        "return_path_asymmetry", "robust_trend_location",
    )}
    for item in catalog["research_terminal_features"]:
        root = repository.materialize(item["materialized_artifact_id"])
        values = pd.read_parquet(root / "feature_values.parquet").rename(
            columns={"feature_value": item["feature_name"]}
        )
        values["trade_date"] = pd.to_datetime(values["trade_date"]).dt.strftime("%Y-%m-%d")
        matrix = matrix.merge(values, on=["symbol", "trade_date"], how="left", validate="one_to_one")
        family_features[item["family"]].append(item["feature_name"])
    return matrix, family_features


def _allowed_features(lane_id: str, family_features: dict[str, list[str]], available: set[str]) -> list[str]:
    core = [
        name for name in (
            "mom_ret_1d", "momentum_20", "momentum_60", "momentum_120",
            "distance_to_high_20", "drawdown_20", "residual_momentum_20",
            "price_efficiency_20", "liq_volume_ratio_5", "style_idio_vol_20",
        ) if name in available
    ]
    mapping = {
        "trend_geometry_lane": (
            "trend_geometry", "drawdown_recovery_geometry",
            "drawdown_age_recovery_timing", "robust_trend_location",
            "range_compression_expansion",
        ),
        "trading_confirmation_lane": (
            "liquidity_amount_dynamics", "volatility_shape",
            "price_volume_lead_lag", "intraday_overnight_decomposition",
            "range_compression_expansion",
        ),
        "relative_asymmetric_lane": (
            "relative_strength", "path_asymmetry",
            "return_path_asymmetry", "robust_trend_location",
        ),
    }
    generated = [
        name for group in mapping[lane_id] for name in family_features[group] if name in available
    ]
    return list(dict.fromkeys(generated + core))[:24]


def _prompt(*, spec: dict, lane_id: str, family: str, archetype: str,
            call_index: int, allowed_features: list[str], known_fingerprints: list[str],
            failure_summary: list[str]) -> str:
    goal_id = "aag1_" + hash_payload({
        "program": spec["program_spec_id"], "call": call_index, "lane": lane_id,
    })
    request = {
        "goal_id": goal_id, "iteration": call_index, "program_id": spec["program_spec_id"],
        "lane_id": lane_id, "round_id": f"{lane_id}-{call_index:02d}",
        "factor_family": family, "required_primary_archetype": archetype,
        "required_primary_test_statistic": ARCHETYPES[archetype]["primary_test_statistic"],
        "allowed_features": allowed_features, "allowed_operators": list(OPERATORS),
        "required_template_dataset_kinds": ["momentum_feature_matrix_v1"],
        "allowed_parameter_roles": ["lookback_window", "factor_internal_weight"],
        "maximum_proposals": 3, "maximum_terminal_features": 3,
        "maximum_parameters": 2, "maximum_ast_depth": 6,
        "strategy_is_fixed": spec["strategy_protocol"],
        "known_structural_fingerprints": known_fingerprints[-80:],
        "adaptive_unlabeled_failure_codes": failure_summary[-12:],
        "forbidden": [
            "2021-2026 evidence", "Fresh evidence", "strategy parameters", "full optimization",
            "strategy optimization", "combined optimization", "promotion state", "financial data",
            "archetype switching after evaluation",
        ],
    }
    return (
        "You are the structure-proposal layer of an archetype-aware bounded alpha research program. "
        "Return exactly one JSON object matching the schema. Produce two simple PIT-safe factor templates for "
        "the required lane, factor family, and primary archetype. Copy REQUEST goal_id, iteration, lane_id, "
        "round_id, factor_family, primary_archetype and primary_test_statistic exactly into each proposal. "
        "Every template.dataset_kinds must be exactly REQUEST.required_template_dataset_kinds. "
        "Declare the archetype before any numerical evaluation. Use one to three allowed Terminal Features, at "
        "most two genuine parameters, explicit_values only, and an operator expression root. At least one input "
        "must encode price/trend direction; pure liquidity/beta/volatility structures are forbidden. Do not emit "
        "labels, data rows, performance, paths, code, strategy controls, or secrets. REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _strip_archetype(proposal: dict) -> dict:
    return {
        key: proposal[key] for key in (
            "proposal_id", "template", "parameter_search", "rationale",
            "expected_behavior", "novelty_claim", "risks", "invalidation_conditions",
        )
    }


def _adaptive_rank(row: dict) -> tuple:
    summary = row["evaluation"]["summary"]
    if row["primary_archetype"] == "monotonic_rank_factor":
        primary = summary.get("median_annual_rankic") or -999
    else:
        primary = summary.get("median_tail_spread") or -999
    return (
        -int(row["evaluation"]["summary"]["gate_passed"]),
        -primary,
        row["evaluation"]["summary"].get("median_turnover") or 999,
        row["factor_instance_id"],
    )


def _checkpoint(repository, program_id: str, usage: dict, calls: list[dict],
                status: str, *, terminal: bool = False, extra: dict | None = None) -> str:
    identity = {
        "schema_version": "archetype-aware-program-checkpoint-v1",
        "record_type": "terminal_report" if terminal else "checkpoint",
        "provider_id": "tushare-pro-v1", "program_id": program_id,
        "status": status, "checkpoint_sequence": len(calls),
        "budget_usage": usage, "rounds": calls,
        "agent_closed": terminal, "planner_closed": terminal,
        "memories_frozen": terminal, "parameters_frozen": terminal,
        "archetypes_frozen": terminal, "promotion_writes": 0,
    } | (extra or {})
    receipt = repository.publish(
        "archetype_aware_program_report", identity,
        {"program_report.json": identity}, lineage=(program_id, *[
            row["response_artifact_id"] for row in calls if row.get("response_artifact_id")
        ]),
    )
    return receipt["artifact_id"]


def _normalize_and_admit(raw: dict, *, round_number: int, family: str,
                         lane_id: str, archetype: str, allowed_features: set[str],
                         known_fingerprints: set[str], index: int) -> dict:
    if raw.get("lane_id") != lane_id or raw.get("factor_family") != family:
        raise ValueError("ALPHA_LANE_OR_FAMILY_MISMATCH")
    if not raw.get("primary_archetype") or not raw.get("primary_test_statistic"):
        raise ValueError("ALPHA_ARCHETYPE_MISSING")
    if raw["primary_archetype"] != archetype:
        raise ValueError("POST_HOC_ALPHA_ARCHETYPE_SWITCH")
    if raw["primary_test_statistic"] != ARCHETYPES[archetype]["primary_test_statistic"]:
        raise ValueError("ALPHA_PRIMARY_TEST_MISMATCH")
    normalized = validate_proposal_parameter_contract(
        _strip_archetype(raw), index, maximum_trials=7,
    )
    normalized["_round_number"] = round_number
    normalized["_factor_family"] = family
    result = admit_proposal(
        normalized, allowed_features=allowed_features,
        allowed_operators=set(OPERATORS), known_fingerprints=known_fingerprints,
    )
    if not result["admitted"]:
        raise ValueError(result["failure_code"])
    return result["proposal"] | {
        "primary_archetype": archetype,
        "primary_hypothesis": raw["primary_hypothesis"],
        "primary_test_statistic": raw["primary_test_statistic"],
        "lane_id": lane_id, "round_id": raw["round_id"],
    }


def _local_spaces(proposal: dict) -> dict[str, list[Any]]:
    return {
        name: list(space["values"])
        for name, space in proposal["parameter_search"]["search_space"].items()
    }


def execute_program(*, program_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None, agent_caller=call_structured_codex,
                    stop_after_round: int | None = None,
                    retrospective_only: bool = False) -> dict:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(program_id)
    if spec.get("schema_version") != "archetype-aware-alpha-program-spec-v1":
        raise ValueError("Archetype-aware Program Spec is absent")
    terminal = [
        row for row in _identities(repository, "archetype_aware_program_report", program_id)
        if row.get("record_type") == "terminal_report"
    ]
    if terminal:
        return replay_program(
            program_id=program_id, repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay", store_root=store_root,
        ) | {"exact_existing": True}
    catalog = repository.identity(spec["feature_catalog_v2_id"])
    if not catalog.get("research_terminal_features"):
        report_id = _checkpoint(
            repository, program_id, empty_usage(), [], "completed_no_new_feature",
            terminal=True, extra={"feature_catalog_v2_id": spec["feature_catalog_v2_id"]},
        )
        return {"status": "completed_no_new_feature", "program_id": program_id, "report_id": report_id}
    matrix, family_features = _feature_matrix(repository, catalog, bundle, Path(work_root) / "matrix")
    features = [name for name in matrix if name not in {
        "symbol", "trade_date", "raw_label", "model_label", "sample_weight",
        "next_tradable", "next_locked_limit",
    }]
    contract = _snapshot_contract(SOURCE_DATASET_ID, features, matrix["trade_date"].nunique())
    correlation_root = Path(work_root) / "evaluation" / "existing-factor-correlation"
    if correlation_root.exists():
        shutil.rmtree(correlation_root)
    evaluator = CampaignEvaluator(
        bundle=bundle, matrix=matrix, contract=contract, work_root=Path(work_root) / "evaluation",
    )
    evaluator.known_values = [
        (
            name,
            values.assign(
                trade_date=pd.to_datetime(values["trade_date"]).dt.strftime("%Y-%m-%d")
            ),
        )
        for name, values in evaluator.known_values
    ]
    normalized = bundle.normalized.copy() if isinstance(bundle.normalized, pd.DataFrame) else pd.read_parquet(bundle.normalized)
    usage = empty_usage()
    prior_responses = {
        row["call_index"]: row
        for row in _identities(repository, "archetype_aware_alpha_proposal", program_id)
        if row.get("record_type") == "agent_response"
    }
    prior_evaluations = {
        (row["call_index"], row["proposal_ordinal"]): row
        for row in _identities(repository, "archetype_aware_alpha_proposal", program_id)
        if row.get("record_type") == "adaptive_evaluation"
    }
    calls: list[dict] = []
    candidates: list[dict] = []
    failures: list[str] = []
    known_fingerprints: set[str] = set()
    lane_counts = Counter()
    family_counts = Counter()
    archetype_counts = Counter()
    for call_index in range(1, spec["budgets"]["maximum_agent_calls"] + 1):
        lane_id = list(LANES)[(call_index - 1) % 3]
        families = LANES[lane_id]["families"]
        family = families[lane_counts[lane_id] % len(families)]
        archetype = "monotonic_rank_factor" if call_index % 2 else "top_tail_selection_factor"
        allowed = _allowed_features(lane_id, family_features, set(features))
        if not allowed:
            failures.append("ALPHA_LANE_HAS_NO_FEATURES")
            continue
        prior = prior_responses.get(call_index)
        if prior is None:
            goal_id = "aag1_" + hash_payload({"program": program_id, "call": call_index, "lane": lane_id})
            response, evidence = agent_caller(
                prompt=_prompt(
                    spec=spec | {"program_spec_id": program_id}, lane_id=lane_id,
                    family=family, archetype=archetype, call_index=call_index,
                    allowed_features=allowed, known_fingerprints=sorted(known_fingerprints),
                    failure_summary=failures,
                ),
                schema=alpha_agent_schema(), model=spec["model"],
            )
            if response.get("goal_id") != goal_id or response.get("iteration") != call_index:
                raise ValueError("Alpha Agent response goal/iteration mismatch")
            identity = {
                "schema_version": "archetype-aware-agent-response-v1",
                "record_type": "agent_response", "provider_id": "tushare-pro-v1",
                "program_id": program_id, "call_index": call_index,
                "lane_id": lane_id, "factor_family": family,
                "required_primary_archetype": archetype,
                "provider_evidence": evidence, "maximum_metric_date": "2020-12-31",
                "validation_evidence_access": False, "report_evidence_access": False,
                "fresh_evidence_access": False, "promotion_writes": 0,
            }
            receipt = repository.publish(
                "archetype_aware_alpha_proposal", identity,
                {"agent_response.json": response, "agent_contract.json": {
                    "allowed_features": allowed, "primary_archetype": archetype,
                    "primary_test_statistic": ARCHETYPES[archetype]["primary_test_statistic"],
                    "maximum_metric_date": "2020-12-31",
                }},
                lineage=(program_id, spec["feature_catalog_v2_id"], spec["archetype_contract_id"]),
            )
            response_artifact_id = receipt["artifact_id"]
        else:
            root = repository.materialize(prior["artifact_id"])
            response = json.loads((root / "agent_response.json").read_text())
            response_artifact_id = prior["artifact_id"]
        usage["agent_calls"] += 1
        usage["rounds"] += 1
        lane_counts[lane_id] += 1
        family_counts[family] += 1
        archetype_counts[archetype] += 1
        call_record = {
            "call_index": call_index, "lane_id": lane_id, "factor_family": family,
            "primary_archetype": archetype, "response_artifact_id": response_artifact_id,
            "proposal_artifact_ids": [],
        }
        for ordinal, raw in enumerate(response.get("proposals", [])[:3], 1):
            if usage["proposals"] >= spec["budgets"]["maximum_proposals"]:
                break
            usage["proposals"] += 1
            existing = prior_evaluations.get((call_index, ordinal))
            if existing is not None:
                call_record["proposal_artifact_ids"].append(existing["artifact_id"])
                if existing.get("admitted"):
                    usage["admissions"] += 1
                    candidate = existing["candidate"]
                    candidates.append(candidate)
                    known_fingerprints.add(candidate["structural_fingerprint"])
                    usage["adaptive_qlib_calls"] += candidate["evaluation"].get("qlib_calls", 0)
                    usage["local_rescue_trials"] += len(candidate.get("local_rescue_trials", []))
                    usage["adaptive_qlib_calls"] += sum(
                        row.get("qlib_calls", 0) for row in candidate.get("local_rescue_trials", [])
                    )
                continue
            try:
                proposal = _normalize_and_admit(
                    raw, round_number=call_index, family=family, lane_id=lane_id,
                    archetype=archetype, allowed_features=set(allowed),
                    known_fingerprints=known_fingerprints, index=ordinal - 1,
                )
                usage["admissions"] += 1
                known_fingerprints.add(proposal["structural_fingerprint"])
                defaults = proposal["default_parameters"]
                orientation = choose_orientation(
                    evaluator=evaluator, normalized=normalized, proposal=proposal,
                    parameters=defaults, start="2019-01-02", end="2020-12-31",
                )
                selected = evaluate_locked(
                    evaluator=evaluator, normalized=normalized, proposal=proposal,
                    parameters=defaults, orientation=orientation,
                    periods=ADAPTIVE_YEARS, phase="adaptive",
                )
                usage["adaptive_qlib_calls"] += selected["qlib_calls"]
                optimization_mode = "default_parameters"
                local_rows = []
                if not selected["summary"]["gate_passed"] and defaults:
                    neighbors = local_factor_neighborhood(defaults, _local_spaces(proposal))[1:3]
                    for parameters in neighbors:
                        if usage["local_rescue_trials"] >= spec["budgets"]["maximum_local_rescue_trials"]:
                            break
                        row = evaluate_locked(
                            evaluator=evaluator, normalized=normalized, proposal=proposal,
                            parameters=parameters, orientation=orientation,
                            periods=ADAPTIVE_YEARS, phase="adaptive",
                        )
                        usage["local_rescue_trials"] += 1
                        usage["adaptive_qlib_calls"] += row["qlib_calls"]
                        local_rows.append({
                            key: value for key, value in row.items() if key != "values"
                        })
                        if row["summary"]["gate_passed"]:
                            selected = row
                            optimization_mode = "local_optimization_research"
                            break
                candidate = {
                    "proposal": proposal, "lane_id": lane_id, "factor_family": family,
                    "primary_archetype": archetype,
                    "primary_test_statistic": proposal["primary_test_statistic"],
                    "factor_template_id": proposal["factor_template_id"],
                    "factor_instance_id": selected["factor_instance_id"],
                    "structural_fingerprint": proposal["structural_fingerprint"],
                    "selected_parameters": selected["parameters"],
                    "orientation": orientation, "orientation_frozen": True,
                    "archetype_frozen_before_evaluation": True,
                    "optimization_mode": optimization_mode,
                    "optimization_rescued": optimization_mode != "default_parameters",
                    "evaluation": {key: value for key, value in selected.items() if key != "values"},
                    "local_rescue_trials": local_rows,
                    "adaptive_rank_input_only": True,
                }
                identity = {
                    "schema_version": "archetype-aware-adaptive-evaluation-v1",
                    "record_type": "adaptive_evaluation", "provider_id": "tushare-pro-v1",
                    "program_id": program_id, "call_index": call_index,
                    "proposal_ordinal": ordinal, "agent_response_artifact_id": response_artifact_id,
                    "admitted": True, "candidate": candidate,
                    "validation_evidence_used": False, "report_evidence_used": False,
                    "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
                    "promotion_writes": 0,
                }
                receipt = repository.publish(
                    "archetype_aware_alpha_proposal", identity,
                    {"adaptive_evaluation.json": identity},
                    lineage=(program_id, response_artifact_id),
                )
                call_record["proposal_artifact_ids"].append(receipt["artifact_id"])
                candidates.append(candidate)
                evaluator.known_values.append((selected["factor_instance_id"], selected["values"]))
            except Exception as exc:
                code = str(exc)[:180]
                failures.append(code)
                identity = {
                    "schema_version": "archetype-aware-adaptive-evaluation-v1",
                    "record_type": "adaptive_evaluation", "provider_id": "tushare-pro-v1",
                    "program_id": program_id, "call_index": call_index,
                    "proposal_ordinal": ordinal, "agent_response_artifact_id": response_artifact_id,
                    "admitted": False, "failure_code": code,
                    "validation_evidence_used": False, "promotion_writes": 0,
                }
                receipt = repository.publish(
                    "archetype_aware_alpha_proposal", identity,
                    {"adaptive_evaluation.json": identity},
                    lineage=(program_id, response_artifact_id),
                )
                call_record["proposal_artifact_ids"].append(receipt["artifact_id"])
        calls.append(call_record)
        _checkpoint(repository, program_id, usage, calls, "running_adaptive_research")
        if stop_after_round and call_index >= stop_after_round:
            return {
                "status": "paused_recoverable_error", "program_id": program_id,
                "budget_usage": usage, "rounds": calls,
            }
        minimum = spec["budgets"]
        if (
            call_index >= minimum["minimum_rounds_before_improvement_stop"]
            and usage["admissions"] >= minimum["minimum_admissions_before_improvement_stop"]
            and len(family_counts) >= minimum["minimum_distinct_families_before_improvement_stop"]
            and len(lane_counts) == 3 and len(archetype_counts) == 2
            and not any(row["evaluation"]["summary"]["gate_passed"] for row in candidates[-6:])
        ):
            break
    if usage["rounds"] < 12 or len(lane_counts) < 3 or len(archetype_counts) < 2:
        raise ValueError("Program minimum coverage was not completed")
    shortlist = sorted(
        [row for row in candidates if row["evaluation"]["summary"]["gate_passed"]],
        key=_adaptive_rank,
    )[:spec["budgets"]["maximum_union_shortlist"]]
    for rank, row in enumerate(shortlist, 1):
        row["union_adaptive_rank"] = rank
    lock = {
        "schema_version": "archetype-aware-union-shortlist-lock-v1",
        "provider_id": "tushare-pro-v1", "program_id": program_id,
        "feature_catalog_v2_id": spec["feature_catalog_v2_id"],
        "archetype_contract_id": spec["archetype_contract_id"],
        "agent_closed": True, "planner_closed": True, "memories_frozen": True,
        "parameters_frozen": True, "orientations_frozen": True,
        "archetypes_frozen": True, "locked_validation_reads_at_lock": 0,
        "objects": shortlist, "object_count": len(shortlist),
        "validation_used_for_ranking": False, "promotion_writes": 0,
    }
    lock_receipt = repository.publish(
        "archetype_aware_union_shortlist_lock", lock,
        {"union_shortlist_lock.json": lock},
        lineage=(program_id, *[row["factor_instance_id"] for row in shortlist]),
    )
    validation_rows = []
    prior_validations = {}
    for kind in ("monotonic_alpha_validation", "tail_alpha_validation"):
        for row in _identities(repository, kind, program_id):
            prior_validations[row["result"]["factor_instance_id"]] = row
    for locked in shortlist:
        prior_validation = prior_validations.get(locked["factor_instance_id"])
        if prior_validation is not None:
            result = prior_validation["result"]
            _, values = factor_values(
                parse_template(locked["proposal"]["template"]), evaluator.contract,
                locked["selected_parameters"], evaluator.matrix,
            )
            result = result | {"values": values}
            artifact_id = prior_validation["artifact_id"]
        else:
            result = evaluate_locked(
                evaluator=evaluator, normalized=normalized, proposal=locked["proposal"],
                parameters=locked["selected_parameters"], orientation=locked["orientation"],
                periods=VALIDATION_YEARS, phase="validation",
            )
            artifact_id = None
        usage["validation_objects"] += 1
        usage["validation_qlib_calls"] += result["qlib_calls"]
        usage["locked_validation_reads"] += result["qlib_calls"]
        if (
            result["parameters"] != locked["selected_parameters"]
            or result["orientation"] != locked["orientation"]
            or result["primary_archetype"] != locked["primary_archetype"]
        ):
            raise ValueError("POST_HOC_ALPHA_ARCHETYPE_SWITCH")
        kind = (
            "monotonic_alpha_validation"
            if locked["primary_archetype"] == "monotonic_rank_factor"
            else "tail_alpha_validation"
        )
        identity = {
            "schema_version": f"{kind}-v1", "provider_id": "tushare-pro-v1",
            "program_id": program_id, "union_shortlist_lock_id": lock_receipt["artifact_id"],
            "union_adaptive_rank": locked["union_adaptive_rank"],
            "parameters_unchanged": True, "orientation_unchanged": True,
            "archetype_unchanged": True,
            "validation_used_for_ranking": False,
            "result": {key: value for key, value in result.items() if key != "values"},
            "promotion_writes": 0,
        }
        if artifact_id is None:
            receipt = repository.publish(
                kind, identity, {"validation.json": identity},
                lineage=(program_id, lock_receipt["artifact_id"]),
            )
            artifact_id = receipt["artifact_id"]
        validation_rows.append((locked, result, artifact_id))
    multiple = benjamini_hochberg([
        {
            "validation_id": artifact_id,
            "factor_instance_id": result["factor_instance_id"],
            "primary_archetype": result["primary_archetype"],
            "primary_test_statistic": result["primary_test_statistic"],
            "raw_p_value": result["statistical_test"]["raw_p_value"],
        }
        for _, result, artifact_id in validation_rows
    ], q=.10)
    control = {
        "schema_version": "archetype-multiple-testing-control-v1",
        "provider_id": "tushare-pro-v1", "program_id": program_id,
        "union_shortlist_lock_id": lock_receipt["artifact_id"],
        "method": "Benjamini-Hochberg", "global_across_archetypes": True,
        "one_primary_p_value_per_object": True, "fdr_q": .10,
        "results": multiple, "promotion_writes": 0,
    }
    control_receipt = repository.publish(
        "archetype_multiple_testing_control", control,
        {"multiple_testing.json": control},
        lineage=(program_id, lock_receipt["artifact_id"], *[row[2] for row in validation_rows]),
    )
    multiple_by_id = {row["validation_id"]: row for row in multiple}
    survivors = []
    failure_ids = []
    for locked, result, artifact_id in validation_rows:
        test = multiple_by_id[artifact_id]
        passed = (
            result["summary"]["gate_passed"]
            and test["multiple_testing_passed"]
            and result["statistical_test"]["raw_p_value"] <= 1
        )
        if passed:
            survivors.append((locked, result, artifact_id, test))
            continue
        failure = {
            "schema_version": "archetype-alpha-validation-failure-v1",
            "provider_id": "tushare-pro-v1", "program_id": program_id,
            "validation_id": artifact_id, "factor_instance_id": result["factor_instance_id"],
            "primary_archetype": result["primary_archetype"],
            "primary_test_statistic": result["primary_test_statistic"],
            "failed_gates": result["summary"]["failed_gates"] + (
                [] if test["multiple_testing_passed"] else ["benjamini_hochberg_fdr"]
            ),
            "raw_p_value": test["raw_p_value"], "adjusted_q_value": test["adjusted_q_value"],
            "registry_write": False, "promotion_writes": 0,
        }
        receipt = repository.publish(
            "archetype_alpha_validation_failure", failure,
            {"validation_failure.json": failure},
            lineage=(program_id, artifact_id, control_receipt["artifact_id"]),
        )
        failure_ids.append(receipt["artifact_id"])
    survivors = sorted(survivors, key=lambda row: row[0]["union_adaptive_rank"])[
        :spec["budgets"]["maximum_final_survivors"]
    ]
    candidate_ids, fresh_ids, report_rows, retrospective_survivors = [], [], [], []
    for locked, result, validation_id, test in survivors:
        if retrospective_only:
            retrospective_survivors.append({
                "lane_id": locked["lane_id"],
                "primary_archetype": locked["primary_archetype"],
                "primary_test_statistic": locked["primary_test_statistic"],
                "factor_template_id": locked["factor_template_id"],
                "factor_instance_id": result["factor_instance_id"],
                "formula": locked["proposal"]["canonical_dsl"],
                "canonical_ast": locked["proposal"]["canonical_ast"],
                "parameters": locked["selected_parameters"],
                "orientation": locked["orientation"],
                "historical_metrics": result["summary"],
                "validation_id": validation_id,
                "adjusted_q_value": test["adjusted_q_value"],
                "search_exposure": {
                    "agent_calls": usage["agent_calls"],
                    "proposals": usage["proposals"],
                    "admissions": usage["admissions"],
                    "local_rescue_trials": usage["local_rescue_trials"],
                },
            })
            continue
        candidate = {
            "schema_version": "archetype-alpha-candidate-lock-v1",
            "provider_id": "tushare-pro-v1", "program_id": program_id,
            "lane_id": locked["lane_id"], "primary_archetype": locked["primary_archetype"],
            "primary_test_statistic": locked["primary_test_statistic"],
            "feature_catalog_v2_id": spec["feature_catalog_v2_id"],
            "factory_feature_ids": [
                row["feature_id"] for row in catalog["research_terminal_features"]
                if row["feature_name"] in locked["proposal"]["input_features"]
            ],
            "union_shortlist_lock_id": lock_receipt["artifact_id"],
            "factor_template_id": locked["factor_template_id"],
            "factor_instance_id": result["factor_instance_id"],
            "canonical_dsl": locked["proposal"]["canonical_dsl"],
            "canonical_ast": locked["proposal"]["canonical_ast"],
            "selected_parameters": locked["selected_parameters"],
            "orientation": locked["orientation"], "status": "research_registered",
            "locked_validation_passed": True, "multiple_testing_passed": True,
            "adjusted_q_value": test["adjusted_q_value"],
            "search_exposure": {
                "agent_calls": usage["agent_calls"], "proposals": usage["proposals"],
                "admissions": usage["admissions"], "local_rescue_trials": usage["local_rescue_trials"],
            },
            "not_fresh_validated": True, "usable_for_production": False,
            "promotion_writes": 0,
        }
        receipt = repository.publish(
            "autonomous_factor_candidate_lock", candidate,
            {"candidate_lock.json": candidate},
            lineage=(program_id, validation_id, control_receipt["artifact_id"]),
        )
        candidate_ids.append(receipt["artifact_id"])
        reports = evaluate_locked(
            evaluator=evaluator, normalized=normalized, proposal=locked["proposal"],
            parameters=locked["selected_parameters"], orientation=locked["orientation"],
            periods=REPORT_PERIODS, phase="contaminated_report",
        )
        usage["report_qlib_calls"] += reports["qlib_calls"]
        report_rows.append({
            "candidate_id": receipt["artifact_id"],
            "result": {key: value for key, value in reports.items() if key != "values"},
            "contaminated_report_only": True, "not_used_for_selection": True,
            "not_used_for_planning": True, "not_used_for_validation": True,
            "not_fresh_validation": True,
        })
        latest, fresh_start = _latest_and_fresh(bundle, matrix)
        fresh = {
            "schema_version": "archetype-alpha-fresh-lock-v1",
            "provider_id": "tushare-pro-v1", "program_id": program_id,
            "candidate_id": receipt["artifact_id"],
            "primary_archetype": locked["primary_archetype"],
            "primary_test_statistic": locked["primary_test_statistic"],
            "formula": locked["proposal"]["canonical_dsl"],
            "parameters": locked["selected_parameters"], "orientation": locked["orientation"],
            "strategy_protocol": spec["strategy_protocol"],
            "universe": spec["universe"], "benchmark": spec["benchmark"],
            "latest_market_data_date_used": latest, "fresh_start_date": fresh_start,
            "no_backfill": True, "minimum_fresh_trading_days": 60,
            "minimum_completed_holding_windows": 5, "minimum_rebalance_periods": 3,
            "status": "locked_awaiting_fresh_data", "promotion_writes": 0,
        }
        fresh_receipt = repository.publish(
            "archetype_alpha_fresh_lock", fresh, {"fresh_lock.json": fresh},
            lineage=(program_id, receipt["artifact_id"]),
        )
        fresh_ids.append(fresh_receipt["artifact_id"])
    usage["final_survivors"] = len(retrospective_survivors) if retrospective_only else len(candidate_ids)
    state = (
        "completed_with_retrospective_survivors" if retrospective_survivors
        else
        "completed_with_survivors" if candidate_ids
        else "completed_no_union_shortlist" if not shortlist
        else "completed_no_validation_survivor"
    )
    report_id = _checkpoint(
        repository, program_id, usage, calls, state, terminal=True,
        extra={
            "feature_catalog_v2_id": spec["feature_catalog_v2_id"],
            "archetype_contract_id": spec["archetype_contract_id"],
            "lane_completion": {lane: lane_counts[lane] for lane in LANES},
            "factor_family_attempts": dict(family_counts),
            "archetype_attempts": dict(archetype_counts),
            "union_shortlist_lock_id": lock_receipt["artifact_id"],
            "union_shortlist_count": len(shortlist),
            "validation_ids": [row[2] for row in validation_rows],
            "multiple_testing_id": control_receipt["artifact_id"],
            "validation_failure_ids": failure_ids,
            "candidate_lock_ids": candidate_ids, "fresh_lock_ids": fresh_ids,
            "retrospective_survivors": retrospective_survivors,
            "retrospective_only": retrospective_only,
            "contaminated_reports": report_rows,
            "manual_intervention_count": 0,
            "manual_alpha_round_planning_count": 0,
            "manual_archetype_switching_count": 0,
            "validation_used_for_ranking": False,
            "contaminated_reports_used_for_selection": False,
            "fresh_evidence_used": False,
        },
    )
    return {
        "status": state, "program_id": program_id, "report_id": report_id,
        "union_shortlist_lock_id": lock_receipt["artifact_id"],
        "validation_ids": [row[2] for row in validation_rows],
        "multiple_testing_id": control_receipt["artifact_id"],
        "validation_failure_ids": failure_ids,
        "candidate_lock_ids": candidate_ids, "fresh_lock_ids": fresh_ids,
        "retrospective_survivors": retrospective_survivors,
        "budget_usage": usage, "store_integrity": repository.integrity(),
    }


def resume_program(**kwargs) -> dict:
    return execute_program(**kwargs)


def inspect_program(*, program_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(program_id)
    reports = _identities(repository, "archetype_aware_program_report", program_id)
    terminal = [row for row in reports if row.get("record_type") == "terminal_report"]
    return {"program_spec": spec, "latest_report": terminal[-1] if terminal else (reports[-1] if reports else None)}


def validate_program(**kwargs) -> dict:
    inspected = inspect_program(**kwargs)
    report = inspected["latest_report"]
    if not report or report.get("record_type") != "terminal_report":
        raise ValueError("Program terminal report is absent")
    usage = report["budget_usage"]
    if usage["rounds"] < 12 and report["status"] != "completed_no_new_feature":
        raise ValueError("Program stopped before minimum coverage")
    if usage["strategy_optimization_calls"] or usage["combined_optimization_calls"] or usage["promotion_writes"]:
        raise ValueError("Program crossed frozen optimization/Promotion boundary")
    return {
        "status": "valid", "program_id": kwargs["program_id"],
        "terminal_state": report["status"], "report_id": report["artifact_id"],
    }


def replay_program(*, program_id: str, repository_root: Path, work_root: Path,
                   store_root: Path | None = None) -> dict:
    result = validate_program(
        program_id=program_id, repository_root=repository_root,
        work_root=work_root, store_root=store_root,
    )
    return result | {
        "status": "exact_replay", "feature_agent_calls": 0, "alpha_agent_calls": 0,
        "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "qlib_calls": 0, "tushare_calls": 0,
        "network_data_calls": 0, "feature_writes": 0, "registry_writes": 0,
        "fresh_lock_writes": 0, "new_artifacts": 0, "new_blobs": 0,
        "promotion_writes": 0,
    }
