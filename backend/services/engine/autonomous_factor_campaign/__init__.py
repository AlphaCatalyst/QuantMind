"""Bounded, Store-backed autonomous factor research campaign."""

from .models import AutonomousFactorCampaignSpecV1
from .models_v2 import AutonomousFactorCampaignSpecV2
from .orchestrator import (
    create_campaign_spec,
    execute_campaign,
    inspect_campaign,
    replay_campaign,
    resume_campaign,
    validate_campaign,
)
from .orchestrator_v2 import (
    create_campaign_spec_v2,
    execute_campaign_v2,
    inspect_campaign_v2,
    replay_campaign_v2,
    resume_campaign_v2,
    validate_campaign_v2,
)

__all__ = [
    "AutonomousFactorCampaignSpecV1",
    "AutonomousFactorCampaignSpecV2",
    "create_campaign_spec",
    "execute_campaign",
    "inspect_campaign",
    "replay_campaign",
    "resume_campaign",
    "validate_campaign",
    "create_campaign_spec_v2",
    "execute_campaign_v2",
    "inspect_campaign_v2",
    "replay_campaign_v2",
    "resume_campaign_v2",
    "validate_campaign_v2",
]
