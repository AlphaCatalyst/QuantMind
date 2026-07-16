from .canonical import sha256_id, template_payload


ENGINE_VERSION = "quantmind-factor-dsl-v1"


def factor_template_id(template):
    return sha256_id("ft_", template_payload(template))


def factor_instance_id(template_id, snapshot_id, parameters, engine_version=ENGINE_VERSION):
    return sha256_id("fi_", {"engine_version": engine_version, "parameters": dict(sorted(parameters.items())),
                             "snapshot_id": snapshot_id, "template_id": template_id})


def factor_values_id(instance_id, parquet_sha256, output_schema):
    return sha256_id("fv_", {"factor_instance_id": instance_id, "output_schema": output_schema,
                             "parquet_sha256": parquet_sha256})
