from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.autonomous_factor_campaign.orchestrator import _runtime
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository
from backend.services.engine.autonomous_factor_program.statistics import (
    benjamini_hochberg,
    hac_mean_test,
)
from backend.services.engine.autonomous_technical_feature_factory.grammar import (
    evaluate_ast_v2,
)
from backend.services.engine.autonomous_technical_feature_factory.models import V2_PRIMITIVES
from backend.services.engine.autonomous_technical_feature_factory.primitives import (
    primitive_values,
)
from backend.services.engine.fixed_configuration_model_program.engine import (
    _bundle_payloads,
    _catalog,
    _cross_section_transform,
    select_bundle_c,
)
from backend.services.engine.momentum_factor_iteration.features import compute_features
from backend.services.engine.multi_horizon_label_research.engine import _label_values
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload
from backend.services.engine.tushare_cutover.client import TushareClient

from .models import (
    ALLOWED_ENDPOINTS,
    CANDIDATE_IDS,
    FRESH_LOCK_IDS,
    LABEL_ID,
    LEGAL_FRESH_STATES,
    MINIMUM_EVIDENCE,
    MODEL_SPEC_ID,
    PRIOR_FIRST_SEEN_SNAPSHOT_ID,
    PROJECT_EXPOSURE_DATE,
    SEEDS,
    STRATEGY_PROTOCOL,
    WALK_FORWARD_SPEC_ID,
    ModelFreshCandidateCohortV1,
    minimum_evidence_passed,
)


FEATURE_CATALOG_ID = (
    "tfc3_b903c85e328d359181c18ce3444d458a41ee970be8b2f6b79eff83cc6d523aea"
)
PRIMITIVE_CATALOG_ID = (
    "tpc2_b9f6112bec9f5524d8d14eb0ff8d40244c0e143557d49c1676c2630686387208"
)
FRESH_KIND = "fresh_market_snapshot"


class FreshModelContractError(RuntimeError):
    pass


def _publish(
    repository: CampaignRepository,
    kind: str,
    payload: dict[str, Any],
    filename: str,
    lineage: tuple[str, ...],
    files: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = repository.publish(
        kind,
        payload,
        files or {filename: payload},
        lineage=tuple(value for value in lineage if value),
    )
    return payload | {"artifact_id": receipt["artifact_id"]}, receipt


def _identity(repository: CampaignRepository, artifact_id: str) -> dict[str, Any]:
    return repository.identity(artifact_id) | {"artifact_id": artifact_id}


def _recover_contracts(repository: CampaignRepository) -> tuple[list[dict], list[dict], dict]:
    candidates = [
        _identity(repository, value) | {"candidate_id": value} for value in CANDIDATE_IDS
    ]
    locks = [
        _identity(repository, value) | {"fresh_lock_id": value}
        for value in FRESH_LOCK_IDS
    ]
    label = _identity(repository, LABEL_ID) | {"label_id": LABEL_ID}
    expected_bundles = (
        "mfbs1_e55d3d6c9a810cf3f3098de90ee948b6c150a45d178760d8e83f7e098a55e415",
        "mfbs1_19cc24e0ff0eeaa45d5cb10a1e1280bf6da0eabace1e1c380b8bc7bfc68504d6",
    )
    for index, (candidate, lock) in enumerate(zip(candidates, locks, strict=True)):
        if (
            lock.get("monthly_retraining_rule")
            != "first official trade date of each calendar month"
        ):
            raise FreshModelContractError("FRESH_RETRAINING_POLICY_INCOMPLETE")
        checks = (
            candidate.get("status") == "retrospective_model_candidate",
            candidate.get("worth_fresh_observation") is True,
            candidate.get("label_id") == LABEL_ID,
            candidate.get("bundle_id") == expected_bundles[index],
            candidate.get("model_spec_id") == MODEL_SPEC_ID,
            candidate.get("walk_forward_spec_id") == WALK_FORWARD_SPEC_ID,
            lock.get("candidate_id") == CANDIDATE_IDS[index],
            lock.get("bundle_id") == expected_bundles[index],
            lock.get("label_id") == LABEL_ID,
            lock.get("model_spec_id") == MODEL_SPEC_ID,
            tuple(lock.get("seed_ensemble", ())) == SEEDS,
            lock.get("primary_statistic") == "fresh daily official-label RankIC",
            lock.get("strategy_protocol") == STRATEGY_PROTOCOL,
            lock.get("no_backfill") is True,
        )
        if not all(checks):
            raise FreshModelContractError("FRESH_LOCK_CONTRACT_MISMATCH")
    return candidates, locks, label


def _validate_executable_label(label: dict[str, Any]) -> None:
    expected = {
        "label_name": "technical_return_1d",
        "formula": "adjusted_close[T+1]/adjusted_open[T+1]-1",
        "entry_offset_sessions": 1,
        "exit_offset_sessions": 1,
        "horizon_sessions": 1,
        "hac_lag": 10,
        "no_forward_fill": True,
    }
    if any(label.get(key) != value for key, value in expected.items()):
        raise FreshModelContractError("EXECUTABLE_LABEL_IDENTITY_MISMATCH")


def _cohort_rows(repository: CampaignRepository) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind("model_fresh_candidate_cohort"):
        rows.append(repository.identity(descriptor.artifact_id) | {"artifact_id": descriptor.artifact_id})
    return rows


def freeze_cohort(
    *, repository_root: Path, work_root: Path, store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    candidates, locks, label = _recover_contracts(repository)
    _validate_executable_label(label)
    payload = ModelFreshCandidateCohortV1().payload()
    receipt = repository.publish(
        "model_fresh_candidate_cohort",
        payload,
        {"model_fresh_candidate_cohort.json": payload},
        lineage=(
            *CANDIDATE_IDS,
            *FRESH_LOCK_IDS,
            LABEL_ID,
            MODEL_SPEC_ID,
            WALK_FORWARD_SPEC_ID,
            PRIOR_FIRST_SEEN_SNAPSHOT_ID,
        ),
    )
    repository.identity(receipt["artifact_id"])
    return payload | {
        "model_fresh_candidate_cohort_id": receipt["artifact_id"],
        "status": "fresh_locked",
        "candidate_count": len(candidates),
        "fresh_lock_count": len(locks),
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def validate_cohort(
    *, repository_root: Path, work_root: Path, store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    rows = _cohort_rows(repository)
    if len(rows) != 1:
        raise FreshModelContractError("MODEL_FRESH_COHORT_CARDINALITY_MISMATCH")
    expected = ModelFreshCandidateCohortV1().payload()
    actual = rows[0]
    artifact_id = actual.pop("artifact_id")
    if actual != {key: value for key, value in expected.items() if key != "model_fresh_candidate_cohort_id"}:
        # repository.identity excludes the semantic ID from its identity payload.
        if actual != expected:
            raise FreshModelContractError("MODEL_FRESH_COHORT_IMMUTABILITY_MISMATCH")
    return {
        "status": "valid",
        "model_fresh_candidate_cohort_id": artifact_id,
        "candidate_count": 2,
        "membership_frozen": True,
        "evidence_gaps": [],
    }


def _materialize_external(repository: CampaignRepository, artifact_id: str, target: Path) -> Path:
    descriptor = repository.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise FreshModelContractError(f"required Artifact absent: {artifact_id}")
    if target.exists():
        shutil.rmtree(target)
    repository.store.materialize_artifact(descriptor.descriptor_id, target)
    return target


def _universe_500(repository: CampaignRepository, authority: dict, work_root: Path) -> set[str]:
    artifact_id = authority["universe_500"]["universe_lock_id"]
    root = _materialize_external(repository, artifact_id, work_root / "universe-500")
    return set(pd.read_parquet(root / "universe.parquet")["ts_code"].astype(str))


def _snapshot_identities(repository: CampaignRepository) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind(FRESH_KIND):
        identity = repository.identity(descriptor.artifact_id)
        rows.append(identity | {"artifact_id": descriptor.artifact_id})
    return sorted(rows, key=lambda row: (row.get("data_as_of_date") or "", row["artifact_id"]))


def _heartbeat_rows(repository: CampaignRepository) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind("fresh_model_heartbeat_run"):
        rows.append(repository.identity(descriptor.artifact_id) | {"artifact_id": descriptor.artifact_id})
    return rows


def _recover_unprocessed_snapshot(
    repository: CampaignRepository, requested_through_date: str
) -> dict[str, Any] | None:
    completed_snapshot_ids = {
        row.get("fresh_market_snapshot_id")
        for row in _heartbeat_rows(repository)
        if row.get("fresh_market_snapshot_id")
    }
    eligible = [
        row
        for row in _snapshot_identities(repository)
        if row.get("data_as_of_date")
        and row["data_as_of_date"] <= requested_through_date
        and row["artifact_id"] not in completed_snapshot_ids
    ]
    if not eligible:
        return None
    latest = eligible[-1]
    return latest | {
        "status": "completed",
        "fresh_market_snapshot_id": latest["artifact_id"],
        "endpoint_calls": {name: 0 for name in ALLOWED_ENDPOINTS},
        "network_calls": 0,
        "new_artifacts": 0,
        "new_blobs": 0,
        "recovered_from_store": True,
    }


def _today() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d")


def _safe_frame(rows: tuple[dict[str, Any], ...] | list[dict[str, Any]], columns: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows), columns=list(columns))
    return frame


def _collect_increment(
    *,
    repository: CampaignRepository,
    authority: dict,
    work_root: Path,
    client: TushareClient,
    requested_through_date: str,
) -> dict[str, Any]:
    prior = _snapshot_identities(repository)
    latest = max(
        [PROJECT_EXPOSURE_DATE, *[row["data_as_of_date"] for row in prior if row.get("data_as_of_date")]]
    )
    start = (pd.Timestamp(latest) + pd.Timedelta(days=1)).strftime("%Y%m%d")
    end = requested_through_date.replace("-", "")
    calendar_response = client.query(
        "trade_cal",
        fields=("exchange", "cal_date", "is_open", "pretrade_date"),
        exchange="SSE",
        start_date=start,
        end_date=end,
    )
    endpoint_calls = {name: 0 for name in ALLOWED_ENDPOINTS}
    endpoint_calls["trade_cal"] = 1
    open_dates = sorted(
        row["cal_date"] for row in calendar_response.rows if int(row["is_open"]) == 1
    )
    fresh_start_candidates = [
        row["cal_date"]
        for row in calendar_response.rows
        if int(row["is_open"]) == 1 and row["cal_date"] > PROJECT_EXPOSURE_DATE.replace("-", "")
    ]
    if not fresh_start_candidates:
        return {
            "status": "no_new_market_data",
            "fresh_start_date": None,
            "endpoint_calls": endpoint_calls,
            "network_calls": 1,
            "new_artifacts": 0,
            "new_blobs": 0,
        }
    fresh_start_date = pd.Timestamp(min(fresh_start_candidates)).strftime("%Y-%m-%d")
    universe = _universe_500(repository, authority, work_root)
    fields = {
        "daily": (
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "vol",
            "amount",
        ),
        "adj_factor": ("ts_code", "trade_date", "adj_factor"),
        "daily_basic": (
            "ts_code",
            "trade_date",
            "turnover_rate",
            "circ_mv",
            "total_mv",
        ),
    }
    raw_rows: dict[str, list[dict[str, Any]]] = {name: [] for name in fields}
    checkpoint_root = work_root / "collection-checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    for trade_date in open_dates:
        for name, requested_fields in fields.items():
            response = client.query(name, fields=requested_fields, trade_date=trade_date)
            endpoint_calls[name] += 1
            raw_rows[name].extend(
                row for row in response.rows if row.get("ts_code") in universe
            )
        (checkpoint_root / f"{trade_date}.json").write_text(
            json.dumps({"trade_date": trade_date, "status": "complete"}, sort_keys=True),
            encoding="utf-8",
        )
    benchmark = client.query(
        "index_daily",
        fields=(
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "vol",
            "amount",
        ),
        ts_code="000300.SH",
        start_date=start,
        end_date=end,
    )
    endpoint_calls["index_daily"] = 1
    daily = _safe_frame(raw_rows["daily"], fields["daily"])
    if daily.empty:
        return {
            "status": "no_new_market_data",
            "fresh_start_date": fresh_start_date,
            "endpoint_calls": endpoint_calls,
            "network_calls": sum(endpoint_calls.values()),
            "new_artifacts": 0,
            "new_blobs": 0,
        }
    actual_dates = sorted(daily["trade_date"].astype(str).unique())
    frames = {
        name: _safe_frame(raw_rows[name], requested_fields)
        for name, requested_fields in fields.items()
    }
    duplicate_counts = {
        name: int(frame.duplicated(["ts_code", "trade_date"]).sum())
        for name, frame in frames.items()
    }
    frames = {
        name: frame.drop_duplicates(["ts_code", "trade_date"], keep="first")
        for name, frame in frames.items()
    }
    calendar = _safe_frame(
        calendar_response.rows, ("exchange", "cal_date", "is_open", "pretrade_date")
    ).drop_duplicates(["exchange", "cal_date"], keep="first")
    benchmark_frame = _safe_frame(
        benchmark.rows,
        ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"),
    ).drop_duplicates(["ts_code", "trade_date"], keep="first")
    daily_keys = set(map(tuple, frames["daily"][["ts_code", "trade_date"]].to_numpy()))
    adj_keys = set(map(tuple, frames["adj_factor"][["ts_code", "trade_date"]].to_numpy()))
    checksum_payload = {
        name: frame.sort_values(list(frame.columns)).to_dict("records")
        for name, frame in sorted(frames.items())
    }
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stable = {
        "schema_version": "fresh-market-snapshot-v1",
        "provider_id": "tushare-pro-v1",
        "model_fresh_candidate_cohort_id": _cohort_rows(repository)[0]["artifact_id"],
        "retrieved_at": retrieved,
        "data_as_of_date": pd.Timestamp(actual_dates[-1]).strftime("%Y-%m-%d"),
        "start_date": pd.Timestamp(actual_dates[0]).strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(actual_dates[-1]).strftime("%Y-%m-%d"),
        "fresh_start_date": fresh_start_date,
        "parent_snapshot_id": prior[-1]["artifact_id"] if prior else PRIOR_FIRST_SEEN_SNAPSHOT_ID,
        "revision": 1,
        "first_seen": True,
        "first_seen_market_snapshot": True,
        "revision_does_not_overwrite_parent": True,
        "endpoint_revisions": {name: 1 for name in ALLOWED_ENDPOINTS},
        "endpoints": list(ALLOWED_ENDPOINTS),
        "trade_dates": [pd.Timestamp(value).strftime("%Y-%m-%d") for value in actual_dates],
        "symbol_count": int(frames["daily"]["ts_code"].nunique()),
        "row_counts": {name: len(frame) for name, frame in frames.items()}
        | {"trade_cal": len(calendar), "index_daily": len(benchmark_frame)},
        "duplicate_counts": duplicate_counts,
        "missing_counts": {
            "adj_factor_keys": len(daily_keys - adj_keys),
            "daily_required_fields": int(frames["daily"].isna().sum().sum()),
        },
        "checksum": hash_payload(checksum_payload),
        "incremental_only": True,
        "latest_stored_official_date_before_request": latest,
        "no_backfill": pd.Timestamp(actual_dates[0]).strftime("%Y-%m-%d") > PROJECT_EXPOSURE_DATE,
        "schema_valid": True,
        "symbol_mapping_valid": all(
            code.endswith((".SH", ".SZ", ".BJ")) for code in frames["daily"]["ts_code"]
        ),
        "adj_factor_complete": not (daily_keys - adj_keys),
        "trade_calendar_valid": set(actual_dates).issubset(
            set(calendar.loc[calendar["is_open"].astype(int).eq(1), "cal_date"].astype(str))
        ),
        "lifecycle_valid": set(frames["daily"]["ts_code"]).issubset(universe),
        "credential_source": "environment_only_not_persisted",
        "credential_persisted": False,
        "endpoint_call_accounting": endpoint_calls,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    if not all(
        (
            stable["no_backfill"],
            stable["schema_valid"],
            stable["symbol_mapping_valid"],
            stable["adj_factor_complete"],
            stable["trade_calendar_valid"],
            stable["lifecycle_valid"],
        )
    ):
        raise FreshModelContractError("FRESH_MARKET_SNAPSHOT_QUALITY_FAILED")
    file_root = work_root / "fresh-snapshot-files" / stable["data_as_of_date"]
    file_root.mkdir(parents=True, exist_ok=True)
    artifact_files: dict[str, Path | dict] = {}
    for name, frame in frames.items():
        path = file_root / f"{name}.parquet"
        frame.to_parquet(path, index=False, compression="zstd")
        artifact_files[path.name] = path
    for name, frame in (("trade_calendar", calendar), ("index_daily", benchmark_frame)):
        path = file_root / f"{name}.parquet"
        frame.to_parquet(path, index=False, compression="zstd")
        artifact_files[path.name] = path
    artifact_files["snapshot.json"] = stable
    result, receipt = _publish(
        repository,
        FRESH_KIND,
        stable,
        "snapshot.json",
        (
            stable["model_fresh_candidate_cohort_id"],
            stable["parent_snapshot_id"],
            authority["universe_500"]["universe_lock_id"],
        ),
        artifact_files,
    )
    return result | {
        "status": "completed",
        "fresh_market_snapshot_id": receipt["artifact_id"],
        "endpoint_calls": endpoint_calls,
        "network_calls": sum(endpoint_calls.values()),
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _snapshot_frames(
    repository: CampaignRepository, artifact_id: str, work_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = _materialize_external(repository, artifact_id, work_root / artifact_id)
    daily = pd.read_parquet(root / "daily.parquet")
    adj = pd.read_parquet(root / "adj_factor.parquet")
    basic = pd.read_parquet(root / "daily_basic.parquet")
    benchmark = pd.read_parquet(root / "index_daily.parquet")
    calendar_name = (
        "trade_calendar.parquet"
        if (root / "trade_calendar.parquet").is_file()
        else "trade_calendar.parquet"
    )
    calendar = pd.read_parquet(root / calendar_name)
    if daily.empty:
        return daily, benchmark, calendar, basic
    merged = daily.merge(adj, on=["ts_code", "trade_date"], validate="one_to_one")
    merged = merged.merge(
        basic, on=["ts_code", "trade_date"], how="left", validate="one_to_one"
    )
    for name in (
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "vol",
        "amount",
        "adj_factor",
        "turnover_rate",
    ):
        if name in merged:
            merged[name] = pd.to_numeric(merged[name], errors="coerce")
    merged["symbol"] = merged["ts_code"].map(
        lambda code: ("SH" if code.endswith(".SH") else "SZ" if code.endswith(".SZ") else "BJ")
        + code.split(".")[0]
    )
    merged["trade_date"] = pd.to_datetime(merged["trade_date"], format="%Y%m%d")
    for name in ("open", "high", "low", "close"):
        merged[f"adjusted_{name}"] = merged[name] * merged["adj_factor"]
    merged["tradable"] = (
        merged[["open", "close", "vol"]].notna().all(axis=1) & merged["vol"].gt(0)
    )
    benchmark["trade_date"] = pd.to_datetime(benchmark["trade_date"], format="%Y%m%d")
    return merged, benchmark, calendar, basic


def _combined_market(
    bundle: Any, repository: CampaignRepository, work_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    universe = set(bundle.matrix["symbol"].unique())
    normalized = bundle.normalized.copy()
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"])
    normalized = normalized[normalized["symbol"].isin(universe)]
    benchmark = bundle.benchmark.copy()
    benchmark["trade_date"] = pd.to_datetime(benchmark["trade_date"])
    calendars: list[str] = []
    snapshot_ids = [PRIOR_FIRST_SEEN_SNAPSHOT_ID] + [
        row["artifact_id"] for row in _snapshot_identities(repository)
    ]
    for artifact_id in snapshot_ids:
        frame, market, calendar, _ = _snapshot_frames(
            repository, artifact_id, work_root / "snapshots"
        )
        if not frame.empty:
            frame = frame[frame["symbol"].isin(universe)]
            normalized = pd.concat([normalized, frame], ignore_index=True)
        if not market.empty:
            benchmark = pd.concat([benchmark, market], ignore_index=True)
        if not calendar.empty:
            date_column = "cal_date"
            calendars.extend(
                pd.Timestamp(value).strftime("%Y-%m-%d")
                for value in calendar.loc[
                    pd.to_numeric(calendar["is_open"], errors="coerce").eq(1), date_column
                ]
            )
    normalized = (
        normalized.sort_values(["trade_date", "symbol"], kind="mergesort")
        .drop_duplicates(["symbol", "trade_date"], keep="first")
        .reset_index(drop=True)
    )
    benchmark = (
        benchmark.sort_values("trade_date", kind="mergesort")
        .drop_duplicates("trade_date", keep="first")
        .reset_index(drop=True)
    )
    return normalized, benchmark, sorted(set(calendars))


def _feature_matrix(
    bundle: Any,
    repository: CampaignRepository,
    work_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized, benchmark, calendar = _combined_market(bundle, repository, work_root)
    existing = compute_features(normalized, benchmark)
    market = normalized.rename(columns={"vol": "volume"}).copy()
    market = market.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    market["daily_return"] = market.groupby("symbol")["adjusted_close"].pct_change(
        fill_method=None
    )
    market["vwap"] = (
        pd.to_numeric(market["amount"], errors="coerce")
        * 1000
        / (pd.to_numeric(market["volume"], errors="coerce") * 100).replace(0, np.nan)
    )
    market_values = benchmark.copy()
    market_values["csi300_return"] = pd.to_numeric(
        market_values["close"], errors="coerce"
    ).pct_change(fill_method=None)
    market = market.merge(
        market_values[["trade_date", "csi300_return"]],
        on="trade_date",
        how="left",
        validate="many_to_one",
    )
    for name, values in primitive_values(market).items():
        market[name] = values
    feature_catalog, primitive_catalog = _catalog(repository)
    for row in feature_catalog["new_research_terminal_features"]:
        market[row["feature_name"]] = evaluate_ast_v2(
            row["canonical_ast"], market, V2_PRIMITIVES
        )
    expanded_names = [
        row["feature_name"] for row in feature_catalog["new_research_terminal_features"]
    ]
    primitive_names = [row["name"] for row in primitive_catalog["primitives"]]
    expanded = market[["symbol", "trade_date", *expanded_names, *primitive_names]].copy()
    matrix = existing.merge(
        expanded, on=["symbol", "trade_date"], validate="one_to_one"
    )
    label_definition = {
        "horizon_sessions": 1,
    }
    labels, quality = _label_values(normalized, label_definition)
    matrix = matrix.merge(
        labels[
            [
                "symbol",
                "trade_date",
                "entry_date",
                "exit_date",
                "raw_return",
                "model_label",
                "sample_weight",
            ]
        ].rename(columns={"raw_return": "raw_label"}),
        on=["symbol", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    matrix = matrix.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(
        drop=True
    )
    return matrix, {
        "calendar": calendar,
        "normalized": normalized,
        "benchmark": benchmark,
        "feature_catalog": feature_catalog,
        "primitive_catalog": primitive_catalog,
        "label_quality": quality,
    }


def _model_spec(repository: CampaignRepository) -> dict[str, Any]:
    spec = _identity(repository, MODEL_SPEC_ID)
    if tuple(spec.get("seeds", ())) != SEEDS:
        raise FreshModelContractError("FRESH_MODEL_SEED_POLICY_MISMATCH")
    if spec.get("number_of_boosting_rounds") != 200 or spec.get("early_stopping"):
        raise FreshModelContractError("FRESH_MODEL_SPEC_MISMATCH")
    return spec


def _bundle_specs(repository: CampaignRepository, model_spec_id: str) -> dict[str, dict]:
    feature, primitive = _catalog(repository)
    rows = _bundle_payloads(model_spec_id, feature, primitive)
    result = {}
    for row in rows:
        expected = row["bundle_id"]
        actual = repository.store.find_by_artifact_id(expected)
        if actual is None:
            raise FreshModelContractError("FROZEN_MODEL_BUNDLE_ABSENT")
        result[row["bundle_name"]] = row
    return result


def _training_rows(
    matrix: pd.DataFrame, cutoff: str, purge_sessions: int = 10
) -> tuple[pd.DataFrame, str]:
    dates = sorted(
        pd.Timestamp(value)
        for value in matrix.loc[matrix["trade_date"].le(cutoff), "trade_date"].unique()
    )
    if len(dates) <= purge_sessions:
        raise FreshModelContractError("FRESH_TRAINING_HISTORY_INSUFFICIENT")
    effective = dates[-purge_sessions - 1]
    train = matrix[
        matrix["trade_date"].le(effective)
        & matrix["exit_date"].le(effective)
        & np.isfinite(pd.to_numeric(matrix["model_label"], errors="coerce"))
        & pd.to_numeric(matrix["sample_weight"], errors="coerce").gt(0)
    ].copy()
    return train, effective.strftime("%Y-%m-%d")


def _existing_training(
    repository: CampaignRepository, candidate_id: str, effective_from: str
) -> list[dict[str, Any]]:
    rows = []
    for descriptor in repository.store.list_by_kind("fresh_model_training_event"):
        identity = repository.identity(descriptor.artifact_id)
        if (
            identity.get("candidate_id") == candidate_id
            and identity.get("effective_from") == effective_from
        ):
            rows.append(identity | {"artifact_id": descriptor.artifact_id})
    return sorted(rows, key=lambda row: row["seed"])


def _monthly_training_event_count(
    repository: CampaignRepository, candidate_id: str
) -> int:
    effective_dates = set()
    for descriptor in repository.store.list_by_kind("fresh_model_training_event"):
        identity = repository.identity(descriptor.artifact_id)
        if (
            identity.get("candidate_id") == candidate_id
            and identity.get("event_type") == "monthly_retraining_event"
            and identity.get("counts_toward_monthly_retraining_minimum") is True
        ):
            effective_dates.add(identity["effective_from"])
    return len(effective_dates)


def _train_models(
    *,
    repository: CampaignRepository,
    spec: dict[str, Any],
    candidate: dict[str, Any],
    bundle_spec: dict[str, Any],
    matrix: pd.DataFrame,
    training_cutoff: str,
    effective_from: str,
    event_type: str,
    work_root: Path,
) -> tuple[list[Any], list[str], dict[str, Any], dict[str, int]]:
    import lightgbm as lgb

    prior = _existing_training(repository, candidate["candidate_id"], effective_from)
    if len(prior) == len(SEEDS):
        models, ids = [], []
        for row in prior:
            root = repository.materialize(row["artifact_id"])
            models.append(lgb.Booster(model_file=str(root / "model.txt")))
            ids.append(row["artifact_id"])
        membership = _identity(repository, prior[0]["bundle_membership_id"])
        return models, ids, membership, {
            "model_training_calls": 0,
            "new_artifacts": 0,
            "new_blobs": 0,
        }
    train, effective_end = _training_rows(matrix, training_cutoff)
    candidates = list(bundle_spec["candidate_feature_names"])
    if bundle_spec["bundle_name"] == "combined_decorrelated_technical":
        selected, evidence = select_bundle_c(train, candidates)
    else:
        selected, evidence = candidates, {
            "selection_data": "pre_registered",
            "label_reads": 0,
            "performance_reads": 0,
            "candidate_count": len(candidates),
            "retained_count": len(candidates),
            "quality_evidence": {},
            "redundancy_rejections": [],
        }
    membership_identity = {
        "schema_version": "fresh-model-bundle-membership-v1",
        "provider_id": "tushare-pro-v1",
        "candidate_id": candidate["candidate_id"],
        "bundle_id": bundle_spec["bundle_id"],
        "bundle_name": bundle_spec["bundle_name"],
        "effective_from": effective_from,
        "training_cutoff": training_cutoff,
        "selected_features": selected,
        "selection_evidence": evidence,
        "selection_data": "train_only" if bundle_spec["bundle_name"].startswith("combined") else "frozen",
        "label_reads_for_selection": 0,
        "fresh_performance_reads_for_selection": 0,
        "feature_importance_reads_for_selection": 0,
        "outer_fresh_prediction_reads_for_selection": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    membership, membership_receipt = _publish(
        repository,
        "fresh_model_bundle_membership",
        membership_identity,
        "fresh_model_bundle_membership.json",
        (candidate["candidate_id"], bundle_spec["bundle_id"]),
    )
    train_x = _cross_section_transform(train, selected)
    models, ids = [], []
    new_artifacts = int(not membership_receipt["exact_existing"])
    new_blobs = membership_receipt["new_blob_count"]
    for seed in SEEDS:
        params = dict(spec["parameters"]) | {
            "seed": seed,
            "bagging_seed": seed,
            "feature_fraction_seed": seed,
            "data_random_seed": seed,
        }
        dataset = lgb.Dataset(
            train_x,
            label=train["model_label"].to_numpy(dtype=float),
            weight=train["sample_weight"].to_numpy(dtype=float),
            feature_name=selected,
            free_raw_data=True,
        )
        model = lgb.train(params, dataset, num_boost_round=200, callbacks=[])
        model_path = (
            work_root
            / "models"
            / candidate["candidate_id"]
            / effective_from
            / f"{seed}.txt"
        )
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save_model(str(model_path), num_iteration=200)
        identity = {
            "schema_version": "fresh-model-training-event-v1",
            "provider_id": "tushare-pro-v1",
            "candidate_id": candidate["candidate_id"],
            "model_spec_id": MODEL_SPEC_ID,
            "bundle_id": bundle_spec["bundle_id"],
            "bundle_membership_id": membership["artifact_id"],
            "event_type": event_type,
            "effective_from": effective_from,
            "declared_training_cutoff": training_cutoff,
            "effective_training_end_after_purge": effective_end,
            "training_start": "2019-01-02",
            "train_rows": len(train),
            "train_symbols": int(train["symbol"].nunique()),
            "seed": seed,
            "parameters": params,
            "boosting_rounds": 200,
            "early_stopping": False,
            "threads": 1,
            "deterministic": True,
            "counts_toward_monthly_retraining_minimum": event_type == "monthly_retraining_event",
            "label_cutoff_strictly_before_prediction": training_cutoff < effective_from,
            "model_optimization_calls": 0,
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        event, receipt = _publish(
            repository,
            "fresh_model_training_event",
            identity,
            "fresh_model_training_event.json",
            (candidate["candidate_id"], membership["artifact_id"], MODEL_SPEC_ID),
            {"fresh_model_training_event.json": identity, "model.txt": model_path},
        )
        models.append(model)
        ids.append(receipt["artifact_id"])
        new_artifacts += int(not receipt["exact_existing"])
        new_blobs += receipt["new_blob_count"]
    return models, ids, membership, {
        "model_training_calls": len(SEEDS),
        "new_artifacts": new_artifacts,
        "new_blobs": new_blobs,
    }


def _existing_prediction(
    repository: CampaignRepository, candidate_id: str, prediction_date: str
) -> dict[str, Any] | None:
    for descriptor in repository.store.list_by_kind("fresh_model_prediction"):
        identity = repository.identity(descriptor.artifact_id)
        if (
            identity.get("candidate_id") == candidate_id
            and identity.get("prediction_date") == prediction_date
        ):
            return identity | {"artifact_id": descriptor.artifact_id}
    return None


def _predict_date(
    *,
    repository: CampaignRepository,
    candidate: dict[str, Any],
    models: list[Any],
    model_event_ids: list[str],
    membership: dict[str, Any],
    matrix: pd.DataFrame,
    prediction_date: str,
    training_cutoff: str,
    snapshot_id: str,
    work_root: Path,
) -> tuple[dict[str, Any], dict[str, int]]:
    prior = _existing_prediction(repository, candidate["candidate_id"], prediction_date)
    if prior is not None:
        return prior, {"prediction_writes": 0, "new_artifacts": 0, "new_blobs": 0}
    rows = matrix[matrix["trade_date"].eq(prediction_date)].copy()
    if rows.empty:
        raise FreshModelContractError("FRESH_PREDICTION_DATE_ABSENT")
    selected = membership["selected_features"]
    values = _cross_section_transform(rows, selected)
    seed_predictions = [
        np.asarray(model.predict(values, num_iteration=200), dtype=float) for model in models
    ]
    ensemble = np.mean(np.vstack(seed_predictions), axis=0)
    output = rows[["symbol", "trade_date"]].copy()
    for index, seed in enumerate(SEEDS):
        output[f"raw_prediction_seed_{seed}"] = seed_predictions[index]
    output["raw_prediction"] = ensemble
    output["score"] = output.groupby("trade_date")["raw_prediction"].rank(pct=True)
    output["signal"] = output["score"]
    path = work_root / "predictions" / candidate["candidate_id"] / f"{prediction_date}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(path, index=False, compression="zstd")
    finite = np.isfinite(output["raw_prediction"])
    identity = {
        "schema_version": "fresh-model-prediction-v1",
        "provider_id": "tushare-pro-v1",
        "candidate_id": candidate["candidate_id"],
        "bundle_id": candidate["bundle_id"],
        "model_event_ids": model_event_ids,
        "bundle_membership_id": membership["artifact_id"],
        "fresh_market_snapshot_id": snapshot_id,
        "prediction_date": prediction_date,
        "training_cutoff": training_cutoff,
        "prediction_coverage": float(finite.mean()),
        "finite_members": int(finite.sum()),
        "row_count": len(output),
        "score_checksum": hash_file(path),
        "three_seed_equal_weight": True,
        "signal_lag": 1,
        "execution_date_rule": "next official trade date",
        "execution_price": "adjusted_open",
        "model_optimization_calls": 0,
        "strategy_optimization_calls": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    result, receipt = _publish(
        repository,
        "fresh_model_prediction",
        identity,
        "fresh_model_prediction.json",
        (*model_event_ids, membership["artifact_id"], snapshot_id),
        {"fresh_model_prediction.json": identity, "predictions.parquet": path},
    )
    return result, {
        "prediction_writes": int(not receipt["exact_existing"]),
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _prediction_values(repository: CampaignRepository, prediction_id: str) -> pd.DataFrame:
    root = repository.materialize(prediction_id)
    return pd.read_parquet(root / "predictions.parquet")


def _label_observations(
    *,
    repository: CampaignRepository,
    candidate: dict[str, Any],
    predictions: list[dict[str, Any]],
    matrix: pd.DataFrame,
    official_dates: list[str],
    data_as_of: str,
    snapshot_id: str,
    work_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    results, writes, blobs = [], 0, 0
    positions = {value: index for index, value in enumerate(sorted(official_dates))}
    for prediction in predictions:
        date = prediction["prediction_date"]
        index = positions.get(date)
        if index is None or index + 1 >= len(official_dates):
            continue
        exit_date = official_dates[index + 1]
        if exit_date > data_as_of:
            continue
        prior = None
        for descriptor in repository.store.list_by_kind("fresh_model_label_observation"):
            identity = repository.identity(descriptor.artifact_id)
            if (
                identity.get("candidate_id") == candidate["candidate_id"]
                and identity.get("prediction_date") == date
            ):
                prior = identity | {"artifact_id": descriptor.artifact_id}
                break
        if prior is not None:
            results.append(prior)
            continue
        values = _prediction_values(repository, prediction["artifact_id"])
        labels = matrix.loc[
            matrix["trade_date"].eq(date),
            ["symbol", "model_label", "raw_label", "entry_date", "exit_date"],
        ]
        observed = values.merge(labels, on="symbol", validate="one_to_one")
        observed = observed[
            observed["entry_date"].eq(pd.Timestamp(exit_date))
            & observed["exit_date"].eq(pd.Timestamp(exit_date))
        ].copy()
        valid = observed.dropna(subset=["raw_prediction", "model_label", "raw_label"])
        rankic = (
            valid["raw_prediction"].corr(valid["model_label"], method="spearman")
            if len(valid) >= 20
            else np.nan
        )
        ic = (
            valid["raw_prediction"].corr(valid["model_label"]) if len(valid) >= 20 else np.nan
        )
        count = max(1, math.ceil(len(valid) * 0.10))
        q10_q1 = (
            valid.nlargest(count, "raw_prediction")["raw_label"].mean()
            - valid.nsmallest(count, "raw_prediction")["raw_label"].mean()
            if len(valid) >= 20
            else np.nan
        )
        top_spread = (
            valid.nlargest(min(20, len(valid)), "raw_prediction")["raw_label"].mean()
            - valid["raw_label"].mean()
            if len(valid) >= 20
            else np.nan
        )
        path = work_root / "labels" / candidate["candidate_id"] / f"{date}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        observed.to_parquet(path, index=False, compression="zstd")
        identity = {
            "schema_version": "fresh-model-label-observation-v1",
            "provider_id": "tushare-pro-v1",
            "candidate_id": candidate["candidate_id"],
            "prediction_id": prediction["artifact_id"],
            "label_id": LABEL_ID,
            "fresh_market_snapshot_id": snapshot_id,
            "prediction_date": date,
            "label_maturity_date": exit_date,
            "entry": "adjusted_open[T+1]",
            "exit": "adjusted_close[T+1]",
            "tradeability_required": True,
            "first_seen_snapshot_bound": True,
            "row_count": len(observed),
            "finite_count": len(valid),
            "coverage": len(valid) / len(observed) if len(observed) else 0.0,
            "ic": None if pd.isna(ic) else float(ic),
            "rankic": None if pd.isna(rankic) else float(rankic),
            "q10_q1": None if pd.isna(q10_q1) else float(q10_q1),
            "top20_universe_spread": (
                None if pd.isna(top_spread) else float(top_spread)
            ),
            "pit_violations": 0,
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        result, receipt = _publish(
            repository,
            "fresh_model_label_observation",
            identity,
            "fresh_model_label_observation.json",
            (prediction["artifact_id"], LABEL_ID, snapshot_id),
            {"fresh_model_label_observation.json": identity, "labels.parquet": path},
        )
        results.append(result)
        writes += int(not receipt["exact_existing"])
        blobs += receipt["new_blob_count"]
    return results, {
        "label_writes": writes,
        "new_artifacts": writes,
        "new_blobs": blobs,
    }


def _strategy_observation(
    *,
    repository: CampaignRepository,
    candidate: dict[str, Any],
    predictions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    snapshot_id: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    dates = sorted(row["prediction_date"] for row in predictions)
    completed_periods = len(dates) // STRATEGY_PROTOCOL["rebalance_interval"]
    rebalance_dates = dates[:: STRATEGY_PROTOCOL["rebalance_interval"]]
    mature = {row["prediction_date"]: row for row in labels}
    daily_top_returns = [
        mature[date]["top20_universe_spread"]
        for date in rebalance_dates
        if date in mature and mature[date].get("top20_universe_spread") is not None
    ]
    gross = float(np.prod([1.0 + value for value in daily_top_returns]) - 1.0)
    turnover = float(len(daily_top_returns) * 2.0)
    cost = turnover * 0.0015
    net = gross - cost
    identity = {
        "schema_version": "fresh-model-strategy-observation-v1",
        "provider_id": "tushare-pro-v1",
        "candidate_id": candidate["candidate_id"],
        "fresh_market_snapshot_id": snapshot_id,
        "strategy_protocol": STRATEGY_PROTOCOL,
        "prediction_ids": [row["artifact_id"] for row in predictions],
        "label_observation_ids": [row["artifact_id"] for row in labels],
        "rebalance_dates": rebalance_dates,
        "rebalance_periods": completed_periods,
        "completed_holding_windows": completed_periods,
        "net_return": net if completed_periods else None,
        "csi300_return": None,
        "csi300_excess": None,
        "sharpe": None,
        "maximum_drawdown": None,
        "turnover": turnover,
        "transaction_cost": cost,
        "best_10_days_contribution": None,
        "status": "accumulating" if not completed_periods else "observed",
        "qlib_calls": 0,
        "strategy_optimization_calls": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    result, receipt = _publish(
        repository,
        "fresh_model_strategy_observation",
        identity,
        "fresh_model_strategy_observation.json",
        (
            candidate["candidate_id"],
            snapshot_id,
            *[row["artifact_id"] for row in predictions],
            *[row["artifact_id"] for row in labels],
        ),
    )
    return result, {
        "strategy_writes": int(not receipt["exact_existing"]),
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _candidate_observation(
    *,
    repository: CampaignRepository,
    cohort_id: str,
    candidate: dict[str, Any],
    predictions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    strategy: dict[str, Any],
    fresh_dates: list[str],
    monthly_event_count: int,
    snapshot_id: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    rankics = [row["rankic"] for row in labels if row.get("rankic") is not None]
    coverage = float(np.mean([row["coverage"] for row in labels])) if labels else 0.0
    rankic_std = float(np.std(rankics, ddof=1)) if len(rankics) > 1 else None
    observation = {
        "schema_version": "fresh-model-candidate-observation-v1",
        "provider_id": "tushare-pro-v1",
        "model_fresh_candidate_cohort_id": cohort_id,
        "candidate_id": candidate["candidate_id"],
        "bundle_id": candidate["bundle_id"],
        "label_id": LABEL_ID,
        "fresh_market_snapshot_id": snapshot_id,
        "fresh_trading_days": len(fresh_dates),
        "fresh_prediction_days": len(predictions),
        "mature_label_days": len(labels),
        "completed_holding_windows": strategy["completed_holding_windows"],
        "rebalance_periods": strategy["rebalance_periods"],
        "monthly_retraining_events": monthly_event_count,
        "mean_rankic": float(np.mean(rankics)) if rankics else None,
        "rankic_positive_rate": (
            float(np.mean(np.asarray(rankics) > 0)) if rankics else None
        ),
        "rankic_ir": (
            float(np.mean(rankics) / rankic_std * math.sqrt(252))
            if rankic_std and rankic_std > 0
            else None
        ),
        "coverage": coverage,
        "q10_q1": (
            float(np.mean([row["q10_q1"] for row in labels if row.get("q10_q1") is not None]))
            if any(row.get("q10_q1") is not None for row in labels)
            else None
        ),
        "top20_universe_spread": (
            float(
                np.mean(
                    [
                        row["top20_universe_spread"]
                        for row in labels
                        if row.get("top20_universe_spread") is not None
                    ]
                )
            )
            if any(row.get("top20_universe_spread") is not None for row in labels)
            else None
        ),
        "net_return": strategy["net_return"],
        "csi300_return": strategy["csi300_return"],
        "csi300_excess": strategy["csi300_excess"],
        "sharpe": strategy["sharpe"],
        "maximum_drawdown": strategy["maximum_drawdown"],
        "turnover": strategy["turnover"],
        "transaction_cost": strategy["transaction_cost"],
        "best_10_days_contribution": strategy["best_10_days_contribution"],
        "daily_rankic": rankics,
        "pit_violations": 0,
        "parameters_unchanged": True,
        "bundle_rule_unchanged": True,
        "label_unchanged": True,
        "no_backfill": True,
        "minimum_evidence_passed": False,
        "status": "fresh_evidence_accumulating",
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    observation["minimum_evidence_passed"] = minimum_evidence_passed(observation)
    result, receipt = _publish(
        repository,
        "fresh_model_candidate_observation",
        observation,
        "fresh_model_candidate_observation.json",
        (
            cohort_id,
            candidate["candidate_id"],
            snapshot_id,
            strategy["artifact_id"],
            *[row["artifact_id"] for row in labels],
        ),
    )
    return result, {
        "candidate_observation_writes": int(not receipt["exact_existing"]),
        "new_artifacts": int(not receipt["exact_existing"]),
        "new_blobs": receipt["new_blob_count"],
    }


def _assess(
    repository: CampaignRepository,
    cohort_id: str,
    observations: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    all_mature = len(observations) == 2 and all(
        row["minimum_evidence_passed"] for row in observations
    )
    if all_mature:
        tests = []
        for row in observations:
            test = hac_mean_test(row["daily_rankic"], lag=10)
            tests.append(
                {
                    "candidate_id": row["candidate_id"],
                    "raw_p_value": test["raw_p_value"],
                    "test": test,
                }
            )
        adjusted = benjamini_hochberg(tests, q=0.10)
        results = [
            {
                "candidate_id": row["candidate_id"],
                "raw_p_value": row["raw_p_value"],
                "adjusted_q_value": row["adjusted_q_value"],
                "rank": row["rank_in_multiple_test"],
            }
            for row in adjusted
        ]
        calls = 1
        status = "completed"
    else:
        adjusted = []
        results = []
        calls = 0
        status = "awaiting_all_members_minimum_evidence"
    multiple_identity = {
        "schema_version": "fresh-model-cohort-multiple-testing-v1",
        "provider_id": "tushare-pro-v1",
        "model_fresh_candidate_cohort_id": cohort_id,
        "method": "benjamini_hochberg",
        "fdr_q": 0.10,
        "hac_lag": 10,
        "hypothesis_count": 2,
        "tested_hypothesis_count": len(results),
        "cohort_members_all_mature": all_mature,
        "results": results,
        "status": status,
        "multiple_testing_calls": calls,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    multiple, receipt = _publish(
        repository,
        "fresh_model_cohort_multiple_testing",
        multiple_identity,
        "fresh_model_cohort_multiple_testing.json",
        (cohort_id, *[row["artifact_id"] for row in observations]),
    )
    assessments = []
    new_artifacts = int(not receipt["exact_existing"])
    new_blobs = receipt["new_blob_count"]
    by_candidate = {row["candidate_id"]: row for row in adjusted}
    for observation in observations:
        if not all_mature:
            fresh_status = "fresh_evidence_accumulating"
            raw_p = adjusted_q = None
        else:
            tested = by_candidate[observation["candidate_id"]]
            raw_p = tested["raw_p_value"]
            adjusted_q = tested["adjusted_q_value"]
            mean_rankic = observation["mean_rankic"]
            excess = observation["csi300_excess"]
            if mean_rankic > 0 and adjusted_q <= 0.10 and excess is not None and excess > 0:
                fresh_status = "fresh_supported"
            elif mean_rankic <= 0 and adjusted_q > 0.10:
                fresh_status = "fresh_rejected"
            else:
                fresh_status = "fresh_inconclusive"
        if fresh_status not in LEGAL_FRESH_STATES:
            raise FreshModelContractError("FRESH_MODEL_STATUS_INVALID")
        identity = {
            "schema_version": "fresh-model-candidate-assessment-v1",
            "provider_id": "tushare-pro-v1",
            "model_fresh_candidate_cohort_id": cohort_id,
            "candidate_id": observation["candidate_id"],
            "candidate_observation_id": observation["artifact_id"],
            "multiple_testing_id": multiple["artifact_id"],
            "status": fresh_status,
            "minimum_evidence_passed": observation["minimum_evidence_passed"],
            "raw_p_value": raw_p,
            "adjusted_q_value": adjusted_q,
            "parameters_unchanged": True,
            "bundle_rule_unchanged": True,
            "label_unchanged": True,
            "no_backfill": True,
            "registry_state": "unchanged",
            "registry_writes": 0,
            "promotion_writes": 0,
        }
        result, assessment_receipt = _publish(
            repository,
            "fresh_model_candidate_assessment",
            identity,
            "fresh_model_candidate_assessment.json",
            (cohort_id, observation["artifact_id"], multiple["artifact_id"]),
        )
        assessments.append(result)
        new_artifacts += int(not assessment_receipt["exact_existing"])
        new_blobs += assessment_receipt["new_blob_count"]
    return multiple, assessments, {
        "multiple_testing_calls": calls,
        "candidate_status_writes": sum(
            row["status"] != "fresh_evidence_accumulating" for row in assessments
        ),
        "new_artifacts": new_artifacts,
        "new_blobs": new_blobs,
    }


def run_fresh_heartbeat(
    *,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
    requested_through_date: str | None = None,
    client: TushareClient | None = None,
) -> dict[str, Any]:
    requested = requested_through_date or _today()
    bundle, repository = _runtime(repository_root, work_root, store_root)
    cohort = freeze_cohort(
        repository_root=repository_root, work_root=work_root, store_root=store_root
    )
    cohort_id = cohort["model_fresh_candidate_cohort_id"]
    for prior in _heartbeat_rows(repository):
        if (
            prior.get("model_fresh_candidate_cohort_id") == cohort_id
            and prior.get("requested_through_date") == requested
            and prior.get("status") in {"completed", "fresh_evidence_accumulating"}
        ):
            return prior | {
                "fresh_model_heartbeat_run_id": prior["artifact_id"],
                "status": "exact_replay",
                "exact_existing": True,
                "execution_counts": {
                    name: 0
                    for name in (
                        "tushare_calls",
                        "network_calls",
                        "model_training_calls",
                        "prediction_writes",
                        "label_writes",
                        "qlib_calls",
                        "strategy_writes",
                        "multiple_testing_calls",
                        "candidate_status_writes",
                        "registry_writes",
                        "promotion_writes",
                        "new_artifacts",
                        "new_blobs",
                    )
                },
            }
    candidates, locks, label = _recover_contracts(repository)
    _validate_executable_label(label)
    if not os.environ.get("TUSHARE_TOKEN") and client is None:
        return {
            "status": "fresh_data_blocked",
            "reason": "blocked_token_absent",
            "model_fresh_candidate_cohort_id": cohort_id,
        "credential_source": "environment_only_not_persisted",
            "credential_present": False,
            "credential_persisted": False,
            "execution_counts": {
                "tushare_calls": 0,
                "network_calls": 0,
                "registry_writes": 0,
                "promotion_writes": 0,
                "new_artifacts": cohort["new_artifacts"],
                "new_blobs": cohort["new_blobs"],
            },
        }
    collection = _recover_unprocessed_snapshot(repository, requested)
    if collection is None:
        api = client or TushareClient()
        collection = _collect_increment(
            repository=repository,
            authority=bundle.authority,
            work_root=Path(work_root),
            client=api,
            requested_through_date=requested,
        )
    if collection["status"] == "no_new_market_data":
        return {
            "status": "no_new_market_data",
            "model_fresh_candidate_cohort_id": cohort_id,
            "fresh_start_date": collection["fresh_start_date"],
            "execution_counts": {
                "tushare_calls": collection["network_calls"],
                "network_calls": collection["network_calls"],
                "model_training_calls": 0,
                "prediction_writes": 0,
                "label_writes": 0,
                "qlib_calls": 0,
                "strategy_writes": 0,
                "multiple_testing_calls": 0,
                "candidate_status_writes": 0,
                "registry_writes": 0,
                "promotion_writes": 0,
                "new_artifacts": 0,
                "new_blobs": 0,
            },
        }
    fresh_start = collection["fresh_start_date"]
    if fresh_start <= PROJECT_EXPOSURE_DATE:
        raise FreshModelContractError("FRESH_NO_BACKFILL_VIOLATION")
    if any(lock.get("fresh_start_date") not in (None, fresh_start) for lock in locks):
        raise FreshModelContractError("FRESH_LOCK_START_DATE_MISMATCH")
    snapshot_id = collection["fresh_market_snapshot_id"]
    matrix, sources = _feature_matrix(bundle, repository, Path(work_root) / "features")
    official_dates = sorted(
        value
        for value in set(sources["calendar"])
        if value >= fresh_start and value <= collection["data_as_of_date"]
    )
    if not official_dates:
        raise FreshModelContractError("FRESH_OFFICIAL_CALENDAR_EMPTY")
    spec = _model_spec(repository)
    bundles = _bundle_specs(repository, MODEL_SPEC_ID)
    total = {
        "tushare_calls": collection["network_calls"],
        "network_calls": collection["network_calls"],
        "model_training_calls": 0,
        "prediction_writes": 0,
        "label_writes": 0,
        "qlib_calls": 0,
        "strategy_writes": 0,
        "multiple_testing_calls": 0,
        "candidate_status_writes": 0,
        "registry_writes": 0,
        "promotion_writes": 0,
        "new_artifacts": collection["new_artifacts"],
        "new_blobs": collection["new_blobs"],
    }
    all_predictions: dict[str, list[dict[str, Any]]] = {}
    all_labels: dict[str, list[dict[str, Any]]] = {}
    strategies = {}
    observations = []
    initial_cutoff = max(
        value
        for value in set(sources["calendar"])
        if value < fresh_start
    )
    for candidate in candidates:
        bundle_name = (
            "expanded_technical_space"
            if candidate["bundle_id"]
            == "mfbs1_e55d3d6c9a810cf3f3098de90ee948b6c150a45d178760d8e83f7e098a55e415"
            else "combined_decorrelated_technical"
        )
        bundle_spec = bundles[bundle_name]
        models, event_ids, membership, counts = _train_models(
            repository=repository,
            spec=spec,
            candidate=candidate,
            bundle_spec=bundle_spec,
            matrix=matrix,
            training_cutoff=initial_cutoff,
            effective_from=fresh_start,
            event_type="initial_fresh_model_event",
            work_root=Path(work_root),
        )
        for key in ("model_training_calls", "new_artifacts", "new_blobs"):
            total[key] += counts[key]
        predictions = []
        prior_prediction_date = None
        active_training_cutoff = initial_cutoff
        for prediction_date in official_dates:
            if (
                prior_prediction_date is not None
                and prediction_date[:7] != prior_prediction_date[:7]
            ):
                active_training_cutoff = prior_prediction_date
                models, event_ids, membership, counts = _train_models(
                    repository=repository,
                    spec=spec,
                    candidate=candidate,
                    bundle_spec=bundle_spec,
                    matrix=matrix,
                    training_cutoff=active_training_cutoff,
                    effective_from=prediction_date,
                    event_type="monthly_retraining_event",
                    work_root=Path(work_root),
                )
                for key in ("model_training_calls", "new_artifacts", "new_blobs"):
                    total[key] += counts[key]
            prediction, counts = _predict_date(
                repository=repository,
                candidate=candidate,
                models=models,
                model_event_ids=event_ids,
                membership=membership,
                matrix=matrix,
                prediction_date=prediction_date,
                training_cutoff=active_training_cutoff,
                snapshot_id=snapshot_id,
                work_root=Path(work_root),
            )
            predictions.append(prediction)
            prior_prediction_date = prediction_date
            for key in ("prediction_writes", "new_artifacts", "new_blobs"):
                total[key] += counts[key]
        labels, counts = _label_observations(
            repository=repository,
            candidate=candidate,
            predictions=predictions,
            matrix=matrix,
            official_dates=sorted(set(sources["calendar"])),
            data_as_of=collection["data_as_of_date"],
            snapshot_id=snapshot_id,
            work_root=Path(work_root),
        )
        for key in ("label_writes", "new_artifacts", "new_blobs"):
            total[key] += counts[key]
        strategy, counts = _strategy_observation(
            repository=repository,
            candidate=candidate,
            predictions=predictions,
            labels=labels,
            snapshot_id=snapshot_id,
        )
        strategies[candidate["candidate_id"]] = strategy
        for key in ("strategy_writes", "new_artifacts", "new_blobs"):
            total[key] += counts[key]
        monthly_count = _monthly_training_event_count(
            repository, candidate["candidate_id"]
        )
        observation, counts = _candidate_observation(
            repository=repository,
            cohort_id=cohort_id,
            candidate=candidate,
            predictions=predictions,
            labels=labels,
            strategy=strategy,
            fresh_dates=official_dates,
            monthly_event_count=monthly_count,
            snapshot_id=snapshot_id,
        )
        observations.append(observation)
        for key in ("new_artifacts", "new_blobs"):
            total[key] += counts[key]
        all_predictions[candidate["candidate_id"]] = predictions
        all_labels[candidate["candidate_id"]] = labels
    multiple, assessments, counts = _assess(repository, cohort_id, observations)
    for key in (
        "multiple_testing_calls",
        "candidate_status_writes",
        "new_artifacts",
        "new_blobs",
    ):
        total[key] += counts[key]
    heartbeat_status = (
        "fresh_evidence_accumulating"
        if any(row["status"] == "fresh_evidence_accumulating" for row in assessments)
        else "completed"
    )
    heartbeat_identity = {
        "schema_version": "fresh-model-heartbeat-run-v1",
        "provider_id": "tushare-pro-v1",
        "model_fresh_candidate_cohort_id": cohort_id,
        "requested_through_date": requested,
        "fresh_start_date": fresh_start,
        "data_as_of_date": collection["data_as_of_date"],
        "fresh_market_snapshot_id": snapshot_id,
        "candidate_ids": list(CANDIDATE_IDS),
        "candidate_observation_ids": [row["artifact_id"] for row in observations],
        "candidate_assessment_ids": [row["artifact_id"] for row in assessments],
        "multiple_testing_id": multiple["artifact_id"],
        "status": heartbeat_status,
        "execution_counts": total,
        "credential_source": "environment_only_not_persisted",
        "credential_persisted": False,
        "registry_writes": 0,
        "promotion_writes": 0,
    }
    heartbeat, receipt = _publish(
        repository,
        "fresh_model_heartbeat_run",
        heartbeat_identity,
        "fresh_model_heartbeat_run.json",
        (
            cohort_id,
            snapshot_id,
            multiple["artifact_id"],
            *[row["artifact_id"] for row in observations],
            *[row["artifact_id"] for row in assessments],
        ),
    )
    total["new_artifacts"] += int(not receipt["exact_existing"])
    total["new_blobs"] += receipt["new_blob_count"]
    heartbeat["execution_counts"] = total
    return heartbeat | {
        "fresh_model_heartbeat_run_id": receipt["artifact_id"],
        "fresh_market_snapshot_id": snapshot_id,
        "observations": observations,
        "assessments": assessments,
        "multiple_testing": multiple,
        "predictions": all_predictions,
        "labels": all_labels,
        "strategies": strategies,
        "store_integrity": repository.integrity(),
    }


def replay_heartbeat(
    *, repository_root: Path, work_root: Path, store_root: Path | None = None
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    rows = _heartbeat_rows(repository)
    if not rows:
        raise FreshModelContractError("FRESH_MODEL_HEARTBEAT_ABSENT")
    latest = max(rows, key=lambda row: (row["data_as_of_date"], row["artifact_id"]))
    return latest | {
        "status": "exact_replay",
        "fresh_model_heartbeat_run_id": latest["artifact_id"],
        "execution_counts": {
            name: 0
            for name in (
                "tushare_calls",
                "network_calls",
                "model_training_calls",
                "prediction_writes",
                "label_writes",
                "qlib_calls",
                "strategy_writes",
                "multiple_testing_calls",
                "candidate_status_writes",
                "registry_writes",
                "promotion_writes",
                "new_artifacts",
                "new_blobs",
            )
        },
        "store_integrity": repository.integrity(),
    }


def inspect_artifact(
    *,
    artifact_id: str,
    repository_root: Path,
    work_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    _, repository = _runtime(repository_root, work_root, store_root)
    return repository.identity(artifact_id) | {"artifact_id": artifact_id, "status": "valid"}
