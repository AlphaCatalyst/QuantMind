import json
import os
import subprocess
import tempfile
from pathlib import Path

from .canonical import canonical_bytes
from .decision import decision_json_schema
from .errors import AgentContractError
from .models import ResearchAgentRequest, ResearchAgentResponse


def _feature(name): return {"type": "feature", "name": name}
def _parameter(name): return {"type": "parameter", "name": name}
def _constant(value): return {"type": "constant", "value": value}
def _binary(kind, left, right): return {"type": kind, "left": left, "right": right}
def _unary(kind, operand): return {"type": kind, "operand": operand}
def _rolling(kind, operand, window="window"): return {"type": kind, "operand": operand, "window": _parameter(window)}


def _template(name, description, parameters, expression):
    return {"schema_version": "1.0.0", "name": name, "description": description,
            "dataset_kinds": ["legacy_feature_matrix_v1"], "parameters": parameters,
            "expression": expression, "output": {"name": name}}


def _integer(name, default, minimum, maximum):
    return {"name": name, "type": "integer", "default": default, "minimum": minimum, "maximum": maximum}


def _number(name, default, minimum, maximum):
    return {"name": name, "type": "number", "default": default, "minimum": minimum, "maximum": maximum}


def baseline_proposals(iteration):
    vol_denom = _binary("add", _rolling("rolling_std", _feature("style_idio_vol_20")), _constant(0.000001))
    liquidity_rank = _unary("cs_rank", _rolling("rolling_mean", _feature("liq_volume_ratio_5")))
    variability_rank = _unary("cs_rank", _rolling("rolling_std", _feature("style_idio_vol_20")))
    blend = _binary("add", _binary("multiply", _parameter("weight"), liquidity_rank),
                    _binary("multiply", _binary("subtract", _constant(1.0), _parameter("weight")), variability_rank))
    proposals = [
        {"proposal_id": "momentum_quality", "hypothesis": "Persistent returns are stronger when idiosyncratic variability is low.",
         "economic_rationale": "Scaling persistence by variability seeks a more stable cross-sectional effect.",
         "template": _template("momentum_quality", "Variability-scaled momentum rank.", [_integer("window", 5, 5, 10)],
            _unary("cs_rank", _binary("divide", _rolling("rolling_mean", _feature("mom_ret_1d")), vol_denom))),
         "parameter_roles": {"window": "lookback_window"},
         "search_space": {"window": {"kind": "explicit_values", "values": [5, 10]}}},
        {"proposal_id": "liquidity_vol_blend", "hypothesis": "Liquidity participation and controlled variability jointly describe a useful cross-section.",
         "economic_rationale": "The blend balances trading participation against instability.",
         "template": _template("liquidity_vol_blend", "Weighted liquidity and variability ranks.",
            [_integer("window", 5, 5, 10), _number("weight", 0.5, 0.3, 0.7)],
            blend),
         "parameter_roles": {"window": "lookback_window", "weight": "factor_internal_weight"},
         "search_space": {"window": {"kind": "explicit_values", "values": [5, 10]},
                          "weight": {"kind": "explicit_values", "values": [0.3, 0.7]}}},
        {"proposal_id": "momentum_beta_shock", "hypothesis": "Short-term momentum changes scaled by beta variability identify cross-sectional shocks.",
         "economic_rationale": "The construction separates return change from broad systematic variability.",
         "template": _template("momentum_beta_shock", "Standardized momentum change relative to beta variability.",
            [_integer("periods", 1, 1, 3), _integer("window", 5, 5, 10)],
            _unary("cs_zscore", _binary("divide", {"type": "delta", "operand": _feature("mom_ret_1d"), "periods": _parameter("periods")},
                    _binary("add", _rolling("rolling_std", _feature("style_beta_20")), _constant(0.000001))))),
         "parameter_roles": {"periods": "lookback_window", "window": "lookback_window"},
         "search_space": {"periods": {"kind": "explicit_values", "values": [1, 3]},
                          "window": {"kind": "explicit_values", "values": [5, 10]}}},
        {"proposal_id": "liquidity_range", "hypothesis": "A wide recent liquidity range identifies changing market participation.",
         "economic_rationale": "Participation range captures a distinct temporal liquidity state.",
         "template": _template("liquidity_range", "Ranked rolling liquidity range.", [_integer("window", 5, 5, 10)],
            _unary("cs_rank", _binary("subtract", _rolling("rolling_max", _feature("liq_volume_ratio_5")),
                                      _rolling("rolling_min", _feature("liq_volume_ratio_5"))))),
         "parameter_roles": {"window": "lookback_window"},
         "search_space": {"window": {"kind": "explicit_values", "values": [5, 10]}}},
    ]
    converted = [{"proposal_id": item["proposal_id"], "template": item["template"],
        "parameter_search": {"parameter_roles": item["parameter_roles"], "search_space": item["search_space"]},
        "rationale": item["economic_rationale"], "expected_behavior": item["hypothesis"],
        "novelty_claim": "Operator and terminal structure differs from the admitted campaign structures.",
        "risks": ["adaptive development feedback can overfit"],
        "invalidation_conditions": ["insufficient finite coverage", "unstable cross-sectional relationship"]}
        for item in proposals]
    groups = {1: converted[:2], 2: converted[2:]}
    return groups.get(iteration, [])


class BaselineResearchAgent:
    provider_id = "quantmind_baseline"
    model_id = "deterministic-research-baseline-v1"

    def propose(self, request: ResearchAgentRequest):
        iteration = int(request.contract["iteration"])
        proposals = baseline_proposals(iteration)
        payload = {"schema_version": "1.0.0", "decision_id": f"baseline-{iteration}",
                   "goal_id": request.goal["goal_id"], "iteration": iteration,
                   "hypothesis_summary": "Deterministic bounded baseline proposal set.", "proposals": proposals,
                   "stop_recommendation": not proposals}
        return ResearchAgentResponse(json.dumps(payload, ensure_ascii=False), self.provider_id, self.model_id,
                                     {"deterministic": True})


class CodexResearchAgent:
    provider_id = "openai_codex_cli"

    def __init__(self, executable="codex", model="gpt-5.6-terra", timeout_seconds=180):
        self.executable = executable; self.model_id = model; self.timeout_seconds = timeout_seconds

    def propose(self, request: ResearchAgentRequest):
        prompt = ("You are the structure-proposal layer of a bounded quantitative research system. "
                  "Return exactly one JSON object matching the supplied schema. Do not include prose, paths, code, "
                  "data rows, labels, control decisions, or secrets. Propose only canonical DSL templates using the "
                  "allowed features/operators and explicit bounded search spaces.\nREQUEST:\n" +
                  canonical_bytes({"goal": request.goal, "memory": request.sanitized_memory,
                                   "contract": request.contract}).decode("utf-8"))
        env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
        with tempfile.TemporaryDirectory(prefix="qm2-agent-") as temp:
            schema_path = Path(temp) / "schema.json"; output_path = Path(temp) / "response.json"
            schema_path.write_bytes(canonical_bytes(decision_json_schema()))
            command = [self.executable, "exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check",
                       "--model", self.model_id, "--output-schema", str(schema_path),
                       "--output-last-message", str(output_path), prompt]
            try:
                completed = subprocess.run(command, cwd=temp, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=self.timeout_seconds, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise AgentContractError(f"Codex adapter unavailable: {type(exc).__name__}") from exc
            if completed.returncode != 0 or not output_path.is_file():
                raise AgentContractError(f"Codex adapter failed with exit code {completed.returncode}")
            if output_path.stat().st_size > 65536:
                raise AgentContractError("Codex adapter response exceeds 65536 bytes")
            raw = output_path.read_text(encoding="utf-8")
        return ResearchAgentResponse(raw, self.provider_id, self.model_id, {"usage_available": False})
