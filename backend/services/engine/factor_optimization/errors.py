class FactorOptimizationError(ValueError):
    """Base error for a rejected or failed bounded optimization operation."""


class OptimizationSpecError(FactorOptimizationError):
    pass


class OptimizationAdmissionError(FactorOptimizationError):
    pass


class OptimizationArtifactError(FactorOptimizationError):
    pass
