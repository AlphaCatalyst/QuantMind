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

__all__ = (
    "ArchitectureDecisionReferenceRecord",
    "ChangedFileRecord",
    "ChangedSymbolRecord",
    "ComponentReferenceRecord",
    "ImplementationArtifactRecord",
    "ImplementationRunRecord",
    "ImplementationTaskRecord",
    "RunRelationshipRecord",
    "TestExecutionRecord",
)
