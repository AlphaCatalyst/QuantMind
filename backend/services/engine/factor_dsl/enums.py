from enum import Enum


class NodeKind(str, Enum):
    FEATURE = "feature"
    PARAMETER = "parameter"
    CONSTANT = "constant"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    NEGATE = "negate"
    ABSOLUTE = "absolute"
    CLIP = "clip"
    LAG = "lag"
    DELTA = "delta"
    ROLLING_MEAN = "rolling_mean"
    ROLLING_STD = "rolling_std"
    ROLLING_MIN = "rolling_min"
    ROLLING_MAX = "rolling_max"
    CS_RANK = "cs_rank"
    CS_ZSCORE = "cs_zscore"


class ValueKind(str, Enum):
    SCALAR = "scalar"
    SERIES = "series"


class ParameterType(str, Enum):
    INTEGER = "integer"
    NUMBER = "number"
