import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import pandas as pd

from backend.services.engine.market_data.feature_snapshot import load_feature_matrix

from .canonical import canonical_json_bytes
from .errors import ArtifactValidationError
from .identity import factor_values_id


VALUES_SCHEMA_VERSION = "factor-values-v1"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_schema():
    return [{"name": "symbol", "type": "string"}, {"name": "trade_date", "type": "timestamp[ns]"},
            {"name": "factor_value", "type": "double"}]


def publish_values(frame, compiled, quality, output_root):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    staging = root / (".staging-" + uuid.uuid4().hex)
    staging.mkdir()
    try:
        values_path = staging / "values.parquet"
        frame.to_parquet(values_path, index=False, engine="pyarrow", compression="zstd")
        parquet_hash = sha256_file(values_path)
        values_id = factor_values_id(compiled.factor_instance_id, parquet_hash, output_schema())
        target = root / values_id
        manifest = {
            "schema_version": VALUES_SCHEMA_VERSION,
            "factor_values_id": values_id,
            "factor_template_id": compiled.template_id,
            "factor_instance_id": compiled.factor_instance_id,
            "dataset_snapshot_id": compiled.snapshot_id,
            "engine_version": compiled.engine_version,
            "bound_parameters": dict(sorted(compiled.bound_parameters.items())),
            "required_features": list(compiled.required_features),
            "output_schema": output_schema(),
            "row_count": len(frame),
            "parquet_sha256": parquet_hash,
            "quality_sha256": hashlib.sha256(canonical_json_bytes(quality)).hexdigest(),
        }
        (staging / "quality.json").write_bytes(canonical_json_bytes(quality) + b"\n")
        (staging / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
        if target.exists():
            existing = json.loads((target / "manifest.json").read_text())
            if existing != manifest or sha256_file(target / "values.parquet") != parquet_hash:
                raise ArtifactValidationError("existing Factor Values identity has different content")
            return values_id, target, manifest, True
        os.replace(staging, target)
        staging = None
        return values_id, target, manifest, False
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)


def validate_values(snapshot_root, output_root, factor_values_id_value):
    path = Path(output_root) / factor_values_id_value
    try:
        manifest = json.loads((path / "manifest.json").read_text())
        quality = json.loads((path / "quality.json").read_text())
    except Exception as exc:
        raise ArtifactValidationError(f"cannot read Factor Values artifact: {exc}") from exc
    if manifest.get("schema_version") != VALUES_SCHEMA_VERSION or manifest.get("factor_values_id") != factor_values_id_value:
        raise ArtifactValidationError("Factor Values manifest identity/schema mismatch")
    if sha256_file(path / "values.parquet") != manifest.get("parquet_sha256"):
        raise ArtifactValidationError("Factor Values parquet hash mismatch")
    if hashlib.sha256(canonical_json_bytes(quality)).hexdigest() != manifest.get("quality_sha256"):
        raise ArtifactValidationError("Factor Values quality hash mismatch")
    expected_id = factor_values_id(manifest["factor_instance_id"], manifest["parquet_sha256"], manifest["output_schema"])
    if expected_id != factor_values_id_value:
        raise ArtifactValidationError("Factor Values content identity mismatch")
    values = pd.read_parquet(path / "values.parquet")
    if list(values.columns) != ["symbol", "trade_date", "factor_value"] or len(values) != manifest["row_count"]:
        raise ArtifactValidationError("Factor Values output schema/row count mismatch")
    if values.duplicated(["symbol", "trade_date"]).any():
        raise ArtifactValidationError("Factor Values has duplicate keys")
    features = manifest["required_features"]
    source = load_feature_matrix(snapshot_root, manifest["dataset_snapshot_id"], feature_columns=features)
    expected_keys = source[["symbol", "trade_date"]].sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    actual_keys = values[["symbol", "trade_date"]].sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    if not actual_keys.equals(expected_keys):
        raise ArtifactValidationError("Factor Values keys do not match Dataset Snapshot")
    return {"status": "valid", "factor_values_id": factor_values_id_value, "rows": len(values), "quality": quality}
