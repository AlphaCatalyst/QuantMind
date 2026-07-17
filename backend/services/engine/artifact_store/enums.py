from enum import Enum


class ArtifactKind(str, Enum):
    DATASET_SNAPSHOT = "dataset_snapshot"
    FACTOR_VALUES = "factor_values"
    FACTOR_OPTIMIZATION = "factor_optimization"
    VALIDATION_DATASET = "validation_dataset"
    FACTOR_VALIDATION_RESULT = "factor_validation_result"
    FROZEN_TEST_RESULT = "frozen_test_result"
    FACTOR_REGISTRY = "factor_registry"
    REGISTRY_RECONCILIATION = "registry_reconciliation"
    FRESH_VALIDATION_ADMISSION = "fresh_validation_admission"
    RESEARCH_CAMPAIGN = "research_campaign"
    FRESH_VALIDATION_ACCRUAL = "fresh_validation_accrual"
    FRESH_VALIDATION_RESULT = "fresh_validation_result"
    IMPLEMENTATION_EVIDENCE = "implementation_evidence"
    GENERIC_RESEARCH_BUNDLE = "generic_research_bundle"


class IntegrityStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CORRUPT = "corrupt"
