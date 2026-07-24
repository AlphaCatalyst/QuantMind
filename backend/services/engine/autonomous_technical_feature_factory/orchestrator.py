from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import SOURCE_DATASET_ID
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

from .admission import quality_evidence, signal_correlation
from .agent import call_structured_codex
from .grammar import FeatureGrammarError, audit_ast, evaluate_ast, expression
from .models import (
    FEATURE_FAMILIES, PRIMITIVES, AutonomousTechnicalFeatureFactorySpecV1,
    empty_usage,
)
from .schemas import feature_agent_schema


def create_factory_spec(*, repository_root: Path, work_root: Path,
                        store_root: Path | None = None,
                        spec: AutonomousTechnicalFeatureFactorySpecV1 | None = None) -> dict:
    payload = (spec or AutonomousTechnicalFeatureFactorySpecV1()).payload()
    _, repository = _runtime(repository_root, work_root, store_root)
    receipt = repository.publish(
        "autonomous_technical_feature_factory_spec", payload,
        {"factory_spec.json": payload}, lineage=(SOURCE_DATASET_ID,),
    )
    repository.identity(payload["factory_spec_id"])
    return payload | {"store_receipt": receipt}


def _rows(repository, kind: str, factory_id: str) -> list[dict]:
    result = []
    for descriptor in repository.store.list_by_kind(kind):
        identity = repository.identity(descriptor.artifact_id)
        if identity.get("factory_spec_id") == factory_id:
            result.append(identity | {"artifact_id": descriptor.artifact_id})
    return result


def _market_frame(bundle) -> pd.DataFrame:
    normalized = bundle.normalized.copy() if isinstance(bundle.normalized, pd.DataFrame) else pd.read_parquet(bundle.normalized)
    if "symbol" in normalized:
        normalized = normalized.drop(columns=["ts_code"], errors="ignore")
    frame = normalized.rename(columns={"ts_code": "symbol", "vol": "volume"})
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame = frame.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    frame["daily_return"] = frame.groupby("symbol")["adjusted_close"].pct_change(fill_method=None)
    frame["vwap"] = (
        pd.to_numeric(frame["amount"], errors="coerce") * 1000
        / (pd.to_numeric(frame["volume"], errors="coerce") * 100).replace(0, np.nan)
    )
    benchmark = bundle.benchmark.copy() if isinstance(bundle.benchmark, pd.DataFrame) else pd.read_parquet(bundle.benchmark)
    benchmark["trade_date"] = pd.to_datetime(benchmark["trade_date"].astype(str)).dt.strftime("%Y-%m-%d")
    benchmark["csi300_return"] = pd.to_numeric(benchmark["close"], errors="coerce").pct_change(fill_method=None)
    frame = frame.merge(benchmark[["trade_date", "csi300_return"]], on="trade_date", how="left", validate="many_to_one")
    missing = [name for name in PRIMITIVES if name not in frame]
    if missing:
        raise ValueError(f"Factory primitive inputs missing: {missing}")
    return frame


def _prompt(spec: dict, call_index: int, family: str, existing: list[dict], failures: list[str]) -> str:
    context = {
        "factory_spec_id": spec["factory_spec_id"], "call_index": call_index,
        "target_family": family, "feature_families": list(FEATURE_FAMILIES),
        "input_primitives": list(PRIMITIVES),
        "authorized_operators": spec["authorized_operators"],
        "explicitly_unauthorized_operators": spec["unauthorized_contract_operators"],
        "fixed_windows": spec["fixed_windows"],
        "limits": {"input_primitives": 4, "window_parameters": 2, "ast_depth": 6, "operator_count": 8},
        "existing_feature_names_and_structures": [
            {"feature_name": row.get("feature_name"), "structural_fingerprint": row.get("structural_fingerprint")}
            for row in existing
        ],
        "unlabeled_failure_summaries": failures[-12:],
        "forbidden": [
            "labels", "forward returns", "RankIC", "returns", "backtests", "candidate performance",
            "2021-2026 metrics", "cs_rank", "cs_zscore", "strategy or portfolio controls",
        ],
    }
    return (
        "You are the unlabeled technical Terminal Feature proposal layer. Return exactly one JSON object "
        "matching the schema, with up to three distinct PIT-safe proposals for target_family. The canonical_ast "
        "is authoritative and must use only the supplied primitive and operator whitelist. Features are time-series "
        "terminals, never factors: no cross-sectional rank/zscore and no predictive or portfolio fields. "
        "Do not use or infer labels, forward returns, performance, or post-2020 evidence. Prefer mechanisms that "
        "are structurally distinct from the supplied catalog. REQUEST:\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _materialize(repository, spec_id: str, proposal_artifact_id: str, proposal: dict,
                 frame: pd.DataFrame, work_root: Path) -> tuple[dict, pd.DataFrame]:
    audit = audit_ast(proposal["canonical_ast"])
    values = frame[["symbol", "trade_date"]].copy()
    values["feature_value"] = evaluate_ast(proposal["canonical_ast"], frame)
    evidence = quality_evidence(values, "2019-01-02", "2020-12-31")
    feature_id = "rtf1_" + hash_payload({
        "ast": proposal["canonical_ast"], "parameters": proposal["default_parameters"],
        "provider": "tushare-pro-v1",
    })
    admission = {
        "schema_version": "technical-feature-admission-v1",
        "provider_id": "tushare-pro-v1", "factory_spec_id": spec_id,
        "proposal_artifact_id": proposal_artifact_id, "feature_id": feature_id,
        "feature_name": proposal["feature_name"], "family": proposal["feature_family"],
        "canonical_expression": expression(proposal["canonical_ast"]),
        "canonical_ast": proposal["canonical_ast"], "input_primitives": list(audit.primitives),
        "parameters": proposal["default_parameters"], "windows": list(audit.windows),
        "pit_contract": {"lagged_only": True, "pit_violations": 0},
        "coverage_evidence": evidence, "distribution_evidence": evidence,
        "persistence_evidence": {"daily_rank_autocorrelation_median": evidence["daily_rank_autocorrelation_median"]},
        "structural_fingerprint": audit.structural_fingerprint,
        "grammar_evidence": {"operator_count": audit.operator_count, "ast_depth": audit.depth},
        "status": "quality_passed" if evidence["passed"] else "rejected",
        "failure_codes": evidence["failed_gates"], "promotion_writes": 0,
    }
    receipt = repository.publish(
        "technical_feature_admission", admission, {"admission.json": admission},
        lineage=(spec_id, proposal_artifact_id),
    )
    admission["artifact_id"] = receipt["artifact_id"]
    if not evidence["passed"]:
        return admission, values
    path = work_root / "materialized" / f"{feature_id}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    values.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
    materialization = {
        "schema_version": "technical-feature-materialization-v1",
        "provider_id": "tushare-pro-v1", "factory_spec_id": spec_id,
        "feature_id": feature_id, "feature_name": proposal["feature_name"],
        "dataset_id": SOURCE_DATASET_ID, "row_count": len(values),
        "minimum_date": values["trade_date"].min(), "maximum_date": values["trade_date"].max(),
        "values_sha256": hash_file(path), "status": "research_terminal_feature",
        "usable_for_production": False, "promotion_writes": 0,
    }
    materialized = repository.publish(
        "technical_feature_materialization", materialization,
        {"feature_values.parquet": path, "materialization.json": materialization},
        lineage=(spec_id, receipt["artifact_id"]),
    )
    admission["materialized_artifact_id"] = materialized["artifact_id"]
    return admission, values


def execute_factory(*, factory_spec_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None, agent_caller=call_structured_codex) -> dict:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(factory_spec_id)
    if spec.get("schema_version") != "autonomous-technical-feature-factory-spec-v1":
        raise ValueError("Factory Spec is absent")
    catalogs = _rows(repository, "technical_feature_catalog_v2", factory_spec_id)
    if catalogs:
        return replay_factory(
            factory_spec_id=factory_spec_id, repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay", store_root=store_root,
        ) | {"exact_existing": True}
    usage = empty_usage()
    frame = _market_frame(bundle)
    existing_matrix, _ = _source_matrix(bundle, Path(work_root) / "existing-features")
    existing_names = [
        name for name in existing_matrix
        if name not in {"symbol", "trade_date", "raw_label", "model_label", "sample_weight"}
    ]
    admitted: list[dict] = []
    admitted_values: list[tuple[str, pd.DataFrame]] = []
    failures: list[str] = []
    response_rows = sorted(
        [row for row in _rows(repository, "technical_feature_proposal", factory_spec_id)
         if row.get("record_type") == "agent_response"],
        key=lambda row: row["call_index"],
    )
    budget = spec["budgets"]
    for call_index in range(1, budget["maximum_agent_calls"] + 1):
        family = FEATURE_FAMILIES[(call_index - 1) % len(FEATURE_FAMILIES)]
        prior = next((row for row in response_rows if row["call_index"] == call_index), None)
        if prior is None:
            response, evidence = agent_caller(
                prompt=_prompt(spec | {"factory_spec_id": factory_spec_id}, call_index, family, admitted, failures),
                schema=feature_agent_schema(), model=spec["model"],
            )
            response_identity = {
                "schema_version": "technical-feature-agent-response-v1",
                "record_type": "agent_response", "provider_id": "tushare-pro-v1",
                "factory_spec_id": factory_spec_id, "call_index": call_index,
                "target_family": family, "provider_evidence": evidence,
                "label_access": False, "performance_access": False,
                "maximum_metric_date": None, "promotion_writes": 0,
            }
            receipt = repository.publish(
                "technical_feature_proposal", response_identity,
                {"agent_response.json": response, "request_contract.json": {
                    "target_family": family, "allowed_primitives": list(PRIMITIVES),
                    "labels_included": False, "performance_included": False,
                }},
                lineage=(factory_spec_id,),
            )
            response_identity["artifact_id"] = receipt["artifact_id"]
            response_identity["response"] = response
        else:
            root = repository.materialize(prior["artifact_id"])
            response_identity = prior | {"response": json.loads((root / "agent_response.json").read_text())}
        usage["agent_calls"] += 1
        proposals = response_identity["response"].get("proposals", [])
        for ordinal, proposal in enumerate(proposals, 1):
            if usage["proposals"] >= budget["maximum_proposals"]:
                break
            usage["proposals"] += 1
            proposal = dict(proposal)
            proposal["feature_name"] = re.sub(r"[^a-z0-9_]+", "_", proposal["feature_name"].lower()).strip("_")[:80]
            identity = {
                "schema_version": "technical-feature-proposal-v1",
                "record_type": "proposal", "provider_id": "tushare-pro-v1",
                "factory_spec_id": factory_spec_id, "call_index": call_index,
                "proposal_ordinal": ordinal, "proposal": proposal,
                "agent_response_artifact_id": response_identity["artifact_id"],
                "label_access": False, "performance_access": False, "promotion_writes": 0,
            }
            receipt = repository.publish(
                "technical_feature_proposal", identity, {"proposal.json": proposal},
                lineage=(factory_spec_id, response_identity["artifact_id"]),
            )
            try:
                audit = audit_ast(proposal["canonical_ast"])
                if proposal["feature_family"] != family:
                    raise FeatureGrammarError("FEATURE_FAMILY_MISMATCH")
                if audit.structural_fingerprint in {row["structural_fingerprint"] for row in admitted}:
                    raise FeatureGrammarError("reject_feature_structure_duplicate")
                admission, values = _materialize(
                    repository, factory_spec_id, receipt["artifact_id"], proposal, frame, Path(work_root),
                )
                if not admission["coverage_evidence"]["passed"]:
                    failures.extend(admission["failure_codes"])
                    continue
                correlations = [
                    {"feature_id": feature_id, "absolute_spearman": abs(correlation)}
                    for feature_id, prior_values in admitted_values
                    if (correlation := signal_correlation(
                        values[values["trade_date"] <= "2020-12-31"],
                        prior_values[prior_values["trade_date"] <= "2020-12-31"],
                    )) is not None
                ]
                maximum = max((row["absolute_spearman"] for row in correlations), default=0.0)
                novelty = {
                    "schema_version": "technical-feature-novelty-index-v1",
                    "provider_id": "tushare-pro-v1", "factory_spec_id": factory_spec_id,
                    "feature_id": admission["feature_id"], "structural_fingerprint": audit.structural_fingerprint,
                    "comparisons": correlations, "maximum_absolute_spearman": maximum,
                    "structure_duplicate": False, "signal_duplicate": maximum >= .95,
                    "high_feature_redundancy": .85 <= maximum < .95,
                    "label_used": False, "promotion_writes": 0,
                }
                novelty_receipt = repository.publish(
                    "technical_feature_novelty_index", novelty, {"novelty.json": novelty},
                    lineage=(factory_spec_id, admission["artifact_id"], admission["materialized_artifact_id"]),
                )
                if maximum >= .95:
                    failures.append("reject_feature_signal_duplicate")
                    continue
                if len(admitted) < budget["maximum_admitted_features"]:
                    admission["status"] = "research_terminal_feature"
                    admission["novelty_artifact_id"] = novelty_receipt["artifact_id"]
                    admitted.append(admission)
                    admitted_values.append((admission["feature_id"], values))
                    usage["admissions"] += 1
                    usage["materializations"] += 1
            except (FeatureGrammarError, KeyError, TypeError, ValueError) as exc:
                failures.append(str(exc))
    existing = [
        {
            "feature_id": "existing_" + hash_payload({"dataset": SOURCE_DATASET_ID, "name": name})[:24],
            "feature_name": name, "source": "existing_formal_feature_dataset",
            "status": "existing_research_feature", "allowed_for_research": True,
            "usable_for_production": False,
        }
        for name in sorted(existing_names)
    ]
    new_features = [
        {
            "feature_id": row["feature_id"], "feature_name": row["feature_name"],
            "family": row["family"], "source": "technical_feature_factory_001",
            "status": "research_terminal_feature", "allowed_for_research": True,
            "usable_for_production": False, "canonical_ast": row["canonical_ast"],
            "canonical_expression": row["canonical_expression"],
            "structural_fingerprint": row["structural_fingerprint"],
            "materialized_artifact_id": row["materialized_artifact_id"],
            "novelty_artifact_id": row["novelty_artifact_id"],
        }
        for row in admitted
    ]
    catalog = {
        "schema_version": "technical-feature-catalog-v2",
        "provider_id": "tushare-pro-v1", "factory_spec_id": factory_spec_id,
        "factory_name": spec["factory_name"], "dataset_id": SOURCE_DATASET_ID,
        "frozen": True, "admission_period": spec["admission_period"],
        "existing_features": existing, "research_terminal_features": new_features,
        "feature_count": len(existing) + len(new_features),
        "budget_usage": usage, "failure_summary": sorted(set(failures)),
        "label_metrics_used": False, "backtests_used": False,
        "manual_intervention_count": 0, "manual_feature_planning_count": 0,
        "usable_for_production": False, "promotion_writes": 0,
    }
    receipt = repository.publish(
        "technical_feature_catalog_v2", catalog,
        {"technical_feature_catalog_v2.json": catalog},
        lineage=(factory_spec_id, *[row["materialized_artifact_id"] for row in admitted],
                 *[row["novelty_artifact_id"] for row in admitted]),
    )
    return {
        "status": "completed" if admitted else "completed_no_new_feature",
        "factory_spec_id": factory_spec_id, "feature_catalog_v2_id": receipt["artifact_id"],
        "admitted_feature_ids": [row["feature_id"] for row in admitted],
        "budget_usage": usage, "store_integrity": repository.integrity(),
    }


def inspect_factory(*, factory_spec_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None) -> dict:
    _, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(factory_spec_id)
    catalogs = _rows(repository, "technical_feature_catalog_v2", factory_spec_id)
    return {"factory_spec": spec, "catalog": catalogs[-1] if catalogs else None}


def validate_factory(**kwargs) -> dict:
    result = inspect_factory(**kwargs)
    catalog = result["catalog"]
    if not catalog or not catalog.get("frozen") or catalog.get("label_metrics_used"):
        raise ValueError("Factory terminal catalog is incomplete")
    return {"status": "valid", "factory_spec_id": kwargs["factory_spec_id"],
            "feature_catalog_v2_id": catalog["artifact_id"]}


def replay_factory(*, factory_spec_id: str, repository_root: Path, work_root: Path,
                   store_root: Path | None = None) -> dict:
    result = validate_factory(
        factory_spec_id=factory_spec_id, repository_root=repository_root,
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
