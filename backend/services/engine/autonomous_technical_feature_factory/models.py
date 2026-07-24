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
V2_FEATURE_FAMILIES = (
    "price_volume_lead_lag",
    "intraday_overnight_decomposition",
    "range_compression_expansion",
    "drawdown_age_recovery_timing",
    "return_path_asymmetry",
    "robust_trend_location",
)
V2_PRIMITIVES = PRIMITIVES + (
    "overnight_gap", "intraday_return", "high_low_range",
    "close_location_value", "close_vs_vwap", "turnover_pressure",
)
V2_AUTHORIZED_OPERATORS = AUTHORIZED_OPERATORS + (
    "rolling_sum", "rolling_corr", "rolling_median",
    "rolling_quantile", "rolling_skew", "rolling_argmax_age",
)


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


@dataclass(frozen=True)
class TechnicalFeatureFactoryBudgetV2:
    maximum_agent_calls: int = 10
    maximum_proposals: int = 30
    maximum_admitted_features: int = 20
    maximum_materialized_features: int = 20
    maximum_repair_attempts_per_call: int = 1

    def validate(self) -> None:
        frozen = TechnicalFeatureFactoryBudgetV2()
        for name, maximum in asdict(frozen).items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{name} exceeds frozen Factory v2 bound")


@dataclass(frozen=True)
class AutonomousTechnicalFeatureFactorySpecV2:
    factory_name: str = "technical_feature_factory_002"
    provider: str = "openai_codex_cli"
    model: str = "gpt-5.6-terra"
    runtime_mode: str = "store_required"
    provider_id: str = "tushare-pro-v1"
    universe: str = "Tushare Fixed-100"
    market_pool: str = "Tushare Fixed-500"
    benchmark: str = "CSI300"
    admission_period: tuple[str, str] = ("2019-01-02", "2020-12-31")
    feature_families: tuple[str, ...] = V2_FEATURE_FAMILIES
    input_primitives: tuple[str, ...] = V2_PRIMITIVES
    authorized_operators: tuple[str, ...] = V2_AUTHORIZED_OPERATORS
    fixed_windows: tuple[int, ...] = WINDOWS
    fixed_quantiles: tuple[float, ...] = (0.20, 0.50, 0.80)
    budgets: TechnicalFeatureFactoryBudgetV2 = TechnicalFeatureFactoryBudgetV2()
    label_access: bool = False
    performance_access: bool = False
    backtest_access: bool = False
    predictive_claim: bool = False
    usable_for_production: bool = False

    def payload(self, *, operator_extension_id: str, primitive_catalog_id: str,
                existing_feature_catalog_v2_id: str) -> dict:
        self.budgets.validate()
        if self.feature_families != V2_FEATURE_FAMILIES:
            raise ValueError("Feature Factory v2 families are frozen")
        if self.authorized_operators != V2_AUTHORIZED_OPERATORS:
            raise ValueError("Feature Factory v2 operators are frozen")
        if any((
            self.label_access, self.performance_access, self.backtest_access,
            self.predictive_claim, self.usable_for_production,
        )):
            raise ValueError("Feature Factory v2 cannot access predictive evidence")
        stable = asdict(self) | {
            "schema_version": "autonomous-technical-feature-factory-spec-v2",
            "operator_extension_id": operator_extension_id,
            "primitive_catalog_id": primitive_catalog_id,
            "existing_feature_catalog_v2_id": existing_feature_catalog_v2_id,
            "maximum_input_primitives_per_feature": 4,
            "maximum_window_parameters_per_feature": 2,
            "maximum_ast_depth": 7,
            "maximum_operator_count": 10,
            "promotion_writes": 0,
        }
        return stable | {"factory_spec_id": "atffs2_" + hash_payload(stable)}


def empty_usage() -> dict[str, int]:
    return {
        "agent_calls": 0, "proposals": 0, "admissions": 0,
        "materializations": 0, "repair_attempts": 0,
        "label_reads": 0, "backtest_calls": 0, "qlib_calls": 0,
        "tushare_calls": 0, "network_data_calls": 0,
        "manual_intervention_count": 0, "manual_feature_planning_count": 0,
        "promotion_writes": 0,
    }
