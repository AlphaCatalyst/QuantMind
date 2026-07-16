import copy
import json

import pytest
from jsonschema import Draft202012Validator

from backend.services.engine.factor_dsl.canonical import canonical_json_bytes
from backend.services.engine.factor_dsl.errors import TemplateValidationError
from backend.services.engine.factor_dsl.examples import rolling_rank_template
from backend.services.engine.factor_dsl.identity import factor_template_id
from backend.services.engine.factor_dsl.parser import parse_template
from backend.services.engine.factor_dsl.schema import factor_template_schema


def test_schema_and_parser_cover_strict_template_contract():
    schema = factor_template_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["additionalProperties"] is False
    parsed = parse_template(rolling_rank_template())
    Draft202012Validator(schema).validate(rolling_rank_template())
    assert parsed.schema_version == "1.0.0"
    assert factor_template_id(parsed).startswith("ft_")


@pytest.mark.parametrize("mutation", [
    lambda x: x.update({"factor_template_id": "agent-chosen"}),
    lambda x: x["expression"].update({"python": "eval('bad')"}),
    lambda x: x.update({"description": "api_key=should-not-enter-contract"}),
    lambda x: x["expression"].update({"type": "arbitrary_python"}),
])
def test_parser_rejects_unknown_fields_ids_secret_like_text_and_unknown_nodes(mutation):
    payload = rolling_rank_template(); mutation(payload)
    with pytest.raises(TemplateValidationError):
        parse_template(payload)


def test_template_identity_is_canonical_and_parameter_instance_not_embedded():
    first = rolling_rank_template()
    second = json.loads(json.dumps(first, sort_keys=True))
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert factor_template_id(parse_template(first)) == factor_template_id(parse_template(second))
    assert "snapshot_id" not in first and "factor_instance_id" not in first


def test_parser_rejects_invalid_parameter_ranges_and_nonfinite_constants():
    bad = rolling_rank_template(); bad["parameters"][0]["default"] = 100
    with pytest.raises(TemplateValidationError): parse_template(bad)
    bad = rolling_rank_template(); bad["expression"] = {"type": "constant", "value": float("nan")}
    with pytest.raises(TemplateValidationError): parse_template(bad)


def test_parser_rejects_duplicate_or_excess_parameters_and_invalid_output():
    bad = rolling_rank_template(); bad["parameters"].append(copy.deepcopy(bad["parameters"][0]))
    with pytest.raises(TemplateValidationError): parse_template(bad)
    bad = rolling_rank_template(); bad["parameters"] = [dict(bad["parameters"][0], name=f"p{i}") for i in range(9)]
    with pytest.raises(TemplateValidationError): parse_template(bad)
    bad = rolling_rank_template(); bad["output"] = {"name": "not safe"}
    with pytest.raises(TemplateValidationError): parse_template(bad)


def test_parser_rejects_nonexistent_lookahead_operator():
    bad = rolling_rank_template(); bad["expression"] = {"type": "lead", "operand": {"type": "feature", "name": "mom_ret_1d"}, "periods": {"type": "constant", "value": 1}}
    with pytest.raises(TemplateValidationError): parse_template(bad)
