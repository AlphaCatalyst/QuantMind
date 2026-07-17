from .canonical import hash_payload
from .errors import RegistryPolicyError
from .models import FactorPromotionPolicy


SAFETY_FIELDS = (
    "git_evidence_complete", "validation_artifact_valid",
    "frozen_artifact_required", "no_label_leakage",
    "development_quarantine_respected", "train_only_orientation",
    "frozen_candidate_selection_immutable", "frozen_reselection_forbidden",
)


def policy_payload(policy, *, include_identity=True):
    payload = dict(policy.__dict__)
    if not include_identity:
        payload.pop("policy_id", None); payload.pop("canonical_hash", None)
    return payload


def default_promotion_policy():
    source = {
        "version": "1.0.0",
        **{name: True for name in SAFETY_FIELDS},
        "minimum_frozen_valid_dates": 60,
        "minimum_frozen_median_daily_observations": 100,
        "minimum_oriented_frozen_mean_rank_ic": 0.01,
        "minimum_oriented_frozen_rank_icir": 0.10,
        "minimum_oriented_frozen_rank_ic_positive_rate": 0.52,
        "require_same_oriented_sign_as_validation": True,
        "requires_human_approval": True,
        "allows_auto_approval": False,
        "allows_auto_activation": False,
        "rationale": "Conservative Registry v1 governance gates; not a return guarantee.",
    }
    digest = hash_payload(source)
    return FactorPromotionPolicy(policy_id="fpp_" + digest,
        canonical_hash=digest, **source)


def validate_policy(policy):
    if not isinstance(policy, FactorPromotionPolicy) or policy.version != "1.0.0":
        raise RegistryPolicyError("unsupported promotion policy")
    if any(getattr(policy, name) is not True for name in SAFETY_FIELDS):
        raise RegistryPolicyError("promotion safety gates cannot be disabled")
    if policy.requires_human_approval is not True or policy.allows_auto_approval or policy.allows_auto_activation:
        raise RegistryPolicyError("automatic approval/activation is forbidden")
    if policy.minimum_frozen_valid_dates < 60 or policy.minimum_frozen_median_daily_observations < 100:
        raise RegistryPolicyError("frozen coverage gates cannot be weakened")
    if policy.minimum_oriented_frozen_mean_rank_ic < 0.01 or policy.minimum_oriented_frozen_rank_icir < 0.10 or policy.minimum_oriented_frozen_rank_ic_positive_rate < 0.52:
        raise RegistryPolicyError("frozen statistical gates cannot be weakened")
    source = policy_payload(policy, include_identity=False)
    digest = hash_payload(source)
    if policy.canonical_hash != digest or policy.policy_id != "fpp_" + digest:
        raise RegistryPolicyError("promotion policy identity mismatch")
    return policy
