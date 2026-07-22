"""Default-first parameter-optimization governance.

This package plans and records governance decisions.  It deliberately does
not execute factor, strategy, Qlib, Agent, network, or promotion work.
"""

from .engine import (
    build_candidate_metadata,
    build_search_budget,
    evaluate_factor,
    evaluate_strategy,
    execute_governance,
    plan_governance,
    replay_governance,
    validate_candidate_lock_metadata,
)
from .models import OptimizationEvidenceClass, OptimizationGovernanceError
from .policies import (
    COMBINED_POLICY,
    FACTOR_POLICY,
    STRATEGY_POLICY,
    CombinedOptimizationPolicyV1,
    FactorOptimizationPolicyV2,
    StrategyOptimizationPolicyV2,
)

__all__ = (
    "COMBINED_POLICY",
    "FACTOR_POLICY",
    "STRATEGY_POLICY",
    "CombinedOptimizationPolicyV1",
    "FactorOptimizationPolicyV2",
    "OptimizationEvidenceClass",
    "OptimizationGovernanceError",
    "StrategyOptimizationPolicyV2",
    "build_candidate_metadata",
    "build_search_budget",
    "evaluate_factor",
    "evaluate_strategy",
    "execute_governance",
    "plan_governance",
    "replay_governance",
    "validate_candidate_lock_metadata",
)
