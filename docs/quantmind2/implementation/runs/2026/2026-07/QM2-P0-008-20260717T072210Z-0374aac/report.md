# QM2-P0-008 Implementation Report

## 1. Task Summary

Implemented Agent Research Campaign v1 across Decision, Control, and existing Execution boundaries. The deterministic real-data Baseline Campaign completed. The real Codex CLI adapter was invoked under the bounded contract, but both permitted attempts returned exit code 1 before structured output, so the task is correctly `partial` rather than completed.

## 2. Goal

Create a runnable, budgeted Agent loop that proposes canonical DSL structures, validates and deduplicates them, reuses Factor Optimization, evaluates only contaminated 2025 Development feedback, and registers research-only entries without exposing Frozen evidence or granting promotion authority.

## 3. Scope

- Closed Research Goal, Research Decision, Agent and Campaign contracts.
- Deterministic baseline plus real Codex CLI adapter.
- Sanitized memory, untrusted-response parser, novelty gate, budgets, retry and event state machine.
- Existing DSL/Optimization dispatch, isolated Development evaluator, optional research evidence in Registry Entry.
- Immutable Campaign artifacts, CLI, schemas, documentation, tests and Project Memory.

## 4. Explicit Non-goals

No formal Validation, Frozen evaluation, promotion, approval, activation, arbitrary Python, structure evolution, LightGBM, Qlib, signal, portfolio, backtest, API/UI, database, daemon, dependency installation, lockfile change, or Factor Lab modification.

## 5. Preflight State

- Repository ID/root: `quantmind-main` at the requested QuantMind root.
- Branch/base: `master` / `0374aaceab7c8b14e26e3d21ff5ed35366795384`.
- Working tree: clean; unrelated dirty files: none.
- Codex CLI: present as app executable; version `0.145.0-alpha.18`.
- DeepSeek/OpenAI API environment variables: absent by presence-only check; no value was printed.
- Factor Lab official 18-file non-cache digest before work: `c25252a40ff9d5f74c596af9faa4c15a599f15ce0031f719a42cd2f04a80409c`.
- Existing Python environment with pandas/numpy/pyarrow/pytest was reused; nothing was installed.

## 6. What Changed

Added `backend/services/engine/research_campaign/`, a local CLI, three runtime contracts, three JSON Schemas, a real Goal example and three focused test modules. Extended `RegistryEntry` with optional quarantined research evidence while preserving old Entry payloads and Snapshot identities. Updated context contracts, validation, tests, Current State, Handoff, Catalog, Known Issues and Roadmap.

## 7. Why It Changed

Existing DSL, Optimization, Development data and Registry capabilities had no compliant Agent loop. This task adds the missing control boundary while keeping structure proposal separate from execution and keeping contaminated feedback separate from formal evidence.

## 8. Files Changed

Changes are confined to the research Campaign package/CLI/tests/contracts, the minimal backward-compatible Registry Entry/parser extension, Project Memory, context validation and this Run. The Manifest is the complete repository-relative file inventory.

## 9. Important Classes / Functions / Documents

- `ResearchGoal`, `ResearchAgent`, `ResearchCampaignBudget`, `CampaignConfig`.
- `BaselineResearchAgent`, `CodexResearchAgent`, `parse_decision`, `structural_fingerprint`.
- `run_campaign`, `evaluate_development`, `CampaignJournal`, `validate_campaign`.
- `RegistryEntry.research_evidence` and the compatible parser/payload path.
- `AGENT_RESEARCH_CAMPAIGN_V1.md`, `RESEARCH_MEMORY_VIEW_V1.md`, and `RESEARCH_DECISION_RUNTIME_V1.md`.

## 10. API Changes

No HTTP API changed. A local Python package and offline CLI were added.

## 11. Database Changes

None. No database was contacted and no migration was introduced.

## 12. Configuration / Environment Changes

None. Runtime artifacts are under `/private/tmp/qm2-p0-008-final3` and `/private/tmp/qm2-p0-008-external4`. No dependency, lockfile, runtime configuration or secret was changed.

## 13. Runtime Flow

```text
ResearchGoal -> SanitizedMemory -> ResearchAgent -> strict ResearchDecision
-> Control validation/novelty/budget -> existing DSL and Optimization
-> fixed pre-2025 orientation -> contaminated 2025 Development evaluation
-> research_registered Registry entries -> immutable Campaign Memory
```

The Agent never calls execution services or Registry. Execution never calls the Agent.

## 14. Architecture Impact

Realizes the Campaign-specific Decision/Control/Execution slice without replacing the broader planned Experiment Manager or generic Code Orchestrator. Research Goal, Decision, Template, Study/Trial, Values, Development result, Registry Entry/Snapshot and Campaign artifacts remain distinct.

## 15. Security Impact

Provider input excludes paths, rows, labels, raw Registry files, credentials, private data and formal evidence details. Provider output is size-bounded strict JSON, closed-schema parsed, content screened, never executed, and retried once at most. Codex runs ephemeral/read-only with an allowlisted environment. No secret or Authorization header is stored. Frozen evaluator imports/calls are absent from the Campaign package.

## 16. Data Lineage Impact

Baseline Campaign `rc_4970d1419d17d1327b2092c7ff85cb52d680488555c6408ec3a8ef571219cd5f` binds Goal `rg_b2382653...4b045a`, Dataset Snapshot `ds_dd1defb...e338f`, Validation Dataset `vd_1ac71a8...c3ed62`, original Registry `frs_436f4a96...f2d9`, four Template/Study/Trial/Values/Development chains and successor Registry `frs_d40bfd74...584718`. Direction is fixed from 2022–2024. The observed Development period is exactly 2025-01-02..2025-12-30.

## 17. Tests Executed

- Focused Campaign tests: 29 passed.
- Registry compatibility regression: 16 passed.
- First full related regression: 215 passed, 9 skipped, 3 context-contract failures caused by the previous exact-next-task invariant.
- Context fixes: 21 passed; Context Bootstrap 39 checks passed.
- Final full related regression: 218 passed, 9 skipped, 0 failed.
- Final strict research-evidence ID and Campaign/Registry targeted rerun: 45 passed.
- Final Baseline real Campaign: three iterations, three Agent calls, four admitted Proposals, 12 successful Trials, four Development evaluations, four research entries; validation and exact-existing replay passed.
- Real Codex Campaign: two bounded calls, both Provider exit code 1; immutable partial artifact validated with zero admitted Proposal/Trial/Registry change.
- `py_compile`, 57 JSON parses, no-Frozen-runtime-import scan, and `git diff --check`: passed.
- Factor Lab digest after work: `c25252a40ff9d5f74c596af9faa4c15a599f15ce0031f719a42cd2f04a80409c`, identical to preflight.

## 18. Test Results

All final code and relevant regression tests are green. Nine skips are pre-existing environment-gated tests. Intermediate context failures were fixed only by advancing Project Memory/schema assertions to the truthful partial task and exact next task; no research behavior was weakened.

## 19. Known Limitations

- External-AI completion is absent: Codex CLI returned exit code 1 before structured output on both bounded attempts.
- The Campaign is offline/single-process with local immutable artifacts; no database/API/UI, worker concurrency or durable object store.
- Development feedback is contaminated and adaptive only; no Agent-generated Factor has fresh formal Validation.
- Search uses existing deterministic explicit-value Optimization; threshold search remains constrained by existing DSL/Optimization support.
- No model, signal, Qlib backtest or promotion consumer is included.

## 20. Compatibility / Migration Notes

Legacy Registry Entries omit the optional `research_evidence` field on serialization, so all existing Snapshot identities and readers remain valid. New research entries require the exact quarantine flags. Other DSL, Optimization, Validation, Ledger, LightGBM and Qlib contracts are unchanged.

## 21. Rollback Notes

Revert the single QM2-P0-008 commit and delete optional `/private/tmp/qm2-p0-008-*` runtime directories. No database, source Dataset, old Registry Snapshot, Factor Lab file, configuration or dependency requires rollback.

## 22. Remaining Work

Enable a real structured Provider response and complete an admitted external-AI Campaign. Only after that should fresh formal Validation be applied to Agent-generated research entries.

## 23. Recommended Next Task

Only `QM2-P0-008F — Agent Provider Enablement and External Campaign Completion`. It must not rewrite the Campaign or weaken safety rules; it should diagnose Provider exit 1 and produce one real structured Decision that completes the existing bounded path.

## 24. Git / Workspace State

This Run is produced against base `0374aac`. Task status is `partial_uncommitted`, completion level is partial, and canonical status is noncanonical. One independent commit `feat(qm2): add agent research campaign v1` is required. No amend or push is authorized. Final post-commit state is recorded in the task response.

## 25. Artifact Index

- Research Campaign package, CLI, Goal/Decision/Campaign Schemas and three contracts.
- Baseline runtime Campaign `rc_4970d141...19cd5f`, Result `rcr_3b292352...c950964`, four Studies and Registry `frs_d40bfd74...584718` under `/private/tmp/qm2-p0-008-final3`.
- External partial Campaign `rc_c9c7a98...3bca43`, Result `rcr_608045df...fb987` under `/private/tmp/qm2-p0-008-external4`.
- This self-reference-free Manifest v2 and Report.
