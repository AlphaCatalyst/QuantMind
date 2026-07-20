STRATEGY_OPTIMIZATION_SPEC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "StrategyOptimizationSpec v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "name", "description", "unified_signal_ids", "universe_id",
        "qlib_view_id", "research_period", "retrospective_holdout_periods", "search_space",
        "budget", "execution_contract", "benchmark_policy", "eligibility", "ordering",
        "evidence_policy", "data_authority",
    ],
}
