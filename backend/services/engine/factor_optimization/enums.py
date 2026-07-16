from enum import Enum


class ParameterRole(str, Enum):
    LOOKBACK_WINDOW = "lookback_window"
    FACTOR_INTERNAL_WEIGHT = "factor_internal_weight"
    SIGNAL_THRESHOLD = "signal_threshold"


class TrialStatus(str, Enum):
    PLANNED = "planned"
    SUCCEEDED = "succeeded"
    REPLAYED = "replayed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class StudyStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
