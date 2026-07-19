# Codex Handoff

## Current authority and next task

- Current task is `QM2-P0-014`; implementation is complete pending its single
  commit and post-commit Ledger Planner verification.
- Active provider is `tushare-pro-v1`; legacy provider
  `quantmind-production-feature-snapshots-v1` is `retired_and_purged` and may
  not be used by formal runtime. Read ADR-0011 and
  `docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json` before data work.
- Fixed universe IDs are `tu500_fb547c...24e8c` and
  `tu100_078e6609...2c526`; formal Qlib view is `tqv_c489efe4...941ff`.
- Canonical research start is empty Genesis Registry
  `trg_0e23d0c7...1d309`. Do not restore old Factor Registry metrics or old
  Research Memory effectiveness labels.
- Artifact Store Inventory `sai_2e7ce672...02040` is healthy with Missing 0,
  Unreferenced 0 and legacy Artifact count 0. The purge is irreversible for
  the deleted local data; rollback means re-fetching/rebuilding Tushare data or
  restoring old data from an independent backup, not changing the authority
  record silently.
- Only recommended next task:
  `QM2-P0-015 — Re-run Fixed-100 Agent Factor Experiment on Tushare Authority`.

## Repository state

- QuantMind root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base before QM2-P0-012F: `32dc6af0be24468da997e9e32e9627e23d360987`
- Current latest commit: the commit containing this handoff; resolve it with
  `git log -1 --format=%H -- docs/quantmind2/context/HANDOFF.md`.
- Dirty before QM2-P0-012F: no
- Unrelated dirty files: none
- Uncommitted work after the QM2-P0-006 commit: no

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

- `QM2-P0-011BF` is a completed diagnostic with a blocked backtest outcome.
  The original 35.17% is exactly 3,822 NaNs / 10,867 observed rows. A full
  100-symbol x 111-date grid has 4,055 missing cells / 11,100 (36.53%): 222
  from two wholly absent symbols (`SH600837`, `SH601989`), 11 local row
  absences, and 3,822 missing `style_idio_vol_20` values across all 98 observed
  symbols and 39 dates.
- Both locked Factor Values artifacts reproduce exactly and all Factor DSL,
  orientation, normalization and combination steps add zero NaNs. The derived
  Qlib view reaches 2026-06-24, has 100 instruments and adds no join, date,
  symbol or score loss. This is an upstream Feature-data-quality boundary, not
  a Qlib or combination defect.
- No safe repair was made: recreating the missing authoritative Feature would
  change research data semantics without sufficient provenance. The 20% gate
  remains unchanged, Qlib rerun calls are zero, and original 011B artifacts
  remain immutable.
- An unchanged, out-of-scope Artifact Store concurrent-import test exposed a
  timing-sensitive Receipt ID conflict in the final broad regression and two
  focused reruns; the archived base tree passed one isolated run. Do not call
  it fixed or attribute it to the signal audit. No production Store concurrency
  code was changed in 011BF.
- Store Audit `sma_33979ef...a9b64`, blocked follow-up
  `hbf_fc927bc...6e1f1`, and Inventory `sai_39e8526...42f2` are current.
  Store state is 97 artifacts / 372 blobs, healthy, zero missing/unreferenced;
  cold recovery and exact-existing replay passed.
- Current task is `QM2-P0-011BF`; status is `blocked`. No successor task is
  authorized by this contract.

- `QM2-P0-011B` is a truthful partial historical diagnostic. Fixed Universe
  `ful_e899c9ce...df2651`, Dataset `fuhd_734dae...f95fb`, final Historical
  Experiment `hae_5e4b11ba...3fedd` and Qlib result
  `qbr_b8be0692...f9dc0` are immutable Store artifacts.
- Four formal external rounds used four Agent calls and 14 factor-only Trials;
  a discarded preflight dataset run used four more calls, keeping the task at
  its eight-call ceiling. Round 2 admitted no Proposal and Round 4 next-year
  RankIC was negative. The Agent assessment is `mixed`.
- Two candidates were locked using evidence only through 2024. 2025 completed
  with about 2.6% net return for each candidate but about -4.4/-4.5 percentage
  points fixed-universe excess. 2026H1 Qlib execution was rejected by the
  unchanged signal-quality gate (35.17% NaN versus 20% maximum). Do not fill,
  reselect, relax the gate or call this Fresh evidence.
- Inventory `sai_8ee9085f...c4ee` has 93 artifacts / 357 blobs. Cold recovery
  and exact replay passed with zero Agent/Optimization/Qlib/Registry calls and
  zero new artifacts/blobs. Production Registry and Fresh control identities
  did not change. No successor task is authorized; ask for an explicit task
  that addresses or accepts the 2026H1 coverage boundary.
- Final read-only verification found no Factor Lab source file at its official
  `/tmp` path (only a `__pycache__` entry). The earlier normalized digest cannot
  be reverified; this task did not write or consume that tree.

- `QM2-P0-012F` aligned the external Agent with the unchanged Proposal
  parameter contract. Campaign `rc_4432a5d3...c04b56` completed after one real
  `openai_codex_cli` / `gpt-5.6-terra` call and no repair. It produced Decision
  `rd_142a0fa4...ab9838`, Template `ft_115afad9...70aef1`, Study
  `fos_22c2f3b6...e8a84`, six successful Trials, selected Factor Values
  `fv_937e5df1...571a`, Development result `der_b8669e6...9a92e`, and Registry
  successor `frs_9f61af9b...92052`.
- The new Registry has 20 entries and adds one `research_registered` factor;
  promotion / approved / active remain 0 / 0 / 0. The 2025 Development result
  is contaminated adaptive research only and creates no Validation, Frozen,
  Fresh or promotion evidence.
- Current Inventory is `sai_820983db...e5e68`, 79 artifacts / 339 blobs,
  healthy with zero missing and zero unreferenced. Empty-cache graph recovery
  passed. Exact replay returned the identical Campaign/Result/Descriptor with
  zero Agent, Optimization and Registry-write calls and no Store delta.
- Three earlier P0-012F Goal/Campaign identities are preserved as immutable
  diagnostics: `rc_29c2c3c9...c3655` (Provider rejected nested `oneOf`),
  `rc_01e211af...fcc47` (nested `anyOf`) and `rc_0cd43051...4cfe7`
  (`uniqueItems`). Each stopped after the fixed two-call ceiling and created no
  Decision, Trial or Registry entry. They explain why Provider transport uses
  the supported explicit-values profile while Control retains the full formal
  Search Space validation.
- P0-012 Campaign `rc_16bf5717...b7ea` remains immutable partial with two
  calls and no admission. Do not describe P0-012F as changing that result.
- Latest Run after this task is the `QM2-P0-012F` Run under
  `docs/quantmind2/implementation/runs/2026/2026-07/`. The only next task is
  `QM2-P0-011B — Fixed-100-Universe 2019—2026 Agent Iteration and Historical
  Backtest`. Conditional `QM2-FV-001` remains forbidden until 60 mature
  post-lock trading dates exist.

- `QM2-P0-012` is a truthful partial production dry run. Campaign
  `rc_16bf5717...b7ea` made exactly two real Codex CLI calls (the second was
  the sole repair); both exited 0 but failed the unchanged Proposal parameter
  contract. It produced no Decision, admitted Proposal, Trial, Development
  result or Registry successor. Do not retry it, widen its budget, or describe
  it as an AI factor discovery.
- The partial Campaign is immutable in Store descriptor
  `sad_2e42bc...7b18b`. Current Inventory is `sai_b0c03807...70320` with 66
  artifacts / 287 blobs, healthy and zero unreferenced. Cold recovery and exact
  replay passed; replay called Agent/Optimization zero times and wrote no
  Registry or Store artifact. Canonical Registry remains
  `frs_c2ef675c...0237b5`, 19 entries, with promotion / approved / active =
  0 / 0 / 0. Fresh remains 0/60.
- Latest Run is `QM2-P0-012-20260717T180925Z-ded5c10`. The only next task is
  `QM2-P0-011B — 2019—2026 Historical Diagnostic Backtest`. Conditional
  `QM2-FV-001` stays forbidden until 60 mature post-lock dates exist.

- `QM2-P0-011` cuts the formal research runtime to `store_required`. Read
  `ARTIFACT_BACKED_RUNTIME_V1.md`, `ARTIFACT_RUNTIME_RECOVERY_V1.md` and
  `ARTIFACT_RUNTIME_ROLLBACK_V1.md` before changing runtime behavior.
- In QM2-P0-011, Store-only empty-cache recovery passed for Factor Values, Optimization,
  Validation, Frozen, canonical Registry, both Campaigns and Fresh Admission.
  External Campaign replay called neither Agent nor Optimization and wrote no
  Registry state. Its Store baseline was healthy at 65 artifacts / 280 blobs on
  Inventory `sai_a0b9e618...55d312`.
- Canonical Registry remains 19 entries with promotion / approved / active =
  0 / 0 / 0. Fresh remains `awaiting_first_fresh_date` at 0/60; no Fresh Result
  exists. Legacy local mode is emergency-only and cannot publish formal results.
- This predecessor state is preserved for historical context.

- `QM2-P0-010` adds persistent Research Artifact Store v1. Current inventory
  is `sai_a0b9e6183a7bed95d9dbcce918a19c9e2f63a67ffbc7617a2091b7a37955d312`;
  reachability plan is `rap_f3aca751ad751c976888fd9b464f9f56dd4913339b226786c0c3a7ef65ccc247`.
- All 65 current reachable artifacts migrated with zero missing sources and
  healthy integrity. Read `RESEARCH_ARTIFACT_STORE_V1.md`, migration and
  recovery contracts before runtime cutover work.
- The original immutable `QM2-P0-010` Implementation Run remains
  Git-inconsistent and non-indexable because only its own Manifest is absent
  from `integrity.git_changed_paths` and `git_added_paths`. The independently
  verified Git inventories contain 42 changed and 28 added paths. Its 41
  business ChangedFiles remain correct: the Manifest is excluded and the
  Report is included.
- `QM2-P0-010F` publishes correction evidence only, with one `corrects`
  relationship. It changes no Store behavior or research artifact identity.
  Latest run: `QM2-P0-010F-20260717T161330Z-77f5b1f`.
- Runtime cutover successor `QM2-P0-012` is the partial dry run recorded above;
  Fresh evaluation is still 0/60 and must not run.

- Architecture: QuantMind 2.0 Architecture v1, frozen.
- ADR-0009 and Research Decision Contract v1 are accepted architecture facts.
- They do not represent implemented Skill, Decision Validator, permission
  guard, state machine, budget controller, or Code Orchestrator runtime.
- Official V7 Factor Lab remains Python-first and does not yet satisfy the
  formal Decision-Control-Execution separation.
- Previous task `QM2-P0-010F` recorded immutable Git inventory correction
  evidence for the Artifact Store implementation Run.
- Completed predecessor: `QM2-P0-008 — Agent Research Campaign v1` remains
  historically partial because its external attempts failed.
- Latest correction run: `QM2-P0-010F-20260717T161330Z-77f5b1f` under
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
- Dataset Snapshot v1 now provides explicit Provider requests, immutable Raw
  Capture, deterministic normalization, blocking quality checks, atomic
  Parquet publication, identity/hash validation and a read-only consumer seam.
- Real TDX is not verified: legacy scripts depend on absent `tqcenter`; pytdx
  and mootdx are absent; source volume/amount units are not evidenced. No real
  Snapshot ID exists. Fake Snapshots are test-only and explicitly identified.
- Existing training remains on feature snapshots and Qlib remains on its
  separate binary view. No production consumer switch occurred.
- The production feature source is explicitly bound read-only as logical source
  `quantmind-production-feature-snapshots-v1`. The latest complete 2025 bytes
  hash to `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
- Real Legacy Snapshot
  `ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`
  contains 5,931 rows, 100 deterministic symbols, 60 observed dates, all 152
  legal research features and zero labels. Default readers cannot expose labels,
  forbidden or unknown columns.
- Production loader parity passed with only its existing numeric-to-float32 cast
  allowlisted. Source and Snapshot values/NaN masks otherwise match exactly.
- Factor DSL must consume validated Snapshot terminals through
  `load_feature_matrix`; it must not read the legacy root or labels directly.
- New v2 Runs must omit their own Manifest from `changed_files`; the Manifest
  remains in integrity Git inventories. Report remains a ChangedFile/Artifact.
- Historical 003L is immutable and uses the generic compatibility warning
  `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED`; its Manifest is not mapped to a
  ChangedFile, while every other Git/hash check remains strict.
- The 003LF test-only assertion now uses `AnalyzedRun.evidence.consistent` and
  `evidence.warnings`; all four opt-in PostgreSQL tests pass without a
  production-code change. Ledger remains closed.
- `QM2-P0-004 — Factor DSL v1 on Real Legacy Feature Dataset Snapshot` now
  provides a closed typed JSON AST, strict feature/parameter
  admission, canonical Template and Instance identities, deterministic
  Snapshot-only execution, and immutable Factor Values artifacts.
- Five parameter instances passed on the real 003L Snapshot with 5,931 rows
  each and exact replay. This is compute evidence, not factor validation,
  Registry status, model value, signal or backtest evidence.
- Factor Optimization v1 now admits only declared `lookback_window` and
  `factor_internal_weight` parameters, enumerates deterministic finite Study
  products under trial/failure budgets, executes or replays existing Factor
  Values, evaluates mechanical quality, and atomically publishes immutable
  Study/Trial artifacts.
- Real Studies
  `fos_969d431e553ad29d1d7bcdd4d912a6ab92471b5c4faf833a18abe2607baa1cb2`
  and `fos_ac8ea3539ba0db8faa4dc223750d649584da270244ec022638faef8bdfeb5a19`
  completed 5 plus 9 trials; all 14 were mechanically eligible and exact Study
  replay passed. Their ordering is not predictive evidence.
- No label, IC/RankIC, return, model, Qlib, signal, backtest, structure
  evolution, random/Bayesian, model, or portfolio optimization was introduced.
- Factor Validation v1 audited current production label behavior and created
  Dataset `vd_1ac71a8b...c3ed62`, full-period Factor Values for all 14 Trials,
  Result `fvr_b9f247e4...c51ab0`, Selection `fvs_f679a630...819e9c`, and Frozen
  Result `fvt_734478fc...21c787`. Four Trials passed Validation gates; only the
  top three were frozen. 2025 remains quarantined and was not used in formal
  metrics. Frozen results did not feed selection or Optimization.
- The original Run remains Git-inconsistent: its immutable Manifest records
  `11db9e00e1babe...` for the pre-change `handoff_v1.schema.json`, while raw
  bytes from base commit `07a3df9e...` hash to `11db9e00e1aabe...`.
  `QM2-P0-006F` preserves that history and adds the correct value as a strict
  evidence-correction Artifact with a `corrects` relationship. It does not
  rewrite the old Run or change Dataset, Validation Result, Selection or
  Frozen Result identities.
- Factor Registry v1 registers 14 real Instances in Snapshot
  `frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9`
  under Policy `fpp_6ca41655ea0ec5692ef2799674ef743a8bf91a6cf58718e124163bf033e255a3`.
  Statuses are 10 Validation-rejected, one passed-not-selected, and three
  Frozen-rejected; candidates, approved and active are all zero.
- Registry is immutable offline artifact authority only. No Registry database,
  API/UI, durable backend, active Factor, LightGBM/Qlib consumption or backtest
  was introduced. Agent may read filtered failure history but cannot mutate,
  approve, activate, or access Frozen details.
- Baseline Campaign `rc_4970d141...19cd5f` produced four new research-only
  Registry entries after 12 real Trials and contaminated 2025 Development
  evaluation. Registry before/after: `frs_436f4a96...f2d9` →
  `frs_d40bfd74...584718`; no promotion candidate, approved, or active entry
  was added.
- External Codex Campaign `rc_c9c7a98...3bca43` is partial: two bounded real
  CLI attempts returned exit code 1 before structured output, so it spent no
  Trial budget and changed no Registry state. This must not be described as an
  external AI factor proposal.
- QM2-P0-008F identifies `invalid_json_schema` as the old root cause and keeps
  the ResearchDecision contract unchanged while adding Provider-schema type
  normalization and classified safe diagnostics in `CodexResearchAgent`.
- External Campaign `rc_0b13d7f...d9401c` used Codex CLI
  `0.145.0-alpha.18` with explicit `gpt-5.6-terra`, admitted one Proposal,
  completed four Trials and contaminated Development evaluation, and published
  one `research_registered` entry in Registry `frs_7ab0a844...01054`.
  Exact-existing replay made zero additional Agent calls; promotion candidate,
  approved, active, Validation evidence and Frozen evidence additions are zero.
- Baseline and External Campaign Registry snapshots are sibling branches. The
  unique current canonical Registry is
  `frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4`
  with 19 Entries and reconciliation
  `frr_9112702e368326365d6f4adb144633c7d0cf3ae59baa61ed76270ae86e93cb32`.
- Fixed Development-evidence admission result
  `fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab`
  admits three of five Agent-generated candidates; the external factor is not
  admitted. This is not Fresh Validation or Frozen evidence.
- QM2-P0-009 locked three admitted candidates on market date 2026-07-17 under
  Candidate Lock `fvcl_716d7465...63c7b`, Protocol `fvp_93163e1b...5a867`,
  Exposure Ledger `rdel_56d95b7...5f5ff`, and Watermark `fdw_3459fb5...aa248`.
  The real source ends 2026-06-24; eligible count is zero and status is
  `awaiting_first_fresh_date`. Registry successor `frs_c2ef675...0237b5` adds
  awaiting-data evidence without changing main status. No historical backfill
  or real Fresh result exists.
- The original QM2-P0-009 Run remains Git-inconsistent/non-indexable because 23
  business ChangedFiles were omitted. QM2-P0-009F records the complete 35-entry
  Git-derived inventory as immutable correction evidence with `corrects`; it
  does not edit the original Run or research controls.
- Recommended next task: `QM2-P0-011B — 2019—2026 Historical Diagnostic Backtest`.

## Unconfirmed facts

- Authorized `tqcenter` runtime/client and daily-bar volume, amount, adjustment,
  timeout, rate-limit and license semantics remain unavailable, but no longer
  block the Legacy Snapshot to Factor DSL route.
- The active production database feature allowlist was not queried; the provider
  is bound to the checked-in 152-enabled-feature catalog.
- The adjacent 2025 source sidecar is stale relative to current Parquet bytes.
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
