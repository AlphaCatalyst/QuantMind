"""Stable, secret-safe errors for Git-backed Ledger indexing."""

from __future__ import annotations


class ImplementationIndexError(RuntimeError):
    error_code = "IMPLEMENTATION_INDEX_ERROR"

    def __init__(
        self,
        message: str,
        *,
        run_id: str | None = None,
        check: str | None = None,
    ) -> None:
        self.message = message
        self.run_id = run_id
        self.check = check
        context = ":".join(value for value in (run_id, check) if value)
        super().__init__(f"{self.error_code}{f'[{context}]' if context else ''}: {message}")


class ManifestParseError(ImplementationIndexError):
    error_code = "MANIFEST_PARSE_ERROR"


class UnsupportedManifestSchemaError(ImplementationIndexError):
    error_code = "UNSUPPORTED_MANIFEST_SCHEMA"


class ReportValidationError(ImplementationIndexError):
    error_code = "REPORT_VALIDATION_ERROR"


class RepositoryBindingError(ImplementationIndexError):
    error_code = "REPOSITORY_BINDING_ERROR"


class GitEvidenceError(ImplementationIndexError):
    error_code = "GIT_EVIDENCE_ERROR"


class GitConsistencyError(ImplementationIndexError):
    error_code = "GIT_CONSISTENCY_ERROR"


class DomainBundleError(ImplementationIndexError):
    error_code = "DOMAIN_BUNDLE_ERROR"


class LedgerIndexConflictError(ImplementationIndexError):
    error_code = "LEDGER_INDEX_CONFLICT"
