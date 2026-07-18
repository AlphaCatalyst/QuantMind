import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from backend.services.engine.research_campaign.agent import (
    CodexProviderError,
    CodexResearchAgent,
    _provider_schema,
    _safe_summary,
)
from backend.services.engine.research_campaign.canonical import canonical_bytes
from backend.services.engine.research_campaign.decision import decision_json_schema
from backend.services.engine.research_campaign.models import ResearchAgentRequest
from backend.services.engine.research_campaign.parameter_contract import (
    proposal_parameter_contract_summary,
)


def request(repair=False):
    contract = {
        "iteration": 1,
        "maximum_trials": 6,
        "parameter_contract": proposal_parameter_contract_summary(),
    }
    if repair:
        contract["repair_instruction"] = {
            "proposal_index": 0,
            "error_code": "parameter_declared_but_unused",
            "field_path": "proposals[0].template.parameters",
            "declared_parameters": ["window"],
            "used_parameters": [],
            "unused_parameters": ["window"],
            "search_space_parameters": ["window"],
            "role_assignments": {"window": "lookback_window"},
            "allowed_fix_actions": ["remove unused parameter"],
        }
    return ResearchAgentRequest({"goal_id": "rg_test"}, {"safe": True}, contract)


def patch_version(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: "codex-cli test\n")


def test_provider_schema_adds_explicit_types_without_changing_contract():
    schema = _provider_schema(decision_json_schema())

    def walk(value):
        if isinstance(value, dict):
            if "const" in value or "enum" in value:
                assert "type" in value
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(schema)
    assert decision_json_schema()["properties"]["schema_version"] == {"const": "1.0.0"}
    search = schema["$defs"]["parameter_search"]["items"]
    assert search["additionalProperties"] is False
    assert set(search["required"]) == {"name", "role", "kind", "values"}
    assert search["properties"]["kind"]["const"] == "explicit_values"
    assert "step" not in schema["$defs"]["template"]["properties"]["parameters"]["items"]["properties"]


def test_success_uses_safe_argv_environment_and_records_evidence(monkeypatch):
    patch_version(monkeypatch)
    observed = {}

    def run(command, **kwargs):
        observed.update(command=command, kwargs=kwargs)
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text('{"ok":true}', encoding="utf-8")
        stdout = "\n".join((json.dumps({"type": "thread.started"}),
                             json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12}})))
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-boundary")
    response = CodexResearchAgent(executable="codex-test", model="model-test").propose(request())
    command = observed["command"]
    assert command[:2] == ["codex-test", "exec"]
    assert "--json" in command and "--output-schema" in command and "--color" in command
    assert "Every declared parameter" in command[-1]
    assert "generated parameter contract" in command[-1]
    assert "signal_threshold is unavailable" in command[-1]
    assert "provider_transport_valid_minimal_examples" in command[-1]
    assert "declared_parameters == used_parameters" in command[-1]
    assert Path(observed["kwargs"]["cwd"]).name.startswith("qm2-agent-")
    assert "OPENAI_API_KEY" not in observed["kwargs"]["env"]
    assert observed["kwargs"]["stdin"] is subprocess.DEVNULL
    evidence = response.usage_summary["provider_call"]
    expected_request = canonical_bytes({"goal": request().goal, "memory": request().sanitized_memory,
                                        "contract": request().contract})
    assert evidence == {
        "provider_id": "openai_codex_cli",
        "cli_version": "codex-cli test",
        "requested_model": "model-test",
        "effective_model": "model-test",
        "model_resolution_source": "explicit_adapter_configuration",
        "request_sha256": hashlib.sha256(expected_request).hexdigest(),
        "response_sha256": hashlib.sha256(b'{"ok":true}').hexdigest(),
        "response_size_bytes": 11,
        "exit_code": 0,
        "repair_attempted": False,
        "event_count": 2,
        "last_event_type": "turn.completed",
    }
    assert response.usage_summary["usage"] == {"input_tokens": 12}


@pytest.mark.parametrize(("detail", "code"), [
    ("authentication required", "authentication_required"),
    ("model_not_found", "unsupported_model"),
    ("unexpected argument '--bad'", "unsupported_flag"),
    ("invalid_json_schema", "invalid_schema"),
    ("invalid prompt", "invalid_prompt_input"),
    ("permission denied", "workspace_permission"),
    ("sandbox policy failed", "sandbox_failure"),
    ("rate_limit exceeded", "provider_rate_limit"),
    ("internal server error", "provider_internal_error"),
    ("failed to parse response", "response_parse_error"),
    ("unclassified provider failure", "unknown_provider_failure"),
])
def test_failed_event_is_classified(monkeypatch, detail, code):
    patch_version(monkeypatch)

    def run(command, **kwargs):
        event = {"type": "turn.failed", "error": {"message": detail}}
        return subprocess.CompletedProcess(command, 1, json.dumps(event), "ignored fallback")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(CodexProviderError) as caught:
        CodexResearchAgent().propose(request())
    assert caught.value.code == code
    assert caught.value.exit_code == 1


def test_missing_cli_and_timeout_are_distinct(monkeypatch):
    patch_version(monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(CodexProviderError, match="cli_not_found"):
        CodexResearchAgent().propose(request())
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(args[0], kwargs["timeout"])))
    with pytest.raises(CodexProviderError, match="timeout"):
        CodexResearchAgent(timeout_seconds=7).propose(request())


def test_safe_summary_redacts_secrets_urls_and_paths():
    rendered = _safe_summary("api key=secret-value Bearer credential https://example.invalid /Users/person/private/file")
    assert "secret-value" not in rendered
    assert "credential" not in rendered
    assert "example.invalid" not in rendered
    assert "/Users/" not in rendered
    assert "<redacted>" in rendered and "<url>" in rendered and "<path>" in rendered


def test_missing_or_oversized_response_is_rejected(monkeypatch):
    patch_version(monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""))
    with pytest.raises(CodexProviderError) as missing:
        CodexResearchAgent().propose(request())
    assert missing.value.code == "response_parse_error"

    def oversized(command, **kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text("x" * 65537)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", oversized)
    with pytest.raises(CodexProviderError, match="exceeds 65536"):
        CodexResearchAgent().propose(request())


def test_repair_evidence_is_derived_from_request_contract(monkeypatch):
    patch_version(monkeypatch)

    def run(command, **kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text("{}")
        return subprocess.CompletedProcess(command, 0, json.dumps({"type": "turn.completed"}), "")

    monkeypatch.setattr(subprocess, "run", run)
    response = CodexResearchAgent().propose(request(repair=True))
    assert response.usage_summary["provider_call"]["repair_attempted"] is True
    assert response.usage_summary["usage"] is None
