from backend.services.engine.factor_dsl.examples import rolling_rank_template, weighted_delta_template


SNAPSHOT_ID = "ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7"


def rolling_rank_study_spec():
    return {"schema_version": "1.0.0", "name": "rolling_rank_window_search",
            "description": "Mechanical parameter search without predictive metrics.",
            "template": rolling_rank_template(), "snapshot_id": SNAPSHOT_ID,
            "parameter_roles": {"window": "lookback_window"},
            "search_space": {"window": {"kind": "explicit_values", "values": [2, 3, 5, 10, 20]}},
            "budget": {"max_trials": 5, "max_failed_trials": 0, "stop_on_first_error": False},
            "quality_gate": {}, "candidate_ordering": "mechanical_validation_readiness_v1"}


def weighted_delta_study_spec():
    return {"schema_version": "1.0.0", "name": "weighted_delta_parameter_search",
            "description": "Mechanical two-parameter search without labels.",
            "template": weighted_delta_template(), "snapshot_id": SNAPSHOT_ID,
            "parameter_roles": {"periods": "lookback_window", "weight": "factor_internal_weight"},
            "search_space": {"periods": {"kind": "explicit_values", "values": [1, 3, 5]},
                             "weight": {"kind": "explicit_values", "values": [0.2, 0.5, 0.8]}},
            "budget": {"max_trials": 9, "max_failed_trials": 0, "stop_on_first_error": False},
            "quality_gate": {}, "candidate_ordering": "mechanical_validation_readiness_v1"}
