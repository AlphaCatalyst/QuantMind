"""JSON-schema-shaped public contracts; runtime parsing remains the authority."""

UNIFIED_SIGNAL_SPEC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "UnifiedSignalSpec v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "name", "description", "inputs", "transformation", "combination",
        "weights", "missing_policy", "universe_id", "dataset_id", "start_date", "end_date",
        "data_authority", "predictive_claim", "eligible_for_production",
    ],
}
