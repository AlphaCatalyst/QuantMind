from collections import defaultdict

from backend.services.engine.factor_dsl.enums import NodeKind

from .enums import ParameterRole
from .errors import OptimizationAdmissionError


def parameter_usage(expression):
    uses = defaultdict(set)

    def visit(node, context="arithmetic_scalar"):
        if node.kind is NodeKind.PARAMETER:
            uses[node.fields["name"]].add(context)
            return
        for name, value in node.fields.items():
            if not hasattr(value, "kind"):
                continue
            child_context = "lookback_window" if name in {"window", "periods"} else "arithmetic_scalar"
            visit(value, child_context)
    visit(expression)
    return {name: frozenset(contexts) for name, contexts in uses.items()}


def validate_parameter_roles(template, roles):
    declared = {p.name for p in template.parameters}
    if set(roles) - declared:
        raise OptimizationAdmissionError(f"roles reference undeclared parameters: {sorted(set(roles)-declared)}")
    usage = parameter_usage(template.expression)
    for name, role in roles.items():
        contexts = usage.get(name, frozenset())
        if role is ParameterRole.SIGNAL_THRESHOLD:
            raise OptimizationAdmissionError("signal_threshold is reserved but unavailable before the Signal stage")
        expected = "lookback_window" if role is ParameterRole.LOOKBACK_WINDOW else "arithmetic_scalar"
        if not contexts or contexts != {expected}:
            raise OptimizationAdmissionError(f"parameter {name} role {role.value} conflicts with AST uses {sorted(contexts)}")
