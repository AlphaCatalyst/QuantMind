from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_payload

from .enums import CorporateActionEventType, EvidenceCompleteness
from .models import SecurityCorporateActionEvent


def _date(value) -> str | None:
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text or None


def normalize_events(raw_root: Path, raw_snapshot_id: str) -> tuple[SecurityCorporateActionEvent, ...]:
    rows = pd.read_parquet(Path(raw_root) / "events.parquet")
    decoded = [
        (row.endpoint, row.source_record_id, json.loads(row.payload_json))
        for row in rows.itertuples(index=False)
    ]
    events = []
    symbols = sorted({payload.get("ts_code") for _, _, payload in decoded if payload.get("ts_code")})
    for ts_code in symbols:
        basics = [item for item in decoded if item[0] == "stock_basic" and item[2].get("ts_code") == ts_code]
        if not basics or not basics[0][2].get("delist_date"):
            continue
        source_record_id, basic = basics[0][1], basics[0][2]
        daily_dates = [
            payload.get("trade_date") for endpoint, _, payload in decoded
            if endpoint == "daily" and payload.get("ts_code") == ts_code and payload.get("trade_date")
        ]
        evidence = {
            "stock_basic": basic,
            "last_daily_date": max(daily_dates, default=None),
            "settlement_fields": {
                "cash_per_share": None, "replacement_symbol": None,
                "conversion_ratio": None, "residual_cash_per_share": None,
                "settlement_date": None,
            },
        }
        code, exchange = ts_code.split(".")
        symbol = exchange + code
        events.append(SecurityCorporateActionEvent(
            symbol=symbol,
            event_type=CorporateActionEventType.DELISTING,
            announcement_date=None,
            last_tradable_date=_date(max(daily_dates, default=None)),
            effective_date=_date(basic.get("delist_date")),
            settlement_date=None, cash_per_share=None, replacement_symbol=None,
            conversion_ratio=None, residual_cash_per_share=None,
            source_artifact_id=raw_snapshot_id, source_record_id=source_record_id,
            evidence_hash=hashlib.sha256(
                json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode()
            ).hexdigest(),
            evidence_completeness=EvidenceCompleteness.MISSING,
        ))
    return tuple(events)


def event_set_identity(events: tuple[SecurityCorporateActionEvent, ...]) -> dict:
    payloads = [event.payload() for event in events]
    return {
        "schema_version": "security-corporate-action-event-set-v1",
        "event_ids": [event.event_id for event in events],
        "event_payload_hash": hash_payload(payloads),
        "all_settlement_evidence_complete": all(
            event.evidence_completeness is EvidenceCompleteness.COMPLETE for event in events
        ),
    }
