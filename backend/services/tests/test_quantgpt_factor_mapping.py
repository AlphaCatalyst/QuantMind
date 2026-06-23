from datetime import date

import pytest

from backend.services.engine.research.factor_promotion import (
    evaluate_promotion_eligibility,
)
from backend.services.engine.research.quantgpt_mapping import (
    normalize_quantgpt_symbol,
    parse_evaluation_payload,
    parse_factor_values_payload,
)
from backend.services.engine.research.schemas import (
    QuantGPTCandidateMetrics,
    QuantGPTContractError,
)


def test_normalize_quantgpt_symbol_accepts_known_formats():
    assert normalize_quantgpt_symbol("sh.600519") == "SH600519"
    assert normalize_quantgpt_symbol("sz.000001") == "SZ000001"
    assert normalize_quantgpt_symbol("600519.SH") == "SH600519"
    assert normalize_quantgpt_symbol("SH600519") == "SH600519"


def test_normalize_quantgpt_symbol_rejects_unknown_format():
    with pytest.raises(QuantGPTContractError):
        normalize_quantgpt_symbol("BAD-CODE")


def test_parse_evaluation_payload_maps_metrics_and_stock_symbols():
    payload = {
        "task_id": "task-1",
        "status": "completed",
        "expression": "rank(close / ts_mean(close, 20))",
        "result": {
            "report_url": "/api/v1/reports/r.html",
            "backtest_summary": {
                "rank_ic_mean": 0.021,
                "ic_ir": 0.31,
                "turnover": 0.28,
                "wq_fitness": 0.7,
                "monotonicity_score": 0.74,
            },
            "scoring": {"score": 68.5, "grade": "B"},
            "anti_overfit": {"score": 71.0},
            "stock_factor_data": {
                "total_stock_count": 2,
                "stocks": [
                    {"stock_code": "sh.600519", "factor_value": 1.2},
                    {"stock_code": "BAD", "factor_value": 0.1},
                ],
            },
            "params": {
                "expression": "rank(close / ts_mean(close, 20))",
                "stock_count": 2,
                "trading_days": 180,
            },
        },
    }

    parsed = parse_evaluation_payload(payload)

    assert parsed.task_id == "task-1"
    assert parsed.status == "completed"
    assert parsed.report_url == "/api/v1/reports/r.html"
    assert parsed.invalid_symbol_count == 1
    assert parsed.normalized_stock_factor_data[0]["symbol"] == "SH600519"
    assert parsed.metrics is not None
    assert parsed.metrics.score == 68.5
    assert parsed.metrics.grade == "B"
    assert parsed.metrics.rank_ic_mean == 0.021
    assert parsed.metrics.coverage_days == 180


def test_parse_factor_values_payload_flattens_date_grouped_values():
    payload = {
        "expression": "rank(close)",
        "universe": "hs300",
        "start_date": "2026-01-01",
        "end_date": "2026-01-02",
        "data": [
            {
                "date": "2026-01-02",
                "values": {
                    "sh.600519": 1.25,
                    "000001.SZ": -0.5,
                    "BAD": 3.0,
                    "sz.000002": "nan",
                },
            }
        ],
    }

    parsed = parse_factor_values_payload(payload)

    assert parsed.invalid_symbol_count == 1
    assert len(parsed.rows) == 2
    assert parsed.rows[0].trade_date == date(2026, 1, 2)
    assert parsed.rows[0].symbol == "SH600519"
    assert parsed.rows[0].factor_value == 1.25
    assert parsed.rows[1].symbol == "SZ000001"
    assert parsed.rows[1].factor_value == -0.5


def test_promotion_policy_accepts_good_candidate_and_rejects_high_turnover():
    good = QuantGPTCandidateMetrics(
        score=72.0,
        grade="B",
        rank_ic_mean=0.018,
        ic_ir=0.22,
        turnover=0.30,
        wq_fitness=0.9,
        monotonicity_score=0.7,
        anti_overfit_score=70.0,
        coverage_days=160,
        total_stock_count=300,
    )
    assert evaluate_promotion_eligibility(good).eligible is True

    bad = QuantGPTCandidateMetrics(
        score=72.0,
        grade="B",
        rank_ic_mean=0.018,
        ic_ir=0.22,
        turnover=0.51,
        wq_fitness=0.9,
        monotonicity_score=0.7,
        anti_overfit_score=70.0,
        coverage_days=160,
        total_stock_count=300,
    )
    decision = evaluate_promotion_eligibility(bad)
    assert decision.eligible is False
    assert "turnover_above_threshold" in decision.reasons
