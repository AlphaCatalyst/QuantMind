from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.cross_sectional_alpha_discovery.engine import (
    _agent_schema,
    _window_gate,
)
from backend.services.engine.cross_sectional_alpha_discovery.models import (
    CrossSectionalBatchBudgetV1,
    CrossSectionalDiscoveryBatchSpecV1,
    empty_counts,
)
from backend.services.engine.cross_sectional_alpha_discovery.ranking import (
    RankingModelSpecV1,
    RankingRelevanceLabelV1,
    relevance_labels,
)
from backend.services.engine.cross_sectional_alpha_discovery.residualization import (
    CONTROL_NAMES,
    CrossSectionalStyleResidualizationV1,
    residualize_scores,
)


def _cross_section(
    *,
    dates: int = 2,
    members: int = 100,
    zero_variance: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw, controls = [], []
    for day in range(dates):
        date = f"2020-01-{day + 2:02d}"
        for index in range(members):
            symbol = f"SH{600000 + index:06d}"
            raw.append(
                {
                    "symbol": symbol,
                    "trade_date": date,
                    "factor_value": 2.0 * index + day + np.sin(index * 0.37),
                }
            )
            controls.append(
                {
                    "symbol": symbol,
                    "trade_date": date,
                    "log_circ_mv": 1.0 if zero_variance == "log_circ_mv" else index,
                    "style_beta_20": (index % 17) + day,
                    "style_idio_vol_20": (index % 13) - day,
                    "amount_ratio_20": (index % 11) + 0.5 * day,
                }
            )
    return pd.DataFrame(raw), pd.DataFrame(controls)


def test_residualization_contract_is_pit_and_fixed():
    contract = CrossSectionalStyleResidualizationV1().payload(
        control_audit={name: {"pit_safe": True} for name in CONTROL_NAMES}
    )
    assert contract["controls"] == CONTROL_NAMES
    assert contract["pit_violation_count"] == 0
    assert contract["return_or_label_reads"] == 0
    assert contract["fit_scope"] == "one_trade_date_only"


def test_same_date_ols_removes_linear_style_exposure():
    raw, controls = _cross_section()
    result, evidence = residualize_scores(raw, controls)
    assert evidence["evaluated_date_count"] == 2
    for date, group in result.groupby("trade_date"):
        merged = group.merge(controls, on=["symbol", "trade_date"])
        for name in CONTROL_NAMES:
            correlation = merged["factor_value"].corr(merged[name])
            assert abs(correlation) < 1e-10
        assert abs(group["factor_value"].mean()) < 1e-12
        assert group["factor_value"].std(ddof=0) == pytest.approx(1.0)


def test_zero_variance_control_is_dropped_and_recorded():
    raw, controls = _cross_section(zero_variance="log_circ_mv")
    result, evidence = residualize_scores(raw, controls)
    assert len(result) == len(raw)
    assert {
        item["control"] for item in evidence["zero_variance_control_drops"]
    } == {"log_circ_mv"}


def test_minimum_member_gate_fails_closed():
    raw, controls = _cross_section(members=79)
    result, evidence = residualize_scores(raw, controls)
    assert result.empty
    assert evidence["insufficient_date_count"] == 2


def test_residualization_preserves_raw_direction_metadata():
    raw, controls = _cross_section()
    result, evidence = residualize_scores(raw, controls)
    assert evidence["direction_preserved"] is True
    assert result["raw_factor_value"].equals(
        raw.sort_values(["trade_date", "symbol"])["factor_value"].reset_index(drop=True)
    )


def test_ranking_relevance_is_same_date_quintile():
    frame = pd.DataFrame(
        {
            "trade_date": ["2020-01-02"] * 10 + ["2020-01-03"] * 10,
            "symbol": [f"S{i:02d}" for i in range(10)] * 2,
            "raw_label": list(range(10)) + list(reversed(range(10))),
        }
    )
    labels = relevance_labels(frame)
    assert labels.iloc[:10].tolist() == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    assert labels.iloc[10:].tolist() == [4, 4, 3, 3, 2, 2, 1, 1, 0, 0]


def test_ranking_label_and_model_are_frozen_before_training():
    label = RankingRelevanceLabelV1().payload()
    model = RankingModelSpecV1().payload(
        relevance_label_id=label["ranking_relevance_label_id"]
    )
    assert label["frozen_before_first_training"] is True
    assert model["objective"] == "lambdarank"
    assert model["metric"] == "ndcg"
    assert model["ndcg_eval_at"] == (20,)
    assert model["seeds"] == (20260701, 20260702, 20260703)
    assert model["seed_ensemble"] == "equal_weight"
    assert model["model_hyperparameter_optimization_calls"] == 0
    assert model["early_stopping"] is False
    assert model["num_threads"] == 1


def test_batch_budget_and_semantics_are_exact():
    spec = CrossSectionalDiscoveryBatchSpecV1()
    spec.budgets.validate()
    assert spec.batch_name == "rolling_blind_discovery_batch_002"
    assert spec.evidence_semantics == "historical_rolling_evaluation"
    assert spec.budgets == CrossSectionalBatchBudgetV1()
    with pytest.raises(ValueError):
        CrossSectionalBatchBudgetV1(maximum_agent_calls=17).validate()


def test_agent_schema_requires_residualization_explanation():
    item = _agent_schema()["properties"]["proposals"]["items"]
    assert "why_style_residualization_is_relevant" in item["required"]
    assert item["properties"]["why_style_residualization_is_relevant"][
        "type"
    ] == "string"


def _rolling_rows(kind: str) -> list[dict]:
    rows = []
    for index in range(18):
        row = {
            "primary_metric": 0.01,
            "csi300_excess": 0.02,
            "turnover": 10.0,
            "best_10_days_contribution": 0.20,
            "configuration_unchanged": True,
        }
        if kind == "style_residual_dsl":
            row |= {"raw_rankic": 0.009, "residual_rankic": 0.01}
        else:
            row |= {"ndcg_at_20": 0.72, "random_ndcg_at_20": 0.60}
        rows.append(row)
    return rows


@pytest.mark.parametrize("kind", ["style_residual_dsl", "ranking_model"])
def test_complete_rolling_gate_passes_only_all_18(kind):
    rows = _rolling_rows(kind)
    assert _window_gate(rows, kind)["passed"] is True
    assert _window_gate(rows[:-1], kind)["passed"] is False


def test_residual_gate_requires_not_worse_than_raw():
    rows = _rolling_rows("style_residual_dsl")
    for row in rows:
        row["raw_rankic"] = 0.02
    gate = _window_gate(rows, "style_residual_dsl")
    assert gate["checks"]["residual_not_worse_than_raw"] is False


def test_ranking_gate_requires_ndcg_above_random():
    rows = _rolling_rows("ranking_model")
    for row in rows:
        row["random_ndcg_at_20"] = 0.80
    gate = _window_gate(rows, "ranking_model")
    assert gate["checks"]["ndcg_above_random"] is False


def test_runtime_replay_counts_are_all_zero():
    counts = empty_counts()
    assert all(value == 0 for value in counts.values())
    assert counts["promotion_writes"] == 0
    assert counts["fresh_lock_writes"] == 0


def test_artifact_registry_contains_batch002_kinds():
    from backend.services.engine.artifact_store.enums import ArtifactKind
    from backend.services.engine.autonomous_factor_campaign.artifact import KINDS

    required = {
        "cross_sectional_style_residualization",
        "ranking_model_spec",
        "ranking_relevance_label",
        "rolling_blind_candidate_batch_lock_v2",
        "rolling_style_residual_result",
        "rolling_ranking_model_result",
        "rolling_evaluation_multiple_testing",
        "rolling_evaluation_alpha_survivor",
    }
    assert required <= {item.value for item in ArtifactKind}
    assert required <= set(KINDS)


def test_supervisor_cli_exposes_only_explicit_batch002_command():
    source = Path("tools/quantmind2/run_autonomous_research_supervisor.py").read_text()
    assert "run-next-cross-sectional-alpha-batch" in source
    assert "run-next-rolling-blind-batch-003" not in source


def test_contract_json_is_secret_free():
    label = RankingRelevanceLabelV1().payload()
    model = RankingModelSpecV1().payload(
        relevance_label_id=label["ranking_relevance_label_id"]
    )
    text = json.dumps(model).lower()
    assert "tushare_token" not in text
    assert "api_key" not in text
