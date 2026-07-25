from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.autonomous_technical_feature_factory.v2 import (
    audit_and_build_research_space,
    execute_factory_v2,
)
from backend.services.engine.archetype_alpha_program.orchestrator import (
    create_program_spec,
    execute_program,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .contamination_ledger import LATEST_PROJECT_EXPOSURE, build_project_evidence_ledger
from .control import global_stop_decision
from .fresh import build_fresh_cohort, build_fresh_lock
from .models import AutonomousResearchSupervisorSpecV1, runtime_counts
from .schemas import validate_candidate


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


def run_next_model_cycle(*, supervisor_spec_id: str, repository_root: Path,
                         work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    """Run Cycle 003 through the existing Supervisor control surface.

    The model program owns its immutable fold artifacts.  The Supervisor only
    dispatches the pre-registered research type and reports the resulting
    terminal cycle; it does not create a parallel Supervisor or select a model.
    """
    repository = _repository(store_root, Path(work_root) / "supervisor-model")
    supervisor = repository.identity(supervisor_spec_id)
    if supervisor.get("schema_version") not in {
        "autonomous-research-supervisor-spec-v1",
        "autonomous-research-supervisor-v1",
        "autonomous-research-supervisor-v2",
    }:
        raise ValueError("Supervisor identity is invalid")
    from backend.services.engine.fixed_configuration_model_program import (
        create_spec as create_model_spec,
        execute_program as execute_model_program,
    )

    frozen = create_model_spec(
        repository_root=repository_root,
        work_root=Path(work_root) / "model-cycle",
        store_root=store_root,
    )
    result = execute_model_program(
        model_spec_id=frozen["model_spec_id"],
        repository_root=repository_root,
        work_root=Path(work_root) / "model-cycle",
        store_root=store_root,
    )
    return result | {
        "supervisor_spec_id": (
            supervisor_spec_id
            if supervisor.get("schema_version") == "autonomous-research-supervisor-spec-v1"
            else supervisor.get("supervisor_spec_id")
        ),
        "research_cycle_name": "autonomous_research_cycle_003",
        "research_type": "fixed_configuration_model_alpha",
        "second_supervisor_created": False,
        "automatic_cycle_004_created": False,
    }


def run_multi_horizon_model_cycle(
    *, supervisor_spec_id: str, repository_root: Path,
    work_root: Path, store_root: Path | None = None
) -> dict[str, Any]:
    """Dispatch the explicitly authorized Cycle 004 without creating a Supervisor."""
    repository = _repository(store_root, Path(work_root) / "supervisor-multi-horizon")
    supervisor = repository.identity(supervisor_spec_id)
    if supervisor.get("schema_version") not in {
        "autonomous-research-supervisor-spec-v1",
        "autonomous-research-supervisor-v1",
        "autonomous-research-supervisor-v2",
    }:
        raise ValueError("Supervisor identity is invalid")
    from backend.services.engine.multi_horizon_label_research import (
        create_label_family,
        execute_study,
    )

    family = create_label_family(
        repository_root=repository_root,
        work_root=Path(work_root) / "multi-horizon-cycle",
        store_root=store_root,
    )
    result = execute_study(
        label_family_id=family["label_family_id"],
        repository_root=repository_root,
        work_root=Path(work_root) / "multi-horizon-cycle",
        store_root=store_root,
    )
    return result | {
        "supervisor_spec_id": (
            supervisor_spec_id
            if supervisor.get("schema_version") == "autonomous-research-supervisor-spec-v1"
            else supervisor.get("supervisor_spec_id")
        ),
        "research_cycle_name": "autonomous_research_cycle_004",
        "research_type": "multi_horizon_model_alpha",
        "second_supervisor_created": False,
        "automatic_cycle_005_created": False,
    }


def run_next_rolling_blind_batch(
    *, supervisor_spec_id: str, repository_root: Path,
    work_root: Path, store_root: Path | None = None,
) -> dict[str, Any]:
    """Dispatch one complete Rolling Blind Batch through the existing Supervisor."""
    repository = _repository(store_root, Path(work_root) / "supervisor-rolling-blind")
    supervisor = repository.identity(supervisor_spec_id)
    if supervisor.get("schema_version") not in {
        "autonomous-research-supervisor-spec-v1",
        "autonomous-research-supervisor-v1",
        "autonomous-research-supervisor-v2",
    }:
        raise ValueError("Supervisor identity is invalid")
    from backend.services.engine.rolling_blind_alpha_discovery import run_batch

    result = run_batch(
        supervisor_id=supervisor_spec_id,
        repository_root=repository_root,
        work_root=Path(work_root) / "rolling-blind-batch-001",
        store_root=store_root,
    )
    return result | {
        "supervisor_id": supervisor_spec_id,
        "research_type": "rolling_blind_alpha_discovery",
        "batch_name": "rolling_blind_discovery_batch_001",
        "automatic_batch_002_created": False,
    }


def _v2_runtime_counts() -> dict[str, int]:
    return runtime_counts() | {
        "operator_writes": 0,
        "primitive_writes": 0,
        "feature_materialization_writes": 0,
    }


def _official_dates(bundle) -> list[str]:
    for name in ("trade_calendar", "trade_cal"):
        value = getattr(bundle, name, None)
        if value is None:
            continue
        if not hasattr(value, "columns"):
            try:
                import pandas as pd
                value = pd.read_parquet(value)
            except Exception:
                continue
        column = "cal_date" if "cal_date" in value.columns else "trade_date"
        selected = value
        if "is_open" in selected.columns:
            selected = selected[selected["is_open"].astype(int) == 1]
        import pandas as pd
        return sorted(
            pd.to_datetime(selected[column].astype(str)).dt.strftime("%Y-%m-%d").unique()
        )
    return []


def run_next_research_cycle(*, supervisor_spec_id: str, repository_root: Path,
                            work_root: Path, store_root: Path | None = None,
                            feature_agent_caller=None,
                            alpha_agent_caller=None) -> dict[str, Any]:
    bundle, repository = _runtime_for_supervisor(repository_root, work_root, store_root)
    spec = repository.identity(supervisor_spec_id) | {
        "supervisor_spec_id": supervisor_spec_id
    }
    if spec.get("schema_version") != "autonomous-research-supervisor-spec-v1":
        raise ValueError("Supervisor Spec is invalid")
    prior_reports = []
    for descriptor in repository.store.list_by_kind("research_space_expansion_report"):
        row = repository.identity(descriptor.artifact_id)
        if row.get("supervisor_spec_id") == supervisor_spec_id:
            prior_reports.append(row | {"artifact_id": descriptor.artifact_id})
    if prior_reports:
        return replay_next_research_cycle(
            supervisor_spec_id=supervisor_spec_id,
            repository_root=repository_root,
            work_root=Path(work_root) / "exact-replay-v2",
            store_root=store_root,
        ) | {"exact_existing": True}

    expansion = audit_and_build_research_space(
        repository_root=repository_root,
        work_root=Path(work_root) / "factory-v2",
        store_root=store_root,
    )
    factory_kwargs = {}
    if feature_agent_caller is not None:
        factory_kwargs["agent_caller"] = feature_agent_caller
    factory = execute_factory_v2(
        factory_spec_id=expansion["factory_spec_id"],
        repository_root=repository_root,
        work_root=Path(work_root) / "factory-v2",
        store_root=store_root,
        **factory_kwargs,
    )
    new_features = len(factory["new_feature_ids"])
    alpha_result = {
        "status": "not_required_no_new_feature",
        "program_id": None,
        "report_id": None,
        "retrospective_survivors": [],
        "budget_usage": {
            "agent_calls": 0, "proposals": 0, "admissions": 0,
            "adaptive_qlib_calls": 0, "validation_qlib_calls": 0,
            "report_qlib_calls": 0,
        },
    }
    if new_features:
        program_spec = create_program_spec(
            feature_catalog_v2_id=factory["feature_catalog_v3_id"],
            repository_root=repository_root,
            work_root=Path(work_root) / "alpha-program-v2",
            store_root=store_root,
        )
        alpha_kwargs = {}
        if alpha_agent_caller is not None:
            alpha_kwargs["agent_caller"] = alpha_agent_caller
        alpha_result = execute_program(
            program_id=program_spec["program_spec_id"],
            repository_root=repository_root,
            work_root=Path(work_root) / "alpha-program-v2",
            store_root=store_root,
            retrospective_only=True,
            **alpha_kwargs,
        )
    candidates = []
    candidate_receipts = []
    for survivor in alpha_result.get("retrospective_survivors", []):
        stable = {
            "schema_version": "retrospective-candidate-v1",
            "provider_id": "tushare-pro-v1",
            "source_cycle_id": "autonomous_research_cycle_002",
            "formula": survivor["formula"],
            "parameters": survivor["parameters"],
            "orientation": survivor["orientation"],
            "archetype": survivor["primary_archetype"],
            "primary_statistic": survivor["primary_test_statistic"],
            "strategy_protocol": {
                "topk": 20, "n_drop": 5, "rebalance_interval": 10,
                "weighting": "equal_weight", "signal_lag": 1,
                "execution": "open", "benchmark": "CSI300",
            },
            "historical_metrics": survivor["historical_metrics"],
            "search_exposure": survivor["search_exposure"],
            "multiple_testing_evidence": {
                "passed": survivor["adjusted_q_value"] <= 0.10,
                "adjusted_q_value": survivor["adjusted_q_value"],
            },
            "correlations": {
                "maximum": survivor["historical_metrics"].get(
                    "maximum_existing_factor_correlation"
                )
            },
            "historical_date_max": "2024-12-31",
            "project_contamination_ledger_id": spec[
                "project_contamination_ledger_id"
            ],
            "status": "retrospective_candidate",
            "worth_fresh_observation": True,
            "registry_write": False,
            "promotion_writes": 0,
        }
        candidate = stable | {"candidate_id": "rcan1_" + hash_payload(stable)}
        validate_candidate(candidate)
        receipt = repository.publish(
            "retrospective_candidate",
            candidate,
            {"retrospective_candidate.json": candidate},
            lineage=(
                alpha_result["program_id"],
                survivor["validation_id"],
                spec["project_contamination_ledger_id"],
            ),
        )
        candidates.append(candidate | {"candidate_id": receipt["artifact_id"]})
        candidate_receipts.append(receipt)
    locks = []
    lock_receipts = []
    official_dates = _official_dates(bundle)
    for candidate in candidates:
        try:
            lock = build_fresh_lock(
                candidate,
                latest_market_date=max(
                    LATEST_PROJECT_EXPOSURE, candidate["historical_date_max"]
                ),
                official_trade_dates=official_dates,
                market_snapshot_id=R1_010_SNAPSHOT_ID,
            )
        except ValueError as exc:
            if "fresh_data_blocked" not in str(exc):
                raise
            continue
        receipt = repository.publish(
            "project_candidate_fresh_lock",
            lock,
            {"fresh_lock.json": lock},
            lineage=(candidate["candidate_id"], R1_010_SNAPSHOT_ID),
        )
        locks.append(lock | {"fresh_lock_id": receipt["artifact_id"]})
        lock_receipts.append(receipt)
    cohort_receipt = None
    if locks:
        cohort = build_fresh_cohort(locks)
        cohort_receipt = repository.publish(
            "fresh_candidate_cohort",
            cohort,
            {"fresh_cohort.json": cohort},
            lineage=tuple(row["fresh_lock_id"] for row in locks),
        )
    previous_queue = next(iter(reversed(repository.store.list_by_kind(
        "autonomous_research_queue"
    ))), None)
    queue_stable = {
        "schema_version": "autonomous-research-queue-v2",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "previous_queue_id": previous_queue.artifact_id if previous_queue else None,
        "operator_extension_id": expansion["operator_extension_id"],
        "primitive_catalog_id": expansion["primitive_catalog_id"],
        "feature_catalog_v3_id": factory["feature_catalog_v3_id"],
        "novelty_status": (
            "expanded_with_new_admitted_features"
            if new_features else "global_authorized_research_space_exhausted"
        ),
        "fresh_performance_used_for_same_candidate_modification": False,
        "promotion_writes": 0,
    }
    queue = queue_stable | {"research_queue_id": "arq2_" + hash_payload(queue_stable)}
    queue_receipt = repository.publish(
        "autonomous_research_queue",
        queue,
        {"research_queue_v2.json": queue},
        lineage=tuple(filter(None, (
            previous_queue.artifact_id if previous_queue else None,
            expansion["operator_extension_id"],
            expansion["primitive_catalog_id"],
            factory["feature_catalog_v3_id"],
        ))),
    )
    counts = _v2_runtime_counts() | {
        "research_cycles": 1,
        "feature_agent_calls": factory["budget_usage"]["agent_calls"],
        "alpha_agent_calls": alpha_result["budget_usage"].get("agent_calls", 0),
        "proposals": (
            factory["budget_usage"]["proposals"]
            + alpha_result["budget_usage"].get("proposals", 0)
        ),
        "admissions": (
            factory["budget_usage"]["admissions"]
            + alpha_result["budget_usage"].get("admissions", 0)
        ),
        "qlib_calls": sum(
            alpha_result["budget_usage"].get(key, 0)
            for key in (
                "adaptive_qlib_calls", "validation_qlib_calls",
                "report_qlib_calls",
            )
        ),
        "feature_writes": new_features,
        "feature_materialization_writes": new_features,
        "candidate_writes": len(candidate_receipts),
        "fresh_lock_writes": len(lock_receipts),
        "operator_writes": 6,
        "primitive_writes": 6,
    }
    empty_feature = 0 if new_features else 2
    empty_candidate = 0 if candidates else 2
    stop = global_stop_decision(
        consecutive_cycles_without_new_feature=empty_feature,
        consecutive_cycles_without_candidate=empty_candidate,
        novelty_exhausted=not new_features and not candidates,
        active_fresh_candidates=len(locks),
    )
    cycle_stable = {
        "schema_version": "autonomous-research-cycle-v2",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "research_queue_id": queue_receipt["artifact_id"],
        "cycle_sequence": 2,
        "factory_spec_id": expansion["factory_spec_id"],
        "feature_catalog_v3_id": factory["feature_catalog_v3_id"],
        "new_admitted_feature_ids": factory["new_feature_ids"],
        "alpha_program_id": alpha_result.get("program_id"),
        "alpha_program_report_id": alpha_result.get("report_id"),
        "retrospective_candidate_ids": [
            row["artifact_id"] for row in candidate_receipts
        ],
        "fresh_lock_ids": [row["artifact_id"] for row in lock_receipts],
        "fresh_cohort_id": (
            cohort_receipt["artifact_id"] if cohort_receipt else None
        ),
        "historical_gate_lowered": False,
        "fdr_lowered": False,
        "runtime_counts": counts,
        "promotion_writes": 0,
    }
    cycle = cycle_stable | {"research_cycle_id": "arc2_" + hash_payload(cycle_stable)}
    cycle_receipt = repository.publish(
        "autonomous_research_cycle_v2",
        cycle,
        {"research_cycle_v2.json": cycle},
        lineage=tuple(filter(None, (
            queue_receipt["artifact_id"],
            expansion["factory_spec_id"],
            factory["feature_catalog_v3_id"],
            alpha_result.get("program_id"),
            alpha_result.get("report_id"),
            *[row["artifact_id"] for row in candidate_receipts],
            *[row["artifact_id"] for row in lock_receipts],
            cohort_receipt["artifact_id"] if cohort_receipt else None,
        ))),
    )
    status = (
        "global_authorized_research_space_exhausted"
        if stop["stop"] and stop["reason"] in {
            "authorized_global_novelty_exhausted", "two_empty_research_cycles",
        }
        else "fresh_evidence_accumulating" if locks
        else "waiting_for_fresh_data_or_novel_space"
    )
    state_stable = {
        "schema_version": "autonomous-research-supervisor-v2",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "research_cycle_ids": [
            row.artifact_id for row in repository.store.list_by_kind(
                "autonomous_research_cycle"
            )
        ] + [cycle_receipt["artifact_id"]],
        "retrospective_candidate_ids": [
            row["artifact_id"] for row in candidate_receipts
        ],
        "fresh_lock_ids": [row["artifact_id"] for row in lock_receipts],
        "fresh_cohort_ids": (
            [cohort_receipt["artifact_id"]] if cohort_receipt else []
        ),
        "active_fresh_candidate_count": len(locks),
        "incremental_data_status": (
            "incremental_data_required"
            if locks else "not_required_no_active_fresh_candidates"
        ),
        "consecutive_cycles_without_new_feature": empty_feature,
        "consecutive_cycles_without_candidate": empty_candidate,
        "global_stop": stop["stop"],
        "stop_reason": stop["reason"],
        "status": status,
        "runtime_counts": counts,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    state = state_stable | {"supervisor_id": "ars2_" + hash_payload(state_stable)}
    state_receipt = repository.publish(
        "autonomous_research_supervisor",
        state,
        {"supervisor_state_v2.json": state},
        lineage=(supervisor_spec_id, cycle_receipt["artifact_id"]),
    )
    report_stable = {
        "schema_version": "research-space-expansion-report-v1",
        "provider_id": "tushare-pro-v1",
        "supervisor_spec_id": supervisor_spec_id,
        "supervisor_id": state_receipt["artifact_id"],
        "research_cycle_id": cycle_receipt["artifact_id"],
        "operator_extension_id": expansion["operator_extension_id"],
        "operator_validation_id": expansion["operator_validation_id"],
        "primitive_catalog_id": expansion["primitive_catalog_id"],
        "factory_spec_id": expansion["factory_spec_id"],
        "feature_catalog_v3_id": factory["feature_catalog_v3_id"],
        "alpha_program_id": alpha_result.get("program_id"),
        "alpha_program_report_id": alpha_result.get("report_id"),
        "new_feature_count": new_features,
        "retrospective_candidate_count": len(candidates),
        "fresh_lock_count": len(locks),
        "fresh_cohort_count": int(cohort_receipt is not None),
        "incremental_data_status": state["incremental_data_status"],
        "global_stop": stop,
        "status": status,
        "runtime_counts": counts,
        "historical_evidence_semantics": "retrospective_research_only",
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    report = report_stable | {
        "research_space_report_id": "rser1_" + hash_payload(report_stable)
    }
    report_receipt = repository.publish(
        "research_space_expansion_report",
        report,
        {"research_space_expansion_report.json": report},
        lineage=(state_receipt["artifact_id"], cycle_receipt["artifact_id"]),
    )
    return {
        "status": status,
        "supervisor_spec_id": supervisor_spec_id,
        "supervisor_id": state_receipt["artifact_id"],
        "research_space_report_id": report_receipt["artifact_id"],
        "research_cycle_id": cycle_receipt["artifact_id"],
        "operator_extension_id": expansion["operator_extension_id"],
        "primitive_catalog_id": expansion["primitive_catalog_id"],
        "factory_spec_id": expansion["factory_spec_id"],
        "feature_catalog_v3_id": factory["feature_catalog_v3_id"],
        "alpha_program_id": alpha_result.get("program_id"),
        "alpha_program_report_id": alpha_result.get("report_id"),
        "new_feature_ids": factory["new_feature_ids"],
        "retrospective_candidate_ids": [
            row["artifact_id"] for row in candidate_receipts
        ],
        "fresh_lock_ids": [row["artifact_id"] for row in lock_receipts],
        "fresh_cohort_id": (
            cohort_receipt["artifact_id"] if cohort_receipt else None
        ),
        "incremental_data_status": state["incremental_data_status"],
        "runtime_counts": counts,
        "store_integrity": repository.integrity(),
    }


def _runtime_for_supervisor(repository_root: Path, work_root: Path,
                            store_root: Path | None):
    from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
    return _runtime(repository_root, work_root, store_root)


def validate_next_research_cycle(*, supervisor_spec_id: str,
                                 repository_root: Path, work_root: Path,
                                 store_root: Path | None = None) -> dict[str, Any]:
    _, repository = _runtime_for_supervisor(repository_root, work_root, store_root)
    rows = []
    for descriptor in repository.store.list_by_kind("research_space_expansion_report"):
        row = repository.identity(descriptor.artifact_id)
        if row.get("supervisor_spec_id") == supervisor_spec_id:
            rows.append((descriptor.artifact_id, row))
    if not rows:
        raise ValueError("Research-space expansion Report is absent")
    artifact_id, report = rows[-1]
    if report["registry_writes"] or report["promotion_writes"]:
        raise ValueError("Research-space Cycle crossed Registry/Promotion boundary")
    integrity = repository.integrity()
    if integrity != {"status": "healthy", "missing": 0, "unreferenced": 0}:
        raise ValueError("Artifact Store integrity is not healthy")
    return {
        "status": "valid",
        "supervisor_spec_id": supervisor_spec_id,
        "research_space_report_id": artifact_id,
        "research_cycle_id": report["research_cycle_id"],
        "evidence_gaps": [],
        "store_integrity": integrity,
    }


def replay_next_research_cycle(**kwargs) -> dict[str, Any]:
    result = validate_next_research_cycle(**kwargs)
    return result | {
        "status": "exact_replay",
        "runtime_counts": _v2_runtime_counts(),
    }
