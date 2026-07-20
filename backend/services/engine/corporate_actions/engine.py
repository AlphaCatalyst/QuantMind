from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory

from .benchmark import FixedUniverseBenchmarkContractV2, require_canonical_revision
from .capability import CapabilityProbe, probe_capabilities
from .errors import CorporateActionEvidenceInsufficient
from .normalization import event_set_identity, normalize_events
from .raw_artifact import artifact_id, publish_artifact, publish_raw_snapshot
from .tushare_client import CorporateActionTushareClient


TARGETS = ("600837.SH", "601989.SH")
UNIVERSE_LOCK_ID = "tu100_078e6609ef84c58e4c9db53fe8ee194a4b8b7b31d4990a61fbddb9022c02c526"
TERMINATION_AUDIT_ID = "htf_4a0762a5b87c0f2837fe70cbf51f2b4ecdc56da8482c25807ec566ba43ba6c3f"


def _probes(symbols: tuple[str, ...]) -> tuple[CapabilityProbe, ...]:
    probes = []
    for symbol in symbols:
        probes.extend((
            CapabilityProbe(
                "stock_basic",
                ("ts_code", "symbol", "name", "market", "exchange", "list_status",
                 "list_date", "delist_date"),
                {"ts_code": symbol, "list_status": "D"}, ("delisting",),
            ),
            CapabilityProbe(
                "daily", ("ts_code", "trade_date", "close", "pre_close"),
                {"ts_code": symbol, "start_date": "20250101", "end_date": "20251231"},
                ("last_tradable_date",),
            ),
            CapabilityProbe(
                "namechange", ("ts_code", "name", "start_date", "end_date",
                               "ann_date", "change_reason"),
                {"ts_code": symbol}, ("name_history",),
            ),
            CapabilityProbe(
                "suspend_d", ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
                {"ts_code": symbol, "start_date": "20240101", "end_date": "20251231"},
                ("suspension",),
            ),
            CapabilityProbe(
                "share_float", ("ts_code", "ann_date", "float_date", "float_share",
                                "float_ratio", "holder_name", "share_type"),
                {"ts_code": symbol}, ("share_capital",),
            ),
            CapabilityProbe(
                "dividend", ("ts_code", "end_date", "ann_date", "div_proc", "stk_div",
                             "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax",
                             "record_date", "ex_date", "pay_date", "div_listdate",
                             "imp_ann_date"),
                {"ts_code": symbol}, ("ordinary_dividend",),
            ),
            CapabilityProbe(
                "anns_d", ("ann_date", "ts_code", "name", "title", "url", "rec_time"),
                {"ts_code": symbol, "start_date": "20240101", "end_date": "20251231"},
                ("raw_issuer_announcement",), raw_announcement=True,
            ),
            CapabilityProbe("merge", ("ts_code",), {"ts_code": symbol},
                            ("merger_exchange",), ("replacement_symbol", "conversion_ratio")),
            CapabilityProbe("merger", ("ts_code",), {"ts_code": symbol},
                            ("merger_exchange",), ("replacement_symbol", "conversion_ratio")),
        ))
    probes.append(CapabilityProbe(
        "major_news", ("title", "pub_time", "src", "url"),
        {"start_date": "2025-02-01 00:00:00", "end_date": "2025-09-10 23:59:59"},
        ("news_metadata_only",),
    ))
    return tuple(probes)


def _cold_restore(store, artifact_ids: tuple[str, ...]) -> None:
    with tempfile.TemporaryDirectory() as root:
        for item in artifact_ids:
            descriptor = store.find_by_artifact_id(item)
            if descriptor is None:
                raise RuntimeError(f"Artifact missing during cold recovery: {item}")
            store.materialize_artifact(descriptor.descriptor_id, Path(root) / item)


def replay_corporate_action_audit(*, raw_snapshot_id: str, store_root: Path | None = None) -> dict:
    store = FileSystemResearchArtifactStore(resolve_config(store_root))
    store.initialize()
    raw = store.find_by_artifact_id(raw_snapshot_id)
    if raw is None or raw.artifact_kind != "tushare_corporate_action_raw":
        raise ValueError("governed corporate-action Raw Snapshot is absent")
    derived = [
        item for item in store.list_artifacts()
        if raw_snapshot_id in item.lineage and item.artifact_kind in {
            "security_corporate_action_event", "fixed_universe_benchmark_contract",
        }
    ]
    if len(derived) != 2:
        raise ValueError("corporate-action replay graph is incomplete")
    ids = (raw_snapshot_id, *(item.artifact_id for item in sorted(derived, key=lambda x: x.artifact_kind)))
    _cold_restore(store, ids)
    integrity = scan_store_integrity(store)
    return {
        "status": "exact_replay", "raw_snapshot_id": raw_snapshot_id,
        "derived_artifact_ids": list(ids[1:]), "tushare_network_calls": 0,
        "qlib_calls": 0, "agent_calls": 0, "new_artifacts": 0, "new_blobs": 0,
        "integrity": integrity.status,
    }


def run_corporate_action_audit(
    *, work_root: Path, store_root: Path | None = None,
    client: CorporateActionTushareClient | None = None,
) -> dict:
    work_root = Path(work_root)
    store = FileSystemResearchArtifactStore(resolve_config(store_root))
    store.initialize()
    before_artifacts = len(store.list_artifacts())
    before_blobs = len({item.sha256 for artifact in store.list_artifacts() for item in artifact.files})
    client = client or CorporateActionTushareClient()
    capabilities, responses = probe_capabilities(client, _probes(TARGETS))
    artifact_root = work_root / "artifacts"
    raw = publish_raw_snapshot(
        artifact_root, symbols=TARGETS, capabilities=capabilities, responses=responses,
    )
    raw_id = artifact_id(raw)
    events = normalize_events(Path(raw["path"]), raw_id)
    if {event.symbol for event in events} != {"SH600837", "SH601989"}:
        raise RuntimeError("target corporate-action event coverage is incomplete")
    assessment = {
        "schema_version": "corporate-action-evidence-assessment-v1",
        "result": "blocked", "reason": "TUSHARE_CORPORATE_ACTION_EVIDENCE_INSUFFICIENT",
        "raw_issuer_announcement_available": any(
            item.endpoint == "anns_d" and item.raw_announcement_available for item in capabilities
        ),
        "structured_cash_settlement_available": False,
        "structured_stock_conversion_available": False,
        "structured_merger_exchange_available": False,
        "unresolved_code": "SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED",
    }
    event_identity = event_set_identity(events) | {"raw_snapshot_id": raw_id}
    normalized = publish_artifact(
        artifact_root, "security_corporate_action_event", event_identity,
        {"normalized_events.json": {"events": [event.payload() for event in events]},
         "evidence_assessment.json": assessment},
    )
    contract = FixedUniverseBenchmarkContractV2(UNIVERSE_LOCK_ID)
    contract_artifact = publish_artifact(
        artifact_root, "fixed_universe_benchmark_contract", contract.payload(include_id=False),
        {"benchmark_contract.json": contract.payload()},
    )
    try:
        require_canonical_revision(events)
    except CorporateActionEvidenceInsufficient:
        revision_status = "blocked"
    else:
        raise RuntimeError("incomplete Tushare evidence unexpectedly admitted a benchmark revision")
    receipts = [
        store.import_artifact(
            "tushare_corporate_action_raw", Path(raw["path"]),
            expected_artifact_id=raw_id,
        ),
        store.import_artifact(
            "security_corporate_action_event", Path(normalized["path"]),
            expected_artifact_id=artifact_id(normalized),
            lineage=(raw_id, TERMINATION_AUDIT_ID),
        ),
        store.import_artifact(
            "fixed_universe_benchmark_contract", Path(contract_artifact["path"]),
            expected_artifact_id=artifact_id(contract_artifact),
            lineage=(raw_id, artifact_id(normalized), UNIVERSE_LOCK_ID),
        ),
    ]
    ids = tuple(receipt.artifact_id for receipt in receipts)
    _cold_restore(store, ids)
    inventory = publish_inventory(store)
    integrity = scan_store_integrity(store)
    return {
        "status": "blocked",
        "reason": "TUSHARE_CORPORATE_ACTION_EVIDENCE_INSUFFICIENT",
        "raw_snapshot_id": raw_id,
        "event_artifact_id": artifact_id(normalized),
        "benchmark_contract_id": artifact_id(contract_artifact),
        "events": [event.payload() for event in events],
        "capabilities": [item.payload() for item in capabilities],
        "benchmark_revision_status": revision_status,
        "canonicality": {
            "2025_fixed_100": "noncanonical",
            "2025_relative_fixed_100": "noncanonical",
            "full_period_fixed_100": "noncanonical",
            "full_period_relative_fixed_100": "noncanonical",
            "strategy_absolute_returns": "unchanged_canonical",
            "strategy_csi300_metrics": "unchanged_canonical",
            "2019_2024": "unchanged_canonical",
            "2026h1": "unchanged_canonical",
        },
        "tushare_network_calls": client.network_calls,
        "qlib_calls": 0, "agent_calls": 0, "optimization_trials": 0,
        "promotion_writes": 0, "benchmark_revisions_published": 0,
        "inventory_id": inventory.inventory_id,
        "artifact_count": inventory.artifact_count,
        "blob_count": inventory.unique_blob_count,
        "new_artifacts": len(store.list_artifacts()) - before_artifacts,
        "new_blobs": len({item.sha256 for artifact in store.list_artifacts()
                           for item in artifact.files}) - before_blobs,
        "integrity": integrity.status, "integrity_issues": len(integrity.issues),
    }

