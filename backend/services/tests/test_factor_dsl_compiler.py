import pytest

from backend.services.engine.factor_dsl.compiler import compile_template
from backend.services.engine.factor_dsl.errors import AdmissionError
from backend.services.engine.factor_dsl.examples import rolling_rank_template
from backend.services.engine.factor_dsl.models import SnapshotContract
from backend.services.engine.factor_dsl.parser import parse_template


CONTRACT = SnapshotContract("ds_" + "a" * 64, "legacy_feature_matrix_v1",
                            {"mom_ret_1d": "feature", "label": "label", "meta": "metadata",
                             "forbidden": "forbidden", "mystery": "unknown", "category": "feature"}, 60,
                            {"mom_ret_1d": "double", "category": "string"})


def test_compiler_binds_parameters_and_derives_lineage_and_warmup():
    compiled = compile_template(parse_template(rolling_rank_template()), CONTRACT, {"window": 10})
    assert compiled.bound_parameters == {"window": 10}
    assert compiled.required_features == ("mom_ret_1d",)
    assert compiled.warmup_periods == 9
    assert compiled.factor_instance_id.startswith("fi_")


@pytest.mark.parametrize("feature", ["label", "meta", "forbidden", "mystery", "missing", "Mom_Ret_1d", "category"])
def test_compiler_denies_label_unknown_missing_and_case_alias_features(feature):
    payload = rolling_rank_template(feature)
    with pytest.raises(AdmissionError): compile_template(parse_template(payload), CONTRACT)


def test_compiler_rejects_invalid_bounds_step_and_dataset_aware_window():
    template = parse_template(rolling_rank_template())
    for binding in ({"window": 1}, {"window": 5.5}, {"extra": 2}):
        with pytest.raises(AdmissionError): compile_template(template, CONTRACT, binding)
    short = SnapshotContract(CONTRACT.snapshot_id, CONTRACT.dataset_kind, CONTRACT.feature_roles, 4, CONTRACT.feature_types)
    with pytest.raises(AdmissionError): compile_template(template, short, {"window": 5})


def test_compiler_rejects_scalar_output_and_excess_depth():
    payload = rolling_rank_template(); payload["expression"] = {"type": "constant", "value": 1.0}
    with pytest.raises(AdmissionError): compile_template(parse_template(payload), CONTRACT)
    payload = rolling_rank_template(); node = {"type": "feature", "name": "mom_ret_1d"}
    for _ in range(17): node = {"type": "absolute", "operand": node}
    payload["expression"] = node
    with pytest.raises(AdmissionError): compile_template(parse_template(payload), CONTRACT)


def test_compiler_rejects_dataset_kind_series_window_and_node_budget():
    other = SnapshotContract(CONTRACT.snapshot_id, "daily_bars_v1", CONTRACT.feature_roles, 60, CONTRACT.feature_types)
    with pytest.raises(AdmissionError): compile_template(parse_template(rolling_rank_template()), other)
    bad = rolling_rank_template(); bad["expression"]["operand"]["window"] = {"type": "feature", "name": "mom_ret_1d"}
    with pytest.raises(AdmissionError): compile_template(parse_template(bad), CONTRACT)


def test_compiler_rejects_feature_terminal_budget():
    nodes = [{"type": "feature", "name": "mom_ret_1d"} for _ in range(17)]
    while len(nodes) > 1:
        next_nodes = []
        for index in range(0, len(nodes), 2):
            next_nodes.append(nodes[index] if index + 1 == len(nodes) else {"type": "add", "left": nodes[index], "right": nodes[index + 1]})
        nodes = next_nodes
    bad = rolling_rank_template(); bad["expression"] = nodes[0]
    with pytest.raises(AdmissionError): compile_template(parse_template(bad), CONTRACT)
    def constants(count):
        nodes = [{"type": "constant", "value": float(i + 1)} for i in range(count)]
        while len(nodes) > 1:
            nodes = [{"type": "add", "left": nodes[i], "right": nodes[i + 1]} for i in range(0, len(nodes), 2)]
        return nodes[0]
    bad = rolling_rank_template(); bad["expression"] = {"type": "add", "left": {"type": "feature", "name": "mom_ret_1d"}, "right": constants(64)}
    with pytest.raises(AdmissionError): compile_template(parse_template(bad), CONTRACT)


def test_identity_changes_with_parameter_snapshot_and_engine():
    from backend.services.engine.factor_dsl.identity import factor_instance_id
    template = parse_template(rolling_rank_template()); first = compile_template(template, CONTRACT, {"window": 3})
    second = compile_template(template, CONTRACT, {"window": 4})
    other_snapshot = SnapshotContract("ds_" + "b" * 64, CONTRACT.dataset_kind, CONTRACT.feature_roles, 60, CONTRACT.feature_types)
    third = compile_template(template, other_snapshot, {"window": 3})
    assert len({first.factor_instance_id, second.factor_instance_id, third.factor_instance_id}) == 3
    assert factor_instance_id(first.template_id, CONTRACT.snapshot_id, {"window": 3}, "other-engine") != first.factor_instance_id
    assert first.bound_instance.factor_template_id == first.template_id
