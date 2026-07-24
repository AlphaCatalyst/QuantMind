from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


LATEST_PROJECT_EXPOSURE = "2026-07-23"
DEFAULT_START = "2019-01-02"


def _eligible(task_id: str) -> bool:
    if task_id.startswith("QM2-R1-"):
        return True
    return task_id in {"QM2-R2-001", "QM2-R2-002", "QM2-R2-003", "QM2-R2-004"}


def build_project_evidence_ledger(repository_root: Path) -> dict[str, Any]:
    runs_root = Path(repository_root) / "docs/quantmind2/implementation/runs"
    entries: list[dict[str, Any]] = []
    for path in sorted(runs_root.rglob("manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task_id = manifest.get("task", {}).get("task_id") or manifest.get("task_id")
        if not isinstance(task_id, str) or not _eligible(task_id):
            continue
        run = manifest.get("run", {})
        run_id = run.get("implementation_run_id") or manifest.get("implementation_run_id")
        artifacts = [
            row.get("artifact_id") for row in manifest.get("artifacts", [])
            if row.get("artifact_type") not in {"implementation_report", "implementation_manifest"}
        ]
        r1_010 = task_id == "QM2-R1-010"
        entries.append({
            "task_id": task_id,
            "run_id": run_id,
            "date_range": [DEFAULT_START, LATEST_PROJECT_EXPOSURE if r1_010 else "2026-06-23"],
            "data_artifacts": [item for item in artifacts if item],
            "signal_artifacts": [],
            "metric_families": ["fresh_forward_protocol"] if r1_010 else ["retrospective_factor_and_portfolio_metrics"],
            "access_purpose": "independent_r1_010_fresh_protocol" if r1_010 else "retrospective_discovery_and_diagnostics",
            "agent_visibility": not r1_010,
            "planner_visibility": not r1_010,
            "parameter_selection_usage": not r1_010,
            "candidate_selection_usage": not r1_010,
            "report_only_usage": r1_010,
            "evidence_semantics": "retrospective_research_only",
            "r1_010_statistical_isolation": r1_010,
        })
    stable = {
        "schema_version": "project-evidence-exposure-ledger-v1",
        "provider_id": "tushare-pro-v1",
        "project_exposed_date_range": [DEFAULT_START, LATEST_PROJECT_EXPOSURE],
        "entries": entries,
        "historical_evidence_semantics": "retrospective_research_only",
        "fresh_supported_claims": 0,
        "promotion_writes": 0,
    }
    return stable | {"exposure_ledger_id": "peel1_" + hash_payload(stable)}
