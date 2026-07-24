from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.services.engine.research_campaign.agent import (
    CodexProviderError, _cli_version, _events, _failure_code, _failure_detail,
    _provider_schema, _safe_summary,
)
from backend.services.engine.research_campaign.canonical import canonical_bytes


def call_structured_codex(*, prompt: str, schema: dict, model: str = "gpt-5.6-terra",
                          timeout_seconds: int = 300, executable: str = "codex") -> tuple[dict, dict]:
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    cli_version = _cli_version(executable, env)
    with tempfile.TemporaryDirectory(prefix="qm2-technical-agent-") as temp:
        schema_path = Path(temp) / "schema.json"
        output_path = Path(temp) / "response.json"
        schema_path.write_bytes(canonical_bytes(_provider_schema(schema)))
        command = [
            executable, "exec", "--ephemeral", "--sandbox", "read-only",
            "--skip-git-repo-check", "--model", model, "--color", "never",
            "--json", "--output-schema", str(schema_path),
            "--output-last-message", str(output_path), prompt,
        ]
        try:
            completed = subprocess.run(
                command, cwd=temp, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=timeout_seconds, check=False,
            )
        except FileNotFoundError as exc:
            raise CodexProviderError("cli_not_found", "Codex CLI executable was not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexProviderError("timeout", f"Codex CLI exceeded {timeout_seconds} seconds") from exc
        events = _events(completed.stdout)
        if completed.returncode != 0 or not output_path.is_file():
            detail = _failure_detail(events, completed.stderr)
            raise CodexProviderError(
                _failure_code(detail, completed.returncode), _safe_summary(detail),
                exit_code=completed.returncode,
            )
        raw = output_path.read_bytes()
        if len(raw) > 131072:
            raise CodexProviderError("response_parse_error", "Agent response exceeds 131072 bytes")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CodexProviderError("response_parse_error", "Agent response is not JSON") from exc
    event = next((item for item in reversed(events) if item.get("type") == "turn.completed"), {})
    evidence: dict[str, Any] = {
        "provider_id": "openai_codex_cli", "requested_model": model,
        "effective_model": model, "cli_version": cli_version,
        "request_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_size_bytes": len(raw), "exit_code": completed.returncode,
        "event_count": len(events), "usage": event.get("usage"),
    }
    return value, evidence
