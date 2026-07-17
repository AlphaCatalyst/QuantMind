from __future__ import annotations

import json
from pathlib import Path

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.factor_registry import load_registry_snapshot
from backend.services.engine.research_campaign import validate_campaign
from backend.services.engine.research_campaign.models import CampaignConfig
from backend.services.engine.artifact_store.validators import DomainValidationContext

from .cache import domain_service_root
from .models import ArtifactRuntimeContext, ExactReplayResult, ResolvedArtifact
from .resolver import resolve_artifact
from .publisher import publish_domain_artifact
from .resolver import _validation_context


def _publish(
    context: ArtifactRuntimeContext,
    artifact_kind: ArtifactKind,
    artifact_id: str,
    staging_root: str | Path,
    *,
    lineage: tuple[str, ...] = (),
    validation_context=None,
):
    return publish_domain_artifact(
        context, artifact_kind.value, artifact_id, staging_root,
        lineage=lineage, validation_context=validation_context,
    )


def publish_factor_values(context, artifact_id, staging_root, *, lineage=(), validation_context=None):
    return _publish(context, ArtifactKind.FACTOR_VALUES, artifact_id, staging_root,
                    lineage=lineage, validation_context=validation_context)


def publish_optimization_study(context, artifact_id, staging_root, *, lineage=(), validation_context=None):
    return _publish(context, ArtifactKind.FACTOR_OPTIMIZATION, artifact_id, staging_root,
                    lineage=lineage, validation_context=validation_context)


def publish_validation_result(context, artifact_id, staging_root, *, lineage=()):
    return _publish(context, ArtifactKind.FACTOR_VALIDATION_RESULT, artifact_id,
                    staging_root, lineage=lineage)


def publish_frozen_result(context, artifact_id, staging_root, *, lineage=()):
    return _publish(context, ArtifactKind.FROZEN_TEST_RESULT, artifact_id,
                    staging_root, lineage=lineage)


def publish_registry_snapshot(context, artifact_id, staging_root, *, lineage=()):
    return _publish(context, ArtifactKind.FACTOR_REGISTRY, artifact_id,
                    staging_root, lineage=lineage)


def publish_research_campaign(context, artifact_id, staging_root, *, lineage=()):
    return _publish(context, ArtifactKind.RESEARCH_CAMPAIGN, artifact_id,
                    staging_root, lineage=lineage)


def publish_fresh_admission(context, artifact_id, staging_root, *, lineage=()):
    return _publish(context, ArtifactKind.FRESH_VALIDATION_ADMISSION, artifact_id,
                    staging_root, lineage=lineage)


def prepare_campaign_config(
    context: ArtifactRuntimeContext,
    *,
    snapshot_id: str,
    validation_dataset_id: str,
    registry_snapshot_id: str,
    execution_root: str | Path,
) -> CampaignConfig:
    """Resolve all immutable Campaign inputs before any Agent call."""
    snapshot = resolve_artifact(
        context, ArtifactKind.DATASET_SNAPSHOT.value, snapshot_id
    )
    validation = resolve_artifact(
        context, ArtifactKind.VALIDATION_DATASET.value, validation_dataset_id
    )
    registry = resolve_artifact(
        context, ArtifactKind.FACTOR_REGISTRY.value, registry_snapshot_id
    )
    for descriptor in context.store.list_by_kind(
        ArtifactKind.FACTOR_OPTIMIZATION.value
    ):
        resolve_artifact(
            context, ArtifactKind.FACTOR_OPTIMIZATION.value,
            descriptor.artifact_id,
        )
    root = Path(execution_root)
    return CampaignConfig(
        str(root / "campaign-artifacts"),
        str(domain_service_root(snapshot.materialized_root, snapshot.reference.artifact_kind)),
        snapshot_id,
        str(domain_service_root(validation.materialized_root, validation.reference.artifact_kind)),
        validation_dataset_id,
        str(domain_service_root(registry.materialized_root, registry.reference.artifact_kind)),
        registry_snapshot_id,
        str(root / "factor-values"),
        str(root / "optimization"),
        str(context.cache_root / "collections" / "optimization"),
        str(root / "registry"),
    )


def publish_campaign_execution(
    context: ArtifactRuntimeContext,
    config: CampaignConfig,
    campaign_artifact: dict,
) -> dict:
    """Publish a completed local Campaign graph, failing if any Store import fails."""
    campaign_id = campaign_artifact["campaign_id"]
    memory = json.loads(
        (Path(campaign_artifact["path"]) / "memory.json").read_text(encoding="utf-8")
    )
    validation_context = DomainValidationContext(
        Path(config.snapshot_root), Path(config.factor_values_root)
    )
    studies = tuple(sorted(set(memory.get("optimization_studies", ()))))
    published_values = []
    for study_id in studies:
        study_root = Path(config.optimization_root) / study_id
        values_ids = tuple(sorted(
            row["factor_values_id"]
            for path in (study_root / "trials").glob("*.json")
            for row in (json.loads(path.read_text(encoding="utf-8")),)
            if row.get("factor_values_id")
        ))
        for values_id in values_ids:
            published_values.append(publish_factor_values(
                context, values_id, Path(config.factor_values_root) / values_id,
                lineage=(config.snapshot_id,),
                validation_context=validation_context,
            ))
        publish_optimization_study(
            context, study_id, study_root,
            lineage=(config.snapshot_id, *values_ids),
            validation_context=validation_context,
        )
    campaign = publish_research_campaign(
        context, campaign_id, campaign_artifact["path"], lineage=studies
    )
    registry_after = campaign_artifact["result"]["registry_snapshot_after"]
    registry = None
    if registry_after != config.registry_snapshot_id:
        registry = publish_registry_snapshot(
            context,
            registry_after,
            Path(config.registry_output_root) / "snapshots" / registry_after,
            lineage=(config.registry_snapshot_id, campaign_id),
        )
    return {
        **campaign.safe_summary(),
        "factor_values_published": len(published_values),
        "optimization_studies_published": len(studies),
        "registry_snapshot_id": registry_after,
        "registry_published": registry is not None,
        "agent_calls": campaign_artifact["result"]["agent_calls"],
    }


def resolve_factor_values(context: ArtifactRuntimeContext, factor_values_id: str) -> ResolvedArtifact:
    return resolve_artifact(context, ArtifactKind.FACTOR_VALUES.value, factor_values_id)


def replay_optimization_study(context: ArtifactRuntimeContext, study_id: str) -> ExactReplayResult:
    resolved = resolve_artifact(
        context, ArtifactKind.FACTOR_OPTIMIZATION.value, study_id
    )
    return ExactReplayResult(resolved)


def resolve_validation_result(context: ArtifactRuntimeContext, result_id: str) -> ResolvedArtifact:
    return resolve_artifact(
        context, ArtifactKind.FACTOR_VALIDATION_RESULT.value, result_id
    )


def resolve_frozen_result(context: ArtifactRuntimeContext, result_id: str) -> ResolvedArtifact:
    return resolve_artifact(context, ArtifactKind.FROZEN_TEST_RESULT.value, result_id)


def load_registry_snapshot_store(context: ArtifactRuntimeContext, snapshot_id: str):
    resolved = resolve_artifact(context, ArtifactKind.FACTOR_REGISTRY.value, snapshot_id)
    root = domain_service_root(resolved.materialized_root, ArtifactKind.FACTOR_REGISTRY.value)
    return load_registry_snapshot(root, snapshot_id), resolved


def replay_research_campaign(context: ArtifactRuntimeContext, campaign_id: str) -> ExactReplayResult:
    resolved = resolve_artifact(
        context, ArtifactKind.RESEARCH_CAMPAIGN.value, campaign_id
    )
    root = domain_service_root(resolved.materialized_root, ArtifactKind.RESEARCH_CAMPAIGN.value)
    validate_campaign(root, campaign_id, exact_existing=True)
    return ExactReplayResult(resolved, True, 0, 0, 0)


def resolve_fresh_admission(context: ArtifactRuntimeContext, result_id: str) -> ResolvedArtifact:
    return resolve_artifact(
        context, ArtifactKind.FRESH_VALIDATION_ADMISSION.value, result_id
    )


def inspect_optimization_replay(result: ExactReplayResult) -> dict:
    manifest = json.loads(
        (result.resolved.materialized_root / "manifest.json").read_text(encoding="utf-8")
    )
    return {
        **result.safe_summary(),
        "result_id": manifest["result_id"],
        "trial_count": manifest["trial_count"],
        "eligible_count": manifest["eligible_count"],
        "predictive_claim": False,
    }


def inspect_campaign_replay(result: ExactReplayResult) -> dict:
    historical = json.loads(
        (result.resolved.materialized_root / "result.json").read_text(encoding="utf-8")
    )
    return {
        **result.safe_summary(),
        "historical_result_id": historical["result_id"],
        "historical_provider_id": historical["provider_id"],
        "historical_model_id": historical["model_id"],
        "replay_agent_calls": 0,
        "replay_optimization_calls": 0,
        "replay_registry_writes": 0,
    }


def publish_existing_artifact(
    context: ArtifactRuntimeContext,
    artifact_kind: str,
    artifact_id: str,
):
    resolved = resolve_artifact(context, artifact_kind, artifact_id)
    descriptor = context.store.get_descriptor(artifact_id)
    validation_context = _validation_context(
        context, artifact_kind, descriptor.lineage, (artifact_id,)
    )
    return publish_domain_artifact(
        context,
        artifact_kind,
        artifact_id,
        resolved.materialized_root,
        lineage=descriptor.lineage,
        validation_context=validation_context,
    )
