from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from backend.services.engine.artifact_store.canonical import hash_file
from backend.services.engine.artifact_store.models import StoredArtifactDescriptor

from .errors import ArtifactResolutionError


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def descriptor_lock(descriptor_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(descriptor_id, threading.Lock())


def collection_destination(cache_root: Path, artifact_kind: str, artifact_id: str) -> Path:
    layout = {
        "dataset_snapshot": ("dataset", "snapshots"),
        "factor_values": ("factor-values",),
        "factor_optimization": ("optimization",),
        "validation_dataset": ("validation-data", "datasets"),
        "factor_validation_result": ("validation-artifacts", "results"),
        "frozen_test_result": ("validation-artifacts", "frozen"),
        "factor_registry": ("registry", "snapshots"),
        "registry_reconciliation": ("registry-reconciliation", "reconciliations"),
        "fresh_validation_admission": ("fresh-admission",),
        "research_campaign": ("campaign-artifacts", "campaigns"),
        "fresh_validation_accrual": ("fresh-accrual",),
        "fresh_validation_result": ("fresh-results", "results"),
        "implementation_evidence": ("implementation-evidence",),
        "generic_research_bundle": ("generic",),
        "unified_signal": ("unified-signal",),
        "portfolio_target": ("portfolio-target",),
        "strategy_backtest_result": ("strategy-results",),
        "strategy_research_registry": ("strategy-registry",),
        "strategy_optimization_study": ("strategy-optimization", "studies"),
        "strategy_optimization_trial": ("strategy-optimization", "trials"),
        "strategy_parameter_candidate_lock": ("strategy-optimization", "candidates"),
        "strategy_optimization_result": ("strategy-optimization", "results"),
        "existing_factor_definition_audit": ("expanded-factor-iteration", "existing-audit"),
        "tushare_feature_catalog_v2": ("expanded-factor-iteration", "feature-catalog"),
        "tushare_feature_dataset_v2": ("expanded-factor-iteration", "feature-dataset"),
        "agent_factor_iteration_v2": ("expanded-factor-iteration", "experiments"),
        "agent_factor_round_result": ("expanded-factor-iteration", "rounds"),
        "agent_factor_candidate_lock": ("expanded-factor-iteration", "candidates"),
        "agent_factor_iteration_assessment": ("expanded-factor-iteration", "assessments"),
        "momentum_feature_catalog": ("momentum-factor-iteration", "feature-catalog"),
        "momentum_feature_dataset": ("momentum-factor-iteration", "feature-dataset"),
        "momentum_factor_iteration": ("momentum-factor-iteration", "experiments"),
        "momentum_factor_round_result": ("momentum-factor-iteration", "rounds"),
        "momentum_factor_candidate_lock": ("momentum-factor-iteration", "candidates"),
        "momentum_factor_ensemble": ("momentum-factor-iteration", "ensembles"),
        "momentum_iteration_assessment": ("momentum-factor-iteration", "assessments"),
        "research_agent_raw_response": ("skip-recent-momentum", "agent-responses"),
        "research_proposal": ("skip-recent-momentum", "proposals"),
        "factor_template_definition": ("skip-recent-momentum", "templates"),
        "factor_optimization_trial_detail": ("skip-recent-momentum", "trials"),
        "factor_fold_candidate_lock": ("skip-recent-momentum", "fold-locks"),
        "factor_candidate_eligibility_evidence": ("skip-recent-momentum", "eligibility"),
        "skip_recent_momentum_experiment": ("skip-recent-momentum", "experiments"),
        "skip_recent_momentum_candidate_lock": ("skip-recent-momentum", "candidates"),
        "skip_recent_momentum_report": ("skip-recent-momentum", "reports"),
        "skip_recent_momentum_assessment": ("skip-recent-momentum", "assessments"),
        "momentum_semantic_audit": ("momentum-alpha-diagnostics", "semantics"),
        "momentum_alpha_decomposition": ("momentum-alpha-diagnostics", "decompositions"),
        "momentum_cross_sectional_diagnostic": ("momentum-alpha-diagnostics", "cross-sectional"),
        "momentum_style_exposure_report": ("momentum-alpha-diagnostics", "style"),
        "momentum_failure_classification": ("momentum-alpha-diagnostics", "classifications"),
        "parameter_optimization_ablation_spec": ("parameter-optimization-ablation", "specs"),
        "factor_optimization_ablation": ("parameter-optimization-ablation", "factor"),
        "strategy_optimization_ablation": ("parameter-optimization-ablation", "strategy"),
        "combined_optimization_ablation": ("parameter-optimization-ablation", "combined"),
        "optimization_trial_rank_stability": ("parameter-optimization-ablation", "rank-stability"),
        "optimization_overfit_assessment": ("parameter-optimization-ablation", "assessments"),
        "optimization_governance_decision": ("optimization-governance", "decisions"),
        "factor_optimization_policy": ("optimization-governance", "factor-policies"),
        "strategy_optimization_policy": ("optimization-governance", "strategy-policies"),
        "combined_optimization_policy": ("optimization-governance", "combined-policies"),
        "default_parameter_evaluation": ("default-first-momentum", "default-evaluations"),
        "local_factor_rescue_study": ("default-first-momentum", "local-rescues"),
        "development_parameter_lock": ("default-first-momentum", "development-locks"),
        "default_first_momentum_annual_evaluation": ("default-first-momentum", "annual-evaluations"),
        "default_first_momentum_eligibility_evidence": ("default-first-momentum", "eligibility"),
        "default_first_momentum_candidate_lock": ("default-first-momentum", "candidates"),
        "default_first_momentum_report": ("default-first-momentum", "reports"),
        "default_first_momentum_assessment": ("default-first-momentum", "assessments"),
        "default_first_momentum_experiment": ("default-first-momentum", "experiments"),
        "low_frequency_momentum_signal_spec": ("low-frequency-momentum", "signal-specs"),
        "low_frequency_execution_protocol": ("low-frequency-momentum", "protocols"),
        "low_frequency_momentum_annual_result": ("low-frequency-momentum", "annual-results"),
        "low_frequency_momentum_candidate_lock": ("low-frequency-momentum", "candidates"),
        "low_frequency_momentum_report": ("low-frequency-momentum", "reports"),
        "low_frequency_momentum_assessment": ("low-frequency-momentum", "assessments"),
        "low_frequency_momentum_study": ("low-frequency-momentum", "studies"),
        "momentum_tail_alpha_diagnostic": ("momentum-tail-alpha", "diagnostics"),
        "momentum_quantile_return_report": ("momentum-tail-alpha", "quantiles"),
        "momentum_rank_transition_report": ("momentum-tail-alpha", "transitions"),
        "momentum_tail_style_exposure": ("momentum-tail-alpha", "style"),
        "momentum_tail_signal_classification": ("momentum-tail-alpha", "classifications"),
        "breadth_momentum_gate_spec": ("breadth-gated-momentum", "gate-specs"),
        "breadth_gated_momentum_historical_diagnostic": ("breadth-gated-momentum", "historical"),
        "breadth_gated_momentum_fresh_lock": ("breadth-gated-momentum", "fresh-locks"),
        "tushare_incremental_market_snapshot": ("breadth-gated-momentum", "incremental-data"),
        "breadth_gated_momentum_fresh_observation": ("breadth-gated-momentum", "fresh-observations"),
        "breadth_gated_momentum_fresh_assessment": ("breadth-gated-momentum", "fresh-assessments"),
        "tushare_historical_round_lock": ("tushare-round-lock",),
        "tushare_qlib_backtest_result": ("tushare-qlib-results",),
    }
    try:
        parts = layout[artifact_kind]
    except KeyError as exc:
        raise ArtifactResolutionError("Artifact kind has no runtime cache layout") from exc
    return cache_root.joinpath("collections", *parts, artifact_id)


def domain_service_root(destination: Path, artifact_kind: str) -> Path:
    if artifact_kind in {
        "dataset_snapshot", "validation_dataset", "factor_validation_result",
        "frozen_test_result", "factor_registry", "registry_reconciliation",
        "research_campaign", "fresh_validation_result",
    }:
        return destination.parents[1]
    return destination.parent


def cache_record_path(cache_root: Path, descriptor_id: str) -> Path:
    return cache_root / "descriptors" / descriptor_id / "CACHE.json"


def cache_payload(descriptor: StoredArtifactDescriptor, destination: Path, cache_root: Path) -> dict:
    return {
        "schema_version": "artifact-runtime-cache-v1",
        "descriptor_id": descriptor.descriptor_id,
        "artifact_kind": descriptor.artifact_kind,
        "artifact_id": descriptor.artifact_id,
        "materialized_relative_path": destination.relative_to(cache_root).as_posix(),
        "files": [
            {"relative_path": item.relative_path, "sha256": item.sha256, "size_bytes": item.size_bytes}
            for item in descriptor.files
        ],
    }


def validate_cached_copy(
    cache_root: Path,
    descriptor: StoredArtifactDescriptor,
    destination: Path,
) -> bool:
    record = cache_record_path(cache_root, descriptor.descriptor_id)
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload != cache_payload(descriptor, destination, cache_root):
        return False
    if not destination.is_dir():
        return False
    expected = {item.relative_path for item in descriptor.files}
    actual = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*") if path.is_file()
    }
    if actual != expected:
        return False
    return all(
        not (destination / item.relative_path).is_symlink()
        and hash_file(destination / item.relative_path) == (item.sha256, item.size_bytes)
        for item in descriptor.files
    )


def write_cache_record(
    cache_root: Path,
    descriptor: StoredArtifactDescriptor,
    destination: Path,
) -> None:
    record = cache_record_path(cache_root, descriptor.descriptor_id)
    record.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        cache_payload(descriptor, destination, cache_root),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    temporary = record.with_name(".CACHE.json.tmp")
    temporary.write_bytes(payload)
    temporary.replace(record)


def discard_cached_copy(cache_root: Path, descriptor: StoredArtifactDescriptor, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    record_dir = cache_record_path(cache_root, descriptor.descriptor_id).parent
    if record_dir.exists():
        shutil.rmtree(record_dir)
