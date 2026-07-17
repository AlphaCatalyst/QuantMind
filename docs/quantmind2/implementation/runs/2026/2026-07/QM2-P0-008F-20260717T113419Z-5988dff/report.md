# QM2-P0-008F Implementation Report

## Task Summary

Completed Agent Provider enablement without changing the ResearchDecision,
Campaign, DSL, Optimization, Development, Registry, promotion, or Frozen-Test
contracts. The real Codex CLI returned a valid structured Decision and one
external-AI Proposal completed the existing research-only Campaign path.

## Goal

Diagnose the two immutable QM2-P0-008 Codex exit-code-1 failures, make the
smallest Provider-adapter correction, and complete one admitted external
Campaign through existing QuantMind 2.0 services.

## Scope

- CodexResearchAgent structured-output transport, safe diagnostics, bounded
  call evidence, and parameter-usage prompt clarification.
- Direct adapter tests and context invariants.
- One real external Codex Campaign, exact-existing replay, Project Memory,
  this Manifest v2 Run, and related regression verification.

## Explicit Non-goals

No Campaign redesign, ResearchDecision relaxation, alternate Provider,
Baseline substitution, arbitrary Python factor path, Frozen access, formal
Validation, promotion, model, signal, Qlib backtest, database, API/UI,
dependency, lockfile, runtime-configuration, or Factor Lab change.

## Preflight State

- Repository/branch: `quantmind-main`, `master`.
- Base commit: `5988dff70f1e86a0ba4478182331dcd3109f929b`.
- Worktree before: clean; unrelated dirty files: none.
- Codex CLI: `/Applications/ChatGPT.app/Contents/Resources/codex`, version
  `0.145.0-alpha.18`; `codex login status` reported ChatGPT login.
- Presence-only environment: `OPENAI_API_KEY` absent, `CODEX_HOME` absent,
  `HOME` present, `PATH` present. No authentication content was read.
- Official Factor Lab: 18 non-cache files, canonical content digest
  `c25252a40ff9d5f74c596af9faa4c15a599f15ce0031f719a42cd2f04a80409c`.

## Existing Production Reality

QM2-P0-008 remains immutable partial evidence: Campaign
`rc_c9c7a980a3df50e3f549422fbd52b326128eb00da5a5473e8870b5ec893bca43`
made two real calls using Codex CLI `0.145.0-alpha.18` and requested model
`gpt-5.6-terra`; both exited 1 before structured output, admitted zero
Proposals, spent zero Trials, and changed no Registry state.

## What Changed

- Provider schema transmission now adds explicit JSON `type` to `const` and
  homogeneous `enum` nodes. This is semantic normalization for the CLI and
  does not mutate the formal ResearchDecision schema.
- Codex runs with JSONL events and no color. The adapter classifies CLI,
  authentication, model, flag, schema, prompt, permission, sandbox, timeout,
  rate-limit, internal, parse, and unknown failures.
- Error summaries redact secret-like values, URLs, and absolute temporary/user
  paths before crossing the boundary.
- Successful responses record CLI/model/hash/size/exit/repair/event evidence
  and actual CLI usage when present.
- The Provider prompt restates existing parameter-to-AST role rules and the
  current pre-Signal prohibition on `signal_threshold`.
- Project Memory now records QM2-P0-008F as complete and recommends only
  QM2-P0-009.

## Why It Changed

Layered probes showed that plain Codex calls and both the CLI default
`gpt-5.6-sol` and requested `gpt-5.6-terra` worked. A `const`-only property in
Probe B was rejected with Provider code `invalid_json_schema`; the same shape
exists in the formal transport schema. Adding the required explicit type made
minimal structured JSON and the formal ResearchDecision schema succeed. The
ResearchDecision parser and all execution controls were already correct.

## Files Changed

Production changes are limited to
`backend/services/engine/research_campaign/agent.py`. Direct tests are in
`backend/services/tests/test_research_campaign_codex_agent.py`. Project Memory,
two context schemas, their validator/test assertions, and this Run are the only
other changes. The Manifest is the exact repository-relative inventory.

## Important Classes / Functions / Documents

- `CodexResearchAgent`, `CodexProviderError`, `_provider_schema`, `_events`,
  `_failure_code`, `_safe_summary`, `_cli_version`.
- `test_research_campaign_codex_agent.py`.
- Current State, Handoff, Component Catalog, Known Issues, and Roadmap.

## Runtime Flow

```text
Codex CLI capability probes
-> semantic Provider-schema normalization
-> strict ResearchDecision parser
-> existing novelty and DSL admission
-> existing Factor Optimization
-> contaminated 2025 Development evaluation
-> existing Registry research_registered
-> exact-existing Campaign replay
```

## Architecture Impact

No architectural boundary changed. Agent still proposes structure only;
Control validates and budgets; existing services execute. Formal Validation,
Frozen Test, and promotion remain outside the Campaign.

## API Changes

No HTTP or public service API changed. `CodexProviderError` is an internal
adapter diagnostic subtype of the existing `AgentContractError`.

## Database Changes

None. No database or migration was used.

## Configuration / Environment Changes

None. No dependency or lockfile changed. Runtime evidence is under
`/private/tmp/qm2-p0-008f-*` and is not production storage.

## Security Impact

The subprocess environment remains allowlisted and excludes API credentials.
The CLI runs ephemeral, read-only, and outside the repository. Output remains
size-bounded strict JSON. Diagnostics are classified and redacted; complete
prompt, memory, stderr, authentication data, and secrets are not persisted.

## Data Lineage Impact

Successful external Campaign
`rc_0b13d7f235ac948a10c97092c6ce3bbad99ecdefc2c20c93c3648644a5d9401c`
produced Result
`rcr_19183f859c9bbe7949ec9e3c07f9870d8e7c47e9140211cc47b9de429db3d3ca`
and Decision
`rd_0efd9c55f10579a99050edfb4cd6b5964e600fab92bf23fff7bc42f4ebf08e96`.
Proposal `liquidity_beta_contrast` completed Study
`fos_eb355bffa4b1ea9279b80d5c6f5166c3cb8a96123b33202fa46eabb393ba56be`
with four successful Trials and Development result
`der_d8e4951edc3a9483306e4040b1cd8ab92d78ff9bd87cb5194c1baffa2e853bbb`.
Registry advanced from `frs_436f4a96...f2d9` to
`frs_7ab0a844...01054` with exactly one `research_registered` entry.

The call evidence records CLI `0.145.0-alpha.18`, requested/effective model
`gpt-5.6-terra` from explicit adapter configuration, exit 0, no repair,
request SHA-256 `2aa4e08a...23ed`, response SHA-256
`5391e357...a38`, and 4,175 response bytes. Usage came from the CLI event and
was not estimated.

## Tests Executed

- Layered live Probes A through D: plain text, supported minimal JSON, formal
  ResearchDecision, and full Campaign request.
- Adapter/contract focused tests: 36 passed.
- Related Campaign, Registry, Validation, Optimization, DSL, Dataset Snapshot,
  Manifest/Indexer and Context regression: 216 passed, 9 skipped after one
  corrected stale context assertion.
- Context focused tests: 38 passed; Context Bootstrap: 39 checks passed.
- Successful Campaign artifact validation, Registry reload and exact-existing
  replay: passed; replay Agent calls: zero.
- JSON parsing, `py_compile`, no-Frozen scan, `git diff --check`, final Factor
  Lab digest and Git scope checks: passed.

## Test Results

All final relevant tests pass. Skips are pre-existing environment-gated tests.
No test was skipped, xfailed, removed, or relaxed to enable the Provider.

## Expected vs Actual

- Expected external structured call: passed.
- Expected at least one admitted Proposal: one admitted; one additional
  Proposal was correctly rejected for an unused lookback parameter.
- Expected Optimization/Development/Registry: four Trials, one contaminated
  Development result, one research entry.
- Expected promotion/approved/active/Frozen: all zero/false.
- Expected replay without Provider cost: exact-existing, zero Agent calls.
- Recommended 24-Trial hard Campaign budget was retained for the successful
  run; only four Trials were consumed.

## Known Limitations

- CLI calls experienced transient reconnects and took roughly two minutes;
  the adapter remains synchronous and single-process.
- Provider prompt clarification improves semantic compliance but does not make
  model output trusted; one generated Proposal was still rejected by Control.
- 2025 feedback is contaminated adaptive research only. The new Factor has no
  fresh formal Validation or promotion eligibility.
- Runtime Campaign/Registry artifacts live under `/private/tmp` and are not a
  durable artifact backend.

## Compatibility / Migration Notes

Formal ResearchDecision schema, parser, Campaign artifact format, IDs, budgets,
old Campaigns, Registry policy, DSL, Optimization, Development and Validation
are unchanged. Existing adapter callers keep the same constructor and response
type; `usage_summary` now contains actual usage and safe provider-call evidence.

## Rollback Notes

Revert the single QM2-P0-008F commit. Runtime evidence can be discarded. No
database, source Dataset, old Registry Snapshot, historical Campaign, Factor
Lab file, dependency, configuration, or credential needs rollback.

## Remaining Work

Apply a fresh immutable formal Validation protocol to eligible Agent-generated
Factors without treating contaminated Development feedback as independent
evidence.

## Recommended Next Task

Only `QM2-P0-009 — Fresh Validation Protocol for Agent-generated Factors`.

## Git / Workspace State

This Run is produced against base `5988dff`. It is completed uncommitted before
the authorized independent commit and noncanonical until Git verification.
No amend or push is performed.

## Artifact Index

- This report and self-reference-free Manifest v2.
- Successful Campaign and Registry under
  `file:///private/tmp/qm2-p0-008f-external4/`.
- Diagnostic Probe metadata under `file:///private/tmp/qm2-008f-probe-*`.
- Historical QM2-P0-008 Report, Manifest and Campaign artifacts remain
  byte-for-byte unchanged.
