class FactorValidationError(ValueError):
    """Base error for the bounded Factor Validation protocol."""


class LabelContractError(FactorValidationError):
    pass


class ValidationDatasetError(FactorValidationError):
    pass


class ValidationSpecError(FactorValidationError):
    pass


class ValidationArtifactError(FactorValidationError):
    pass


class FrozenAccessError(FactorValidationError):
    pass
