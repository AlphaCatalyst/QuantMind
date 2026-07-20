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
    "candidate_lock_id",
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
