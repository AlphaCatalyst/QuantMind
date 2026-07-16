import json
from pathlib import Path

from backend.services.engine.market_data.feature_snapshot import LegacyFeatureSnapshotService

from .errors import AdmissionError
from .models import SnapshotContract


def snapshot_contract(snapshot_root, snapshot_id):
    root = Path(snapshot_root)
    try:
        summary = LegacyFeatureSnapshotService(root).validate(snapshot_id)
    except Exception as exc:
        raise AdmissionError(f"dataset snapshot validation failed: {exc}") from exc
    path = root / "snapshots" / snapshot_id
    schema = json.loads((path / "schema.json").read_text(encoding="utf-8"))
    roles = schema.get("column_roles")
    if not isinstance(roles, dict):
        raise AdmissionError("dataset snapshot schema has no column_roles mapping")
    output_schema = schema.get("output_schema")
    if not isinstance(output_schema, list):
        raise AdmissionError("dataset snapshot schema has no output_schema list")
    types = {item.get("name"): item.get("type") for item in output_schema if isinstance(item, dict)}
    return SnapshotContract(snapshot_id, summary["dataset_kind"], roles, int(summary["dates"]), types)
