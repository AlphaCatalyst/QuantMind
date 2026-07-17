import hashlib
import json

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.artifact_store.reachability import build_reachability_plan
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


def make_bundle(root, identity):
    root.mkdir()
    data = identity.encode()
    (root / "data").write_bytes(data)
    (root / "manifest.json").write_text(json.dumps({"result_id": identity, "file_hashes": {
        "data": hashlib.sha256(data).hexdigest()}}))
    return root


def test_inventory_and_integrity_are_stable(tmp_path):
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store")); store.initialize()
    receipt = store.import_artifact("generic_research_bundle", make_bundle(tmp_path / "bundle", "gen_inventory"))
    first = publish_inventory(store); second = publish_inventory(store)
    assert first.inventory_id == second.inventory_id
    assert first.created_at == second.created_at
    assert scan_store_integrity(store).status == "healthy"
    descriptor = store.get_descriptor(receipt.descriptor_id)
    store.blobs.path_for(descriptor.files[0].sha256).write_bytes(b"bad")
    assert scan_store_integrity(store).status == "corrupt"


def test_reachability_reports_missing_and_cycles_stably():
    args = dict(root_ids=("a",), lineage_by_artifact_id={"a": ("b",), "b": ("a", "c")},
                available_artifact_ids=("a", "b"))
    first = build_reachability_plan(**args); second = build_reachability_plan(**args)
    assert first.plan_id == second.plan_id
    assert "cycle:a" in first.unresolved_references
    assert "b->c" in first.unresolved_references


def test_unreferenced_blob_is_degraded_and_format_damage_is_corrupt(tmp_path):
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store")); store.initialize()
    digest = "a" * 64
    blob = store.blobs.path_for(digest); blob.parent.mkdir(parents=True); blob.write_bytes(b"orphan")
    assert scan_store_integrity(store).status == "degraded"
    (store.root / "FORMAT.json").write_text("{}")
    report = scan_store_integrity(store)
    assert report.status == "corrupt"
    assert any(item.code == "INVALID_FORMAT" for item in report.issues)
