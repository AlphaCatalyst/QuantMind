class CorporateActionError(RuntimeError):
    """Base error that must never contain credential or upstream message text."""


class CorporateActionCredentialError(CorporateActionError):
    """Raised when the environment-only credential is absent."""


class CorporateActionEvidenceInsufficient(CorporateActionError):
    """Raised when governed evidence cannot determine termination settlement."""

