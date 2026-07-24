from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


LAUNCH_AGENT_LABEL = "com.quantmind.fresh-model-heartbeat"
SCHEDULE = (
    {"Weekday": 1, "Hour": 21, "Minute": 30},
    {"Weekday": 2, "Hour": 21, "Minute": 30},
    {"Weekday": 3, "Hour": 21, "Minute": 30},
    {"Weekday": 4, "Hour": 21, "Minute": 30},
    {"Weekday": 5, "Hour": 21, "Minute": 30},
    {"Weekday": 1, "Hour": 23, "Minute": 30},
    {"Weekday": 2, "Hour": 23, "Minute": 30},
    {"Weekday": 3, "Hour": 23, "Minute": 30},
    {"Weekday": 4, "Hour": 23, "Minute": 30},
    {"Weekday": 5, "Hour": 23, "Minute": 30},
    {"Weekday": 2, "Hour": 7, "Minute": 30},
    {"Weekday": 3, "Hour": 7, "Minute": 30},
    {"Weekday": 4, "Hour": 7, "Minute": 30},
    {"Weekday": 5, "Hour": 7, "Minute": 30},
    {"Weekday": 6, "Hour": 7, "Minute": 30},
)


@dataclass(frozen=True)
class FreshHeartbeatSchedulerStatusV1:
    template_path: str
    installed_path: str
    template_checksum: str
    installed_checksum: str
    loaded: bool
    enabled: bool
    last_exit_status: int | None
    last_run_at: str | None
    last_success_at: str | None
    consecutive_failures: int
    next_expected_run: str | None
    token_available_in_launch_context: bool
    repository_head_at_install: str
    latest_heartbeat_id: str | None = None

    def payload(self) -> dict[str, Any]:
        value = asdict(self) | {
            "schema_version": "fresh-heartbeat-scheduler-status-v1",
            "launch_agent_label": LAUNCH_AGENT_LABEL,
            "schedule": list(SCHEDULE),
            "credential_source": "login_shell_environment_only",
            "credential_persisted": False,
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        value["fresh_heartbeat_scheduler_status_id"] = "fhss1_" + hash_payload(value)
        return value
