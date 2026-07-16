from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .enums import NodeKind, ParameterType, ValueKind


@dataclass(frozen=True)
class ParameterDefinition:
    name: str
    parameter_type: ParameterType
    default: float
    minimum: float
    maximum: float
    step: Optional[float] = None


@dataclass(frozen=True)
class ExpressionNode:
    kind: NodeKind
    fields: Mapping[str, Any]


@dataclass(frozen=True)
class FactorTemplate:
    schema_version: str
    name: str
    description: str
    dataset_kinds: Tuple[str, ...]
    parameters: Tuple[ParameterDefinition, ...]
    expression: ExpressionNode
    output_name: str


@dataclass(frozen=True)
class SnapshotContract:
    snapshot_id: str
    dataset_kind: str
    feature_roles: Mapping[str, str]
    date_count: int
    feature_types: Mapping[str, str]


@dataclass(frozen=True)
class BoundFactorInstance:
    factor_instance_id: str
    factor_template_id: str
    dataset_snapshot_id: str
    engine_version: str
    bound_parameters: Mapping[str, float]


@dataclass(frozen=True)
class FactorValuesArtifact:
    factor_values_id: str
    artifact_path: str
    manifest: Mapping[str, Any]


@dataclass(frozen=True)
class CompiledFactor:
    template_id: str
    factor_instance_id: str
    snapshot_id: str
    engine_version: str
    template: FactorTemplate
    bound_parameters: Mapping[str, float]
    required_features: Tuple[str, ...]
    output_kind: ValueKind
    node_count: int
    depth: int
    warmup_periods: int
    warnings: Tuple[str, ...]

    @property
    def bound_instance(self) -> BoundFactorInstance:
        return BoundFactorInstance(self.factor_instance_id, self.template_id, self.snapshot_id,
                                   self.engine_version, self.bound_parameters)


@dataclass(frozen=True)
class ExecutionResult:
    factor_values_id: str
    artifact_path: str
    manifest: Dict[str, Any]
    replayed: bool

    @property
    def artifact(self) -> FactorValuesArtifact:
        return FactorValuesArtifact(self.factor_values_id, self.artifact_path, self.manifest)
