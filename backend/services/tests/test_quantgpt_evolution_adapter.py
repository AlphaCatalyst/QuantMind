import pytest

from backend.services.engine.research.quantgpt_evolution_adapter import (
    generate_quantgpt_evolution_candidates,
)
from backend.services.engine.research.quantgpt_expression_guard import (
    is_quantmind_executable_expression,
    validate_quantgpt_candidate_expression,
)


def test_quantgpt_expression_guard_accepts_current_evaluator_contract():
    parsed = validate_quantgpt_candidate_expression(
        "rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))"
    )

    assert parsed.kind == "hybrid"
    assert parsed.mean_window == 20
    assert parsed.momentum_window == 5
    assert (
        validate_quantgpt_candidate_expression(
            "rank(ts_corr(rank(close), rank(volume), 10))"
        ).kind
        == "correlation"
    )
    assert (
        validate_quantgpt_candidate_expression("rank(ts_std(close, 20))").kind
        == "volatility"
    )
    assert (
        validate_quantgpt_candidate_expression(
            "rank(tanh(ts_delta(close, 5) / ts_shift(close, 5)))"
        ).kind
        == "tanh_momentum"
    )
    assert (
        validate_quantgpt_candidate_expression(
            "rank(amount / ts_mean(amount, 20))"
        ).kind
        == "mean"
    )
    assert (
        validate_quantgpt_candidate_expression("rank(ts_rank(close, 20))").kind
        == "ts_rank"
    )
    assert (
        validate_quantgpt_candidate_expression("rank(decay_linear(close, 20))").kind
        == "decay_linear"
    )
    assert (
        validate_quantgpt_candidate_expression("rank(zscore(close, 20))").kind
        == "rolling_zscore"
    )
    assert (
        validate_quantgpt_candidate_expression("rank(scale(volume))").kind
        == "scale_cross_sectional"
    )
    assert (
        validate_quantgpt_candidate_expression(
            "rank(where(close > ts_mean(close, 20), close / ts_mean(close, 20), 0))"
        ).kind
        == "where_mean"
    )


def test_quantgpt_expression_guard_rejects_unsafe_or_unsupported_expression():
    with pytest.raises(ValueError, match="blocked token|unsafe|not supported"):
        validate_quantgpt_candidate_expression("__import__('os').system('echo x')")

    with pytest.raises(ValueError, match="not supported"):
        validate_quantgpt_candidate_expression("rank(ts_mean(amount, 10))")

    with pytest.raises(ValueError, match="not supported"):
        validate_quantgpt_candidate_expression("rank(ts_corr(rank(close), rank(amount), 10))")


def test_quantgpt_meta_evolution_generates_only_executable_candidates():
    result = generate_quantgpt_evolution_candidates(
        seed_expressions=[
            "rank(close / ts_mean(close, 20))",
            "rank(ts_delta(close, 5) / ts_shift(close, 5))",
        ],
        max_candidates=6,
        strategy="quantgpt_meta_evolution",
        iteration_history=[
            {"expression": "rank(close / ts_mean(close, 20))", "score": 20.0},
            {
                "expression": "rank(ts_delta(close, 5) / ts_shift(close, 5))",
                "score": 55.0,
            },
        ],
    )

    assert result.strategy == "quantgpt_meta_evolution"
    assert result.candidates
    assert all(
        is_quantmind_executable_expression(candidate.expression)
        for candidate in result.candidates
    )


def test_quantgpt_crossover_respects_excluded_expression_keys():
    result = generate_quantgpt_evolution_candidates(
        seed_expressions=[
            "rank(close / ts_mean(close, 20))",
            "rank(ts_delta(close, 5) / ts_shift(close, 5))",
            "rank(close / ts_mean(close, 40))",
            "rank(ts_delta(close, 10) / ts_shift(close, 10))",
        ],
        max_candidates=3,
        strategy="quantgpt_crossover_only",
        exclude_keys={
            "rank((close/ts_mean(close,20))*(ts_delta(close,5)/ts_shift(close,5)))"
        },
    )

    assert result.candidates
    assert all(
        "20)) * (ts_delta(close, 5)" not in item.expression
        for item in result.candidates
    )
