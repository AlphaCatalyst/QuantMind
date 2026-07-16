class FactorDslError(ValueError):
    """Base error for a rejected Factor DSL operation."""


class TemplateValidationError(FactorDslError):
    pass


class AdmissionError(FactorDslError):
    pass


class ExecutionError(FactorDslError):
    pass


class ArtifactValidationError(FactorDslError):
    pass
