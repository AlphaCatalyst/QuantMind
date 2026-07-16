# Codex Handoff

## Repository state

- QuantMind root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base before QM2-P0-002B1: `0353435a3c1fb4b1469a5ab32462a1a010999872`
- Current latest commit: the commit containing this handoff; resolve it with
  `git log -1 --format=%H -- docs/quantmind2/context/HANDOFF.md`.
- Dirty before QM2-P0-002B1: no
- Unrelated dirty files: none
- Uncommitted work after the finalization commit: no

## Official Factor Lab source

- Root: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/`
- Source: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`
- Branch: `factor-lab/real-bounded-v7-orchestrator-v1`
- Commit: `c83192c2278767e03f008bc39197b1ba33bfb6a9`
- Its source bytes remained read-only during QM2-P0-002B1. The supplied `/tmp`
  root had no `.git` directory, so the expected branch/commit and Git-clean
  claims could not be reverified locally; a before/after content digest was
  used for the task boundary instead.

## Current position

- Architecture: QuantMind 2.0 Architecture v1, frozen.
- ADR-0009 and Research Decision Contract v1 are accepted architecture facts.
- They do not represent implemented Skill, Decision Validator, permission
  guard, state machine, budget controller, or Code Orchestrator runtime.
- Official V7 Factor Lab remains Python-first and does not yet satisfy the
  formal Decision-Control-Execution separation.
- Current task: `QM2-P0-002B1`, completed as the forward-indexable Manifest v2
  producer and final Ledger infrastructure closure.
- Completed task name: `QM2-P0-002B1 — Manifest v2 Producer and Forward Indexability`.
- Latest run: `QM2-P0-002B1-20260716T135059Z-0353435` under
  `docs/quantmind2/implementation/runs/2026/2026-07/`.
- Persistence conclusion: future Ledger access should use SQLAlchemy 2.0 async,
  the shared master engine/session manager, API-owned metadata, versioned
  transaction-wrapped PostgreSQL SQL, and an explicit `quantmind2` schema.
  Migration invocation and rollback are implemented. The async PostgreSQL
  Repository and explicit UoW now reuse the shared manager's engine/sessionmaker;
  Repository methods never own transaction completion.
  Production deployment and final schema privilege policy remain unconfirmed.
- Immutable Ledger domain objects, stable enums, structured errors,
  side-effect-free validators, Run state invariants, and direct relationship
  conflict checks now exist under `backend/services/engine/project_knowledge/domain/`.
- Synchronous Repository Protocols, query objects, stable errors, full
  in-memory graph-cycle checks, expected-version behavior, append-only details,
  stable history queries, and atomic-batch contract tests now exist.
- `InMemoryLedgerRepository` is a test double only; it is not production
  persistence or an implementation fact source.
- API-Base static ORM records now map Task, Run, RunRelationship, ChangedFile,
  ChangedSymbol, TestExecution, ImplementationArtifact, ComponentReference,
  ArchitectureDecisionReference, Limitation, and RecommendedTask to eleven explicit
  `quantmind2` table shapes. PostgreSQL DDL compiles without a database connection.
- All current target ORM mappings and explicit bidirectional Domain mappers
  exist. Migration `0001` and the async PostgreSQL Repository/UoW are complete.
  Exact replay/conflict, expected version, finalization, append-only children,
  recursive-CTE/advisory-lock DAG admission, typed history, and atomic batch
  behavior pass isolated PostgreSQL 15 tests, including independent Sessions.
  Manifest Parser/Indexer, Git consistency service, trusted binding, and CLI
  now exist. API and UI do not exist.
- Limitation does not foreign-key Component Catalog; RecommendedTask does not
  foreign-key, create, or execute a future Task. Neither historical annotation
  has an ORM update method, and no annotation data was written.
- Mapper Contract v1 covers all eleven objects. The complete explicit Mapper
  package implements pure conversion, safe errors, round trips, and frozen
  `changed-file-v1` / `changed-symbol-v1` identities. It has no database runtime.
- Manifest v2 is the default for future Runs. It separates logical repository
  identity from execution path, declares Mapper/identity versions, and carries
  every current Ledger Domain family. ADR-0010 and the Indexer still require an
  explicit trusted binding. Manifest v1 remains immutable compatibility only.
- All eleven objects now have explicit `to_record` and `from_record` functions.
  Stored ChangedFile/Symbol technical IDs are recomputed and verified; explicit
  parent Run IDs cannot disagree with Domain values. Task/Run version behavior
  remains unchanged. Parser, binding, Git consistency, and Indexer exist; API
  and UI do not.
- At the B1 base, 17 historical Manifest v1 Runs exist: 16 pass mandatory Git
  evidence and zero form complete Domain Bundles. It did not invent missing
  Task/child facts and did not claim a historical backfill. The 001F Run fails
  result-commit consistency. A complete synthetic bundle passed isolated
  PostgreSQL insert, replay, immutable-conflict, and rollback verification.
- ADR-0010 requires explicit caller binding from logical repository ID to local
  worktree; v1 absolute paths remain informational execution evidence.
- The B1 v2 Run passes committed Git consistency and complete Domain Bundle
  construction, and is fully indexable with all eleven families in isolated
  PostgreSQL. Exact replay and immutable-conflict rollback are verified.
- Ledger infrastructure is closed. Production deployment/backfill, API/UI,
  watcher, webhook, and daemon remain absent.
- Recommended next task: `QM2-P0-003 — TongDaXin Provider Reality Audit and Dataset Snapshot Entry`.

## Unconfirmed facts

- Concrete TongDaXin Provider implementation and capability contract.
- Long-term durable location for the official Factor Lab source.
- Production execution-role permission policy for the explicit `quantmind2` schema.
- CI capability and scheduling for the opt-in disposable PostgreSQL test.
- Final artifact storage backend for large snapshot and ledger artifacts.
- Concrete actor identity and permission policy for ResearchDecision.
- Persistent idempotency-key and semantic-duplicate policy.
- SQLAlchemy 2.0.25 / asyncpg 0.29 pinned-runtime behavior;
  A2a1/A2a2a/A2a2b1/A2a2b2 static verification used an existing SQLAlchemy
  2.0.51 environment and A3 used SQLAlchemy 2.0.51 / asyncpg 0.31.0.
- Production schema privileges and CI execution remain unverified; local
  ordering, checksums, rollback, reapply, parity, and cleanup are verified.

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
