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
    "technical_dsl_operator_extension": ("operator_extension_id", "tdoe1_"),
    "technical_dsl_operator_validation": ("operator_validation_id", "tdov1_"),
    "technical_primitive_catalog": ("primitive_catalog_id", "tpc2_"),
    "technical_primitive_materialization": ("primitive_materialization_id", "tpm2_"),
    "autonomous_technical_feature_factory_spec_v2": ("factory_spec_id", "atffs2_"),
    "technical_feature_catalog_v3": ("feature_catalog_v3_id", "tfc3_"),
    "autonomous_research_cycle_v2": ("research_cycle_id", "arc2_"),
    "research_space_expansion_report": ("research_space_report_id", "rser1_"),
    "fixed_configuration_model_spec": ("model_spec_id", "fcms1_"),
    "model_feature_bundle_spec": ("bundle_id", "mfbs1_"),
    "purged_walk_forward_spec": ("walk_forward_spec_id", "pwfs1_"),
    "model_training_leakage_audit": ("leakage_audit_id", "mtla1_"),
    "model_fold_training": ("fold_model_id", "mft1_"),
    "model_fold_prediction": ("prediction_artifact_id", "mfp1_"),
    "model_fold_result": ("fold_result_id", "mfr1_"),
    "model_stability_assessment": ("stability_assessment_id", "msa1_"),
    "model_multiple_testing_control": ("multiple_testing_id", "mmtc1_"),
    "retrospective_model_candidate": ("candidate_id", "rmc1_"),
    "model_factor_distillation_queue": ("distillation_queue_id", "mfdq1_"),
    "project_model_candidate_fresh_lock": ("fresh_lock_id", "pmcfl1_"),
    "model_fresh_observation": ("fresh_observation_id", "mfo1_"),
    "model_fresh_assessment": ("fresh_assessment_id", "mfa1_"),
    "technical_return_label_family": ("label_family_id", "trlf1_"),
    "technical_return_label": ("label_id", "trl1_"),
    "executable_label_audit": ("label_audit_id", "ela1_"),
    "label_quality_assessment": ("quality_assessment_id", "lqa1_"),
    "multi_horizon_model_fold_result": ("fold_result_id", "mhfr1_"),
    "horizon_alignment_assessment": ("alignment_assessment_id", "haa1_"),
    "multi_horizon_multiple_testing": ("multiple_testing_id", "mhmt1_"),
    "multi_horizon_retrospective_model_candidate": ("candidate_id", "mhrmc1_"),
    "multi_horizon_model_fresh_lock": ("fresh_lock_id", "mhmfl1_"),
    "multi_horizon_label_research_report": ("research_report_id", "mhlrr1_"),
    "model_fresh_candidate_cohort": ("model_fresh_candidate_cohort_id", "mfcc1_"),
    "fresh_model_training_event": ("fresh_model_training_event_id", "fmte1_"),
    "fresh_model_bundle_membership": ("fresh_model_bundle_membership_id", "fmbm1_"),
    "fresh_model_prediction": ("fresh_model_prediction_id", "fmp1_"),
    "fresh_model_label_observation": ("fresh_model_label_observation_id", "fmlo1_"),
    "fresh_model_strategy_observation": ("fresh_model_strategy_observation_id", "fmso1_"),
    "fresh_model_candidate_observation": ("fresh_model_candidate_observation_id", "fmco1_"),
    "fresh_model_cohort_multiple_testing": (
        "fresh_model_cohort_multiple_testing_id",
        "fmcmt1_",
    ),
    "fresh_model_candidate_assessment": ("fresh_model_candidate_assessment_id", "fmca1_"),
    "fresh_model_heartbeat_run": ("fresh_model_heartbeat_run_id", "fmhr1_"),
    "fresh_heartbeat_scheduler_status": (
        "fresh_heartbeat_scheduler_status_id",
        "fhss1_",
    ),
    "fresh_heartbeat_operational_run": (
        "fresh_heartbeat_operational_run_id",
        "fhor1_",
    ),
    "fresh_runtime_path_audit": ("fresh_runtime_path_audit_id", "frpa1_"),
    "fresh_runtime_app_snapshot": ("fresh_runtime_app_snapshot_id", "fras1_"),
    "fresh_runtime_environment_snapshot": (
        "fresh_runtime_environment_snapshot_id",
        "fres1_",
    ),
    "fresh_runtime_state_migration": (
        "fresh_runtime_state_migration_id",
        "frsm1_",
    ),
    "fresh_runtime_deployment_status": (
        "fresh_runtime_deployment_status_id",
        "frds1_",
    ),
    "fresh_heartbeat_tmp_cleanup_assessment": (
        "tmp_cleanup_assessment_id",
        "fhtca1_",
    ),
    "runtime_diagnostic_whitelist": ("diagnostic_whitelist_id", "rdw1_"),
    "runtime_diagnostic_redaction_guard": ("redaction_guard_id", "rdrg1_"),
    "historical_session_diagnostic_exposure_record": (
        "exposure_record_id",
        "hsder1_",
    ),
    "fresh_runtime_hardening_status": (
        "fresh_runtime_hardening_status_id",
        "frhs1_",
    ),
    "environment_validation_tmp_assessment": (
        "environment_validation_tmp_assessment_id",
        "evta1_",
    ),
    "fresh_runtime_status_consistency_validation": (
        "fresh_runtime_status_consistency_validation_id",
        "frscv1_",
    ),
    "canonical_runtime_artifact_resolution": (
        "canonical_runtime_artifact_resolution_id",
        "crar1_",
    ),
    "fresh_runtime_hardening_completion": (
        "fresh_runtime_hardening_completion_id",
        "frhc1_",
    ),
    "rolling_blind_window_set": ("rolling_blind_window_set_id", "rbws1_"),
    "rolling_blind_discovery_batch": (
        "rolling_blind_discovery_batch_id",
        "rbdb1_",
    ),
    "rolling_blind_candidate_batch_lock": (
        "rolling_blind_candidate_batch_lock_id",
        "rbcbl1_",
    ),
    "rolling_blind_candidate_result": (
        "rolling_blind_candidate_result_id",
        "rbcr1_",
    ),
    "rolling_blind_multiple_testing": (
        "rolling_blind_multiple_testing_id",
        "rbmt1_",
    ),
    "rolling_blind_search_exposure": (
        "rolling_blind_search_exposure_id",
        "rbse1_",
    ),
    "rolling_blind_alpha_survivor": (
        "rolling_blind_alpha_survivor_id",
        "rbas1_",
    ),
    "rolling_blind_submission_ledger": (
        "rolling_blind_submission_ledger_id",
        "rbsl1_",
    ),
    "rolling_blind_research_report": (
        "rolling_blind_research_report_id",
        "rbrr1_",
    ),
}

OPERATIONAL_KINDS = {
    "fresh_heartbeat_scheduler_status",
    "fresh_heartbeat_operational_run",
    "fresh_runtime_path_audit",
    "fresh_runtime_app_snapshot",
    "fresh_runtime_environment_snapshot",
    "fresh_runtime_state_migration",
    "fresh_runtime_deployment_status",
    "fresh_heartbeat_tmp_cleanup_assessment",
    "runtime_diagnostic_whitelist",
    "runtime_diagnostic_redaction_guard",
    "historical_session_diagnostic_exposure_record",
    "fresh_runtime_hardening_status",
    "environment_validation_tmp_assessment",
    "fresh_runtime_status_consistency_validation",
    "canonical_runtime_artifact_resolution",
    "fresh_runtime_hardening_completion",
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
    if kind not in OPERATIONAL_KINDS and identity.get("provider_id") != "tushare-pro-v1":
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
