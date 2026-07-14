"""Stable string enums for the Implementation Ledger domain."""

from enum import Enum


class ImplementationTaskStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ImplementationRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED_UNCOMMITTED = "completed_uncommitted"
    PARTIAL_UNCOMMITTED = "partial_uncommitted"
    COMPLETED_COMMITTED = "completed_committed"
    PARTIAL_COMMITTED = "partial_committed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class CompletionLevel(str, Enum):
    NONE = "none"
    PARTIAL = "partial"
    COMPLETE = "complete"


class VerificationLevel(str, Enum):
    NOT_VERIFIED = "not_verified"
    STATIC_CHECKS = "static_checks"
    TARGETED_TESTS = "targeted_tests"
    INTEGRATION_TESTS = "integration_tests"
    FULL_RELEVANT_TESTS = "full_relevant_tests"


class ConsistencyStatus(str, Enum):
    UNVERIFIED = "unverified"
    CONSISTENT = "consistent"
    WARNING = "warning"
    ERROR = "error"
    STALE = "stale"


class CanonicalStatus(str, Enum):
    NONCANONICAL = "noncanonical"
    CANDIDATE = "candidate"
    CANONICAL = "canonical"
    REJECTED = "rejected"


class RunRelationshipType(str, Enum):
    FINALIZES = "finalizes"
    CORRECTS = "corrects"
    SUPERSEDES = "supersedes"
    DEPENDS_ON = "depends_on"
    RETRIES = "retries"
    CONTINUES = "continues"


class TestExecutionStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_RUN = "not_run"


class FileChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNCHANGED = "unchanged"


class SymbolChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class SymbolType(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    CONSTANT = "constant"
    SCHEMA = "schema"
    TABLE = "table"
    ENDPOINT = "endpoint"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class ImpactType(str, Enum):
    INTRODUCED = "introduced"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"
    REMOVED = "removed"
    VERIFIED = "verified"
    DOCUMENTED = "documented"
    UNAFFECTED = "unaffected"


class ADRReferenceRelation(str, Enum):
    IMPLEMENTS = "implements"
    CONFORMS_TO = "conforms_to"
    DOCUMENTS = "documents"
    SUPERSEDES = "supersedes"
    AFFECTED_BY = "affected_by"


class LimitationSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LimitationStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class RecommendationPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
