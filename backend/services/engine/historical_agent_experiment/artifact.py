from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from .canonical import hash_file, hash_payload, write_json


PREFIXES = {
    "fixed_universe_lock": ("universe_lock_id", "ful_"),
    "fixed_universe_historical_dataset": ("dataset_id", "fuhd_"),
    "historical_agent_experiment": ("experiment_id", "hae_"),
    "historical_round_lock": ("round_lock_id", "hrcl_"),
    "historical_round_evaluation": ("evaluation_id", "hre_"),
    "qlib_backtest_result": ("backtest_result_id", "qbr_"),
    "historical_holdout_result": ("holdout_result_id", "hhr_"),
    "agent_iteration_assessment": ("assessment_id", "aia_"),
    "signal_missingness_audit": ("signal_missingness_audit_id", "sma_"),
    "historical_backtest_followup": ("historical_backtest_followup_id", "hbf_"),
}


def publish_historical_artifact(root: Path, kind: str, identity: Mapping[str, Any],
                                files: Mapping[str, Path] | None = None) -> dict:
    if kind not in PREFIXES:
        raise ValueError("unsupported historical artifact kind")
    id_field, prefix = PREFIXES[kind]
    stable = dict(identity)
    stable.pop(id_field, None); stable.pop("file_hashes", None); stable.pop("created_at", None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_historical_artifact(kind, target, artifact_id)
        return {"status": "existing", id_field: artifact_id, "path": str(target)}
    staging = Path(root) / kind / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        hashes = {}
        for relative, source in sorted((files or {}).items()):
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            hashes[relative] = hash_file(destination)
        manifest = {**stable, id_field: artifact_id, "artifact_kind": kind, "file_hashes": hashes}
        write_json(staging / "manifest.json", manifest)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        validate_historical_artifact(kind, target, artifact_id)
        return {"status": "created", id_field: artifact_id, "path": str(target), "manifest": manifest}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def validate_historical_artifact(kind: str, source: Path, artifact_id: str) -> str:
    if kind not in PREFIXES:
        raise ValueError("unsupported historical artifact kind")
    id_field, prefix = PREFIXES[kind]
    manifest = json.loads((Path(source) / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("artifact_kind") != kind or manifest.get(id_field) != artifact_id:
        raise ValueError("historical artifact kind or identity mismatch")
    stable = {key: value for key, value in manifest.items()
              if key not in {id_field, "artifact_kind", "file_hashes", "created_at"}}
    if artifact_id != prefix + hash_payload(stable):
        raise ValueError("historical artifact content identity mismatch")
    for relative, expected in manifest.get("file_hashes", {}).items():
        path = Path(source) / relative
        if not path.is_file() or hash_file(path) != expected:
            raise ValueError("historical artifact file hash mismatch")
    if kind == "fixed_universe_lock":
        symbols = manifest.get("symbols", [])
        if len(symbols) != 100 or len(set(symbols)) != 100 or manifest.get("replacement_policy") != "never":
            raise ValueError("fixed universe invariant failed")
    if kind == "historical_round_lock" and manifest.get("locked_before_evaluation") is not True:
        raise ValueError("historical round lock timing evidence absent")
    if kind == "signal_missingness_audit":
        required = {
            "protocol.json", "layer_metrics.json", "daily_missingness.parquet",
            "symbol_missingness.parquet", "feature_missingness.json",
            "ast_node_missingness.json", "qlib_alignment.json", "root_cause.json",
        }
        if not required.issubset(manifest.get("file_hashes", {})):
            raise ValueError("signal missingness audit is incomplete")
        outcomes = {"blocked.json", "rerun_result.json"}
        if len(outcomes.intersection(manifest.get("file_hashes", {}))) != 1:
            raise ValueError("signal missingness audit requires exactly one outcome")
    if kind == "historical_backtest_followup":
        if manifest.get("quality_gate_threshold") != 0.2:
            raise ValueError("historical follow-up changed the signal quality gate")
        if manifest.get("status") not in {"blocked", "completed"}:
            raise ValueError("historical follow-up status is invalid")
    return "historical_agent_experiment.validate_historical_artifact"
