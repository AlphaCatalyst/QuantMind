"""Static ORM mappings for the Project Knowledge persistence boundary."""

from .orm_models import (
    ImplementationRunRecord,
    ImplementationTaskRecord,
    RunRelationshipRecord,
)
from .orm_detail_models import (
    ChangedFileRecord,
    ChangedSymbolRecord,
    ImplementationArtifactRecord,
    TestExecutionRecord,
)
from .orm_reference_models import (
    ArchitectureDecisionReferenceRecord,
    ComponentReferenceRecord,
)
from .orm_annotation_models import LimitationRecord, RecommendedTaskRecord

__all__ = (
    "ArchitectureDecisionReferenceRecord",
    "ChangedFileRecord",
    "ChangedSymbolRecord",
    "ComponentReferenceRecord",
    "ImplementationArtifactRecord",
    "ImplementationRunRecord",
    "ImplementationTaskRecord",
    "LimitationRecord",
    "RecommendedTaskRecord",
    "RunRelationshipRecord",
    "TestExecutionRecord",
)
