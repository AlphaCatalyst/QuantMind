class UnifiedSignalError(ValueError):
    """Raised when a unified-signal contract or artifact is invalid."""


class LegacyMarketDataAuthorityForbidden(UnifiedSignalError):
    code = "LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN"
