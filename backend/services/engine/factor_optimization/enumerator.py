import itertools

from backend.services.engine.factor_dsl.compiler import compile_template
from backend.services.engine.factor_dsl.identity import factor_template_id

from .errors import OptimizationAdmissionError
from .enums import ParameterRole
from .identity import study_id, trial_id
from .models import FactorOptimizationStudy, PlannedTrial


def plan_study(spec, snapshot_contract):
    names = tuple(sorted(spec.search_spaces))
    for name in names:
        if (spec.parameter_roles[name] is ParameterRole.LOOKBACK_WINDOW and
                any(value > snapshot_contract.date_count for value in spec.search_spaces[name].values)):
            raise OptimizationAdmissionError(
                f"lookback parameter {name} exceeds Snapshot date count"
            )
    combinations = list(itertools.product(*(spec.search_spaces[name].values for name in names)))
    if len(combinations) > spec.budget.max_trials:
        raise OptimizationAdmissionError(f"enumerated trial count {len(combinations)} exceeds max_trials")
    template_id = factor_template_id(spec.template)
    sid = study_id(spec, template_id)
    trials = []
    for ordinal, combination in enumerate(combinations):
        parameters = dict(zip(names, combination))
        compiled = compile_template(spec.template, snapshot_contract, parameters)
        trials.append(PlannedTrial(trial_id(sid, parameters, compiled.factor_instance_id), ordinal,
                                   parameters, compiled.factor_instance_id))
    return FactorOptimizationStudy(sid, template_id, spec.snapshot_id, tuple(trials), spec)
