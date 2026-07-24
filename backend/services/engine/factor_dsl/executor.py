import numpy as np
import pandas as pd

from backend.services.engine.market_data.feature_snapshot import load_feature_matrix

from .artifact import publish_values, validate_values
from .enums import NodeKind
from .errors import ExecutionError
from .models import ExecutionResult
from .quality import factor_quality


def _argmax_age(values):
    finite = np.isfinite(values)
    if not finite.all():
        return np.nan
    maximum = np.max(values)
    positions = np.flatnonzero(values == maximum)
    return float(len(values) - 1 - positions[-1])


def _stable_skew(values):
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or len(values) < 3:
        return np.nan
    centered = values - values.mean()
    variance = np.mean(centered ** 2)
    if variance <= 1e-24:
        return np.nan
    return float(np.mean(centered ** 3) / variance ** 1.5)


def _evaluate(node, frame, parameters):
    kind = node.kind
    if kind is NodeKind.FEATURE:
        return frame[node.fields["name"]].astype(float)
    if kind is NodeKind.PARAMETER:
        return parameters[node.fields["name"]]
    if kind is NodeKind.CONSTANT:
        return node.fields["value"]
    if kind in (NodeKind.ADD, NodeKind.SUBTRACT, NodeKind.MULTIPLY, NodeKind.DIVIDE):
        left = _evaluate(node.fields["left"], frame, parameters)
        right = _evaluate(node.fields["right"], frame, parameters)
        if kind is NodeKind.ADD: return left + right
        if kind is NodeKind.SUBTRACT: return left - right
        if kind is NodeKind.MULTIPLY: return left * right
        if np.isscalar(right):
            return np.nan if abs(right) <= 1e-12 else left / right
        denominator = right.astype(float)
        return left / denominator.where(denominator.abs() > 1e-12)
    if kind is NodeKind.NEGATE:
        return -_evaluate(node.fields["operand"], frame, parameters)
    if kind is NodeKind.ABSOLUTE:
        return abs(_evaluate(node.fields["operand"], frame, parameters))
    if kind is NodeKind.CLIP:
        value = _evaluate(node.fields["operand"], frame, parameters)
        lower = _evaluate(node.fields["lower"], frame, parameters)
        upper = _evaluate(node.fields["upper"], frame, parameters)
        return value.clip(lower=lower, upper=upper) if isinstance(value, pd.Series) else min(max(value, lower), upper)
    if kind in (NodeKind.LAG, NodeKind.DELTA):
        value = _evaluate(node.fields["operand"], frame, parameters)
        periods = int(_evaluate(node.fields["periods"], frame, parameters))
        grouped = value.groupby(frame["symbol"], sort=False)
        return grouped.shift(periods) if kind is NodeKind.LAG else value - grouped.shift(periods)
    if kind in (
        NodeKind.ROLLING_MEAN, NodeKind.ROLLING_STD, NodeKind.ROLLING_MIN,
        NodeKind.ROLLING_MAX, NodeKind.ROLLING_SUM, NodeKind.ROLLING_MEDIAN,
        NodeKind.ROLLING_SKEW, NodeKind.ROLLING_ARGMAX_AGE,
    ):
        value = _evaluate(node.fields["operand"], frame, parameters)
        window = int(_evaluate(node.fields["window"], frame, parameters))
        grouped = value.groupby(frame["symbol"], sort=False)
        if kind is NodeKind.ROLLING_MEAN:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).mean())
        if kind is NodeKind.ROLLING_STD:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).std(ddof=0))
        if kind is NodeKind.ROLLING_MIN:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).min())
        if kind is NodeKind.ROLLING_MAX:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).max())
        if kind is NodeKind.ROLLING_SUM:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).sum())
        if kind is NodeKind.ROLLING_MEDIAN:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).median())
        if kind is NodeKind.ROLLING_SKEW:
            return grouped.transform(
                lambda x: x.rolling(window, min_periods=window).apply(_stable_skew, raw=True)
            )
        return grouped.transform(
            lambda x: x.rolling(window, min_periods=window).apply(_argmax_age, raw=True)
        )
    if kind is NodeKind.ROLLING_CORR:
        left = _evaluate(node.fields["left"], frame, parameters)
        right = _evaluate(node.fields["right"], frame, parameters)
        window = int(_evaluate(node.fields["window"], frame, parameters))
        pair = pd.DataFrame({"left": left, "right": right, "symbol": frame["symbol"]})
        grouped = pair.groupby("symbol", sort=False)
        result = grouped["left"].transform(
            lambda values: values.rolling(window, min_periods=window).corr(
                pair.loc[values.index, "right"]
            )
        )
        left_std = grouped["left"].transform(
            lambda values: values.rolling(window, min_periods=window).std(ddof=0)
        )
        right_std = grouped["right"].transform(
            lambda values: values.rolling(window, min_periods=window).std(ddof=0)
        )
        return result.where((left_std > 1e-12) & (right_std > 1e-12))
    if kind is NodeKind.ROLLING_QUANTILE:
        value = _evaluate(node.fields["operand"], frame, parameters)
        window = int(_evaluate(node.fields["window"], frame, parameters))
        quantile = float(_evaluate(node.fields["quantile"], frame, parameters))
        return value.groupby(frame["symbol"], sort=False).transform(
            lambda x: x.rolling(window, min_periods=window).quantile(quantile, interpolation="linear")
        )
    value = _evaluate(node.fields["operand"], frame, parameters)
    grouped = value.groupby(frame["trade_date"], sort=False)
    if kind is NodeKind.CS_RANK:
        return grouped.transform(lambda x: x.rank(method="average", pct=True) if x.notna().sum() >= 2 else pd.Series(np.nan, index=x.index))
    if kind is NodeKind.CS_ZSCORE:
        def zscore(x):
            if x.notna().sum() < 2:
                return pd.Series(np.nan, index=x.index)
            std = x.std(ddof=0)
            return pd.Series(np.nan, index=x.index) if not np.isfinite(std) or std == 0 else (x - x.mean()) / std
        return grouped.transform(zscore)
    raise ExecutionError(f"unhandled node {kind.value}")


def execute_compiled(compiled, snapshot_root, output_root):
    try:
        frame = load_feature_matrix(snapshot_root, compiled.snapshot_id, feature_columns=compiled.required_features)
        frame = frame.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
        if frame.duplicated(["symbol", "trade_date"]).any():
            raise ExecutionError("Dataset Snapshot contains duplicate factor keys")
        values = _evaluate(compiled.template.expression, frame, compiled.bound_parameters)
        if not isinstance(values, pd.Series):
            raise ExecutionError("compiled factor did not produce a series")
        output = frame[["symbol", "trade_date"]].copy()
        output["factor_value"] = values.astype(float)
        quality = factor_quality(output, compiled.warmup_periods)
        quality["compiler_warnings"] = list(compiled.warnings)
        values_id, path, manifest, replayed = publish_values(output, compiled, quality, output_root)
        validate_values(snapshot_root, output_root, values_id)
        return ExecutionResult(values_id, str(path), manifest, replayed)
    except ExecutionError:
        raise
    except Exception as exc:
        raise ExecutionError(str(exc)) from exc
