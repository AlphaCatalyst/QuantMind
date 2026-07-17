import json
from pathlib import Path

import pandas as pd

from backend.services.engine.factor_validation.dataset import load_development_labels
from backend.services.engine.factor_validation.metrics import calculate_split_metrics, metrics_payload, train_orientation

from .canonical import hash_payload


def evaluate_development(*, validation_root, validation_dataset_id, factor_values_root, factor_values_id):
    labels = load_development_labels(validation_root, validation_dataset_id)
    labels["trade_date"] = pd.to_datetime(labels["trade_date"])
    values = pd.read_parquet(Path(factor_values_root) / factor_values_id / "values.parquet", engine="pyarrow")
    values["trade_date"] = pd.to_datetime(values["trade_date"])
    research = labels[(labels["trade_date"] >= "2022-01-01") & (labels["trade_date"] <= "2024-12-31")]
    development = labels[(labels["trade_date"] >= "2025-01-01") & (labels["trade_date"] <= "2025-12-31")]
    raw_research = calculate_split_metrics(values, research)
    orientation = train_orientation(raw_research)
    if orientation is None:
        metrics = None
    else:
        metrics = calculate_split_metrics(values, development, orientation=orientation)
    research_period = [research["trade_date"].min().date().isoformat(), research["trade_date"].max().date().isoformat()]
    development_period = [development["trade_date"].min().date().isoformat(), development["trade_date"].max().date().isoformat()]
    identity = {"protocol": "adaptive-development-2025-v1", "validation_dataset_id": validation_dataset_id,
                "factor_values_id": factor_values_id, "orientation": orientation,
                "orientation_period": research_period, "development_period": development_period,
                "development_is_contaminated": True, "is_validation_evidence": False, "is_frozen_evidence": False,
                "predictive_claim": False, "adaptive_research_only": True, "contaminated_period": True,
                "eligible_for_registry_promotion": False, "orientation_source": "pre_2025_research_period",
                "research_metrics": metrics_payload(raw_research),
                "development_metrics": metrics_payload(metrics) if metrics else None}
    return {**identity, "development_evaluation_id": "der_" + hash_payload(identity)}
