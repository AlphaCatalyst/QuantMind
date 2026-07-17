class ArtifactStoreError(RuntimeError):
    """Stable, safe Artifact Store failure."""

    code = "ARTIFACT_STORE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.code


class StoreFormatError(ArtifactStoreError):
    code = "STORE_FORMAT_ERROR"


class SourceSecurityError(ArtifactStoreError):
    code = "SOURCE_SECURITY_ERROR"


class DomainValidationError(ArtifactStoreError):
    code = "DOMAIN_VALIDATION_FAILED"


class BlobContentConflict(ArtifactStoreError):
    code = "BLOB_CONTENT_CONFLICT"


class ArtifactDescriptorConflict(ArtifactStoreError):
    code = "ARTIFACT_DESCRIPTOR_CONFLICT"


class ArtifactNotFound(ArtifactStoreError):
    code = "ARTIFACT_NOT_FOUND"


class MaterializationError(ArtifactStoreError):
    code = "MATERIALIZATION_ERROR"
