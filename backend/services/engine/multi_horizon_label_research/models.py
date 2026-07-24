from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.services.engine.tushare_cutover.canonical import hash_payload


@dataclass(frozen=True)
class TechnicalReturnLabelFamilyV1:
    labels: tuple[dict, ...] = (
        {
            "label_name": "technical_return_1d",
            "horizon_sessions": 1,
            "entry_offset_sessions": 1,
            "exit_offset_sessions": 1,
            "purpose": "existing_label_control",
            "overlapping_label": False,
            "hac_lag": 10,
        },
        {
            "label_name": "technical_return_5d",
            "horizon_sessions": 5,
            "entry_offset_sessions": 1,
            "exit_offset_sessions": 5,
            "purpose": "five_session_alignment_test",
            "overlapping_label": True,
            "hac_lag": 10,
        },
        {
            "label_name": "technical_return_10d",
            "horizon_sessions": 10,
            "entry_offset_sessions": 1,
            "exit_offset_sessions": 10,
            "purpose": "ten_session_alignment_test",
            "overlapping_label": True,
            "hac_lag": 15,
        },
    )

    def payload(self) -> dict:
        if tuple(row["horizon_sessions"] for row in self.labels) != (1, 5, 10):
            raise ValueError("only the preregistered 1d/5d/10d Label family is authorized")
        stable = asdict(self) | {
            "schema_version": "technical-return-label-family-v1",
            "provider_id": "tushare-pro-v1",
            "frozen_before_training": True,
            "adjustment_policy": "adjusted_prices",
            "calendar_policy": "official_trade_sessions",
            "lifecycle_policy": "fixed_100_no_replacement",
            "tradeability_policy": "entry_and_exit_must_be_tradable",
            "missing_policy": "no_forward_fill_no_last_price_substitution",
            "cross_section_transform": "same-date 5-MAD winsor then population zscore",
            "fourth_horizon_allowed": False,
            "promotion_writes": 0,
        }
        return stable | {"label_family_id": "trlf1_" + hash_payload(stable)}


@dataclass(frozen=True)
class ExecutableLabelAuditV1:
    metadata_formula: str
    executable_formula: str
    actual_materialized_values: str

    def payload(self) -> dict:
        stable = asdict(self) | {
            "schema_version": "executable-label-audit-v1",
            "provider_id": "tushare-pro-v1",
            "signal_date": "T",
            "entry_date": "T+1 official session",
            "exit_date": "T+h official session",
            "entry_price": "adjusted_open[T+1]",
            "exit_price": "adjusted_close[T+h]",
            "corporate_action_policy": "adjusted prices",
            "tradeability_policy": "entry and exit observations must be finite and tradable",
            "missing_policy": "sample absent; no forward fill or exit substitution",
            "legacy_label_artifact_modified": False,
            "promotion_writes": 0,
        }
        return stable | {"label_audit_id": "ela1_" + hash_payload(stable)}
