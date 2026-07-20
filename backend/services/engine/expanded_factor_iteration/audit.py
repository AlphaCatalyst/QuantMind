from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.research_campaign.novelty import structural_fingerprint
from backend.services.engine.tushare_cutover.canonical import hash_payload


SIGNALS = (
    "usa_a4dad65c88f6e74122d96325d003e6eea5d651c4e5fb578c589e4b87c8350ca3",
    "usa_5399f8d7095d3592278cd06ae09b8c99df028ae07bd6c2ac45f3fa147f89d72d",
    "usa_839f30c4ac0d8ab68f2828c1037269438c3cc65cca83b6a4ee23f0e0e99cdb73",
)


def _dsl(node: dict[str, Any]) -> str:
    kind = node["type"]
    if kind in {"feature", "parameter"}:
        return node["name"]
    if kind == "constant":
        return repr(node["value"])
    if kind in {"negate", "absolute", "cs_rank", "cs_zscore"}:
        return f"{kind}({_dsl(node['operand'])})"
    if kind in {"rolling_mean", "rolling_std", "rolling_min", "rolling_max"}:
        return f"{kind}({_dsl(node['operand'])},window={_dsl(node['window'])})"
    if kind in {"lag", "delta"}:
        return f"{kind}({_dsl(node['operand'])},periods={_dsl(node['periods'])})"
    if kind in {"add", "subtract", "multiply", "divide"}:
        symbol = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}[kind]
        return f"({_dsl(node['left'])} {symbol} {_dsl(node['right'])})"
    if kind == "clip":
        return f"clip({_dsl(node['operand'])},{_dsl(node['lower'])},{_dsl(node['upper'])})"
    raise ValueError(f"unsupported DSL node in historical audit: {kind}")


def _feature_names(node: Any) -> list[str]:
    result: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "feature":
            result.append(node["name"])
        for value in node.values():
            result.extend(_feature_names(value))
    elif isinstance(node, list):
        for value in node:
            result.extend(_feature_names(value))
    return sorted(set(result))


def _explanation(name: str, orientation: int) -> dict[str, str]:
    known = {
        "liquidity_normalized_momentum": {
            "preference": "偏好相对成交活跃、近期收益持续且流动性可承载的股票。",
            "high_value": "高值表示滚动收益相对成交量状态更强。",
            "behavior": "试图捕获成交活跃背景下的短期价格延续。",
            "failure": "动量方向和成交量含义会随行情阶段反转，且容易产生较高换手。",
        },
        "liquidity_persistence_beta_penalty": {
            "preference": "偏好持续受到交易关注、同时绝对市场Beta较低的股票。",
            "high_value": "高值表示流动性持续性较强且系统性市场暴露较低。",
            "behavior": "试图分离个股交易关注度与宽基市场风险。",
            "failure": "低Beta惩罚可能错过风险偏好行情，流动性持续性也具有明显制度切换。",
        },
        "momentum_peak_volatility_adjusted": {
            "preference": "经方向翻转后偏好近期动量峰值较弱、特异波动更可控的股票。",
            "high_value": "存储值已按方向处理；高值代表原始动量峰值/波动结构的反向暴露。",
            "behavior": "试图捕获动量极值后的反转并惩罚不稳定波动。",
            "failure": "峰值算子依赖少数极端日，方向容易在趋势与反转市场之间切换。",
        },
    }
    value = known.get(name, {
        "preference": "偏好由正式DSL结构定义的横截面股票。",
        "high_value": f"高值代表按orientation={orientation}处理后的较强暴露。",
        "behavior": "试图捕获Agent提出的经济结构。",
        "failure": "可能受参数、市场制度和交易成本影响。",
    })
    return value


def build_existing_factor_audit(store, work_root: Path) -> dict:
    materialized: dict[str, tuple[Path, dict]] = {}
    definitions = []
    for signal_id in SIGNALS:
        descriptor = store.find_by_artifact_id(signal_id)
        if descriptor is None or descriptor.artifact_kind != "unified_signal":
            raise RuntimeError("EXISTING_FACTOR_DEFINITION_UNRESOLVED")
        signal_root = Path(work_root) / "existing-signals" / signal_id
        if signal_root.exists():
            shutil.rmtree(signal_root)
        store.materialize_artifact(descriptor.descriptor_id, signal_root)
        spec = json.loads((signal_root / "spec.json").read_text(encoding="utf-8"))
        source = spec["inputs"][0]
        source_id = source["source_artifact_id"]
        if source_id not in materialized:
            source_descriptor = store.find_by_artifact_id(source_id)
            if source_descriptor is None or source_descriptor.artifact_kind != "tushare_historical_round_lock":
                raise RuntimeError("EXISTING_FACTOR_DEFINITION_UNRESOLVED")
            source_root = Path(work_root) / "existing-round-locks" / source_id
            if source_root.exists():
                shutil.rmtree(source_root)
            store.materialize_artifact(source_descriptor.descriptor_id, source_root)
            source_manifest = json.loads((source_root / "manifest.json").read_text(encoding="utf-8"))
            materialized[source_id] = (source_root, source_manifest)
        _, round_manifest = materialized[source_id]
        identity = round_manifest["identity"]
        factor_id = source["factor_instance_id"]
        candidate = next(
            (row for row in identity["candidates"] if row["selected_trial"]["factor_instance_id"] == factor_id),
            None,
        )
        if candidate is None:
            raise RuntimeError("EXISTING_FACTOR_DEFINITION_UNRESOLVED")
        template_payload = candidate["template"]
        template = parse_template(template_payload)
        selected = candidate["selected_trial"]
        goal_id = "trg_" + hash_payload({"protocol": identity["protocol_id"], "round": identity["round_number"]})
        explanation = _explanation(template.name, int(selected["orientation"]))
        definitions.append({
            "factor_instance_id": factor_id,
            "factor_template_id": candidate["template_id"],
            "template_name": template.name,
            "agent_round": identity["round_number"],
            "research_goal_id": goal_id,
            "research_decision_id": identity["decision_id"],
            "canonical_dsl": _dsl(template_payload["expression"]),
            "canonical_ast": template_payload["expression"],
            "input_features": _feature_names(template_payload["expression"]),
            "parameter_schema": template_payload["parameters"],
            "selected_parameters": selected["parameters"],
            "orientation": selected["orientation"],
            "values_are_oriented": source["values_are_oriented"],
            "factor_value_artifact_id": source["factor_values_id"],
            "unified_signal_id": signal_id,
            "source_round_lock_id": source_id,
            "structural_fingerprint": structural_fingerprint(template),
            "economic_hypothesis": candidate["rationale"],
            "risks": candidate["risks"],
            "human_explanation": explanation,
        })
    stable = {
        "schema_version": "existing-factor-definition-audit-v1",
        "provider_id": "tushare-pro-v1",
        "factor_count": len(definitions),
        "factors": definitions,
        "complete_formula_recovery": len(definitions) == 3,
        "legacy_reads": 0,
        "promotion_writes": 0,
    }
    if not stable["complete_formula_recovery"]:
        raise RuntimeError("EXISTING_FACTOR_DEFINITION_UNRESOLVED")
    return stable | {"audit_id": "efda_" + hash_payload(stable)}
