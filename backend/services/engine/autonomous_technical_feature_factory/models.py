from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.services.engine.tushare_cutover.canonical import hash_payload


FEATURE_FAMILIES = (
    "trend_geometry",
    "drawdown_recovery_geometry",
    "volatility_shape",
    "liquidity_amount_dynamics",
    "relative_strength",
    "path_asymmetry",
)
PRIMITIVES = (
    "adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close",
    "volume", "amount", "vwap", "daily_return", "csi300_return",
)
AUTHORIZED_OPERATORS = (
    "add", "subtract", "multiply", "safe_divide", "negate", "abs", "clip",
    "lag", "delta", "rolling_mean", "rolling_std", "rolling_min", "rolling_max",
)
UNAUTHORIZED_CONTRACT_OPERATORS = ("rolling_sum", "rolling_corr", "log1p")
WINDOWS = (5, 10, 20, 40, 60, 120)


@dataclass(frozen=True)
class TechnicalFeatureFactoryBudget:
    maximum_agent_calls: int = 8
    maximum_proposals: int = 24
    maximum_admitted_features: int = 16
    maximum_materialized_features: int = 16
    maximum_repair_attempts_per_call: int = 1

    def validate(self) -> None:
        frozen = TechnicalFeatureFactoryBudget()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen Factory bound")


@dataclass(frozen=True)
class AutonomousTechnicalFeatureFactorySpecV1:
    factory_name: str = "technical_feature_factory_001"
    provider: str = "openai_codex_cli"
    model: str = "gpt-5.6-terra"
    runtime_mode: str = "store_required"
    provider_id: str = "tushare-pro-v1"
    universe: str = "Tushare Fixed-100"
    admission_period: tuple[str, str] = ("2019-01-02", "2020-12-31")
    feature_families: tuple[str, ...] = FEATURE_FAMILIES
    input_primitives: tuple[str, ...] = PRIMITIVES
    authorized_operators: tuple[str, ...] = AUTHORIZED_OPERATORS
    unauthorized_contract_operators: tuple[str, ...] = UNAUTHORIZED_CONTRACT_OPERATORS
    fixed_windows: tuple[int, ...] = WINDOWS
    budgets: TechnicalFeatureFactoryBudget = TechnicalFeatureFactoryBudget()
    label_access: bool = False
    backtest_access: bool = False
    predictive_claim: bool = False
    usable_for_production: bool = False

    def payload(self) -> dict:
        self.budgets.validate()
        if self.feature_families != FEATURE_FAMILIES:
            raise ValueError("Feature family contract is frozen")
        if self.authorized_operators != AUTHORIZED_OPERATORS:
            raise ValueError("Feature operator contract is frozen")
        if any((self.label_access, self.backtest_access, self.predictive_claim, self.usable_for_production)):
            raise ValueError("Feature Factory cannot use labels/backtests or claim production evidence")
        stable = asdict(self) | {"schema_version": "autonomous-technical-feature-factory-spec-v1"}
        return stable | {"factory_spec_id": "atffs1_" + hash_payload(stable)}


def empty_usage() -> dict[str, int]:
    return {
        "agent_calls": 0, "proposals": 0, "admissions": 0,
        "materializations": 0, "repair_attempts": 0,
        "label_reads": 0, "backtest_calls": 0, "qlib_calls": 0,
        "tushare_calls": 0, "network_data_calls": 0,
        "manual_intervention_count": 0, "manual_feature_planning_count": 0,
        "promotion_writes": 0,
    }
