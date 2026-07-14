# Implementation Report: QM2-P0-001G

## 1. Task Summary

`QM2-P0-001G — Formalize Decision-Control-Execution Separation` accepts and
records the three-layer authority model, defines Research Decision Contract v1,
updates architecture/project memory, and extends bounded structural validation.
It implements no research, orchestration, execution, data, model, or backtest
runtime.

## 2. Goal

Make one boundary authoritative: Agent/Skill proposes structured research
actions; Code Orchestrator validates and controls authority/state/budget/
idempotency/dispatch; deterministic execution services return facts without
inventing research direction or promotion decisions.

## 3. Scope

- Accept ADR-0009.
- Define ResearchDecision fields, actions, validation pipeline, and boundaries.
- Add a bounded JSON Schema and valid example.
- Add the three layers to Architecture v1 without changing frozen DSL,
  Optimization, Validation, Registry, LightGBM, Qlib, or Frozen Test decisions.
- Record V7 gaps from direct code evidence.
- Update ADR index, terminology, component/issue/roadmap state, Current State,
  Handoff, context schemas, validator, tests, and this Implementation Run.
- Create one local commit and do not push.

## 4. Explicit Non-goals

No Skill runtime, Decision Validator code, Code Orchestrator v2, state machine,
permission service, budget service, database, API, DSL, Optimization,
Validation, Registry, TDX, LightGBM, Qlib, Risk, UI, dependency, lockfile,
configuration, or Factor Lab change.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base commit: `05c2db2b0797c6c173b4916d7f70dc97853dc5ec`
- QuantMind workspace: clean.
- Factor Lab: clean at `c83192c2278767e03f008bc39197b1ba33bfb6a9`.
- Unrelated dirty files: none.

## 6. Design Reasoning

### Why three layers, not two

Decision and execution alone leave authority, state, permission, budget,
idempotency, concurrency, retry, timeout, persistence, and recovery without a
single owner. The Control Layer is required to convert an untrusted proposal
into an approved deterministic task while preserving temporal truth.

### Why Code Orchestrator is control

Its product is a legal state transition and dispatch record, not a financial
hypothesis or factor value. It owns policy enforcement and process correctness,
so it belongs between research judgment and execution services.

### Why Skill cannot own the real loop

Skill and Agent outputs are probabilistic and replayable suggestions. They
cannot guarantee durable locks, exact budgets, idempotent retries, concurrency
control, or crash recovery. Markdown describes phases and stopping logic but is
not executable persistent state.

### Why execution cannot invent the next action

An execution service has validated inputs and returns measured facts. Allowing
it to revise formulas or initiate a round would merge evidence with hypothesis,
bypass permission and budget policy, and make results irreproducible.

## 7. Accepted Architecture Decision

ADR-0009 defines:

- Decision Layer: Research Skill, Campaign Orchestrator Skill, Research Agent.
- Control Layer: contract, validator, state/permission/budget/idempotency
  controls, Code Orchestrator, Experiment/Run coordinator.
- Execution Layer: deterministic DSL, compute, optimization, validation,
  Registry, Feature Snapshot, LightGBM, Signal, Qlib, and Risk services.

The core rule is that an Agent may propose what to try but cannot claim it
succeeded; execution can prove what happened but cannot invent the next
research direction; Code Orchestrator is the only controlled boundary.

## 8. ResearchDecision Contract

Fields are `decision_id`, `decision_schema_version`, `campaign_id`,
`experiment_id`, `round_id`, `actor_type`, `action`, `target_type`, `target_id`,
`rationale`, `evidence_refs`, `requested_parameters`, `requested_budget`,
`expected_outcome`, and `created_at`.

`decision_id` is an idempotency identity, not a Run ID. Evidence must already
exist and be visible. Parameters and budgets are suggestions, not authority.
The Decision cannot mutate Registry state, contain Frozen Test data, fabricate
execution IDs, call an execution service, or assert success.

Allowed actions:

- `CREATE_TEMPLATE`: propose a new parameterized draft, never final parameters.
- `REVISE_TEMPLATE`: create a child version, never overwrite the parent.
- `REQUEST_OPTIMIZATION`: request search roles/ranges/budget; controller owns
  Search Space and Optimizer owns Trials.
- `REQUEST_VALIDATION`: request validation of an immutable Instance; Agent
  cannot choose or inspect Frozen Test.
- `ARCHIVE_TEMPLATE`: request stopping future work without deleting history.
- `STOP_FAMILY`: stop one family in the Campaign and persist the reason.
- `STOP_CAMPAIGN`: request termination; controller seals state and Artifacts.

## 9. Decision Validation Pipeline

The contract specifies:

```text
ResearchDecision
→ Schema Validation
→ Actor Permission Check
→ Campaign State Check
→ Target State Check
→ Budget Check
→ Duplicate / Idempotency Check
→ Frozen Test Access Check
→ Experiment / Run Creation
→ Execution Service Dispatch
→ Result Persistence
→ Visible Result Summary
→ Research Memory Update
```

For every step the contract records inputs, outputs, failure state, owner,
retry policy, and whether it creates a Run. Only accepted Experiment/Run
creation makes a new logical Run; retries remain attempts under that lineage.

## 10. Permission, Budget, Frozen Test, and Idempotency Boundaries

- Permission: actor type alone does not authorize an action; Control Layer maps
  actor identity and target state to policy.
- Budget: Decision requests a ceiling; Budget Controller may reduce or reject
  it. Agent cannot expand it.
- Frozen Test: Decisions, Evidence, Visible Research Memory, Optimizer, and
  Agent loops cannot contain details. Only an authorized final Validation Run
  can access it.
- Idempotency: `decision_id` plus semantic fingerprint distinguishes exact
  replay from conflict. Exact replay returns prior control/result references;
  changed payload under the same ID conflicts.
- Optimization: structure revision and parameter Trial cannot be mixed. Code,
  not Agent, generates/deduplicates every window/weight/threshold Trial.

## 11. Current V7 Reality Check

| Concern | V7 path | Symbol | Current behavior | Target gap |
| --- | --- | --- | --- | --- |
| Bounded campaign | `agent_research/bounded_campaign_runner.py` | `BoundedCampaignRunner.run`, `choose_next_mode`, `_execute_session`, `_record_session` | Owns loop, budget, mode choice, CLI dispatch, persistence, stopping, and memory | No ResearchDecision admission; decision and control responsibilities remain combined |
| Minimal driver | `agent_research/minimal_research_driver.py` | `MinimalAgentResearchDriver._generate_validated`, `_materialize_session_candidate`, `_execute`, `_round_feedback` | Model generates complete source package; driver validates, materializes, executes, and feeds source/results forward | Candidate is not a pure proposal; research choice, execution request, and feedback are coupled |
| Prompt builder | `orchestrator/batch_draft_prompt_builder.py` | `BatchDraftPromptBuilder.build_minimal_draft_prompt`, `build_prompt` | Requests `factor_impl.py` ABI and embeds extensive research heuristics/memory | Prompt is Python-first and Agent selects structure plus concrete values |
| Candidate contract | `productization/agent_candidate_schema_v2.py` | `candidate_schema_v2` | Requires `factor_impl.py`, FactorSpec, rationale, primitive/mutation/capability traces | No canonical ResearchDecision object or DSL-only proposal boundary |
| Capability policy | `productization/agent_capability_router.py` | `route_capabilities_for_candidate` | Maps failures to primitives/mutations and factor implementation evidence | Useful donor policy, but still targets Python implementation construction |
| Execution gateway | `orchestrator/execution_backend_interface.py` | `ExecutionBackendGateway.execute` | Selects backend, enforces Docker-only candidate execution, returns structured result | Controlled execution exists, but dispatch is not preceded by Decision Validator/Run admission |
| Session control | `productization/bounded_v7_session_orchestrator.py` | `BoundedV7SessionOrchestrator`, `run_registered_candidate`, `run_registered_round` | Explicit state, checkpoint, locks, stages, repository/gate handling | Strong donor controls but Candidate registration is not ResearchDecision validation |
| Validation | `evaluation/hardened_evaluator.py` | `HardenedEvaluator.run_hardened_evaluation` | Returns research-only metrics and gate preview | No target Validation service or isolated Frozen Test authority |
| Memory | `memory/memory_store.py` | `MemoryStore` | Persists JSON/JSONL factor/family/hypothesis/failure/repair memory | No Control Layer visibility filter tied to formal Result/Artifact authority |

These are code-confirmed observations, not claims that the target architecture
already exists.

## 12. Files Added

- `ADR-0009-decision-control-execution-separation.md`: accepted authority model.
- `RESEARCH_DECISION_CONTRACT_V1.md`: proposal/action/pipeline contract.
- `research_decision_v1.schema.json`: bounded machine-readable contract.
- `research_decision_v1.example.json`: valid optimization-request example.
- This Implementation Report and adjacent Manifest.

## 13. Files Modified

- Architecture v1: added three layers and feedback flow.
- ADR indexes: registered accepted ADR-0009.
- Terminology: added eight boundary terms with negative definitions.
- Component Catalog: added planned Skill, Decision Validator, and Code
  Orchestrator; expanded V7 limitations.
- Known Issues: added the unresolved V7 semantic-coupling issue.
- Roadmap: recorded this contract task and next QM2-P0-002A1 audit.
- Current State/Handoff: recorded accepted contract versus unimplemented code.
- Context/Manifest schemas: minimally admitted accurate committed handoff and
  QM2-P0-002A1 identifiers.
- Validator/tests: added ADR, architecture, contract, positive example, invalid
  action, missing rationale, and prohibited Frozen Test field checks.

## 14. Architecture Impact

Architecture v1 gains an authority envelope around the existing research
chain. Frozen DSL, Optimization, Validation, Registry, LightGBM, Qlib, data,
identity, and Frozen Test decisions are unchanged.

## 15. Security Impact

The contract reduces future authority ambiguity and explicitly blocks Frozen
Test leakage and direct Agent-to-execution calls. No runtime enforcement or
permission code is implemented yet.

## 16. Data Lineage Impact

No data or research Artifact changed. The contract requires future Decisions,
Runs, Results, summaries, and memory updates to preserve separate lineage.

## 17. Validation and Test Results

- Context validator: 13 structural/repository checks passed.
- Targeted unittest: 13 tests passed, including three required negative
  ResearchDecision cases.
- JSON parse check: all 17 JSON files present before this Run parsed.
- `git diff --check`: passed with no output.
- Factor Lab status/HEAD: clean and unchanged.

The validator supports only the JSON Schema keywords used by local contracts;
it does not claim full generic Draft 2020-12 or semantic date-time validation.

## 18. Boundary and Failure Handling

- Illegal Decision: rejected before Run creation.
- Duplicate Decision: exact replay resolves prior outcome; conflicting payload
  is rejected.
- Over budget: rejected or reduced by Budget Controller, never expanded by
  Agent.
- Invalid state: rejected without target mutation.
- Frozen Test access: rejected and not summarized to Agent/Skill/Memory.
- Direct Agent-to-Qlib attempt: permission/dispatch rejection before Qlib.
- Execution service auto-next-round attempt: no authority or dispatch path;
  only a new Decision can request another action.
- Persistence outcome unknown: reconcile before retry; do not duplicate side
  effects or fabricate success.

These are accepted future control behaviors, not implemented runtime claims.

## 19. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| ADR-0009 | accepted | Created and indexed | ADR file and both indexes | Passed |
| Three-layer Architecture | explicit layers | Architecture v1 updated | Three section headings and flow | Passed |
| ResearchDecision Contract | fields and proposal semantics | Contract plus Schema/example | Architecture files | Passed |
| Seven actions | full semantics | Conditions, checks, state, failure, side effects documented | Contract section 3 | Passed |
| Validation Pipeline | all prescribed stages | 12-step table with ownership/retry/Run behavior | Contract section 4 | Passed |
| Skill/Markdown/Code boundary | explicit | Documented | Contract section 5 | Passed |
| Parameter/Frozen Test boundary | explicit | Documented | Contract sections 6–7 | Passed |
| V7 code gap | code-backed | Nine concerns recorded | Source paths/symbols above | Passed |
| Context truth | contracts not code | Planned statuses retained | Catalog, State, Handoff | Passed |
| Tests | positive/negative | 13/13 passed | unittest output | Passed |
| No business/Factor Lab change | none | Documentation/tool/test only | Git scope and Factor Lab status | Passed |

## 20. Known Limitations

- This is architecture and contract only.
- No ResearchDecision Python/domain model exists.
- No executable Decision Validator, actor permission policy, or Frozen Test
  enforcement exists.
- No Skill runtime exists.
- Code Orchestrator v2 and its persistent state/budget/idempotency controls are
  not implemented.
- V7 remains Python-first and does not consume ResearchDecision.
- Runtime state-machine, concurrency, retry, and outcome reconciliation remain
  future work.
- JSON Schema validation is a bounded local subset.

## 21. Unresolved Questions

- Exact actor identity, authentication, delegation, and permission policy.
- Semantic fingerprint rules across Decision revisions.
- Persistent storage and uniqueness mechanism for Decisions and attempts.
- Whether a rejected/revision-required proposal becomes an Artifact or only a
  Ledger event.
- Visible summary redaction policy for restricted validation stages.
- Durable migration boundary for selected V7 donor components.

## 22. Compatibility and Migration

No runtime interface changes. Existing LightGBM, Qlib, Factor Lab, data, and
business APIs are untouched. The context-schema enum/pattern changes are
backward-compatible additions needed to record committed status and the exact
next subtask.

## 23. Rollback

Revert the single commit containing this Run. That removes ADR-0009, contract,
schema/example, architecture/context updates, and validator/test extensions.
No database, data, service, model, Qlib, UI, dependency, or environment rollback
is required.

## 24. Git and Self-Reference

At Run generation the workspace is uncommitted, so Manifest `result_commit` is
null and `task_status` is `completed_uncommitted`. A commit cannot embed its own
hash. After the required commit, the containing commit is resolved with:

```text
git log -1 --format=%H -- docs/quantmind2/implementation/runs/2026/2026-07/QM2-P0-001G-20260714T142514Z-05c2db2/manifest.json
```

No amend or follow-up self-hash commit is permitted.

## 25. Recommended Next Task

Only `QM2-P0-002A1 — Ledger Persistence Mechanism Audit and Domain Contract`.
It should independently audit persistence facts and define the Ledger domain
contract. No part of that audit or implementation was started here.

## 26. Artifact Index

- ADR-0009.
- Research Decision Contract v1.
- ResearchDecision v1 Schema and example.
- Updated Architecture v1 and project-memory documents.
- This report and adjacent manifest.
