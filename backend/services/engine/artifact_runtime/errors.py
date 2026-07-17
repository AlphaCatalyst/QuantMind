class ArtifactRuntimeError(RuntimeError):
    """Stable and safe Artifact Runtime failure."""

    code = "ARTIFACT_RUNTIME_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.code


class InvalidRuntimeMode(ArtifactRuntimeError):
    code = "INVALID_ARTIFACT_RUNTIME_MODE"


class LegacyArtifactPathForbidden(ArtifactRuntimeError):
    code = "LEGACY_ARTIFACT_PATH_FORBIDDEN"


class ArtifactReferenceMismatch(ArtifactRuntimeError):
    code = "ARTIFACT_REFERENCE_MISMATCH"


class ArtifactResolutionError(ArtifactRuntimeError):
    code = "ARTIFACT_RESOLUTION_FAILED"


class ArtifactPublicationError(ArtifactRuntimeError):
    code = "ARTIFACT_PUBLICATION_FAILED"


class ResearchStateRecoveryError(ArtifactRuntimeError):
    code = "RESEARCH_STATE_RECOVERY_FAILED"
