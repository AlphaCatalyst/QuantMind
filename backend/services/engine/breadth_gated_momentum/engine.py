from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.low_frequency_momentum.engine import _source_matrix, build_signal_values
from backend.services.engine.low_frequency_momentum.artifact import validate_artifact as validate_low_frequency_artifact
from backend.services.engine.momentum_factor_iteration.features import compute_features
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes
from backend.services.engine.momentum_tail_alpha.artifact import validate_artifact as validate_tail_artifact
from backend.services.engine.momentum_tail_alpha.engine import recover_source
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle, load_authority_bundle
from backend.services.engine.tushare_cutover.canonical import hash_payload
from backend.services.engine.tushare_cutover.client import TushareClient

from .artifact import KINDS, publish_artifact, validate_artifact
from .protocol import (
    FRESH_START_DATE, MINIMUM_EVIDENCE, PATH_G, PATH_R, PATH_U, PERIODS,
    SOURCE_CLASSIFICATION_ID, SOURCE_DIAGNOSTIC_ID, SOURCE_SIGNAL_ARTIFACT_ID,
    TASK_ID, breadth_contract_identity, fresh_lock, gate_spec,
)


AUTHORITY_RELATIVE = "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json"


def _bundle(repository_root: Path, work_root: Path, store_root: Path | None) -> AuthorityBundle:
    return load_authority_bundle(authority_path=Path(repository_root) / AUTHORITY_RELATIVE,
                                 work_root=Path(work_root), store_root=store_root)


def _store(bundle: AuthorityBundle, artifact: dict[str, Any], kind: str,
           lineage: tuple[str, ...]) -> dict[str, Any]:
    field = KINDS[kind][0]
    existing = bundle.store.find_by_artifact_id(artifact[field])
    if existing is not None:
        if existing.artifact_kind != kind:
            raise RuntimeError("Artifact ID kind conflict")
        return {"artifact_kind": kind, "artifact_id": existing.artifact_id,
                "descriptor_id": existing.descriptor_id, "exact_existing": True,
                "new_blob_count": 0}
    receipt = bundle.store.import_artifact(kind, Path(artifact["path"]), artifact[field], lineage=lineage)
    return {"artifact_kind": kind, "artifact_id": receipt.artifact_id,
            "descriptor_id": receipt.descriptor_id, "exact_existing": receipt.exact_existing,
            "new_blob_count": receipt.new_blob_count}


def _materialize(bundle: AuthorityBundle, artifact_id: str, root: Path,
                 expected_kind: str | None = None) -> tuple[Path, dict[str, Any]]:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None or expected_kind is not None and descriptor.artifact_kind != expected_kind:
        raise RuntimeError(f"required artifact missing or wrong kind: {artifact_id}")
    target = Path(root) / descriptor.artifact_kind / artifact_id
    if target.exists():
        shutil.rmtree(target)
    bundle.store.materialize_artifact(descriptor.descriptor_id, target)
    identity = json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return target, identity


def _verify_sources(bundle: AuthorityBundle, root: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    _, signal, values, _ = recover_source(bundle, root / "signal")
    if signal["signal_artifact_id"] != SOURCE_SIGNAL_ARTIFACT_ID:
        raise RuntimeError("Signal D Artifact identity changed")
    diagnostic_root, diagnostic = _materialize(bundle, SOURCE_DIAGNOSTIC_ID, root / "diagnostic",
                                                "momentum_tail_alpha_diagnostic")
    validate_tail_artifact(diagnostic_root, SOURCE_DIAGNOSTIC_ID, "momentum_tail_alpha_diagnostic")
    _, classification = _materialize(bundle, SOURCE_CLASSIFICATION_ID, root / "classification",
                                      "momentum_tail_signal_classification")
    if diagnostic.get("classification_id") != SOURCE_CLASSIFICATION_ID:
        raise RuntimeError("R1-009 classification lineage mismatch")
    if classification.get("primary_classification") != "regime_specific_factor" or \
            classification.get("research_decision") != "retain_for_regime_specific_research":
        raise RuntimeError("R1-009 classification contract mismatch")
    matrix, _ = _source_matrix(bundle, root / "matrix")
    return signal, values, matrix


def preregister(*, repository_root: Path, work_root: Path,
                store_root: Path | None = None) -> dict[str, Any]:
    bundle = _bundle(repository_root, Path(work_root) / "authority", store_root)
    signal, _, _ = _verify_sources(bundle, Path(work_root) / "sources")
    regimes, contract = build_regimes(bundle.normalized, bundle.benchmark)
    if not {"narrow", "neutral", "broad"}.issubset(set(regimes.breadth_regime)):
        raise RuntimeError("formal Breadth Contract states unavailable")
    universe_id = bundle.authority["universe_100"]["universe_lock_id"]
    binding = breadth_contract_identity(contract,
        normalized_bars_id=bundle.authority["normalized_bars_id"], universe_id=universe_id)
    spec = gate_spec(breadth=binding, universe_id=universe_id)
    gate_artifact = publish_artifact(Path(work_root) / "domain", "breadth_momentum_gate_spec", spec,
                                     {"gate_spec.json": spec, "breadth_contract.json": binding})
    spec["gate_spec_id"] = gate_artifact["gate_spec_id"]
    gate_receipt = _store(bundle, gate_artifact, "breadth_momentum_gate_spec",
                          (SOURCE_SIGNAL_ARTIFACT_ID, SOURCE_DIAGNOSTIC_ID, SOURCE_CLASSIFICATION_ID,
                           bundle.authority["normalized_bars_id"], universe_id))
    lock = fresh_lock(spec, universe_id=universe_id)
    lock_artifact = publish_artifact(Path(work_root) / "domain", "breadth_gated_momentum_fresh_lock", lock,
                                     {"fresh_lock.json": lock, "gate_spec.json": spec})
    lock_receipt = _store(bundle, lock_artifact, "breadth_gated_momentum_fresh_lock",
                          (gate_artifact["gate_spec_id"], SOURCE_SIGNAL_ARTIFACT_ID))
    return {"status": "locked_awaiting_fresh_data", "signal_artifact_id": signal["signal_artifact_id"],
            "gate_spec_id": gate_artifact["gate_spec_id"], "fresh_lock_id": lock_artifact["fresh_lock_id"],
            "breadth_contract_id": binding["breadth_contract_id"],
            "breadth_dataset_id": binding["breadth_dataset_id"],
            "receipts": [gate_receipt, lock_receipt], "network_calls": 0,
            "registry_writes": 0, "promotion_writes": 0}


def _find_one(bundle: AuthorityBundle, kind: str, root: Path) -> tuple[Any, dict[str, Any]]:
    candidates = []
    for index, descriptor in enumerate(bundle.store.list_by_kind(kind)):
        target = root / str(index)
        if target.exists():
            shutil.rmtree(target)
        bundle.store.materialize_artifact(descriptor.descriptor_id, target)
        identity = json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]
        if identity.get("task_id") == TASK_ID:
            candidates.append((descriptor, identity))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one canonical {kind}, found {len(candidates)}")
    return candidates[0]


def _gate_series(bundle: AuthorityBundle) -> tuple[pd.DataFrame, dict[str, Any]]:
    regimes, contract = build_regimes(bundle.normalized, bundle.benchmark)
    regimes = regimes.copy()
    regimes["gate_on"] = regimes["breadth_regime"].eq("narrow")
    regimes["breadth_gate_state"] = regimes["breadth_regime"].replace({
        "narrow": "narrow_or_weak", "neutral": "neutral_breadth", "broad": "broad_strength",
    })
    return regimes, contract


def _cost(buy_fraction: float, sell_fraction: float, capital: float = 1_000_000.0) -> float:
    buy_value, sell_value = buy_fraction * capital, sell_fraction * capital
    commission = (max(5.0, buy_value * .00025) if buy_value else 0.0) + \
                 (max(5.0, sell_value * .00025) if sell_value else 0.0)
    stamp = sell_value * .0005
    transfer = (max(.01, buy_value * .00001) if buy_value else 0.0) + \
               (max(.01, sell_value * .00001) if sell_value else 0.0)
    impact = (buy_value + sell_value) * .0005
    return commission + stamp + transfer + impact


def _portfolio_path(values: pd.DataFrame, normalized: pd.DataFrame, benchmark: pd.DataFrame,
                    regimes: pd.DataFrame, *, gated: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = normalized[["symbol", "trade_date", "adjusted_open", "tradable"]].copy()
    bars["trade_date"] = pd.to_datetime(bars.trade_date)
    bars = bars.sort_values(["symbol", "trade_date"])
    bars["asset_return"] = bars.groupby("symbol")["adjusted_open"].shift(-1) / bars.adjusted_open - 1.0
    score = values.copy(); score["trade_date"] = pd.to_datetime(score.trade_date)
    score_map = {(d, s): float(v) for s, d, v in score[["symbol", "trade_date", "factor_value"]].itertuples(index=False, name=None)
                 if pd.notna(v)}
    return_map = {(d, s): float(v) for s, d, v in bars[["symbol", "trade_date", "asset_return"]].itertuples(index=False, name=None)
                  if pd.notna(v)}
    trade_map = {(d, s): bool(v) for s, d, v in bars[["symbol", "trade_date", "tradable"]].itertuples(index=False, name=None)}
    dates = sorted(set(score.trade_date.unique()) & set(bars.trade_date.unique()))
    market = benchmark.copy(); market["trade_date"] = pd.to_datetime(market.trade_date)
    market = market.sort_values("trade_date").drop_duplicates("trade_date")
    close = pd.to_numeric(market["close"], errors="coerce")
    market["benchmark_return"] = close.shift(-1) / close - 1.0
    bench = dict(zip(market.trade_date, market.benchmark_return))
    gate = dict(zip(pd.to_datetime(regimes.trade_date), regimes.gate_on))
    holdings: set[str] = set(); rows, position_rows = [], []
    interval_gate = False
    for ordinal, date in enumerate(dates[:-1]):
        rebalance = ordinal % 10 == 0
        turnover = cost = 0.0
        if rebalance:
            interval_gate = bool(gate.get(date, False))
            previous = set(holdings)
            if gated and not interval_gate:
                holdings = set()
            else:
                signal_date = dates[max(0, ordinal - 1)]
                ranked = sorted(((score_map.get((signal_date, symbol)), symbol)
                                 for symbol in bars.loc[bars.trade_date.eq(date), "symbol"]
                                 if trade_map.get((date, symbol), False) and score_map.get((signal_date, symbol)) is not None),
                                reverse=True)
                top = [symbol for _, symbol in ranked[:20]]
                retained = [symbol for _, symbol in ranked if symbol in previous][:15]
                holdings = set((retained + [symbol for symbol in top if symbol not in retained])[:20])
            buys, sells = holdings - previous, previous - holdings
            buy_fraction = len(buys) / max(20, len(holdings))
            sell_fraction = len(sells) / max(20, len(previous))
            turnover = buy_fraction + sell_fraction
            cost = _cost(buy_fraction, sell_fraction)
        returns = [return_map[(date, symbol)] for symbol in holdings if (date, symbol) in return_map]
        gross = float(np.mean(returns)) if returns else 0.0
        net = gross - cost / 1_000_000.0
        benchmark_return = float(bench.get(date, np.nan))
        rows.append({"trade_date": date, "path": "G" if gated else "U", "rebalance": rebalance,
                     "gate_on": interval_gate if gated else bool(gate.get(date, False)),
                     "holding_count": len(holdings), "gross_return": gross, "net_return": net,
                     "benchmark_return": benchmark_return, "turnover": turnover,
                     "transaction_cost": cost})
        for symbol in holdings:
            position_rows.append({"trade_date": date, "path": "G" if gated else "U", "symbol": symbol,
                                  "gate_on": interval_gate if gated else bool(gate.get(date, False)),
                                  "asset_return": return_map.get((date, symbol))})
    return pd.DataFrame(rows), pd.DataFrame(position_rows)


def _path_r(path_g: pd.DataFrame) -> pd.DataFrame:
    result = path_g[["trade_date", "rebalance", "gate_on", "benchmark_return"]].copy()
    result["path"] = "R"; result["holding_count"] = result.gate_on.astype(int)
    result["gross_return"] = result.benchmark_return.where(result.gate_on, 0.0).fillna(0.0)
    result["net_return"] = result.gross_return; result["turnover"] = 0.0
    result["transaction_cost"] = 0.0
    return result[["trade_date", "path", "rebalance", "gate_on", "holding_count", "gross_return",
                   "net_return", "benchmark_return", "turnover", "transaction_cost"]]


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _metrics(frame: pd.DataFrame) -> dict[str, Any]:
    net = pd.to_numeric(frame.net_return, errors="coerce").fillna(0.0)
    gross = pd.to_numeric(frame.gross_return, errors="coerce").fillna(0.0)
    benchmark = pd.to_numeric(frame.benchmark_return, errors="coerce").fillna(0.0)
    nav = (1 + net).cumprod(); drawdown = nav / nav.cummax() - 1.0
    std = net.std(ddof=0)
    return {"active_trading_days": int((frame.holding_count > 0).sum()),
            "active_rebalance_dates": int((frame.rebalance & (frame.holding_count > 0)).sum()),
            "exposure_ratio": float((frame.holding_count > 0).mean()) if len(frame) else 0.0,
            "gross_return": float((1 + gross).prod() - 1), "net_return": float(nav.iloc[-1] - 1) if len(nav) else 0.0,
            "csi300_return": float((1 + benchmark).prod() - 1),
            "csi300_excess": float((1 + net).prod() - (1 + benchmark).prod()),
            "maximum_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
            "sharpe": None if not std else float(net.mean() / std * np.sqrt(252)),
            "turnover": float(frame.turnover.sum()), "transaction_cost": float(frame.transaction_cost.sum())}


def _episodes(regimes: pd.DataFrame) -> pd.DataFrame:
    frame = regimes[["trade_date", "gate_on"]].copy().sort_values("trade_date")
    group = frame.gate_on.ne(frame.gate_on.shift()).cumsum()
    rows = []
    for _, values in frame[frame.gate_on].groupby(group[frame.gate_on]):
        rows.append({"start_date": values.trade_date.min(), "end_date": values.trade_date.max(),
                     "length": len(values)})
    return pd.DataFrame(rows, columns=["start_date", "end_date", "length"])


def _rankic(values: pd.DataFrame, normalized: pd.DataFrame) -> pd.DataFrame:
    bars = normalized[["symbol", "trade_date", "adjusted_open"]].sort_values(["symbol", "trade_date"]).copy()
    bars["future_return"] = bars.groupby("symbol").adjusted_open.shift(-1) / bars.adjusted_open - 1
    frame = values.merge(bars[["symbol", "trade_date", "future_return"]], on=["symbol", "trade_date"], how="left")
    def summarize(group: pd.DataFrame) -> pd.Series:
        valid = group.dropna(subset=["factor_value", "future_return"])
        if valid.empty:
            return pd.Series({"rankic": np.nan, "q10_universe": np.nan})
        count = max(1, int(np.ceil(len(valid) * .1)))
        top = valid.nlargest(count, "factor_value")
        return pd.Series({"rankic": valid.factor_value.corr(valid.future_return, method="spearman"),
                          "q10_universe": top.future_return.mean() - valid.future_return.mean()})
    return frame.groupby("trade_date").apply(summarize, include_groups=False).reset_index()


def _historical_outputs(bundle: AuthorityBundle, values: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    regimes, contract = _gate_series(bundle)
    u, up = _portfolio_path(values, bundle.normalized, bundle.benchmark, regimes, gated=False)
    g, gp = _portfolio_path(values, bundle.normalized, bundle.benchmark, regimes, gated=True)
    r = _path_r(g)
    paths = pd.concat([u, g, r], ignore_index=True)
    rankic = _rankic(values, bundle.normalized).merge(regimes[["trade_date", "gate_on"]], on="trade_date", how="left")
    summary: dict[str, Any] = {"periods": {}, "retrospective": True, "contaminated": True,
                               "not_used_for_gate_selection": True, "not_fresh_evidence": True}
    for period, (start, end) in PERIODS.items():
        period_paths = paths[paths.trade_date.between(start, end)]
        metrics = {name: _metrics(period_paths[period_paths.path.eq(name)]) for name in ("U", "G", "R")}
        metrics["G"]["conditional_selection_alpha"] = metrics["G"]["net_return"] - metrics["R"]["net_return"]
        active = rankic[rankic.trade_date.between(start, end) & rankic.gate_on.fillna(False)]
        active_ic = active.rankic.dropna()
        metrics["G"]["active_period_mean_rankic"] = _finite(active_ic.mean())
        metrics["G"]["active_period_hit_rate"] = _finite((active_ic > 0).mean())
        metrics["G"]["active_period_q10_universe"] = _finite(active.q10_universe.mean())
        summary["periods"][period] = metrics
    episodes = _episodes(regimes)
    gate_days = int(regimes.gate_on.sum())
    summary["gate_statistics"] = {"gate_on_day_count": gate_days,
        "gate_on_ratio": float(regimes.gate_on.mean()), "gate_episode_count": len(episodes),
        "episode_length_mean": _finite(episodes.length.mean()), "episode_length_median": _finite(episodes.length.median()),
        "episode_length_max": None if episodes.empty else int(episodes.length.max())}
    u_state = u.groupby("gate_on").net_return.apply(lambda x: float((1 + x).prod() - 1)).to_dict()
    top_returns = pd.concat([up, gp], ignore_index=True).groupby(["path", "gate_on"]).asset_return.mean().reset_index()
    summary["gate_contribution"] = {"always_on_gate_on_return": u_state.get(True),
        "always_on_gate_off_return": u_state.get(False), "top20_holding_returns_by_gate": top_returns.to_dict("records")}
    summary["breadth_contract"] = contract
    return paths, episodes, summary


def build_historical(*, repository_root: Path, work_root: Path,
                     store_root: Path | None = None) -> dict[str, Any]:
    bundle = _bundle(repository_root, Path(work_root) / "authority", store_root)
    gate_descriptor, gate_identity = _find_one(bundle, "breadth_momentum_gate_spec", Path(work_root) / "gate")
    _, values, _ = _verify_sources(bundle, Path(work_root) / "sources")
    paths, episodes, decomposition = _historical_outputs(bundle, values)
    identity = {"schema_version": "breadth-gated-momentum-historical-diagnostic-v1", "computation_revision": 2,
        "provider_id": "tushare-pro-v1", "task_id": TASK_ID,
        "gate_spec_id": gate_descriptor.artifact_id, "signal_artifact_id": SOURCE_SIGNAL_ARTIFACT_ID,
        "periods": PERIODS, "paths": {"U": PATH_U, "G": PATH_G, "R": PATH_R},
        "retrospective": True, "contaminated": True, "not_fresh_evidence": True,
        "execution_counts": {"agent_calls": 0, "factor_optimization_calls": 0,
            "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
            "network_calls": 0, "qlib_calls": 0}, "registry_writes": 0, "promotion_writes": 0}
    artifact = publish_artifact(Path(work_root) / "domain", "breadth_gated_momentum_historical_diagnostic",
        identity, {"historical_paths.parquet": paths, "historical_gate_episodes.parquet": episodes,
                   "historical_decomposition.json": decomposition, "gate_spec.json": gate_identity})
    receipt = _store(bundle, artifact, "breadth_gated_momentum_historical_diagnostic",
                     (gate_descriptor.artifact_id, SOURCE_SIGNAL_ARTIFACT_ID, SOURCE_DIAGNOSTIC_ID))
    return {"status": "completed", "historical_diagnostic_id": artifact["historical_diagnostic_id"],
            "metrics": decomposition, "receipt": receipt, "registry_writes": 0, "promotion_writes": 0}


def token_status() -> dict[str, Any]:
    return {"provider_id": "tushare-pro-v1", "credential_source": "TUSHARE_TOKEN environment only",
            "credential_present": bool(os.environ.get("TUSHARE_TOKEN")), "credential_persisted": False}


def _universe_500(bundle: AuthorityBundle, root: Path) -> set[str]:
    artifact_id = bundle.authority["universe_500"]["universe_lock_id"]
    path, _ = _materialize(bundle, artifact_id, root, "tushare_500_universe_lock")
    return set(pd.read_parquet(path / "universe.parquet").ts_code.astype(str))


def fetch_incremental(*, repository_root: Path, work_root: Path,
                      store_root: Path | None = None, end_date: str | None = None,
                      client: TushareClient | None = None) -> dict[str, Any]:
    bundle = _bundle(repository_root, Path(work_root) / "authority", store_root)
    gate, _ = _find_one(bundle, "breadth_momentum_gate_spec", Path(work_root) / "gate")
    lock, lock_identity = _find_one(bundle, "breadth_gated_momentum_fresh_lock", Path(work_root) / "lock")
    if lock_identity["gate_spec_id"] != gate.artifact_id:
        raise RuntimeError("Fresh Lock does not bind canonical Gate Spec")
    if not os.environ.get("TUSHARE_TOKEN") and client is None:
        return {"status": "blocked_token_absent", "network_calls": 0, "fresh_lock_id": lock.artifact_id}
    api = client or TushareClient()
    start = FRESH_START_DATE.replace("-", "")
    end = (end_date or pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d")).replace("-", "")
    calendar = api.query("trade_cal", fields=("exchange", "cal_date", "is_open", "pretrade_date"),
                         exchange="SSE", start_date=start, end_date=end)
    calls = 1
    open_dates = sorted(row["cal_date"] for row in calendar.rows if int(row["is_open"]) == 1)
    symbols = _universe_500(bundle, Path(work_root) / "universe")
    endpoint_fields = {
        "daily": ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"),
        "adj_factor": ("ts_code", "trade_date", "adj_factor"),
        "daily_basic": ("ts_code", "trade_date", "turnover_rate", "circ_mv", "total_mv"),
    }
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in endpoint_fields}
    checkpoint = Path(work_root) / "checkpoints"; checkpoint.mkdir(parents=True, exist_ok=True)
    for trade_date in open_dates:
        for name, fields in endpoint_fields.items():
            response = api.query(name, fields=fields, trade_date=trade_date); calls += 1
            selected = [row for row in response.rows if row.get("ts_code") in symbols]
            rows[name].extend(selected)
        (checkpoint / f"{trade_date}.done").write_text("complete\n", encoding="utf-8")
    benchmark = api.query("index_daily", fields=("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"),
                          ts_code="000300.SH", start_date=start, end_date=end); calls += 1
    frames = {name: pd.DataFrame(value).drop_duplicates(["ts_code", "trade_date"], keep="last")
              for name, value in rows.items()}
    cal_frame = pd.DataFrame(calendar.rows).drop_duplicates(["exchange", "cal_date"], keep="last")
    benchmark_frame = pd.DataFrame(benchmark.rows).drop_duplicates(["ts_code", "trade_date"], keep="last")
    quality = {"duplicate_keys": {name: int(frame.duplicated(["ts_code", "trade_date"]).sum()) for name, frame in frames.items()},
               "missing_adj_factor": 0 if frames["adj_factor"].empty else int(frames["adj_factor"].adj_factor.isna().sum()),
               "symbol_mapping_valid": all(code.endswith((".SH", ".SZ", ".BJ")) for code in set(frames["daily"].get("ts_code", []))),
               "open_session_count": len(open_dates), "checkpoint_count": len(open_dates)}
    identity = {"schema_version": "tushare-incremental-market-snapshot-v1", "provider_id": "tushare-pro-v1",
        "task_id": TASK_ID, "fresh_lock_id": lock.artifact_id, "gate_spec_id": gate.artifact_id,
        "parent_normalized_bars_id": bundle.authority["normalized_bars_id"],
        "universe_500_id": bundle.authority["universe_500"]["universe_lock_id"],
        "start_date": FRESH_START_DATE, "end_date": None if not open_dates else pd.Timestamp(open_dates[-1]).strftime("%Y-%m-%d"),
        "endpoints": ["daily", "adj_factor", "daily_basic", "trade_cal", "index_daily"],
        "incremental_only": True, "network_calls": calls, "quality": quality,
        "credential_source": "environment_only_not_persisted", "revision_policy": "immutable_first_observation",
        "registry_writes": 0, "promotion_writes": 0}
    files = {"daily.parquet": frames["daily"], "adj_factor.parquet": frames["adj_factor"],
             "daily_basic.parquet": frames["daily_basic"], "trade_calendar.parquet": cal_frame,
             "index_daily.parquet": benchmark_frame, "incremental_data_manifest.json": identity | {"quality": quality}}
    artifact = publish_artifact(Path(work_root) / "domain", "tushare_incremental_market_snapshot", identity, files)
    receipt = _store(bundle, artifact, "tushare_incremental_market_snapshot", (lock.artifact_id, gate.artifact_id,
        bundle.authority["normalized_bars_id"], bundle.authority["universe_500"]["universe_lock_id"]))
    return {"status": "completed", "incremental_snapshot_id": artifact["incremental_snapshot_id"],
            "network_calls": calls, "quality": quality, "receipt": receipt}


def _incremental_frames(bundle: AuthorityBundle, descriptor: Any, work_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    root, _ = _materialize(bundle, descriptor.artifact_id, work_root, "tushare_incremental_market_snapshot")
    daily = pd.read_parquet(root / "daily.parquet"); adj = pd.read_parquet(root / "adj_factor.parquet")
    basic = pd.read_parquet(root / "daily_basic.parquet")
    if daily.empty:
        return bundle.normalized.copy(), bundle.benchmark.copy()
    frame = daily.merge(adj, on=["ts_code", "trade_date"], validate="one_to_one").merge(
        basic, on=["ts_code", "trade_date"], how="left", validate="one_to_one")
    for column in ("open", "high", "low", "close", "pre_close", "vol", "amount", "adj_factor"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["symbol"] = frame.ts_code.map(lambda code: ("SH" if code.endswith(".SH") else "SZ") + code.split(".")[0])
    frame["trade_date"] = pd.to_datetime(frame.trade_date, format="%Y%m%d")
    for column in ("open", "high", "low", "close"):
        frame[f"adjusted_{column}"] = frame[column] * frame.adj_factor
    frame["tradable"] = frame[["open", "close", "vol"]].notna().all(axis=1) & frame.vol.gt(0)
    historical = bundle.normalized.copy()
    historical["trade_date"] = pd.to_datetime(historical.trade_date)
    historical = historical[historical.trade_date < pd.Timestamp(FRESH_START_DATE)]
    normalized = pd.concat([historical, frame], ignore_index=True).drop_duplicates(["symbol", "trade_date"], keep="last")
    market = pd.read_parquet(root / "index_daily.parquet"); market["trade_date"] = pd.to_datetime(market.trade_date, format="%Y%m%d")
    old_market = bundle.benchmark.copy()
    old_market["trade_date"] = pd.to_datetime(old_market.trade_date)
    old_market = old_market[old_market.trade_date < pd.Timestamp(FRESH_START_DATE)]
    benchmark = pd.concat([old_market, market], ignore_index=True).drop_duplicates("trade_date", keep="last")
    return normalized.sort_values(["symbol", "trade_date"]), benchmark.sort_values("trade_date")


def build_incremental_features(*, repository_root: Path, work_root: Path,
                               store_root: Path | None = None) -> dict[str, Any]:
    bundle = _bundle(repository_root, Path(work_root) / "authority", store_root)
    snapshots = bundle.store.list_by_kind("tushare_incremental_market_snapshot")
    if not snapshots:
        raise RuntimeError("incremental snapshot is absent")
    descriptor = snapshots[-1]
    normalized, benchmark = _incremental_frames(bundle, descriptor, Path(work_root) / "snapshot")
    features = compute_features(normalized, benchmark)[["symbol", "trade_date", "momentum_120_20", "residual_momentum_60"]]
    universe = set(bundle.matrix.symbol.unique()); features = features[features.symbol.isin(universe)]
    values = build_signal_values(features, "residual_absolute_momentum_consensus")
    regimes, contract = build_regimes(normalized[normalized.symbol.isin(universe)], benchmark)
    fresh = values[values.trade_date >= pd.Timestamp(FRESH_START_DATE)].copy()
    fresh_regimes = regimes[regimes.trade_date >= pd.Timestamp(FRESH_START_DATE)].copy()
    target = Path(work_root) / "incremental-features"; target.mkdir(parents=True, exist_ok=True)
    fresh.to_parquet(target / "signal_values.parquet", index=False)
    fresh_regimes.to_parquet(target / "breadth_regimes.parquet", index=False)
    (target / "contract.json").write_text(json.dumps(contract, sort_keys=True), encoding="utf-8")
    return {"status": "completed", "incremental_snapshot_id": descriptor.artifact_id,
            "feature_names": ["momentum_120_20", "residual_momentum_60"],
            "warmup_used": True, "warmup_counted_as_fresh": False,
            "fresh_row_count": len(fresh), "fresh_date_count": int(fresh.trade_date.nunique()),
            "output_root": str(target), "new_feature_count": 0}


def classify_fresh(counts: dict[str, int], metrics: dict[str, Any]) -> str:
    if any(counts[name] < required for name, required in MINIMUM_EVIDENCE.items()):
        return "fresh_evidence_accumulating"
    if (metrics["conditional_selection_alpha"] > 0 and metrics["gate_on_rankic"] > 0 and
            metrics["gate_on_q10_universe"] > 0 and
            abs(metrics["path_g_maximum_drawdown"]) <= abs(metrics["path_u_maximum_drawdown"])):
        return "fresh_regime_overlay_supported"
    if metrics["conditional_selection_alpha"] <= 0 and metrics["gate_on_q10_universe"] <= 0:
        return "fresh_regime_overlay_rejected"
    return "fresh_regime_overlay_inconclusive"


def run_fresh(*, repository_root: Path, work_root: Path,
              store_root: Path | None = None) -> dict[str, Any]:
    bundle = _bundle(repository_root, Path(work_root) / "authority", store_root)
    gate, _ = _find_one(bundle, "breadth_momentum_gate_spec", Path(work_root) / "gate")
    lock, _ = _find_one(bundle, "breadth_gated_momentum_fresh_lock", Path(work_root) / "lock")
    snapshots = bundle.store.list_by_kind("tushare_incremental_market_snapshot")
    if not snapshots:
        return {"status": "historical_mechanism_only", "reason": "incremental snapshot absent"}
    snapshot = snapshots[-1]
    normalized, benchmark = _incremental_frames(bundle, snapshot, Path(work_root) / "snapshot")
    universe = set(bundle.matrix.symbol.unique())
    features = compute_features(normalized[normalized.symbol.isin(universe)], benchmark)
    values = build_signal_values(features, "residual_absolute_momentum_consensus")
    regimes, _ = build_regimes(normalized[normalized.symbol.isin(universe)], benchmark)
    regimes["gate_on"] = regimes.breadth_regime.eq("narrow")
    u, _ = _portfolio_path(values, normalized[normalized.symbol.isin(universe)], benchmark, regimes, gated=False)
    g, _ = _portfolio_path(values, normalized[normalized.symbol.isin(universe)], benchmark, regimes, gated=True)
    r = _path_r(g)
    paths = pd.concat([u, g, r], ignore_index=True)
    paths = paths[paths.trade_date >= pd.Timestamp(FRESH_START_DATE)].copy()
    fresh_regimes = regimes[regimes.trade_date >= pd.Timestamp(FRESH_START_DATE)].copy()
    observations = paths.copy(); rebalances = observations[observations.rebalance].copy()
    um, gm, rm = (_metrics(paths[paths.path.eq(name)]) for name in ("U", "G", "R"))
    ranks = _rankic(values, normalized).merge(regimes[["trade_date", "gate_on"]], on="trade_date", how="left")
    gate_daily = ranks[(ranks.trade_date >= FRESH_START_DATE) & ranks.gate_on.fillna(False)]
    gate_ranks = gate_daily.rankic.dropna()
    counts = {"fresh_trading_days": int(observations.trade_date.nunique()),
        "fresh_rebalance_dates": int(rebalances.trade_date.nunique()),
        "gate_on_trading_days": int(fresh_regimes.gate_on.sum()),
        "gate_on_rebalance_dates": int(rebalances[rebalances.path.eq("G") & rebalances.gate_on].trade_date.nunique()),
        "completed_10_day_holding_windows": max(0, int(observations.trade_date.nunique() // 10))}
    metrics = {"path_u_net_return": um["net_return"], "path_g_net_return": gm["net_return"],
        "path_r_return": rm["net_return"], "conditional_selection_alpha": gm["net_return"] - rm["net_return"],
        "path_g_maximum_drawdown": gm["maximum_drawdown"], "path_u_maximum_drawdown": um["maximum_drawdown"],
        "path_g_turnover": gm["turnover"], "path_g_transaction_cost": gm["transaction_cost"],
        "gate_on_rankic": _finite(gate_ranks.mean()), "gate_on_q10_universe": _finite(gate_daily.q10_universe.mean()),
        "gate_on_hit_rate": _finite((gate_ranks > 0).mean())}
    safe_metrics = metrics | {"gate_on_rankic": metrics["gate_on_rankic"] or 0.0,
                              "gate_on_q10_universe": metrics["gate_on_q10_universe"] or 0.0}
    status = classify_fresh(counts, safe_metrics)
    observation_identity = {"schema_version": "breadth-gated-momentum-fresh-observation-v1", "computation_revision": 2,
        "provider_id": "tushare-pro-v1", "task_id": TASK_ID, "fresh_lock_id": lock.artifact_id,
        "gate_spec_id": gate.artifact_id, "incremental_snapshot_id": snapshot.artifact_id,
        "signal_artifact_id": SOURCE_SIGNAL_ARTIFACT_ID, "fresh_start_date": FRESH_START_DATE,
        "no_backfill": True, "observation_counts": counts, "metrics": metrics,
        "network_calls": 0, "qlib_calls": 0, "registry_writes": 0, "promotion_writes": 0}
    observation = publish_artifact(Path(work_root) / "domain", "breadth_gated_momentum_fresh_observation",
        observation_identity, {"fresh_daily_observations.parquet": observations,
                               "fresh_rebalance_observations.parquet": rebalances,
                               "fresh_metrics.json": metrics})
    observation_receipt = _store(bundle, observation, "breadth_gated_momentum_fresh_observation",
        (lock.artifact_id, gate.artifact_id, snapshot.artifact_id, SOURCE_SIGNAL_ARTIFACT_ID))
    assessment_identity = {"schema_version": "breadth-gated-momentum-fresh-assessment-v1", "computation_revision": 2,
        "provider_id": "tushare-pro-v1", "task_id": TASK_ID,
        "fresh_observation_id": observation["fresh_observation_id"], "fresh_lock_id": lock.artifact_id,
        "fresh_start_date": FRESH_START_DATE, "fresh_status": status,
        "minimum_evidence_policy": MINIMUM_EVIDENCE, "observation_counts": counts,
        "metrics": metrics, "minimum_evidence_met": status != "fresh_evidence_accumulating",
        "promotion_authorized": False, "registry_writes": 0, "promotion_writes": 0}
    assessment = publish_artifact(Path(work_root) / "domain", "breadth_gated_momentum_fresh_assessment",
        assessment_identity, {"fresh_status.json": assessment_identity, "fresh_metrics.json": metrics})
    assessment_receipt = _store(bundle, assessment, "breadth_gated_momentum_fresh_assessment",
        (observation["fresh_observation_id"], lock.artifact_id))
    return {"status": status, "fresh_observation_id": observation["fresh_observation_id"],
            "fresh_assessment_id": assessment["fresh_assessment_id"], "counts": counts,
            "metrics": metrics, "receipts": [observation_receipt, assessment_receipt],
            "registry_writes": 0, "promotion_writes": 0}


def replay(*, repository_root: Path, work_root: Path,
           store_root: Path | None = None) -> dict[str, Any]:
    bundle = _bundle(repository_root, Path(work_root) / "authority", store_root)
    kinds = list(KINDS)
    recovered = []
    for kind in kinds:
        descriptors = bundle.store.list_by_kind(kind)
        if not descriptors:
            continue
        ranked = []
        for index, candidate in enumerate(descriptors):
            target, identity = _materialize(bundle, candidate.artifact_id,
                                             Path(work_root) / "selection" / kind / str(index), kind)
            validate_artifact(target, candidate.artifact_id, kind)
            ranked.append((int(identity.get("computation_revision", 1)), candidate.artifact_id, candidate))
        descriptor = max(ranked, key=lambda item: (item[0], item[1]))[2]
        target, _ = _materialize(bundle, descriptor.artifact_id, Path(work_root) / "cold", kind)
        validate_artifact(target, descriptor.artifact_id, kind)
        recovered.append(descriptor.artifact_id)
    if len(recovered) < 3:
        raise RuntimeError("breadth-gated momentum study is incomplete")
    signal_root, _ = _materialize(bundle, SOURCE_SIGNAL_ARTIFACT_ID,
                                  Path(work_root) / "cold-source",
                                  "low_frequency_momentum_signal_spec")
    validate_low_frequency_artifact(signal_root, SOURCE_SIGNAL_ARTIFACT_ID,
                                    "low_frequency_momentum_signal_spec")
    recovered.append(SOURCE_SIGNAL_ARTIFACT_ID)
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "recovered_artifact_count": len(recovered), "artifact_ids": recovered,
        "agent_calls": 0, "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
        "combined_optimization_calls": 0, "tushare_calls": 0, "qlib_calls": 0,
        "network_calls": 0, "new_artifacts": 0, "new_blobs": 0,
        "registry_writes": 0, "promotion_writes": 0, "store_integrity": integrity.status,
        "missing": len(integrity.issues), "unreferenced": len(integrity.unreferenced_blobs)}


def validate_study(*, repository_root: Path, work_root: Path,
                   store_root: Path | None = None) -> dict[str, Any]:
    result = replay(repository_root=repository_root, work_root=work_root, store_root=store_root)
    result["inventory_id"] = publish_inventory(_bundle(repository_root, Path(work_root) / "inventory-authority", store_root).store).inventory_id
    return result
