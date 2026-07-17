import json
import os
import shutil
import uuid
from pathlib import Path

import pandas as pd

from backend.services.engine.factor_validation.dataset import load_development_labels
from backend.services.engine.factor_validation.metrics import calculate_split_metrics, metrics_payload, train_orientation

from .canonical import hash_payload, sha256_file, write_json


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


def publish_development_bundle(output_root, development):
    """Publish one immutable, quarantined Development result as a Store-ready bundle."""
    result_id = development["development_evaluation_id"]
    target = Path(output_root) / result_id
    if target.exists():
        validate_development_bundle(target, result_id)
        return target
    staging = Path(output_root) / f".{result_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        write_json(staging / "development.json", development)
        manifest = {
            "schema_version": "development-result-bundle-v1",
            "result_id": result_id,
            "file_hashes": {"development.json": sha256_file(staging / "development.json")},
        }
        write_json(staging / "manifest.json", manifest)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
    validate_development_bundle(target, result_id)
    return target


def validate_development_bundle(root, expected_id):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    development = json.loads((root / "development.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != "development-result-bundle-v1"
            or manifest.get("result_id") != expected_id
            or development.get("development_evaluation_id") != expected_id
            or manifest.get("file_hashes") != {"development.json": sha256_file(root / "development.json")}):
        raise ValueError("Development result bundle identity or hash mismatch")
    required = {
        "development_is_contaminated": True,
        "is_validation_evidence": False,
        "is_frozen_evidence": False,
        "predictive_claim": False,
        "adaptive_research_only": True,
        "contaminated_period": True,
        "eligible_for_registry_promotion": False,
    }
    if any(development.get(key) is not value for key, value in required.items()):
        raise ValueError("Development result quarantine is invalid")
    return development
