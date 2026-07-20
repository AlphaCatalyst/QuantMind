from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.tushare_agent_experiment.artifact import publish_experiment_artifact
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner
from backend.services.engine.tushare_cutover.canonical import hash_payload

from .policy import FixedUniverseLifecyclePolicyV1, audit_lifecycles, daily_member_counts


ORIGINAL_EXPERIMENT_ID = "tha_2b3676218af9693cf6bfcf0ab47d102db0cc865f94f0e5b54de6fba26d76383b"
PRELIMINARY_FOLLOWUP_ID = "thf_39155cdb05613cd12d24c359109617ab24f38c873233d7dca399525ff3d498d6"
PERIODS = {
    "2019": ("2019-01-02", "2019-12-31"), "2020": ("2020-01-02", "2020-12-31"),
    "2021": ("2021-01-04", "2021-12-31"), "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"), "2024": ("2024-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-30"), "2026H1": ("2026-01-05", "2026-06-23"),
}
PARITY_FIELDS = (
    "gross_return", "net_return", "benchmark_return", "fixed_100_benchmark_return",
    "net_excess_csi300", "net_excess_fixed_100", "turnover", "transaction_cost", "max_drawdown",
)


def _materialize(store, artifact_id: str, root: Path) -> Path:
    descriptor = store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required Artifact missing: {artifact_id}")
    target = root / artifact_id
    if target.exists():
        shutil.rmtree(target)
    store.materialize_artifact(descriptor.descriptor_id, target)
    return target


def _raw_id(store, kind: str) -> str:
    matches = store.list_by_kind(kind)
    if len(matches) != 1:
        raise RuntimeError(f"expected one authority artifact for {kind}")
    return matches[0].artifact_id


def _positions_equal(left: dict, right: dict) -> bool:
    def ordered(value: dict) -> list:
        return sorted(value.get("positions") or [], key=lambda row: (row["date"], row["symbol"], row["side"]))
    first, second = ordered(left), ordered(right)
    if len(first) != len(second):
        return False
    for a, b in zip(first, second):
        if (a["date"], a["symbol"], a["side"]) != (b["date"], b["symbol"], b["side"]):
            return False
        if not _equal(a.get("amount"), b.get("amount")) or not _equal(a.get("weight"), b.get("weight")):
            return False
    return True


def _equal(left, right) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return abs(float(left) - float(right)) <= 1e-12
    except (TypeError, ValueError):
        return left == right


def _identity(bundle, experiment: dict, policy: FixedUniverseLifecyclePolicyV1) -> dict:
    return {
        "provider_id": "tushare-pro-v1", "original_experiment_id": ORIGINAL_EXPERIMENT_ID,
        "original_qlib_backtest_result_id": experiment["qlib_backtest_result_id"],
        "universe_lock_id": bundle.authority["universe_100"]["universe_lock_id"],
        "qlib_view_id": bundle.authority["qlib_view_id"], "lifecycle_policy_id": policy.policy_id,
        "selected_factor_instance_ids": experiment["candidate_lock"]["selected_factor_instance_ids"],
        "combination": "equal_weight_combo", "period": list(PERIODS["2026H1"]),
        "portfolio": experiment["protocol"]["portfolio"], "promotion_writes": 0,
        "contract_revision": 2, "supersedes_preliminary_followup_id": PRELIMINARY_FOLLOWUP_ID,
    }


def run_lifecycle_followup(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict:
    repository_root, work_root = Path(repository_root), Path(work_root)
    authority_path = repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json"
    bundle = load_authority_bundle(authority_path=authority_path, work_root=work_root / "authority", store_root=store_root)
    store = bundle.store
    original_path = _materialize(store, ORIGINAL_EXPERIMENT_ID, work_root / "source")
    experiment = json.loads((original_path / "experiment.json").read_text(encoding="utf-8"))
    policy = FixedUniverseLifecyclePolicyV1()
    identity = _identity(bundle, experiment, policy)
    intended_id = "thf_" + hash_payload(identity)
    existing = store.find_by_artifact_id(intended_id)
    if existing is not None:
        with tempfile.TemporaryDirectory() as cold:
            cold_path = Path(cold) / intended_id
            store.materialize_artifact(existing.descriptor_id, cold_path)
        integrity = scan_store_integrity(store)
        return {"status": "exact_replay", "artifact_id": intended_id, "qlib_calls": 0,
                "new_artifacts": 0, "new_blobs": 0, "integrity": integrity.status}

    qlib_result_path = _materialize(store, experiment["qlib_backtest_result_id"], work_root / "source")
    original_results = json.loads((qlib_result_path / "results.json").read_text(encoding="utf-8"))
    signal_paths = {path.stem: path for path in sorted((qlib_result_path / "signals").glob("*.parquet"))}
    signals = {name: pd.read_parquet(path) for name, path in signal_paths.items()}

    universe500 = _materialize(store, bundle.authority["universe_500"]["universe_lock_id"], work_root / "source")
    stock_basic = pd.read_parquet(universe500 / "stock_basic.parquet")
    raw = {}
    for name, kind, filename in (
        ("daily", "tushare_raw_daily", "daily.parquet"),
        ("adj", "tushare_raw_adj_factor", "adj_factor.parquet"),
        ("basic", "tushare_raw_daily_basic", "daily_basic.parquet"),
    ):
        raw[name] = pd.read_parquet(_materialize(store, _raw_id(store, kind), work_root / "source") / filename)
    audits, instrument_contract = audit_lifecycles(
        bundle.universe, stock_basic, raw["daily"], raw["adj"], raw["basic"], bundle.normalized,
        bundle.qlib_view / "instruments/all.txt", period_start=PERIODS["2026H1"][0],
    )
    absent = [row for row in audits if row["absence_reason"]]
    if len(absent) != 2 or {row["absence_reason"] for row in absent} != {"DELISTED_BEFORE_PERIOD"}:
        raise RuntimeError("2026H1 absence is not the frozen two-member lifecycle case")
    if len(bundle.universe) != 100 or not instrument_contract["membership_exact"]:
        raise RuntimeError("Fixed-100 lock or Qlib instrument membership changed")

    counts = daily_member_counts(
        bundle.universe, stock_basic, bundle.normalized, signals,
        start=PERIODS["2026H1"][0], end=PERIODS["2026H1"][1],
    )
    signal_columns = [name for name in counts if name.endswith("__signal_nan_ratio")]
    if counts.observable_member_count.min() < policy.minimum_observable_instruments or any(counts[name].max() > 0 for name in signal_columns):
        raise RuntimeError("lifecycle-aware signal quality or capacity gate failed")

    runner = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    parity = {"schema_version": "fixed100-lifecycle-parity-v1", "periods": {}, "passed": True}
    for name, signal in signal_paths.items():
        parity["periods"][name] = {}
        signal_hash = hashlib.sha256((qlib_result_path / "signals" / f"{name}.parquet").read_bytes()).hexdigest()
        for year in list(PERIODS)[:7]:
            rerun = runner.run(signal, *PERIODS[year], lifecycle_policy=policy.payload())
            old = original_results["annual_backtests"][name][year]
            fields = {field: _equal(old.get(field), rerun.get(field)) for field in PARITY_FIELDS}
            positions_equal = _positions_equal(old, rerun)
            passed = rerun.get("status") == "completed" and all(fields.values()) and positions_equal
            parity["periods"][name][year] = {
                "passed": passed, "signal_sha256": signal_hash,
                "positions_equal": positions_equal, "metric_equality": fields,
            }
            parity["passed"] = parity["passed"] and passed
    if not parity["passed"]:
        (work_root / "parity_failure.json").write_text(
            json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise RuntimeError("2019-2025 lifecycle parity failed")

    backtests = {"schema_version": "fixed100-lifecycle-2026h1-backtest-v1", "strategies": {}}
    for name, signal in signal_paths.items():
        backtests["strategies"][name] = runner.run(
            signal, *PERIODS["2026H1"], lifecycle_policy=policy.payload()
        )
        if backtests["strategies"][name].get("status") != "completed":
            raise RuntimeError(f"2026H1 formal Qlib failed for {name}")
        result = backtests["strategies"][name]
        maximum_drawdown = result.get("max_drawdown")
        result["calmar_ratio"] = (
            None if not maximum_drawdown else float(result["annual_return"]) / abs(float(maximum_drawdown))
        )
        result["lifecycle_evidence"] = {
            "locked_member_count": 100,
            "active_member_range": [int(counts.active_member_count.min()), int(counts.active_member_count.max())],
            "observable_member_range": [int(counts.observable_member_count.min()), int(counts.observable_member_count.max())],
            "tradable_member_range": [int(counts.tradable_member_count.min()), int(counts.tradable_member_count.max())],
            "signal_nan_ratio_observable_denominator": float(counts[f"{name}__signal_nan_ratio"].max()),
            "structurally_inactive_locked_member_count": 2,
            "replacement_count": 0, "market_fill_count": 0, "signal_fill_count": 0,
        }
    backtests["lifecycle_summary"] = {
        "locked_member_count": 100, "active_member_range": [int(counts.active_member_count.min()), int(counts.active_member_count.max())],
        "observable_member_range": [int(counts.observable_member_count.min()), int(counts.observable_member_count.max())],
        "tradable_member_range": [int(counts.tradable_member_count.min()), int(counts.tradable_member_count.max())],
        "structurally_inactive_locked_members": [row["ts_code"] for row in absent],
        "replacement_count": 0, "market_fill_count": 0, "signal_fill_count": 0,
    }

    artifact_root = work_root / "artifacts"
    counts_path = work_root / "daily_member_counts.parquet"
    counts.to_parquet(counts_path, index=False, compression="zstd")
    artifact = publish_experiment_artifact(
        artifact_root, "tushare_historical_experiment_lifecycle_followup", identity,
        {"lifecycle_policy.json": policy.payload(), "symbol_lifecycle_audit.json": {"members": audits, "absent_2026h1": absent},
         "daily_member_counts.parquet": counts_path, "qlib_instrument_contract.json": instrument_contract,
         "parity_2019_2025.json": parity, "backtest_2026h1.json": backtests},
    )
    before_artifacts = len(store.list_artifacts())
    before_blobs = len({f.sha256 for d in store.list_artifacts() for f in d.files})
    receipt = store.import_artifact(
        "tushare_historical_experiment_lifecycle_followup", Path(artifact["path"]),
        expected_artifact_id=artifact["historical_experiment_lifecycle_followup_id"],
        lineage=(ORIGINAL_EXPERIMENT_ID, experiment["qlib_backtest_result_id"], bundle.authority["qlib_view_id"], PRELIMINARY_FOLLOWUP_ID),
    )
    inventory = publish_inventory(store)
    integrity = scan_store_integrity(store)
    with tempfile.TemporaryDirectory() as cold:
        store.materialize_artifact(receipt.descriptor_id, Path(cold) / receipt.artifact_id)
    return {
        "status": "completed", "artifact_id": receipt.artifact_id, "descriptor_id": receipt.descriptor_id,
        "policy_id": policy.policy_id, "qlib_calls": runner.calls, "absent_members": absent,
        "parity_passed": parity["passed"], "backtests": backtests, "inventory_id": inventory.inventory_id,
        "artifact_count": inventory.artifact_count, "blob_count": inventory.unique_blob_count,
        "new_artifacts": len(store.list_artifacts()) - before_artifacts,
        "new_blobs": len({f.sha256 for d in store.list_artifacts() for f in d.files}) - before_blobs,
        "integrity": integrity.status, "integrity_issues": len(integrity.issues),
    }
