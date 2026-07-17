from dataclasses import replace
import json
from pathlib import Path

import pytest

from backend.services.engine.factor_registry import active_factors, apply_decision, list_by_family, list_by_status, load_registry_snapshot, plan_decision, publish_snapshot
from backend.services.engine.factor_registry.enums import RegistryStatus
from backend.services.engine.factor_registry.errors import RegistryArtifactError, RegistryDecisionError
from backend.services.engine.factor_registry.policy import default_promotion_policy
from backend.services.tests.test_factor_registry_schema import entry


def test_snapshot_deterministic_exact_existing_ordering_and_reader(tmp_path):
    policy=default_promotion_policy(); entries=(entry(),replace(entry(),factor_instance_id="fi_"+"0"*64))
    first=publish_snapshot(tmp_path,policy,entries); second=publish_snapshot(tmp_path,policy,reversed(entries))
    assert first.registry_snapshot_id==second.registry_snapshot_id and second.exact_existing
    loaded=load_registry_snapshot(tmp_path,first.registry_snapshot_id)
    assert [x.factor_instance_id for x in loaded.entries]==sorted(x.factor_instance_id for x in entries)
    assert len(list_by_status(loaded,"validation_rejected"))==2
    assert len(list_by_family(loaded,entry().family_id))==2 and active_factors(loaded)==()
    assert not list((tmp_path/"snapshots").glob(".*.staging-*"))


def test_corrupt_snapshot_rejected_and_never_overwritten(tmp_path):
    snap=publish_snapshot(tmp_path,default_promotion_policy(),(entry(),))
    path=Path(snap.artifact_path)/"entries"/f"{entry().factor_instance_id}.json"; path.write_text("{}")
    with pytest.raises(RegistryArtifactError): load_registry_snapshot(tmp_path,snap.registry_snapshot_id)
    with pytest.raises(RegistryArtifactError): publish_snapshot(tmp_path,default_promotion_policy(),(entry(),))


def test_decision_creates_new_snapshot_and_stale_reference_rejected(tmp_path):
    candidate=replace(entry(),status=RegistryStatus.PROMOTION_CANDIDATE)
    first=publish_snapshot(tmp_path,default_promotion_policy(),(candidate,))
    decision=plan_decision(entry=candidate,registry_snapshot_id=first.registry_snapshot_id,policy_id=first.policy.policy_id,
        action="reject",reason="synthetic fixture only",decided_by="reviewer",decision_source="human",created_at="2026-07-17T05:00:00Z")
    second=apply_decision(first,decision,tmp_path)
    assert second.registry_snapshot_id!=first.registry_snapshot_id and second.previous_registry_snapshot_id==first.registry_snapshot_id
    assert second.entries[0].status is RegistryStatus.FROZEN_REJECTED
    with pytest.raises(RegistryDecisionError): apply_decision(second,decision,tmp_path)
