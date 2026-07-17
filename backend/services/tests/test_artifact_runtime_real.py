from __future__ import annotations

from pathlib import Path

from backend.services.engine.artifact_runtime import (
    inspect_campaign_replay,
    prepare_campaign_config,
    publish_existing_artifact,
    recover_campaign_graph,
    recover_research_state,
    replay_research_campaign,
    resolve_artifact,
    resolve_runtime_context,
)
from backend.services.engine.artifact_store.integrity import scan_store_integrity


INVENTORY = "sai_b0c038070f5e09a4f6ab261647c8686ef09c8e99bfc924afc2ced942c2370320"
ARTIFACTS = (
    ("factor_values", "fv_609cfa536f8906576fd4f78424e4e06c6ce76d124ec4602a941c580b5115c07f"),
    ("factor_optimization", "fos_fdd33e0903b25cea2b20414fc62418474e12dbefbdc7b58527cf06c8d0046ba9"),
    ("factor_validation_result", "fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"),
    ("frozen_test_result", "fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"),
    ("factor_registry", "frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5"),
    ("research_campaign", "rc_4970d1419d17d1327b2092c7ff85cb52d680488555c6408ec3a8ef571219cd5f"),
    ("research_campaign", "rc_0b13d7f235ac948a10c97092c6ce3bbad99ecdefc2c20c93c3648644a5d9401c"),
    ("research_campaign", "rc_16bf571792c6a91fd22cb08149cb28a3de795572b0355000d40242b76548b7ea"),
    ("fresh_validation_admission", "fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab"),
)


def test_empty_cache_store_only_recovery_and_research_state(tmp_path):
    context = resolve_runtime_context(
        explicit_mode="store_required", explicit_cache_root=tmp_path / "empty-cache",
        inventory_id=INVENTORY,
    )
    assert not any(context.cache_root.iterdir()) if context.cache_root.exists() else True
    recovered = []
    for kind, artifact_id in ARTIFACTS:
        item = resolve_artifact(context, kind, artifact_id)
        recovered.append(item)
        assert item.verified and not item.cache_hit
        item.materialized_root.relative_to(context.cache_root)
        assert "/private/tmp/qm2-" not in str(item.materialized_root)
    for kind, artifact_id in ARTIFACTS:
        assert resolve_artifact(context, kind, artifact_id).cache_hit
    state = recover_research_state(context, Path(__file__).resolve().parents[3])
    assert state.canonical_registry_id == ARTIFACTS[4][1]
    assert state.registry_entry_count == 19
    assert state.campaign_ids == tuple(sorted((ARTIFACTS[5][1], ARTIFACTS[6][1], ARTIFACTS[7][1])))
    assert len(state.optimization_study_ids) == 7
    assert state.validation_result_id == ARTIFACTS[2][1]
    assert state.frozen_result_id == ARTIFACTS[3][1]
    assert state.fresh_admission_result_id == ARTIFACTS[8][1]
    assert state.fresh_status == "awaiting_first_fresh_date"
    assert state.fresh_eligible_date_count == 0
    assert (state.promotion_candidate_count, state.approved_count, state.active_count) == (0, 0, 0)


def test_external_campaign_exact_replay_calls_nothing(tmp_path):
    context = resolve_runtime_context(
        explicit_mode="store_required", explicit_cache_root=tmp_path / "campaign-cache",
        inventory_id=INVENTORY,
    )
    replay = replay_research_campaign(context, ARTIFACTS[6][1])
    summary = inspect_campaign_replay(replay)
    assert replay.exact_existing
    assert summary["replay_agent_calls"] == 0
    assert summary["replay_optimization_calls"] == 0
    assert summary["replay_registry_writes"] == 0


def test_partial_production_dry_run_cold_recovers_and_exact_replays(tmp_path):
    context = resolve_runtime_context(
        explicit_mode="store_required", explicit_cache_root=tmp_path / "partial-campaign",
        inventory_id=INVENTORY,
    )
    replay = replay_research_campaign(context, ARTIFACTS[7][1])
    summary = inspect_campaign_replay(replay)
    assert summary["replay_agent_calls"] == 0
    graph = recover_campaign_graph(context, ARTIFACTS[7][1])
    assert graph["new_campaign_id"] == ARTIFACTS[7][1]
    assert graph["new_decision_id"] is None
    assert graph["new_factor_values_ids"] == []
    assert graph["new_registry_id"] == ARTIFACTS[4][1]
    assert graph["registry_entry_count"] == 19


def test_exact_existing_write_through_changes_no_store_identity(tmp_path):
    context = resolve_runtime_context(
        explicit_mode="store_required", explicit_cache_root=tmp_path / "publish-cache",
        inventory_id=INVENTORY,
    )
    before_descriptors = tuple(x.descriptor_id for x in context.store.list_artifacts())
    before = scan_store_integrity(context.store)
    for kind, artifact_id in (ARTIFACTS[1], ARTIFACTS[4], ARTIFACTS[6]):
        published = publish_existing_artifact(context, kind, artifact_id)
        assert published.exact_existing and published.new_blob_count == 0
    after_descriptors = tuple(x.descriptor_id for x in context.store.list_artifacts())
    after = scan_store_integrity(context.store)
    assert before_descriptors == after_descriptors
    assert before.artifact_count == after.artifact_count == 66
    assert before.blob_count == after.blob_count == 287
    assert before.status == after.status == "healthy"
    assert after.issues == () and after.unreferenced_blobs == ()


def test_new_campaign_inputs_are_prepared_from_store_not_legacy_sources(tmp_path):
    context = resolve_runtime_context(
        explicit_mode="store_required", explicit_cache_root=tmp_path / "campaign-inputs",
        inventory_id=INVENTORY,
    )
    config = prepare_campaign_config(
        context,
        snapshot_id="ds_dd1defb79ddf2a81f057be9e34715cb04df340204d68338f73ab1ad4692e338f",
        validation_dataset_id="vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62",
        registry_snapshot_id="frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9",
        execution_root=tmp_path / "execution",
    )
    for value in (
        config.snapshot_root, config.validation_root, config.registry_root,
        config.existing_optimization_root,
    ):
        Path(value).resolve().relative_to(context.cache_root)
        assert "/private/tmp/qm2-p0-" not in value
