from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload

from .enums import CorporateActionEventType, EvidenceCompleteness, PermissionStatus


@dataclass(frozen=True)
class CapabilityResult:
    endpoint: str
    permission_status: PermissionStatus
    available_fields: tuple[str, ...]
    target_symbol_coverage: tuple[str, ...]
    target_event_coverage: tuple[str, ...]
    structured_settlement_fields: tuple[str, ...]
    raw_announcement_available: bool
    safe_error_code: str | None
    row_count: int

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value["permission_status"] = self.permission_status.value
        return value


@dataclass(frozen=True)
class SecurityCorporateActionEvent:
    symbol: str
    event_type: CorporateActionEventType
    announcement_date: str | None
    last_tradable_date: str | None
    effective_date: str | None
    settlement_date: str | None
    cash_per_share: float | None
    replacement_symbol: str | None
    conversion_ratio: float | None
    residual_cash_per_share: float | None
    source_artifact_id: str
    source_record_id: str
    evidence_hash: str
    evidence_completeness: EvidenceCompleteness

    @property
    def event_id(self) -> str:
        return "scaev_" + hash_payload(self.payload(include_id=False))

    def payload(self, *, include_id: bool = True) -> dict[str, Any]:
        value = asdict(self)
        value["event_type"] = self.event_type.value
        value["evidence_completeness"] = self.evidence_completeness.value
        if include_id:
            value["event_id"] = self.event_id
        return value


@dataclass(frozen=True)
class FixedUniverseBenchmarkContractV2:
    universe_lock_id: str
    rebalance_frequency: str = "weekly_unchanged"
    weighting: str = "equal_weight"
    active_member_policy: str = "allocate_new_target_weight_only_to_active_members"
    observable_member_policy: str = "missing_observation_is_not_zero_return"
    corporate_action_policy: str = "governed_security_termination_events_only"
    cash_handling: str = "settlement_cash_remains_in_self_financing_cash_account"
    replacement_policy: str = "no_locked_universe_replacement"
    termination_settlement: str = "cash_conversion_or_writeoff_requires_complete_evidence"
    transaction_cost_policy: str = "unchanged_from_original_benchmark_contract"
    benchmark_semantics: str = "investable_self_financing_equal_weight_portfolio"
    settlement_asset_membership: str = "settlement_asset_is_not_a_new_locked_member"

    @property
    def benchmark_contract_id(self) -> str:
        return "fubc_" + hash_payload(self.payload(include_id=False))

    def payload(self, *, include_id: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if include_id:
            value["benchmark_contract_id"] = self.benchmark_contract_id
        return value

