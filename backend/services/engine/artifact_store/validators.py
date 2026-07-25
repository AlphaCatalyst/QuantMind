from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .canonical import hash_file
from .enums import ArtifactKind
from .errors import DomainValidationError
from .models import DomainValidation


ID_FIELDS = (
    "snapshot_id", "factor_values_id", "study_id", "dataset_id", "result_id",
    "registry_snapshot_id", "reconciliation_id", "campaign_id",
    "universe_lock_id", "experiment_id", "round_lock_id", "evaluation_id",
    "backtest_result_id", "holdout_result_id", "assessment_id",
    "signal_missingness_audit_id", "historical_backtest_followup_id",
    "qlib_view_id", "authority_record_id", "purge_plan_id", "purge_result_id",
    "memory_id",
    "historical_experiment_registry_id",
    "historical_experiment_lifecycle_followup_id",
    "termination_followup_id",
    "raw_snapshot_id", "event_artifact_id", "benchmark_contract_id",
    "benchmark_revision_id", "benchmark_followup_id",
    "unified_signal_artifact_id", "portfolio_target_artifact_id",
    "strategy_backtest_result_id", "strategy_research_registry_id",
    "strategy_optimization_study_id", "strategy_optimization_trial_id",
    "strategy_parameter_candidate_lock_id", "strategy_optimization_result_id",
    "audit_id", "catalog_id", "feature_dataset_id", "round_result_id",
    "candidate_lock_id", "ensemble_id",
    "raw_response_artifact_id", "proposal_artifact_id", "template_definition_id",
    "trial_detail_id", "fold_lock_id", "eligibility_evidence_id", "report_id",
    "gate_spec_id", "historical_diagnostic_id", "fresh_lock_id",
    "incremental_snapshot_id", "fresh_observation_id", "fresh_assessment_id",
    "campaign_spec_id", "round_plan_id", "near_miss_id",
    "factory_spec_id", "feature_proposal_id", "feature_admission_id",
    "feature_materialization_id", "novelty_index_id", "feature_catalog_v2_id",
    "archetype_contract_id", "program_spec_id", "union_shortlist_lock_id",
    "validation_id", "multiple_testing_id", "validation_failure_id",
    "exposure_ledger_id", "supervisor_spec_id", "supervisor_id",
    "research_queue_id", "research_cycle_id", "candidate_id",
    "fresh_cohort_id", "fresh_market_snapshot_id", "fresh_multiple_testing_id",
    "operator_extension_id", "operator_validation_id", "primitive_catalog_id",
    "primitive_materialization_id", "feature_catalog_v3_id",
    "research_space_report_id",
    "model_spec_id", "bundle_id", "walk_forward_spec_id", "leakage_audit_id",
    "fold_model_id", "prediction_artifact_id", "fold_result_id",
    "stability_assessment_id", "distillation_queue_id",
    "model_fresh_candidate_cohort_id", "fresh_model_training_event_id",
    "fresh_model_bundle_membership_id", "fresh_model_prediction_id",
    "fresh_model_label_observation_id", "fresh_model_strategy_observation_id",
    "fresh_model_candidate_observation_id",
    "fresh_model_cohort_multiple_testing_id",
    "fresh_model_candidate_assessment_id", "fresh_model_heartbeat_run_id",
    "fresh_heartbeat_scheduler_status_id", "fresh_heartbeat_operational_run_id",
    "fresh_runtime_path_audit_id", "fresh_runtime_app_snapshot_id",
    "fresh_runtime_environment_snapshot_id", "fresh_runtime_state_migration_id",
    "fresh_runtime_deployment_status_id",
    "tmp_cleanup_assessment_id", "diagnostic_whitelist_id",
    "redaction_guard_id", "exposure_record_id",
    "fresh_runtime_hardening_status_id",
    "environment_validation_tmp_assessment_id",
    "fresh_runtime_status_consistency_validation_id",
    "canonical_runtime_artifact_resolution_id",
    "fresh_runtime_hardening_completion_id",
)


@dataclass(frozen=True)
class DomainValidationContext:
    snapshot_root: Path | None = None
    factor_values_root: Path | None = None


@dataclass(frozen=True)
class ValidatedDomainArtifact:
    artifact_id: str
    source_protocol: str
    source_manifest_sha256: str
    validation: DomainValidation


def _manifest(source: Path) -> tuple[dict, Path]:
    path = source / "manifest.json"
    if not path.is_file():
        raise DomainValidationError("trusted research artifact requires manifest.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainValidationError("research artifact Manifest is unreadable") from exc
    if not isinstance(value, dict):
        raise DomainValidationError("research artifact Manifest must be an object")
    return value, path


def _artifact_id(manifest: dict, expected: str | None) -> str:
    present = [manifest[name] for name in ID_FIELDS if isinstance(manifest.get(name), str)]
    if expected:
        if present and expected not in present:
            raise DomainValidationError("expected Domain Artifact ID differs from Manifest")
        return expected
    if not present:
        raise DomainValidationError("Manifest does not expose a recognized Domain Artifact ID")
    return present[0]


def _verify_manifest_hashes(source: Path, manifest: dict) -> None:
    hashes = manifest.get("file_hashes", {})
    if hashes is None:
        return
    if not isinstance(hashes, dict):
        raise DomainValidationError("Manifest file_hashes must be an object")
    for relative, expected in hashes.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise DomainValidationError("Manifest file hash entry is invalid")
        path = source / relative
        try:
            path.resolve().relative_to(source.resolve())
        except ValueError as exc:
            raise DomainValidationError("Manifest file path escapes source") from exc
        if not path.is_file() or hash_file(path)[0] != expected:
            raise DomainValidationError("Manifest-declared file hash mismatch")


def _formal_validate(kind: ArtifactKind, source: Path, artifact_id: str,
                     context: DomainValidationContext) -> str:
    if kind in {
        ArtifactKind.MOMENTUM_FEATURE_CATALOG,
        ArtifactKind.MOMENTUM_FEATURE_DATASET,
        ArtifactKind.MOMENTUM_FACTOR_ITERATION,
        ArtifactKind.MOMENTUM_FACTOR_ROUND_RESULT,
        ArtifactKind.MOMENTUM_FACTOR_CANDIDATE_LOCK,
        ArtifactKind.MOMENTUM_FACTOR_ENSEMBLE,
        ArtifactKind.MOMENTUM_ITERATION_ASSESSMENT,
    }:
        from backend.services.engine.momentum_factor_iteration.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "momentum_factor_iteration.validate_artifact"
    if kind in {
        ArtifactKind.RESEARCH_AGENT_RAW_RESPONSE,
        ArtifactKind.RESEARCH_PROPOSAL,
        ArtifactKind.FACTOR_TEMPLATE_DEFINITION,
        ArtifactKind.FACTOR_OPTIMIZATION_TRIAL_DETAIL,
        ArtifactKind.FACTOR_FOLD_CANDIDATE_LOCK,
        ArtifactKind.FACTOR_CANDIDATE_ELIGIBILITY_EVIDENCE,
        ArtifactKind.SKIP_RECENT_MOMENTUM_EXPERIMENT,
        ArtifactKind.SKIP_RECENT_MOMENTUM_CANDIDATE_LOCK,
        ArtifactKind.SKIP_RECENT_MOMENTUM_REPORT,
        ArtifactKind.SKIP_RECENT_MOMENTUM_ASSESSMENT,
    }:
        from backend.services.engine.skip_recent_momentum.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "skip_recent_momentum.validate_artifact"
    if kind in {
        ArtifactKind.MOMENTUM_SEMANTIC_AUDIT,
        ArtifactKind.MOMENTUM_ALPHA_DECOMPOSITION,
        ArtifactKind.MOMENTUM_CROSS_SECTIONAL_DIAGNOSTIC,
        ArtifactKind.MOMENTUM_STYLE_EXPOSURE_REPORT,
        ArtifactKind.MOMENTUM_FAILURE_CLASSIFICATION,
    }:
        from backend.services.engine.momentum_alpha_diagnostics.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "momentum_alpha_diagnostics.validate_artifact"
    if kind in {
        ArtifactKind.PARAMETER_OPTIMIZATION_ABLATION_SPEC,
        ArtifactKind.FACTOR_OPTIMIZATION_ABLATION,
        ArtifactKind.STRATEGY_OPTIMIZATION_ABLATION,
        ArtifactKind.COMBINED_OPTIMIZATION_ABLATION,
        ArtifactKind.OPTIMIZATION_TRIAL_RANK_STABILITY,
        ArtifactKind.OPTIMIZATION_OVERFIT_ASSESSMENT,
    }:
        from backend.services.engine.parameter_optimization_ablation.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "parameter_optimization_ablation.validate_artifact"
    if kind in {
        ArtifactKind.OPTIMIZATION_GOVERNANCE_DECISION,
        ArtifactKind.FACTOR_OPTIMIZATION_POLICY,
        ArtifactKind.STRATEGY_OPTIMIZATION_POLICY,
        ArtifactKind.COMBINED_OPTIMIZATION_POLICY,
    }:
        from backend.services.engine.optimization_governance.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "optimization_governance.validate_artifact"
    if kind in {
        ArtifactKind.DEFAULT_PARAMETER_EVALUATION,
        ArtifactKind.LOCAL_FACTOR_RESCUE_STUDY,
        ArtifactKind.DEVELOPMENT_PARAMETER_LOCK,
        ArtifactKind.DEFAULT_FIRST_MOMENTUM_ANNUAL_EVALUATION,
        ArtifactKind.DEFAULT_FIRST_MOMENTUM_ELIGIBILITY_EVIDENCE,
        ArtifactKind.DEFAULT_FIRST_MOMENTUM_CANDIDATE_LOCK,
        ArtifactKind.DEFAULT_FIRST_MOMENTUM_REPORT,
        ArtifactKind.DEFAULT_FIRST_MOMENTUM_ASSESSMENT,
        ArtifactKind.DEFAULT_FIRST_MOMENTUM_EXPERIMENT,
    }:
        from backend.services.engine.default_first_momentum_search.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "default_first_momentum_search.validate_artifact"
    if kind in {
        ArtifactKind.LOW_FREQUENCY_MOMENTUM_SIGNAL_SPEC,
        ArtifactKind.LOW_FREQUENCY_EXECUTION_PROTOCOL,
        ArtifactKind.LOW_FREQUENCY_MOMENTUM_ANNUAL_RESULT,
        ArtifactKind.LOW_FREQUENCY_MOMENTUM_CANDIDATE_LOCK,
        ArtifactKind.LOW_FREQUENCY_MOMENTUM_REPORT,
        ArtifactKind.LOW_FREQUENCY_MOMENTUM_ASSESSMENT,
        ArtifactKind.LOW_FREQUENCY_MOMENTUM_STUDY,
    }:
        from backend.services.engine.low_frequency_momentum.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "low_frequency_momentum.validate_artifact"
    if kind in {
        ArtifactKind.MOMENTUM_TAIL_ALPHA_DIAGNOSTIC,
        ArtifactKind.MOMENTUM_QUANTILE_RETURN_REPORT,
        ArtifactKind.MOMENTUM_RANK_TRANSITION_REPORT,
        ArtifactKind.MOMENTUM_TAIL_STYLE_EXPOSURE,
        ArtifactKind.MOMENTUM_TAIL_SIGNAL_CLASSIFICATION,
    }:
        from backend.services.engine.momentum_tail_alpha.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "momentum_tail_alpha.validate_artifact"
    if kind in {
        ArtifactKind.BREADTH_MOMENTUM_GATE_SPEC,
        ArtifactKind.BREADTH_GATED_MOMENTUM_HISTORICAL_DIAGNOSTIC,
        ArtifactKind.BREADTH_GATED_MOMENTUM_FRESH_LOCK,
        ArtifactKind.TUSHARE_INCREMENTAL_MARKET_SNAPSHOT,
        ArtifactKind.BREADTH_GATED_MOMENTUM_FRESH_OBSERVATION,
        ArtifactKind.BREADTH_GATED_MOMENTUM_FRESH_ASSESSMENT,
    }:
        from backend.services.engine.breadth_gated_momentum.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "breadth_gated_momentum.validate_artifact"
    if kind in {
        ArtifactKind.AUTONOMOUS_FACTOR_CAMPAIGN_SPEC,
        ArtifactKind.AUTONOMOUS_FACTOR_CAMPAIGN,
        ArtifactKind.AUTONOMOUS_FACTOR_ROUND,
        ArtifactKind.AUTONOMOUS_FACTOR_PROPOSAL,
        ArtifactKind.AUTONOMOUS_FACTOR_FAILURE_MEMORY,
        ArtifactKind.AUTONOMOUS_FACTOR_ROUND_PLAN,
        ArtifactKind.AUTONOMOUS_FACTOR_CANDIDATE_LOCK,
        ArtifactKind.AUTONOMOUS_FACTOR_NEAR_MISS,
        ArtifactKind.AUTONOMOUS_FACTOR_CAMPAIGN_REPORT,
        ArtifactKind.AUTONOMOUS_FACTOR_VALUE_MATERIALIZATION,
        ArtifactKind.AUTONOMOUS_FACTOR_CAMPAIGN_SPEC_V2,
        ArtifactKind.CAMPAIGN_EVIDENCE_PARTITION,
        ArtifactKind.CLEAN_ROOM_CAMPAIGN_SEED_MEMORY,
        ArtifactKind.CANDIDATE_SEARCH_EXPOSURE,
        ArtifactKind.AUTONOMOUS_CAMPAIGN_SHORTLIST_LOCK,
        ArtifactKind.CAMPAIGN_FAILURE_MEMORY_FREEZE,
        ArtifactKind.LOCKED_HOLDOUT_EVALUATION,
        ArtifactKind.AUTONOMOUS_HOLDOUT_FAILURE_REPORT,
        ArtifactKind.AUTONOMOUS_CAMPAIGN_V1_GENERALIZATION_ASSESSMENT,
        ArtifactKind.AUTONOMOUS_CANDIDATE_FRESH_LOCK,
        ArtifactKind.AUTONOMOUS_FACTOR_CAMPAIGN_REPORT_V2,
        ArtifactKind.AUTONOMOUS_FACTOR_RESEARCH_PROGRAM_SPEC,
        ArtifactKind.RESEARCH_PROGRAM_EVIDENCE_PARTITION,
        ArtifactKind.RESEARCH_PROGRAM_CLEAN_ROOM_SEED,
        ArtifactKind.AUTONOMOUS_FACTOR_PROGRAM,
        ArtifactKind.AUTONOMOUS_FACTOR_LANE,
        ArtifactKind.AUTONOMOUS_LANE_SHORTLIST_LOCK,
        ArtifactKind.GLOBAL_RESEARCH_NOVELTY_INDEX,
        ArtifactKind.PROGRAM_SEARCH_EXPOSURE,
        ArtifactKind.AUTONOMOUS_PROGRAM_UNION_SHORTLIST_LOCK,
        ArtifactKind.PROGRAM_LOCKED_VALIDATION,
        ArtifactKind.PROGRAM_MULTIPLE_TESTING_CONTROL,
        ArtifactKind.PROGRAM_VALIDATION_FAILURE_REPORT,
        ArtifactKind.AUTONOMOUS_PROGRAM_CANDIDATE_FRESH_LOCK,
        ArtifactKind.AUTONOMOUS_FACTOR_PROGRAM_REPORT,
        ArtifactKind.AUTONOMOUS_TECHNICAL_FEATURE_FACTORY_SPEC,
        ArtifactKind.TECHNICAL_FEATURE_PROPOSAL,
        ArtifactKind.TECHNICAL_FEATURE_ADMISSION,
        ArtifactKind.TECHNICAL_FEATURE_MATERIALIZATION,
        ArtifactKind.TECHNICAL_FEATURE_NOVELTY_INDEX,
        ArtifactKind.TECHNICAL_FEATURE_CATALOG_V2,
        ArtifactKind.ALPHA_ARCHETYPE_CONTRACT,
        ArtifactKind.ARCHETYPE_AWARE_PROGRAM_SPEC,
        ArtifactKind.ARCHETYPE_AWARE_ALPHA_PROPOSAL,
        ArtifactKind.ARCHETYPE_AWARE_UNION_SHORTLIST_LOCK,
        ArtifactKind.MONOTONIC_ALPHA_VALIDATION,
        ArtifactKind.TAIL_ALPHA_VALIDATION,
        ArtifactKind.ARCHETYPE_MULTIPLE_TESTING_CONTROL,
        ArtifactKind.ARCHETYPE_ALPHA_VALIDATION_FAILURE,
        ArtifactKind.ARCHETYPE_ALPHA_FRESH_LOCK,
        ArtifactKind.ARCHETYPE_AWARE_PROGRAM_REPORT,
        ArtifactKind.PROJECT_EVIDENCE_EXPOSURE_LEDGER,
        ArtifactKind.AUTONOMOUS_RESEARCH_SUPERVISOR_SPEC,
        ArtifactKind.AUTONOMOUS_RESEARCH_SUPERVISOR,
        ArtifactKind.AUTONOMOUS_RESEARCH_QUEUE,
        ArtifactKind.AUTONOMOUS_RESEARCH_CYCLE,
        ArtifactKind.RETROSPECTIVE_CANDIDATE,
        ArtifactKind.PROJECT_CANDIDATE_FRESH_LOCK,
        ArtifactKind.FRESH_CANDIDATE_COHORT,
        ArtifactKind.FRESH_MARKET_SNAPSHOT,
        ArtifactKind.FRESH_CANDIDATE_OBSERVATION,
        ArtifactKind.FRESH_COHORT_MULTIPLE_TESTING,
        ArtifactKind.FRESH_CANDIDATE_ASSESSMENT,
        ArtifactKind.AUTONOMOUS_RESEARCH_SUPERVISOR_REPORT,
        ArtifactKind.TECHNICAL_DSL_OPERATOR_EXTENSION,
        ArtifactKind.TECHNICAL_DSL_OPERATOR_VALIDATION,
        ArtifactKind.TECHNICAL_PRIMITIVE_CATALOG,
        ArtifactKind.TECHNICAL_PRIMITIVE_MATERIALIZATION,
        ArtifactKind.AUTONOMOUS_TECHNICAL_FEATURE_FACTORY_SPEC_V2,
        ArtifactKind.TECHNICAL_FEATURE_CATALOG_V3,
        ArtifactKind.AUTONOMOUS_RESEARCH_CYCLE_V2,
        ArtifactKind.RESEARCH_SPACE_EXPANSION_REPORT,
        ArtifactKind.FIXED_CONFIGURATION_MODEL_SPEC,
        ArtifactKind.MODEL_FEATURE_BUNDLE_SPEC,
        ArtifactKind.PURGED_WALK_FORWARD_SPEC,
        ArtifactKind.MODEL_TRAINING_LEAKAGE_AUDIT,
        ArtifactKind.MODEL_FOLD_TRAINING,
        ArtifactKind.MODEL_FOLD_PREDICTION,
        ArtifactKind.MODEL_FOLD_RESULT,
        ArtifactKind.MODEL_STABILITY_ASSESSMENT,
        ArtifactKind.MODEL_MULTIPLE_TESTING_CONTROL,
        ArtifactKind.RETROSPECTIVE_MODEL_CANDIDATE,
        ArtifactKind.MODEL_FACTOR_DISTILLATION_QUEUE,
        ArtifactKind.PROJECT_MODEL_CANDIDATE_FRESH_LOCK,
        ArtifactKind.MODEL_FRESH_OBSERVATION,
        ArtifactKind.MODEL_FRESH_ASSESSMENT,
        ArtifactKind.TECHNICAL_RETURN_LABEL_FAMILY,
        ArtifactKind.TECHNICAL_RETURN_LABEL,
        ArtifactKind.EXECUTABLE_LABEL_AUDIT,
        ArtifactKind.LABEL_QUALITY_ASSESSMENT,
        ArtifactKind.MULTI_HORIZON_MODEL_FOLD_RESULT,
        ArtifactKind.HORIZON_ALIGNMENT_ASSESSMENT,
        ArtifactKind.MULTI_HORIZON_MULTIPLE_TESTING,
        ArtifactKind.MULTI_HORIZON_RETROSPECTIVE_MODEL_CANDIDATE,
        ArtifactKind.MULTI_HORIZON_MODEL_FRESH_LOCK,
        ArtifactKind.MULTI_HORIZON_LABEL_RESEARCH_REPORT,
        ArtifactKind.MODEL_FRESH_CANDIDATE_COHORT,
        ArtifactKind.FRESH_MODEL_TRAINING_EVENT,
        ArtifactKind.FRESH_MODEL_BUNDLE_MEMBERSHIP,
        ArtifactKind.FRESH_MODEL_PREDICTION,
        ArtifactKind.FRESH_MODEL_LABEL_OBSERVATION,
        ArtifactKind.FRESH_MODEL_STRATEGY_OBSERVATION,
        ArtifactKind.FRESH_MODEL_CANDIDATE_OBSERVATION,
        ArtifactKind.FRESH_MODEL_COHORT_MULTIPLE_TESTING,
        ArtifactKind.FRESH_MODEL_CANDIDATE_ASSESSMENT,
        ArtifactKind.FRESH_MODEL_HEARTBEAT_RUN,
        ArtifactKind.FRESH_HEARTBEAT_SCHEDULER_STATUS,
        ArtifactKind.FRESH_HEARTBEAT_OPERATIONAL_RUN,
        ArtifactKind.FRESH_RUNTIME_PATH_AUDIT,
        ArtifactKind.FRESH_RUNTIME_APP_SNAPSHOT,
        ArtifactKind.FRESH_RUNTIME_ENVIRONMENT_SNAPSHOT,
        ArtifactKind.FRESH_RUNTIME_STATE_MIGRATION,
            ArtifactKind.FRESH_RUNTIME_DEPLOYMENT_STATUS,
            ArtifactKind.FRESH_HEARTBEAT_TMP_CLEANUP_ASSESSMENT,
            ArtifactKind.RUNTIME_DIAGNOSTIC_WHITELIST,
            ArtifactKind.RUNTIME_DIAGNOSTIC_REDACTION_GUARD,
            ArtifactKind.HISTORICAL_SESSION_DIAGNOSTIC_EXPOSURE_RECORD,
            ArtifactKind.FRESH_RUNTIME_HARDENING_STATUS,
            ArtifactKind.ENVIRONMENT_VALIDATION_TMP_ASSESSMENT,
            ArtifactKind.FRESH_RUNTIME_STATUS_CONSISTENCY_VALIDATION,
            ArtifactKind.CANONICAL_RUNTIME_ARTIFACT_RESOLUTION,
            ArtifactKind.FRESH_RUNTIME_HARDENING_COMPLETION,
            ArtifactKind.ROLLING_BLIND_WINDOW_SET,
            ArtifactKind.ROLLING_BLIND_DISCOVERY_BATCH,
            ArtifactKind.ROLLING_BLIND_CANDIDATE_BATCH_LOCK,
            ArtifactKind.ROLLING_BLIND_CANDIDATE_RESULT,
            ArtifactKind.ROLLING_BLIND_MULTIPLE_TESTING,
            ArtifactKind.ROLLING_BLIND_SEARCH_EXPOSURE,
            ArtifactKind.ROLLING_BLIND_ALPHA_SURVIVOR,
            ArtifactKind.ROLLING_BLIND_SUBMISSION_LEDGER,
            ArtifactKind.ROLLING_BLIND_RESEARCH_REPORT,
        }:
        from backend.services.engine.autonomous_factor_campaign.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "autonomous_factor_campaign.validate_artifact"
    if kind in {
        ArtifactKind.UNIFIED_SIGNAL,
        ArtifactKind.PORTFOLIO_TARGET,
        ArtifactKind.STRATEGY_BACKTEST_RESULT,
        ArtifactKind.STRATEGY_RESEARCH_REGISTRY,
    }:
        from backend.services.engine.strategy_layer.artifact import validate_strategy_domain_artifact
        validate_strategy_domain_artifact(source, artifact_id, kind.value)
        return "strategy_layer.validate_strategy_domain_artifact"
    if kind in {
        ArtifactKind.STRATEGY_OPTIMIZATION_STUDY,
        ArtifactKind.STRATEGY_OPTIMIZATION_TRIAL,
        ArtifactKind.STRATEGY_PARAMETER_CANDIDATE_LOCK,
        ArtifactKind.STRATEGY_OPTIMIZATION_RESULT,
    }:
        from backend.services.engine.strategy_optimization.artifact import validate_strategy_optimization_artifact
        validate_strategy_optimization_artifact(source, artifact_id, kind.value)
        return "strategy_optimization.validate_strategy_optimization_artifact"
    if kind in {
        ArtifactKind.EXISTING_FACTOR_DEFINITION_AUDIT,
        ArtifactKind.TUSHARE_FEATURE_CATALOG_V2,
        ArtifactKind.TUSHARE_FEATURE_DATASET_V2,
        ArtifactKind.AGENT_FACTOR_ITERATION_V2,
        ArtifactKind.AGENT_FACTOR_ROUND_RESULT,
        ArtifactKind.AGENT_FACTOR_CANDIDATE_LOCK,
        ArtifactKind.AGENT_FACTOR_ITERATION_ASSESSMENT,
    }:
        from backend.services.engine.expanded_factor_iteration.artifact import validate_artifact
        validate_artifact(source, artifact_id, kind.value)
        return "expanded_factor_iteration.validate_artifact"
    if kind is ArtifactKind.DATASET_SNAPSHOT:
        from backend.services.engine.market_data.feature_snapshot import LegacyFeatureSnapshotService
        LegacyFeatureSnapshotService(source.parents[1]).validate(artifact_id)
        return "LegacyFeatureSnapshotService.validate"
    if kind is ArtifactKind.FACTOR_VALUES:
        if context.snapshot_root is None:
            raise DomainValidationError("Factor Values validation requires Dataset Snapshot context")
        from backend.services.engine.factor_dsl.artifact import validate_values
        validate_values(context.snapshot_root, source.parent, artifact_id)
        return "factor_dsl.validate_values"
    if kind is ArtifactKind.FACTOR_OPTIMIZATION:
        if context.snapshot_root is None or context.factor_values_root is None:
            raise DomainValidationError("Optimization validation requires Snapshot and Factor Values context")
        from backend.services.engine.factor_dsl.admission import snapshot_contract
        from backend.services.engine.factor_optimization.artifact import validate_study
        from backend.services.engine.factor_optimization.enumerator import plan_study
        from backend.services.engine.factor_optimization.parser import parse_optimization_spec
        spec = parse_optimization_spec(json.loads((source / "spec.json").read_text()))
        study = plan_study(spec, snapshot_contract(context.snapshot_root, spec.snapshot_id))
        validate_study(study, context.snapshot_root, context.factor_values_root, source.parent)
        return "factor_optimization.validate_study"
    if kind is ArtifactKind.VALIDATION_DATASET:
        from backend.services.engine.factor_validation.dataset import validate_validation_dataset
        validate_validation_dataset(source.parents[1], artifact_id)
        return "factor_validation.validate_validation_dataset"
    if kind is ArtifactKind.FACTOR_VALIDATION_RESULT:
        from backend.services.engine.factor_validation.validation import validate_validation_result_directory
        validate_validation_result_directory(source, artifact_id)
        return "factor_validation.validate_validation_result_directory"
    if kind is ArtifactKind.FROZEN_TEST_RESULT:
        from backend.services.engine.factor_validation.frozen import validate_frozen_result
        validate_frozen_result(source.parents[1], artifact_id)
        return "factor_validation.validate_frozen_result"
    if kind is ArtifactKind.FACTOR_REGISTRY:
        from backend.services.engine.factor_registry.snapshot import validate_registry_snapshot
        validate_registry_snapshot(source.parents[1], artifact_id)
        return "factor_registry.validate_registry_snapshot"
    if kind is ArtifactKind.REGISTRY_RECONCILIATION:
        from backend.services.engine.factor_registry.reconciliation import validate_reconciliation
        validate_reconciliation(source.parents[1], artifact_id)
        return "factor_registry.validate_reconciliation"
    if kind is ArtifactKind.FRESH_VALIDATION_ADMISSION:
        from backend.services.engine.fresh_validation_admission.artifact import validate_admission_result
        validate_admission_result(source.parent, artifact_id)
        return "fresh_validation_admission.validate_admission_result"
    if kind is ArtifactKind.RESEARCH_CAMPAIGN:
        from backend.services.engine.research_campaign.artifact import validate_campaign
        validate_campaign(source.parents[1], artifact_id)
        return "research_campaign.validate_campaign"
    if kind is ArtifactKind.FRESH_VALIDATION_ACCRUAL:
        from backend.services.engine.fresh_validation.accrual import validate_accrual_snapshot
        validate_accrual_snapshot(source.parent, artifact_id)
        return "fresh_validation.validate_accrual_snapshot"
    if kind is ArtifactKind.FRESH_VALIDATION_RESULT:
        from backend.services.engine.fresh_validation.evaluation import validate_fresh_validation_result
        validate_fresh_validation_result(source.parents[1], artifact_id)
        return "fresh_validation.validate_fresh_validation_result"
    if kind in {ArtifactKind.IMPLEMENTATION_EVIDENCE, ArtifactKind.GENERIC_RESEARCH_BUNDLE}:
        return "artifact_store.manifest_hash_validator"
    if kind in {
        ArtifactKind.TUSHARE_CORPORATE_ACTION_RAW,
        ArtifactKind.SECURITY_CORPORATE_ACTION_EVENT,
        ArtifactKind.FIXED_UNIVERSE_BENCHMARK_CONTRACT,
        ArtifactKind.FIXED_UNIVERSE_BENCHMARK_REVISION,
        ArtifactKind.HISTORICAL_BACKTEST_BENCHMARK_FOLLOWUP,
    }:
        from backend.services.engine.corporate_actions.validation import (
            validate_domain_artifact as validate_corporate_action_artifact,
        )
        validate_corporate_action_artifact(source, artifact_id, kind.value)
        return "corporate_actions.validate_domain_artifact"
    if kind in {
        ArtifactKind.FIXED_UNIVERSE_LOCK,
        ArtifactKind.FIXED_UNIVERSE_HISTORICAL_DATASET,
        ArtifactKind.HISTORICAL_AGENT_EXPERIMENT,
        ArtifactKind.HISTORICAL_ROUND_LOCK,
        ArtifactKind.HISTORICAL_ROUND_EVALUATION,
        ArtifactKind.QLIB_BACKTEST_RESULT,
        ArtifactKind.HISTORICAL_HOLDOUT_RESULT,
        ArtifactKind.AGENT_ITERATION_ASSESSMENT,
        ArtifactKind.SIGNAL_MISSINGNESS_AUDIT,
        ArtifactKind.HISTORICAL_BACKTEST_FOLLOWUP,
    }:
        from backend.services.engine.historical_agent_experiment.artifact import validate_historical_artifact
        return validate_historical_artifact(kind.value, source, artifact_id)
    if kind in {
        ArtifactKind.TUSHARE_HISTORICAL_AGENT_EXPERIMENT,
        ArtifactKind.TUSHARE_HISTORICAL_ROUND_LOCK,
        ArtifactKind.TUSHARE_HISTORICAL_ROUND_EVALUATION,
        ArtifactKind.TUSHARE_QLIB_BACKTEST_RESULT,
        ArtifactKind.TUSHARE_HISTORICAL_HOLDOUT_RESULT,
        ArtifactKind.TUSHARE_AGENT_ITERATION_ASSESSMENT,
        ArtifactKind.TUSHARE_HISTORICAL_EXPERIMENT_REGISTRY,
        ArtifactKind.TUSHARE_HISTORICAL_EXPERIMENT_LIFECYCLE_FOLLOWUP,
        ArtifactKind.HISTORICAL_BACKTEST_TERMINATION_FOLLOWUP,
    }:
        from backend.services.engine.tushare_agent_experiment.artifact import (
            validate_experiment_artifact,
        )
        validate_experiment_artifact(source, artifact_id, expected_kind=kind.value)
        return "tushare_agent_experiment.validate_experiment_artifact"
    if kind.value.startswith("tushare_") or kind in {
        ArtifactKind.SANITIZED_RESEARCH_MEMORY,
        ArtifactKind.DATA_AUTHORITY_RECORD,
        ArtifactKind.LEGACY_DATA_PURGE_PLAN,
        ArtifactKind.LEGACY_DATA_PURGE_RESULT,
    }:
        from backend.services.engine.tushare_cutover.pipeline import validate_tushare_artifact
        validate_tushare_artifact(source, artifact_id, expected_kind=kind.value)
        return "tushare_cutover.validate_tushare_artifact"
    raise DomainValidationError("Artifact kind has no v1 Domain Validator")


def validate_domain_artifact(
    artifact_kind: str,
    source_directory: Path,
    *,
    expected_artifact_id: str | None = None,
    context: DomainValidationContext | None = None,
) -> ValidatedDomainArtifact:
    try:
        kind = ArtifactKind(artifact_kind)
    except ValueError as exc:
        raise DomainValidationError("unsupported Artifact kind") from exc
    source = Path(source_directory)
    manifest, manifest_path = _manifest(source)
    artifact_id = _artifact_id(manifest, expected_artifact_id)
    if not re.fullmatch(r"^[a-z][a-z0-9]*_[A-Za-z0-9._-]+$", artifact_id):
        raise DomainValidationError("Domain Artifact ID format is invalid")
    _verify_manifest_hashes(source, manifest)
    try:
        validator = _formal_validate(kind, source, artifact_id, context or DomainValidationContext())
    except DomainValidationError:
        raise
    except Exception as exc:
        raise DomainValidationError(f"formal Domain Validator rejected {artifact_kind}") from exc
    protocol = str(
        manifest.get("schema_version")
        or manifest.get("snapshot_schema_version")
        or "manifest-declared-v1"
    )
    return ValidatedDomainArtifact(
        artifact_id,
        protocol,
        hash_file(manifest_path)[0],
        DomainValidation(validator, "1.0.0", "valid"),
    )
