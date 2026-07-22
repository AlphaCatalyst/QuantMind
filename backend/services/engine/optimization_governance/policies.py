from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FactorOptimizationPolicyV2:
    policy_id: str = "factor-optimization-policy-v2-default-first"
    policy_version: str = "2.0.0"
    default_mode: str = "default_first"
    max_trials_per_template: int = 7
    local_search_rule: str = "default_plus_previous_and_next_one_parameter_at_a_time"
    full_search_diagnostic_enabled_by_default: bool = False
    full_search_usable_for_candidate_selection: bool = False
    full_search_usable_for_promotion: bool = False
    missing_default_error: str = "AGENT_DEFAULT_PARAMETERS_MISSING"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyOptimizationPolicyV2:
    policy_id: str = "strategy-optimization-policy-v2-default-first"
    policy_version: str = "2.0.0"
    default_mode: str = "default_first"
    topk: int = 20
    n_drop: int = 5
    rebalance_interval: int = 5
    weighting: str = "equal_weight"
    signal_lag: int = 1
    execution_price: str = "open"
    max_trials: int = 7
    full_search_diagnostic_enabled_by_default: bool = False
    full_search_usable_for_candidate_selection: bool = False
    full_search_usable_for_promotion: bool = False

    @property
    def default_parameters(self) -> dict[str, Any]:
        return {
            "topk": self.topk,
            "n_drop": self.n_drop,
            "rebalance_interval": self.rebalance_interval,
            "weighting": self.weighting,
            "signal_lag": self.signal_lag,
            "execution_price": self.execution_price,
        }

    @property
    def local_neighborhood(self) -> tuple[dict[str, Any], ...]:
        return tuple({**self.default_parameters, "topk": topk, "n_drop": n_drop,
                      "rebalance_interval": rebalance}
                     for topk, n_drop, rebalance in (
                         (20, 5, 5), (10, 5, 5), (30, 5, 5),
                         (20, 0, 5), (20, 10, 5), (20, 5, 1), (20, 5, 10),
                     ))

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["default_parameters"] = self.default_parameters
        value["local_neighborhood"] = list(self.local_neighborhood)
        return value


@dataclass(frozen=True)
class CombinedOptimizationPolicyV1:
    policy_id: str = "combined-optimization-policy-v1-suspended"
    policy_version: str = "1.0.0"
    status: str = "suspended"
    violation_error: str = "COMBINED_PARAMETER_OPTIMIZATION_SUSPENDED"
    both_defaults_fail_order: str = "factor_local_with_default_strategy_then_stop"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


FACTOR_POLICY = FactorOptimizationPolicyV2()
STRATEGY_POLICY = StrategyOptimizationPolicyV2()
COMBINED_POLICY = CombinedOptimizationPolicyV1()
