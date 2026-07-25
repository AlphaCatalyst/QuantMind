from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.expanded_factor_iteration.features import (
    DEFINITIONS,
    compute_feature_candidates,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload


CONTROL_NAMES = (
    "log_circ_mv",
    "style_beta_20",
    "style_idio_vol_20",
    "amount_ratio_20",
)


@dataclass(frozen=True)
class CrossSectionalStyleResidualizationV1:
    controls: tuple[str, ...] = CONTROL_NAMES
    minimum_finite_members: int = 80
    control_transform: str = "same_date_population_zscore"
    regression: str = "deterministic_ols_with_intercept"
    output_transform: str = "same_date_population_zscore"
    zero_variance_policy: str = "drop_control_for_date_and_record"
    industry_neutralization: bool = False

    def payload(self, *, control_audit: dict[str, Any]) -> dict[str, Any]:
        if self.controls != CONTROL_NAMES or self.minimum_finite_members < 80:
            raise ValueError("frozen residualization contract changed")
        stable = asdict(self) | {
            "schema_version": "cross-sectional-style-residualization-v1",
            "provider_id": "tushare-pro-v1",
            "control_audit": control_audit,
            "fit_scope": "one_trade_date_only",
            "return_or_label_reads": 0,
            "future_data_reads": 0,
            "pit_violation_count": 0,
            "direction_preserved": True,
            "control_set_search_calls": 0,
            "promotion_writes": 0,
        }
        return stable | {
            "cross_sectional_style_residualization_id": "cssr1_"
            + hash_payload(stable)
        }


def build_style_controls(bundle) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Materialize the four pre-existing PIT-safe Feature definitions."""
    computed = compute_feature_candidates(bundle.normalized, bundle.benchmark)
    controls = computed[["symbol", "trade_date", *CONTROL_NAMES]].copy()
    controls["trade_date"] = pd.to_datetime(controls["trade_date"]).dt.strftime(
        "%Y-%m-%d"
    )
    definitions = {item.name: item for item in DEFINITIONS}
    audit = {
        name: {
            "formal_name": name,
            "canonical_formula": definitions[name].canonical_formula,
            "source_columns": list(definitions[name].source_columns),
            "lookback": definitions[name].lookback,
            "pit_statement": definitions[name].pit_statement,
            "mapping": "exact_formal_feature_name",
            "pit_safe": True,
            "finite_coverage": float(
                pd.to_numeric(controls[name], errors="coerce").notna().mean()
            ),
        }
        for name in CONTROL_NAMES
    }
    return controls, audit


def _zscore(values: np.ndarray) -> np.ndarray:
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=0))
    if not np.isfinite(std) or std <= 0:
        return np.full(len(values), np.nan)
    return (values - mean) / std


def residualize_scores(
    raw_values: pd.DataFrame,
    controls: pd.DataFrame,
    *,
    minimum_finite_members: int = 80,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"symbol", "trade_date", "factor_value"}
    if not required.issubset(raw_values):
        raise ValueError("raw factor values are missing keys")
    merged = raw_values.copy()
    merged["trade_date"] = pd.to_datetime(merged["trade_date"]).dt.strftime(
        "%Y-%m-%d"
    )
    merged = merged.merge(
        controls,
        on=["symbol", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    output: list[pd.DataFrame] = []
    dropped: list[dict[str, Any]] = []
    insufficient: list[str] = []
    for date, group in merged.groupby("trade_date", sort=True):
        numeric = group[["factor_value", *CONTROL_NAMES]].apply(
            pd.to_numeric, errors="coerce"
        )
        finite = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
        valid = group.loc[finite, ["symbol", "trade_date"]].copy()
        values = numeric.loc[finite].reset_index(drop=True)
        if len(valid) < minimum_finite_members:
            insufficient.append(str(date))
            continue
        active: list[str] = []
        standardized: list[np.ndarray] = []
        for name in CONTROL_NAMES:
            z = _zscore(values[name].to_numpy(dtype=float))
            if np.isfinite(z).all():
                active.append(name)
                standardized.append(z)
            else:
                dropped.append(
                    {"trade_date": str(date), "control": name, "reason": "zero_variance"}
                )
        x = np.column_stack(
            [np.ones(len(values), dtype=float), *standardized]
        )
        y = values["factor_value"].to_numpy(dtype=float)
        coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
        residual = y - x @ coefficients
        score = _zscore(residual)
        if not np.isfinite(score).all():
            insufficient.append(str(date))
            continue
        valid["factor_value"] = score
        valid["raw_factor_value"] = y
        valid["active_control_count"] = len(active)
        output.append(valid)
    frame = (
        pd.concat(output, ignore_index=True)
        if output
        else pd.DataFrame(
            columns=[
                "symbol",
                "trade_date",
                "factor_value",
                "raw_factor_value",
                "active_control_count",
            ]
        )
    )
    evidence = {
        "minimum_finite_members": minimum_finite_members,
        "input_row_count": len(raw_values),
        "output_row_count": len(frame),
        "output_coverage": float(len(frame) / len(raw_values)) if len(raw_values) else 0.0,
        "evaluated_date_count": int(frame["trade_date"].nunique()) if not frame.empty else 0,
        "insufficient_date_count": len(insufficient),
        "insufficient_dates": insufficient,
        "zero_variance_control_drops": dropped,
        "return_or_label_reads": 0,
        "future_data_reads": 0,
        "pit_violation_count": 0,
        "direction_preserved": True,
    }
    return frame, evidence
