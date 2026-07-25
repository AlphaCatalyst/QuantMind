#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.fresh_runtime_deployment import (  # noqa: E402
    FreshRuntimeDeploymentService,
    RuntimeDeploymentError,
)
from backend.services.engine.fresh_runtime_deployment.temporary_directory import (  # noqa: E402
    RuntimeTemporaryDirectoryError,
    cleanup_stale_runtime_tmp,
    cleanup_owned_scheduler_lock,
    create_runtime_tmp,
    remove_runtime_tmp,
)
from backend.services.engine.runtime_diagnostics import (  # noqa: E402
    RuntimeDiagnosticRedactionGuardV1,
)


DEFAULT_SOURCE_PYTHON = Path(
    "/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/.venv/bin/python"
)
DEFAULT_SOURCE_LIBOMP = Path(
    "/Users/yj/Documents/Codex/2026-06-30/nih/work/AlphaQuant/"
    "third-party/runtime/libomp/libomp/22.1.8/lib"
)


def _service(args: argparse.Namespace) -> FreshRuntimeDeploymentService:
    return FreshRuntimeDeploymentService(
        repository_root=Path(args.repository_root),
        runtime_root=Path(args.runtime_root).expanduser(),
        source_python=Path(args.source_python).expanduser(),
        source_libomp=Path(args.source_libomp).expanduser(),
        artifact_store_root=Path(args.store_root).expanduser(),
    )


def _id(value: dict[str, Any], name: str) -> str:
    receipt = value.get("artifact_receipt") or {}
    if receipt.get("artifact_id"):
        return receipt["artifact_id"]
    if value.get(name):
        return value[name]
    raise RuntimeDeploymentError(f"Artifact identity absent: {name}")


def deploy(service: FreshRuntimeDeploymentService) -> dict[str, Any]:
    audit = service.audit_paths(publish=True)
    storage = service.estimate_storage()
    if storage["physical_copy_storage_budget_blocked"]:
        raise RuntimeDeploymentError("physical_copy_storage_budget_blocked")
    app = service.build_app_snapshot(publish=True)
    environment = service.build_environment_snapshot(publish=True)
    state = service.migrate_state(publish=True)
    config = service.render_runtime_config()
    validation = service.validate_runtime()
    if not validation["valid"]:
        raise RuntimeDeploymentError("runtime validation failed")
    installation = service.install_launchagent()
    activation = service.activate()
    first = service.run_now(launchd=True)
    second = service.run_now(launchd=True)
    scheduler = service.publish_scheduler_status()
    refs = (
        _id(audit, "fresh_runtime_path_audit_id"),
        _id(app, "fresh_runtime_app_snapshot_id"),
        _id(environment, "fresh_runtime_environment_snapshot_id"),
        _id(state, "fresh_runtime_state_migration_id"),
        _id(scheduler, "fresh_heartbeat_scheduler_status_id"),
    )
    deployment = service.record_deployment(
        app_snapshot_id=refs[1],
        environment_fingerprint=environment["environment_fingerprint"],
        artifact_refs=refs,
        first_run=first,
        second_run=second,
    )
    if not (
        deployment["launch_agent_loaded"]
        and deployment["launchd_trigger_verified"]
        and deployment["launchd_exit_status"] == 0
        and deployment["idempotency_verified"]
        and deployment["protected_path_dependency_count"] == 0
    ):
        service.uninstall()
        raise RuntimeDeploymentError("formal deployment acceptance failed")
    return {
        "status": "completed",
        "audit": audit,
        "storage": storage,
        "app_snapshot": app,
        "environment_snapshot": environment,
        "state_migration": state,
        "runtime_config": config,
        "runtime_validation": validation,
        "installation": installation,
        "activation": activation,
        "first_launchd_run": first,
        "idempotency_run": second,
        "scheduler_status": scheduler,
        "deployment_status": deployment,
        "cleanup_candidates": service.cleanup_candidates(),
    }


def validated_run(
    service: FreshRuntimeDeploymentService, *, launchd: bool, trigger: str
) -> dict[str, Any]:
    validation = service.validate_runtime()
    if not validation["valid"]:
        raise RuntimeDeploymentError("runtime validation failed before heartbeat")
    return service.run_now(launchd=launchd, trigger=trigger)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--repository-root", default=str(ROOT))
    value.add_argument(
        "--runtime-root",
        default="~/Library/Application Support/QuantMind",
    )
    value.add_argument("--source-python", default=str(DEFAULT_SOURCE_PYTHON))
    value.add_argument("--source-libomp", default=str(DEFAULT_SOURCE_LIBOMP))
    value.add_argument("--store-root", default="~/.quantmind2/artifact-store/v1")
    sub = value.add_subparsers(dest="command", required=True)
    for name in (
        "audit",
        "estimate-storage",
        "build-app-snapshot",
        "build-env-snapshot",
        "migrate-state",
        "render-runtime-config",
        "validate-runtime",
        "install-launchagent",
        "activate",
        "status",
        "rollback",
        "uninstall",
        "cold-recover",
        "replay",
        "deploy",
        "safe-status",
        "safe-launchctl-status",
        "safe-credential-check",
        "safe-runtime-diagnostics",
        "cleanup-stale-runtime-tmp",
    ):
        sub.add_parser(name)
    create_tmp = sub.add_parser("create-runtime-tmp")
    create_tmp.add_argument("--run-id", required=True)
    create_tmp.add_argument("--owner-pid", required=True, type=int)
    remove_tmp = sub.add_parser("cleanup-runtime-tmp")
    remove_tmp.add_argument("--run-id", required=True)
    owned_lock = sub.add_parser("cleanup-owned-scheduler-lock")
    owned_lock.add_argument("--run-id", required=True)
    owned_lock.add_argument("--owner-pid", required=True, type=int)
    run = sub.add_parser("run-now")
    run.add_argument("--launchd", action="store_true")
    run.add_argument("--trigger", default="manual")
    hardening = sub.add_parser("publish-hardening-artifacts")
    hardening.add_argument("--implementation-run-id", required=True)
    hardening.add_argument("--app-snapshot-id", required=True)
    hardening.add_argument("--environment-fingerprint", required=True)
    cutover = sub.add_parser("hardened-cutover")
    cutover.add_argument("--implementation-run-id", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    service = _service(args)
    operations = {
        "audit": lambda: service.audit_paths(publish=False),
        "estimate-storage": service.estimate_storage,
        "build-app-snapshot": lambda: service.build_app_snapshot(publish=False),
        "build-env-snapshot": lambda: service.build_environment_snapshot(
            publish=False
        ),
        "migrate-state": lambda: service.migrate_state(publish=False),
        "render-runtime-config": service.render_runtime_config,
        "validate-runtime": service.validate_runtime,
        "install-launchagent": service.install_launchagent,
        "activate": service.activate,
        "run-now": lambda: validated_run(
            service, launchd=args.launchd, trigger=args.trigger
        ),
        "status": service.status,
        "safe-status": service.status,
        "safe-launchctl-status": service.safe_launchctl_status,
        "safe-credential-check": service.safe_credential_check,
        "safe-runtime-diagnostics": service.safe_runtime_diagnostics,
        "cleanup-stale-runtime-tmp": lambda: cleanup_stale_runtime_tmp(
            service.state_root / "tmp",
            scheduler_lock=service.state_root / "locks/fresh-heartbeat.lock",
        ),
        "create-runtime-tmp": lambda: create_runtime_tmp(
            service.state_root / "tmp",
            args.run_id,
            owner_pid=args.owner_pid,
        ),
        "cleanup-runtime-tmp": lambda: remove_runtime_tmp(
            service.state_root / "tmp", args.run_id
        ),
        "cleanup-owned-scheduler-lock": lambda: cleanup_owned_scheduler_lock(
            service.state_root / "locks/fresh-heartbeat.lock",
            owner_pid=args.owner_pid,
            run_id=args.run_id,
        ),
        "publish-hardening-artifacts": lambda: service.publish_hardening_artifacts(
            implementation_run_id=args.implementation_run_id,
            app_snapshot_id=args.app_snapshot_id,
            environment_fingerprint=args.environment_fingerprint,
        ),
        "hardened-cutover": lambda: service.hardened_cutover(
            implementation_run_id=args.implementation_run_id
        ),
        "rollback": service.rollback,
        "uninstall": service.uninstall,
        "cold-recover": service.cold_recover,
        "replay": service.replay,
        "deploy": lambda: deploy(service),
    }
    try:
        result = operations[args.command]()
    except (RuntimeDeploymentError, RuntimeTemporaryDirectoryError) as exc:
        safe = RuntimeDiagnosticRedactionGuardV1().redact(str(exc))
        print(
            json.dumps(
                {
                    "status": "partial",
                    "reason": safe.text,
                    "redaction_count": safe.redaction_count,
                    "redaction_event_categories": list(safe.categories),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    safe = RuntimeDiagnosticRedactionGuardV1().redact(serialized)
    value = json.loads(safe.text)
    if safe.redaction_count:
        value["redaction_count"] = safe.redaction_count
        value["redaction_event_categories"] = list(safe.categories)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
