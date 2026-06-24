"""Safety and executability guard for QuantGPT-origin factor expressions."""

from __future__ import annotations

import re
from dataclasses import dataclass


_BLOCKED_TOKENS = {
    "__",
    "import",
    "exec",
    "eval",
    "open(",
    "read(",
    "write(",
    "http",
    "request",
    "submit",
    "brain",
    "os.",
    "sys.",
    "subprocess",
}
_SAFE_CHARS_RE = re.compile(r"^[A-Za-z0-9_\s,().+\-*/<>]+$")


@dataclass(frozen=True)
class SupportedFactorExpression:
    expression: str
    key: str
    kind: str
    field: str | None = None
    second_field: str | None = None
    mean_window: int | None = None
    momentum_window: int | None = None
    volatility_window: int | None = None
    correlation_window: int | None = None


def normalize_factor_expression(expression: str) -> str:
    return " ".join(str(expression or "").strip().split())


def factor_expression_key(expression: str) -> str:
    return re.sub(r"\s+", "", normalize_factor_expression(expression).lower())


def expression_nesting_depth(expression: str) -> int:
    depth = 0
    max_depth = 0
    for char in expression:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth -= 1
            if depth < 0:
                return max_depth + 1
    return max_depth if depth == 0 else max_depth + 1


def parse_supported_factor_expression(
    expression: str,
) -> SupportedFactorExpression | None:
    normalized = normalize_factor_expression(expression)
    key = factor_expression_key(normalized)

    factor_field = r"(close|volume|amount|vwap)"

    mean_match = re.fullmatch(
        rf"rank\({factor_field}/ts_mean\(\1,(\d+)\)\)",
        key,
    )
    if mean_match:
        field = mean_match.group(1)
        window = int(mean_match.group(2))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="mean",
                field=field,
                mean_window=window,
            )

    ts_rank_match = re.fullmatch(rf"rank\(ts_rank\({factor_field},(\d+)\)\)", key)
    if ts_rank_match:
        field = ts_rank_match.group(1)
        window = int(ts_rank_match.group(2))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="ts_rank",
                field=field,
                mean_window=window,
            )

    decay_match = re.fullmatch(
        rf"rank\(decay_linear\({factor_field},(\d+)\)\)",
        key,
    )
    if decay_match:
        field = decay_match.group(1)
        window = int(decay_match.group(2))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="decay_linear",
                field=field,
                mean_window=window,
            )

    rolling_zscore_match = re.fullmatch(
        rf"rank\(zscore\({factor_field},(\d+)\)\)",
        key,
    )
    if rolling_zscore_match:
        field = rolling_zscore_match.group(1)
        window = int(rolling_zscore_match.group(2))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="rolling_zscore",
                field=field,
                mean_window=window,
            )

    cross_sectional_transform_match = re.fullmatch(
        rf"rank\((zscore|scale)\({factor_field}\)\)",
        key,
    )
    if cross_sectional_transform_match:
        transform = cross_sectional_transform_match.group(1)
        field = cross_sectional_transform_match.group(2)
        return SupportedFactorExpression(
            expression=normalized,
            key=key,
            kind=f"{transform}_cross_sectional",
            field=field,
        )

    momentum_match = re.fullmatch(
        r"rank\(ts_delta\(close,(\d+)\)/ts_shift\(close,\1\)\)",
        key,
    )
    if momentum_match:
        window = int(momentum_match.group(1))
        if 1 <= window <= 120:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="momentum",
                field="close",
                momentum_window=window,
            )

    tanh_momentum_match = re.fullmatch(
        r"rank\(tanh\(ts_delta\(close,(\d+)\)/ts_shift\(close,\1\)\)\)",
        key,
    )
    if tanh_momentum_match:
        window = int(tanh_momentum_match.group(1))
        if 1 <= window <= 120:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="tanh_momentum",
                field="close",
                momentum_window=window,
            )

    volatility_match = re.fullmatch(r"rank\(ts_std\(close,(\d+)\)\)", key)
    if volatility_match:
        window = int(volatility_match.group(1))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="volatility",
                field="close",
                volatility_window=window,
            )

    correlation_match = re.fullmatch(
        r"rank\(ts_corr\((?:rank\()?close\)?,(?:rank\()?volume\)?,(\d+)\)\)",
        key,
    )
    if correlation_match:
        window = int(correlation_match.group(1))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="correlation",
                field="close",
                second_field="volume",
                correlation_window=window,
            )

    where_mean_match = re.fullmatch(
        r"rank\(where\(close>ts_mean\(close,(\d+)\),close/ts_mean\(close,\1\),0\)\)",
        key,
    )
    if where_mean_match:
        window = int(where_mean_match.group(1))
        if 2 <= window <= 252:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="where_mean",
                field="close",
                mean_window=window,
            )

    hybrid_match = re.fullmatch(
        r"rank\(\(close/ts_mean\(close,(\d+)\)\)\*\(ts_delta\(close,(\d+)\)/ts_shift\(close,\2\)\)\)",
        key,
    )
    if hybrid_match:
        mean_window = int(hybrid_match.group(1))
        momentum_window = int(hybrid_match.group(2))
        if 2 <= mean_window <= 252 and 1 <= momentum_window <= 120:
            return SupportedFactorExpression(
                expression=normalized,
                key=key,
                kind="hybrid",
                field="close",
                mean_window=mean_window,
                momentum_window=momentum_window,
            )

    return None


def validate_quantgpt_candidate_expression(
    expression: str,
    *,
    max_length: int = 500,
    max_depth: int = 10,
) -> SupportedFactorExpression:
    """Validate a QuantGPT candidate against QuantMind's executable contract."""
    normalized = normalize_factor_expression(expression)
    lowered = normalized.lower()
    if not normalized:
        raise ValueError("factor expression is empty")
    if len(normalized) > max_length:
        raise ValueError("factor expression is too long")
    if not _SAFE_CHARS_RE.fullmatch(normalized):
        raise ValueError("factor expression contains unsafe characters")
    if any(token in lowered for token in _BLOCKED_TOKENS):
        raise ValueError("factor expression contains blocked token")
    if expression_nesting_depth(normalized) > max_depth:
        raise ValueError("factor expression nesting is too deep")

    parsed = parse_supported_factor_expression(normalized)
    if parsed is None:
        raise ValueError("factor expression is not supported by QuantMind evaluator")
    return parsed


def is_quantmind_executable_expression(expression: str) -> bool:
    try:
        validate_quantgpt_candidate_expression(expression)
    except ValueError:
        return False
    return True
