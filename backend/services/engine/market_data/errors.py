class MarketDataError(Exception):
    """Base error that never embeds credentials."""


class InvalidMarketDataRequest(MarketDataError):
    pass


class ProviderUnavailableError(MarketDataError):
    pass


class NormalizationError(MarketDataError):
    pass


class DataQualityError(MarketDataError):
    pass


class SnapshotConflictError(MarketDataError):
    pass


class SnapshotValidationError(MarketDataError):
    pass
