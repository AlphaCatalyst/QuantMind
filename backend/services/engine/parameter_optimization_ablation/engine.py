from __future__ import annotations

import itertools
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.artifact_store.inventory import publish_inventory
from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.skip_recent_momentum.artifact import validate_artifact as validate_source
from backend.services.engine.skip_recent_momentum.engine import _source_dataset
from backend.services.engine.tushare_agent_experiment.data import AuthorityBundle
from backend.services.engine.tushare_agent_experiment.evaluation import FormalQlibRunner, equal_weight_signal
from backend.services.engine.tushare_cutover.canonical import hash_file, hash_payload

from .artifact import publish_artifact, validate_artifact
from .metrics import (
    classify_overfit, clean_qlib, gains, ordering_key, parameter_consistency,
    plateau_analysis, rank_stability, rankic_metrics, select_trial, selection_summary,
)


def _load_ablation_bundle(*, authority_path: Path, work_root: Path,
                          store_root: Path | None = None, market_data: bool = True) -> AuthorityBundle:
    """Load only authority columns consumed by this retrospective diagnostic."""
    authority = json.loads(Path(authority_path).read_text(encoding="utf-8"))
    if authority.get("provider_id") != "tushare-pro-v1" or authority.get("authority_status") != "active":
        raise RuntimeError("Tushare authority is not active")
    legacy = authority.get("legacy_provider", {})
    if legacy.get("runtime_read_allowed") is not False or legacy.get("authority_status") != "retired_and_purged":
        raise RuntimeError("LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN")
    store = FileSystemResearchArtifactStore(resolve_config(store_root)); store.validate_format()

    def materialize(artifact_id: str, expected_kind: str) -> Path:
        descriptor = store.find_by_artifact_id(artifact_id)
        if descriptor is None or descriptor.artifact_kind != expected_kind:
            raise RuntimeError(f"required Tushare Artifact missing or wrong kind: {artifact_id}")
        destination = Path(work_root) / expected_kind / artifact_id
        if destination.exists():
            shutil.rmtree(destination)
        store.materialize_artifact(descriptor.descriptor_id, destination)
        return destination

    empty = pd.DataFrame()
    if not market_data:
        return AuthorityBundle(authority, empty, empty, empty, empty, Path(), {}, {}, {}, store)
    label_path = materialize(authority["label_dataset_id"], "tushare_label_dataset")
    normalized_path = materialize(authority["normalized_bars_id"], "tushare_normalized_bars")
    qlib_path = materialize(authority["qlib_view_id"], "tushare_100_qlib_view")
    labels = pd.read_parquet(label_path / "labels.parquet",
                             columns=["symbol", "trade_date", "raw_label", "model_label"])
    labels["trade_date"] = pd.to_datetime(labels["trade_date"])
    normalized = pd.read_parquet(normalized_path / "normalized_bars.parquet",
                                 columns=["symbol", "trade_date", "adjusted_close"])
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"])
    return AuthorityBundle(authority, empty, labels, normalized, empty, qlib_path,
                           {}, {}, {"label": label_path, "normalized": normalized_path,
                                    "qlib": qlib_path}, store)
from .protocol import (
    ARTIFACT_FILES, CANDIDATE_A, CANDIDATE_B, COMBINED_MODES, DATASET_ID,
    ENSEMBLE_ID, FACTOR_MODES, FOLDS, FORMAL_STRATEGY, LIFECYCLE_POLICY,
    ORDERING, PERIODS, SOURCE_ASSESSMENT_ID, SOURCE_EXPERIMENT_ID, STRATEGY_MODES, TASK_ID,
    YEAR_PERIODS,
)


def _restore(bundle: AuthorityBundle, artifact_id: str, destination: Path,
             expected_kind: str | None = None) -> tuple[Path, dict[str, Any], str]:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise RuntimeError(f"required Store artifact is missing: {artifact_id}")
    if expected_kind is not None and descriptor.artifact_kind != expected_kind:
        raise RuntimeError(f"Store artifact kind mismatch: {artifact_id}")
    if destination.exists():
        shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    if descriptor.artifact_kind in {
        "skip_recent_momentum_candidate_lock", "factor_template_definition",
        "research_proposal", "factor_optimization_trial_detail",
    }:
        validate_source(destination, artifact_id, descriptor.artifact_kind)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    return destination, manifest["identity"], descriptor.artifact_kind


def _candidate_inputs(bundle: AuthorityBundle, root: Path) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    raw_locks = {}
    for name, lock_id in (("candidate_a", CANDIDATE_A), ("candidate_b", CANDIDATE_B)):
        _, raw_locks[name], _ = _restore(bundle, lock_id, root / "locks" / name,
                                         "skip_recent_momentum_candidate_lock")
    required_templates = {lock["factor_template_id"] for lock in raw_locks.values()}
    template_by_factor: dict[str, tuple[str, dict[str, Any]]] = {}
    for index, descriptor in enumerate(bundle.store.list_by_kind("factor_template_definition")):
        _, identity, _ = _restore(bundle, descriptor.artifact_id, root / "templates" / str(index))
        if identity["factor_template_id"] in required_templates:
            template_by_factor[identity["factor_template_id"]] = (descriptor.artifact_id, identity)
    required_definitions = {item[0] for item in template_by_factor.values()}
    trial_by_factor: dict[str, list[dict[str, Any]]] = {}
    relevant_trials = [descriptor for descriptor in bundle.store.list_by_kind("factor_optimization_trial_detail")
                       if required_definitions.intersection(descriptor.lineage)]
    for index, descriptor in enumerate(relevant_trials):
        path, identity, _ = _restore(bundle, descriptor.artifact_id, root / "trials" / str(index))
        trial_by_factor.setdefault(identity["factor_template_id"], []).append({
            **identity, "trial_detail_id": descriptor.artifact_id,
            "factor_values_path": path / "factor_values.parquet",
        })
    for name, lock_id in (("candidate_a", CANDIDATE_A), ("candidate_b", CANDIDATE_B)):
        lock = raw_locks[name]
        factor_template_id = lock["factor_template_id"]
        if factor_template_id not in template_by_factor:
            raise RuntimeError("PARAMETER_BASELINE_UNRESOLVED:template_definition")
        template_definition_id, template = template_by_factor[factor_template_id]
        proposal_id = template.get("source_proposal_artifact_id")
        if not proposal_id:
            raise RuntimeError("PARAMETER_BASELINE_UNRESOLVED:source_proposal")
        _, proposal, _ = _restore(bundle, proposal_id, root / "proposals" / name,
                                  "research_proposal")
        payload = proposal.get("proposal_payload", {})
        schema = template.get("parameter_schema")
        search = payload.get("parameter_search", {}).get("search_space")
        if not isinstance(schema, list) or not schema or not isinstance(search, dict):
            raise RuntimeError("PARAMETER_BASELINE_UNRESOLVED:parameter_schema")
        defaults = {item["name"]: item.get("default") for item in schema}
        if any(value is None for value in defaults.values()) or set(defaults) != set(search):
            raise RuntimeError("PARAMETER_BASELINE_UNRESOLVED:agent_default_parameters")
        full_rows = _parameter_rows(search)
        local_rows = _local_rows(defaults, full_rows)
        source_trials = trial_by_factor.get(factor_template_id, [])
        values: dict[str, dict[str, Any]] = {}
        for row in full_rows:
            matches = [item for item in source_trials if item["parameters"] == row]
            if not matches:
                raise RuntimeError(f"PARAMETER_BASELINE_UNRESOLVED:trial:{name}:{row}")
            chosen = sorted(matches, key=lambda item: (item["research_fold"], item["trial_detail_id"]))[-1]
            key = _parameter_key(row)
            values[key] = {
                "parameters": row, "factor_instance_id": chosen["factor_instance_id"],
                "factor_value_artifact_id": chosen["factor_value_artifact_id"],
                "source_trial_detail_ids": sorted(item["trial_detail_id"] for item in matches),
                "factor_values_path": chosen["factor_values_path"],
            }
        candidates[name] = {
            "candidate_lock_id": lock_id, "factor_template_id": factor_template_id,
            "template_definition_id": template_definition_id,
            "source_proposal_artifact_id": proposal_id,
            "factor_instance_id": lock["factor_instance_id"], "parameter_schema": schema,
            "agent_default_parameters": defaults, "original_search_space": search,
            "full_parameter_rows": full_rows, "local_parameter_rows": local_rows,
            "fold_selected_parameters": lock["fold_selected_parameters"],
            "fold_selected_trial_ids": lock["fold_selected_trials"],
            "final_reporting_parameters": lock["final_reporting_parameters"],
            "orientation": lock["orientation"],
            "status": lock.get("status", lock.get("registry_status", "research_registered")),
            "semantic_display_name": (
                "medium-horizon momentum baseline deviation" if name == "candidate_a"
                else "skip-recent momentum plus pullback reward"
            ),
            "values": values,
        }
    return candidates


def _source_ensemble(bundle: AuthorityBundle, root: Path) -> dict[str, Any]:
    _, identity, _ = _restore(bundle, SOURCE_ASSESSMENT_ID, root,
                              "skip_recent_momentum_assessment")
    ensemble = identity.get("ensemble", {})
    if (ensemble.get("ensemble_id") != ENSEMBLE_ID
            or sorted(identity.get("candidate_lock_ids", [])) != sorted((CANDIDATE_A, CANDIDATE_B))):
        raise RuntimeError("source equal-weight ensemble contract changed")
    return {"source_assessment_id": SOURCE_ASSESSMENT_ID,
            "ensemble_id": ENSEMBLE_ID, "ensemble_eligible": ensemble.get("ensemble_eligible")}


def _parameter_rows(search: dict[str, Any]) -> list[dict[str, Any]]:
    names = sorted(search)
    spaces = []
    for name in names:
        item = search[name]
        if item.get("kind") != "explicit_values" or not item.get("values"):
            raise RuntimeError("PARAMETER_BASELINE_UNRESOLVED:unsupported_search_space")
        spaces.append(item["values"])
    return [dict(zip(names, row)) for row in itertools.product(*spaces)]


def _local_rows(defaults: dict[str, Any], full_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(defaults)]
    for name in sorted(defaults):
        values = sorted({row[name] for row in full_rows})
        position = values.index(defaults[name])
        for neighbor in (position - 1, position + 1):
            if 0 <= neighbor < len(values):
                row = dict(defaults); row[name] = values[neighbor]; rows.append(row)
    unique = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    if len(unique) > 7:
        raise RuntimeError("F1 factor trial budget exceeded")
    return unique


def _parameter_key(parameters: dict[str, Any]) -> str:
    return hash_payload(parameters)


def _write_signal(frame: pd.DataFrame, orientation: int, path: Path) -> tuple[str, Path]:
    output = frame[["symbol", "trade_date", "factor_value"]].rename(columns={"factor_value": "pred"}).copy()
    output["trade_date"] = pd.to_datetime(output["trade_date"])
    output["pred"] = pd.to_numeric(output["pred"], errors="coerce") * int(orientation)
    path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(path, index=False, compression="zstd")
    return "poas1_" + hash_payload({"signal_sha256": hash_file(path)}), path


class Evaluator:
    def __init__(self, runner: FormalQlibRunner, matrix: pd.DataFrame, work_root: Path):
        self.runner, self.matrix, self.work_root = runner, matrix, Path(work_root)
        self.signals: dict[str, Path] = {}
        self.rank_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.qlib_cache: dict[tuple[str, str, str, tuple[int, int, int]], dict[str, Any]] = {}

    def add_signal(self, signal_id: str, path: Path) -> str:
        self.signals[signal_id] = path
        return signal_id

    def ensemble(self, left: str, right: str) -> str:
        identity = "poae1_" + hash_payload({"left": left, "right": right, "weights": [0.5, 0.5]})
        if identity not in self.signals:
            path = self.work_root / "signals" / f"{identity}.parquet"
            equal_weight_signal({"left": self.signals[left], "right": self.signals[right]}, path)
            self.signals[identity] = path
        return identity

    def rankic(self, signal_id: str, period: tuple[str, str]) -> dict[str, Any]:
        key = (signal_id, *period)
        if key not in self.rank_cache:
            frame = pd.read_parquet(self.signals[signal_id])
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
            self.rank_cache[key] = rankic_metrics(frame, self.matrix, *period)
        return self.rank_cache[key]

    def qlib(self, signal_id: str, period: tuple[str, str], config: tuple[int, int, int]) -> dict[str, Any]:
        key = (signal_id, *period, config)
        if key not in self.qlib_cache:
            topk, n_drop, rebalance = config
            lifecycle = {**LIFECYCLE_POLICY, "minimum_observable_instruments": topk + n_drop}
            raw = self.runner.run(
                self.signals[signal_id], *period, topk=topk, n_drop=n_drop,
                rebalance_days=rebalance, lifecycle_policy=lifecycle,
            )
            if raw.get("status") != "completed":
                raise RuntimeError(f"formal Qlib ablation failed: {signal_id}/{period}/{config}")
            self.qlib_cache[key] = clean_qlib(raw)
        return self.qlib_cache[key]

    def selection_trial(self, *, layer: str, mode: str, object_name: str,
                        signal_id: str, config: tuple[int, int, int], fold: dict,
                        parameters: dict[str, Any]) -> dict[str, Any]:
        years = [year for year in YEAR_PERIODS if int(year) <= 2019 + fold["fold"]]
        annual = []
        for year in years:
            rankic = self.rankic(signal_id, YEAR_PERIODS[year])
            qlib = self.qlib(signal_id, YEAR_PERIODS[year], config)
            annual.append({
                "year": year, "rankic": rankic["mean_rankic"],
                "excess": qlib["net_excess_csi300"],
                "maximum_drawdown": qlib["max_drawdown"], "turnover": qlib["turnover"],
                "transaction_cost": qlib["transaction_cost"],
            })
        identity = {"layer": layer, "mode": mode, "object": object_name, "fold": fold["fold"],
                    "signal_id": signal_id, "parameters": parameters,
                    "strategy": list(config)}
        configuration = {key: identity[key] for key in (
            "object", "fold", "signal_id", "parameters", "strategy")}
        return {
            **identity, "trial_id": "poat1_" + hash_payload(identity),
            "configuration_id": "poac1_" + hash_payload(configuration),
            "topk": config[0], "n_drop": config[1], "rebalance_interval": config[2],
            "selection_metrics": selection_summary(annual), "annual_metrics": annual,
        }

    def period_result(self, signal_id: str, config: tuple[int, int, int],
                      period_name: str) -> dict[str, Any]:
        period = PERIODS[period_name]
        rankic = self.rankic(signal_id, period)
        qlib = self.qlib(signal_id, period, config)
        return {
            **rankic, "gross_return": qlib["gross_return"], "net_return": qlib["net_return"],
            "benchmark_return": qlib["benchmark_return"],
            "net_csi300_excess": qlib["net_excess_csi300"],
            "sharpe_ratio": qlib["sharpe_ratio"], "maximum_drawdown": qlib["max_drawdown"],
            "turnover": qlib["turnover"], "transaction_cost": qlib["transaction_cost"],
            "cost_drag": None if qlib["gross_return"] is None or qlib["net_return"] is None
            else qlib["gross_return"] - qlib["net_return"],
            "best_10_days_contribution": qlib["best_10_days_contribution"],
            "return_without_best_10_days": qlib["return_without_best_10_days"],
            "evidence_class": "retrospective_report_only" if period_name in {"2025", "2026H1"}
            else "retrospective_parameter_optimization_ablation",
            "usable_for_selection": period_name == "2019-2024",
        }


def _mode_parameter_rows(candidate: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    if mode == "F0": return [candidate["agent_default_parameters"]]
    if mode == "F1": return candidate["local_parameter_rows"]
    if mode == "F2": return candidate["full_parameter_rows"]
    raise ValueError(f"unknown factor mode: {mode}")


def _register_candidate_signals(evaluator: Evaluator, candidates: dict[str, Any], root: Path) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for name, candidate in candidates.items():
        output[name] = {}
        for key, item in candidate["values"].items():
            frame = pd.read_parquet(item["factor_values_path"])
            signal_id, path = _write_signal(frame, candidate["orientation"], root / name / f"{key}.parquet")
            evaluator.add_signal(signal_id, path); output[name][key] = signal_id
    return output


def _factor_ablation(evaluator: Evaluator, candidates: dict[str, Any], signal_map: dict[str, dict[str, str]]):
    folds, trials, final_signals, trial_sets = [], [], {}, {}
    for mode in FACTOR_MODES:
        selected_by_object = {"candidate_a": [], "candidate_b": [], "ensemble": []}
        for fold in FOLDS:
            selected = {}
            for name in ("candidate_a", "candidate_b"):
                rows = []
                for parameters in _mode_parameter_rows(candidates[name], mode):
                    signal_id = signal_map[name][_parameter_key(parameters)]
                    rows.append(evaluator.selection_trial(
                        layer="factor", mode=mode, object_name=name, signal_id=signal_id,
                        config=(20, 5, 5), fold=fold, parameters=parameters,
                    ))
                choice = select_trial(rows); selected[name] = choice; trials.extend(rows)
                trial_sets[(mode, name, fold["fold"])] = rows
                selected_by_object[name].append(choice)
            ensemble_rows = []
            for parameters_a, parameters_b in itertools.product(
                    _mode_parameter_rows(candidates["candidate_a"], mode),
                    _mode_parameter_rows(candidates["candidate_b"], mode)):
                ensemble_signal = evaluator.ensemble(
                    signal_map["candidate_a"][_parameter_key(parameters_a)],
                    signal_map["candidate_b"][_parameter_key(parameters_b)],
                )
                ensemble_rows.append(evaluator.selection_trial(
                    layer="factor", mode=mode, object_name="ensemble", signal_id=ensemble_signal,
                    config=(20, 5, 5), fold=fold,
                    parameters={"candidate_a": parameters_a, "candidate_b": parameters_b},
                ))
            ensemble_row = select_trial(ensemble_rows)
            selected_by_object["ensemble"].append(ensemble_row)
            trials.extend(ensemble_rows)
            trial_sets[(mode, "ensemble", fold["fold"])] = ensemble_rows
            for name, choice in (*selected.items(), ("ensemble", ensemble_row)):
                evaluation = _evaluation_result(evaluator, choice, fold)
                folds.append({**_flat_choice(choice), **evaluation})
        for name, choices in selected_by_object.items():
            final_signals[(mode, name)] = choices[-1]
    periods = _periods(evaluator, final_signals)
    return folds, trials, periods, final_signals, trial_sets


def _strategy_ablation(evaluator: Evaluator, candidates: dict[str, Any], signal_map: dict[str, dict[str, str]]):
    default_a = signal_map["candidate_a"][_parameter_key(candidates["candidate_a"]["agent_default_parameters"])]
    default_b = signal_map["candidate_b"][_parameter_key(candidates["candidate_b"]["agent_default_parameters"])]
    sources = {"candidate_a": default_a, "candidate_b": default_b,
               "ensemble": evaluator.ensemble(default_a, default_b)}
    folds, trials, finals, trial_sets = [], [], {}, {}
    for mode, configs in STRATEGY_MODES.items():
        for name, signal_id in sources.items():
            choices = []
            for fold in FOLDS:
                rows = [evaluator.selection_trial(
                    layer="strategy", mode=mode, object_name=name, signal_id=signal_id,
                    config=config, fold=fold, parameters={"factor_mode": "F0"},
                ) for config in configs]
                choice = select_trial(rows); choices.append(choice); trials.extend(rows)
                trial_sets[(mode, name, fold["fold"])] = rows
                folds.append({**_flat_choice(choice), **_evaluation_result(evaluator, choice, fold)})
            finals[(mode, name)] = choices[-1]
    return folds, trials, _periods(evaluator, finals), finals, trial_sets


def _combined_ablation(evaluator: Evaluator, factor_finals: dict, factor_folds: list[dict]):
    folds, trials, finals, trial_sets = [], [], {}, {}
    factor_choice = {(row["mode"], row["object_name"], row["fold"]): row for row in factor_folds}
    for mode, (factor_mode, strategy_mode) in COMBINED_MODES.items():
        for name in ("candidate_a", "candidate_b", "ensemble"):
            choices = []
            for fold in FOLDS:
                base = factor_choice[(factor_mode, name, fold["fold"])]
                rows = [evaluator.selection_trial(
                    layer="combined", mode=mode, object_name=name,
                    signal_id=base["signal_id"], config=config, fold=fold,
                    parameters={"factor_parameters": json.loads(base["parameters_json"])},
                ) for config in STRATEGY_MODES[strategy_mode]]
                choice = select_trial(rows); choices.append(choice); trials.extend(rows)
                trial_sets[(mode, name, fold["fold"])] = rows
                folds.append({**_flat_choice(choice), **_evaluation_result(evaluator, choice, fold)})
            finals[(mode, name)] = choices[-1]
    return folds, trials, _periods(evaluator, finals), finals, trial_sets


def _evaluation_result(evaluator: Evaluator, choice: dict[str, Any], fold: dict) -> dict[str, Any]:
    rankic = evaluator.rankic(choice["signal_id"], fold["evaluation"])
    qlib = evaluator.qlib(choice["signal_id"], fold["evaluation"],
                          (choice["topk"], choice["n_drop"], choice["rebalance_interval"]))
    return {
        "evaluation_start": fold["evaluation"][0], "evaluation_end": fold["evaluation"][1],
        "evaluation_rankic": rankic["mean_rankic"], "evaluation_rankicir": rankic["rankicir"],
        "evaluation_rankic_positive_rate": rankic["rankic_positive_rate"],
        "evaluation_net_return": qlib["net_return"], "evaluation_csi300_return": qlib["benchmark_return"],
        "evaluation_csi300_excess": qlib["net_excess_csi300"], "evaluation_sharpe": qlib["sharpe_ratio"],
        "evaluation_maximum_drawdown": qlib["max_drawdown"], "evaluation_turnover": qlib["turnover"],
        "evaluation_transaction_cost": qlib["transaction_cost"],
        "evaluation_best_10_days_contribution": qlib["best_10_days_contribution"],
        "evaluation_return_without_best_10_days": qlib["return_without_best_10_days"],
        "selection_used_2025": False, "selection_used_2026H1": False,
    }


def _flat_choice(choice: dict[str, Any]) -> dict[str, Any]:
    lock_payload = {key: choice[key] for key in (
        "layer", "mode", "object", "fold", "trial_id", "signal_id", "parameters",
        "topk", "n_drop", "rebalance_interval", "selection_metrics",
    )}
    return {
        "layer": choice["layer"], "mode": choice["mode"], "object_name": choice["object"],
        "fold": choice["fold"], "selected_trial_id": choice["trial_id"],
        "selected_configuration_id": choice["configuration_id"],
        "fold_lock_id": "poafl1_" + hash_payload(lock_payload),
        "signal_id": choice["signal_id"], "parameters_json": json.dumps(choice["parameters"], sort_keys=True),
        "topk": choice["topk"], "n_drop": choice["n_drop"],
        "rebalance_interval": choice["rebalance_interval"],
        **{f"research_{key}": value for key, value in choice["selection_metrics"].items() if key != "eligible"},
    }


def _flat_trial(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": row["layer"], "mode": row["mode"], "object_name": row["object"],
        "fold": row["fold"], "trial_id": row["trial_id"], "signal_id": row["signal_id"],
        "configuration_id": row["configuration_id"],
        "parameters_json": json.dumps(row["parameters"], sort_keys=True),
        "topk": row["topk"], "n_drop": row["n_drop"], "rebalance_interval": row["rebalance_interval"],
        **row["selection_metrics"],
    }


def _periods(evaluator: Evaluator, finals: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for (mode, name), choice in finals.items():
        config = (choice["topk"], choice["n_drop"], choice["rebalance_interval"])
        output.setdefault(mode, {})[name] = {
            period: evaluator.period_result(choice["signal_id"], config, period)
            for period in PERIODS
        } | {"selected_trial_id": choice["trial_id"], "parameters": choice["parameters"],
             "strategy": list(config), "signal_id": choice["signal_id"]}
    return output


def _consistency_and_plateau(folds: list[dict], trial_sets: dict, modes: list[str],
                             parameter_fields: tuple[str, ...]) -> tuple[dict, dict]:
    consistency, plateau = {}, {}
    for mode in modes:
        consistency[mode], plateau[mode] = {}, {}
        for name in ("candidate_a", "candidate_b", "ensemble"):
            selected_rows = [row for row in folds if row["mode"] == mode and row["object_name"] == name]
            parameters = []
            legal = []
            for row in selected_rows:
                payload = json.loads(row["parameters_json"])
                combined = {**_flatten_parameters(payload), "topk": row["topk"], "n_drop": row["n_drop"],
                            "rebalance_interval": row["rebalance_interval"]}
                parameters.append(combined)
                legal.extend([{**_flatten_parameters(item["parameters"]), "topk": item["topk"], "n_drop": item["n_drop"],
                               "rebalance_interval": item["rebalance_interval"]}
                              for item in trial_sets[(mode, name, row["fold"])]] )
            consistency[mode][name] = parameter_consistency(parameters, legal)
            final_trials = trial_sets[(mode, name, 4)]
            selected_id = selected_rows[-1]["selected_trial_id"]
            flattened_trials = [
                {
                    **item,
                    **_flatten_parameters(item["parameters"]),
                    "topk": item["topk"],
                    "n_drop": item["n_drop"],
                    "rebalance_interval": item["rebalance_interval"],
                }
                for item in final_trials
            ]
            selected = next(item for item in flattened_trials if item["trial_id"] == selected_id)
            fields = tuple(sorted(set(parameters[0]))) if parameters else parameter_fields
            plateau[mode][name] = plateau_analysis(selected, flattened_trials, fields)
    return consistency, plateau


def _flatten_parameters(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested factor parameter payloads without losing parameter identity."""
    flattened: dict[str, Any] = {}
    for key, item in sorted(value.items()):
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(_flatten_parameters(item, name))
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            flattened[name] = item
    return flattened


def _rank_and_winner(evaluator: Evaluator, all_trial_sets: list[tuple[str, dict]]) -> tuple[pd.DataFrame, dict]:
    rows, winners = [], {}
    for layer, trial_sets in all_trial_sets:
        for (mode, name, fold_number), trials in trial_sets.items():
            research_order = sorted(trials, key=ordering_key)
            research_rank = {row["trial_id"]: len(research_order)-index for index, row in enumerate(research_order)}
            selected = research_order[0]
            winner = {"selected_trial_id": selected["trial_id"],
                      "research_selected_metric": selected["selection_metrics"]["median_csi300_excess"],
                      "research_median_trial_metric": float(np.median([r["selection_metrics"]["median_csi300_excess"] for r in trials]))}
            winner["research_selected_minus_median"] = winner["research_selected_metric"] - winner["research_median_trial_metric"]
            evaluation_year = str(2020 + fold_number)
            later_periods = [(f"evaluation_{evaluation_year}", YEAR_PERIODS[evaluation_year])]
            if fold_number == 4:
                later_periods.extend((period, PERIODS[period]) for period in ("2025", "2026H1"))
            for period, interval in later_periods:
                later_values, later_rows = {}, []
                for trial in trials:
                    config = (trial["topk"], trial["n_drop"], trial["rebalance_interval"])
                    rankic = evaluator.rankic(trial["signal_id"], interval)["mean_rankic"]
                    qlib = evaluator.qlib(trial["signal_id"], interval, config)
                    metric = selection_summary([{"rankic": rankic, "excess": qlib["net_excess_csi300"],
                        "maximum_drawdown": qlib["max_drawdown"], "turnover": qlib["turnover"],
                        "transaction_cost": qlib["transaction_cost"]}])
                    later = {**trial, "selection_metrics": metric}
                    later_rows.append(later)
                later_order = sorted(later_rows, key=ordering_key)
                for index, trial in enumerate(later_order): later_values[trial["trial_id"]] = len(later_order)-index
                stable = rank_stability(research_rank, later_values, selected["trial_id"], period)
                rows.append({"layer": layer, "mode": mode, "object_name": name, **stable})
                selected_later = next(r for r in later_rows if r["trial_id"] == selected["trial_id"])["selection_metrics"]["median_csi300_excess"]
                median_later = float(np.median([r["selection_metrics"]["median_csi300_excess"] for r in later_rows]))
                winner[period] = {"selected_trial_metric": selected_later, "median_trial_metric": median_later,
                                  "selected_minus_median": selected_later-median_later,
                                  "selected_trial_percentile": stable["selected_trial_later_percentile"]}
            winner["winner_curse_detected_evaluation"] = (
                winner["research_selected_minus_median"] > 0
                and winner[f"evaluation_{evaluation_year}"]["selected_minus_median"] <= 0
            )
            winner["winner_curse_detected"] = fold_number == 4 and winner["research_selected_minus_median"] > 0 and all(
                winner[p]["selected_minus_median"] <= 0 for p in ("2025", "2026H1")
            )
            winners[f"{layer}:{mode}:{name}:fold_{fold_number}"] = winner
    return pd.DataFrame(rows), winners


def _assessment(factor_periods: dict, strategy_periods: dict, combined_periods: dict,
                consistency: dict, plateau: dict, rank_rows: pd.DataFrame, winners: dict) -> tuple[dict, dict, dict]:
    layers = {
        "factor_parameter_optimization": (factor_periods, "F0", ("F1", "F2"), "factor"),
        "strategy_parameter_optimization": (strategy_periods, "S0", ("S1", "S2"), "strategy"),
        "combined_optimization": (combined_periods, "O0", ("O1", "O2"), "combined"),
    }
    gaps, classifications = {}, {}
    decisions = {}
    for label, (periods, baseline_mode, optimized_modes, layer_key) in layers.items():
        gaps[label], classifications[label] = {}, {}
        for mode in optimized_modes:
            gaps[label][mode], classifications[label][mode] = {}, {}
            for name in ("candidate_a", "candidate_b", "ensemble"):
                baseline = periods[baseline_mode][name]
                optimized = periods[mode][name]
                research_gain = gains(optimized["2019-2024"], baseline["2019-2024"])
                report_gains = [gains(optimized[p], baseline[p]) for p in ("2025", "2026H1")]
                average = {key: float(np.mean([row[key] for row in report_gains if row[key] is not None]))
                           if any(row[key] is not None for row in report_gains) else None
                           for key in research_gain}
                gap = {key: None if research_gain[key] is None or average[key] is None
                       else research_gain[key] - average[key] for key in research_gain}
                gaps[label][mode][name] = {"research_gain": research_gain,
                    "gain_2025": report_gains[0], "gain_2026h1": report_gains[1],
                    "average_report_gain": average, "generalization_gap": gap}
                rank = rank_rows[(rank_rows.layer == layer_key) & (rank_rows.mode == mode) &
                                 (rank_rows.object_name == name)]
                percentiles = [rank.loc[rank.period == p, "selected_trial_later_percentile"].iloc[0]
                               if not rank[rank.period == p].empty else None for p in ("2025", "2026H1")]
                classifications[label][mode][name] = classify_overfit(
                    research_gain, report_gains, plateau[layer_key][mode][name]["plateau_ratio"],
                    consistency[layer_key][mode][name]["adjacent_match_rate"], percentiles,
                )
        light, full = optimized_modes
        light_labels = list(classifications[label][light].values())
        full_labels = list(classifications[label][full].values())
        if all(value == "likely_robust" for value in full_labels):
            decision = "keep_full_optimization"
        elif full_labels.count("likely_overfit") > light_labels.count("likely_overfit"):
            decision = "replace_full_with_local_optimization"
        elif full_labels.count("likely_overfit") >= 2 and light_labels.count("likely_overfit") >= 2:
            decision = "suspend_parameter_optimization"
        else:
            decision = "default_first_optimize_only_on_failure"
        decisions[label] = decision
    return gaps, classifications, {
        "factor_parameter_optimization": decisions["factor_parameter_optimization"],
        "strategy_parameter_optimization": decisions["strategy_parameter_optimization"],
        "combined_optimization": decisions["combined_optimization"],
        "apply_automatically": False, "promotion_writes": 0,
    }


def _search_intensity(trial_sets: dict, periods: dict) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for (mode, name, fold), rows in sorted(trial_sets.items()):
        if fold != 4:
            continue
        metrics = [row["selection_metrics"] for row in rows]
        best = select_trial(rows)
        excess = [float(item["median_csi300_excess"]) for item in metrics]
        result.setdefault(mode, {})[name] = {
            "trial_count": len(rows),
            "eligible_trial_count": sum(bool(item.get("eligible")) for item in metrics),
            "best_metric": best["selection_metrics"]["median_csi300_excess"],
            "median_metric": float(np.median(excess)),
            "best_minus_median": best["selection_metrics"]["median_csi300_excess"] - float(np.median(excess)),
            "research_excess": periods[mode][name]["2019-2024"]["net_csi300_excess"],
            "report_2025_excess": periods[mode][name]["2025"]["net_csi300_excess"],
            "report_2026h1_excess": periods[mode][name]["2026H1"]["net_csi300_excess"],
        }
    modes = sorted(result)
    result["intensity_effect"] = {}
    for name in ("candidate_a", "candidate_b", "ensemble"):
        research = [result[mode][name]["research_excess"] for mode in modes]
        report = [np.mean([result[mode][name]["report_2025_excess"],
                           result[mode][name]["report_2026h1_excess"]]) for mode in modes]
        research_up = all(right >= left for left, right in zip(research, research[1:]))
        report_down = all(right <= left for left, right in zip(report, report[1:]))
        result["intensity_effect"][name] = {
            "mode_order": modes, "research_excess": research,
            "average_report_excess": [float(value) for value in report],
            "research_monotonic_non_decreasing": research_up,
            "report_monotonic_non_increasing": report_down,
            "research_rises_while_report_falls": research_up and report_down,
        }
    return result


def _turnover_cost(periods: dict, baseline_mode: str, optimized_modes: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for mode in optimized_modes:
        result[mode] = {}
        for name in ("candidate_a", "candidate_b", "ensemble"):
            result[mode][name] = {}
            for period in PERIODS:
                baseline, optimized = periods[baseline_mode][name][period], periods[mode][name][period]
                gross_improvement = optimized["gross_return"] - baseline["gross_return"]
                net_improvement = optimized["net_return"] - baseline["net_return"]
                cost_drag_change = optimized["cost_drag"] - baseline["cost_drag"]
                result[mode][name][period] = {
                    "turnover_change": optimized["turnover"] - baseline["turnover"],
                    "transaction_cost_change": optimized["transaction_cost"] - baseline["transaction_cost"],
                    "gross_improvement": gross_improvement,
                    "net_improvement": net_improvement,
                    "cost_drag_change": cost_drag_change,
                    "optimization_gain_consumed_by_cost": gross_improvement > 0 and net_improvement <= 0,
                }
    return result


def _publish_store(bundle: AuthorityBundle, artifact: dict, lineage: tuple[str, ...]) -> dict:
    receipt = bundle.store.import_artifact(
        artifact["artifact_kind"], Path(artifact["path"]), artifact["artifact_id"], lineage=lineage,
    )
    return {"artifact_id": artifact["artifact_id"], "descriptor_id": receipt.descriptor_id,
            "exact_existing": receipt.exact_existing, "new_blob_count": receipt.new_blob_count}


def _cold(bundle: AuthorityBundle, artifact_id: str, root: Path) -> dict:
    descriptor = bundle.store.find_by_artifact_id(artifact_id)
    if descriptor is None: raise RuntimeError(f"published artifact missing: {artifact_id}")
    destination = root / artifact_id
    if destination.exists(): shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    return validate_artifact(destination, artifact_id, descriptor.artifact_kind)


def _parquet(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False, compression="zstd")
    return path


def _identity(kind: str, payload: Any, source_ids: list[str], qlib_calls: int) -> dict[str, Any]:
    return {"schema_version": "parameter-optimization-ablation-v1", "contract_revision": 2,
            "task_id": TASK_ID,
            "provider_id": "tushare-pro-v1", "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_ids": source_ids, "payload_hash": hash_payload(payload),
            "artifact_role": kind, "predictive_claim": False, "usable_for_promotion": False,
            "eligible_for_production": False, "agent_calls": 0, "network_calls": 0,
            "promotion_writes": 0, "qlib_calls_at_publication": qlib_calls}


def _find_existing(bundle: AuthorityBundle, root: Path):
    matches = []
    for index, descriptor in enumerate(bundle.store.list_by_kind("optimization_overfit_assessment")):
        destination = root / str(index)
        bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
        manifest = json.loads((destination / "manifest.json").read_text())
        identity = manifest["identity"]
        if (identity.get("task_id") == TASK_ID
                and identity.get("source_experiment_id") == SOURCE_EXPERIMENT_ID
                and identity.get("contract_revision") == 2):
            matches.append((descriptor, identity))
    if len(matches) > 1: raise RuntimeError("multiple canonical parameter ablation assessments")
    return matches[0] if matches else None


def execute_study(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    repository_root, work_root = Path(repository_root), Path(work_root)
    bundle = _load_ablation_bundle(authority_path=repository_root / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=work_root / "authority", store_root=store_root)
    if _find_existing(bundle, work_root / "existing"):
        return replay_study(repository_root=repository_root, work_root=work_root / "replay", store_root=store_root) | {"exact_existing": True}
    candidates = _candidate_inputs(bundle, work_root / "source")
    source_ensemble = _source_ensemble(bundle, work_root / "source" / "ensemble")
    matrix, dataset_artifact = _source_dataset(bundle, work_root / "dataset")
    if (dataset_artifact.get("provider_id") != "tushare-pro-v1"
            or dataset_artifact.get("symbol_count") != 100
            or dataset_artifact.get("dataset_kind") != "momentum_feature_matrix_v1"):
        raise RuntimeError("momentum Dataset identity contract changed")
    runner = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
    runner.service.initialize()
    try:
        from qlib.config import C
        C.kernels = 1
    except Exception:
        pass
    evaluator = Evaluator(runner, matrix, work_root / "evaluation")
    signal_map = _register_candidate_signals(evaluator, candidates, work_root / "signals")

    input_summary = {name: {key: value for key, value in candidate.items() if key != "values"}
                     for name, candidate in candidates.items()}
    factor_modes = {name: {mode: _mode_parameter_rows(candidate, mode) for mode in FACTOR_MODES}
                    for name, candidate in candidates.items()}
    spec = {"schema_version": "parameter-optimization-ablation-spec-v1", "contract_revision": 2,
            "task_id": TASK_ID,
            "study_type": "retrospective_parameter_optimization_ablation",
            "source_experiment_id": SOURCE_EXPERIMENT_ID, "candidate_lock_ids": [CANDIDATE_A, CANDIDATE_B],
            "ensemble_id": ENSEMBLE_ID, "dataset_id": DATASET_ID, "folds": list(FOLDS),
            "factor_modes": list(FACTOR_MODES), "strategy_modes": {k: [list(v) for v in rows] for k, rows in STRATEGY_MODES.items()},
            "combined_modes": COMBINED_MODES, "ordering": list(ORDERING), "fixed_strategy": FORMAL_STRATEGY,
            "selection_uses_2025": False, "selection_uses_2026H1": False,
            "agent_calls": 0, "network_calls": 0, "promotion_writes": 0}
    spec_artifact = publish_artifact(work_root / "domain", "parameter_optimization_ablation_spec",
        _identity("spec", spec, [SOURCE_EXPERIMENT_ID, SOURCE_ASSESSMENT_ID, CANDIDATE_A, CANDIDATE_B], runner.calls),
        {"spec.json": spec, "input_candidates.json": {"candidates": input_summary, "ensemble": source_ensemble},
         "factor_modes.json": factor_modes,
         "strategy_modes.json": {key: [list(value) for value in values] for key, values in STRATEGY_MODES.items()}})
    receipts = [_publish_store(bundle, spec_artifact, (SOURCE_EXPERIMENT_ID, SOURCE_ASSESSMENT_ID, CANDIDATE_A, CANDIDATE_B))]
    _cold(bundle, spec_artifact["artifact_id"], work_root / "cold")

    factor_folds, factor_trials, factor_periods, factor_finals, factor_sets = _factor_ablation(evaluator, candidates, signal_map)
    strategy_folds, strategy_trials, strategy_periods, strategy_finals, strategy_sets = _strategy_ablation(evaluator, candidates, signal_map)
    combined_folds, combined_trials, combined_periods, combined_finals, combined_sets = _combined_ablation(evaluator, factor_finals, factor_folds)
    consistency, plateau = {}, {}
    consistency["factor"], plateau["factor"] = _consistency_and_plateau(
        factor_folds, factor_sets, list(FACTOR_MODES),
        ("baseline_window", "high_distance_weight", "candidate_a", "candidate_b"))
    consistency["strategy"], plateau["strategy"] = _consistency_and_plateau(
        strategy_folds, strategy_sets, list(STRATEGY_MODES), ("topk", "n_drop", "rebalance_interval"))
    consistency["combined"], plateau["combined"] = _consistency_and_plateau(
        combined_folds, combined_sets, list(COMBINED_MODES),
        ("factor_parameters", "topk", "n_drop", "rebalance_interval"))
    rank_frame, winners = _rank_and_winner(evaluator, [
        ("factor", factor_sets), ("strategy", strategy_sets), ("combined", combined_sets)])
    total_qlib_result_count = len(list((work_root / "qlib-cache").glob("*.json")))
    gaps, classifications, decisions = _assessment(
        factor_periods, strategy_periods, combined_periods, consistency, plateau, rank_frame, winners)
    search_intensity = {
        "factor": _search_intensity(factor_sets, factor_periods),
        "strategy": _search_intensity(strategy_sets, strategy_periods),
        "combined": _search_intensity(combined_sets, combined_periods),
    }
    turnover_cost = {
        "factor": _turnover_cost(factor_periods, "F0", ("F1", "F2")),
        "strategy": _turnover_cost(strategy_periods, "S0", ("S1", "S2")),
        "combined": _turnover_cost(combined_periods, "O0", ("O1", "O2")),
    }

    artifacts = []
    for kind, folds, trials, periods, layer in (
        ("factor_optimization_ablation", factor_folds, factor_trials, factor_periods, "factor"),
        ("strategy_optimization_ablation", strategy_folds, strategy_trials, strategy_periods, "strategy"),
        ("combined_optimization_ablation", combined_folds, combined_trials, combined_periods, "combined"),
    ):
        fold_path = _parquet(folds, work_root / "outputs" / kind / "fold_results.parquet")
        trial_path = _parquet([_flat_trial(row) for row in trials], work_root / "outputs" / kind / "trial_metrics.parquet")
        payload = {"periods": periods, "consistency": consistency[layer], "plateau": plateau[layer],
                   "fold_hash": hash_file(fold_path), "trial_hash": hash_file(trial_path)}
        artifact = publish_artifact(work_root / "domain", kind,
            _identity(kind, payload, [spec_artifact["artifact_id"]], total_qlib_result_count),
            {"fold_results.parquet": fold_path, "trial_metrics.parquet": trial_path,
             "parameter_consistency.json": consistency[layer], "plateau_analysis.json": plateau[layer],
             "period_results.json": periods})
        receipts.append(_publish_store(bundle, artifact, (spec_artifact["artifact_id"],)))
        _cold(bundle, artifact["artifact_id"], work_root / "cold"); artifacts.append(artifact)
    rank_path = _parquet(rank_frame.to_dict("records"), work_root / "outputs" / "trial_rank_stability.parquet")
    rank_artifact = publish_artifact(work_root / "domain", "optimization_trial_rank_stability",
        _identity("rank_stability", {"rank_hash": hash_file(rank_path), "winners": winners},
                  [item["artifact_id"] for item in artifacts], total_qlib_result_count),
        {"trial_rank_stability.parquet": rank_path, "parameter_consistency.json":
         {"consistency": consistency, "winner_curse": winners}})
    receipts.append(_publish_store(bundle, rank_artifact, tuple(item["artifact_id"] for item in artifacts)))
    _cold(bundle, rank_artifact["artifact_id"], work_root / "cold")
    summary = {"task_id": TASK_ID, "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "factor_f1_equals_f2_space": all(
            {hash_payload(row) for row in factor_modes[name]["F1"]}
            == {hash_payload(row) for row in factor_modes[name]["F2"]}
            for name in factor_modes),
        "qlib_calls": total_qlib_result_count,
        "factor_optimization_calls": 0,
        "strategy_optimization_trial_evaluations": len(strategy_trials) + len(combined_trials),
        "agent_calls": 0, "network_calls": 0, "promotion_writes": 0,
        "candidate_status_before": ["research_registered", "research_registered"],
        "candidate_status_after": ["research_registered", "research_registered"],
        "predictive_claim": False, "usable_for_promotion": False, "eligible_for_production": False}
    assessment_artifact = publish_artifact(work_root / "domain", "optimization_overfit_assessment",
        _identity("assessment", {"gaps": gaps, "classifications": classifications,
                  "decisions": decisions, "search_intensity": search_intensity,
                  "turnover_cost": turnover_cost, "summary": summary},
                  [spec_artifact["artifact_id"], *[item["artifact_id"] for item in artifacts], rank_artifact["artifact_id"]], total_qlib_result_count),
        {"generalization_gap.json": gaps, "overfit_classification.json": classifications,
         "framework_decision.json": decisions, "search_intensity.json": search_intensity,
         "turnover_cost_analysis.json": turnover_cost, "summary.json": summary})
    lineage = (spec_artifact["artifact_id"], *[item["artifact_id"] for item in artifacts], rank_artifact["artifact_id"])
    receipts.append(_publish_store(bundle, assessment_artifact, lineage))
    _cold(bundle, assessment_artifact["artifact_id"], work_root / "cold")
    inventory = publish_inventory(bundle.store); integrity = scan_store_integrity(bundle.store)
    return {"status": "completed", "spec_id": spec_artifact["artifact_id"],
        "artifact_ids": [spec_artifact["artifact_id"], *[item["artifact_id"] for item in artifacts],
                         rank_artifact["artifact_id"], assessment_artifact["artifact_id"]],
        "assessment_id": assessment_artifact["artifact_id"], "framework_decision": decisions,
        "overfit_classification": classifications, "generalization_gap": gaps,
        "summary": summary, "receipts": receipts, "inventory_id": inventory.inventory_id,
        "store_integrity": integrity.status, "missing": len(integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs)}


def replay_study(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = _load_ablation_bundle(authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                   work_root=Path(work_root) / "authority", store_root=store_root,
                                   market_data=False)
    found = _find_existing(bundle, Path(work_root) / "lookup")
    if not found: raise RuntimeError("parameter optimization ablation assessment not found")
    descriptor, identity = found
    artifact_ids = [*identity["source_ids"], descriptor.artifact_id]
    recovered = []
    for artifact_id in artifact_ids:
        child = bundle.store.find_by_artifact_id(artifact_id)
        if child is None: raise RuntimeError(f"ablation lineage missing: {artifact_id}")
        destination = Path(work_root) / "cold" / artifact_id
        bundle.store.materialize_artifact(child.descriptor_id, destination)
        recovered.append(validate_artifact(destination, artifact_id, child.artifact_kind))
    assessment = json.loads(((Path(work_root) / "cold" / descriptor.artifact_id) / "framework_decision.json").read_text())
    integrity = scan_store_integrity(bundle.store)
    return {"status": "valid", "assessment_id": descriptor.artifact_id,
        "framework_decision": assessment, "recovered_artifact_count": len(recovered),
        "factor_optimization_calls": 0, "strategy_optimization_calls": 0,
        "qlib_calls": 0, "agent_calls": 0, "network_calls": 0,
        "promotion_writes": 0, "new_artifacts": 0, "new_blobs": 0,
        "store_integrity": integrity.status, "missing": len(integrity.issues),
        "unreferenced": len(integrity.unreferenced_blobs)}


def plan_study(*, repository_root: Path, work_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    bundle = _load_ablation_bundle(
        authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=Path(work_root) / "authority", store_root=store_root, market_data=False,
    )
    candidates = _candidate_inputs(bundle, Path(work_root) / "source")
    source_ensemble = _source_ensemble(bundle, Path(work_root) / "source" / "ensemble")
    return {
        "status": "valid", "task_id": TASK_ID, "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "dataset_id": DATASET_ID, "candidate_lock_ids": [CANDIDATE_A, CANDIDATE_B],
        "source_ensemble": source_ensemble,
        "candidate_parameters": {
            name: {
                "agent_default_parameters": item["agent_default_parameters"],
                "original_search_space": item["original_search_space"],
                "final_reporting_parameters": item["final_reporting_parameters"],
                "orientation": item["orientation"], "status": item["status"],
                "f0_trial_count": 1, "f1_trial_count": len(item["local_parameter_rows"]),
                "f2_trial_count": len(item["full_parameter_rows"]),
            }
            for name, item in candidates.items()
        },
        "strategy_trial_counts": {name: len(rows) for name, rows in STRATEGY_MODES.items()},
        "fold_count": len(FOLDS), "selection_uses_2025": False,
        "selection_uses_2026H1": False, "agent_calls": 0, "network_calls": 0,
        "promotion_writes": 0,
    }


def inspect_study(*, repository_root: Path, work_root: Path, store_root: Path | None = None,
                  artifact_kind: str | None = None) -> dict[str, Any]:
    bundle = _load_ablation_bundle(
        authority_path=Path(repository_root) / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=Path(work_root) / "authority", store_root=store_root, market_data=False,
    )
    found = _find_existing(bundle, Path(work_root) / "lookup")
    if not found:
        raise RuntimeError("parameter optimization ablation assessment not found")
    descriptor, identity = found
    artifact_ids = [*identity["source_ids"], descriptor.artifact_id]
    records = []
    for artifact_id in artifact_ids:
        child = bundle.store.find_by_artifact_id(artifact_id)
        if child is None or (artifact_kind and child.artifact_kind != artifact_kind):
            continue
        destination = Path(work_root) / "artifacts" / artifact_id
        if destination.exists():
            shutil.rmtree(destination)
        bundle.store.materialize_artifact(child.descriptor_id, destination)
        valid = validate_artifact(destination, artifact_id, child.artifact_kind)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        inspection = {}
        for item in manifest["files"]:
            path = destination / item["path"]
            if path.suffix == ".json":
                inspection[item["path"]] = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".parquet":
                frame = pd.read_parquet(path)
                inspection[item["path"]] = {"row_count": len(frame),
                                             "columns": list(frame.columns)}
        records.append({**valid, "files": [item["path"] for item in manifest["files"]],
                        "inspection": inspection})
    return {"status": "valid", "assessment_id": descriptor.artifact_id,
            "artifact_kind_filter": artifact_kind, "artifacts": records,
            "agent_calls": 0, "network_calls": 0, "promotion_writes": 0}
