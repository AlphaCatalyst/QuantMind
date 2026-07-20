from pathlib import Path

from backend.services.engine.artifact_runtime import publish_domain_artifact, resolve_artifact, resolve_runtime_context
from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config
from backend.services.engine.strategy_optimization.artifact import publish_json_artifact
from backend.services.engine.tushare_cutover.canonical import hash_payload


def test_store_publication_cold_recovery_and_exact_existing(tmp_path):
    FileSystemResearchArtifactStore(resolve_config(tmp_path / "store")).initialize()
    context = resolve_runtime_context(explicit_mode="store_required", explicit_store_root=tmp_path / "store", explicit_cache_root=tmp_path / "cache")
    identity = {"spec": {"data_authority": "tushare-pro-v1"}, "engine_version": "1.0.0"}
    artifact_id = "sos_" + hash_payload(identity)
    artifact = publish_json_artifact(tmp_path / "domain", "strategy_optimization_study", artifact_id, identity, {"spec.json": identity["spec"], "summary.json": {"trial_count": 96}, "trial_index.json": {"trial_ids": []}})
    first = publish_domain_artifact(context, "strategy_optimization_study", artifact_id, artifact["path"])
    second = publish_domain_artifact(context, "strategy_optimization_study", artifact_id, artifact["path"])
    assert not first.exact_existing and second.exact_existing and second.new_blob_count == 0
    recovered = resolve_artifact(context, "strategy_optimization_study", artifact_id)
    assert recovered.verified and (recovered.materialized_root / "summary.json").is_file()
