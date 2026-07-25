from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.archetype_alpha_program.orchestrator import (
    _allowed_features,
    _feature_matrix,
    _normalize_and_admit,
)
from backend.services.engine.archetype_alpha_program.schemas import alpha_agent_schema
from backend.services.engine.autonomous_factor_campaign.evaluation import (
    CampaignEvaluator,
    signal_similarity,
)
from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg,
)
from backend.services.engine.autonomous_technical_feature_factory.agent import (
    call_structured_codex,
)
from backend.services.engine.default_first_momentum_search.engine import _clean_result
from backend.services.engine.default_first_momentum_search.protocol import (
    LIFECYCLE_POLICY,
    SOURCE_DATASET_ID,
)
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.fixed_configuration_model_program.engine import (
    _bundle_payloads,
    _catalog,
    _model_matrix,
)
from backend.services.engine.momentum_factor_iteration.engine import _snapshot_contract
from backend.services.engine.optimization_governance.engine import (
    local_factor_neighborhood,
)
from backend.services.engine.rolling_blind_alpha_discovery.engine import (
    FRESH_COHORT_ID,
    _fresh_identity_snapshot,
    _mean_test,
)
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner,
    factor_values,
    oriented_signal,
    split_metrics,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .models import CrossSectionalDiscoveryBatchSpecV1, empty_counts
from .ranking import (
    RankingModelSpecV1,
    RankingRelevanceLabelV1,
    train_ranking_fold,
)
from .residualization import (
    CONTROL_NAMES,
    CrossSectionalStyleResidualizationV1,
    build_style_controls,
    residualize_scores,
)


TERMINAL_STATUSES = {
    "completed_with_survivors",
    "completed_no_survivor",
    "completed_no_batch_lock_candidate",
    "completed_early_stop",
}
DISCOVERY = ("2019-01-02", "2021-12-31")
R3_001_BATCH_ID = (
    "rbdb1_6ca989dfab231a2b57fb3679d2dbca8006a370bc082d1b6b2f55840479f88851"
)


def _repository(
    repository_root: Path, work_root: Path, store_root: Path | None
) -> tuple[Any, CampaignRepository]:
    return _runtime(Path(repository_root), Path(work_root), store_root)


def _rows(
    repository: CampaignRepository, kind: str, batch_id: str | None = None
) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind(kind):
        identity = repository.identity(descriptor.artifact_id)
        if batch_id is None or (
            identity.get("rolling_blind_discovery_batch_id") == batch_id
            or identity.get("parent_batch_id") == batch_id
            or batch_id in descriptor.lineage
        ):
            rows.append(identity | {"artifact_id": descriptor.artifact_id})
    return rows


def _publish(
    repository: CampaignRepository,
    kind: str,
    identity: dict[str, Any],
    filename: str,
    *,
    lineage: tuple[str, ...] = (),
    files: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = {filename: identity}
    payload.update(files or {})
    receipt = repository.publish(kind, identity, payload, lineage=lineage)
    return receipt["artifact_id"], receipt


def create_batch(
    *,
    supervisor_id: str,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    bundle, repository = _repository(repository_root, work_root, store_root)
    supervisor = repository.identity(supervisor_id)
    if supervisor.get("schema_version") not in {
        "autonomous-research-supervisor-spec-v1",
        "autonomous-research-supervisor-v1",
        "autonomous-research-supervisor-v2",
    }:
        raise ValueError("Supervisor identity is invalid")
    window_set = repository.identity(
        CrossSectionalDiscoveryBatchSpecV1().rolling_window_set_id
    )
    if (
        window_set.get("complete_window_count") != 18
        or window_set["windows"][0]["start_date"] != "2022-01-04"
        or window_set["windows"][-1]["end_date"] != "2026-06-23"
    ):
        raise ValueError("R3-001 frozen rolling Window Set changed")
    controls, control_audit = build_style_controls(bundle)
    contract = CrossSectionalStyleResidualizationV1().payload(
        control_audit=control_audit
    )
    residual_id, residual_receipt = _publish(
        repository,
        "cross_sectional_style_residualization",
        contract,
        "residualization_contract.json",
        lineage=(SOURCE_DATASET_ID,),
    )
    label = RankingRelevanceLabelV1().payload()
    label_id, label_receipt = _publish(
        repository,
        "ranking_relevance_label",
        label,
        "ranking_relevance_label.json",
        lineage=(bundle.authority["label_dataset_id"],),
    )
    ranking = RankingModelSpecV1().payload(relevance_label_id=label_id)
    ranking_id, ranking_receipt = _publish(
        repository,
        "ranking_model_spec",
        ranking,
        "ranking_model_spec.json",
        lineage=(label_id, CrossSectionalDiscoveryBatchSpecV1().feature_catalog_id),
    )
    batch = CrossSectionalDiscoveryBatchSpecV1().payload(
        supervisor_id=supervisor_id,
        residualization_id=residual_id,
        ranking_model_spec_id=ranking_id,
        ranking_label_id=label_id,
    )
    batch_id, batch_receipt = _publish(
        repository,
        "rolling_blind_discovery_batch",
        batch,
        "cross_sectional_batch.json",
        lineage=(
            supervisor_id,
            batch["rolling_window_set_id"],
            residual_id,
            label_id,
            ranking_id,
        ),
    )
    return batch | {
        "rolling_blind_discovery_batch_id": batch_id,
        "status": "batch_frozen",
        "style_control_columns": list(controls.columns),
        "new_artifacts": sum(
            int(not row["exact_existing"])
            for row in (
                residual_receipt,
                label_receipt,
                ranking_receipt,
                batch_receipt,
            )
        ),
        "new_blobs": sum(
            row["new_blob_count"]
            for row in (
                residual_receipt,
                label_receipt,
                ranking_receipt,
                batch_receipt,
            )
        ),
    }


def _agent_schema() -> dict[str, Any]:
    schema = alpha_agent_schema()
    item = schema["properties"]["proposals"]["items"]
    item["properties"]["why_style_residualization_is_relevant"] = {
        "type": "string"
    }
    item["required"].append("why_style_residualization_is_relevant")
    return schema


def _schedule() -> list[tuple[str, str]]:
    families = (
        "trend_geometry",
        "liquidity_amount_dynamics",
        "relative_strength",
        "path_asymmetry",
        "volatility_shape",
        "price_volume_lead_lag",
        "range_compression_expansion",
        "robust_trend_location",
        "return_path_asymmetry",
    )
    lanes = (
        "trend_geometry_lane",
        "trading_confirmation_lane",
        "relative_asymmetric_lane",
    )
    return [(lanes[index % 3], families[index % len(families)]) for index in range(18)]


def _prompt(
    *,
    batch_id: str,
    call_index: int,
    lane: str,
    family: str,
    allowed: list[str],
    fingerprints: list[str],
    failures: list[str],
) -> str:
    goal_id = "csag1_" + hash_payload(
        {"batch": batch_id, "call": call_index, "lane": lane, "family": family}
    )
    request = {
        "goal_id": goal_id,
        "iteration": call_index,
        "program_id": batch_id,
        "lane_id": lane,
        "round_id": f"style-residual-{call_index:02d}",
        "factor_family": family,
        "required_primary_archetype": "monotonic_rank_factor",
        "required_primary_test_statistic": "daily_official_label_rankic",
        "allowed_features": allowed,
        "allowed_operators": [
            "add",
            "subtract",
            "multiply",
            "divide",
            "negate",
            "absolute",
            "clip",
            "lag",
            "delta",
            "rolling_mean",
            "rolling_std",
            "rolling_min",
            "rolling_max",
            "cs_rank",
            "cs_zscore",
        ],
        "maximum_proposals": 3,
        "maximum_terminal_features": 3,
        "maximum_parameters": 1,
        "maximum_ast_depth": 6,
        "required_fields": [
            "economic_hypothesis in primary_hypothesis",
            "canonical DSL in template",
            "default_parameters",
            "expected_holding_horizon",
            "why_style_residualization_is_relevant",
        ],
        "fixed_style_controls": list(CONTROL_NAMES),
        "known_structural_fingerprints": fingerprints[-80:],
        "unlabeled_admission_failures": failures[-12:],
        "forbidden": [
            "rolling-window metrics",
            "Fresh metrics",
            "returns as residualization controls",
            "industry neutralization",
            "strategy parameters",
            "more than one parameter",
        ],
    }
    return (
        "You propose simple PIT-safe technical structures for a fixed same-date "
        "style-residual Alpha lane. Return exactly one schema-valid JSON object and "
        "exactly three proposals. Copy REQUEST identity fields exactly. Each proposal "
        "must use one to three allowed Terminal Features, at most one genuine "
        "optimizable parameter and AST depth at most six. The execution layer always "
        "residualizes the raw score against the four fixed controls; do not put those "
        "controls into the DSL merely to emulate residualization. Explain the economic "
        "hypothesis, holding horizon and why residualization is relevant. Never emit "
        "metrics, data, paths, code or secrets. REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _metric(values: pd.DataFrame, matrix: pd.DataFrame, period: tuple[str, str]) -> dict:
    result = split_metrics(values, matrix, *period, 1)
    return {
        "coverage": result.get("factor_finite_coverage"),
        "mean_rankic": result.get("mean_rank_ic"),
        "rankic_positive_rate": result.get("rank_ic_positive_rate"),
    }


def _evaluate_residual_candidate(
    *,
    proposal: dict,
    parameters: dict,
    evaluator: CampaignEvaluator,
    controls: pd.DataFrame,
    work_root: Path,
    key: str,
) -> dict[str, Any]:
    compiled, raw = factor_values(
        parse_template(proposal["template"]),
        evaluator.contract,
        parameters,
        evaluator.matrix,
    )
    residual, evidence = residualize_scores(raw, controls)
    raw_metric = _metric(raw, evaluator.matrix, DISCOVERY)
    positive = _metric(residual, evaluator.matrix, DISCOVERY)
    orientation = 1 if (positive["mean_rankic"] or 0.0) >= 0 else -1
    if orientation == -1:
        residual["factor_value"] *= -1
        positive = _metric(residual, evaluator.matrix, DISCOVERY)
    similarities = [
        signal_similarity(residual[["symbol", "trade_date", "factor_value"]], prior)
        for _, prior in evaluator.known_values
    ]
    maximum = max(
        (
            abs(row["spearman"])
            for row in similarities
            if row.get("spearman") is not None
        ),
        default=0.0,
    )
    signal = oriented_signal(
        residual[["symbol", "trade_date", "factor_value"]],
        1,
        work_root / "signals" / f"{key}.parquet",
    )
    qlib = _clean_result(
        evaluator.qlib.run(
            signal,
            *DISCOVERY,
            topk=20,
            n_drop=5,
            rebalance_days=10,
            lifecycle_policy=LIFECYCLE_POLICY,
        )
    )
    checks = {
        "coverage": (positive["coverage"] or 0.0) >= 0.90,
        "pit": evidence["pit_violation_count"] == 0,
        "mean_rankic": (positive["mean_rankic"] or -999.0) > 0,
        "turnover": (qlib.get("turnover") or 999.0) <= 35,
        "concentration": (qlib.get("best_10_days_contribution") or 999.0) <= 0.35,
        "independence": maximum < 0.85,
    }
    return {
        "factor_instance_id": compiled.factor_instance_id,
        "parameters": parameters,
        "orientation": orientation,
        "raw_metric": raw_metric,
        "residual_metric": positive,
        "residualization_evidence": evidence,
        "qlib": qlib,
        "maximum_existing_spearman": maximum,
        "gate": {
            "checks": checks,
            "passed": all(checks.values()),
            "failed_gates": [name for name, passed in checks.items() if not passed],
        },
        "values": residual[["symbol", "trade_date", "factor_value"]],
    }


def _residual_discovery(
    *,
    batch: dict,
    bundle,
    repository: CampaignRepository,
    controls: pd.DataFrame,
    work_root: Path,
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    catalog = repository.identity(batch["feature_catalog_id"])
    matrix, family_features = _feature_matrix(
        repository, catalog, bundle, work_root / "feature-matrix"
    )
    matrix["trade_date"] = pd.to_datetime(matrix["trade_date"]).dt.strftime("%Y-%m-%d")
    contract = _snapshot_contract(
        SOURCE_DATASET_ID,
        [
            name
            for name in matrix.columns
            if name not in {"symbol", "trade_date", "raw_label", "model_label"}
        ],
        matrix["trade_date"].nunique(),
    )
    evaluator = CampaignEvaluator(
        bundle=bundle,
        matrix=matrix,
        contract=contract,
        work_root=work_root / "evaluation",
    )
    for _, values in evaluator.known_values:
        values["trade_date"] = pd.to_datetime(values["trade_date"]).dt.strftime(
            "%Y-%m-%d"
        )
    existing_rounds = {
        row["round_number"]: row
        for row in _rows(
            repository,
            "rolling_blind_discovery_batch",
            batch["rolling_blind_discovery_batch_id"],
        )
        if row.get("record_type") == "style_residual_agent_round"
    }
    candidates: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    failures: list[str] = []
    for round_number, (lane, family) in enumerate(_schedule(), 1):
        prior = existing_rounds.get(round_number)
        if prior is not None:
            counts["agent_calls"] += 1
            counts["proposals"] += prior["proposal_count"]
            counts["admissions"] += prior["admission_count"]
            counts["rejected_structures"] += prior["rejection_count"]
            counts["duplicate_structures"] += prior["duplicate_count"]
            counts["local_rescue_trials"] += prior["local_rescue_trial_count"]
            counts["qlib_calls"] += prior["qlib_calls"]
            root = repository.materialize(prior["artifact_id"])
            for item in prior["admitted_candidates"]:
                values = pd.read_parquet(root / item["factor_values_file"])
                candidates.append(
                    item | {"values": values, "round_artifact_id": prior["artifact_id"]}
                )
                evaluator.known_values.append((item["factor_instance_id"], values))
                fingerprints.add(item["structural_fingerprint"])
            continue
        allowed = _allowed_features(lane, family_features, set(matrix.columns))
        response, provider = call_structured_codex(
            prompt=_prompt(
                batch_id=batch["rolling_blind_discovery_batch_id"],
                call_index=round_number,
                lane=lane,
                family=family,
                allowed=allowed,
                fingerprints=sorted(fingerprints),
                failures=failures,
            ),
            schema=_agent_schema(),
            model="gpt-5.6-terra",
            timeout_seconds=300,
        )
        counts["agent_calls"] += 1
        proposals = response.get("proposals", [])
        admitted, rejected = [], []
        files: dict[str, Any] = {}
        qlib_before = evaluator.qlib.calls
        rescue_count = 0
        duplicate_count = 0
        for ordinal, raw in enumerate(proposals, 1):
            if counts["proposals"] >= batch["budgets"]["maximum_dsl_proposals"]:
                break
            counts["proposals"] += 1
            try:
                proposal = _normalize_and_admit(
                    raw,
                    round_number=round_number,
                    family=family,
                    lane_id=lane,
                    archetype="monotonic_rank_factor",
                    allowed_features=set(allowed),
                    known_fingerprints=fingerprints,
                    index=ordinal,
                )
                if len(proposal["default_parameters"]) > 1:
                    raise ValueError("STYLE_RESIDUAL_MAXIMUM_ONE_PARAMETER")
                if proposal["structural_fingerprint"] in fingerprints:
                    raise ValueError("DUPLICATE_STRUCTURE")
                if counts["admissions"] >= batch["budgets"]["maximum_dsl_admissions"]:
                    raise ValueError("ADMISSION_BUDGET_EXHAUSTED")
                selected = _evaluate_residual_candidate(
                    proposal=proposal,
                    parameters=proposal["default_parameters"],
                    evaluator=evaluator,
                    controls=controls,
                    work_root=work_root,
                    key=f"{round_number:02d}-{ordinal:02d}-default",
                )
                mode = "default_parameters"
                if not selected["gate"]["passed"] and proposal["default_parameters"]:
                    spaces = {
                        name: list(value["values"])
                        for name, value in proposal["parameter_search"][
                            "search_space"
                        ].items()
                    }
                    for parameters in local_factor_neighborhood(
                        proposal["default_parameters"], spaces
                    )[1:2]:
                        if (
                            counts["local_rescue_trials"]
                            >= batch["budgets"]["maximum_local_rescue_trials"]
                        ):
                            break
                        local = _evaluate_residual_candidate(
                            proposal=proposal,
                            parameters=parameters,
                            evaluator=evaluator,
                            controls=controls,
                            work_root=work_root,
                            key=f"{round_number:02d}-{ordinal:02d}-rescue",
                        )
                        counts["local_rescue_trials"] += 1
                        rescue_count += 1
                        if local["gate"]["passed"]:
                            selected = local
                            mode = "one_hop_local_rescue"
                            break
                relative = f"factor-values/{round_number:02d}-{ordinal:02d}.parquet"
                path = work_root / "round-files" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                selected["values"].to_parquet(path, index=False, compression="zstd")
                files[relative] = path
                item = {
                    "candidate_type": "style_residual_dsl",
                    "round_number": round_number,
                    "proposal_ordinal": ordinal,
                    "proposal": proposal,
                    "factor_instance_id": selected["factor_instance_id"],
                    "structural_fingerprint": proposal["structural_fingerprint"],
                    "parameters": selected["parameters"],
                    "orientation": selected["orientation"],
                    "optimization_mode": mode,
                    "primary_statistic": "daily_official_label_rankic",
                    "residualization_contract_id": batch[
                        "cross_sectional_style_residualization_id"
                    ],
                    "discovery_result": {
                        key: value for key, value in selected.items() if key != "values"
                    },
                    "discovery_gate": selected["gate"],
                    "factor_values_file": relative,
                }
                admitted.append(item)
                candidates.append(item | {"values": selected["values"]})
                evaluator.known_values.append(
                    (selected["factor_instance_id"], selected["values"])
                )
                fingerprints.add(proposal["structural_fingerprint"])
                counts["admissions"] += 1
            except Exception as exc:
                code = str(exc)[:180]
                rejected.append(
                    {"proposal_ordinal": ordinal, "failure_code": code}
                )
                failures.append(code)
                counts["rejected_structures"] += 1
                if "DUPLICATE" in code:
                    counts["duplicate_structures"] += 1
                    duplicate_count += 1
        identity = {
            "schema_version": "style-residual-agent-round-v1",
            "provider_id": "tushare-pro-v1",
            "parent_batch_id": batch["rolling_blind_discovery_batch_id"],
            "record_type": "style_residual_agent_round",
            "round_number": round_number,
            "lane": lane,
            "family": family,
            "provider_evidence": provider,
            "response": response,
            "proposal_count": len(proposals),
            "admission_count": len(admitted),
            "rejection_count": len(rejected),
            "duplicate_count": duplicate_count,
            "local_rescue_trial_count": rescue_count,
            "qlib_calls": evaluator.qlib.calls - qlib_before,
            "admitted_candidates": admitted,
            "rejections": rejected,
            "rolling_evaluation_reads": 0,
            "fresh_metric_reads": 0,
            "promotion_writes": 0,
        }
        round_id, receipt = _publish(
            repository,
            "rolling_blind_discovery_batch",
            identity,
            "style_residual_agent_round.json",
            lineage=(batch["rolling_blind_discovery_batch_id"],),
            files=files,
        )
        counts["qlib_calls"] += identity["qlib_calls"]
        counts["new_artifacts"] += int(not receipt["exact_existing"])
        counts["new_blobs"] += receipt["new_blob_count"]
        for item in candidates[-len(admitted) :] if admitted else []:
            item["round_artifact_id"] = round_id
    return candidates


def _ranking_discovery(
    *,
    batch: dict,
    bundle,
    repository: CampaignRepository,
    work_root: Path,
    counts: dict[str, int],
) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    feature, primitive = _catalog(repository)
    matrix = _model_matrix(
        bundle,
        repository,
        {"feature_catalog": feature, "primitive_catalog": primitive},
        work_root / "matrix",
    )
    matrix["trade_date"] = pd.to_datetime(matrix["trade_date"]).dt.strftime("%Y-%m-%d")
    ranking_spec = repository.identity(batch["ranking_model_spec_id"]) | {
        "ranking_model_spec_id": batch["ranking_model_spec_id"]
    }
    fixed_spec = {
        "model_spec_id": ranking_spec["ranking_model_spec_id"],
        "ranking_model_spec_id": ranking_spec["ranking_model_spec_id"],
    }
    bundle_specs = [
        row
        for row in _bundle_payloads(
            fixed_spec["model_spec_id"], feature, primitive
        )
        if row["bundle_name"] in ranking_spec["bundles"]
    ]
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    qlib.service.initialize()
    from qlib.config import C

    C.kernels = 1
    candidates = []
    for row in bundle_specs:
        row = row | {"bundle_id": row["bundle_id"]}
        result = train_ranking_fold(
            spec=ranking_spec,
            bundle_spec=row,
            matrix=matrix,
            train_start="2019-01-02",
            train_end="2020-12-31",
            test_start="2021-01-04",
            test_end="2021-12-31",
            qlib=qlib,
            work_root=work_root,
        )
        counts["model_hypotheses"] += 1
        counts["model_training_calls"] += result["model_training_calls"]
        counts["qlib_calls"] += 1
        concentration = result["qlib"].get("best_10_days_contribution")
        checks = {
            "coverage": (result["coverage"] or 0.0) >= 0.90,
            "pit": result["pit_violation_count"] == 0,
            "mean_rankic": (result["mean_rankic"] or -999.0) > 0,
            "top20_spread": (result["top20_universe_spread"] or -999.0) > 0,
            "turnover": (result["qlib"].get("turnover") or 999.0) <= 35,
            "concentration": (concentration or 999.0) <= 0.35,
        }
        candidate = {
            "candidate_type": "ranking_model",
            "candidate_key": f"ranking:{row['bundle_name']}",
            "ranking_model_spec_id": batch["ranking_model_spec_id"],
            "ranking_relevance_label_id": batch["ranking_relevance_label_id"],
            "bundle_spec": row,
            "feature_bundle": row["bundle_name"],
            "primary_statistic": "daily_official_label_rankic",
            "orientation": 1,
            "parameters": {},
            "discovery_result": {
                key: value for key, value in result.items() if key != "predictions"
            },
            "discovery_gate": {
                "checks": checks,
                "passed": all(checks.values()),
                "failed_gates": [
                    name for name, passed in checks.items() if not passed
                ],
            },
        }
        candidates.append(candidate)
    return candidates, matrix, ranking_spec, bundle_specs


def _lock(
    repository: CampaignRepository,
    batch: dict,
    residual: list[dict[str, Any]],
    ranking: list[dict[str, Any]],
    counts: dict[str, int],
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    eligible = [
        row for row in residual + ranking if row["discovery_gate"]["passed"]
    ]
    eligible.sort(
        key=lambda row: (
            -(
                row["discovery_result"].get("residual_metric", {}).get(
                    "mean_rankic"
                )
                if row["candidate_type"] == "style_residual_dsl"
                else row["discovery_result"].get("mean_rankic")
                or -999.0
            ),
            row.get("factor_instance_id") or row["candidate_key"],
        )
    )
    selected = eligible[
        : batch["budgets"]["maximum_rolling_evaluation_submissions"]
    ]
    members = []
    for order, row in enumerate(selected, 1):
        if row["candidate_type"] == "style_residual_dsl":
            key = f"residual:{row['factor_instance_id']}"
            member = {
                key: value
                for key, value in row.items()
                if key not in {"values", "discovery_result"}
            }
            member["factor_values_parent_artifact_id"] = row["round_artifact_id"]
            member["formula"] = row["proposal"]["template"]
            member["style_residualization_contract"] = row[
                "residualization_contract_id"
            ]
            member["ranking_label_contract"] = None
            member["feature_bundle"] = None
        else:
            key = row["candidate_key"]
            member = {
                key_name: value
                for key_name, value in row.items()
                if key_name != "discovery_result"
            }
            member["formula"] = None
            member["style_residualization_contract"] = None
            member["ranking_label_contract"] = row[
                "ranking_relevance_label_id"
            ]
        member.update(
            {
                "candidate_key": key,
                "discovery_order": order,
                "strategy_protocol": batch["strategy_protocol"],
                "configuration_frozen": True,
            }
        )
        members.append(member)
    lock = {
        "schema_version": "rolling-blind-candidate-batch-lock-v2",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch[
            "rolling_blind_discovery_batch_id"
        ],
        "window_set_id": batch["rolling_window_set_id"],
        "members": members,
        "candidate_count": len(members),
        "agent_calls_before_lock": counts["agent_calls"],
        "agent_closed": True,
        "planner_closed": True,
        "rolling_evaluation_reads_before_publish": 0,
        "configuration_frozen": True,
        "new_rounds_after_lock": 0,
        "fresh_metric_reads": 0,
        "promotion_writes": 0,
    }
    lock_id, receipt = _publish(
        repository,
        "rolling_blind_candidate_batch_lock_v2",
        lock,
        "candidate_batch_lock_v2.json",
        lineage=tuple(
            [
                batch["rolling_blind_discovery_batch_id"],
                batch["rolling_window_set_id"],
            ]
            + [
                row.get("factor_values_parent_artifact_id")
                for row in members
                if row.get("factor_values_parent_artifact_id")
            ]
        ),
    )
    return lock, lock_id, receipt


def _window_gate(
    rows: list[dict[str, Any]], candidate_type: str
) -> dict[str, Any]:
    def values(name: str) -> list[float]:
        return [
            float(row[name])
            for row in rows
            if row.get(name) is not None and math.isfinite(float(row[name]))
        ]

    primary = values("primary_metric")
    excess = values("csi300_excess")
    turnover = values("turnover")
    concentration = values("best_10_days_contribution")
    worst_count = max(1, int(math.ceil(len(primary) * 0.20)))
    checks = {
        "complete_windows": len(rows) == 18 and len(primary) == 18,
        "primary_positive_rate": len(primary) == 18
        and float(np.mean(np.asarray(primary) > 0)) >= 0.70,
        "primary_median": len(primary) == 18 and median(primary) > 0,
        "primary_worst20_mean": len(primary) == 18
        and float(np.mean(sorted(primary)[:worst_count])) > -0.01,
        "excess_positive_rate": len(excess) == 18
        and float(np.mean(np.asarray(excess) > 0)) >= 0.60,
        "excess_median": len(excess) == 18 and median(excess) > 0,
        "turnover_median": len(turnover) == 18 and median(turnover) <= 30,
        "concentration_median": len(concentration) == 18
        and median(concentration) <= 0.35,
        "configuration_unchanged": all(
            row.get("configuration_unchanged") for row in rows
        ),
    }
    extra: dict[str, Any] = {}
    if candidate_type == "style_residual_dsl":
        raw = values("raw_rankic")
        residual = values("residual_rankic")
        checks["residual_not_worse_than_raw"] = (
            len(raw) == 18
            and len(residual) == 18
            and median(residual) >= median(raw)
        )
        extra["raw_rankic_median"] = median(raw) if len(raw) == 18 else None
        extra["residual_rankic_median"] = (
            median(residual) if len(residual) == 18 else None
        )
    else:
        ndcg = values("ndcg_at_20")
        baseline = values("random_ndcg_at_20")
        checks["ndcg_above_random"] = (
            len(ndcg) == 18
            and len(baseline) == 18
            and median(ndcg) > median(baseline)
        )
        extra["ndcg_at_20_median"] = median(ndcg) if len(ndcg) == 18 else None
        extra["random_ndcg_at_20_median"] = (
            median(baseline) if len(baseline) == 18 else None
        )
    return extra | {
        "checks": checks,
        "passed": all(checks.values()),
        "failed_gates": [name for name, passed in checks.items() if not passed],
        "primary_positive_window_rate": (
            float(np.mean(np.asarray(primary) > 0)) if primary else None
        ),
        "primary_median": median(primary) if primary else None,
        "primary_worst20_mean": (
            float(np.mean(sorted(primary)[:worst_count])) if primary else None
        ),
        "csi300_excess_positive_window_rate": (
            float(np.mean(np.asarray(excess) > 0)) if excess else None
        ),
        "csi300_excess_median": median(excess) if excess else None,
        "turnover_median": median(turnover) if turnover else None,
        "concentration_median": (
            median(concentration) if concentration else None
        ),
    }


def _evaluate_windows(
    *,
    batch: dict,
    lock: dict,
    residual_candidates: list[dict[str, Any]],
    model_matrix: pd.DataFrame,
    ranking_spec: dict[str, Any],
    windows: dict,
    bundle,
    repository: CampaignRepository,
    work_root: Path,
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    residual_by_key = {
        f"residual:{row['factor_instance_id']}": row
        for row in residual_candidates
    }
    evaluator_matrix = model_matrix.copy()
    qlib = FormalQlibRunner(
        bundle.qlib_view, bundle.normalized, work_root / "ranking-qlib-cache"
    )
    qlib.service.initialize()
    from qlib.config import C

    C.kernels = 1
    results = []
    for member in lock["members"]:
        existing = [
            row
            for row in _rows(
                repository,
                (
                    "rolling_style_residual_result"
                    if member["candidate_type"] == "style_residual_dsl"
                    else "rolling_ranking_model_result"
                ),
                batch["rolling_blind_discovery_batch_id"],
            )
            if row.get("candidate_key") == member["candidate_key"]
        ]
        if existing:
            results.append(existing[0])
            counts["rolling_submissions"] += 1
            counts["rolling_window_evaluations"] += 18
            continue
        window_rows = []
        child_ids = []
        if member["candidate_type"] == "style_residual_dsl":
            values = residual_by_key[member["candidate_key"]]["values"].copy()
            raw_values = values.rename(
                columns={"factor_value": "residual_factor_value"}
            )
            # Raw score is preserved in the parent round only as diagnostic input.
            proposal = residual_by_key[member["candidate_key"]]["proposal"]
            raw_compiled, raw_factor = factor_values(
                parse_template(proposal["template"]),
                _snapshot_contract(
                    SOURCE_DATASET_ID,
                    [
                        name
                        for name in model_matrix.columns
                        if name
                        not in {
                            "symbol",
                            "trade_date",
                            "raw_label",
                            "model_label",
                            "sample_weight",
                            "next_tradable",
                            "next_locked_limit",
                        }
                    ],
                    model_matrix["trade_date"].nunique(),
                ),
                member["parameters"],
                model_matrix,
            )
            del raw_compiled
            for window in windows["windows"]:
                period = (window["start_date"], window["end_date"])
                residual_metric = _metric(values, model_matrix, period)
                raw_metric = _metric(raw_factor, model_matrix, period)
                signal = oriented_signal(
                    values,
                    1,
                    work_root
                    / "residual-signals"
                    / f"{member['candidate_key'].replace(':', '-')}-{window['window_id']}.parquet",
                )
                qlib_result = _clean_result(
                    qlib.run(
                        signal,
                        *period,
                        topk=20,
                        n_drop=5,
                        rebalance_days=10,
                        lifecycle_policy=LIFECYCLE_POLICY,
                    )
                )
                counts["qlib_calls"] += 1
                row = {
                    "window": window,
                    "primary_metric": residual_metric["mean_rankic"],
                    "raw_rankic": raw_metric["mean_rankic"],
                    "residual_rankic": residual_metric["mean_rankic"],
                    "neutralization_contribution": (
                        None
                        if raw_metric["mean_rankic"] is None
                        or residual_metric["mean_rankic"] is None
                        else residual_metric["mean_rankic"]
                        - raw_metric["mean_rankic"]
                    ),
                    "csi300_excess": qlib_result.get("net_excess_csi300"),
                    "turnover": qlib_result.get("turnover"),
                    "transaction_cost": qlib_result.get("transaction_cost"),
                    "max_drawdown": qlib_result.get("max_drawdown"),
                    "best_10_days_contribution": qlib_result.get(
                        "best_10_days_contribution"
                    ),
                    "configuration_unchanged": True,
                }
                identity = {
                    "schema_version": "rolling-style-residual-window-result-v1",
                    "provider_id": "tushare-pro-v1",
                    "rolling_blind_discovery_batch_id": batch[
                        "rolling_blind_discovery_batch_id"
                    ],
                    "candidate_batch_lock_id": lock[
                        "rolling_blind_candidate_batch_lock_v2_id"
                    ],
                    "candidate_key": member["candidate_key"],
                    "record_type": "window_result",
                    "window_result": row,
                    "agent_visible": False,
                    "planner_visible": False,
                    "failure_memory_visible": False,
                    "promotion_writes": 0,
                }
                child_id, receipt = _publish(
                    repository,
                    "rolling_style_residual_result",
                    identity,
                    "window_result.json",
                    lineage=(
                        lock["rolling_blind_candidate_batch_lock_v2_id"],
                        member["factor_values_parent_artifact_id"],
                    ),
                )
                counts["new_artifacts"] += int(not receipt["exact_existing"])
                counts["new_blobs"] += receipt["new_blob_count"]
                counts["rolling_window_evaluations"] += 1
                child_ids.append(child_id)
                window_rows.append(row)
            kind = "rolling_style_residual_result"
        else:
            bundle_spec = member["bundle_spec"]
            all_dates = sorted(model_matrix["trade_date"].unique())
            for window in windows["windows"]:
                before = [
                    date for date in all_dates if date < window["start_date"]
                ]
                if len(before) <= 10:
                    raise ValueError("ranking pre-window training history is insufficient")
                train_end = before[-11]
                result = train_ranking_fold(
                    spec=ranking_spec,
                    bundle_spec=bundle_spec,
                    matrix=evaluator_matrix,
                    train_start="2019-01-02",
                    train_end=train_end,
                    test_start=window["start_date"],
                    test_end=window["end_date"],
                    qlib=qlib,
                    work_root=work_root / "ranking",
                )
                counts["model_training_calls"] += 3
                counts["qlib_calls"] += 1
                row = {
                    "window": window,
                    "train_range": result["train_range"],
                    "primary_metric": result["mean_rankic"],
                    "ndcg_at_20": result["ndcg_at_20"],
                    "random_ndcg_at_20": result["random_ndcg_at_20"],
                    "top20_universe_spread": result[
                        "top20_universe_spread"
                    ],
                    "csi300_excess": result["qlib"].get("net_excess_csi300"),
                    "turnover": result["qlib"].get("turnover"),
                    "transaction_cost": result["qlib"].get("transaction_cost"),
                    "max_drawdown": result["qlib"].get("max_drawdown"),
                    "best_10_days_contribution": result["qlib"].get(
                        "best_10_days_contribution"
                    ),
                    "selected_features": result["selected_features"],
                    "seed_model_ids": result["seed_model_ids"],
                    "configuration_unchanged": True,
                }
                identity = {
                    "schema_version": "rolling-ranking-model-window-result-v1",
                    "provider_id": "tushare-pro-v1",
                    "rolling_blind_discovery_batch_id": batch[
                        "rolling_blind_discovery_batch_id"
                    ],
                    "candidate_batch_lock_id": lock[
                        "rolling_blind_candidate_batch_lock_v2_id"
                    ],
                    "candidate_key": member["candidate_key"],
                    "record_type": "window_result",
                    "window_result": row,
                    "agent_visible": False,
                    "planner_visible": False,
                    "failure_memory_visible": False,
                    "promotion_writes": 0,
                }
                child_id, receipt = _publish(
                    repository,
                    "rolling_ranking_model_result",
                    identity,
                    "window_result.json",
                    lineage=(
                        lock["rolling_blind_candidate_batch_lock_v2_id"],
                        batch["ranking_model_spec_id"],
                    ),
                )
                counts["new_artifacts"] += int(not receipt["exact_existing"])
                counts["new_blobs"] += receipt["new_blob_count"]
                counts["rolling_window_evaluations"] += 1
                child_ids.append(child_id)
                window_rows.append(row)
            kind = "rolling_ranking_model_result"
        gate = _window_gate(window_rows, member["candidate_type"])
        test = _mean_test(
            [row["primary_metric"] for row in window_rows if row["primary_metric"] is not None]
        )
        aggregate = {
            "schema_version": (
                "rolling-style-residual-result-v1"
                if member["candidate_type"] == "style_residual_dsl"
                else "rolling-ranking-model-result-v1"
            ),
            "provider_id": "tushare-pro-v1",
            "rolling_blind_discovery_batch_id": batch[
                "rolling_blind_discovery_batch_id"
            ],
            "candidate_batch_lock_id": lock[
                "rolling_blind_candidate_batch_lock_v2_id"
            ],
            "candidate_key": member["candidate_key"],
            "candidate_type": member["candidate_type"],
            "record_type": "candidate_aggregate",
            "primary_statistic": "daily_official_label_rankic",
            "window_result_ids": child_ids,
            "windows": window_rows,
            "gate": gate,
            "statistical_test": test,
            "all_windows_evaluated": len(window_rows) == 18,
            "early_stopped": False,
            "agent_visible": False,
            "planner_visible": False,
            "failure_memory_visible": False,
            "promotion_writes": 0,
        }
        aggregate_id, receipt = _publish(
            repository,
            kind,
            aggregate,
            "candidate_aggregate.json",
            lineage=(
                lock["rolling_blind_candidate_batch_lock_v2_id"],
                *child_ids,
            ),
        )
        counts["new_artifacts"] += int(not receipt["exact_existing"])
        counts["new_blobs"] += receipt["new_blob_count"]
        counts["rolling_submissions"] += 1
        results.append(aggregate | {"artifact_id": aggregate_id})
    return results


def _finalize(
    *,
    batch: dict,
    lock: dict,
    results: list[dict[str, Any]],
    repository: CampaignRepository,
    counts: dict[str, int],
    fresh_before: dict[str, list[str]],
) -> dict[str, Any]:
    tested = benjamini_hochberg(
        [
            {
                "candidate_result_id": row["artifact_id"],
                "candidate_key": row["candidate_key"],
                "raw_p_value": row["statistical_test"]["raw_p_value"],
            }
            for row in results
        ],
        q=0.10,
    )
    multiple = {
        "schema_version": "rolling-evaluation-multiple-testing-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch[
            "rolling_blind_discovery_batch_id"
        ],
        "candidate_batch_lock_id": lock[
            "rolling_blind_candidate_batch_lock_v2_id"
        ],
        "method": "Benjamini-Hochberg",
        "global_across_lanes": True,
        "fdr_q": 0.10,
        "results": tested,
        "promotion_writes": 0,
    }
    multiple_id, receipt = _publish(
        repository,
        "rolling_evaluation_multiple_testing",
        multiple,
        "multiple_testing.json",
        lineage=tuple(row["artifact_id"] for row in results),
    )
    counts["new_artifacts"] += int(not receipt["exact_existing"])
    counts["new_blobs"] += receipt["new_blob_count"]
    adjusted = {row["candidate_result_id"]: row for row in tested}
    survivors, fresh_locks = [], []
    for row in results:
        test = adjusted[row["artifact_id"]]
        if row["gate"]["passed"] and test["adjusted_q_value"] <= 0.10:
            survivor = {
                "schema_version": "rolling-evaluation-alpha-survivor-v1",
                "provider_id": "tushare-pro-v1",
                "rolling_blind_discovery_batch_id": batch[
                    "rolling_blind_discovery_batch_id"
                ],
                "candidate_batch_lock_id": lock[
                    "rolling_blind_candidate_batch_lock_v2_id"
                ],
                "candidate_result_id": row["artifact_id"],
                "multiple_testing_id": multiple_id,
                "candidate_key": row["candidate_key"],
                "candidate_type": row["candidate_type"],
                "status": "research_registered",
                "historical_rolling_evaluation_passed": True,
                "real_fresh_validated": False,
                "production_eligible": False,
                "registry_state": "research_registered",
                "adjusted_q_value": test["adjusted_q_value"],
                "promotion_writes": 0,
            }
            survivor_id, survivor_receipt = _publish(
                repository,
                "rolling_evaluation_alpha_survivor",
                survivor,
                "survivor.json",
                lineage=(row["artifact_id"], multiple_id),
            )
            survivors.append(
                survivor | {"rolling_evaluation_alpha_survivor_id": survivor_id}
            )
            counts["survivor_writes"] += int(
                not survivor_receipt["exact_existing"]
            )
            counts["registry_writes"] += int(
                not survivor_receipt["exact_existing"]
            )
            counts["new_artifacts"] += int(
                not survivor_receipt["exact_existing"]
            )
            counts["new_blobs"] += survivor_receipt["new_blob_count"]
            fresh = {
                "schema_version": "project-candidate-fresh-lock-v1",
                "provider_id": "tushare-pro-v1",
                "candidate_id": survivor_id,
                "candidate_type": "rolling_evaluation_alpha_survivor",
                "formula_parameters_orientation_archetype_frozen": True,
                "latest_market_data_date_at_lock": "2026-06-24",
                "fresh_start_date": "2026-06-25",
                "no_backfill": True,
                "minimum_fresh_trading_days": 60,
                "status": "fresh_locked",
                "real_fresh_validated": False,
                "promotion_writes": 0,
            }
            fresh_id, fresh_receipt = _publish(
                repository,
                "project_candidate_fresh_lock",
                fresh,
                "fresh_lock.json",
                lineage=(survivor_id,),
            )
            fresh_locks.append(fresh_id)
            counts["fresh_lock_writes"] += int(
                not fresh_receipt["exact_existing"]
            )
            counts["new_artifacts"] += int(not fresh_receipt["exact_existing"])
            counts["new_blobs"] += fresh_receipt["new_blob_count"]
    prior_ledgers = _rows(repository, "rolling_blind_submission_ledger")
    cumulative_before = max(
        (row.get("cumulative_blind_submissions", 0) for row in prior_ledgers),
        default=2,
    )
    ledger = {
        "schema_version": "rolling-blind-submission-ledger-v2",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch[
            "rolling_blind_discovery_batch_id"
        ],
        "candidate_batch_lock_id": lock[
            "rolling_blind_candidate_batch_lock_v2_id"
        ],
        "batch_blind_submissions": len(results),
        "cumulative_blind_submissions_before": cumulative_before,
        "cumulative_blind_submissions": cumulative_before + len(results),
        "submitted_structure_keys": [row["candidate_key"] for row in results],
        "metrics_included": False,
        "failure_reasons_included": False,
        "promotion_writes": 0,
    }
    ledger_id, ledger_receipt = _publish(
        repository,
        "rolling_blind_submission_ledger",
        ledger,
        "submission_ledger_v2.json",
        lineage=(lock["rolling_blind_candidate_batch_lock_v2_id"],),
    )
    counts["new_artifacts"] += int(not ledger_receipt["exact_existing"])
    counts["new_blobs"] += ledger_receipt["new_blob_count"]
    historical_calls = sum(
        int(row.get("agent_calls", 0))
        for row in _rows(repository, "rolling_blind_search_exposure")
        if row.get("rolling_blind_discovery_batch_id") != batch[
            "rolling_blind_discovery_batch_id"
        ]
    )
    exposure = {
        "schema_version": "rolling-blind-search-exposure-v2",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch[
            "rolling_blind_discovery_batch_id"
        ],
        "historical_cumulative_agent_calls": historical_calls,
        "batch_agent_calls": counts["agent_calls"],
        "project_cumulative_agent_calls": historical_calls + counts["agent_calls"],
        "proposals": counts["proposals"],
        "admissions": counts["admissions"],
        "local_rescue_trials": counts["local_rescue_trials"],
        "model_hypotheses": counts["model_hypotheses"],
        "rolling_submissions": len(results),
        "project_cumulative_rolling_submissions": ledger[
            "cumulative_blind_submissions"
        ],
        "r3_001_submission_count": 2,
        "r3_001_metrics_included": False,
        "promotion_writes": 0,
    }
    exposure_id, exposure_receipt = _publish(
        repository,
        "rolling_blind_search_exposure",
        exposure,
        "search_exposure_v2.json",
        lineage=(ledger_id, lock["rolling_blind_candidate_batch_lock_v2_id"]),
    )
    counts["new_artifacts"] += int(not exposure_receipt["exact_existing"])
    counts["new_blobs"] += exposure_receipt["new_blob_count"]
    fresh_after = {
        kind: sorted(
            row.artifact_id for row in repository.store.list_by_kind(kind)
        )
        for kind in fresh_before
    }
    if fresh_after != fresh_before:
        raise ValueError("existing Fresh Cohort identities changed")
    status = (
        "completed_with_survivors"
        if survivors
        else "completed_no_batch_lock_candidate"
        if not lock["members"]
        else "completed_no_survivor"
    )
    report = {
        "schema_version": "cross-sectional-alpha-research-report-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch[
            "rolling_blind_discovery_batch_id"
        ],
        "status": status,
        "mainline_blocked": False,
        "evidence_semantics": "historical_rolling_evaluation",
        "window_set_id": batch["rolling_window_set_id"],
        "candidate_batch_lock_id": lock[
            "rolling_blind_candidate_batch_lock_v2_id"
        ],
        "candidate_result_ids": [row["artifact_id"] for row in results],
        "multiple_testing_id": multiple_id,
        "search_exposure_id": exposure_id,
        "submission_ledger_id": ledger_id,
        "survivor_ids": [
            row["rolling_evaluation_alpha_survivor_id"] for row in survivors
        ],
        "fresh_lock_ids": fresh_locks,
        "runtime_counts": counts,
        "existing_fresh_cohort_id": FRESH_COHORT_ID,
        "existing_fresh_objects_unchanged": True,
        "real_fresh_validation": False,
        "rolling_feedback_to_same_batch": False,
        "automatic_batch_003_created": False,
        "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0,
        "promotion_writes": 0,
    }
    report_id, report_receipt = _publish(
        repository,
        "rolling_blind_research_report",
        report,
        "cross_sectional_research_report.json",
        lineage=(
            batch["rolling_blind_discovery_batch_id"],
            lock["rolling_blind_candidate_batch_lock_v2_id"],
            multiple_id,
            exposure_id,
            ledger_id,
            *report["candidate_result_ids"],
            *report["survivor_ids"],
            *fresh_locks,
        ),
    )
    counts["new_artifacts"] += int(not report_receipt["exact_existing"])
    counts["new_blobs"] += report_receipt["new_blob_count"]
    return report | {
        "rolling_blind_research_report_id": report_id,
        "multiple_testing": multiple,
        "survivors": survivors,
        "store_integrity": repository.integrity(),
    }


def run_batch(
    *,
    supervisor_id: str,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    bundle, repository = _repository(repository_root, work_root, store_root)
    frozen = create_batch(
        supervisor_id=supervisor_id,
        repository_root=repository_root,
        work_root=work_root,
        store_root=store_root,
    )
    batch_id = frozen["rolling_blind_discovery_batch_id"]
    reports = [
        row
        for row in _rows(repository, "rolling_blind_research_report", batch_id)
        if row.get("schema_version")
        == "cross-sectional-alpha-research-report-v1"
    ]
    if reports:
        return replay_batch(
            rolling_blind_discovery_batch_id=batch_id,
            repository_root=repository_root,
            work_root=Path(work_root) / "terminal-replay",
            store_root=store_root,
        ) | {
            "supervisor_id": supervisor_id,
            "research_type": "cross_sectional_alpha_discovery",
            "exact_existing": True,
        }
    batch = repository.identity(batch_id) | {
        "rolling_blind_discovery_batch_id": batch_id
    }
    windows = repository.identity(batch["rolling_window_set_id"]) | {
        "rolling_blind_window_set_id": batch["rolling_window_set_id"]
    }
    controls, _ = build_style_controls(bundle)
    fresh_before = _fresh_identity_snapshot(repository)
    counts = empty_counts()
    counts["new_artifacts"] = frozen["new_artifacts"]
    counts["new_blobs"] = frozen["new_blobs"]
    residual = _residual_discovery(
        batch=batch,
        bundle=bundle,
        repository=repository,
        controls=controls,
        work_root=Path(work_root) / "style-residual-lane",
        counts=counts,
    )
    ranking, model_matrix, ranking_spec, _ = _ranking_discovery(
        batch=batch,
        bundle=bundle,
        repository=repository,
        work_root=Path(work_root) / "ranking-lane",
        counts=counts,
    )
    if counts["agent_calls"] != 18 or counts["model_hypotheses"] != 2:
        raise ValueError("Batch 002 frozen research coverage was not completed")
    lock, lock_id, lock_receipt = _lock(
        repository, batch, residual, ranking, counts
    )
    lock = lock | {"rolling_blind_candidate_batch_lock_v2_id": lock_id}
    counts["new_artifacts"] += int(not lock_receipt["exact_existing"])
    counts["new_blobs"] += lock_receipt["new_blob_count"]
    results = _evaluate_windows(
        batch=batch,
        lock=lock,
        residual_candidates=residual,
        model_matrix=model_matrix,
        ranking_spec=ranking_spec,
        windows=windows,
        bundle=bundle,
        repository=repository,
        work_root=Path(work_root) / "rolling-evaluation",
        counts=counts,
    )
    if counts["qlib_calls"] > batch["budgets"]["maximum_qlib_calls"]:
        raise ValueError("Batch 002 Qlib budget exceeded")
    final = _finalize(
        batch=batch,
        lock=lock,
        results=results,
        repository=repository,
        counts=counts,
        fresh_before=fresh_before,
    )
    return final | {
        "supervisor_id": supervisor_id,
        "research_type": "cross_sectional_alpha_discovery",
        "candidate_batch_lock_id": lock_id,
        "exact_existing": False,
    }


def validate_batch(
    *,
    rolling_blind_discovery_batch_id: str,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    _, repository = _repository(repository_root, work_root, store_root)
    batch = repository.identity(rolling_blind_discovery_batch_id)
    if batch.get("schema_version") != "cross-sectional-alpha-discovery-batch-v1":
        raise ValueError("Cross-sectional Batch is invalid")
    reports = [
        row
        for row in _rows(
            repository,
            "rolling_blind_research_report",
            rolling_blind_discovery_batch_id,
        )
        if row.get("schema_version")
        == "cross-sectional-alpha-research-report-v1"
    ]
    if len(reports) != 1 or reports[0]["status"] not in TERMINAL_STATUSES:
        raise ValueError("Cross-sectional terminal Report is absent or ambiguous")
    report = reports[0]
    result_rows = [
        repository.identity(artifact_id) | {"artifact_id": artifact_id}
        for artifact_id in report["candidate_result_ids"]
    ]
    window_result_ids = [
        artifact_id
        for row in result_rows
        for artifact_id in row.get("window_result_ids", [])
    ]
    recovered = [
        batch["cross_sectional_style_residualization_id"],
        batch["ranking_relevance_label_id"],
        batch["ranking_model_spec_id"],
        report["window_set_id"],
        report["candidate_batch_lock_id"],
        *report["candidate_result_ids"],
        *window_result_ids,
        report["multiple_testing_id"],
        report["search_exposure_id"],
        report["submission_ledger_id"],
        *report["survivor_ids"],
        *report["fresh_lock_ids"],
        report["artifact_id"],
    ]
    for artifact_id in recovered:
        repository.materialize(artifact_id)
    integrity = repository.integrity()
    if integrity != {"status": "healthy", "missing": 0, "unreferenced": 0}:
        raise ValueError("Artifact Store integrity is not healthy")
    return {
        "status": "valid",
        "rolling_blind_discovery_batch_id": rolling_blind_discovery_batch_id,
        "rolling_blind_research_report_id": report["artifact_id"],
        "terminal_status": report["status"],
        "recovered_artifact_count": len(recovered),
        "evidence_gaps": [],
        "store_integrity": integrity,
    }


def replay_batch(
    *,
    rolling_blind_discovery_batch_id: str,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    result = validate_batch(
        rolling_blind_discovery_batch_id=rolling_blind_discovery_batch_id,
        repository_root=repository_root,
        work_root=work_root,
        store_root=store_root,
    )
    return result | {
        "status": "exact_replay",
        "runtime_counts": empty_counts(),
        "agent_calls": 0,
        "model_training_calls": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "candidate_writes": 0,
        "fresh_lock_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
    }


def inspect_artifact(
    *,
    artifact_id: str,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    _, repository = _repository(repository_root, work_root, store_root)
    return repository.identity(artifact_id) | {"artifact_id": artifact_id}
