from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload, write_json


KINDS = {
    "autonomous_factor_campaign_spec": ("campaign_spec_id", "afc1_"),
    "autonomous_factor_campaign": ("campaign_id", "afcs1_"),
    "autonomous_factor_round": ("round_result_id", "afr1_"),
    "autonomous_factor_proposal": ("proposal_artifact_id", "afp1_"),
    "autonomous_factor_failure_memory": ("memory_id", "affm1_"),
    "autonomous_factor_round_plan": ("round_plan_id", "afrp1_"),
    "autonomous_factor_candidate_lock": ("candidate_lock_id", "afcl1_"),
    "autonomous_factor_near_miss": ("near_miss_id", "afnm1_"),
    "autonomous_factor_campaign_report": ("report_id", "afcr1_"),
    "autonomous_factor_value_materialization": ("factor_values_id", "afcv1_"),
    "autonomous_factor_campaign_spec_v2": ("campaign_spec_id", "afc2_"),
    "campaign_evidence_partition": ("evidence_partition_id", "acep1_"),
    "clean_room_campaign_seed_memory": ("seed_memory_id", "acsm1_"),
    "candidate_search_exposure": ("search_exposure_id", "acse1_"),
    "autonomous_campaign_shortlist_lock": ("shortlist_lock_id", "acsl1_"),
    "campaign_failure_memory_freeze": ("memory_freeze_id", "acfmf1_"),
    "locked_holdout_evaluation": ("holdout_evaluation_id", "ache1_"),
    "autonomous_holdout_failure_report": ("holdout_failure_id", "achfr1_"),
    "autonomous_campaign_v1_generalization_assessment": ("v1_assessment_id", "acv1ga1_"),
    "autonomous_candidate_fresh_lock": ("fresh_lock_id", "acfl1_"),
    "autonomous_factor_campaign_report_v2": ("report_id", "afcr2_"),
    "autonomous_factor_research_program_spec": ("program_spec_id", "afrp1_"),
    "research_program_evidence_partition": ("evidence_partition_id", "rpep1_"),
    "research_program_clean_room_seed": ("seed_id", "rpcs1_"),
    "autonomous_factor_program": ("program_state_id", "afps1_"),
    "autonomous_factor_lane": ("lane_state_id", "afls1_"),
    "autonomous_lane_shortlist_lock": ("lane_shortlist_lock_id", "alsl1_"),
    "global_research_novelty_index": ("novelty_index_id", "grni1_"),
    "program_search_exposure": ("search_exposure_id", "pse1_"),
    "autonomous_program_union_shortlist_lock": ("union_shortlist_lock_id", "apusl1_"),
    "program_locked_validation": ("validation_id", "plv1_"),
    "program_multiple_testing_control": ("multiple_testing_id", "pmtc1_"),
    "program_validation_failure_report": ("validation_failure_id", "pvfr1_"),
    "autonomous_program_candidate_fresh_lock": ("fresh_lock_id", "apfl1_"),
    "autonomous_factor_program_report": ("report_id", "afpr1_"),
    "autonomous_technical_feature_factory_spec": ("factory_spec_id", "atffs1_"),
    "technical_feature_proposal": ("feature_proposal_id", "tfp1_"),
    "technical_feature_admission": ("feature_admission_id", "tfa1_"),
    "technical_feature_materialization": ("feature_materialization_id", "tfm1_"),
    "technical_feature_novelty_index": ("novelty_index_id", "tfni1_"),
    "technical_feature_catalog_v2": ("feature_catalog_v2_id", "tfc2_"),
    "alpha_archetype_contract": ("archetype_contract_id", "aac1_"),
    "archetype_aware_program_spec": ("program_spec_id", "aap1_"),
    "archetype_aware_alpha_proposal": ("proposal_artifact_id", "aaap1_"),
    "archetype_aware_union_shortlist_lock": ("union_shortlist_lock_id", "aausl1_"),
    "monotonic_alpha_validation": ("validation_id", "mav1_"),
    "tail_alpha_validation": ("validation_id", "tav1_"),
    "archetype_multiple_testing_control": ("multiple_testing_id", "amtc1_"),
    "archetype_alpha_validation_failure": ("validation_failure_id", "aavf1_"),
    "archetype_alpha_fresh_lock": ("fresh_lock_id", "aafl1_"),
    "archetype_aware_program_report": ("report_id", "aapr1_"),
    "project_evidence_exposure_ledger": ("exposure_ledger_id", "peel1_"),
    "autonomous_research_supervisor_spec": ("supervisor_spec_id", "arsv1_"),
    "autonomous_research_supervisor": ("supervisor_id", "ars1_"),
    "autonomous_research_queue": ("research_queue_id", "arq1_"),
    "autonomous_research_cycle": ("research_cycle_id", "arc1_"),
    "retrospective_candidate": ("candidate_id", "rcan1_"),
    "project_candidate_fresh_lock": ("fresh_lock_id", "pcfl1_"),
    "fresh_candidate_cohort": ("fresh_cohort_id", "fcc1_"),
    "fresh_market_snapshot": ("fresh_market_snapshot_id", "fms1_"),
    "fresh_candidate_observation": ("fresh_observation_id", "fco1_"),
    "fresh_cohort_multiple_testing": ("fresh_multiple_testing_id", "fcmt1_"),
    "fresh_candidate_assessment": ("fresh_assessment_id", "fca1_"),
    "autonomous_research_supervisor_report": ("supervisor_report_id", "arsr1_"),
}


def validate_artifact(root: Path, expected_id: str, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in KINDS or (expected_kind and kind != expected_kind):
        raise ValueError("autonomous campaign Artifact kind mismatch")
    field, prefix = KINDS[kind]
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or expected_id != prefix + hash_payload(identity):
        raise ValueError("autonomous campaign Artifact identity mismatch")
    if manifest.get(field) != expected_id:
        raise ValueError("autonomous campaign Artifact ID field mismatch")
    if identity.get("provider_id") != "tushare-pro-v1":
        raise ValueError("autonomous campaign data authority mismatch")
    if identity.get("promotion_writes", 0) != 0:
        raise ValueError("autonomous campaign crossed Promotion boundary")
    if kind == "autonomous_factor_candidate_lock" and identity.get("status") != "research_registered":
        raise ValueError("autonomous candidate status is not research_registered")
    if any(key in json.dumps(identity, sort_keys=True).lower() for key in ("tushare_token", "access_token", "api_key")):
        raise ValueError("secret marker is forbidden")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or "manifest.json" in hashes:
        raise ValueError("autonomous campaign file inventory invalid")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != set(hashes) or any(hash_file(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("autonomous campaign file hash mismatch")
    for name in actual:
        if name.endswith(".json"):
            lowered = (root / name).read_bytes().lower()
            if any(marker in lowered for marker in (b"tushare_token", b"access_token", b"api_key", b"private_key")):
                raise ValueError("autonomous campaign JSON contains a forbidden secret marker")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": expected_id, "file_count": len(actual)}


def publish_artifact(root: Path, kind: str, identity: Mapping[str, Any], files: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("unsupported autonomous campaign Artifact kind")
    field, prefix = KINDS[kind]
    stable = dict(identity)
    stable.pop(field, None)
    artifact_id = prefix + hash_payload(stable)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_artifact(target, artifact_id, kind)
        return json.loads((target / "manifest.json").read_text()) | {"path": str(target), "exact_existing": True}
    staging = target.parent / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        for relative, value in sorted(files.items()):
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, Path):
                shutil.copyfile(value, destination)
            elif isinstance(value, bytes):
                destination.write_bytes(value)
            elif isinstance(value, str):
                destination.write_text(value, encoding="utf-8")
            else:
                write_json(destination, value)
        hashes = {p.relative_to(staging).as_posix(): hash_file(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        manifest = {
            "schema_version": "autonomous-factor-campaign-artifact-v1",
            "artifact_kind": kind, field: artifact_id, "identity": stable, "file_hashes": hashes,
        }
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, artifact_id, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}
