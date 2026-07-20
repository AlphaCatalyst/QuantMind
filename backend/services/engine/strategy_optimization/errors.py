class StrategyOptimizationError(ValueError):
    """Stable strategy-optimization contract failure."""

    def __init__(self, message: str, *, code: str = "STRATEGY_OPTIMIZATION_INVALID") -> None:
        super().__init__(message)
        self.code = code
