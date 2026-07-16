import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .canonical import hash_payload, sha256_file, write_json
from .dataset import validate_validation_dataset
from .errors import FrozenAccessError, ValidationArtifactError
from .metrics import calculate_split_metrics, metrics_payload
from .models import FrozenTestAccessContext


def _read_frozen_labels(dataset_root, dataset_id):
    root = Path(dataset_root) / "datasets" / dataset_id
    validate_validation_dataset(dataset_root, dataset_id)
    return pd.read_parquet(root / "label_snapshot" / "frozen_labels.parquet", engine="pyarrow")


def evaluate_frozen(context, *, dataset_root, validation_root, factor_values_root):
    if not isinstance(context, FrozenTestAccessContext): raise FrozenAccessError("explicit FrozenTestAccessContext required")
    if not all((context.protocol_id, context.validation_dataset_id, context.candidate_selection_id,
                context.access_reason, context.requested_by)):
        raise FrozenAccessError("Frozen access context fields are required")
    selection_root = Path(validation_root) / "selections" / context.candidate_selection_id
    if not selection_root.is_dir(): raise FrozenAccessError("published Candidate Selection is required")
    selection = json.loads((selection_root / "selection.json").read_text())
    if selection["validation_dataset_id"] != context.validation_dataset_id:
        raise FrozenAccessError("selection and Dataset identities differ")
    protocol_root = Path(validation_root) / "frozen_protocols" / context.protocol_id
    if protocol_root.exists():
        locked = json.loads((protocol_root / "lock.json").read_text())
        if locked["candidate_selection_id"] != context.candidate_selection_id or locked["validation_dataset_id"] != context.validation_dataset_id:
            raise FrozenAccessError("Frozen protocol is locked to a different immutable candidate set")
        return validate_frozen_result(validation_root, locked["frozen_result_id"])
    labels = _read_frozen_labels(dataset_root, context.validation_dataset_id)
    dataset = validate_validation_dataset(dataset_root, context.validation_dataset_id)["manifest"]
    split = dataset["splits"]["frozen_test"]
    labels = labels[(labels.trade_date >= split["effective_start"]) & (labels.trade_date <= split["effective_end"])]
    results = []
    for candidate in selection["candidates"]:
        values_path = Path(factor_values_root) / candidate["factor_values_id"] / "values.parquet"
        if not values_path.is_file(): raise FrozenAccessError("selected immutable Factor Values are unavailable")
        values = pd.read_parquet(values_path, engine="pyarrow")
        metrics = calculate_split_metrics(values, labels, orientation=candidate["orientation"])
        results.append({**candidate, "frozen_metrics": metrics_payload(metrics)})
    stable = {"schema_version": "factor-frozen-test-result-v1", "protocol_id": context.protocol_id,
              "validation_dataset_id": context.validation_dataset_id,
              "candidate_selection_id": context.candidate_selection_id,
              "frozen_split": split, "candidate_ids": [x["trial_id"] for x in selection["candidates"]],
              "results": results, "selection_history_changed": False, "reselection_permitted": False}
    result_id = "fvt_" + hash_payload(stable)
    target = Path(validation_root) / "frozen" / result_id
    staging = Path(validation_root) / "frozen" / f".{result_id}.staging-{uuid.uuid4().hex}"
    lock_staging = Path(validation_root) / "frozen_protocols" / f".{context.protocol_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True); lock_staging.mkdir(parents=True)
    try:
        write_json(staging / "access.json", dict(context.__dict__))
        write_json(staging / "results.json", stable)
        hashes = {p.name: sha256_file(p) for p in sorted(staging.glob("*.json"))}
        write_json(staging / "manifest.json", {**stable, "frozen_result_id": result_id,
                                               "created_at": datetime.now(timezone.utc).isoformat(), "file_hashes": hashes})
        write_json(lock_staging / "lock.json", {"protocol_id": context.protocol_id,
                                                "validation_dataset_id": context.validation_dataset_id,
                                                "candidate_selection_id": context.candidate_selection_id,
                                                "frozen_result_id": result_id})
        target.parent.mkdir(parents=True, exist_ok=True); protocol_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target); os.replace(lock_staging, protocol_root)
    finally:
        if staging.exists(): shutil.rmtree(staging)
        if lock_staging.exists(): shutil.rmtree(lock_staging)
    return validate_frozen_result(validation_root, result_id)


def validate_frozen_result(validation_root, result_id):
    root = Path(validation_root) / "frozen" / result_id
    try: manifest = json.loads((root / "manifest.json").read_text())
    except Exception as exc: raise ValidationArtifactError("Frozen result unreadable") from exc
    stable = {key: manifest[key] for key in ("schema_version", "protocol_id", "validation_dataset_id",
              "candidate_selection_id", "frozen_split", "candidate_ids", "results", "selection_history_changed", "reselection_permitted")}
    if result_id != "fvt_" + hash_payload(stable): raise ValidationArtifactError("Frozen result identity mismatch")
    for name, digest in manifest["file_hashes"].items():
        if sha256_file(root / name) != digest: raise ValidationArtifactError("Frozen result file hash mismatch")
    return {"status": "valid", "frozen_result_id": result_id, "path": str(root), "manifest": manifest}
