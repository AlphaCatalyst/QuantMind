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
    FIXED_UNIVERSE_LOCK = "fixed_universe_lock"
    FIXED_UNIVERSE_HISTORICAL_DATASET = "fixed_universe_historical_dataset"
    HISTORICAL_AGENT_EXPERIMENT = "historical_agent_experiment"
    HISTORICAL_ROUND_LOCK = "historical_round_lock"
    HISTORICAL_ROUND_EVALUATION = "historical_round_evaluation"
    QLIB_BACKTEST_RESULT = "qlib_backtest_result"
    HISTORICAL_HOLDOUT_RESULT = "historical_holdout_result"
    AGENT_ITERATION_ASSESSMENT = "agent_iteration_assessment"
    SIGNAL_MISSINGNESS_AUDIT = "signal_missingness_audit"
    HISTORICAL_BACKTEST_FOLLOWUP = "historical_backtest_followup"


class IntegrityStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CORRUPT = "corrupt"
