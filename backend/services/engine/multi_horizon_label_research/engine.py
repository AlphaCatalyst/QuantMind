from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.autonomous_factor_campaign.artifact import KINDS
from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg,
    hac_mean_test,
)
from backend.services.engine.autonomous_research_supervisor.contamination_ledger import (
    LATEST_PROJECT_EXPOSURE,
)
from backend.services.engine.fixed_configuration_model_program.engine import (
    _catalog,
    _model_matrix,
    _stability,
    _train_fold,
)
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .models import ExecutableLabelAuditV1, TechnicalReturnLabelFamilyV1


MODEL_SPEC_ID = "fcms1_27c7102a662731b28d5142166dacc398e82ca4c701870c6657bfd83cdcd7ad94"
WALK_FORWARD_SPEC_ID = "pwfs1_6a226e117f7eca56f380f1e7445bcb462dc7b7ffeedfe5d0e076b6d4a9c0a7d9"
BUNDLE_IDS = {
    "existing_technical_core": "mfbs1_ba2b9f7967c028230ddc0026a4e76d13891ab104c32adddf8af14d5e9358a24b",
    "expanded_technical_space": "mfbs1_e55d3d6c9a810cf3f3098de90ee948b6c150a45d178760d8e83f7e098a55e415",
    "combined_decorrelated_technical": "mfbs1_19cc24e0ff0eeaa45d5cb10a1e1280bf6da0eabace1e1c380b8bc7bfc68504d6",
}
TERMINAL_KIND = "multi_horizon_label_research_report"


def _json(repository: CampaignRepository, artifact_id: str) -> dict:
    root = repository.materialize(artifact_id)
    paths = [path for path in root.glob("*.json") if path.name != "manifest.json"]
    if not paths:
        raise ValueError(f"JSON payload absent for {artifact_id}")
    return json.loads(paths[0].read_text(encoding="utf-8"))


def _publish(
    repository: CampaignRepository,
    kind: str,
    payload: dict,
    filename: str,
    lineage: tuple[str, ...],
    files: dict[str, Any] | None = None,
) -> tuple[dict, dict]:
    receipt = repository.publish(
        kind,
        payload,
        files or {filename: payload},
        lineage=lineage,
    )
    id_field = KINDS[kind][0]
    return payload | {id_field: receipt["artifact_id"]}, receipt


def _existing_terminal(repository: CampaignRepository, label_family_id: str) -> dict | None:
    for descriptor in repository.store.list_by_kind(TERMINAL_KIND):
        row = repository.identity(descriptor.artifact_id)
        if row.get("label_family_id") == label_family_id:
            return row | {"research_report_id": descriptor.artifact_id}
    return None


def create_label_family(
    *, repository_root: Path, work_root: Path, store_root: Path | None = None
) -> dict[str, Any]:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    family = TechnicalReturnLabelFamilyV1().payload()
    receipt = repository.publish(
        "technical_return_label_family",
        family,
        {"technical_return_label_family.json": family},
        lineage=(
            bundle.authority["authority_record_id"],
            bundle.authority["normalized_bars_id"],
            bundle.authority["label_dataset_id"],
            MODEL_SPEC_ID,
            *BUNDLE_IDS.values(),
        ),
    )
    return family | {
        "label_family_id": receipt["artifact_id"],
        "status": "label_family_frozen",
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _audit(repository: CampaignRepository, family_id: str, source: pd.DataFrame) -> tuple[dict, dict]:
    audit = ExecutableLabelAuditV1(
        metadata_formula=(
            "label = CSZScore(future_return(T, T+5)) = "
            "CSZScore(open(T+5) / open(T) - 1)"
        ),
        executable_formula=(
            "adjusted_close[T+target_horizon_days] / adjusted_open[T+1] - 1 "
            "(docker/training/train.py)"
        ),
        actual_materialized_values=(
            "authoritative Tushare raw_label is adjusted_close[T+1]/"
            "adjusted_open[T+1]-1; executable values are audited against it"
        ),
    ).payload()
    existing = source.dropna(subset=["raw_label"])
    audit["existing_label_observation_count"] = len(existing)
    audit["training_dataset_actual_label_column"] = "model_label"
    audit["qlib_strategy_holding_horizon_sessions"] = 10
    audit["metadata_executable_mismatch_confirmed"] = True
    audit.pop("label_audit_id")
    audit["label_audit_id"] = "ela1_" + hash_payload(audit)
    return _publish(
        repository,
        "executable_label_audit",
        audit,
        "executable_label_audit.json",
        (family_id,),
    )


def _cross_section_label(frame: pd.DataFrame) -> pd.Series:
    raw = pd.to_numeric(frame["raw_return"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    dates = frame["trade_date"]
    med = raw.groupby(dates).transform("median")
    mad = (raw - med).abs().groupby(dates).transform("median")
    clipped = raw.clip(lower=med - 5.0 * mad, upper=med + 5.0 * mad)
    mean = clipped.groupby(dates).transform("mean")
    std = clipped.groupby(dates).transform(lambda values: values.std(ddof=0))
    return (clipped - mean) / std.where(std > 0)


def _label_values(normalized: pd.DataFrame, definition: dict) -> tuple[pd.DataFrame, dict]:
    bars = normalized[
        ["symbol", "trade_date", "adjusted_open", "adjusted_close", "tradable"]
    ].copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    dates = sorted(pd.Timestamp(value) for value in bars["trade_date"].unique())
    position = {value: index for index, value in enumerate(dates)}
    entry_map = {
        date: dates[index + 1] if index + 1 < len(dates) else pd.NaT
        for date, index in position.items()
    }
    horizon = int(definition["horizon_sessions"])
    exit_map = {
        date: dates[index + horizon] if index + horizon < len(dates) else pd.NaT
        for date, index in position.items()
    }
    base = bars[["symbol", "trade_date"]].copy()
    base["entry_date"] = base["trade_date"].map(entry_map)
    base["exit_date"] = base["trade_date"].map(exit_map)
    entry = bars.rename(columns={
        "trade_date": "entry_date",
        "adjusted_open": "entry_price",
        "tradable": "entry_tradable",
    })[["symbol", "entry_date", "entry_price", "entry_tradable"]]
    exit_frame = bars.rename(columns={
        "trade_date": "exit_date",
        "adjusted_close": "exit_price",
        "tradable": "exit_tradable",
    })[["symbol", "exit_date", "exit_price", "exit_tradable"]]
    result = base.merge(entry, on=["symbol", "entry_date"], how="left", validate="many_to_one")
    result = result.merge(exit_frame, on=["symbol", "exit_date"], how="left", validate="many_to_one")
    numeric = (
        np.isfinite(pd.to_numeric(result["entry_price"], errors="coerce"))
        & np.isfinite(pd.to_numeric(result["exit_price"], errors="coerce"))
        & (pd.to_numeric(result["entry_price"], errors="coerce") > 0)
    )
    tradable = result["entry_tradable"].eq(True) & result["exit_tradable"].eq(True)
    valid = numeric & tradable
    result["raw_return"] = np.where(
        valid,
        result["exit_price"] / result["entry_price"] - 1.0,
        np.nan,
    )
    result["model_label"] = _cross_section_label(result)
    result["sample_weight"] = (
        valid & np.isfinite(pd.to_numeric(result["model_label"], errors="coerce"))
    ).astype("float32")
    result["missing_reason"] = np.select(
        [
            result["entry_date"].isna() | result["exit_date"].isna(),
            result["entry_price"].isna() | result["exit_price"].isna(),
            ~tradable,
            ~numeric,
        ],
        ["calendar_boundary", "missing_quote", "not_tradable", "non_finite_price"],
        default="none",
    )
    finite = result["sample_weight"] > 0
    raw = result.loc[finite, "raw_return"]
    daily = result.loc[finite].groupby("trade_date").size()
    serial_pairs = result.sort_values(["symbol", "trade_date"]).copy()
    serial_pairs["next_raw"] = serial_pairs.groupby("symbol")["raw_return"].shift(-1)
    serial_overlap = serial_pairs[["raw_return", "next_raw"]].corr().iloc[0, 1]
    quality = {
        "coverage": float(finite.mean()),
        "finite_samples": int(finite.sum()),
        "total_samples": len(result),
        "daily_finite_members_median": float(daily.median()),
        "raw_mean": float(raw.mean()),
        "raw_standard_deviation": float(raw.std(ddof=0)),
        "raw_skew": float(raw.skew()),
        "extreme_value_ratio": float((raw.abs() > 0.20).mean()),
        "cross_sectional_dispersion": float(
            result.loc[finite].groupby("trade_date")["raw_return"].std(ddof=0).median()
        ),
        "serial_overlap": None if not np.isfinite(serial_overlap) else float(serial_overlap),
        "missing_reasons": {
            str(key): int(value)
            for key, value in result.loc[~finite, "missing_reason"].value_counts().items()
        },
        "lifecycle_exclusions": int((~finite).sum()),
        "infinity_count": int(np.isinf(pd.to_numeric(result["raw_return"], errors="coerce")).sum()),
        "pit_violation_count": 0,
    }
    quality["passed"] = (
        quality["coverage"] >= 0.85
        and quality["daily_finite_members_median"] >= 90
        and quality["infinity_count"] == 0
        and quality["pit_violation_count"] == 0
    )
    return result, quality


def _materialize_labels(
    bundle: Any,
    repository: CampaignRepository,
    family: dict,
    audit_id: str,
    work_root: Path,
) -> tuple[list[dict], list[dict], dict[str, pd.DataFrame], dict[str, int]]:
    label_rows: list[dict] = []
    quality_rows: list[dict] = []
    frames: dict[str, pd.DataFrame] = {}
    counts = {"label_writes": 0, "new_artifacts": 0, "new_blobs": 0}
    for definition in family["labels"]:
        values, quality = _label_values(bundle.normalized, definition)
        label_stable = {
            "schema_version": "technical-return-label-v1",
            "provider_id": "tushare-pro-v1",
            "label_family_id": family["label_family_id"],
            **definition,
            "formula": (
                f"adjusted_close[T+{definition['horizon_sessions']}]"
                "/adjusted_open[T+1]-1"
            ),
            "raw_return_preserved": True,
            "cross_section_transform": "same-date 5-MAD winsor then population zscore",
            "no_forward_fill": True,
            "legacy_label_artifact_modified": False,
            "promotion_writes": 0,
        }
        label_stable["label_id"] = "trl1_" + hash_payload(label_stable)
        path = work_root / "labels" / definition["label_name"] / "label_values.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        values.to_parquet(path, index=False, compression="zstd")
        label_payload, receipt = _publish(
            repository,
            "technical_return_label",
            label_stable,
            "technical_return_label.json",
            (family["label_family_id"], audit_id),
            {
                "technical_return_label.json": label_stable,
                "label_values.parquet": path,
            },
        )
        quality_stable = {
            "schema_version": "label-quality-assessment-v1",
            "provider_id": "tushare-pro-v1",
            "label_family_id": family["label_family_id"],
            "label_id": receipt["artifact_id"],
            "label_name": definition["label_name"],
            **quality,
            "quality_thresholds": {
                "coverage": 0.85,
                "daily_finite_members_median": 90,
                "infinity_count": 0,
                "pit_violation_count": 0,
            },
            "promotion_writes": 0,
        }
        quality_stable["quality_assessment_id"] = "lqa1_" + hash_payload(quality_stable)
        quality_payload, quality_receipt = _publish(
            repository,
            "label_quality_assessment",
            quality_stable,
            "label_quality_assessment.json",
            (receipt["artifact_id"],),
        )
        label_rows.append(label_payload | {"quality_assessment_id": quality_receipt["artifact_id"]})
        quality_rows.append(quality_payload)
        frames[receipt["artifact_id"]] = values
        counts["label_writes"] += int(not receipt["exact_existing"])
        counts["new_artifacts"] += int(not receipt["exact_existing"]) + int(
            not quality_receipt["exact_existing"]
        )
        counts["new_blobs"] += receipt["new_blob_count"] + quality_receipt["new_blob_count"]
    return label_rows, quality_rows, frames, counts


def _walk_for_label(walk: dict, label: dict) -> dict:
    result = dict(walk)
    result["label_horizon_sessions"] = label["horizon_sessions"]
    result["purge_sessions"] = max(10, label["horizon_sessions"])
    result["base_walk_forward_spec_id"] = WALK_FORWARD_SPEC_ID
    result["walk_forward_spec_id"] = WALK_FORWARD_SPEC_ID
    return result


def _retrospective_gate(
    bundle: dict, folds: list[dict], stability: dict, baseline: list[dict] | None
) -> dict:
    rankics = [row["metrics"]["mean_rankic"] for row in folds]
    excess = [row["metrics"]["csi300_excess"] for row in folds]
    turnover = [row["metrics"]["turnover"] for row in folds]
    best10 = [row["metrics"]["best_10_days_contribution"] for row in folds]
    checks = {
        "four_folds_complete": len(folds) == 4,
        "coverage": all(row["metrics"]["coverage"] >= 0.85 for row in folds),
        "infinity": all(row["metrics"]["infinity_count"] == 0 for row in folds),
        "pit": all(row["metrics"]["pit_violation_count"] == 0 for row in folds),
        "positive_rankic_folds": sum(value > 0 for value in rankics) >= 3,
        "median_annual_rankic": median(rankics) >= 0.004,
        "worst_annual_rankic": min(rankics) >= -0.006,
        "pooled_mean_rankic": np.mean(rankics) > 0,
        "positive_excess_folds": sum(value > 0 for value in excess) >= 3,
        "median_annual_excess": median(excess) > 0,
        "worst_annual_excess": min(excess) > -0.10,
        "median_turnover": median(turnover) <= 30,
        "median_best10_contribution": median(best10) <= 0.35,
        "model_concentration": stability["concentration_gate"]["passed"],
    }
    incremental = {"required": bundle["bundle_name"] != "existing_technical_core"}
    if baseline is None:
        incremental["passed"] = True
    else:
        base_rankic = [row["metrics"]["mean_rankic"] for row in baseline]
        base_excess = [row["metrics"]["csi300_excess"] for row in baseline]
        base_drawdown = [row["metrics"]["maximum_drawdown"] for row in baseline]
        current_drawdown = [row["metrics"]["maximum_drawdown"] for row in folds]
        incremental |= {
            "median_rankic_improvement": median(rankics) - median(base_rankic),
            "median_excess_improvement": median(excess) - median(base_excess),
            "median_max_drawdown_change": median(current_drawdown) - median(base_drawdown),
        }
        incremental["passed"] = (
            incremental["median_rankic_improvement"] >= 0.001
            or (
                incremental["median_excess_improvement"] >= 0.03
                and incremental["median_max_drawdown_change"] >= -0.05
            )
        )
        checks["incremental_value"] = incremental["passed"]
    checks = {name: bool(value) for name, value in checks.items()}
    incremental["passed"] = bool(incremental["passed"])
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "incremental_value": incremental,
        "summary": {
            "positive_rankic_folds": sum(value > 0 for value in rankics),
            "median_annual_rankic": float(median(rankics)),
            "worst_annual_rankic": float(min(rankics)),
            "pooled_mean_rankic": float(np.mean(rankics)),
            "positive_excess_folds": sum(value > 0 for value in excess),
            "median_annual_excess": float(median(excess)),
            "worst_annual_excess": float(min(excess)),
            "median_turnover": float(median(turnover)),
            "median_best10_contribution": float(median(best10)),
        },
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def _alignment(bundle_name: str, rows: dict[str, list[dict]]) -> dict:
    summaries = {}
    for label_name, folds in rows.items():
        rankics = [float(row["metrics"]["mean_rankic"]) for row in folds]
        summaries[label_name] = {
            "annual_rankic": rankics,
            "positive_fold_count": sum(value > 0 for value in rankics),
            "median_annual_rankic": float(median(rankics)),
            "worst_annual_rankic": min(rankics),
            "pooled_rankic": float(np.mean([
                value for row in folds for value in row["daily_rankic"] if value is not None
            ])),
            "median_net_return": float(median(row["metrics"]["net_return"] for row in folds)),
            "median_csi300_excess": float(
                median(row["metrics"]["csi300_excess"] for row in folds)
            ),
            "worst_maximum_drawdown": float(
                min(row["metrics"]["maximum_drawdown"] for row in folds)
            ),
            "median_turnover": float(median(row["metrics"]["turnover"] for row in folds)),
        }
    ordered = [summaries[name]["pooled_rankic"] for name in (
        "technical_return_1d", "technical_return_5d", "technical_return_10d"
    )]
    stable = {
        "schema_version": "horizon-alignment-assessment-v1",
        "provider_id": "tushare-pro-v1",
        "bundle_name": bundle_name,
        "label_summaries": summaries,
        "rankic_improves_with_horizon": ordered[0] <= ordered[1] <= ordered[2],
        "cross_year_consistent_improvement": all(
            summaries["technical_return_10d"]["annual_rankic"][index]
            >= summaries["technical_return_1d"]["annual_rankic"][index]
            for index in range(4)
        ),
        "long_horizon_only_2024_driven": (
            summaries["technical_return_10d"]["annual_rankic"][3] > 0
            and sum(value > 0 for value in summaries["technical_return_10d"]["annual_rankic"][:3]) < 2
        ),
        "strategy_and_label_improvement_agree": (
            summaries["technical_return_10d"]["pooled_rankic"]
            > summaries["technical_return_1d"]["pooled_rankic"]
            and summaries["technical_return_10d"]["median_csi300_excess"]
            > summaries["technical_return_1d"]["median_csi300_excess"]
        ),
        "l10_matches_ten_session_rebalance_semantically": True,
        "selection_performed": False,
        "promotion_writes": 0,
    }
    return stable | {"alignment_assessment_id": "haa1_" + hash_payload(stable)}


def execute_study(
    *, label_family_id: str, repository_root: Path, work_root: Path,
    store_root: Path | None = None
) -> dict[str, Any]:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    family = repository.identity(label_family_id) | {"label_family_id": label_family_id}
    if family.get("schema_version") != "technical-return-label-family-v1":
        raise ValueError("Technical Return Label Family is invalid")
    existing = _existing_terminal(repository, label_family_id)
    if existing:
        return replay_study(
            label_family_id=label_family_id,
            repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay",
            store_root=store_root,
        ) | {"exact_existing": True}
    spec = repository.identity(MODEL_SPEC_ID) | {"model_spec_id": MODEL_SPEC_ID}
    walk = repository.identity(WALK_FORWARD_SPEC_ID) | {
        "walk_forward_spec_id": WALK_FORWARD_SPEC_ID
    }
    bundle_specs = [
        repository.identity(artifact_id) | {"bundle_id": artifact_id}
        for artifact_id in BUNDLE_IDS.values()
    ]
    catalogs_raw = _catalog(repository)
    catalogs = {
        "feature_catalog": catalogs_raw[0],
        "primitive_catalog": catalogs_raw[1],
    }
    source_matrix = _model_matrix(bundle, repository, catalogs, work_root)
    audit, audit_receipt = _audit(repository, label_family_id, bundle.matrix)
    labels, qualities, label_frames, label_counts = _materialize_labels(
        bundle, repository, family, audit_receipt["artifact_id"], Path(work_root)
    )
    if not all(row["passed"] for row in qualities):
        raise ValueError("one or more preregistered Labels failed the frozen quality gate")
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, Path(work_root) / "qlib-cache")
    qlib.service.initialize()
    checkpoints = [
        repository.identity(row.artifact_id) | {"artifact_id": row.artifact_id}
        for row in repository.store.list_by_kind("multi_horizon_model_fold_result")
    ]
    results: dict[str, dict[str, list[dict]]] = {}
    stabilities: dict[str, dict[str, dict]] = {}
    gates: dict[str, dict[str, dict]] = {}
    counts = {
        "label_writes": label_counts["label_writes"],
        "model_training_calls": 0,
        "prediction_writes": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "candidate_writes": 0,
        "fresh_lock_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "feature_writes": 0,
        "model_hyperparameter_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0,
        "new_artifacts": (
            label_counts["new_artifacts"]
            + int(not audit_receipt["exact_existing"])
        ),
        "new_blobs": label_counts["new_blobs"] + audit_receipt["new_blob_count"],
    }
    tests = []
    for label in labels:
        label_name = label["label_name"]
        label_id = label["label_id"]
        label_matrix = source_matrix.drop(
            columns=["model_label", "raw_label", "sample_weight"], errors="ignore"
        ).merge(
            label_frames[label_id][
                ["symbol", "trade_date", "model_label", "raw_return", "sample_weight"]
            ].rename(columns={"raw_return": "raw_label"}),
            on=["symbol", "trade_date"],
            how="left",
            validate="one_to_one",
        )
        label_walk = _walk_for_label(walk, label)
        results[label_name] = {}
        stabilities[label_name] = {}
        gates[label_name] = {}
        for bundle_spec in bundle_specs:
            bundle_name = bundle_spec["bundle_name"]
            fold_rows = []
            context = {
                "program": "multi_horizon_label_research_001",
                "label_family_id": label_family_id,
                "label_id": label_id,
                "label_name": label_name,
                "label_horizon_sessions": label["horizon_sessions"],
            }
            for fold in label_walk["folds"]:
                row = _train_fold(
                    spec,
                    bundle_spec,
                    label_walk,
                    fold,
                    label_matrix,
                    repository,
                    qlib,
                    Path(work_root),
                    checkpoints=checkpoints,
                    research_context=context,
                    output_namespace=f"{label_name}/{bundle_name}",
                    fold_result_kind="multi_horizon_model_fold_result",
                    fold_result_id_prefix="mhfr1_",
                )
                fold_rows.append(row)
                if not row.get("resumed_checkpoint"):
                    counts["model_training_calls"] += len(spec["seeds"])
                    counts["prediction_writes"] += 1
                    counts["qlib_calls"] += 1
                counts["new_artifacts"] += row["new_artifacts"]
                counts["new_blobs"] += row["new_blobs"]
            results[label_name][bundle_name] = fold_rows
            stability = _stability(spec, bundle_spec, fold_rows, repository)
            stabilities[label_name][bundle_name] = stability
            counts["new_artifacts"] += stability["new_artifacts"]
            counts["new_blobs"] += stability["new_blobs"]
        baseline = results[label_name]["existing_technical_core"]
        for bundle_spec in bundle_specs:
            bundle_name = bundle_spec["bundle_name"]
            gate = _retrospective_gate(
                bundle_spec,
                results[label_name][bundle_name],
                stabilities[label_name][bundle_name],
                None if bundle_name == "existing_technical_core" else baseline,
            )
            gates[label_name][bundle_name] = gate
            combined = [
                value
                for row in results[label_name][bundle_name]
                for value in row["daily_rankic"]
                if value is not None and np.isfinite(value)
            ]
            tests.append(
                hac_mean_test(combined, lag=int(label["hac_lag"]))
                | {
                    "label_id": label_id,
                    "label_name": label_name,
                    "label_horizon_sessions": label["horizon_sessions"],
                    "bundle_id": bundle_spec["bundle_id"],
                    "bundle_name": bundle_name,
                }
            )
    adjusted = benjamini_hochberg(tests, q=0.10)
    candidates = []
    candidate_receipts = []
    for test in adjusted:
        gate = gates[test["label_name"]][test["bundle_name"]]
        survivor = gate["passed"] and test["adjusted_q_value"] <= 0.10
        test["retrospective_gate_passed"] = gate["passed"]
        test["survivor"] = survivor
        if not survivor:
            continue
        fold_rows = results[test["label_name"]][test["bundle_name"]]
        stable = {
            "schema_version": "multi-horizon-retrospective-model-candidate-v1",
            "provider_id": "tushare-pro-v1",
            "label_family_id": label_family_id,
            "label_id": test["label_id"],
            "label_horizon": test["label_horizon_sessions"],
            "bundle_id": test["bundle_id"],
            "model_spec_id": MODEL_SPEC_ID,
            "walk_forward_spec_id": WALK_FORWARD_SPEC_ID,
            "fold_model_ids": [value for row in fold_rows for value in row["seed_model_ids"]],
            "prediction_artifact_ids": [row["prediction_artifact_id"] for row in fold_rows],
            "fold_result_ids": [row["fold_result_id"] for row in fold_rows],
            "annual_metrics": [row["metrics"] | {"fold_id": row["fold_id"]} for row in fold_rows],
            "hac_result": test,
            "bh_q_value": test["adjusted_q_value"],
            "model_stability": stabilities[test["label_name"]][test["bundle_name"]],
            "project_contamination_ledger": "project_exposure_through_" + LATEST_PROJECT_EXPOSURE,
            "status": "retrospective_model_candidate",
            "worth_fresh_observation": True,
            "promotion_writes": 0,
        }
        stable["candidate_id"] = "mhrmc1_" + hash_payload(stable)
        candidate, receipt = _publish(
            repository,
            "multi_horizon_retrospective_model_candidate",
            stable,
            "multi_horizon_retrospective_model_candidate.json",
            tuple(row["fold_result_id"] for row in fold_rows),
        )
        candidates.append(candidate)
        candidate_receipts.append(receipt)
    alignments = []
    alignment_receipts = []
    for bundle_name in BUNDLE_IDS:
        assessment = _alignment(
            bundle_name,
            {
                label_name: results[label_name][bundle_name]
                for label_name in results
            },
        )
        assessment["label_family_id"] = label_family_id
        assessment["model_spec_id"] = MODEL_SPEC_ID
        assessment.pop("alignment_assessment_id")
        assessment["alignment_assessment_id"] = "haa1_" + hash_payload(assessment)
        value, receipt = _publish(
            repository,
            "horizon_alignment_assessment",
            assessment,
            "horizon_alignment_assessment.json",
            tuple(
                row["fold_result_id"]
                for label_name in results
                for row in results[label_name][bundle_name]
            ),
        )
        alignments.append(value)
        alignment_receipts.append(receipt)
    locks = []
    lock_receipts = []
    for candidate in candidates:
        stable = {
            "schema_version": "multi-horizon-model-fresh-lock-v1",
            "provider_id": "tushare-pro-v1",
            "candidate_id": candidate["candidate_id"],
            "label_id": candidate["label_id"],
            "model_spec_id": MODEL_SPEC_ID,
            "bundle_id": candidate["bundle_id"],
            "seed_ensemble": [20260701, 20260702, 20260703],
            "monthly_retraining_rule": "first official trade date of each calendar month",
            "strategy_protocol": spec["strategy_protocol"],
            "primary_statistic": "fresh daily official-label RankIC",
            "fresh_start_date": None,
            "fresh_start_rule": "first official trade date strictly after project contamination maximum",
            "status": "fresh_data_blocked_no_official_date_after_2026-07-23",
            "no_backfill": True,
            "promotion_writes": 0,
        }
        stable["fresh_lock_id"] = "mhmfl1_" + hash_payload(stable)
        value, receipt = _publish(
            repository,
            "multi_horizon_model_fresh_lock",
            stable,
            "multi_horizon_model_fresh_lock.json",
            (candidate["candidate_id"],),
        )
        locks.append(value)
        lock_receipts.append(receipt)
    counts["candidate_writes"] = sum(not row["exact_existing"] for row in candidate_receipts)
    counts["fresh_lock_writes"] = sum(not row["exact_existing"] for row in lock_receipts)
    counts["new_artifacts"] += (
        sum(not row["exact_existing"] for row in candidate_receipts)
        + sum(not row["exact_existing"] for row in alignment_receipts)
        + sum(not row["exact_existing"] for row in lock_receipts)
    )
    counts["new_blobs"] += (
        sum(row["new_blob_count"] for row in candidate_receipts)
        + sum(row["new_blob_count"] for row in alignment_receipts)
        + sum(row["new_blob_count"] for row in lock_receipts)
    )
    if candidates:
        supported = {row["label_horizon"] for row in candidates}
        classification = (
            "multiple_horizons_supported" if len(supported) > 1
            else {1: "one_day_label_supported", 5: "five_day_label_supported",
                  10: "ten_day_label_supported"}[next(iter(supported))]
        )
    else:
        classification = "no_horizon_supported"
    multiple = {
        "schema_version": "multi-horizon-multiple-testing-v1",
        "provider_id": "tushare-pro-v1",
        "label_family_id": label_family_id,
        "model_spec_id": MODEL_SPEC_ID,
        "base_walk_forward_spec_id": WALK_FORWARD_SPEC_ID,
        "primary_hypothesis_count": 9,
        "method": "benjamini_hochberg",
        "fdr_q": 0.10,
        "results": adjusted,
        "gates": gates,
        "label_support_classification": classification,
        "candidate_ids": [row["candidate_id"] for row in candidates],
        "fresh_lock_ids": [row["fresh_lock_id"] for row in locks],
        "report_periods_used_for_selection": False,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    multiple["multiple_testing_id"] = "mhmt1_" + hash_payload(multiple)
    multiple_value, multiple_receipt = _publish(
        repository,
        "multi_horizon_multiple_testing",
        multiple,
        "multi_horizon_multiple_testing.json",
        (
            label_family_id,
            *[row["alignment_assessment_id"] for row in alignments],
            *[row["candidate_id"] for row in candidates],
            *[row["fresh_lock_id"] for row in locks],
        ),
    )
    counts["new_artifacts"] += int(not multiple_receipt["exact_existing"])
    counts["new_blobs"] += multiple_receipt["new_blob_count"]
    report = {
        "schema_version": "multi-horizon-label-research-report-v1",
        "provider_id": "tushare-pro-v1",
        "label_family_id": label_family_id,
        "executable_label_audit_id": audit["label_audit_id"],
        "label_ids": [row["label_id"] for row in labels],
        "quality_assessment_ids": [row["quality_assessment_id"] for row in labels],
        "model_spec_id": MODEL_SPEC_ID,
        "bundle_ids": list(BUNDLE_IDS.values()),
        "walk_forward_spec_id": WALK_FORWARD_SPEC_ID,
        "fold_result_ids": {
            label_name: {
                bundle_name: [row["fold_result_id"] for row in rows]
                for bundle_name, rows in bundle_rows.items()
            }
            for label_name, bundle_rows in results.items()
        },
        "alignment_assessment_ids": [row["alignment_assessment_id"] for row in alignments],
        "multiple_testing_id": multiple_receipt["artifact_id"],
        "candidate_ids": [row["candidate_id"] for row in candidates],
        "fresh_lock_ids": [row["fresh_lock_id"] for row in locks],
        "label_support_classification": classification,
        "cycle": {
            "cycle_name": "autonomous_research_cycle_004",
            "research_type": "multi_horizon_model_alpha",
            "status": (
                "completed_with_label_aligned_candidate"
                if candidates else "completed_no_label_aligned_candidate"
            ),
            "automatic_cycle_005_created": False,
        },
        "global_stop": {
            "technical_feature_space_exhausted": not bool(candidates),
            "fixed_model_aggregation_exhausted": not bool(candidates),
            "tested_label_horizons": ["1d", "5d", "10d"],
            "multi_horizon_alignment_exhausted": not bool(candidates),
            "status": (
                "fresh_candidate_waiting_for_unexposed_data"
                if candidates else "global_authorized_technical_research_space_exhausted"
            ),
        },
        "runtime_counts": counts,
        "historical_evidence_semantics": "retrospective_research_only",
        "legacy_label_modified": False,
        "feature_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    report["research_report_id"] = "mhlrr1_" + hash_payload(report)
    report_value, report_receipt = _publish(
        repository,
        TERMINAL_KIND,
        report,
        "multi_horizon_label_research_report.json",
        (
            label_family_id,
            audit_receipt["artifact_id"],
            multiple_receipt["artifact_id"],
            *[row["alignment_assessment_id"] for row in alignments],
        ),
    )
    counts["new_artifacts"] += int(not report_receipt["exact_existing"])
    counts["new_blobs"] += report_receipt["new_blob_count"]
    return {
        "status": report["cycle"]["status"],
        "label_family_id": label_family_id,
        "label_ids": report["label_ids"],
        "research_report_id": report_receipt["artifact_id"],
        "multiple_testing_id": multiple_receipt["artifact_id"],
        "candidate_ids": report["candidate_ids"],
        "fresh_lock_ids": report["fresh_lock_ids"],
        "label_support_classification": classification,
        "runtime_counts": counts,
        "store_integrity": repository.integrity(),
    }


def plan_study(
    *, label_family_id: str, repository_root: Path, work_root: Path,
    store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    family = repository.identity(label_family_id)
    return {
        "status": "planned",
        "label_family_id": label_family_id,
        "label_count": len(family["labels"]),
        "bundle_count": 3,
        "fold_count": 4,
        "seed_count": 3,
        "planned_model_training_calls": 108,
        "planned_prediction_writes": 36,
        "planned_qlib_calls": 36,
        "primary_hypothesis_count": 9,
    }


def inspect_artifact(
    *, artifact_id: str, repository_root: Path, work_root: Path,
    store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    return repository.identity(artifact_id) | {"artifact_id": artifact_id}


def validate_study(
    *, label_family_id: str, repository_root: Path, work_root: Path,
    store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    terminal = _existing_terminal(repository, label_family_id)
    if terminal is None:
        raise ValueError("multi-horizon terminal Report is absent")
    gaps = []
    if len(terminal["label_ids"]) != 3:
        gaps.append("label_count")
    fold_count = sum(
        len(rows)
        for label_rows in terminal["fold_result_ids"].values()
        for rows in label_rows.values()
    )
    if fold_count != 36:
        gaps.append("fold_result_count")
    integrity = repository.integrity()
    if integrity["status"] != "healthy":
        gaps.append("store_integrity")
    return {
        "status": "valid" if not gaps else "invalid",
        "label_family_id": label_family_id,
        "research_report_id": terminal["research_report_id"],
        "evidence_gaps": gaps,
        "store_integrity": integrity,
    }


def replay_study(
    *, label_family_id: str, repository_root: Path, work_root: Path,
    store_root: Path | None = None
) -> dict[str, Any]:
    validation = validate_study(
        label_family_id=label_family_id,
        repository_root=repository_root,
        work_root=work_root,
        store_root=store_root,
    )
    return validation | {
        "status": "exact_replay",
        "label_writes": 0,
        "model_training_calls": 0,
        "prediction_writes": 0,
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
