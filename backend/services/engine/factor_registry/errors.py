class FactorRegistryError(ValueError):
    """Safe base error for Registry contract violations."""


class RegistryEvidenceError(FactorRegistryError):
    pass


class RegistryPolicyError(FactorRegistryError):
    pass


class RegistryDecisionError(FactorRegistryError):
    pass


class RegistryArtifactError(FactorRegistryError):
    pass
