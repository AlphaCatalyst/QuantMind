from __future__ import annotations

from typing import Any


class FreshRuntimeStatusConsistencyError(RuntimeError):
    code = "RUNTIME_STATUS_CROSS_ARTIFACT_MISMATCH"


class FreshRuntimeStatusConsistencyValidatorV1:
    FIELDS = (
        "source_commit",
        "app_snapshot_id",
        "runtime_config_checksum",
        "idempotency_verified",
        "tmp_cleanup_verified",
        "redaction_violation_count",
    )

    def validate(
        self,
        *,
        scheduler: dict[str, Any],
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        mismatches = tuple(
            field
            for field in self.FIELDS
            if scheduler.get(field) != deployment.get(field)
        )
        if mismatches:
            raise FreshRuntimeStatusConsistencyError(
                f"{FreshRuntimeStatusConsistencyError.code}: {','.join(mismatches)}"
            )
        if scheduler.get("deployment_status_id") != deployment.get(
            "fresh_runtime_deployment_status_id"
        ):
            raise FreshRuntimeStatusConsistencyError(
                f"{FreshRuntimeStatusConsistencyError.code}: deployment_status_id"
            )
        return {
            "consistent": True,
            "mismatch_code": None,
            "checked_fields": self.FIELDS + ("deployment_status_id",),
        }
