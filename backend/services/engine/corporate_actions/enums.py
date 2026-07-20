from enum import Enum


class CorporateActionEventType(str, Enum):
    DELISTING = "delisting"
    CASH_SETTLEMENT = "cash_settlement"
    STOCK_CONVERSION = "stock_conversion"
    MERGER_EXCHANGE = "merger_exchange"
    WRITE_OFF = "write_off"
    UNKNOWN_TERMINATION = "unknown_termination"


class EvidenceCompleteness(str, Enum):
    COMPLETE = "evidence_complete"
    PARTIAL = "evidence_partial"
    MISSING = "evidence_missing"


class PermissionStatus(str, Enum):
    AVAILABLE = "available"
    PERMISSION_OR_PARAMETER_ERROR = "permission_or_parameter_error"
    TRANSPORT_ERROR = "transport_error"

