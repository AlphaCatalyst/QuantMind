from backend.services.engine.factor_dsl.identity import ENGINE_VERSION as DSL_ENGINE_VERSION

from .canonical import hash_payload, spec_payload


OPTIMIZATION_SCHEMA_VERSION = "1.0.0"
OPTIMIZATION_ENGINE_VERSION = "1.0.0"


def study_id(spec, template_id):
    return "fos_" + hash_payload({"optimization_spec": spec_payload(spec), "template_id": template_id,
                                  "snapshot_id": spec.snapshot_id, "factor_dsl_engine_version": DSL_ENGINE_VERSION,
                                  "factor_optimization_engine_version": OPTIMIZATION_ENGINE_VERSION})


def trial_id(study_id_value, parameters, factor_instance_id):
    return "fot_" + hash_payload({"study_id": study_id_value, "parameters": dict(sorted(parameters.items())),
                                  "factor_instance_id": factor_instance_id})


def result_id(study_id_value, trial_summaries, candidate_order, study_manifest_hash):
    return "for_" + hash_payload({"study_id": study_id_value, "trial_results": trial_summaries,
                                  "validation_candidate_order": list(candidate_order),
                                  "study_manifest_hash": study_manifest_hash})
