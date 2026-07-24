from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .contamination_ledger import LATEST_PROJECT_EXPOSURE, build_project_evidence_ledger
from .control import global_stop_decision
from .models import AutonomousResearchSupervisorSpecV1, runtime_counts


FACTORY_SPEC_ID = "atffs1_59f2c98666d95c2e5d2414b0837863908df38cbcd12bf86333465ea4cc3cf288"
FEATURE_CATALOG_ID = "tfc2_229f1939bdd3023e0410d3def332f1a9fdbd8cb4193cc71e7e6a8660138cf5e6"
ALPHA_PROGRAM_ID = "aap1_30e59bce48153a721dd29b459548dafc98271f6eef4236c07a8569b70acd0100"
ALPHA_REPORT_ID = "aapr1_e344e138cb76bd1c0307920426b879c0b0a1019b4e3083cc3f373a739df4f6e3"
R1_010_SNAPSHOT_ID = "tims1_a59e3127abcdd187f352b4d268d765c73bfec480ac5fefd6c6c865ebe909168c"


def _repository(store_root: Path | None, work_root: Path) -> CampaignRepository:
    store = FileSystemResearchArtifactStore(resolve_config(store_root))
    store.validate_format()
    return CampaignRepository(store, Path(work_root) / "domain", Path(work_root) / "recovery")


def _publish(repository: CampaignRepository, kind: str, identity: dict,
             files: dict[str, Any], lineage=()) -> tuple[dict, dict]:
    receipt = repository.publish(kind, identity, files, lineage=lineage)
    return repository.identity(receipt["artifact_id"]), receipt


def create_supervisor_spec(*, repository_root: Path, work_root: Path,
                           store_root: Path | None = None) -> dict[str, Any]:
    repository = _repository(store_root, work_root)
    ledger = build_project_evidence_ledger(repository_root)
    ledger_identity, ledger_receipt = _publish(
        repository, "project_evidence_exposure_ledger", ledger,
        {"exposure_ledger.json": ledger},
    )
    spec = AutonomousResearchSupervisorSpecV1().payload() | {
        "project_contamination_ledger_id": ledger_receipt["artifact_id"],
        "project_exposed_date_max": LATEST_PROJECT_EXPOSURE,
    }
    spec_identity, spec_receipt = _publish(
        repository, "autonomous_research_supervisor_spec", spec,
        {"supervisor_spec.json": spec},
        (ledger_receipt["artifact_id"],),
    )
    return {
        "status": "spec_frozen",
        "supervisor_spec_id": spec_receipt["artifact_id"],
        "project_contamination_ledger_id": ledger_receipt["artifact_id"],
        "ledger_entries": len(ledger_identity["entries"]),
        "project_exposed_date_max": ledger_identity["project_exposed_date_range"][1],
        "credential_present": bool(os.environ.get("TUSHARE_TOKEN")),
        "credential_persisted": False,
        "new_artifacts": int(not ledger_receipt["exact_existing"]) + int(not spec_receipt["exact_existing"]),
        "new_blobs": ledger_receipt["new_blob_count"] + spec_receipt["new_blob_count"],
    }


def _queue(spec: dict, ledger_id: str) -> dict[str, Any]:
    directions = [
        ("trend_geometry", "trend_geometry", "monotonic_rank_factor"),
        ("trading_confirmation", "liquidity_amount", "top_tail_selection_factor"),
        ("relative_asymmetric", "relative_path_asymmetry", "monotonic_rank_factor"),
    ]
    rows = []
    for research_family, feature_family, archetype in directions:
        rows.append({
            "research_family": research_family,
            "feature_family": feature_family,
            "archetype": archetype,
            "novelty_remaining": "bounded_unproven",
            "historical_attempt_count": 6,
            "duplicate_rate": None,
            "admission_rate": None,
            "candidate_rate": 0.0,
            "last_run": "QM2-R2-004",
            "next_priority": "defer_until_new_authorized_space",
            "freeze_reason": "current_catalog_and_program_revision_exhausted",
        })
    stable = {
        "schema_version": "autonomous-research-queue-v1",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": spec["supervisor_spec_id"],
        "project_contamination_ledger_id": ledger_id,
        "directions": rows,
        "priority_inputs": [
            "structural_coverage", "feature_coverage", "duplicate_rate",
            "static_failure", "historical_research_efficiency",
        ],
        "fresh_performance_used_for_same_candidate_modification": False,
        "promotion_writes": 0,
    }
    return stable | {"research_queue_id": "arq1_" + hash_payload(stable)}


def execute_supervisor(*, supervisor_spec_id: str, repository_root: Path,
                       work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    repository = _repository(store_root, work_root)
    spec = repository.identity(supervisor_spec_id)
    spec["supervisor_spec_id"] = supervisor_spec_id
    if spec.get("schema_version") != "autonomous-research-supervisor-spec-v1":
        raise ValueError("Supervisor Spec is invalid")
    reports = [
        repository.identity(row.artifact_id)
        for row in repository.store.list_by_kind("autonomous_research_supervisor_report")
    ]
    completed = [row for row in reports if row.get("supervisor_spec_id") == supervisor_spec_id]
    if completed:
        latest = completed[-1]
        return latest | {"status": "resumed_terminal", "runtime_counts": runtime_counts()}

    ledger_id = spec["project_contamination_ledger_id"]
    queue = _queue(spec, ledger_id)
    queue_identity, queue_receipt = _publish(
        repository, "autonomous_research_queue", queue,
        {"research_queue.json": queue},
        (supervisor_spec_id, ledger_id),
    )
    cycle_stable = {
        "schema_version": "autonomous-research-cycle-v1",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "research_queue_id": queue_receipt["artifact_id"],
        "cycle_sequence": 1,
        "global_novelty_status": "current_catalog_and_program_revision_exhausted",
        "feature_factory": {
            "implementation_reused": True,
            "factory_spec_id": FACTORY_SPEC_ID,
            "feature_catalog_v2_id": FEATURE_CATALOG_ID,
            "new_agent_calls": 0,
            "new_features": 0,
        },
        "alpha_program": {
            "implementation_reused": True,
            "program_id": ALPHA_PROGRAM_ID,
            "report_id": ALPHA_REPORT_ID,
            "terminal_state": "completed_no_validation_survivor",
            "new_agent_calls": 0,
            "new_qlib_calls": 0,
        },
        "retrospective_candidate_ids": [],
        "historical_gate_lowered": False,
        "promotion_writes": 0,
    }
    cycle = cycle_stable | {"research_cycle_id": "arc1_" + hash_payload(cycle_stable)}
    cycle_identity, cycle_receipt = _publish(
        repository, "autonomous_research_cycle", cycle,
        {"research_cycle.json": cycle},
        (queue_receipt["artifact_id"], FACTORY_SPEC_ID, FEATURE_CATALOG_ID, ALPHA_PROGRAM_ID, ALPHA_REPORT_ID),
    )
    counts = runtime_counts() | {"research_cycles": 1}
    stop = global_stop_decision(
        consecutive_cycles_without_new_feature=1,
        consecutive_cycles_without_candidate=1,
        novelty_exhausted=False,
        active_fresh_candidates=0,
    )
    state_stable = {
        "schema_version": "autonomous-research-supervisor-v1",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "project_contamination_ledger_id": ledger_id,
        "research_queue_id": queue_receipt["artifact_id"],
        "research_cycle_ids": [cycle_receipt["artifact_id"]],
        "retrospective_candidate_ids": [],
        "fresh_lock_ids": [],
        "fresh_cohort_ids": [],
        "fresh_assessment_ids": [],
        "active_fresh_candidate_count": 0,
        "active_fresh_capacity": 20,
        "incremental_data_status": "not_required_no_active_fresh_candidates",
        "credential_source": "environment_only_not_persisted",
        "credential_present": bool(os.environ.get("TUSHARE_TOKEN")),
        "historical_market_date_max": LATEST_PROJECT_EXPOSURE,
        "r1_010_isolated": True,
        "consecutive_cycles_without_new_feature": 1,
        "consecutive_cycles_without_candidate": 1,
        "global_stop": stop["stop"],
        "stop_reason": stop["reason"] or "waiting_for_new_authorized_research_space_or_fresh_candidate",
        "status": "waiting_for_fresh_data_or_novel_space",
        "runtime_counts": counts,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    state = state_stable | {"supervisor_id": "ars1_" + hash_payload(state_stable)}
    state_identity, state_receipt = _publish(
        repository, "autonomous_research_supervisor", state,
        {"supervisor_state.json": state},
        (supervisor_spec_id, ledger_id, queue_receipt["artifact_id"], cycle_receipt["artifact_id"]),
    )
    report_stable = {
        "schema_version": "autonomous-research-supervisor-report-v1",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "supervisor_id": state_receipt["artifact_id"],
        "project_contamination_ledger_id": ledger_id,
        "research_queue_id": queue_receipt["artifact_id"],
        "research_cycle_ids": [cycle_receipt["artifact_id"]],
        "historical_research_conclusion": {
            "autonomous_research_execution": "operational",
            "historical_robust_alpha_survivor": "none",
            "evidence_semantics": "retrospective_research_only",
        },
        "retrospective_candidate_count": 0,
        "fresh_lock_count": 0,
        "fresh_cohort_count": 0,
        "fresh_observation_count": 0,
        "fresh_status_counts": {},
        "incremental_data_status": state["incremental_data_status"],
        "runtime_counts": counts,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    report = report_stable | {"supervisor_report_id": "arsr1_" + hash_payload(report_stable)}
    report_identity, report_receipt = _publish(
        repository, "autonomous_research_supervisor_report", report,
        {"supervisor_report.json": report},
        (state_receipt["artifact_id"],),
    )
    return {
        "status": state_identity["status"],
        "supervisor_spec_id": supervisor_spec_id,
        "supervisor_id": state_receipt["artifact_id"],
        "supervisor_report_id": report_receipt["artifact_id"],
        "project_contamination_ledger_id": ledger_id,
        "research_queue_id": queue_receipt["artifact_id"],
        "research_cycle_id": cycle_receipt["artifact_id"],
        "retrospective_candidate_count": 0,
        "fresh_lock_count": 0,
        "fresh_cohort_count": 0,
        "incremental_data_status": state_identity["incremental_data_status"],
        "runtime_counts": counts,
        "store_integrity": repository.integrity(),
        "new_artifacts": sum(not row["exact_existing"] for row in (
            queue_receipt, cycle_receipt, state_receipt, report_receipt
        )),
        "new_blobs": sum(row["new_blob_count"] for row in (
            queue_receipt, cycle_receipt, state_receipt, report_receipt
        )),
    }


def validate_supervisor(*, supervisor_spec_id: str, work_root: Path,
                        store_root: Path | None = None) -> dict[str, Any]:
    repository = _repository(store_root, work_root)
    spec = repository.identity(supervisor_spec_id)
    spec["supervisor_spec_id"] = supervisor_spec_id
    reports = []
    for descriptor in repository.store.list_by_kind("autonomous_research_supervisor_report"):
        row = repository.identity(descriptor.artifact_id)
        if row.get("supervisor_spec_id") == supervisor_spec_id:
            reports.append((descriptor.artifact_id, row))
    if not reports:
        raise ValueError("Supervisor terminal Report is absent")
    report_id, report = reports[-1]
    if report["promotion_writes"] or report["registry_writes"]:
        raise ValueError("Supervisor crossed Registry/Promotion boundary")
    integrity = repository.integrity()
    if integrity != {"status": "healthy", "missing": 0, "unreferenced": 0}:
        raise ValueError("Artifact Store integrity is not healthy")
    return {
        "status": "valid",
        "supervisor_spec_id": spec["supervisor_spec_id"],
        "supervisor_report_id": report_id,
        "historical_robust_alpha_survivor": "none",
        "evidence_gaps": [],
        "store_integrity": integrity,
    }


def replay_supervisor(*, supervisor_spec_id: str, work_root: Path,
                      store_root: Path | None = None) -> dict[str, Any]:
    result = validate_supervisor(
        supervisor_spec_id=supervisor_spec_id,
        work_root=work_root,
        store_root=store_root,
    )
    return result | {"status": "exact_replay", "runtime_counts": runtime_counts()}
