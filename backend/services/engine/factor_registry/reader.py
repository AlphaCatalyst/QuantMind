from .snapshot import validate_registry_snapshot


def load_registry_snapshot(output_root, snapshot_id): return validate_registry_snapshot(output_root, snapshot_id)
def get_registry_entry(snapshot, factor_instance_id): return next((x for x in snapshot.entries if x.factor_instance_id == factor_instance_id), None)
def list_registry_entries(snapshot): return snapshot.entries
def list_by_status(snapshot, status): return tuple(x for x in snapshot.entries if x.status.value == str(getattr(status, "value", status)))
def list_by_family(snapshot, family_id): return tuple(x for x in snapshot.entries if x.family_id == family_id)
def promotion_candidates(snapshot): return list_by_status(snapshot, "promotion_candidate")
def active_factors(snapshot): return list_by_status(snapshot, "active")
