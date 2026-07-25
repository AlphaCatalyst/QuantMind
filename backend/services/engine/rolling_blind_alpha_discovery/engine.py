from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.archetype_alpha_program.evaluation import (
    choose_orientation,
    evaluate_locked,
    tail_observations,
)
from backend.services.engine.archetype_alpha_program.models import ARCHETYPES, LANES
from backend.services.engine.archetype_alpha_program.orchestrator import (
    _allowed_features,
    _feature_matrix,
    _normalize_and_admit,
    _prompt,
)
from backend.services.engine.archetype_alpha_program.schemas import alpha_agent_schema
from backend.services.engine.autonomous_factor_campaign.evaluation import (
    CampaignEvaluator,
    signal_similarity,
)
from backend.services.engine.autonomous_factor_campaign.evaluation_v2 import (
    _year_result,
)
from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg,
)
from backend.services.engine.autonomous_technical_feature_factory.agent import (
    call_structured_codex,
)
from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import (
    OPERATORS,
    SOURCE_DATASET_ID,
)
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.fixed_configuration_model_program.engine import (
    _bundle_payloads,
    _catalog,
    _model_matrix,
    _train_fold,
    select_bundle_c,
)
from backend.services.engine.momentum_factor_iteration.engine import _snapshot_contract
from backend.services.engine.optimization_governance.engine import (
    local_factor_neighborhood,
)
from backend.services.engine.tushare_agent_experiment.evaluation import (
    factor_values,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .models import RollingBlindDiscoveryBatchSpecV1, empty_runtime_counts


MODEL_SPEC_ID = "fcms1_27c7102a662731b28d5142166dacc398e82ca4c701870c6657bfd83cdcd7ad94"
WALK_FORWARD_SPEC_ID = "pwfs1_6a226e117f7eca56f380f1e7445bcb462dc7b7ffeedfe5d0e076b6d4a9c0a7d9"
FRESH_COHORT_ID = "mfcc1_faab1ee6f07fe1ce46bb13ab8403e104433c5781058d3e8c6720e6ffd7bde6dc"
DISCOVERY = {"discovery_2019_2021": ("2019-01-02", "2021-12-31")}
TERMINAL_STATUSES = {
    "completed_no_blind_submission",
    "completed_no_blind_survivor",
    "completed_with_blind_survivors",
}


def _repository(
    repository_root: Path, work_root: Path, store_root: Path | None
) -> tuple[Any, CampaignRepository]:
    return _runtime(Path(repository_root), Path(work_root), store_root)


def _rows(repository: CampaignRepository, kind: str, batch_id: str | None = None) -> list[dict]:
    result = []
    for descriptor in repository.store.list_by_kind(kind):
        identity = repository.identity(descriptor.artifact_id)
        belongs_to_batch = (
            identity.get("rolling_blind_discovery_batch_id") == batch_id
            or identity.get("parent_batch_id") == batch_id
            or batch_id in descriptor.lineage
        )
        if batch_id is None or belongs_to_batch:
            result.append(identity | {"artifact_id": descriptor.artifact_id})
    return result


def _publish(
    repository: CampaignRepository,
    kind: str,
    identity: dict,
    filename: str,
    *,
    lineage: tuple[str, ...] = (),
    files: dict[str, Any] | None = None,
) -> tuple[str, dict]:
    payload = {filename: identity}
    payload.update(files or {})
    receipt = repository.publish(kind, identity, payload, lineage=lineage)
    return receipt["artifact_id"], receipt


def _trade_calendar(bundle, start: str, end: str) -> list[str]:
    path = Path(bundle.qlib_view) / "calendars" / "day.txt"
    dates = sorted({
        line.strip()[:10]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and start <= line.strip()[:10] <= end
    })
    if not dates or dates[0] != start:
        raise ValueError("formal A-share calendar does not begin at the frozen Blind Pool start")
    return dates


def _window_set(bundle, spec: RollingBlindDiscoveryBatchSpecV1) -> dict[str, Any]:
    dates = _trade_calendar(bundle, *spec.blind_pool)
    size = spec.window_trading_days
    complete = len(dates) // size
    windows = []
    for index in range(complete):
        selected = dates[index * size:(index + 1) * size]
        windows.append({
            "window_id": f"rbw_{index + 1:02d}",
            "sequence": index + 1,
            "start_date": selected[0],
            "end_date": selected[-1],
            "trading_day_count": len(selected),
        })
    tail = dates[complete * size:]
    stable = {
        "schema_version": "rolling-blind-window-set-v1",
        "provider_id": "tushare-pro-v1",
        "evidence_semantics": "historical_rolling_blind",
        "requested_pool_start": spec.blind_pool[0],
        "requested_pool_end": spec.blind_pool[1],
        "available_calendar_end": dates[-1],
        "window_trading_days": size,
        "windows": windows,
        "complete_window_count": len(windows),
        "tail_excluded": True,
        "tail_trading_day_count": len(tail),
        "tail_start": tail[0] if tail else None,
        "tail_end": tail[-1] if tail else None,
        "boundaries_performance_selected": False,
        "frozen_before_agent_calls": True,
        "agent_calls_before_freeze": 0,
        "promotion_writes": 0,
    }
    if len(windows) < 12 or any(row["trading_day_count"] != 60 for row in windows):
        raise ValueError("Rolling Blind Window Set has insufficient complete windows")
    for left, right in zip(windows, windows[1:]):
        if left["end_date"] >= right["start_date"]:
            raise ValueError("Rolling Blind windows overlap")
    return stable


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
    spec = RollingBlindDiscoveryBatchSpecV1()
    windows = _window_set(bundle, spec)
    window_id, window_receipt = _publish(
        repository,
        "rolling_blind_window_set",
        windows,
        "rolling_blind_window_set.json",
        lineage=(SOURCE_DATASET_ID,),
    )
    batch = spec.payload(supervisor_id=supervisor_id, window_set_id=window_id)
    batch_id, batch_receipt = _publish(
        repository,
        "rolling_blind_discovery_batch",
        batch,
        "rolling_blind_discovery_batch.json",
        lineage=(supervisor_id, window_id, spec.feature_catalog_id, spec.model_spec_id),
    )
    return batch | {
        "rolling_blind_discovery_batch_id": batch_id,
        "status": "batch_frozen",
        "complete_window_count": windows["complete_window_count"],
        "new_artifacts": int(not window_receipt["exact_existing"]) + int(
            not batch_receipt["exact_existing"]
        ),
        "new_blobs": window_receipt["new_blob_count"] + batch_receipt["new_blob_count"],
    }


def _discovery_gate(result: dict, maximum_correlation: float) -> dict[str, Any]:
    row = result["annual"][0]
    metrics, qlib = row["metrics"], row["qlib"]
    checks = {
        "coverage": (metrics.get("factor_finite_coverage") or 0.0) >= 0.90,
        "pit": row["pit_violation_count"] == 0,
        "infinity": row["infinity_count"] == 0,
        "mean_rankic": (metrics.get("mean_rank_ic") or -999.0) > 0,
        "turnover": (qlib.get("turnover") or 999.0) <= 35,
        "concentration": (qlib.get("best_10_days_contribution") or 999.0) <= 0.35,
        "independence": maximum_correlation < 0.85,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "failed_gates": [name for name, passed in checks.items() if not passed],
        "mean_rankic": metrics.get("mean_rank_ic"),
        "rankic_positive_rate": metrics.get("rank_ic_positive_rate"),
        "net_return": qlib.get("net_return"),
        "csi300_excess": qlib.get("net_excess_csi300"),
        "turnover": qlib.get("turnover"),
        "best_10_days_contribution": qlib.get("best_10_days_contribution"),
        "maximum_existing_spearman": maximum_correlation,
    }


def _dsl_round_schedule() -> list[tuple[str, str, str]]:
    rows = []
    for lane, config in LANES.items():
        for family in config["families"]:
            for archetype in ARCHETYPES:
                rows.append((lane, family, archetype))
    return rows[:18]


def _dsl_discovery(
    *,
    batch: dict,
    bundle,
    repository: CampaignRepository,
    work_root: Path,
    counts: dict,
) -> list[dict]:
    catalog = repository.identity(batch["feature_catalog_id"])
    matrix, family_features = _feature_matrix(
        repository, catalog, bundle, work_root / "feature-matrix"
    )
    matrix["trade_date"] = pd.to_datetime(matrix["trade_date"]).dt.strftime("%Y-%m-%d")
    normalized = bundle.normalized.copy()
    normalized["trade_date"] = pd.to_datetime(
        normalized["trade_date"]
    ).dt.strftime("%Y-%m-%d")
    contract = _snapshot_contract(
        SOURCE_DATASET_ID,
        [
            name for name in matrix.columns
            if name not in {"symbol", "trade_date", "raw_label", "model_label"}
        ],
        matrix["trade_date"].nunique(),
    )
    evaluator = CampaignEvaluator(
        bundle=bundle,
        matrix=matrix,
        contract=contract,
        work_root=work_root / "dsl-evaluation",
    )
    # CampaignEvaluator loads the legacy comparison factors with their stored
    # timestamp dtype.  The generated matrix uses the canonical YYYY-MM-DD key
    # required by the rolling protocol, so align those read-only comparison
    # frames before the novelty merge.
    for _, comparison_values in evaluator.known_values:
        comparison_values["trade_date"] = pd.to_datetime(
            comparison_values["trade_date"]
        ).dt.strftime("%Y-%m-%d")
    known_fingerprints: set[str] = set()
    failure_codes: list[str] = []
    candidates: list[dict] = []
    existing_rounds = {
        row["round_number"]: row
        for row in _rows(
            repository, "rolling_blind_discovery_batch",
            batch["rolling_blind_discovery_batch_id"],
        )
        if row.get("record_type") == "dsl_agent_round"
    }
    for round_number, (lane, family, archetype) in enumerate(_dsl_round_schedule(), 1):
        counts["rounds"] += 1
        prior = existing_rounds.get(round_number)
        if prior is not None:
            counts["agent_calls"] += 1
            counts["proposals"] += prior["proposal_count"]
            counts["admissions"] += prior["admission_count"]
            counts["rejected_structures"] += prior["rejection_count"]
            counts["duplicate_structures"] += prior["duplicate_count"]
            counts["local_rescue_trials"] += prior["local_rescue_trial_count"]
            counts["qlib_calls"] += prior["qlib_calls"]
            for item in prior["admitted_candidates"]:
                root = repository.materialize(prior["artifact_id"])
                values = pd.read_parquet(root / item["factor_values_file"])
                candidates.append(
                    item | {"values": values, "round_artifact_id": prior["artifact_id"]}
                )
                evaluator.known_values.append((item["factor_instance_id"], values))
                known_fingerprints.add(item["structural_fingerprint"])
            continue
        allowed = _allowed_features(lane, family_features, set(matrix.columns))
        prompt = _prompt(
            spec={
                "program_spec_id": batch["rolling_blind_discovery_batch_id"],
                "strategy_protocol": batch["strategy_protocol"],
            },
            lane_id=lane,
            family=family,
            archetype=archetype,
            call_index=round_number,
            allowed_features=allowed,
            known_fingerprints=sorted(known_fingerprints),
            failure_summary=failure_codes,
        )
        response, provider = call_structured_codex(
            prompt=prompt,
            schema=alpha_agent_schema(),
            model="gpt-5.6-terra",
            timeout_seconds=300,
        )
        counts["agent_calls"] += 1
        raw_identity = {
            "schema_version": "rolling-blind-agent-response-v1",
            "provider_id": "tushare-pro-v1",
            "parent_batch_id": batch["rolling_blind_discovery_batch_id"],
            "record_type": "agent_response",
            "round_number": round_number,
            "lane": lane,
            "family": family,
            "archetype": archetype,
            "provider_evidence": provider,
            "response": response,
            "discovery_metrics_in_prompt": False,
            "blind_window_reads": 0,
            "fresh_evidence_reads": 0,
            "promotion_writes": 0,
        }
        response_id, response_receipt = _publish(
            repository,
            "rolling_blind_discovery_batch",
            raw_identity,
            "agent_response.json",
            lineage=(batch["rolling_blind_discovery_batch_id"],),
        )
        counts["new_artifacts"] += int(not response_receipt["exact_existing"])
        counts["new_blobs"] += response_receipt["new_blob_count"]
        admitted, rejections, duplicates = [], [], 0
        round_files: dict[str, Any] = {}
        qlib_before = evaluator.qlib.calls
        rescue_count = 0
        for index, raw in enumerate(response.get("proposals", []), 1):
            if counts["proposals"] >= batch["budgets"]["maximum_proposals"]:
                break
            counts["proposals"] += 1
            try:
                proposal = _normalize_and_admit(
                    raw,
                    round_number=round_number,
                    family=family,
                    lane_id=lane,
                    archetype=archetype,
                    allowed_features=set(allowed),
                    known_fingerprints=known_fingerprints,
                    index=index,
                )
                if proposal["structural_fingerprint"] in known_fingerprints:
                    raise ValueError("DUPLICATE_STRUCTURE")
                if counts["admissions"] >= batch["budgets"]["maximum_admissions"]:
                    raise ValueError("ADMISSION_BUDGET_EXHAUSTED")
                defaults = proposal["default_parameters"]
                orientation = choose_orientation(
                    evaluator=evaluator,
                    normalized=normalized,
                    proposal=proposal,
                    parameters=defaults,
                    start=DISCOVERY["discovery_2019_2021"][0],
                    end=DISCOVERY["discovery_2019_2021"][1],
                )
                result = evaluate_locked(
                    evaluator=evaluator,
                    normalized=normalized,
                    proposal=proposal,
                    parameters=defaults,
                    orientation=orientation,
                    periods=DISCOVERY,
                    phase="adaptive",
                )
                maximum = result["summary"]["maximum_existing_factor_correlation"]
                gate = _discovery_gate(result, maximum)
                selected_parameters = defaults
                optimization_mode = "default_parameters"
                if not gate["passed"] and defaults:
                    spaces = {
                        name: list(value["values"])
                        for name, value in proposal["parameter_search"]["search_space"].items()
                    }
                    neighbors = local_factor_neighborhood(defaults, spaces)[1:2]
                    for parameters in neighbors:
                        if counts["local_rescue_trials"] >= batch["budgets"]["maximum_local_rescue_trials"]:
                            break
                        local = evaluate_locked(
                            evaluator=evaluator,
                            normalized=normalized,
                            proposal=proposal,
                            parameters=parameters,
                            orientation=orientation,
                            periods=DISCOVERY,
                            phase="adaptive",
                        )
                        counts["local_rescue_trials"] += 1
                        rescue_count += 1
                        local_gate = _discovery_gate(
                            local, local["summary"]["maximum_existing_factor_correlation"]
                        )
                        if local_gate["passed"]:
                            result, gate = local, local_gate
                            selected_parameters = parameters
                            optimization_mode = "one_hop_local_rescue"
                            break
                _, values = factor_values(
                    parse_template(proposal["template"]),
                    evaluator.contract,
                    selected_parameters,
                    evaluator.matrix,
                )
                relative = f"factor-values/{round_number:02d}-{index:02d}.parquet"
                value_path = work_root / "round-values" / relative
                value_path.parent.mkdir(parents=True, exist_ok=True)
                values.to_parquet(value_path, index=False, compression="zstd")
                round_files[relative] = value_path
                candidate = {
                    "lane": "dsl_lane",
                    "round_number": round_number,
                    "proposal_ordinal": index,
                    "proposal": proposal,
                    "factor_template_id": proposal["factor_template_id"],
                    "factor_instance_id": result["factor_instance_id"],
                    "structural_fingerprint": proposal["structural_fingerprint"],
                    "archetype": archetype,
                    "primary_statistic": ARCHETYPES[archetype]["primary_test_statistic"],
                    "parameters": selected_parameters,
                    "orientation": orientation,
                    "optimization_mode": optimization_mode,
                    "discovery_result": {
                        key: value for key, value in result.items() if key != "values"
                    },
                    "discovery_gate": gate,
                    "factor_values_file": relative,
                    "candidate_search_exposure": {
                        "agent_calls": counts["agent_calls"],
                        "proposals": counts["proposals"],
                        "admissions": counts["admissions"] + 1,
                        "local_rescue_trials": counts["local_rescue_trials"],
                    },
                }
                admitted.append(candidate)
                candidates.append(candidate | {"values": values})
                counts["admissions"] += 1
                known_fingerprints.add(proposal["structural_fingerprint"])
                evaluator.known_values.append((result["factor_instance_id"], values))
            except Exception as exc:
                code = str(exc)[:160]
                rejections.append({"proposal_ordinal": index, "failure_code": code})
                failure_codes.append(code)
                counts["rejected_structures"] += 1
                if "DUPLICATE" in code:
                    duplicates += 1
                    counts["duplicate_structures"] += 1
        round_identity = {
            "schema_version": "rolling-blind-agent-round-v1",
            "provider_id": "tushare-pro-v1",
            "parent_batch_id": batch["rolling_blind_discovery_batch_id"],
            "record_type": "dsl_agent_round",
            "round_number": round_number,
            "lane": lane,
            "family": family,
            "archetype": archetype,
            "agent_response_id": response_id,
            "proposal_count": len(response.get("proposals", [])),
            "admission_count": len(admitted),
            "rejection_count": len(rejections),
            "duplicate_count": duplicates,
            "local_rescue_trial_count": rescue_count,
            "qlib_calls": evaluator.qlib.calls - qlib_before,
            "admitted_candidates": admitted,
            "rejections": rejections,
            "blind_window_reads": 0,
            "blind_metrics_exposed": False,
            "fresh_evidence_reads": 0,
            "promotion_writes": 0,
        }
        round_id, round_receipt = _publish(
            repository,
            "rolling_blind_discovery_batch",
            round_identity,
            "round.json",
            lineage=(batch["rolling_blind_discovery_batch_id"], response_id),
            files=round_files,
        )
        counts["new_artifacts"] += int(not round_receipt["exact_existing"])
        counts["new_blobs"] += round_receipt["new_blob_count"]
        for candidate in candidates[-len(admitted):] if admitted else ():
            candidate["round_artifact_id"] = round_id
        counts["qlib_calls"] += evaluator.qlib.calls - qlib_before
    return candidates


def _model_hypotheses(
    repository: CampaignRepository,
    matrix: pd.DataFrame,
    catalogs: dict,
    model_spec: dict,
) -> list[dict]:
    feature = catalogs["feature_catalog"]
    primitive = catalogs["primitive_catalog"]
    base = _bundle_payloads(model_spec["model_spec_id"], feature, primitive)
    all_names = list(dict.fromkeys(
        name
        for row in base
        for name in row["candidate_feature_names"]
    ))
    existing = list(base[0]["candidate_feature_names"])
    expanded = list(base[1]["candidate_feature_names"])
    trend = [
        name for name in all_names
        if any(token in name.lower() for token in ("momentum", "trend", "path", "drawdown", "high"))
    ]
    trading = [
        name for name in all_names
        if any(token in name.lower() for token in ("volume", "amount", "liquidity", "volatility", "range"))
    ]
    discovery = matrix[matrix["trade_date"].between("2019-01-02", "2021-12-31")]
    decorrelated, selection = select_bundle_c(discovery, all_names)
    rows = [
        ("existing_technical_core", existing, "frozen existing technical core"),
        ("expanded_technical_space", expanded, "frozen expanded technical space"),
        ("all_technical_features", all_names, "fixed union of all authorized technical features"),
        ("trend_path_subset", trend[:32], "name-based trend/path family subset without labels"),
        ("trading_confirmation_subset", trading[:32], "name-based trading confirmation subset without labels"),
        ("label_free_decorrelated_union", decorrelated, "train-only label-free |Spearman|<0.95 union"),
    ]
    result = []
    for name, features, rationale in rows:
        stable = {
            "schema_version": "rolling-blind-model-hypothesis-v1",
            "provider_id": "tushare-pro-v1",
            "model_spec_id": model_spec["model_spec_id"],
            "hypothesis_name": name,
            "candidate_feature_names": list(dict.fromkeys(features)),
            "feature_count": len(set(features)),
            "membership_rule": rationale,
            "label_reads_for_membership": 0,
            "performance_reads_for_membership": 0,
            "hyperparameter_optimization_calls": 0,
            "seed_selection": False,
            "promotion_writes": 0,
        }
        stable["bundle_id"] = "rbmb1_" + hash_payload(stable)
        if name == "label_free_decorrelated_union":
            stable["selection_evidence"] = selection
        result.append(stable)
    return result


def _model_discovery(
    *,
    batch: dict,
    bundle,
    repository: CampaignRepository,
    work_root: Path,
    counts: dict,
) -> tuple[list[dict], pd.DataFrame, dict]:
    model_spec = repository.identity(MODEL_SPEC_ID) | {"model_spec_id": MODEL_SPEC_ID}
    catalogs_tuple = _catalog(repository)
    catalogs = {
        "feature_catalog": catalogs_tuple[0],
        "primitive_catalog": catalogs_tuple[1],
    }
    matrix = _model_matrix(bundle, repository, catalogs, work_root / "model-matrix")
    hypotheses = _model_hypotheses(repository, matrix, catalogs, model_spec)
    walk = {
        "walk_forward_spec_id": WALK_FORWARD_SPEC_ID,
        "purge_sessions": 10,
    }
    qlib = CampaignEvaluator(
        bundle=bundle,
        matrix=matrix.rename(columns={"model_label": "model_label"}),
        contract=_snapshot_contract(
            SOURCE_DATASET_ID,
            [name for name in matrix.columns if name not in {
                "symbol", "trade_date", "model_label", "raw_label",
                "sample_weight", "next_tradable", "next_locked_limit",
            }],
            matrix["trade_date"].nunique(),
        ),
        work_root=work_root / "model-qlib",
    ).qlib
    results = []
    prior_signals: list[pd.DataFrame] = []
    for index, hypothesis in enumerate(hypotheses, 1):
        counts["rounds"] += 1
        counts["model_hypotheses"] += 1
        counts["proposals"] += 1
        counts["admissions"] += 1
        bundle_spec = {
            "bundle_id": hypothesis["bundle_id"],
            "bundle_name": hypothesis["hypothesis_name"],
            "candidate_feature_names": hypothesis["candidate_feature_names"],
        }
        fold = {
            "fold_id": f"rolling_blind_model_discovery_{index:02d}",
            "train_start": "2019-01-02",
            "train_end": "2020-12-31",
            "test_start": "2021-01-04",
            "test_end": "2021-12-31",
        }
        before = qlib.calls
        result = _train_fold(
            model_spec,
            bundle_spec,
            walk,
            fold,
            matrix,
            repository,
            qlib,
            work_root / "model-discovery",
            research_context={
                "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
                "partition": "discovery_2019_2021",
                "blind_window_reads": 0,
            },
            output_namespace=f"rolling-blind-model-{index:02d}",
        )
        counts["model_training_calls"] += 3
        counts["qlib_calls"] += qlib.calls - before
        counts["new_artifacts"] += result["new_artifacts"]
        counts["new_blobs"] += result["new_blobs"]
        root = repository.materialize(result["fold_result_id"])
        signal = pd.read_parquet(root / "unified_signal.parquet").rename(
            columns={"pred": "factor_value"}
        )
        correlations = [
            signal_similarity(signal[["symbol", "trade_date", "factor_value"]], prior)
            for prior in prior_signals
        ]
        maximum = max(
            (abs(row["spearman"]) for row in correlations if row["spearman"] is not None),
            default=0.0,
        )
        metrics, qlib_result = result["metrics"], result["qlib"]
        checks = {
            "coverage": (metrics.get("coverage") or 0.0) >= 0.90,
            "pit": (metrics.get("pit_violation_count") or 0) == 0,
            "infinity": (metrics.get("infinity_count") or 0) == 0,
            "mean_rankic": (metrics.get("mean_rankic") or -999.0) > 0,
            "turnover": (qlib_result.get("turnover") or 999.0) <= 35,
            "concentration": (qlib_result.get("best_10_days_contribution") or 999.0) <= 0.35,
            "independence": maximum < 0.85,
        }
        results.append({
            "lane": "fixed_model_lane",
            "model_hypothesis": hypothesis,
            "bundle_id": hypothesis["bundle_id"],
            "archetype": "model_candidate",
            "primary_statistic": "daily_official_label_rankic",
            "model_configuration": model_spec["parameters"],
            "seeds": model_spec["seeds"],
            "discovery_result_id": result["fold_result_id"],
            "discovery_result": result,
            "discovery_gate": {
                "checks": checks,
                "passed": all(checks.values()),
                "failed_gates": [name for name, passed in checks.items() if not passed],
                "mean_rankic": metrics.get("mean_rankic"),
                "rankic_positive_rate": metrics.get("rankic_positive_rate"),
                "net_return": qlib_result.get("net_return"),
                "csi300_excess": qlib_result.get("net_excess_csi300"),
                "turnover": qlib_result.get("turnover"),
                "best_10_days_contribution": qlib_result.get("best_10_days_contribution"),
                "maximum_existing_spearman": maximum,
            },
            "candidate_search_exposure": {
                "agent_calls": counts["agent_calls"],
                "proposals": counts["proposals"],
                "admissions": counts["admissions"],
                "model_hypotheses": counts["model_hypotheses"],
            },
        })
        prior_signals.append(signal[["symbol", "trade_date", "factor_value"]])
    return results, matrix, model_spec


def _candidate_order(row: dict) -> tuple:
    gate = row["discovery_gate"]
    return (
        -int(gate["passed"]),
        -(gate.get("mean_rankic") or -999.0),
        -(gate.get("csi300_excess") or -999.0),
        gate.get("turnover") or 999.0,
        row.get("factor_instance_id") or row.get("bundle_id"),
    )


def _freeze_lock(
    repository: CampaignRepository,
    batch: dict,
    windows: dict,
    candidates: list[dict],
    counts: dict,
) -> tuple[dict, str, dict]:
    passed = sorted(
        [row for row in candidates if row["discovery_gate"]["passed"]],
        key=_candidate_order,
    )
    remaining = batch["budgets"]["maximum_qlib_calls"] - counts["qlib_calls"]
    capacity = min(
        batch["budgets"]["maximum_blind_submissions"],
        max(0, remaining // windows["complete_window_count"]),
    )
    selected = passed[:capacity]
    objects = []
    for rank, row in enumerate(selected, 1):
        item = {
            key: value for key, value in row.items()
            if key not in {"values", "discovery_result"}
        }
        item["discovery_rank"] = rank
        if row["lane"] == "dsl_lane":
            item["round_artifact_id"] = row.get("round_artifact_id")
            item["formula"] = row["proposal"]["canonical_dsl"]
            item["canonical_ast"] = row["proposal"]["canonical_ast"]
            item["feature_bundle"] = None
            item["label"] = "technical_return_1d"
        else:
            item["formula"] = None
            item["canonical_ast"] = None
            item["feature_bundle"] = row["model_hypothesis"]
            item["label"] = "technical_return_1d"
        objects.append(item)
    lock = {
        "schema_version": "rolling-blind-candidate-batch-lock-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
        "rolling_blind_window_set_id": batch["rolling_blind_window_set_id"],
        "objects": objects,
        "object_count": len(objects),
        "blind_window_reads_before_publish": 0,
        "agent_closed": True,
        "planner_closed": True,
        "failure_memory_closed": True,
        "parameters_frozen": True,
        "orientation_frozen": True,
        "archetype_frozen": True,
        "label_frozen": True,
        "feature_bundle_frozen": True,
        "strategy_frozen": True,
        "primary_statistic_frozen": True,
        "discovery_order_frozen": True,
        "blind_used_for_ranking": False,
        "fresh_evidence_used": False,
        "promotion_writes": 0,
    }
    lock_id, receipt = _publish(
        repository,
        "rolling_blind_candidate_batch_lock",
        lock,
        "candidate_batch_lock.json",
        lineage=(
            batch["rolling_blind_discovery_batch_id"],
            batch["rolling_blind_window_set_id"],
            *[row.get("round_artifact_id") or row.get("discovery_result_id") for row in selected],
        ),
    )
    return lock | {"rolling_blind_candidate_batch_lock_id": lock_id}, lock_id, receipt


def _window_metric(result: dict, archetype: str) -> float | None:
    row = result["annual"][0]
    if archetype == "top_tail_selection_factor":
        return row["tail"]["top20_universe_spread_mean"]
    return row["metrics"].get("mean_rank_ic")


def _window_payload(window: dict, result: dict, archetype: str) -> dict[str, Any]:
    row = result["annual"][0]
    metrics, qlib = row["metrics"], row["qlib"]
    return {
        "window_id": window["window_id"],
        "start_date": window["start_date"],
        "end_date": window["end_date"],
        "trading_day_count": window["trading_day_count"],
        "primary_metric": _window_metric(result, archetype),
        "mean_rankic": metrics.get("mean_rank_ic"),
        "rankic_positive_rate": metrics.get("rank_ic_positive_rate"),
        "q10_q1": row["diagnostics"].get("top_bottom_return"),
        "top20_universe_spread": row["tail"].get("top20_universe_spread_mean"),
        "net_return": qlib.get("net_return"),
        "csi300_return": qlib.get("benchmark_return"),
        "csi300_excess": qlib.get("net_excess_csi300"),
        "sharpe": qlib.get("sharpe_ratio"),
        "maximum_drawdown": qlib.get("max_drawdown"),
        "turnover": qlib.get("turnover"),
        "transaction_cost": qlib.get("transaction_cost"),
        "best_10_days_contribution": qlib.get("best_10_days_contribution"),
        "coverage": metrics.get("factor_finite_coverage"),
        "infinity_count": row["infinity_count"],
        "pit_violation_count": row["pit_violation_count"],
    }


def _model_window_payload(window: dict, result: dict) -> dict[str, Any]:
    metrics, qlib = result["metrics"], result["qlib"]
    return {
        "window_id": window["window_id"],
        "start_date": window["start_date"],
        "end_date": window["end_date"],
        "trading_day_count": window["trading_day_count"],
        "primary_metric": metrics.get("mean_rankic"),
        "mean_rankic": metrics.get("mean_rankic"),
        "rankic_positive_rate": metrics.get("rankic_positive_rate"),
        "q10_q1": metrics.get("q10_q1"),
        "top20_universe_spread": metrics.get("top20_universe_spread"),
        "net_return": qlib.get("net_return"),
        "csi300_return": qlib.get("benchmark_return"),
        "csi300_excess": qlib.get("net_excess_csi300"),
        "sharpe": qlib.get("sharpe_ratio"),
        "maximum_drawdown": qlib.get("max_drawdown"),
        "turnover": qlib.get("turnover"),
        "transaction_cost": qlib.get("transaction_cost"),
        "best_10_days_contribution": qlib.get("best_10_days_contribution"),
        "coverage": metrics.get("coverage"),
        "infinity_count": metrics.get("infinity_count"),
        "pit_violation_count": metrics.get("pit_violation_count"),
    }


def _mean_test(values: list[float]) -> dict[str, Any]:
    clean = np.asarray([value for value in values if value is not None], dtype=float)
    if len(clean) < 2:
        return {
            "observation_count": len(clean),
            "mean": float(np.mean(clean)) if len(clean) else None,
            "t_statistic": None,
            "raw_p_value": 1.0,
        }
    standard_error = float(np.std(clean, ddof=1) / math.sqrt(len(clean)))
    statistic = float(np.mean(clean) / standard_error) if standard_error > 0 else (
        math.inf if float(np.mean(clean)) > 0 else 0.0
    )
    try:
        from scipy.stats import t

        p_value = float(t.sf(statistic, df=len(clean) - 1))
    except Exception:
        p_value = float(0.5 * math.erfc(statistic / math.sqrt(2)))
    return {
        "observation_count": len(clean),
        "mean": float(np.mean(clean)),
        "standard_error": standard_error,
        "t_statistic": statistic,
        "raw_p_value": p_value,
        "alternative": "mean_window_primary_metric_greater_than_zero",
    }


def _blind_gate(rows: list[dict], *, unchanged: bool) -> dict[str, Any]:
    def clean(name: str) -> list[float]:
        return [
            float(row[name]) for row in rows
            if row.get(name) is not None and math.isfinite(float(row[name]))
        ]

    primary = clean("primary_metric")
    excess = clean("csi300_excess")
    turnover = clean("turnover")
    concentration = clean("best_10_days_contribution")
    worst_count = max(1, math.ceil(len(primary) * 0.20))

    def rate_positive(values: list[float]) -> float | None:
        return float(np.mean(np.asarray(values) > 0)) if values else None

    def midpoint(values: list[float]) -> float | None:
        return float(median(values)) if values else None

    summary = {
        "complete_window_count": len(rows),
        "primary_observation_count": len(primary),
        "primary_positive_window_rate": rate_positive(primary),
        "primary_window_median": midpoint(primary),
        "worst_20_percent_primary_mean": (
            float(np.mean(sorted(primary)[:worst_count])) if primary else None
        ),
        "csi300_excess_observation_count": len(excess),
        "csi300_excess_positive_window_rate": rate_positive(excess),
        "csi300_excess_window_median": midpoint(excess),
        "turnover_observation_count": len(turnover),
        "turnover_window_median": midpoint(turnover),
        "concentration_observation_count": len(concentration),
        "concentration_window_median": midpoint(concentration),
    }
    complete_metrics = all(
        len(values) == len(rows)
        for values in (primary, excess, turnover, concentration)
    )
    checks = {
        "minimum_windows": len(rows) >= 12,
        "complete_metrics": complete_metrics,
        "primary_positive_rate": (
            summary["primary_positive_window_rate"] is not None
            and summary["primary_positive_window_rate"] >= 0.70
        ),
        "primary_median": (
            summary["primary_window_median"] is not None
            and summary["primary_window_median"] > 0
        ),
        "primary_worst_20_percent": (
            summary["worst_20_percent_primary_mean"] is not None
            and summary["worst_20_percent_primary_mean"] > -0.01
        ),
        "excess_positive_rate": (
            summary["csi300_excess_positive_window_rate"] is not None
            and summary["csi300_excess_positive_window_rate"] >= 0.60
        ),
        "excess_median": (
            summary["csi300_excess_window_median"] is not None
            and summary["csi300_excess_window_median"] > 0
        ),
        "turnover": (
            summary["turnover_window_median"] is not None
            and summary["turnover_window_median"] <= 30
        ),
        "concentration": (
            summary["concentration_window_median"] is not None
            and summary["concentration_window_median"] <= 0.35
        ),
        "configuration_unchanged": unchanged,
    }
    return summary | {
        "checks": checks,
        "passed": all(checks.values()),
        "failed_gates": [name for name, passed in checks.items() if not passed],
    }


def _evaluate_blind(
    *,
    batch: dict,
    lock: dict,
    windows: dict,
    dsl_candidates: list[dict],
    model_matrix: pd.DataFrame,
    model_spec: dict,
    bundle,
    repository: CampaignRepository,
    work_root: Path,
    counts: dict,
) -> list[dict]:
    dsl_by_id = {row["factor_instance_id"]: row for row in dsl_candidates}
    source_matrix, _ = _source_matrix(bundle, work_root / "blind-source")
    source_matrix["trade_date"] = pd.to_datetime(source_matrix["trade_date"]).dt.strftime("%Y-%m-%d")
    normalized = bundle.normalized.copy()
    normalized["trade_date"] = pd.to_datetime(
        normalized["trade_date"]
    ).dt.strftime("%Y-%m-%d")
    contract = _snapshot_contract(
        SOURCE_DATASET_ID,
        [name for name in source_matrix.columns if name not in {
            "symbol", "trade_date", "raw_label", "model_label",
        }],
        source_matrix["trade_date"].nunique(),
    )
    evaluator = CampaignEvaluator(
        bundle=bundle,
        matrix=source_matrix,
        contract=contract,
        work_root=work_root / "blind-dsl",
    )
    qlib_model = CampaignEvaluator(
        bundle=bundle,
        matrix=model_matrix,
        contract=contract,
        work_root=work_root / "blind-model",
    ).qlib
    calendar = sorted(pd.to_datetime(model_matrix["trade_date"]).dt.strftime("%Y-%m-%d").unique())
    results = []
    for locked in lock["objects"]:
        counts["blind_submissions"] += 1
        window_rows = []
        window_artifacts = []
        for window in windows["windows"]:
            prior = [
                row for row in _rows(
                    repository,
                    "rolling_blind_candidate_result",
                    batch["rolling_blind_discovery_batch_id"],
                )
                if row.get("record_type") == "window_result"
                and row.get("candidate_key") == (
                    locked.get("factor_instance_id") or locked.get("bundle_id")
                )
                and row.get("window_id") == window["window_id"]
            ]
            if prior:
                window_rows.append(prior[-1]["metrics"])
                window_artifacts.append(prior[-1]["artifact_id"])
                continue
            if locked["lane"] == "dsl_lane":
                candidate = dsl_by_id[locked["factor_instance_id"]]
                before = evaluator.qlib.calls
                annual = _year_result(
                    evaluator,
                    candidate["values"],
                    locked["orientation"],
                    locked["factor_instance_id"],
                    window["window_id"],
                    (window["start_date"], window["end_date"]),
                    "historical_rolling_blind",
                )
                tails = tail_observations(
                    candidate["values"],
                    normalized,
                    locked["orientation"],
                    window["start_date"],
                    window["end_date"],
                )
                annual["tail"] = {
                    "observation_count": len(tails),
                    "non_overlapping_10_session_windows": True,
                    "top20_universe_spread_mean": (
                        float(np.mean([row["top20_universe_spread"] for row in tails]))
                        if tails else None
                    ),
                    "q10_universe_spread_mean": (
                        float(np.mean([row["q10_universe_spread"] for row in tails]))
                        if tails else None
                    ),
                    "top20_hit_rate": (
                        float(np.mean([row["top20_hit"] for row in tails]))
                        if tails else None
                    ),
                }
                result = {"annual": [annual]}
                payload = _window_payload(window, result, locked["archetype"])
                counts["qlib_calls"] += evaluator.qlib.calls - before
                lineage = (lock["rolling_blind_candidate_batch_lock_id"], locked["round_artifact_id"])
            else:
                prior_dates = [date for date in calendar if date < window["start_date"]]
                if len(prior_dates) <= 10:
                    raise ValueError("insufficient pre-window model training history")
                fold = {
                    "fold_id": f"{locked['bundle_id']}-{window['window_id']}",
                    "train_start": "2019-01-02",
                    "train_end": prior_dates[-1],
                    "test_start": window["start_date"],
                    "test_end": window["end_date"],
                }
                before = qlib_model.calls
                result = _train_fold(
                    model_spec,
                    {
                        "bundle_id": locked["bundle_id"],
                        "bundle_name": locked["model_hypothesis"]["hypothesis_name"],
                        "candidate_feature_names": locked["model_hypothesis"][
                            "candidate_feature_names"
                        ],
                    },
                    {"walk_forward_spec_id": WALK_FORWARD_SPEC_ID, "purge_sessions": 10},
                    fold,
                    model_matrix,
                    repository,
                    qlib_model,
                    work_root / "blind-model-folds",
                    research_context={
                        "rolling_blind_discovery_batch_id": batch[
                            "rolling_blind_discovery_batch_id"
                        ],
                        "partition": "historical_rolling_blind",
                        "window_id": window["window_id"],
                        "configuration_frozen": True,
                    },
                    output_namespace=f"{locked['bundle_id']}-{window['window_id']}",
                    fold_result_kind="model_fold_result",
                    fold_result_id_prefix="mfr1_",
                )
                counts["model_training_calls"] += 3
                counts["qlib_calls"] += qlib_model.calls - before
                payload = _model_window_payload(window, result)
                lineage = (
                    lock["rolling_blind_candidate_batch_lock_id"],
                    result["fold_result_id"],
                )
            identity = {
                "schema_version": "rolling-blind-candidate-window-result-v1",
                "provider_id": "tushare-pro-v1",
                "rolling_blind_discovery_batch_id": batch[
                    "rolling_blind_discovery_batch_id"
                ],
                "record_type": "window_result",
                "candidate_key": locked.get("factor_instance_id") or locked.get("bundle_id"),
                "lane": locked["lane"],
                "archetype": locked["archetype"],
                "window_id": window["window_id"],
                "metrics": payload,
                "agent_visible": False,
                "planner_visible": False,
                "failure_memory_visible": False,
                "configuration_unchanged": True,
                "promotion_writes": 0,
            }
            artifact_id, receipt = _publish(
                repository,
                "rolling_blind_candidate_result",
                identity,
                "window_result.json",
                lineage=lineage,
            )
            window_rows.append(payload)
            window_artifacts.append(artifact_id)
            counts["blind_window_evaluations"] += 1
            counts["new_artifacts"] += int(not receipt["exact_existing"])
            counts["new_blobs"] += receipt["new_blob_count"]
            if counts["qlib_calls"] > batch["budgets"]["maximum_qlib_calls"]:
                raise ValueError("QLIB_BUDGET_EXCEEDED")
        gate = _blind_gate(window_rows, unchanged=True)
        test = _mean_test([row["primary_metric"] for row in window_rows])
        final = {
            "schema_version": "rolling-blind-candidate-result-v1",
            "provider_id": "tushare-pro-v1",
            "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
            "record_type": "candidate_result",
            "candidate_key": locked.get("factor_instance_id") or locked.get("bundle_id"),
            "lane": locked["lane"],
            "archetype": locked["archetype"],
            "primary_statistic": locked["primary_statistic"],
            "candidate_batch_lock_id": lock["rolling_blind_candidate_batch_lock_id"],
            "window_set_id": batch["rolling_blind_window_set_id"],
            "window_result_ids": window_artifacts,
            "windows": window_rows,
            "gate": gate,
            "statistical_test": test,
            "all_windows_evaluated": len(window_rows) == windows["complete_window_count"],
            "early_stopped": False,
            "agent_visible": False,
            "planner_visible": False,
            "failure_memory_visible": False,
            "promotion_writes": 0,
        }
        result_id, receipt = _publish(
            repository,
            "rolling_blind_candidate_result",
            final,
            "candidate_result.json",
            lineage=(lock["rolling_blind_candidate_batch_lock_id"], *window_artifacts),
        )
        results.append(final | {"rolling_blind_candidate_result_id": result_id})
        counts["new_artifacts"] += int(not receipt["exact_existing"])
        counts["new_blobs"] += receipt["new_blob_count"]
    return results


def _latest_market_date(repository: CampaignRepository, fallback: str) -> str:
    dates = []
    for descriptor in repository.store.list_by_kind("fresh_market_snapshot"):
        row = repository.identity(descriptor.artifact_id)
        value = row.get("data_as_of_date") or row.get("latest_trade_date")
        if value:
            dates.append(value)
    return max(dates, default=fallback)


def _next_trade_date(bundle, latest: str) -> str:
    path = Path(bundle.qlib_view) / "calendars" / "day.txt"
    future = [
        line.strip()[:10] for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()[:10] > latest
    ]
    return future[0] if future else (pd.Timestamp(latest) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")


def _finalize(
    *,
    batch: dict,
    lock: dict,
    windows: dict,
    results: list[dict],
    counts: dict,
    bundle,
    repository: CampaignRepository,
    fresh_before: dict[str, list[str]],
) -> dict[str, Any]:
    multiple = benjamini_hochberg([
        {
            "candidate_result_id": row["rolling_blind_candidate_result_id"],
            "candidate_key": row["candidate_key"],
            "raw_p_value": row["statistical_test"]["raw_p_value"],
        }
        for row in results
    ], q=0.10)
    control = {
        "schema_version": "rolling-blind-multiple-testing-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
        "candidate_batch_lock_id": lock["rolling_blind_candidate_batch_lock_id"],
        "method": "Benjamini-Hochberg",
        "global_across_lanes": True,
        "fdr_q": 0.10,
        "results": multiple,
        "promotion_writes": 0,
    }
    control_id, control_receipt = _publish(
        repository,
        "rolling_blind_multiple_testing",
        control,
        "multiple_testing.json",
        lineage=tuple(row["rolling_blind_candidate_result_id"] for row in results),
    )
    counts["new_artifacts"] += int(not control_receipt["exact_existing"])
    counts["new_blobs"] += control_receipt["new_blob_count"]
    adjusted = {row["candidate_result_id"]: row for row in multiple}
    survivors, failures, fresh_locks = [], [], []
    for row in results:
        test = adjusted[row["rolling_blind_candidate_result_id"]]
        if row["gate"]["passed"] and test["adjusted_q_value"] <= 0.10:
            survivor = {
                "schema_version": "rolling-blind-alpha-survivor-v1",
                "provider_id": "tushare-pro-v1",
                "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
                "candidate_batch_lock_id": lock["rolling_blind_candidate_batch_lock_id"],
                "candidate_result_id": row["rolling_blind_candidate_result_id"],
                "multiple_testing_id": control_id,
                "candidate_key": row["candidate_key"],
                "lane": row["lane"],
                "archetype": row["archetype"],
                "primary_statistic": row["primary_statistic"],
                "status": "research_registered",
                "rolling_blind_passed": True,
                "historical_pseudo_fresh": True,
                "real_fresh_validated": False,
                "production_eligible": False,
                "adjusted_q_value": test["adjusted_q_value"],
                "registry_state": "research_registered",
                "promotion_writes": 0,
            }
            survivor_id, receipt = _publish(
                repository,
                "rolling_blind_alpha_survivor",
                survivor,
                "rolling_blind_alpha_survivor.json",
                lineage=(row["rolling_blind_candidate_result_id"], control_id),
            )
            survivors.append(survivor | {"rolling_blind_alpha_survivor_id": survivor_id})
            counts["survivor_writes"] += int(not receipt["exact_existing"])
            counts["registry_writes"] += int(not receipt["exact_existing"])
            counts["new_artifacts"] += int(not receipt["exact_existing"])
            counts["new_blobs"] += receipt["new_blob_count"]
            latest = _latest_market_date(repository, windows["available_calendar_end"])
            fresh = {
                "schema_version": "project-candidate-fresh-lock-v1",
                "provider_id": "tushare-pro-v1",
                "candidate_id": survivor_id,
                "candidate_type": "rolling_blind_alpha_survivor",
                "formula_parameters_orientation_archetype_frozen": True,
                "latest_market_data_date_at_lock": latest,
                "fresh_start_date": _next_trade_date(bundle, latest),
                "no_backfill": True,
                "minimum_fresh_trading_days": 60,
                "status": "fresh_locked",
                "real_fresh_validated": False,
                "promotion_writes": 0,
            }
            fresh_id, receipt = _publish(
                repository,
                "project_candidate_fresh_lock",
                fresh,
                "fresh_lock.json",
                lineage=(survivor_id,),
            )
            fresh_locks.append(fresh_id)
            counts["fresh_lock_writes"] += int(not receipt["exact_existing"])
            counts["new_artifacts"] += int(not receipt["exact_existing"])
            counts["new_blobs"] += receipt["new_blob_count"]
        else:
            failures.append({
                "candidate_result_id": row["rolling_blind_candidate_result_id"],
                "candidate_key": row["candidate_key"],
                "failed_gates": row["gate"]["failed_gates"],
                "adjusted_q_value": test["adjusted_q_value"],
                "feedback_to_agent": False,
                "feedback_to_planner": False,
                "feedback_to_failure_memory": False,
            })
    prior_ledgers = _rows(repository, "rolling_blind_submission_ledger")
    cumulative_before = max(
        (row.get("cumulative_blind_submissions", 0) for row in prior_ledgers),
        default=0,
    )
    ledger = {
        "schema_version": "rolling-blind-submission-ledger-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
        "candidate_batch_lock_id": lock["rolling_blind_candidate_batch_lock_id"],
        "batch_blind_submissions": len(results),
        "cumulative_blind_submissions_before": cumulative_before,
        "cumulative_blind_submissions": cumulative_before + len(results),
        "submitted_structure_keys": [row["candidate_key"] for row in results],
        "metrics_included": False,
        "failure_reasons_included": False,
        "usable_by_future_agent": {
            "duplicate_structure_only": True,
            "blind_submission_budget_only": True,
        },
        "promotion_writes": 0,
    }
    ledger_id, ledger_receipt = _publish(
        repository,
        "rolling_blind_submission_ledger",
        ledger,
        "submission_ledger.json",
        lineage=(lock["rolling_blind_candidate_batch_lock_id"],),
    )
    counts["new_artifacts"] += int(not ledger_receipt["exact_existing"])
    counts["new_blobs"] += ledger_receipt["new_blob_count"]
    exposure = {
        "schema_version": "rolling-blind-search-exposure-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
        "agent_calls": counts["agent_calls"],
        "proposals": counts["proposals"],
        "admissions": counts["admissions"],
        "rejected_structures": counts["rejected_structures"],
        "duplicate_structures": counts["duplicate_structures"],
        "local_rescue_trials": counts["local_rescue_trials"],
        "model_hypotheses": counts["model_hypotheses"],
        "blind_submissions": counts["blind_submissions"],
        "cumulative_historical_blind_submissions": ledger[
            "cumulative_blind_submissions"
        ],
        "candidate_search_exposure_embedded_in_lock": True,
        "batch_search_exposure_embedded_in_lock": True,
        "project_search_exposure_id": ledger_id,
        "promotion_writes": 0,
    }
    exposure_id, exposure_receipt = _publish(
        repository,
        "rolling_blind_search_exposure",
        exposure,
        "search_exposure.json",
        lineage=(ledger_id, lock["rolling_blind_candidate_batch_lock_id"]),
    )
    counts["new_artifacts"] += int(not exposure_receipt["exact_existing"])
    counts["new_blobs"] += exposure_receipt["new_blob_count"]
    fresh_after = {
        kind: sorted(row.artifact_id for row in repository.store.list_by_kind(kind))
        for kind in fresh_before
    }
    fresh_unchanged = fresh_before == fresh_after
    if not fresh_unchanged:
        raise ValueError("existing Fresh Cohort identities changed")
    status = (
        "completed_with_blind_survivors"
        if survivors
        else "completed_no_blind_submission"
        if not results
        else "completed_no_blind_survivor"
    )
    report = {
        "schema_version": "rolling-blind-research-report-v1",
        "provider_id": "tushare-pro-v1",
        "rolling_blind_discovery_batch_id": batch["rolling_blind_discovery_batch_id"],
        "status": status,
        "mainline_blocked": False,
        "window_set_id": batch["rolling_blind_window_set_id"],
        "candidate_batch_lock_id": lock["rolling_blind_candidate_batch_lock_id"],
        "candidate_result_ids": [
            row["rolling_blind_candidate_result_id"] for row in results
        ],
        "multiple_testing_id": control_id,
        "search_exposure_id": exposure_id,
        "submission_ledger_id": ledger_id,
        "survivor_ids": [
            row["rolling_blind_alpha_survivor_id"] for row in survivors
        ],
        "fresh_lock_ids": fresh_locks,
        "blind_failures": failures,
        "runtime_counts": counts,
        "existing_fresh_cohort_id": FRESH_COHORT_ID,
        "existing_fresh_objects_unchanged": fresh_unchanged,
        "historical_pseudo_fresh": True,
        "real_fresh_validation": False,
        "blind_feedback_to_same_batch": False,
        "manual_intervention_count": 0,
        "manual_round_planning_count": 0,
        "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0,
        "promotion_writes": 0,
        "research_efficiency": {
            "proposals_per_call": (
                counts["proposals"] / counts["agent_calls"]
                if counts["agent_calls"] else 0.0
            ),
            "admission_rate": (
                counts["admissions"] / counts["proposals"]
                if counts["proposals"] else 0.0
            ),
            "duplicate_rate": (
                counts["duplicate_structures"] / counts["proposals"]
                if counts["proposals"] else 0.0
            ),
            "discovery_to_blind_rate": (
                counts["blind_submissions"] / counts["admissions"]
                if counts["admissions"] else 0.0
            ),
            "blind_survival_rate": (
                len(survivors) / len(results) if results else 0.0
            ),
            "qlib_calls_per_blind_candidate": (
                counts["qlib_calls"] / len(results) if results else None
            ),
            "qlib_calls_per_survivor": (
                counts["qlib_calls"] / len(survivors) if survivors else None
            ),
            "manual_intervention_count": 0,
            "manual_round_planning_count": 0,
        },
    }
    report_id, report_receipt = _publish(
        repository,
        "rolling_blind_research_report",
        report,
        "rolling_blind_research_report.json",
        lineage=(
            batch["rolling_blind_discovery_batch_id"],
            lock["rolling_blind_candidate_batch_lock_id"],
            control_id,
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
        "multiple_testing": control,
        "survivors": survivors,
        "store_integrity": repository.integrity(),
    }


def _fresh_identity_snapshot(repository: CampaignRepository) -> dict[str, list[str]]:
    kinds = (
        "multi_horizon_retrospective_model_candidate",
        "multi_horizon_model_fresh_lock",
        "model_fresh_candidate_cohort",
        "fresh_model_heartbeat_run",
    )
    return {
        kind: sorted(row.artifact_id for row in repository.store.list_by_kind(kind))
        for kind in kinds
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
    reports = _rows(repository, "rolling_blind_research_report", batch_id)
    if reports:
        replay = replay_batch(
            rolling_blind_discovery_batch_id=batch_id,
            repository_root=repository_root,
            work_root=Path(work_root) / "terminal-replay",
            store_root=store_root,
        )
        return replay | {
            "supervisor_id": supervisor_id,
            "research_type": "rolling_blind_alpha_discovery",
            "exact_existing": True,
        }
    batch = repository.identity(batch_id) | {
        "rolling_blind_discovery_batch_id": batch_id
    }
    windows = repository.identity(batch["rolling_blind_window_set_id"]) | {
        "rolling_blind_window_set_id": batch["rolling_blind_window_set_id"]
    }
    fresh_before = _fresh_identity_snapshot(repository)
    counts = empty_runtime_counts()
    counts["new_artifacts"] = frozen["new_artifacts"]
    counts["new_blobs"] = frozen["new_blobs"]
    dsl = _dsl_discovery(
        batch=batch,
        bundle=bundle,
        repository=repository,
        work_root=Path(work_root) / "dsl-lane",
        counts=counts,
    )
    model, model_matrix, model_spec = _model_discovery(
        batch=batch,
        bundle=bundle,
        repository=repository,
        work_root=Path(work_root) / "model-lane",
        counts=counts,
    )
    if counts["agent_calls"] < 18 or counts["rounds"] < 18:
        raise ValueError("automatic early stop occurred before minimum coverage")
    if len({family for _, family, _ in _dsl_round_schedule()}) < 8:
        raise ValueError("minimum distinct Family coverage was not reached")
    lock, lock_id, lock_receipt = _freeze_lock(
        repository, batch, windows, dsl + model, counts
    )
    counts["new_artifacts"] += int(not lock_receipt["exact_existing"])
    counts["new_blobs"] += lock_receipt["new_blob_count"]
    results = _evaluate_blind(
        batch=batch,
        lock=lock,
        windows=windows,
        dsl_candidates=dsl,
        model_matrix=model_matrix,
        model_spec=model_spec,
        bundle=bundle,
        repository=repository,
        work_root=Path(work_root) / "blind",
        counts=counts,
    )
    final = _finalize(
        batch=batch,
        lock=lock,
        windows=windows,
        results=results,
        counts=counts,
        bundle=bundle,
        repository=repository,
        fresh_before=fresh_before,
    )
    return final | {
        "supervisor_id": supervisor_id,
        "research_type": "rolling_blind_alpha_discovery",
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
    if batch.get("schema_version") != "rolling-blind-discovery-batch-v1":
        raise ValueError("Rolling Blind Batch is invalid")
    reports = _rows(
        repository, "rolling_blind_research_report",
        rolling_blind_discovery_batch_id,
    )
    if len(reports) != 1 or reports[0]["status"] not in TERMINAL_STATUSES:
        raise ValueError("Rolling Blind terminal Report is absent or ambiguous")
    report = reports[0]
    recovered = []
    for identity in (
        report["window_set_id"],
        report["candidate_batch_lock_id"],
        *report["candidate_result_ids"],
        report["multiple_testing_id"],
        report["search_exposure_id"],
        report["submission_ledger_id"],
        *report["survivor_ids"],
        *report["fresh_lock_ids"],
        report["artifact_id"],
    ):
        repository.materialize(identity)
        recovered.append(identity)
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
        "runtime_counts": empty_runtime_counts(),
        "agent_calls": 0,
        "model_training_calls": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "candidate_writes": 0,
        "survivor_writes": 0,
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
