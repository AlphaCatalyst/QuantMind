# Codex Handoff

## Repository state

- QuantMind root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base before QM2-P0-002A2a1: `6a624a1dbaa8ba02073f3a5fc5b41805fc7481f0`
- Current latest commit: the commit containing this handoff; resolve it with
  `git log -1 --format=%H -- docs/quantmind2/context/HANDOFF.md`.
- Dirty before QM2-P0-002A2a1: no
- Unrelated dirty files: none
- Uncommitted work after the finalization commit: no

## Official Factor Lab source

- Root: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/`
- Source: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`
- Branch: `factor-lab/real-bounded-v7-orchestrator-v1`
- Commit: `c83192c2278767e03f008bc39197b1ba33bfb6a9`
- It remained read-only and clean during QM2-P0-002A2a1.

## Current position

- Architecture: QuantMind 2.0 Architecture v1, frozen.
- ADR-0009 and Research Decision Contract v1 are accepted architecture facts.
- They do not represent implemented Skill, Decision Validator, permission
  guard, state machine, budget controller, or Code Orchestrator runtime.
- Official V7 Factor Lab remains Python-first and does not yet satisfy the
  formal Decision-Control-Execution separation.
- Current task: `QM2-P0-002A2a1`, completed as a static core ORM mapping
  increment.
- Latest run: the immutable A2a1 run under
  `docs/quantmind2/implementation/runs/2026/2026-07/`.
- Persistence conclusion: future Ledger access should use SQLAlchemy 2.0 async,
  the shared master engine/session manager, API-owned metadata, versioned
  transaction-wrapped PostgreSQL SQL, and an explicit `quantmind2` schema.
  Deployment invocation, schema privileges, and an applied-version mechanism
  remain unconfirmed and must not be presented as implemented.
- Immutable Ledger domain objects, stable enums, structured errors,
  side-effect-free validators, Run state invariants, and direct relationship
  conflict checks now exist under `backend/services/engine/project_knowledge/domain/`.
- Synchronous Repository Protocols, query objects, stable errors, full
  in-memory graph-cycle checks, expected-version behavior, append-only details,
  stable history queries, and atomic-batch contract tests now exist.
- `InMemoryLedgerRepository` is a test double only; it is not production
  persistence or an implementation fact source.
- API-Base static ORM records now map only Task, Run, and RunRelationship to
  three explicit `quantmind2` table shapes. PostgreSQL DDL compiles without a
  database connection.
- Detail ORM tables, domain mappers, PostgreSQL Repository, actual tables and
  schema, migration, database transaction code, Manifest Parser/Indexer, Git
  consistency service, API, and UI do not exist.
- Recommended next task: `QM2-P0-002A2a2 — Ledger Detail ORM Mapping and Domain Mappers`;
  it has not started. Machine-readable task lists use parent
  `QM2-P0-002` due to the current schema pattern.

## Unconfirmed facts

- Concrete TongDaXin Provider implementation and capability contract.
- Long-term durable location for the official Factor Lab source.
- Operational invocation/order/checksum tracking for incremental SQL migrations.
- Permission and search-path support for an explicit `quantmind2` PostgreSQL schema.
- Isolated PostgreSQL fixture and CI PostgreSQL capability.
- Final artifact storage backend for large snapshot and ledger artifacts.
- A first-class Manifest field for non-correction relationships between runs.
- Concrete actor identity and permission policy for ResearchDecision.
- Persistent idempotency-key and semantic-duplicate policy.
- Exact Manifest v1 mapping for general Run relationships, logical repository
  identity, and the richer domain enums.
- PostgreSQL realization of Repository uniqueness, expected versions, DAG
  checks, and atomic batch behavior.
- SQLAlchemy 2.0.25 pinned-runtime DDL compilation and real PostgreSQL behavior;
  A2a1 static verification used an existing SQLAlchemy 2.0.51 environment.

## Constraints that must not be broken

- Do not replace LightGBM or Qlib.
- Do not put Python `factor_impl.py` in the v1 standard factor path.
- Keep Factor, Model, and Portfolio optimization separate.
- Keep Research Memory, Project Architecture Memory, and Implementation Ledger separate.
- Do not expose Frozen Test to Agent, Optimizer, or Campaign Memory.
- Do not treat plans, mocks, fixtures, fallbacks, or temporary evidence as implemented production facts.
- Do not modify accepted ADRs silently.
- Decision Layer may propose actions but cannot claim execution success.
- Code Orchestrator is the only controlled boundary to execution services.
- Execution services cannot autonomously choose the next research action.

## Next-session read order

Read `CONTEXT_INDEX.md`, Project Charter, Architecture v1, Current State, this
Handoff, task-related ADRs, Component Catalog, the latest relevant
Implementation Run, then current code, Git state, and tests. For research-loop
tasks, also read ADR-0009 and `RESEARCH_DECISION_CONTRACT_V1.md`.
