"""JSON-schema-shaped public contracts; runtime parsing remains the authority."""

STRATEGY_SPEC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "StrategySpec v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "name", "description", "unified_signal_id", "universe_id", "qlib_view_id",
        "start_date", "end_date", "selection", "rebalance", "weighting", "execution", "costs",
        "benchmark", "quality_gates", "evidence_policy", "data_authority",
    ],
}
