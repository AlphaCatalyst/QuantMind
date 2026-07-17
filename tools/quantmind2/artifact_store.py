#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.artifact_store.canonical import canonical_json_bytes
from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.current import plan_current
from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.artifact_store.security import inspect_source
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore


def _store(args) -> FileSystemResearchArtifactStore:
    store = FileSystemResearchArtifactStore(resolve_config(args.store_root))
    if args.command != "init":
        store.validate_format()
    return store


def _write_plan(store, plan) -> Path:
    path = store.root / "inventories" / f"{plan.plan_id}.reachability.json"
    payload = canonical_json_bytes(asdict(plan)) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("plan_id") != plan.plan_id:
            raise RuntimeError("immutable Reachability Plan conflict")
        return path
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
    return path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind 2.0 persistent Research Artifact Store")
    value.add_argument("--store-root")
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    inspect_source_parser = commands.add_parser("inspect-source")
    inspect_source_parser.add_argument("source", type=Path)
    import_parser = commands.add_parser("import")
    import_parser.add_argument("artifact_kind")
    import_parser.add_argument("source", type=Path)
    import_parser.add_argument("--artifact-id")
    commands.add_parser("plan-current")
    commands.add_parser("migrate-current")
    list_parser = commands.add_parser("list")
    list_parser.add_argument("--artifact-kind")
    list_parser.add_argument("--artifact-id")
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact-id")
    materialize = commands.add_parser("materialize")
    materialize.add_argument("identity")
    materialize.add_argument("destination", type=Path)
    commands.add_parser("inventory")
    commands.add_parser("inspect")
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        store = _store(args)
        if args.command == "init":
            result = {"status": "initialized", "format": store.initialize(),
                      "root_resolution_source": store.config.root_resolution_source}
        elif args.command == "inspect-source":
            inventory = inspect_source(args.source,
                maximum_file_count=store.config.maximum_file_count,
                maximum_artifact_bytes=store.config.maximum_artifact_bytes)
            result = {"status": "safe", "source_type": "directory",
                      "file_count": len(inventory.files), "total_bytes": inventory.total_bytes}
        elif args.command == "import":
            result = asdict(store.import_artifact(args.artifact_kind, args.source, args.artifact_id))
        elif args.command == "plan-current":
            plan, _, missing_sources = plan_current(ROOT)
            _write_plan(store, plan)
            result = {**asdict(plan), "missing_source_artifact_ids": list(missing_sources)}
        elif args.command == "migrate-current":
            plan, sources, missing_sources = plan_current(ROOT)
            _write_plan(store, plan)
            receipts = []
            for source in sources:
                if source.artifact_id not in plan.reachable_artifact_ids or not source.source_directory.is_dir():
                    continue
                receipt = store.import_artifact(
                    source.artifact_kind, source.source_directory, source.artifact_id,
                    lineage=source.lineage, validation_context=source.validation_context)
                receipts.append(receipt)
            inventory = publish_inventory(store)
            result = {"status": "completed" if not missing_sources else "partial",
                      "reachability_plan_id": plan.plan_id,
                      "inventory_id": inventory.inventory_id,
                      "migrated_artifact_count": len(receipts),
                      "missing_artifact_ids": list(plan.missing_artifact_ids),
                      "missing_source_artifact_ids": list(missing_sources),
                      "logical_bytes": sum(item.logical_bytes for item in receipts),
                      "unique_blob_bytes": inventory.unique_blob_bytes,
                      "deduplicated_bytes": inventory.deduplicated_bytes,
                      "deduplication_ratio": (
                          inventory.logical_bytes / inventory.unique_blob_bytes
                          if inventory.unique_blob_bytes else 1.0
                      ),
                      "new_blob_bytes": sum(item.new_blob_bytes for item in receipts),
                      "reused_blob_bytes": sum(item.reused_blob_bytes for item in receipts)}
        elif args.command == "list":
            rows = store.list_artifacts()
            if args.artifact_kind:
                rows = tuple(item for item in rows if item.artifact_kind == args.artifact_kind)
            if args.artifact_id:
                rows = tuple(item for item in rows if item.artifact_id == args.artifact_id)
            result = {"artifact_count": len(rows), "artifacts": [
                {"artifact_kind": item.artifact_kind, "artifact_id": item.artifact_id,
                 "descriptor_id": item.descriptor_id, "file_count": item.total_file_count,
                 "total_bytes": item.total_bytes} for item in rows]}
        elif args.command == "verify":
            if args.artifact_id:
                result = {"status": "healthy" if store.verify_artifact(args.artifact_id) else "corrupt",
                          "artifact_id": args.artifact_id}
            else:
                result = asdict(scan_store_integrity(store))
        elif args.command == "materialize":
            result = asdict(store.materialize_artifact(args.identity, args.destination))
        elif args.command == "inventory":
            result = asdict(publish_inventory(store))
        else:
            report = scan_store_integrity(store)
            inventory = publish_inventory(store)
            plan, _, _ = plan_current(ROOT)
            stored_ids = set(inventory.artifact_ids)
            result = {"store_format_version": store.config.format_version,
                      "artifact_count": inventory.artifact_count,
                      "artifact_kind_counts": inventory.artifact_kind_counts,
                      "unique_blob_count": inventory.unique_blob_count,
                      "logical_bytes": inventory.logical_bytes,
                      "unique_blob_bytes": inventory.unique_blob_bytes,
                      "deduplicated_bytes": inventory.deduplicated_bytes,
                      "deduplication_ratio": (
                          inventory.logical_bytes / inventory.unique_blob_bytes
                          if inventory.unique_blob_bytes else 1.0
                      ),
                      "missing_reachable_artifact_ids": [
                          identity for identity in plan.reachable_artifact_ids
                          if identity not in stored_ids
                      ],
                      "integrity": report.status}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        code = getattr(exc, "code", "ARTIFACT_STORE_CLI_ERROR")
        print(json.dumps({"status": "error", "error_code": code,
                          "message": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
