"""Pure result values for the Git-to-Ledger indexing boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from backend.services.engine.project_knowledge.domain.models import (
    ArchitectureDecisionReference,
    ChangedFile,
    ChangedSymbol,
    ComponentReference,
    ImplementationArtifact,
    ImplementationRun,
    ImplementationTask,
    Limitation,
    RecommendedTask,
    RunRelationship,
    TestExecution,
)


@dataclass(frozen=True)
class RepositoryBinding:
    repository_id: str
    repository_path: Path


@dataclass(frozen=True)
class DiscoveredRun:
    run_id: str
    directory: str
    manifest_path: str
    report_path: str


@dataclass(frozen=True)
class ParsedImplementationManifest:
    run_id: str
    manifest_path: str
    report_path: str
    source_status: str
    payload: Mapping[str, Any] = field(repr=False, compare=False)

    @property
    def schema_version(self) -> str:
        return str(
            self.payload.get(
                "schema_version", self.payload.get("manifest_schema_version", "")
            )
        )


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    mandatory: bool
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvidenceWarning:
    code: str
    field: str
    detail: str


@dataclass(frozen=True)
class GitConsistencyEvidence:
    run_id: str
    repository_id: str
    ref_commit: str
    containing_commit: str | None
    source_status: str | None
    resolved_status: str | None
    resolved_result_commit: str | None
    actual_changed_files: tuple[str, ...]
    checks: tuple[EvidenceCheck, ...]
    warnings: tuple[EvidenceWarning, ...] = ()

    @property
    def consistent(self) -> bool:
        return all(check.passed for check in self.checks if check.mandatory)


@dataclass(frozen=True)
class EvidenceGap:
    code: str
    field: str
    detail: str


@dataclass(frozen=True)
class ResolvedImplementationRun:
    source_status: str
    resolved_status: str
    containing_commit: str
    run: ImplementationRun


@dataclass(frozen=True)
class ImplementationDomainBundle:
    task: ImplementationTask
    run: ImplementationRun
    changed_files: tuple[ChangedFile, ...] = ()
    changed_symbols: tuple[ChangedSymbol, ...] = ()
    tests: tuple[TestExecution, ...] = ()
    artifacts: tuple[ImplementationArtifact, ...] = ()
    component_refs: tuple[ComponentReference, ...] = ()
    adr_refs: tuple[ArchitectureDecisionReference, ...] = ()
    limitations: tuple[Limitation, ...] = ()
    recommended_tasks: tuple[RecommendedTask, ...] = ()
    relationships: tuple[RunRelationship, ...] = ()


@dataclass(frozen=True)
class DomainBundleBuild:
    resolved_run: ResolvedImplementationRun | None
    bundle: ImplementationDomainBundle | None
    gaps: tuple[EvidenceGap, ...]

    @property
    def indexable(self) -> bool:
        return self.bundle is not None and not self.gaps


@dataclass(frozen=True)
class AnalyzedRun:
    discovered: DiscoveredRun
    parsed: ParsedImplementationManifest | None
    evidence: GitConsistencyEvidence
    domain_build: DomainBundleBuild | None
    errors: tuple[str, ...] = ()

    @property
    def validated(self) -> bool:
        return self.parsed is not None and self.evidence.consistent

    @property
    def indexable(self) -> bool:
        return self.validated and self.domain_build is not None and self.domain_build.indexable


@dataclass(frozen=True)
class BackfillPlan:
    repository_id: str
    ref_commit: str
    runs: tuple[AnalyzedRun, ...]

    @property
    def discovered_count(self) -> int:
        return len(self.runs)

    @property
    def validated_count(self) -> int:
        return sum(run.validated for run in self.runs)

    @property
    def indexable_count(self) -> int:
        return sum(run.indexable for run in self.runs)


@dataclass(frozen=True)
class IndexRunResult:
    run_id: str
    status: str


@dataclass(frozen=True)
class BackfillResult:
    repository_id: str
    ref_commit: str
    discovered: int
    validated: int
    indexed: int
    replayed: int
    skipped: int
    failed: int
    relationships: int
    runs: tuple[IndexRunResult, ...]


@dataclass(frozen=True)
class LedgerStatus:
    repository_id: str
    ref_commit: str
    git_runs: tuple[str, ...]
    indexed_runs: tuple[str, ...]
    pending: tuple[str, ...]
    replay: tuple[str, ...]
    conflicts: tuple[str, ...]
    database_only: tuple[str, ...]
    git_only: tuple[str, ...]
