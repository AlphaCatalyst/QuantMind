from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.default_first_momentum_search.protocol import SOURCE_DATASET_ID
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

from .admission import quality_evidence, signal_correlation
from .agent import call_structured_codex
from .grammar import FeatureGrammarError, audit_ast_v2, evaluate_ast_v2, expression
from .models import (
    V2_AUTHORIZED_OPERATORS,
    V2_FEATURE_FAMILIES,
    V2_PRIMITIVES,
    AutonomousTechnicalFeatureFactorySpecV2,
    empty_usage,
)
from .operators import (
    AUTHORIZED_EXTENSION_OPERATORS,
    build_operator_extension,
    operator_validation,
)
from .orchestrator import _market_frame
from .primitives import build_primitive_catalog, primitive_values
from .schemas import feature_agent_schema_v2


EXISTING_CATALOG_V2_ID = "tfc2_229f1939bdd3023e0410d3def332f1a9fdbd8cb4193cc71e7e6a8660138cf5e6"


def _rows(repository, kind: str, factory_spec_id: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind(kind):
        identity = repository.identity(descriptor.artifact_id)
        if factory_spec_id is None or identity.get("factory_spec_id") == factory_spec_id:
            rows.append(identity | {"artifact_id": descriptor.artifact_id})
    return rows


def audit_and_build_research_space(*, repository_root: Path, work_root: Path,
                                   store_root: Path | None = None) -> dict[str, Any]:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    existing = repository.identity(EXISTING_CATALOG_V2_ID)
    if existing.get("schema_version") != "technical-feature-catalog-v2" or not existing.get("frozen"):
        raise ValueError("immutable Technical Feature Catalog v2 is unavailable")
    extension = build_operator_extension()
    extension_receipt = repository.publish(
        "technical_dsl_operator_extension",
        extension,
        {"operator_extension.json": extension},
        lineage=(EXISTING_CATALOG_V2_ID,),
    )
    validation = operator_validation(extension_receipt["artifact_id"])
    validation_receipt = repository.publish(
        "technical_dsl_operator_validation",
        validation,
        {"operator_validation.json": validation},
        lineage=(extension_receipt["artifact_id"],),
    )
    frame = _market_frame(bundle)
    primitive_catalog, primitive_counts = build_primitive_catalog(
        repository=repository,
        frame=frame,
        work_root=Path(work_root),
        operator_extension_id=extension_receipt["artifact_id"],
    )
    spec = AutonomousTechnicalFeatureFactorySpecV2().payload(
        operator_extension_id=extension_receipt["artifact_id"],
        primitive_catalog_id=primitive_catalog["primitive_catalog_id"],
        existing_feature_catalog_v2_id=EXISTING_CATALOG_V2_ID,
    )
    spec_receipt = repository.publish(
        "autonomous_technical_feature_factory_spec_v2",
        spec,
        {"factory_spec_v2.json": spec},
        lineage=(
            extension_receipt["artifact_id"],
            validation_receipt["artifact_id"],
            primitive_catalog["primitive_catalog_id"],
            EXISTING_CATALOG_V2_ID,
        ),
    )
    return {
        "status": "factory_v2_spec_frozen",
        "operator_extension_id": extension_receipt["artifact_id"],
        "operator_validation_id": validation_receipt["artifact_id"],
        "authorized_operators": list(AUTHORIZED_EXTENSION_OPERATORS),
        "rejected_operators": [
            row["operator_name"] for row in extension["rejected_operators"]
        ],
        "primitive_catalog_id": primitive_catalog["primitive_catalog_id"],
        "primitive_count": primitive_catalog["primitive_count"],
        "factory_spec_id": spec_receipt["artifact_id"],
        "tushare_calls": 0,
        "network_data_calls": 0,
        "new_artifacts": (
            int(not extension_receipt["exact_existing"])
            + int(not validation_receipt["exact_existing"])
            + int(not spec_receipt["exact_existing"])
            + primitive_counts["new_artifacts"]
        ),
        "new_blobs": (
            extension_receipt["new_blob_count"]
            + validation_receipt["new_blob_count"]
            + spec_receipt["new_blob_count"]
            + primitive_counts["new_blobs"]
        ),
        "store_integrity": repository.integrity(),
    }


def _v2_frame(bundle) -> pd.DataFrame:
    frame = _market_frame(bundle)
    for name, values in primitive_values(frame).items():
        frame[name] = values
    return frame


def _prompt(spec: dict[str, Any], call_index: int, family: str,
            existing_structures: list[dict[str, Any]], failures: list[str]) -> str:
    context = {
        "factory_spec_id": spec["factory_spec_id"],
        "call_index": call_index,
        "target_family": family,
        "input_primitives": spec["input_primitives"],
        "authorized_operators": spec["authorized_operators"],
        "fixed_windows": spec["fixed_windows"],
        "fixed_quantiles": spec["fixed_quantiles"],
        "limits": {
            "input_primitives": 4,
            "window_parameters": 2,
            "ast_depth": 7,
            "operator_count": 10,
        },
        "existing_feature_names_and_structures": existing_structures[-80:],
        "unlabeled_failure_summaries": failures[-12:],
        "forbidden": [
            "labels", "forward returns", "RankIC", "returns", "backtests",
            "candidate performance", "2021-2026 metrics", "Fresh results",
            "cs_rank", "cs_zscore", "strategy parameters", "dynamic positions",
            "regime gates", "financial data", "industry data",
        ],
    }
    return (
        "You are Feature Factory revision 2. Return one JSON object matching the schema "
        "with up to three structurally distinct PIT-safe Terminal Feature proposals for "
        "target_family. Use only supplied primitives/operators. Quantile is a fixed DSL "
        "constant, never a parameter. Do not infer or use labels, returns, backtests, "
        "post-2020 metrics, Fresh evidence, or portfolio controls. REQUEST:\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _publish_feature(repository, *, spec: dict[str, Any], proposal_artifact_id: str,
                     proposal: dict[str, Any], frame: pd.DataFrame,
                     work_root: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    primitives = tuple(spec["input_primitives"])
    audit = audit_ast_v2(proposal["canonical_ast"], primitives)
    values = frame[["symbol", "trade_date"]].copy()
    values["feature_value"] = evaluate_ast_v2(
        proposal["canonical_ast"], frame, primitives
    )
    evidence = quality_evidence(values, *spec["admission_period"])
    feature_id = "rtf2_" + hash_payload({
        "ast": proposal["canonical_ast"],
        "parameters": proposal["default_parameters"],
        "provider": "tushare-pro-v1",
        "factory": spec["factory_spec_id"],
    })
    admission = {
        "schema_version": "technical-feature-admission-v2",
        "provider_id": "tushare-pro-v1",
        "factory_spec_id": spec["factory_spec_id"],
        "proposal_artifact_id": proposal_artifact_id,
        "feature_id": feature_id,
        "feature_name": proposal["feature_name"],
        "family": proposal["feature_family"],
        "canonical_expression": expression(proposal["canonical_ast"]),
        "canonical_ast": proposal["canonical_ast"],
        "input_primitives": list(audit.primitives),
        "parameters": proposal["default_parameters"],
        "windows": list(audit.windows),
        "pit_contract": {"trailing_only": True, "pit_violations": 0},
        "coverage_evidence": evidence,
        "distribution_evidence": evidence,
        "persistence_evidence": {
            "daily_rank_autocorrelation_median": evidence[
                "daily_rank_autocorrelation_median"
            ]
        },
        "structural_fingerprint": audit.structural_fingerprint,
        "grammar_evidence": {
            "operator_count": audit.operator_count,
            "ast_depth": audit.depth,
        },
        "label_metrics_used": False,
        "backtests_used": False,
        "status": "quality_passed" if evidence["passed"] else "rejected",
        "failure_codes": evidence["failed_gates"],
        "promotion_writes": 0,
    }
    receipt = repository.publish(
        "technical_feature_admission",
        admission,
        {"admission_v2.json": admission},
        lineage=(spec["factory_spec_id"], proposal_artifact_id),
    )
    admission["artifact_id"] = receipt["artifact_id"]
    if not evidence["passed"]:
        return admission, values
    path = Path(work_root) / "materialized-v2" / f"{feature_id}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    values.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
    materialization = {
        "schema_version": "technical-feature-materialization-v2",
        "provider_id": "tushare-pro-v1",
        "factory_spec_id": spec["factory_spec_id"],
        "feature_id": feature_id,
        "feature_name": proposal["feature_name"],
        "dataset_id": SOURCE_DATASET_ID,
        "row_count": len(values),
        "minimum_date": values["trade_date"].min(),
        "maximum_date": values["trade_date"].max(),
        "values_sha256": hash_file(path),
        "status": "research_terminal_feature",
        "usable_for_production": False,
        "promotion_writes": 0,
    }
    materialized = repository.publish(
        "technical_feature_materialization",
        materialization,
        {"feature_values.parquet": path, "materialization_v2.json": materialization},
        lineage=(spec["factory_spec_id"], receipt["artifact_id"]),
    )
    admission["materialized_artifact_id"] = materialized["artifact_id"]
    return admission, values


def execute_factory_v2(*, factory_spec_id: str, repository_root: Path,
                       work_root: Path, store_root: Path | None = None,
                       agent_caller=call_structured_codex) -> dict[str, Any]:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(factory_spec_id) | {"factory_spec_id": factory_spec_id}
    if spec.get("schema_version") != "autonomous-technical-feature-factory-spec-v2":
        raise ValueError("Factory v2 Spec is absent")
    existing_catalogs = _rows(repository, "technical_feature_catalog_v3", factory_spec_id)
    if existing_catalogs:
        return replay_factory_v2(
            factory_spec_id=factory_spec_id,
            repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay",
            store_root=store_root,
        ) | {"exact_existing": True}
    catalog_v2 = repository.identity(spec["existing_feature_catalog_v2_id"])
    frame = _v2_frame(bundle)
    usage = empty_usage()
    failures: list[str] = []
    admitted: list[dict[str, Any]] = []
    admitted_values: list[tuple[str, pd.DataFrame]] = []
    existing_structures = [
        {
            "feature_name": row.get("feature_name"),
            "structural_fingerprint": row.get("structural_fingerprint"),
        }
        for row in catalog_v2.get("research_terminal_features", [])
    ]
    existing_fingerprints = {
        row["structural_fingerprint"] for row in existing_structures
        if row.get("structural_fingerprint")
    }
    prior_values: list[tuple[str, pd.DataFrame]] = []
    for row in catalog_v2.get("research_terminal_features", []):
        root = repository.materialize(row["materialized_artifact_id"])
        prior_values.append((
            row["feature_id"],
            pd.read_parquet(root / "feature_values.parquet"),
        ))
    response_rows = {
        row["call_index"]: row
        for row in _rows(repository, "technical_feature_proposal", factory_spec_id)
        if row.get("record_type") == "agent_response_v2"
    }
    budget = spec["budgets"]
    for call_index in range(1, budget["maximum_agent_calls"] + 1):
        family = V2_FEATURE_FAMILIES[(call_index - 1) % len(V2_FEATURE_FAMILIES)]
        prior = response_rows.get(call_index)
        if prior is None:
            response, evidence = agent_caller(
                prompt=_prompt(spec, call_index, family, existing_structures + admitted, failures),
                schema=feature_agent_schema_v2(),
                model=spec["model"],
            )
            response_identity = {
                "schema_version": "technical-feature-agent-response-v2",
                "record_type": "agent_response_v2",
                "provider_id": "tushare-pro-v1",
                "factory_spec_id": factory_spec_id,
                "call_index": call_index,
                "target_family": family,
                "provider_evidence": evidence,
                "label_access": False,
                "performance_access": False,
                "maximum_metric_date": None,
                "promotion_writes": 0,
            }
            receipt = repository.publish(
                "technical_feature_proposal",
                response_identity,
                {
                    "agent_response_v2.json": response,
                    "request_contract_v2.json": {
                        "target_family": family,
                        "allowed_primitives": spec["input_primitives"],
                        "allowed_operators": spec["authorized_operators"],
                        "labels_included": False,
                        "performance_included": False,
                    },
                },
                lineage=(factory_spec_id, spec["primitive_catalog_id"]),
            )
            response_artifact_id = receipt["artifact_id"]
        else:
            root = repository.materialize(prior["artifact_id"])
            response = json.loads((root / "agent_response_v2.json").read_text())
            response_artifact_id = prior["artifact_id"]
        usage["agent_calls"] += 1
        for ordinal, raw in enumerate(response.get("proposals", [])[:3], 1):
            if usage["proposals"] >= budget["maximum_proposals"]:
                break
            usage["proposals"] += 1
            proposal = dict(raw)
            proposal["feature_name"] = re.sub(
                r"[^a-z0-9_]+", "_", proposal["feature_name"].lower()
            ).strip("_")[:80]
            proposal_identity = {
                "schema_version": "technical-feature-proposal-v2",
                "record_type": "proposal_v2",
                "provider_id": "tushare-pro-v1",
                "factory_spec_id": factory_spec_id,
                "call_index": call_index,
                "proposal_ordinal": ordinal,
                "proposal": proposal,
                "agent_response_artifact_id": response_artifact_id,
                "label_access": False,
                "performance_access": False,
                "promotion_writes": 0,
            }
            proposal_receipt = repository.publish(
                "technical_feature_proposal",
                proposal_identity,
                {"proposal_v2.json": proposal},
                lineage=(factory_spec_id, response_artifact_id),
            )
            try:
                audit = audit_ast_v2(proposal["canonical_ast"], tuple(spec["input_primitives"]))
                if proposal["feature_family"] != family:
                    raise FeatureGrammarError("FEATURE_FAMILY_MISMATCH")
                if audit.structural_fingerprint in existing_fingerprints | {
                    row["structural_fingerprint"] for row in admitted
                }:
                    raise FeatureGrammarError("reject_feature_structure_duplicate")
                admission, values = _publish_feature(
                    repository,
                    spec=spec,
                    proposal_artifact_id=proposal_receipt["artifact_id"],
                    proposal=proposal,
                    frame=frame,
                    work_root=Path(work_root),
                )
                if not admission["coverage_evidence"]["passed"]:
                    failures.extend(admission["failure_codes"])
                    continue
                comparisons = []
                for feature_id, known in prior_values + admitted_values:
                    correlation = signal_correlation(
                        values[values["trade_date"] <= "2020-12-31"],
                        known[known["trade_date"] <= "2020-12-31"],
                    )
                    if correlation is not None:
                        comparisons.append({
                            "feature_id": feature_id,
                            "absolute_spearman": abs(correlation),
                        })
                maximum = max(
                    (row["absolute_spearman"] for row in comparisons),
                    default=0.0,
                )
                novelty = {
                    "schema_version": "technical-feature-novelty-index-v2",
                    "provider_id": "tushare-pro-v1",
                    "factory_spec_id": factory_spec_id,
                    "feature_id": admission["feature_id"],
                    "structural_fingerprint": audit.structural_fingerprint,
                    "comparisons": comparisons,
                    "maximum_absolute_spearman": maximum,
                    "structure_duplicate": False,
                    "signal_duplicate": maximum >= 0.95,
                    "high_feature_redundancy": 0.85 <= maximum < 0.95,
                    "label_used": False,
                    "promotion_writes": 0,
                }
                novelty_receipt = repository.publish(
                    "technical_feature_novelty_index",
                    novelty,
                    {"novelty_v2.json": novelty},
                    lineage=(
                        factory_spec_id,
                        admission["artifact_id"],
                        admission["materialized_artifact_id"],
                    ),
                )
                if maximum >= 0.95:
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
    new_features = [
        {
            "feature_id": row["feature_id"],
            "feature_name": row["feature_name"],
            "family": row["family"],
            "source": "technical_feature_factory_002",
            "status": "research_terminal_feature",
            "allowed_for_research": True,
            "usable_for_production": False,
            "canonical_ast": row["canonical_ast"],
            "canonical_expression": row["canonical_expression"],
            "structural_fingerprint": row["structural_fingerprint"],
            "materialized_artifact_id": row["materialized_artifact_id"],
            "novelty_artifact_id": row["novelty_artifact_id"],
        }
        for row in admitted
    ]
    catalog = {
        "schema_version": "technical-feature-catalog-v3",
        "provider_id": "tushare-pro-v1",
        "factory_spec_id": factory_spec_id,
        "factory_name": spec["factory_name"],
        "dataset_id": SOURCE_DATASET_ID,
        "parent_feature_catalog_v2_id": spec["existing_feature_catalog_v2_id"],
        "primitive_catalog_id": spec["primitive_catalog_id"],
        "operator_extension_id": spec["operator_extension_id"],
        "frozen": True,
        "admission_period": spec["admission_period"],
        "existing_features": catalog_v2["existing_features"],
        "research_terminal_features": (
            catalog_v2["research_terminal_features"] + new_features
        ),
        "new_research_terminal_features": new_features,
        "new_feature_count": len(new_features),
        "primitive_names": list(spec["input_primitives"]),
        "authorized_operators": list(spec["authorized_operators"]),
        "budget_usage": usage,
        "failure_summary": sorted(set(failures)),
        "label_metrics_used": False,
        "backtests_used": False,
        "manual_intervention_count": 0,
        "manual_feature_planning_count": 0,
        "usable_for_production": False,
        "promotion_writes": 0,
    }
    receipt = repository.publish(
        "technical_feature_catalog_v3",
        catalog,
        {"technical_feature_catalog_v3.json": catalog},
        lineage=(
            factory_spec_id,
            spec["existing_feature_catalog_v2_id"],
            spec["primitive_catalog_id"],
            spec["operator_extension_id"],
            *[row["materialized_artifact_id"] for row in new_features],
            *[row["novelty_artifact_id"] for row in new_features],
        ),
    )
    return {
        "status": "completed" if new_features else "completed_no_new_feature",
        "factory_spec_id": factory_spec_id,
        "feature_catalog_v3_id": receipt["artifact_id"],
        "new_feature_ids": [row["feature_id"] for row in new_features],
        "budget_usage": usage,
        "tushare_calls": 0,
        "network_data_calls": 0,
        "store_integrity": repository.integrity(),
    }


def inspect_factory_v2(*, factory_spec_id: str, repository_root: Path,
                       work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    catalogs = _rows(repository, "technical_feature_catalog_v3", factory_spec_id)
    return {
        "factory_spec": repository.identity(factory_spec_id),
        "catalog_v3": catalogs[-1] if catalogs else None,
    }


def validate_factory_v2(**kwargs) -> dict[str, Any]:
    value = inspect_factory_v2(**kwargs)
    catalog = value["catalog_v3"]
    if not catalog or not catalog.get("frozen"):
        raise ValueError("Technical Feature Catalog v3 is absent or mutable")
    if catalog.get("label_metrics_used") or catalog.get("backtests_used"):
        raise ValueError("Factory v2 accessed predictive evidence")
    return {
        "status": "valid",
        "factory_spec_id": kwargs["factory_spec_id"],
        "feature_catalog_v3_id": catalog["artifact_id"],
        "new_feature_count": catalog["new_feature_count"],
        "new_feature_ids": [
            row["feature_id"]
            for row in catalog.get("new_research_terminal_features", [])
        ],
        "budget_usage": catalog["budget_usage"],
    }


def replay_factory_v2(**kwargs) -> dict[str, Any]:
    result = validate_factory_v2(**kwargs)
    return result | {
        "status": "exact_replay",
        "operator_writes": 0,
        "primitive_writes": 0,
        "feature_agent_calls": 0,
        "alpha_agent_calls": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_data_calls": 0,
        "feature_writes": 0,
        "candidate_writes": 0,
        "fresh_lock_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
    }
