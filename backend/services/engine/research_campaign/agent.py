import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .canonical import canonical_bytes
from .decision import decision_json_schema
from .errors import AgentContractError
from .models import ResearchAgentRequest, ResearchAgentResponse


_SECRET = re.compile(
    r"(?i)(authorization|api[ _-]?key|access[ _-]?token|secret|password)"
    r"(\s*[:=]\s*)([^\s,}\"]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[^\s,}\"]+")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


class CodexProviderError(AgentContractError):
    """Safe, classified failure from the external Codex CLI boundary."""

    def __init__(self, code, summary, *, exit_code=None):
        self.code = code
        self.safe_summary = summary
        self.exit_code = exit_code
        super().__init__(f"{code}: {summary}")


def _provider_schema(value):
    """Add types required by Codex structured output without changing semantics."""
    if isinstance(value, list):
        return [_provider_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _provider_schema(item) for key, item in value.items()}
    if "type" in result:
        return result
    values = [result["const"]] if "const" in result else result.get("enum")
    if not values:
        return result
    kinds = {_json_type(item) for item in values}
    if len(kinds) == 1 and None not in kinds:
        result["type"] = kinds.pop()
    return result


def _json_type(value):
    if isinstance(value, bool): return "boolean"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "number"
    if isinstance(value, str): return "string"
    if value is None: return "null"
    return None


def _events(stdout):
    result = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(event, dict):
            result.append(event)
    return result


def _safe_summary(value):
    rendered = str(value or "").replace("\x00", " ")
    rendered = _SECRET.sub(r"\1\2<redacted>", rendered)
    rendered = _BEARER.sub("Bearer <redacted>", rendered)
    rendered = _URL.sub("<url>", rendered)
    rendered = re.sub(r"/(?:Users|private/tmp|tmp)/[^\s,}\"]+", "<path>", rendered)
    return " ".join(rendered.split())[:300] or "no safe provider detail"


def _failure_detail(events, stderr):
    for event in reversed(events):
        if event.get("type") == "turn.failed":
            error = event.get("error")
            return error.get("message") if isinstance(error, dict) else error
    errors = [event.get("message") for event in events if event.get("type") == "error"]
    return errors[-1] if errors else stderr


def _failure_code(detail, returncode):
    text = str(detail or "").lower()
    checks = (
        ("authentication_required", ("not logged in", "authentication required", "unauthorized", "invalid api key")),
        ("unsupported_model", ("model_not_found", "unsupported model", "does not exist", "model is not supported")),
        ("unsupported_flag", ("unexpected argument", "unknown option", "unrecognized option", "unsupported flag")),
        ("invalid_schema", ("invalid_json_schema", "invalid schema", "text.format.schema")),
        ("invalid_prompt_input", ("invalid prompt", "prompt is required", "input is too long")),
        ("workspace_permission", ("permission denied", "not a trusted directory", "workspace permission")),
        ("sandbox_failure", ("sandbox", "seatbelt")),
        ("provider_rate_limit", ("rate_limit", "rate limit", "too many requests", "quota")),
        ("provider_internal_error", ("internal server error", "server_error", "service unavailable")),
        ("response_parse_error", ("failed to parse", "invalid json response", "response parse")),
    )
    for code, needles in checks:
        if any(needle in text for needle in needles):
            return code
    return "unknown_provider_failure" if returncode else "response_parse_error"


def _cli_version(executable, env):
    try:
        return subprocess.check_output(
            [executable, "--version"], env=env, stderr=subprocess.DEVNULL,
            text=True, timeout=10,
        ).strip()[:120]
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


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
                  "allowed features/operators and explicit bounded search spaces. Every declared parameter must be "
                  "referenced by the expression AST and parameter_search; use lookback parameters only in rolling "
                  "window or delta periods nodes and factor weights as arithmetic operands. Do not declare unused "
                  "parameters. The expression root must be an operator, not a constant or bare feature, and must "
                  "contain at least one allowed feature. A valid lookback use has the exact shape "
                  "{\"type\":\"rolling_mean\",\"operand\":{\"type\":\"feature\",\"name\":\"mom_ret_1d\"},"
                  "\"window\":{\"type\":\"parameter\",\"name\":\"window\"}}. For this pre-Signal Campaign, "
                  "use only lookback_window and factor_internal_weight; signal_threshold is reserved. Use two "
                  "explicit search values per parameter so each proposal remains small.\nREQUEST:\n" +
                  canonical_bytes({"goal": request.goal, "memory": request.sanitized_memory,
                                   "contract": request.contract}).decode("utf-8"))
        env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
        cli_version = _cli_version(self.executable, env)
        with tempfile.TemporaryDirectory(prefix="qm2-agent-") as temp:
            schema_path = Path(temp) / "schema.json"; output_path = Path(temp) / "response.json"
            schema_path.write_bytes(canonical_bytes(_provider_schema(decision_json_schema())))
            command = [self.executable, "exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check",
                       "--model", self.model_id, "--color", "never", "--json", "--output-schema", str(schema_path),
                       "--output-last-message", str(output_path), prompt]
            try:
                completed = subprocess.run(command, cwd=temp, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=self.timeout_seconds, check=False)
            except FileNotFoundError as exc:
                raise CodexProviderError("cli_not_found", "Codex CLI executable was not found") from exc
            except subprocess.TimeoutExpired as exc:
                raise CodexProviderError("timeout", f"Codex CLI exceeded {self.timeout_seconds} seconds") from exc
            except OSError as exc:
                raise CodexProviderError("unknown_provider_failure", _safe_summary(type(exc).__name__)) from exc
            events = _events(completed.stdout)
            if completed.returncode != 0 or not output_path.is_file():
                detail = _failure_detail(events, completed.stderr)
                raise CodexProviderError(_failure_code(detail, completed.returncode), _safe_summary(detail),
                                         exit_code=completed.returncode)
            if output_path.stat().st_size > 65536:
                raise CodexProviderError("response_parse_error", "Codex adapter response exceeds 65536 bytes",
                                         exit_code=completed.returncode)
            raw = output_path.read_text(encoding="utf-8")
        completed_event = next((event for event in reversed(events) if event.get("type") == "turn.completed"), {})
        usage = completed_event.get("usage") if isinstance(completed_event.get("usage"), dict) else None
        request_bytes = canonical_bytes({"goal": request.goal, "memory": request.sanitized_memory,
                                         "contract": request.contract})
        evidence = {"provider_id": self.provider_id, "cli_version": cli_version,
                    "requested_model": self.model_id, "effective_model": self.model_id,
                    "model_resolution_source": "explicit_adapter_configuration",
                    "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
                    "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                    "response_size_bytes": len(raw.encode("utf-8")), "exit_code": completed.returncode,
                    "repair_attempted": "repair_instruction" in request.contract,
                    "event_count": len(events), "last_event_type": events[-1].get("type") if events else None}
        return ResearchAgentResponse(raw, self.provider_id, self.model_id,
                                     {"provider_call": evidence, "usage": usage})
