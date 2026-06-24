from __future__ import annotations

from backend.shared.model_registry import ModelRegistryService


def test_training_run_model_metadata_preserves_factor_research_context(tmp_path):
    service = ModelRegistryService()
    service.user_models_root = tmp_path

    metadata = service._build_training_run_model_metadata(
        run_id="train-factor-1",
        request_payload={
            "display_name": "因子研究 Shadow 训练 - factor_alpha",
            "target_horizon_days": 5,
            "target_mode": "return",
            "label_formula": "return_t_plus_5",
            "training_window": "2025-01-01~2025-12-31",
            "factor_research": {
                "promotion_id": "promotion-1",
                "candidate_id": "candidate-1",
                "factor_run_id": "run-1",
                "feature_key": "factor_alpha",
                "feature_set_version_id": "feature-set-1",
                "expression": "rank(close / mean(close, 20))",
                "pipeline_stage": "factor_shadow_training",
                "includes_promoted_factor": True,
                "baseline_training_run_id": "baseline-train-1",
            },
        },
        result_payload={"metadata": {"trainer": "unit-test"}},
    )

    assert metadata["display_name"] == "因子研究 Shadow 训练 - factor_alpha"
    assert metadata["trainer"] == "unit-test"
    assert metadata["source_pipeline"] == "factor_shadow_training"
    assert metadata["promoted_factor_key"] == "factor_alpha"
    assert metadata["promoted_factor_expression"] == "rank(close / mean(close, 20))"
    assert metadata["feature_set_version_id"] == "feature-set-1"
    assert metadata["factor_research"]["promotion_id"] == "promotion-1"
    assert metadata["factor_research"]["baseline_training_run_id"] == "baseline-train-1"
