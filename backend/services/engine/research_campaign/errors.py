class ResearchCampaignError(Exception):
    """Base error for deterministic campaign control."""


class AgentContractError(ResearchCampaignError):
    """Agent output did not satisfy the closed decision contract."""


class CampaignArtifactError(ResearchCampaignError):
    """Campaign artifact is incomplete, mutable, or inconsistent."""
