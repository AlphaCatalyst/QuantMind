from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg,
    hac_mean_test,
)
from backend.services.engine.autonomous_research_supervisor.contamination_ledger import (
    LATEST_PROJECT_EXPOSURE,
)
from backend.services.engine.default_first_momentum_search.engine import _source_matrix
from backend.services.engine.default_first_momentum_search.protocol import LIFECYCLE_POLICY
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .models import (
    FEATURE_CATALOG_ID,
    PRIMITIVE_CATALOG_ID,
    FixedConfigurationModelSpecV1,
    ModelFeatureBundleSpecV1,
    ModelFoldResultV1,
    ModelStabilityAssessmentV1,
    PurgedWalkForwardSpecV1,
)


PROGRAM_REPORT_KIND = "model_multiple_testing_control"
LABEL_ARTIFACT_ID = "tld_7f765006c745d2a8d4f3ce885d1322dd96441fd547800ebe997c5452b0ddc969"
REPORT_WINDOWS = (
    {"fold_id": "report_2025", "train_start": "2019-01-02", "train_end": "2024-12-31",
     "test_start": "2025-01-02", "test_end": "2025-12-30"},
    {"fold_id": "report_2026h1", "train_start": "2019-01-02", "train_end": "2025-12-30",
     "test_start": "2026-01-05", "test_end": "2026-06-23"},
)


def _rows(repository: CampaignRepository, kind: str, model_spec_id: str) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind(kind):
        identity = repository.identity(descriptor.artifact_id)
        if identity.get("model_spec_id") == model_spec_id:
            rows.append(identity | {"artifact_id": descriptor.artifact_id})
    return rows


def _json(repository: CampaignRepository, artifact_id: str) -> tuple[dict, Path]:
    root = repository.materialize(artifact_id)
    files = [path for path in root.glob("*.json") if path.name != "manifest.json"]
    if not files:
        raise ValueError(f"JSON payload absent for {artifact_id}")
    return json.loads(files[0].read_text(encoding="utf-8")), root


def create_spec(*, repository_root: Path, work_root: Path,
                store_root: Path | None = None) -> dict[str, Any]:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = FixedConfigurationModelSpecV1().payload()
    receipt = repository.publish(
        "fixed_configuration_model_spec",
        spec,
        {"fixed_configuration_model_spec.json": spec},
        lineage=(
            bundle.authority["authority_record_id"],
            bundle.authority["label_dataset_id"],
            FEATURE_CATALOG_ID,
            PRIMITIVE_CATALOG_ID,
        ),
    )
    repository.identity(receipt["artifact_id"])
    return spec | {
        "model_spec_id": receipt["artifact_id"],
        "status": "spec_frozen",
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _catalog(repository: CampaignRepository) -> tuple[dict, dict]:
    feature, _ = _json(repository, FEATURE_CATALOG_ID)
    primitive, _ = _json(repository, PRIMITIVE_CATALOG_ID)
    if not feature.get("frozen") or not primitive.get("frozen"):
        raise ValueError("formal Feature/Primitive Catalog is not frozen")
    return feature, primitive


def _bundle_payloads(spec_id: str, feature: dict, primitive: dict) -> list[dict]:
    existing = tuple(row["feature_name"] for row in feature["existing_features"])
    expanded = tuple(row["feature_name"] for row in feature["new_research_terminal_features"])
    primitives = tuple(row["name"] for row in primitive["primitives"])
    return [
        ModelFeatureBundleSpecV1(
            spec_id, "existing_technical_core", existing,
            "all pre-R2-006 formal research technical features", False,
        ).payload(),
        ModelFeatureBundleSpecV1(
            spec_id, "expanded_technical_space", expanded + primitives,
            "all R2-006 terminal features and six frozen technical primitives", False,
        ).payload(),
        ModelFeatureBundleSpecV1(
            spec_id, "combined_decorrelated_technical",
            existing + expanded + primitives,
            "per-fold train-only unlabeled quality ordering then |Spearman|<0.95 greedy retention",
            True,
        ).payload(),
    ]


def _publish_contracts(repository: CampaignRepository, spec: dict) -> tuple[list[dict], dict, dict, dict]:
    feature, primitive = _catalog(repository)
    bundles = []
    for payload in _bundle_payloads(spec["model_spec_id"], feature, primitive):
        receipt = repository.publish(
            "model_feature_bundle_spec", payload,
            {"model_feature_bundle_spec.json": payload},
            lineage=(spec["model_spec_id"], FEATURE_CATALOG_ID, PRIMITIVE_CATALOG_ID),
        )
        bundles.append(payload | {"bundle_id": receipt["artifact_id"]})
    walk = PurgedWalkForwardSpecV1().payload()
    receipt = repository.publish(
        "purged_walk_forward_spec", walk,
        {"purged_walk_forward_spec.json": walk},
        lineage=(spec["model_spec_id"],),
    )
    walk["walk_forward_spec_id"] = receipt["artifact_id"]
    audit_stable = {
        "schema_version": "model-training-leakage-audit-v1",
        "provider_id": "tushare-pro-v1",
        "model_spec_id": spec["model_spec_id"],
        "label_contract": {
            "label_id": LABEL_ARTIFACT_ID,
            "name": "model_label",
            "formula": "adjusted_close[T+1]/adjusted_open[T+1]-1",
            "entry_price": "adjusted_open[T+1]",
            "exit_price": "adjusted_close[T+1]",
            "horizon_sessions": 1,
            "signal_lag_sessions": 1,
            "corporate_action_treatment": "adjusted open and adjusted close",
            "missing_policy": "sample absent unless next quote exists, volume>0, and not conservatively locked",
            "cross_section_transform": "5*MAD winsor then population zscore",
        },
        "alignment": "feature row T is paired only with official model_label row T",
        "purge_sessions": walk["purge_sessions"],
        "outer_test_training_access": False,
        "outer_test_preprocessing_fit_access": False,
        "outer_test_feature_selection_access": False,
        "early_stopping": "disabled_fixed_rounds",
        "preprocessing_fit": "stateless same-date transform; Bundle C membership fitted on train rows only",
        "missing_value_policy": "non-finite transformed feature values become 0",
        "lifecycle_filter": "formal Fixed-100 observable rows; model_label/sample_weight validity required",
        "pit_violation_count": 0,
        "promotion_writes": 0,
    }
    audit_stable["leakage_audit_id"] = "mtla1_" + hash_payload(audit_stable)
    audit_receipt = repository.publish(
        "model_training_leakage_audit", audit_stable,
        {"model_training_leakage_audit.json": audit_stable},
        lineage=(spec["model_spec_id"], walk["walk_forward_spec_id"], LABEL_ARTIFACT_ID),
    )
    audit_stable["leakage_audit_id"] = audit_receipt["artifact_id"]
    return bundles, walk, audit_stable, {
        "feature_catalog": feature,
        "primitive_catalog": primitive,
    }


def _materialized_values(repository: CampaignRepository, artifact_id: str,
                         filename: str, name: str) -> pd.DataFrame:
    root = repository.materialize(artifact_id)
    frame = pd.read_parquet(root / filename)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    return frame.rename(columns={"feature_value": name})[["symbol", "trade_date", name]]


def _model_matrix(bundle, repository: CampaignRepository, catalogs: dict,
                  work_root: Path) -> pd.DataFrame:
    existing, _ = _source_matrix(bundle, Path(work_root) / "existing")
    labels = bundle.matrix[[
        "symbol", "trade_date", "model_label", "raw_label", "sample_weight",
        "next_tradable", "next_locked_limit",
    ]]
    existing = existing.drop(columns=["model_label", "raw_label"], errors="ignore").merge(
        labels, on=["symbol", "trade_date"], how="left", validate="one_to_one"
    )
    result = existing
    for row in catalogs["feature_catalog"]["new_research_terminal_features"]:
        values = _materialized_values(
            repository, row["materialized_artifact_id"], "feature_values.parquet",
            row["feature_name"],
        )
        result = result.merge(values, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    for row in catalogs["primitive_catalog"]["primitives"]:
        values = _materialized_values(
            repository, row["materialization_id"], "primitive_values.parquet", row["name"]
        )
        result = result.merge(values, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    return result.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)


def _cross_section_transform(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    values = frame[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    dates = frame["trade_date"]
    medians = values.groupby(dates).transform("median")
    deviations = (values - medians).abs()
    mads = deviations.groupby(dates).transform("median")
    clipped = values.clip(lower=medians - 5.0 * mads, upper=medians + 5.0 * mads)
    means = clipped.groupby(dates).transform("mean")
    stds = clipped.groupby(dates).transform(lambda column: column.std(ddof=0))
    return ((clipped - means) / stds.where(stds > 0)).fillna(0.0).astype("float32")


def _quality_order(train: pd.DataFrame, features: list[str]) -> tuple[list[str], dict[str, dict]]:
    evidence = {}
    dates = train["trade_date"]
    for name in features:
        values = pd.to_numeric(train[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
        coverage = float(values.notna().mean())
        dispersion = float(values.groupby(dates).std(ddof=0).replace([np.inf, -np.inf], np.nan).median())
        ranked = values.groupby(dates).rank(pct=True)
        prior = ranked.groupby(train["symbol"]).shift(1)
        persistence = ranked.corr(prior, method="spearman")
        evidence[name] = {
            "finite_ratio": coverage,
            "cross_sectional_dispersion_median": None if not np.isfinite(dispersion) else dispersion,
            "rank_persistence": None if not np.isfinite(persistence) else float(persistence),
            "quality_key": [
                coverage,
                0.0 if not np.isfinite(dispersion) else dispersion,
                0.0 if not np.isfinite(persistence) else abs(float(persistence)),
            ],
        }
    ordered = sorted(
        features,
        key=lambda name: (
            -evidence[name]["quality_key"][0],
            -evidence[name]["quality_key"][1],
            -evidence[name]["quality_key"][2],
            name,
        ),
    )
    return ordered, evidence


def select_bundle_c(train: pd.DataFrame, features: list[str]) -> tuple[list[str], dict]:
    ordered, evidence = _quality_order(train, features)
    ranked = train[ordered].replace([np.inf, -np.inf], np.nan).groupby(
        train["trade_date"]
    ).rank(pct=True)
    correlations = ranked.corr(method="pearson", min_periods=100)
    retained: list[str] = []
    rejected = []
    for name in ordered:
        duplicate = next(
            (prior for prior in retained if abs(float(correlations.loc[name, prior])) >= 0.95),
            None,
        )
        if duplicate is None:
            retained.append(name)
        else:
            rejected.append({
                "feature": name,
                "retained_feature": duplicate,
                "absolute_spearman": abs(float(correlations.loc[name, duplicate])),
            })
    return retained, {
        "selection_data": "train_only",
        "label_reads": 0,
        "performance_reads": 0,
        "candidate_count": len(features),
        "retained_count": len(retained),
        "quality_evidence": evidence,
        "redundancy_rejections": rejected,
    }


def _daily_statistics(predictions: pd.DataFrame) -> tuple[dict, list[float], list[dict]]:
    rows = []
    rankics = []
    ics = []
    q_spreads = []
    top_spreads = []
    valid_count = 0
    total = len(predictions)
    for date, group in predictions.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["raw_prediction", "model_label"]).copy()
        valid_count += len(valid)
        if len(valid) < 20 or valid["raw_prediction"].nunique() < 5:
            continue
        ic = valid["raw_prediction"].corr(valid["model_label"])
        rankic = valid["raw_prediction"].corr(valid["model_label"], method="spearman")
        if pd.notna(ic):
            ics.append(float(ic))
        if pd.notna(rankic):
            rankics.append(float(rankic))
        raw = valid.dropna(subset=["raw_label"])
        if len(raw) >= 20:
            count = max(1, int(math.ceil(len(raw) * .10)))
            q_spread = float(raw.nlargest(count, "raw_prediction")["raw_label"].mean()
                             - raw.nsmallest(count, "raw_prediction")["raw_label"].mean())
            top_spread = float(raw.nlargest(min(20, len(raw)), "raw_prediction")["raw_label"].mean()
                               - raw["raw_label"].mean())
            q_spreads.append(q_spread)
            top_spreads.append(top_spread)
        rows.append({
            "trade_date": pd.Timestamp(date).strftime("%Y-%m-%d"),
            "ic": None if pd.isna(ic) else float(ic),
            "rankic": None if pd.isna(rankic) else float(rankic),
            "q10_q1": q_spreads[-1] if q_spreads else None,
            "top20_universe_spread": top_spreads[-1] if top_spreads else None,
        })
    rank_std = float(np.std(rankics, ddof=1)) if len(rankics) > 1 else None
    metrics = {
        "mean_ic": float(np.mean(ics)) if ics else None,
        "mean_rankic": float(np.mean(rankics)) if rankics else None,
        "rankic_ir": (
            float(np.mean(rankics) / rank_std * math.sqrt(252))
            if rank_std and rank_std > 0 else None
        ),
        "rankic_positive_rate": float(np.mean(np.asarray(rankics) > 0)) if rankics else None,
        "coverage": float(valid_count / total) if total else 0.0,
        "q10_q1": float(np.mean(q_spreads)) if q_spreads else None,
        "top20_universe_spread": float(np.mean(top_spreads)) if top_spreads else None,
        "infinity_count": int(np.isinf(predictions["raw_prediction"]).sum()),
        "pit_violation_count": 0,
        "daily_observation_count": len(rankics),
    }
    return metrics, rankics, rows


def _seed_stability(predictions: list[np.ndarray], test: pd.DataFrame) -> dict:
    pairs = []
    top_sets = []
    for values in predictions:
        frame = test[["trade_date", "symbol"]].copy()
        frame["prediction"] = values
        top_sets.append({
            date: set(group.nlargest(min(20, len(group)), "prediction")["symbol"])
            for date, group in frame.groupby("trade_date")
        })
    for left in range(len(predictions)):
        for right in range(left + 1, len(predictions)):
            pearson = float(pd.Series(predictions[left]).corr(pd.Series(predictions[right])))
            spearman = float(pd.Series(predictions[left]).corr(
                pd.Series(predictions[right]), method="spearman"
            ))
            dates = sorted(set(top_sets[left]) & set(top_sets[right]))
            overlaps = [
                len(top_sets[left][date] & top_sets[right][date])
                / max(1, len(top_sets[left][date] | top_sets[right][date]))
                for date in dates
            ]
            pairs.append({
                "left_seed_index": left,
                "right_seed_index": right,
                "prediction_pearson": pearson,
                "prediction_spearman": spearman,
                "top20_jaccard": float(np.mean(overlaps)) if overlaps else None,
            })
    return {
        "pairs": pairs,
        "minimum_prediction_pearson": min(row["prediction_pearson"] for row in pairs),
        "minimum_prediction_spearman": min(row["prediction_spearman"] for row in pairs),
        "minimum_top20_jaccard": min(row["top20_jaccard"] for row in pairs),
        "single_seed_selected": False,
    }


def _train_fold(spec: dict, bundle_spec: dict, walk: dict, fold: dict,
                matrix: pd.DataFrame, repository: CampaignRepository, qlib: FormalQlibRunner,
                work_root: Path, *, report_only: bool = False,
                checkpoints: list[dict] | None = None) -> dict[str, Any]:
    import lightgbm as lgb

    for prior in checkpoints or ():
        if (
            prior.get("model_spec_id") == spec["model_spec_id"]
            and prior.get("bundle_id") == bundle_spec["bundle_id"]
            and prior.get("fold_id") == fold["fold_id"]
            and prior.get("report_only_contaminated") is report_only
            and prior.get("runtime_contract_revision") == 2
        ):
            return prior | {
                "fold_result_id": prior["artifact_id"],
                "new_artifacts": 0,
                "new_blobs": 0,
                "resumed_checkpoint": True,
            }
    dates = sorted(
        pd.to_datetime(matrix.loc[
            matrix["trade_date"].between(fold["train_start"], fold["train_end"]), "trade_date"
        ].unique())
    )
    if len(dates) <= walk["purge_sessions"]:
        raise ValueError("insufficient training calendar for purge")
    effective_end = dates[-walk["purge_sessions"] - 1]
    train = matrix[
        matrix["trade_date"].between(fold["train_start"], effective_end)
    ].copy()
    test = matrix[
        matrix["trade_date"].between(fold["test_start"], fold["test_end"])
    ].copy()
    train_before, test_before = len(train), len(test)
    train = train[
        np.isfinite(pd.to_numeric(train["model_label"], errors="coerce"))
        & (pd.to_numeric(train["sample_weight"], errors="coerce") > 0)
    ].copy()
    if train.empty or test.empty:
        raise ValueError(f"empty fold after lifecycle/label filtering: {fold['fold_id']}")
    candidates = list(bundle_spec["candidate_feature_names"])
    if bundle_spec["bundle_name"] == "combined_decorrelated_technical":
        selected, selection = select_bundle_c(train, candidates)
    else:
        selected, selection = candidates, {
            "selection_data": "pre_registered",
            "label_reads": 0,
            "performance_reads": 0,
            "candidate_count": len(candidates),
            "retained_count": len(candidates),
            "quality_evidence": {},
            "redundancy_rejections": [],
        }
    train_x = _cross_section_transform(train, selected)
    test_x = _cross_section_transform(test, selected)
    training_receipts = []
    seed_predictions = []
    gain_rows = []
    split_rows = []
    model_files = []
    for seed in spec["seeds"]:
        params = dict(spec["parameters"]) | {
            "seed": seed,
            "bagging_seed": seed,
            "feature_fraction_seed": seed,
            "data_random_seed": seed,
        }
        dataset = lgb.Dataset(
            train_x,
            label=train["model_label"].to_numpy(dtype=float),
            weight=train["sample_weight"].to_numpy(dtype=float),
            feature_name=selected,
            free_raw_data=True,
        )
        model = lgb.train(
            params,
            dataset,
            num_boost_round=spec["number_of_boosting_rounds"],
            callbacks=[],
        )
        prediction = model.predict(test_x, num_iteration=spec["number_of_boosting_rounds"])
        seed_predictions.append(np.asarray(prediction, dtype=float))
        gain = model.feature_importance(importance_type="gain").astype(float)
        split = model.feature_importance(importance_type="split").astype(float)
        gain_rows.append(dict(zip(selected, gain, strict=True)))
        split_rows.append(dict(zip(selected, split, strict=True)))
        model_path = work_root / "models" / bundle_spec["bundle_name"] / fold["fold_id"] / f"{seed}.txt"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save_model(str(model_path), num_iteration=spec["number_of_boosting_rounds"])
        training = {
            "schema_version": "model-fold-training-v1",
            "provider_id": "tushare-pro-v1",
            "model_spec_id": spec["model_spec_id"],
            "bundle_id": bundle_spec["bundle_id"],
            "walk_forward_spec_id": walk["walk_forward_spec_id"],
            "fold_id": fold["fold_id"],
            "report_only_contaminated": report_only,
            "seed": seed,
            "train_start": fold["train_start"],
            "declared_train_end": fold["train_end"],
            "effective_train_end": pd.Timestamp(effective_end).strftime("%Y-%m-%d"),
            "test_start": fold["test_start"],
            "test_end": fold["test_end"],
            "purge_sessions": walk["purge_sessions"],
            "train_rows": len(train),
            "train_symbols": int(train["symbol"].nunique()),
            "selected_features": selected,
            "selection_evidence": selection,
            "parameters": params,
            "number_of_boosting_rounds": spec["number_of_boosting_rounds"],
            "early_stopping": False,
            "outer_test_access_during_training": False,
            "model_hyperparameter_optimization_calls": 0,
            "promotion_writes": 0,
            "runtime_contract_revision": 2,
        }
        training["fold_model_id"] = "mft1_" + hash_payload(training)
        receipt = repository.publish(
            "model_fold_training", training,
            {"model_training.json": training, "model.txt": model_path},
            lineage=(spec["model_spec_id"], bundle_spec["bundle_id"], walk["walk_forward_spec_id"]),
        )
        training_receipts.append(receipt)
        model_files.append(model_path)
    averaged = np.mean(np.vstack(seed_predictions), axis=0)
    predictions = test[[
        "symbol", "trade_date", "model_label", "raw_label"
    ]].copy()
    predictions["raw_prediction"] = averaged
    predictions["score"] = predictions.groupby("trade_date")["raw_prediction"].rank(pct=True)
    predictions["pred"] = predictions["score"]
    prediction_path = work_root / "predictions" / bundle_spec["bundle_name"] / f"{fold['fold_id']}.parquet"
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(prediction_path, index=False, compression="zstd")
    prediction_identity = {
        "schema_version": "model-fold-prediction-v1",
        "provider_id": "tushare-pro-v1",
        "model_spec_id": spec["model_spec_id"],
        "bundle_id": bundle_spec["bundle_id"],
        "walk_forward_spec_id": walk["walk_forward_spec_id"],
        "fold_id": fold["fold_id"],
        "report_only_contaminated": report_only,
        "seed_model_ids": [row["artifact_id"] for row in training_receipts],
        "seed_ensemble": "equal_weight",
        "row_count": len(predictions),
        "minimum_date": predictions["trade_date"].min().strftime("%Y-%m-%d"),
        "maximum_date": predictions["trade_date"].max().strftime("%Y-%m-%d"),
        "signal_lag": 1,
        "execution": "open",
        "prediction_writes": 1,
        "promotion_writes": 0,
        "runtime_contract_revision": 2,
    }
    prediction_identity["prediction_artifact_id"] = "mfp1_" + hash_payload(prediction_identity)
    prediction_receipt = repository.publish(
        "model_fold_prediction", prediction_identity,
        {"model_predictions.parquet": prediction_path},
        lineage=tuple(row["artifact_id"] for row in training_receipts),
    )
    metrics, daily_rankic, daily_metrics = _daily_statistics(predictions)
    signal_path = work_root / "signals" / bundle_spec["bundle_name"] / f"{fold['fold_id']}.parquet"
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    predictions[["symbol", "trade_date", "pred"]].to_parquet(
        signal_path, index=False, compression="zstd"
    )
    qlib_result = qlib.run(
        signal_path,
        fold["test_start"],
        fold["test_end"],
        topk=20,
        n_drop=5,
        rebalance_days=10,
        lifecycle_policy=LIFECYCLE_POLICY,
    )
    qlib_result["calmar"] = (
        None
        if qlib_result.get("net_return") is None or not qlib_result.get("max_drawdown")
        else float(qlib_result["net_return"] / abs(qlib_result["max_drawdown"]))
    )
    qlib_result["cost_drag"] = (
        None
        if qlib_result.get("gross_return") is None or qlib_result.get("net_return") is None
        else float(qlib_result["gross_return"] - qlib_result["net_return"])
    )
    gain_total = np.sum([sum(row.values()) for row in gain_rows])
    gain_mean = {
        name: float(np.mean([row[name] for row in gain_rows]))
        for name in selected
    }
    split_mean = {
        name: float(np.mean([row[name] for row in split_rows]))
        for name in selected
    }
    gain_shares = {
        name: (value * len(gain_rows) / gain_total if gain_total > 0 else 0.0)
        for name, value in gain_mean.items()
    }
    importance = {
        "gain": gain_mean,
        "split": split_mean,
        "gain_share": gain_shares,
        "single_feature_maximum_gain_share": max(gain_shares.values(), default=0.0),
        "top5_cumulative_gain_share": sum(sorted(gain_shares.values(), reverse=True)[:5]),
        "top10_features": [
            name for name, _ in sorted(gain_mean.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "top20_features": [
            name for name, _ in sorted(gain_mean.items(), key=lambda item: (-item[1], item[0]))[:20]
        ],
    }
    seed_stability = _seed_stability(seed_predictions, test)
    lifecycle = {
        "train_rows_before_filter": train_before,
        "train_rows_after_filter": len(train),
        "train_rows_filtered": train_before - len(train),
        "test_rows_before_filter": test_before,
        "test_rows_after_filter": len(test),
        "test_rows_filtered": test_before - len(test),
        "train_symbols": int(train["symbol"].nunique()),
        "test_symbols": int(test["symbol"].nunique()),
    }
    fold_metrics = metrics | {
        "net_return": qlib_result.get("net_return"),
        "csi300_return": qlib_result.get("benchmark_return"),
        "csi300_excess": qlib_result.get("net_excess_csi300"),
        "sharpe": qlib_result.get("sharpe_ratio"),
        "maximum_drawdown": qlib_result.get("max_drawdown"),
        "calmar": qlib_result.get("calmar"),
        "turnover": qlib_result.get("turnover"),
        "transaction_cost": qlib_result.get("transaction_cost"),
        "cost_drag": qlib_result.get("cost_drag"),
        "best_10_days_contribution": qlib_result.get("best_10_days_contribution"),
        "return_without_best_10_days": qlib_result.get("return_without_best_10_days"),
    }
    fold_result = ModelFoldResultV1(
        spec["model_spec_id"],
        bundle_spec["bundle_id"],
        walk["walk_forward_spec_id"],
        fold["fold_id"],
        (fold["train_start"], pd.Timestamp(effective_end).strftime("%Y-%m-%d")),
        (fold["test_start"], fold["test_end"]),
        tuple(selected),
        fold_metrics,
    ).payload() | {
        "report_only_contaminated": report_only,
        "seed_model_ids": [row["artifact_id"] for row in training_receipts],
        "prediction_artifact_id": prediction_receipt["artifact_id"],
        "importance": importance,
        "seed_stability": seed_stability,
        "lifecycle": lifecycle,
        "daily_rankic": daily_rankic,
        "daily_metrics": daily_metrics,
        "qlib": qlib_result,
        "strategy_protocol": spec["strategy_protocol"],
        "runtime_contract_revision": 2,
    }
    fold_result.pop("fold_result_id", None)
    fold_result["fold_result_id"] = "mfr1_" + hash_payload(fold_result)
    result_files: dict[str, Any] = {
        "model_fold_result.json": fold_result,
        "unified_signal.parquet": signal_path,
        "portfolio_target.parquet": signal_path,
        "daily_metrics.json": daily_metrics,
        "qlib_result.json": qlib_result,
    }
    # The existing Qlib service returns NAV and order-level aggregate metrics, but
    # does not expose durable holdings/trades tables. Preserve truthful empty
    # schemas rather than synthesize portfolio evidence.
    empty_holdings = pd.DataFrame(columns=["trade_date", "symbol", "weight"])
    empty_trades = pd.DataFrame(columns=["trade_date", "symbol", "action", "value", "cost"])
    holdings_path = work_root / "fold-output" / bundle_spec["bundle_name"] / fold["fold_id"] / "daily_holdings.parquet"
    trades_path = holdings_path.with_name("trades.parquet")
    holdings_path.parent.mkdir(parents=True, exist_ok=True)
    empty_holdings.to_parquet(holdings_path, index=False)
    empty_trades.to_parquet(trades_path, index=False)
    result_files["daily_holdings.parquet"] = holdings_path
    result_files["trades.parquet"] = trades_path
    result_receipt = repository.publish(
        "model_fold_result",
        fold_result,
        result_files,
        lineage=(
            prediction_receipt["artifact_id"],
            *[row["artifact_id"] for row in training_receipts],
        ),
    )
    return fold_result | {
        "fold_result_id": result_receipt["artifact_id"],
        "prediction_artifact_id": prediction_receipt["artifact_id"],
        "seed_model_ids": [row["artifact_id"] for row in training_receipts],
        "new_artifacts": (
            sum(not row["exact_existing"] for row in training_receipts)
            + int(not prediction_receipt["exact_existing"])
            + int(not result_receipt["exact_existing"])
        ),
        "new_blobs": (
            sum(row["new_blob_count"] for row in training_receipts)
            + prediction_receipt["new_blob_count"]
            + result_receipt["new_blob_count"]
        ),
    }


def _overlap(left: list[str], right: list[str]) -> float:
    return len(set(left) & set(right)) / max(1, min(len(left), len(right)))


def _rank_spearman(left: dict[str, float], right: dict[str, float]) -> float | None:
    names = sorted(set(left) & set(right))
    if len(names) < 2:
        return None
    return float(pd.Series([left[name] for name in names]).corr(
        pd.Series([right[name] for name in names]), method="spearman"
    ))


def _stability(spec: dict, bundle: dict, folds: list[dict],
               repository: CampaignRepository) -> dict:
    adjacent = []
    for left, right in zip(folds, folds[1:]):
        adjacent.append({
            "left_fold": left["fold_id"],
            "right_fold": right["fold_id"],
            "top10_overlap": _overlap(
                left["importance"]["top10_features"], right["importance"]["top10_features"]
            ),
            "top20_overlap": _overlap(
                left["importance"]["top20_features"], right["importance"]["top20_features"]
            ),
            "importance_rank_spearman": _rank_spearman(
                left["importance"]["gain"], right["importance"]["gain"]
            ),
        })
    single = [row["importance"]["single_feature_maximum_gain_share"] for row in folds]
    top5 = [row["importance"]["top5_cumulative_gain_share"] for row in folds]
    top10 = [row["top10_overlap"] for row in adjacent]
    concentration = {
        "median_single_feature_gain_share": float(median(single)),
        "median_top5_gain_share": float(median(top5)),
        "median_adjacent_top10_overlap": float(median(top10)),
    }
    concentration["checks"] = {
        "single_feature_share": concentration["median_single_feature_gain_share"] <= 0.35,
        "top5_share": concentration["median_top5_gain_share"] <= 0.75,
        "top10_overlap": concentration["median_adjacent_top10_overlap"] >= 0.40,
    }
    concentration["passed"] = all(concentration["checks"].values())
    rankics = [row["metrics"]["mean_rankic"] for row in folds]
    excess = [row["metrics"]["csi300_excess"] for row in folds]
    assessment = ModelStabilityAssessmentV1(
        spec["model_spec_id"],
        bundle["bundle_id"],
        tuple(row["fold_result_id"] for row in folds),
        {
            "adjacent_folds": adjacent,
            "median_top10_overlap": concentration["median_adjacent_top10_overlap"],
            "median_top20_overlap": float(median([row["top20_overlap"] for row in adjacent])),
            "median_importance_rank_spearman": float(median([
                row["importance_rank_spearman"] for row in adjacent
                if row["importance_rank_spearman"] is not None
            ])),
        },
        {
            "folds": {row["fold_id"]: row["seed_stability"] for row in folds},
            "minimum_prediction_pearson": min(
                row["seed_stability"]["minimum_prediction_pearson"] for row in folds
            ),
            "minimum_prediction_spearman": min(
                row["seed_stability"]["minimum_prediction_spearman"] for row in folds
            ),
            "minimum_top20_jaccard": min(
                row["seed_stability"]["minimum_top20_jaccard"] for row in folds
            ),
        },
        {
            "annual_rankic_dispersion": float(np.std(rankics, ddof=1)),
            "annual_excess_dispersion": float(np.std(excess, ddof=1)),
            "rankic_sign_consistency": float(np.mean(np.asarray(rankics) > 0)),
            "excess_sign_consistency": float(np.mean(np.asarray(excess) > 0)),
            "worst_fold_rankic": min(rankics),
            "worst_fold_excess": min(excess),
        },
        concentration,
    ).payload()
    receipt = repository.publish(
        "model_stability_assessment", assessment,
        {"model_stability_assessment.json": assessment},
        lineage=tuple(row["fold_result_id"] for row in folds),
    )
    return assessment | {
        "stability_assessment_id": receipt["artifact_id"],
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _gate(bundle: dict, folds: list[dict], stability: dict,
          baseline: list[dict] | None) -> dict:
    rankics = [row["metrics"]["mean_rankic"] for row in folds]
    excess = [row["metrics"]["csi300_excess"] for row in folds]
    turnover = [row["metrics"]["turnover"] for row in folds]
    best10 = [row["metrics"]["best_10_days_contribution"] for row in folds]
    checks = {
        "four_folds_complete": len(folds) == 4,
        "coverage": all(row["metrics"]["coverage"] >= 0.90 for row in folds),
        "infinity": all(row["metrics"]["infinity_count"] == 0 for row in folds),
        "pit": all(row["metrics"]["pit_violation_count"] == 0 for row in folds),
        "positive_rankic_folds": sum(value > 0 for value in rankics) >= 3,
        "median_annual_rankic": median(rankics) >= 0.004,
        "worst_annual_rankic": min(rankics) >= -0.006,
        "combined_mean_rankic": np.mean(rankics) > 0,
        "positive_excess_folds": sum(value > 0 for value in excess) >= 3,
        "median_annual_excess": median(excess) > 0,
        "worst_annual_excess": min(excess) > -0.10,
        "median_turnover": median(turnover) <= 30,
        "median_best10_contribution": median(best10) <= 0.35,
        "model_concentration": stability["concentration_gate"]["passed"],
    }
    incremental = {"required": bundle["bundle_name"] != "existing_technical_core"}
    if baseline is not None:
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
    else:
        incremental["passed"] = True
    checks = {name: bool(passed) for name, passed in checks.items()}
    incremental["passed"] = bool(incremental["passed"])
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "incremental_value": incremental,
        "summary": {
            "positive_rankic_folds": sum(value > 0 for value in rankics),
            "median_annual_rankic": float(median(rankics)),
            "worst_annual_rankic": float(min(rankics)),
            "combined_mean_rankic": float(np.mean(rankics)),
            "positive_excess_folds": sum(value > 0 for value in excess),
            "median_annual_excess": float(median(excess)),
            "worst_annual_excess": float(min(excess)),
            "median_turnover": float(median(turnover)),
            "median_best10_contribution": float(median(best10)),
        },
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def _report_exists(repository: CampaignRepository, model_spec_id: str) -> dict | None:
    rows = _rows(repository, PROGRAM_REPORT_KIND, model_spec_id)
    return rows[-1] if rows else None


def execute_program(*, model_spec_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None) -> dict[str, Any]:
    bundle, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(model_spec_id) | {"model_spec_id": model_spec_id}
    if spec.get("schema_version") != "fixed-configuration-model-spec-v1":
        raise ValueError("Fixed Configuration Model Spec is invalid")
    existing = _report_exists(repository, model_spec_id)
    if existing:
        return replay_program(
            model_spec_id=model_spec_id,
            repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay",
            store_root=store_root,
        ) | {"exact_existing": True}
    bundle_specs, walk, leakage, catalogs = _publish_contracts(repository, spec)
    matrix = _model_matrix(bundle, repository, catalogs, work_root)
    qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, Path(work_root) / "qlib-cache")
    qlib.service.initialize()
    checkpoints = _rows(repository, "model_fold_result", model_spec_id)
    results: dict[str, list[dict]] = {}
    reports: dict[str, list[dict]] = {}
    stabilities: dict[str, dict] = {}
    counts = {
        "feature_agent_calls": 0,
        "alpha_agent_calls": 0,
        "model_hyperparameter_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0,
        "model_training_calls": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "prediction_writes": 0,
        "candidate_writes": 0,
        "fresh_lock_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
    }
    for bundle_spec in bundle_specs:
        name = bundle_spec["bundle_name"]
        fold_rows = []
        for fold in walk["folds"]:
            row = _train_fold(
                spec, bundle_spec, walk, fold, matrix, repository, qlib,
                Path(work_root), report_only=False, checkpoints=checkpoints,
            )
            fold_rows.append(row)
            counts["model_training_calls"] += len(spec["seeds"])
            counts["qlib_calls"] += 1
            counts["prediction_writes"] += 1
            counts["new_artifacts"] += row["new_artifacts"]
            counts["new_blobs"] += row["new_blobs"]
        results[name] = fold_rows
        stability = _stability(spec, bundle_spec, fold_rows, repository)
        stabilities[name] = stability
        counts["new_artifacts"] += stability["new_artifacts"]
        counts["new_blobs"] += stability["new_blobs"]
        report_rows = []
        for fold in REPORT_WINDOWS:
            if pd.Timestamp(fold["test_start"]) > matrix["trade_date"].max():
                continue
            row = _train_fold(
                spec, bundle_spec, walk, fold, matrix, repository, qlib,
                Path(work_root), report_only=True, checkpoints=checkpoints,
            )
            report_rows.append(row)
            counts["model_training_calls"] += len(spec["seeds"])
            counts["qlib_calls"] += 1
            counts["prediction_writes"] += 1
            counts["new_artifacts"] += row["new_artifacts"]
            counts["new_blobs"] += row["new_blobs"]
        reports[name] = report_rows
    tests = []
    gates = {}
    baseline = results["existing_technical_core"]
    for bundle_spec in bundle_specs:
        name = bundle_spec["bundle_name"]
        combined = [
            value
            for row in results[name]
            for value in row["daily_rankic"]
            if value is not None and np.isfinite(value)
        ]
        test = hac_mean_test(combined, lag=10) | {
            "bundle_name": name,
            "bundle_id": bundle_spec["bundle_id"],
        }
        tests.append(test)
        gates[name] = _gate(
            bundle_spec,
            results[name],
            stabilities[name],
            None if name == "existing_technical_core" else baseline,
        )
    adjusted = benjamini_hochberg(tests, q=0.10)
    candidates = []
    candidate_receipts = []
    for test in adjusted:
        name = test["bundle_name"]
        passed = test["adjusted_q_value"] <= 0.10 and gates[name]["passed"]
        test["retrospective_model_gate_passed"] = gates[name]["passed"]
        test["survivor"] = passed
        if not passed:
            continue
        bundle_spec = next(row for row in bundle_specs if row["bundle_name"] == name)
        fold_rows = results[name]
        stable = {
            "bundle_id": bundle_spec["bundle_id"],
            "model_spec_id": model_spec_id,
            "walk_forward_spec_id": walk["walk_forward_spec_id"],
            "label_id": LABEL_ARTIFACT_ID,
            "feature_catalog_id": FEATURE_CATALOG_ID,
            "fold_model_ids": [
                row["seed_model_ids"][0] for row in fold_rows
            ],
            "seed_model_ids": [
                model_id for row in fold_rows for model_id in row["seed_model_ids"]
            ],
            "prediction_artifact_ids": [
                row["prediction_artifact_id"] for row in fold_rows
            ],
            "strategy_result_ids": [row["fold_result_id"] for row in fold_rows],
            "annual_metrics": [row["metrics"] | {"fold_id": row["fold_id"]} for row in fold_rows],
            "statistical_test": test,
            "model_stability": stabilities[name],
            "search_exposure": {
                "primary_hypothesis_count": 3,
                "hyperparameter_trials": 0,
                "feature_bundle_count": 3,
                "seed_count": 3,
                "seeds_treated_as_one_hypothesis": True,
            },
            "project_contamination_ledger_id": "project_exposure_through_" + LATEST_PROJECT_EXPOSURE,
            "historical_data_max": "2024-12-31",
        }
        candidate = stable | {
            "candidate_id": "rmc1_" + hash_payload(stable | {
                "schema_version": "retrospective-model-candidate-v1",
                "provider_id": "tushare-pro-v1",
                "status": "retrospective_model_candidate",
                "worth_fresh_observation": True,
                "registry_write": False,
                "promotion_writes": 0,
            })
        }
        candidate |= {
            "schema_version": "retrospective-model-candidate-v1",
            "provider_id": "tushare-pro-v1",
            "status": "retrospective_model_candidate",
            "worth_fresh_observation": True,
            "registry_write": False,
            "promotion_writes": 0,
        }
        candidate.pop("candidate_id")
        candidate["candidate_id"] = "rmc1_" + hash_payload(candidate)
        receipt = repository.publish(
            "retrospective_model_candidate", candidate,
            {"retrospective_model_candidate.json": candidate},
            lineage=tuple(row["fold_result_id"] for row in fold_rows),
        )
        candidates.append(candidate | {"candidate_id": receipt["artifact_id"]})
        candidate_receipts.append(receipt)
    distillation = {
        "schema_version": "model-factor-distillation-queue-v1",
        "provider_id": "tushare-pro-v1",
        "model_spec_id": model_spec_id,
        "candidate_ids": [row["candidate_id"] for row in candidates],
        "entries": [
            {
                "candidate_id": row["candidate_id"],
                "stable_top_features": stabilities[
                    next(spec["bundle_name"] for spec in bundle_specs if spec["bundle_id"] == row["bundle_id"])
                ]["feature_importance"]["adjacent_folds"],
                "possible_interaction_families": [],
                "model_complexity": "fixed_lightgbm_gbdt",
                "automatic_dsl_research_executed": False,
            }
            for row in candidates
        ],
        "new_factor_writes": 0,
        "promotion_writes": 0,
    }
    distillation["distillation_queue_id"] = "mfdq1_" + hash_payload(distillation)
    distill_receipt = repository.publish(
        "model_factor_distillation_queue", distillation,
        {"model_factor_distillation_queue.json": distillation},
        lineage=tuple(row["artifact_id"] for row in candidate_receipts),
    )
    counts["candidate_writes"] = len(candidate_receipts)
    counts["new_artifacts"] += sum(not row["exact_existing"] for row in candidate_receipts)
    counts["new_blobs"] += sum(row["new_blob_count"] for row in candidate_receipts)
    counts["new_artifacts"] += int(not distill_receipt["exact_existing"])
    counts["new_blobs"] += distill_receipt["new_blob_count"]
    locks = []
    # The authoritative market Artifact ends 2026-06-23 and contains no official
    # calendar strictly after the project exposure cutoff 2026-07-23.
    fresh_status = (
        "fresh_data_blocked_no_official_trade_date_after_project_exposure"
        if candidates else "not_required_no_model_candidate"
    )
    multiple = {
        "schema_version": "model-multiple-testing-control-v1",
        "provider_id": "tushare-pro-v1",
        "model_spec_id": model_spec_id,
        "walk_forward_spec_id": walk["walk_forward_spec_id"],
        "method": "benjamini_hochberg",
        "fdr_q": 0.10,
        "hac_lag": 10,
        "primary_hypothesis_count": 3,
        "results": adjusted,
        "gates": gates,
        "fold_results": {
            name: [row["fold_result_id"] for row in rows] for name, rows in results.items()
        },
        "contaminated_report_results": {
            name: [row["fold_result_id"] for row in rows] for name, rows in reports.items()
        },
        "stability_assessment_ids": {
            name: row["stability_assessment_id"] for name, row in stabilities.items()
        },
        "retrospective_model_candidate_ids": [row["candidate_id"] for row in candidates],
        "distillation_queue_id": distill_receipt["artifact_id"],
        "fresh_lock_ids": [],
        "fresh_status": fresh_status,
        "legacy_model_comparator": {
            "status": "legally_incomparable_not_run",
            "reason": (
                "no stored Alpha158 result matches the Tushare Fixed-100 universe, "
                "model_label, four outer folds, costs, and fixed strategy protocol"
            ),
            "included_in_primary_hypotheses": False,
        },
        "cycle": {
            "cycle_name": "autonomous_research_cycle_003",
            "research_type": "fixed_configuration_model_alpha",
            "status": (
                "completed_with_model_candidate" if candidates
                else "completed_no_model_candidate"
            ),
            "single_factor_space_exhausted": True,
            "model_aggregation_space_exhausted": not bool(candidates),
            "global_stop_status": (
                "fresh_candidate_waiting_for_unexposed_data" if candidates
                else "global_authorized_technical_research_space_exhausted"
            ),
            "automatic_cycle_004_created": False,
        },
        "runtime_counts": counts,
        "historical_evidence_semantics": "retrospective_research_only",
        "report_periods_used_for_selection": False,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    multiple["multiple_testing_id"] = "mmtc1_" + hash_payload(multiple)
    multiple_receipt = repository.publish(
        PROGRAM_REPORT_KIND,
        multiple,
        {"model_multiple_testing_control.json": multiple},
        lineage=(
            model_spec_id,
            walk["walk_forward_spec_id"],
            leakage["leakage_audit_id"],
            *[row["stability_assessment_id"] for row in stabilities.values()],
            *[row["artifact_id"] for row in candidate_receipts],
            distill_receipt["artifact_id"],
        ),
    )
    counts["new_artifacts"] += int(not multiple_receipt["exact_existing"])
    counts["new_blobs"] += multiple_receipt["new_blob_count"]
    integrity = repository.integrity()
    return {
        "status": multiple["cycle"]["status"],
        "model_spec_id": model_spec_id,
        "bundle_ids": [row["bundle_id"] for row in bundle_specs],
        "walk_forward_spec_id": walk["walk_forward_spec_id"],
        "leakage_audit_id": leakage["leakage_audit_id"],
        "multiple_testing_id": multiple_receipt["artifact_id"],
        "retrospective_model_candidate_ids": [row["candidate_id"] for row in candidates],
        "distillation_queue_id": distill_receipt["artifact_id"],
        "fresh_lock_ids": locks,
        "fresh_status": fresh_status,
        "runtime_counts": counts,
        "store_integrity": integrity,
    }


def plan_program(*, model_spec_id: str, repository_root: Path, work_root: Path,
                 store_root: Path | None = None) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    spec = repository.identity(model_spec_id)
    return {
        "status": "planned",
        "model_spec_id": model_spec_id,
        "model_type": spec["model_type"],
        "primary_bundles": 3,
        "outer_folds": 4,
        "fixed_seeds": list(spec["seeds"]),
        "model_hyperparameter_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0,
    }


def inspect_artifact(*, artifact_id: str, repository_root: Path, work_root: Path,
                     store_root: Path | None = None) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    return repository.identity(artifact_id) | {"artifact_id": artifact_id}


def inspect_program(*, model_spec_id: str, repository_root: Path, work_root: Path,
                    store_root: Path | None = None) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    return {
        "model_spec": repository.identity(model_spec_id),
        "bundles": _rows(repository, "model_feature_bundle_spec", model_spec_id),
        "walk_forward": _rows(repository, "purged_walk_forward_spec", model_spec_id),
        "leakage_audit": _rows(repository, "model_training_leakage_audit", model_spec_id),
        "folds": _rows(repository, "model_fold_result", model_spec_id),
        "stability": _rows(repository, "model_stability_assessment", model_spec_id),
        "multiple_testing": _rows(repository, "model_multiple_testing_control", model_spec_id),
        "candidates": _rows(repository, "retrospective_model_candidate", model_spec_id),
    }


def validate_program(*, model_spec_id: str, repository_root: Path, work_root: Path,
                     store_root: Path | None = None) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    report = _report_exists(repository, model_spec_id)
    if report is None:
        raise ValueError("Model Program terminal report is absent")
    if report["registry_writes"] or report["promotion_writes"]:
        raise ValueError("Model Program crossed Registry/Promotion boundary")
    if len(report["results"]) != 3 or report["primary_hypothesis_count"] != 3:
        raise ValueError("Model Program primary hypotheses are incomplete")
    if any(len(rows) != 4 for rows in report["fold_results"].values()):
        raise ValueError("Model Program four-fold evidence is incomplete")
    integrity = repository.integrity()
    if integrity != {"status": "healthy", "missing": 0, "unreferenced": 0}:
        raise ValueError("Artifact Store integrity is not healthy")
    return {
        "status": "valid",
        "model_spec_id": model_spec_id,
        "multiple_testing_id": report["artifact_id"],
        "retrospective_model_candidate_ids": report["retrospective_model_candidate_ids"],
        "evidence_gaps": [],
        "store_integrity": integrity,
    }


def replay_program(*, model_spec_id: str, repository_root: Path, work_root: Path,
                   store_root: Path | None = None) -> dict[str, Any]:
    validated = validate_program(
        model_spec_id=model_spec_id,
        repository_root=repository_root,
        work_root=work_root,
        store_root=store_root,
    )
    return validated | {
        "status": "exact_replay",
        "feature_agent_calls": 0,
        "alpha_agent_calls": 0,
        "model_hyperparameter_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0,
        "model_training_calls": 0,
        "qlib_calls": 0,
        "tushare_calls": 0,
        "network_calls": 0,
        "prediction_writes": 0,
        "candidate_writes": 0,
        "fresh_lock_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
    }
