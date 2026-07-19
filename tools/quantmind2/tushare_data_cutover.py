#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.services.engine.tushare_cutover.pipeline import TushareCutoverPipeline


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Tushare-only QuantMind data-authority cutover")
    value.add_argument("--workspace", default="~/.quantmind2/tushare-authority/v1")
    value.add_argument("--store-root")
    sub = value.add_subparsers(dest="command", required=True)
    for name in ("probe", "select-500", "lock-100", "fetch-history", "build-features", "build-labels", "build-qlib-view", "validate-cutover", "plan-purge", "execute-purge", "verify-after-purge"):
        command = sub.add_parser(name)
        if name == "plan-purge":
            command.add_argument("--legacy-root", action="append", default=[])
    return value


def _load_state(root: Path) -> dict:
    path = root / "state.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def _save_state(root: Path, state: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / ".state.json.tmp"
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.replace(root / "state.json")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(args.workspace).expanduser().resolve()
    pipeline = TushareCutoverPipeline(root, store_root=Path(args.store_root).expanduser() if args.store_root else None)
    state = _load_state(root)
    command = args.command
    if command == "probe":
        result = pipeline.probe()
    elif command == "select-500":
        result = pipeline.select_500(); state["universe_500"] = result
    elif command == "lock-100":
        result = pipeline.lock_100(state["universe_500"]); state["universe_100"] = result
    elif command == "fetch-history":
        result = pipeline.fetch_history(state["universe_500"]); state["history"] = result
    elif command == "build-features":
        normalized = state.get("normalized") or pipeline.build_normalized(state["universe_500"], state["history"])
        result = pipeline.build_features(normalized, state["history"]["tushare_market_benchmark"])
        state["normalized"], state["features"] = normalized, result
    elif command == "build-labels":
        result = pipeline.build_labels(state["normalized"]); state["labels"] = result
    elif command == "build-qlib-view":
        result = pipeline.build_qlib_view(state["universe_100"], state["normalized"], state["features"], state["labels"], state["history"]["tushare_trade_calendar"], state["history"]["tushare_market_benchmark"]); state["qlib"] = result
    elif command == "validate-cutover":
        result = pipeline.validate_cutover(state["universe_500"], state["universe_100"], state["history"], state["normalized"], state["features"], state["labels"], state["qlib"]); state["validation"] = result
    elif command == "plan-purge":
        result = pipeline.plan_purge(Path(item) for item in args.legacy_root); state["purge_plan"] = result
    elif command == "execute-purge":
        if state.get("validation", {}).get("status") != "passed":
            raise SystemExit("cutover validation is not passed; legacy data was not deleted")
        result = pipeline.execute_purge(state["purge_plan"]); state["purge_result"] = result
    elif command == "verify-after-purge":
        from backend.services.engine.artifact_store.integrity import scan_store_integrity
        report = scan_store_integrity(pipeline.store)
        result = {"status": report.status, "artifact_count": report.artifact_count, "blob_count": report.blob_count, "missing": len(report.issues), "unreferenced": len(report.unreferenced_blobs)}
    else:
        raise AssertionError("unreachable")
    _save_state(root, state)
    if isinstance(result, dict) and "artifact_kind" in result:
        summary = {"artifact_kind": result["artifact_kind"], "artifact_id": next((result.get(name) for name in ("universe_lock_id", "dataset_id", "qlib_view_id", "registry_snapshot_id", "memory_id", "authority_record_id", "purge_plan_id", "purge_result_id") if result.get(name)), None), "path": result.get("path"), "exact_existing": result.get("exact_existing")}
    elif isinstance(result, dict) and result and all(isinstance(value, dict) and "artifact_kind" in value for value in result.values()):
        summary = {key: {"artifact_kind": value["artifact_kind"], "artifact_id": next((value.get(name) for name in ("dataset_id", "universe_lock_id", "qlib_view_id") if value.get(name)), None)} for key, value in result.items()}
    else:
        summary = result
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
