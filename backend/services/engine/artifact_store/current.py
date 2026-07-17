from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .enums import ArtifactKind
from .reachability import build_reachability_plan
from .validators import DomainValidationContext


CANONICAL_REGISTRY_ID = "frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5"
CANDIDATE_LOCK_ID = "fvcl_716d7465285f7a8f541924877aa3acde9e90a38efe7d10dea2e20d6874063c7b"
PROTOCOL_ID = "fvp_93163e1b4f82b52154bf0472b1cd165916f8ecae722ab851dd7fc4210bb5a867"
EXPOSURE_LEDGER_ID = "rdel_56d95b77f42f5b9784badaf3558e92e375d87be9cc1194143e334aba3e55f5ff"
WATERMARK_ID = "fdw_3459fb5a20fb60707c6bf001dc194a931cfea7cddf250de2a099cba97efaa248"


@dataclass(frozen=True)
class CurrentArtifactSource:
    artifact_kind: str
    artifact_id: str
    source_directory: Path
    lineage: tuple[str, ...]
    validation_context: DomainValidationContext


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _trial_values(study_path: Path) -> tuple[str, ...]:
    values = []
    for path in sorted((study_path / "trials").glob("*.json")):
        value = _read(path).get("factor_values_id")
        if value:
            values.append(value)
    return tuple(sorted(set(values)))


def current_artifact_sources(repository_root: Path) -> tuple[CurrentArtifactSource, ...]:
    tmp = Path("/private/tmp")
    original_snapshot_root = tmp / "qm2-p0-003l-real-snapshot"
    validation_root = tmp / "qm2-p0-006-validation"
    validation_snapshot_root = validation_root / "snapshots"
    sources: dict[str, CurrentArtifactSource] = {}

    def add(kind: ArtifactKind, artifact_id: str, path: Path, lineage=(), context=None):
        sources[artifact_id] = CurrentArtifactSource(
            kind.value, artifact_id, path, tuple(sorted(set(lineage))),
            context or DomainValidationContext(),
        )

    ds_original = "ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7"
    ds_validation = "ds_dd1defb79ddf2a81f057be9e34715cb04df340204d68338f73ab1ad4692e338f"
    add(ArtifactKind.DATASET_SNAPSHOT, ds_original, original_snapshot_root / "snapshots" / ds_original)
    add(ArtifactKind.DATASET_SNAPSHOT, ds_validation, validation_snapshot_root / "snapshots" / ds_validation)

    study_groups = (
        (tmp / "qm2-p0-005-optimization", tmp / "qm2-p0-004-factor-values", original_snapshot_root),
        (tmp / "qm2-p0-008-final3" / "optimization", tmp / "qm2-p0-008-final3" / "factor-values", validation_snapshot_root),
        (tmp / "qm2-p0-008f-external4" / "optimization", tmp / "qm2-p0-008f-external4" / "factor-values", validation_snapshot_root),
    )
    for optimization_root, values_root, snapshot_root in study_groups:
        if not optimization_root.is_dir():
            continue
        for study_path in sorted(optimization_root.glob("fos_*")):
            manifest = _read(study_path / "manifest.json")
            study_id = manifest["study_id"]
            values_ids = _trial_values(study_path)
            snapshot_id = manifest["snapshot_id"]
            add(
                ArtifactKind.FACTOR_OPTIMIZATION, study_id, study_path,
                (snapshot_id, *values_ids),
                DomainValidationContext(snapshot_root, values_root),
            )
            for values_id in values_ids:
                add(
                    ArtifactKind.FACTOR_VALUES, values_id, values_root / values_id,
                    (snapshot_id,), DomainValidationContext(snapshot_root, values_root),
                )

    # Formal Validation uses full-period Factor Values distinct from Optimization values.
    validation_values_root = validation_root / "factor-values"
    for path in sorted(validation_values_root.glob("fv_*")):
        manifest = _read(path / "manifest.json")
        add(
            ArtifactKind.FACTOR_VALUES, manifest["factor_values_id"], path,
            (manifest["dataset_snapshot_id"],),
            DomainValidationContext(validation_snapshot_root, validation_values_root),
        )

    validation_dataset_id = "vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62"
    validation_result_id = "fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"
    frozen_result_id = "fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"
    add(ArtifactKind.VALIDATION_DATASET, validation_dataset_id,
        validation_root / "data" / "datasets" / validation_dataset_id, (ds_validation,))
    validation_result_path = validation_root / "artifacts" / "results" / validation_result_id
    validation_manifest = _read(validation_result_path / "manifest.json")
    validation_fv_ids = tuple(sorted(
        row["factor_values_id"] for row in validation_manifest["trial_results"]
    ))
    add(ArtifactKind.FACTOR_VALIDATION_RESULT, validation_result_id,
        validation_result_path, (validation_dataset_id, ds_validation, *validation_fv_ids))
    add(ArtifactKind.FROZEN_TEST_RESULT, frozen_result_id,
        validation_root / "artifacts" / "frozen" / frozen_result_id,
        (validation_result_id, validation_dataset_id))

    registry_sources = {
        "frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9": tmp / "qm2-p0-007-registry" / "snapshots",
        "frs_d40bfd7497ad56d3f71fd16dd7363222d32a5528e8780ca3765c27ca3c584718": tmp / "qm2-p0-008-final3" / "registry" / "snapshots",
        "frs_7ab0a844d791abf4dbd62c5558a7261078875bbc0b3606aa1b02ce591cf01054": tmp / "qm2-p0-008f-external4" / "registry" / "snapshots",
        "frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4": tmp / "qm2-p0-008g-final" / "registry" / "snapshots",
        CANONICAL_REGISTRY_ID: tmp / "qm2-p0-009" / "registry" / "snapshots",
    }
    baseline_campaign = "rc_4970d1419d17d1327b2092c7ff85cb52d680488555c6408ec3a8ef571219cd5f"
    external_campaign = "rc_0b13d7f235ac948a10c97092c6ce3bbad99ecdefc2c20c93c3648644a5d9401c"
    base_studies = tuple(sorted(p.name for p in (tmp / "qm2-p0-005-optimization").glob("fos_*")))
    add(ArtifactKind.FACTOR_REGISTRY, next(iter(registry_sources)),
        registry_sources[next(iter(registry_sources))] / next(iter(registry_sources)),
        (*base_studies, validation_result_id, frozen_result_id))
    add(ArtifactKind.RESEARCH_CAMPAIGN, baseline_campaign,
        tmp / "qm2-p0-008-final3" / "campaign-artifacts" / "campaigns" / baseline_campaign,
        tuple(sorted(p.name for p in (tmp / "qm2-p0-008-final3" / "optimization").glob("fos_*"))))
    add(ArtifactKind.RESEARCH_CAMPAIGN, external_campaign,
        tmp / "qm2-p0-008f-external4" / "campaign-artifacts" / "campaigns" / external_campaign,
        tuple(sorted(p.name for p in (tmp / "qm2-p0-008f-external4" / "optimization").glob("fos_*"))))
    ancestor, baseline_registry, external_registry, reconciled = tuple(registry_sources)[:4]
    add(ArtifactKind.FACTOR_REGISTRY, baseline_registry, registry_sources[baseline_registry] / baseline_registry,
        (ancestor, baseline_campaign))
    add(ArtifactKind.FACTOR_REGISTRY, external_registry, registry_sources[external_registry] / external_registry,
        (ancestor, external_campaign))
    reconciliation_id = "frr_9112702e368326365d6f4adb144633c7d0cf3ae59baa61ed76270ae86e93cb32"
    add(ArtifactKind.REGISTRY_RECONCILIATION, reconciliation_id,
        tmp / "qm2-p0-008g-final" / "registry-reconciliation" / "reconciliations" / reconciliation_id,
        (ancestor, baseline_registry, external_registry))
    admission_id = "fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab"
    add(ArtifactKind.FRESH_VALIDATION_ADMISSION, admission_id,
        tmp / "qm2-p0-008g-final" / "fresh-validation-admission" / admission_id,
        (baseline_campaign, external_campaign, reconciliation_id))
    add(ArtifactKind.FACTOR_REGISTRY, reconciled, registry_sources[reconciled] / reconciled,
        (reconciliation_id, admission_id))
    add(ArtifactKind.FACTOR_REGISTRY, CANONICAL_REGISTRY_ID,
        registry_sources[CANONICAL_REGISTRY_ID] / CANONICAL_REGISTRY_ID,
        (reconciled, CANDIDATE_LOCK_ID, PROTOCOL_ID, EXPOSURE_LEDGER_ID, WATERMARK_ID))
    return tuple(sorted(sources.values(), key=lambda item: (item.artifact_kind, item.artifact_id)))


def plan_current(repository_root: Path):
    sources = current_artifact_sources(repository_root)
    available = tuple(item.artifact_id for item in sources if item.source_directory.is_dir())
    lineage = {item.artifact_id: item.lineage for item in sources}
    missing_sources = tuple(item.artifact_id for item in sources if not item.source_directory.is_dir())
    # Missing runtime sources are deliberately included as unavailable graph nodes.
    plan = build_reachability_plan(
        root_ids=(CANONICAL_REGISTRY_ID, CANDIDATE_LOCK_ID, PROTOCOL_ID,
                  EXPOSURE_LEDGER_ID, WATERMARK_ID),
        lineage_by_artifact_id=lineage,
        available_artifact_ids=available,
        optional_artifact_ids=(CANDIDATE_LOCK_ID, PROTOCOL_ID, EXPOSURE_LEDGER_ID, WATERMARK_ID),
    )
    return plan, sources, missing_sources
