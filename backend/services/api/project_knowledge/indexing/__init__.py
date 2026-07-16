"""Git-authoritative Implementation Manifest indexing services."""

from .domain_bundle import DomainBundleBuilder
from .errors import (
    DomainBundleError,
    GitConsistencyError,
    GitEvidenceError,
    ImplementationIndexError,
    LedgerIndexConflictError,
    ManifestParseError,
    ManifestSelfReferenceError,
    ReportValidationError,
    RepositoryBindingError,
    UnsupportedManifestSchemaError,
)
from .git_evidence import GitSnapshot, ImplementationRunPlanner, discover_runs
from .indexer import LedgerIndexer
from .manifest_parser import ImplementationManifestParser
from .manifest_v2 import (
    canonical_manifest_v2_payload_hash,
    finalize_manifest_v2_payload,
    manifest_self_reference_items,
    validate_manifest_v2_payload,
)
from .repository_binding import bind_repository

__all__ = (
    "DomainBundleBuilder",
    "DomainBundleError",
    "GitConsistencyError",
    "GitEvidenceError",
    "GitSnapshot",
    "ImplementationIndexError",
    "ImplementationManifestParser",
    "ImplementationRunPlanner",
    "LedgerIndexConflictError",
    "LedgerIndexer",
    "ManifestParseError",
    "ManifestSelfReferenceError",
    "ReportValidationError",
    "RepositoryBindingError",
    "UnsupportedManifestSchemaError",
    "bind_repository",
    "canonical_manifest_v2_payload_hash",
    "discover_runs",
    "finalize_manifest_v2_payload",
    "manifest_self_reference_items",
    "validate_manifest_v2_payload",
)
