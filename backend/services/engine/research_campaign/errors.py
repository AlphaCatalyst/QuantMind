class ResearchCampaignError(Exception):
    """Base error for deterministic campaign control."""


class AgentContractError(ResearchCampaignError):
    """Agent output did not satisfy the closed decision contract."""


class ProposalParameterContractError(AgentContractError):
    """Structured, safe Proposal parameter diagnostic for one repair attempt."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(f"{detail['error_code']} at {detail['field_path']}")

    def repair_payload(self):
        return dict(self.detail)


class CampaignArtifactError(ResearchCampaignError):
    """Campaign artifact is incomplete, mutable, or inconsistent."""
