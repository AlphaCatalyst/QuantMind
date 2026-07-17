from enum import Enum


class RegistryStatus(str, Enum):
    RESEARCH_REGISTERED = "research_registered"
    VALIDATION_REJECTED = "validation_rejected"
    VALIDATION_PASSED_NOT_SELECTED = "validation_passed_not_selected"
    FROZEN_REJECTED = "frozen_rejected"
    PROMOTION_CANDIDATE = "promotion_candidate"
    APPROVED = "approved"
    ACTIVE = "active"
    RETIRED = "retired"
    INVALIDATED = "invalidated"


class PromotionAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ACTIVATE = "activate"
    RETIRE = "retire"
    INVALIDATE = "invalidate"


class DecisionSource(str, Enum):
    HUMAN = "human"
    CONTROL_LAYER = "control_layer"
