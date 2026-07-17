import re

from .enums import DecisionSource, PromotionAction, RegistryStatus
from .errors import FactorRegistryError


REGISTRY_SCHEMA_VERSION = "1.0.0"
POLICY_VERSION = "1.0.0"
ID_PATTERNS = {
    "factor_instance_id": r"^fi_[0-9a-f]{64}$",
    "template_id": r"^ft_[0-9a-f]{64}$",
    "factor_values_id": r"^fv_[0-9a-f]{64}$",
    "dataset_snapshot_id": r"^ds_[0-9a-f]{64}$",
    "study_id": r"^fos_[0-9a-f]{64}$",
    "trial_id": r"^fot_[0-9a-f]{64}$",
    "validation_dataset_id": r"^vd_[0-9a-f]{64}$",
    "validation_result_id": r"^fvr_[0-9a-f]{64}$",
    "selection_id": r"^fvs_[0-9a-f]{64}$",
    "frozen_result_id": r"^fvt_[0-9a-f]{64}$",
}


def require_id(name, value, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not re.fullmatch(ID_PATTERNS[name], value):
        raise FactorRegistryError(f"invalid {name}")


def require_exact_keys(payload, keys, *, label):
    if not isinstance(payload, dict) or set(payload) != set(keys):
        raise FactorRegistryError(f"{label} fields do not match the closed schema")


def require_known_status(value):
    try:
        return RegistryStatus(value)
    except ValueError as exc:
        raise FactorRegistryError("unknown Registry status") from exc


def require_decision_enums(action, source):
    try:
        return PromotionAction(action), DecisionSource(source)
    except ValueError as exc:
        raise FactorRegistryError("unknown Promotion Decision enum") from exc
