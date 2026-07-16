def parameter(name):
    return {"type": "parameter", "name": name}


def feature(name):
    return {"type": "feature", "name": name}


def rolling_rank_template(feature_name="mom_ret_1d"):
    return {"schema_version": "1.0.0", "name": "rolling_rank", "description": "Rank of a parameterized trailing mean.",
            "dataset_kinds": ["legacy_feature_matrix_v1"],
            "parameters": [{"name": "window", "type": "integer", "default": 5, "minimum": 2, "maximum": 20, "step": 1}],
            "expression": {"type": "cs_rank", "operand": {"type": "rolling_mean", "operand": feature(feature_name), "window": parameter("window")}},
            "output": {"name": "rolling_rank"}}


def weighted_delta_template(feature_a="mom_ret_1d", feature_b="liq_volume_ratio_5"):
    return {"schema_version": "1.0.0", "name": "weighted_delta", "description": "Weighted combination of two time-series deltas.",
            "dataset_kinds": ["legacy_feature_matrix_v1"],
            "parameters": [{"name": "weight", "type": "number", "default": 0.5, "minimum": 0.0, "maximum": 1.0, "step": 0.1},
                           {"name": "periods", "type": "integer", "default": 3, "minimum": 1, "maximum": 10, "step": 1}],
            "expression": {"type": "add", "left": {"type": "multiply", "left": parameter("weight"), "right": {"type": "delta", "operand": feature(feature_a), "periods": parameter("periods")}},
                           "right": {"type": "multiply", "left": {"type": "subtract", "left": {"type": "constant", "value": 1.0}, "right": parameter("weight")}, "right": {"type": "delta", "operand": feature(feature_b), "periods": parameter("periods")}}},
            "output": {"name": "weighted_delta"}}


def normalized_spread_template(feature_a="style_beta_20", feature_b="style_idio_vol_20"):
    return {"schema_version": "1.0.0", "name": "normalized_spread", "description": "Cross-sectional z-score of a safe normalized spread.",
            "dataset_kinds": ["legacy_feature_matrix_v1"], "parameters": [],
            "expression": {"type": "cs_zscore", "operand": {"type": "divide", "left": {"type": "subtract", "left": feature(feature_a), "right": feature(feature_b)},
                           "right": {"type": "add", "left": {"type": "absolute", "operand": feature(feature_b)}, "right": {"type": "constant", "value": 1e-06}}}},
            "output": {"name": "normalized_spread"}}
