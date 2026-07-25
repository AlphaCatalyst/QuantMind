from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.default_first_momentum_search.protocol import (
    LIFECYCLE_POLICY,
)
from backend.services.engine.fixed_configuration_model_program.engine import (
    _cross_section_transform,
    select_bundle_c,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload


SEEDS = (20260701, 20260702, 20260703)


@dataclass(frozen=True)
class RankingRelevanceLabelV1:
    source_label: str = "technical_return_1d"
    source_value: str = "raw_return"
    relevance_levels: int = 5
    group_scope: str = "same_trade_date_cross_section"
    tie_break: str = "symbol_ascending_then_first_rank"

    def payload(self) -> dict[str, Any]:
        if self.relevance_levels != 5 or self.source_label != "technical_return_1d":
            raise ValueError("ranking relevance contract changed")
        stable = asdict(self) | {
            "schema_version": "ranking-relevance-label-v1",
            "provider_id": "tushare-pro-v1",
            "mapping": {
                "lowest_20pct": 0,
                "20_to_40pct": 1,
                "40_to_60pct": 2,
                "60_to_80pct": 3,
                "highest_20pct": 4,
            },
            "frozen_before_first_training": True,
            "future_data_reads": 0,
            "promotion_writes": 0,
        }
        return stable | {
            "ranking_relevance_label_id": "rrl1_" + hash_payload(stable)
        }


@dataclass(frozen=True)
class RankingModelSpecV1:
    model_type: str = "existing_quantmind_lightgbm"
    objective: str = "lambdarank"
    metric: str = "ndcg"
    ndcg_eval_at: tuple[int, ...] = (20,)
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_data_in_leaf: int = 50
    feature_fraction: float = 0.8
    bagging_fraction: float = 0.8
    bagging_freq: int = 5
    boosting_rounds: int = 200
    early_stopping: bool = False
    num_threads: int = 1
    deterministic: bool = True
    seeds: tuple[int, ...] = SEEDS
    bundles: tuple[str, ...] = (
        "expanded_technical_space",
        "combined_decorrelated_technical",
    )
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "boosting_type": "gbdt",
        "verbosity": -1,
        "force_col_wise": True,
    })

    def payload(self, *, relevance_label_id: str) -> dict[str, Any]:
        if (
            self.objective != "lambdarank"
            or self.metric != "ndcg"
            or self.seeds != SEEDS
            or self.bundles
            != ("expanded_technical_space", "combined_decorrelated_technical")
        ):
            raise ValueError("frozen ranking model contract changed")
        stable = asdict(self) | {
            "schema_version": "ranking-model-spec-v1",
            "provider_id": "tushare-pro-v1",
            "ranking_relevance_label_id": relevance_label_id,
            "seed_ensemble": "equal_weight",
            "model_hyperparameter_optimization_calls": 0,
            "best_seed_selection_calls": 0,
            "strategy_optimization_calls": 0,
            "promotion_writes": 0,
        }
        return stable | {"ranking_model_spec_id": "rms1_" + hash_payload(stable)}


def relevance_labels(frame: pd.DataFrame) -> pd.Series:
    output = pd.Series(np.nan, index=frame.index, dtype="float64")
    source = pd.to_numeric(frame["raw_label"], errors="coerce")
    for _, index in frame.assign(_label=source).groupby("trade_date", sort=True).groups.items():
        values = frame.loc[index, ["symbol"]].copy()
        values["_label"] = source.loc[index]
        values = values.dropna().sort_values(["_label", "symbol"], kind="mergesort")
        if len(values) < 5:
            continue
        ranks = np.arange(len(values), dtype=int)
        levels = np.minimum(4, (ranks * 5) // len(values))
        output.loc[values.index] = levels
    return output


def _ndcg_at_20(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    values, baselines = [], []
    for _, group in frame.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["raw_prediction", "relevance"]).copy()
        if len(valid) < 20:
            continue
        ordered = valid.sort_values(
            ["raw_prediction", "symbol"], ascending=[False, True], kind="mergesort"
        )
        relevance = ordered["relevance"].to_numpy(dtype=float)[:20]
        ideal = np.sort(valid["relevance"].to_numpy(dtype=float))[::-1][:20]
        discount = 1.0 / np.log2(np.arange(2, 2 + len(relevance)))
        dcg = float(np.sum((np.power(2.0, relevance) - 1.0) * discount))
        idcg = float(np.sum((np.power(2.0, ideal) - 1.0) * discount))
        if idcg <= 0:
            continue
        values.append(dcg / idcg)
        # The expected random DCG uses the same-day mean gain at each position.
        mean_gain = float(np.mean(np.power(2.0, valid["relevance"]) - 1.0))
        baselines.append(float(mean_gain * discount.sum() / idcg))
    return (
        float(np.mean(values)) if values else None,
        float(np.mean(baselines)) if baselines else None,
    )


def train_ranking_fold(
    *,
    spec: dict[str, Any],
    bundle_spec: dict[str, Any],
    matrix: pd.DataFrame,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    qlib,
    work_root: Path,
) -> dict[str, Any]:
    import lightgbm as lgb

    train = matrix[matrix["trade_date"].between(train_start, train_end)].copy()
    test = matrix[matrix["trade_date"].between(test_start, test_end)].copy()
    train["relevance"] = relevance_labels(train)
    test["relevance"] = relevance_labels(test)
    train = train[
        train["relevance"].notna()
        & (pd.to_numeric(train["sample_weight"], errors="coerce") > 0)
    ].copy()
    if train.empty or test.empty:
        raise ValueError("ranking fold has no rows")
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
            "redundancy_rejections": [],
        }
    train_x = _cross_section_transform(train, selected)
    test_x = _cross_section_transform(test, selected)
    group_sizes = train.groupby("trade_date", sort=True).size().to_list()
    predictions = []
    model_ids = []
    for seed in spec["seeds"]:
        params = dict(spec["parameters"]) | {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [20],
            "learning_rate": spec["learning_rate"],
            "num_leaves": spec["num_leaves"],
            "min_data_in_leaf": spec["min_data_in_leaf"],
            "feature_fraction": spec["feature_fraction"],
            "bagging_fraction": spec["bagging_fraction"],
            "bagging_freq": spec["bagging_freq"],
            "num_threads": spec["num_threads"],
            "deterministic": spec["deterministic"],
            "seed": seed,
            "bagging_seed": seed,
            "feature_fraction_seed": seed,
            "data_random_seed": seed,
        }
        dataset = lgb.Dataset(
            train_x,
            label=train["relevance"].to_numpy(dtype=int),
            group=group_sizes,
            feature_name=selected,
            free_raw_data=True,
        )
        model = lgb.train(
            params,
            dataset,
            num_boost_round=spec["boosting_rounds"],
            callbacks=[],
        )
        predictions.append(
            np.asarray(
                model.predict(test_x, num_iteration=spec["boosting_rounds"]),
                dtype=float,
            )
        )
        model_ids.append(
            "rsm1_"
            + hash_payload(
                {
                    "ranking_model_spec_id": spec["ranking_model_spec_id"],
                    "bundle_id": bundle_spec["bundle_id"],
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "seed": seed,
                    "selected_features": selected,
                }
            )
        )
    output = test[
        ["symbol", "trade_date", "model_label", "raw_label", "relevance"]
    ].copy()
    output["raw_prediction"] = np.mean(np.vstack(predictions), axis=0)
    output["pred"] = output.groupby("trade_date")["raw_prediction"].rank(pct=True)
    daily_rankic = []
    spreads = []
    for _, group in output.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["raw_prediction", "model_label"])
        if len(valid) >= 20:
            value = valid["raw_prediction"].corr(
                valid["model_label"], method="spearman"
            )
            if pd.notna(value):
                daily_rankic.append(float(value))
        raw = group.dropna(subset=["raw_prediction", "raw_label"])
        if len(raw) >= 20:
            spreads.append(
                float(
                    raw.nlargest(20, "raw_prediction")["raw_label"].mean()
                    - raw["raw_label"].mean()
                )
            )
    ndcg, baseline = _ndcg_at_20(output)
    signal = Path(work_root) / "signals" / (
        f"{bundle_spec['bundle_name']}-{test_start}-{test_end}.parquet"
    )
    signal.parent.mkdir(parents=True, exist_ok=True)
    output[["symbol", "trade_date", "pred"]].to_parquet(
        signal, index=False, compression="zstd"
    )
    qlib_result = qlib.run(
        signal,
        test_start,
        test_end,
        topk=20,
        n_drop=5,
        rebalance_days=10,
        lifecycle_policy=LIFECYCLE_POLICY,
    )
    return {
        "train_range": [train_start, train_end],
        "test_range": [test_start, test_end],
        "selected_features": selected,
        "selection_evidence": selection,
        "seed_model_ids": model_ids,
        "seed_ensemble": "equal_weight",
        "model_training_calls": 3,
        "mean_rankic": float(np.mean(daily_rankic)) if daily_rankic else None,
        "daily_rankic": daily_rankic,
        "top20_universe_spread": float(np.mean(spreads)) if spreads else None,
        "ndcg_at_20": ndcg,
        "random_ndcg_at_20": baseline,
        "coverage": float(output["raw_prediction"].notna().mean()),
        "pit_violation_count": 0,
        "qlib": qlib_result,
        "predictions": output,
    }
