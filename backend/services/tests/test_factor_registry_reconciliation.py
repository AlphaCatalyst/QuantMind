from dataclasses import replace
from pathlib import Path

import pytest

from backend.services.engine.factor_registry.errors import RegistryArtifactError, RegistryMergeConflict
from backend.services.engine.factor_registry.models import RegistrySnapshot
from backend.services.engine.factor_registry.policy import default_promotion_policy
from backend.services.engine.factor_registry.decisions import plan_decision
from backend.services.engine.factor_registry.enums import RegistryStatus
from backend.services.engine.factor_registry.reconciliation import merge_registry_snapshots, publish_reconciliation, reconciliation_payload
from backend.services.engine.factor_registry.snapshot import publish_snapshot, registry_snapshot_id
from backend.services.tests.test_factor_registry_snapshot import entry


def snapshot():
    return RegistrySnapshot("frs_"+"0"*64,default_promotion_policy(),(entry(),),(),None,"",False)


def sibling(base, sid, entries, decisions=()):
    return replace(base, registry_snapshot_id=sid, entries=tuple(entries), decisions=tuple(decisions),
                   previous_registry_snapshot_id="frs_"+"a"*64)


def test_sibling_union_exact_duplicate_and_sorted_sources():
    base=snapshot(); common=entry(); extra=replace(common,factor_instance_id="fi_"+"9"*64)
    left=sibling(base,"frs_"+"2"*64,[common]); right=sibling(base,"frs_"+"1"*64,[common,extra])
    sources,entries,_,duplicates,summary,_=merge_registry_snapshots(left,right,"frs_"+"a"*64)
    assert sources==tuple(sorted(sources)); assert len(entries)==2; assert len(duplicates)==1
    assert summary=={"source_entry_occurrences":3,"result_entry_count":2,"exact_duplicates_deduplicated":1,"conflict_count":0}


def test_non_sibling_and_conflicting_entry_hard_fail():
    base=snapshot(); left=sibling(base,"frs_"+"1"*64,[entry()]); right=sibling(base,"frs_"+"2"*64,[replace(entry(),template_name="changed")])
    with pytest.raises(RegistryMergeConflict,match="REGISTRY_ENTRY_MERGE_CONFLICT"):
        merge_registry_snapshots(left,right,"frs_"+"a"*64)
    with pytest.raises(RegistryArtifactError): merge_registry_snapshots(left,replace(right,previous_registry_snapshot_id="frs_"+"b"*64),"frs_"+"a"*64)


def test_decision_exact_duplicate_deduplicates_and_conflict_fails():
    base=snapshot(); candidate=replace(entry(),status=RegistryStatus.PROMOTION_CANDIDATE)
    decision=plan_decision(entry=candidate,registry_snapshot_id="frs_"+"0"*64,
        policy_id=base.policy.policy_id,action="reject",reason="fixture",decided_by="human",
        decision_source="human",created_at="2026-07-17T00:00:00Z")
    left=sibling(base,"frs_"+"1"*64,[candidate],[decision]); right=sibling(base,"frs_"+"2"*64,[candidate],[decision])
    merged=merge_registry_snapshots(left,right,"frs_"+"a"*64)
    assert merged[2]==(decision,) and merged[5]["exact_duplicates_deduplicated"]==1
    with pytest.raises(RegistryMergeConflict,match="REGISTRY_DECISION_MERGE_CONFLICT"):
        merge_registry_snapshots(left,replace(right,decisions=(replace(decision,reason="different"),)),"frs_"+"a"*64)


def test_reconciled_snapshot_multi_parent_identity_and_exact_replay(tmp_path):
    base=snapshot(); parents=("frs_"+"1"*64,"frs_"+"2"*64)
    expected=registry_snapshot_id(base.policy,base.entries,(),parent_registry_snapshot_ids=parents)
    payload=reconciliation_payload(common_ancestor_snapshot_id="frs_"+"a"*64,source_snapshot_ids=parents,
        source_campaign_ids=("rc_"+"1"*64,"rc_"+"2"*64),source_result_ids=("rcr_"+"1"*64,"rcr_"+"2"*64),
        entry_merge_summary={},decision_merge_summary={},duplicate_entries=(),conflicts=(),resulting_snapshot_id=expected)
    rec=publish_reconciliation(tmp_path/"reconciliation",payload)
    first=publish_snapshot(tmp_path/"registry",base.policy,base.entries,parent_registry_snapshot_ids=parents,reconciliation_artifact_id=rec.reconciliation_id)
    second=publish_snapshot(tmp_path/"registry",base.policy,base.entries,parent_registry_snapshot_ids=parents,reconciliation_artifact_id=rec.reconciliation_id)
    assert first.registry_snapshot_id==expected and first.parent_registry_snapshot_ids==parents
    assert second.exact_existing
