from pathlib import Path

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.current import plan_current
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


REPO = Path(__file__).resolve().parents[3]


def test_current_research_reachability_is_closed():
    plan, sources, missing = plan_current(REPO)
    assert not plan.missing_artifact_ids
    assert not plan.unresolved_references
    assert not missing
    assert len(plan.reachable_artifact_ids) >= 60
    assert {"dataset_snapshot", "factor_values", "factor_registry", "research_campaign"} <= {
        item.artifact_kind for item in sources}


def test_real_research_artifacts_import_and_replay(tmp_path):
    plan, sources, missing = plan_current(REPO)
    assert not missing
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store")); store.initialize()
    selected = [item for item in sources if item.artifact_id in plan.reachable_artifact_ids]
    receipts = [store.import_artifact(item.artifact_kind, item.source_directory, item.artifact_id,
                lineage=item.lineage, validation_context=item.validation_context) for item in selected]
    assert len(receipts) == len(plan.reachable_artifact_ids)
    assert all(store.verify_artifact(item.artifact_id) for item in receipts)
    replay = [store.import_artifact(item.artifact_kind, item.source_directory, item.artifact_id,
              lineage=item.lineage, validation_context=item.validation_context) for item in selected]
    assert all(item.exact_existing for item in replay)
