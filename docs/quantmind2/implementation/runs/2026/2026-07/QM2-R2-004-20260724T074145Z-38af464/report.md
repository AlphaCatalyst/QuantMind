# QM2-R2-004 Implementation Report

## 1. Task summary

Task `QM2-R2-004 — Autonomous Technical Feature Factory and Archetype-Aware
Alpha Program v1` implemented the bounded technical Terminal Feature factory,
froze Technical Feature Catalog v2, implemented pre-registered monotonic and
top-tail Alpha evaluation, and formally ran `technical_feature_factory_001`
and `technical_alpha_program_002`.

The formal Program completed with nine locked-validation objects and zero
Validation Survivors. This is the governed terminal result; no threshold,
archetype, budget or retrospective reporting boundary was relaxed.

## 2. Goal and scope

The change adds:

- a label-free, bounded Feature Agent contract and Feature Factory;
- a formal grammar over already-authorized DSL operators;
- PIT, numerical-quality, persistence, structural and signal-novelty gates;
- immutable research Terminal Feature materializations and Catalog v2;
- Alpha Archetype pre-registration;
- three Alpha research Lanes with default-first and optional local rescue;
- archetype-specific adaptive and locked-validation statistics;
- global Benjamini–Hochberg FDR control;
- Artifact Store persistence, cold recovery, resume and exact replay;
- CLIs, tests, frozen contract and Project Memory.

## 3. Explicit non-goals

No financial, industry, news, intraday, northbound, margin, Dragon-Tiger or
Fresh data was used. No operator was added only to satisfy a proposal. No full
Factor Search, Strategy Optimization, Combined Optimization, Promotion,
production activation, market-data fetch, database/API/UI, dependency,
lockfile, LightGBM or Qlib replacement was performed.

## 4. Preflight state

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base: `38af464809d2bec14ea9284a4e2ba6e634f61d3b`
- Worktree: clean
- Unrelated dirty files: none
- Official Factor Lab remained read-only.

## 5. Search-space audit and Feature Factory architecture

The current canonical DSL evaluator formally supports the factory operations
`add`, `subtract`, `multiply`, `safe_divide`, `negate`, `abs`, `clip`, `lag`,
`delta`, `rolling_mean`, `rolling_std`, `rolling_min` and `rolling_max`.
`rolling_sum`, `rolling_corr` and `log1p` do not have an authorized current
implementation and are rejected as `FEATURE_OPERATOR_NOT_AUTHORIZED`.

Factory Spec
`atffs1_59f2c98666d95c2e5d2414b0837863908df38cbcd12bf86333465ea4cc3cf288`
was persisted before its first Agent call. It fixes eight Agent calls, 24
proposals, 16 admissions/materializations, one repair per call, windows
5/10/20/40/60/120, four primitives, two windows, AST depth six and eight
operators.

The Agent receives the raw-feature contract, existing Terminal Feature
definitions, authorized operators, structural fingerprints, non-predictive
failure summaries and family coverage. Its schema and prompt exclude Label,
RankIC, returns, backtests, historical Candidate performance and all
2021–2026 evidence.

## 6. Formal Feature Factory result

The formal factory made eight Agent calls and emitted ten proposals. Two
proposals passed every 2019–2020 label-free gate and were materialized:

| Feature | Family | Feature ID | Materialization |
| --- | --- | --- | --- |
| `smoothed_level_to_displacement` | trend_geometry | `rtf1_a3fe37...ad4db` | `tfm1_36bd48...287a6` |
| `trailing_envelope_location` | trend_geometry | `rtf1_506819...732e2` | `tfm1_132caa...49fa5` |

Admission required at least 95% finite coverage, at least 90 finite daily
members, zero infinity/duplicate/PIT violations, dispersion on at least 95%
of days, median unique-value ratio at least 10%, rank autocorrelation in
[0.20, 0.995], and the structural/signal novelty rules. No predictive metric
or strategy backtest entered admission.

Both new objects are `research_terminal_feature`, never approved, active or
production. Catalog
`tfc2_229f1939bdd3023e0410d3def332f1a9fdbd8cb4193cc71e7e6a8660138cf5e6`
contains existing formal features plus these research-only objects and was
frozen before the Alpha Program's first Agent call.

Factory counters are: Label reads 0, backtest/Qlib calls 0, Tushare/network
calls 0, manual planning/intervention 0 and Promotion writes 0.

## 7. Archetype contract and Program Spec

Archetype Contract
`aac1_853b0df7f8146c0024b3b95f94ea20ed87a2a35c096d8d64813b5d649fe8e961`
requires every proposal to freeze one primary archetype, hypothesis, statistic
and holding horizon before any numerical evaluation.

- `monotonic_rank_factor` uses daily official-label RankIC and HAC lag 10.
- `top_tail_selection_factor` uses non-overlapping ten-session Top20
  equal-weight future gross return minus observable-universe equal-weight
  future gross return and HAC lag 1.

Missing declarations and post-hoc switches are hard failures. Full RankIC for
a tail object remains secondary evidence and cannot replace its primary test.

Final Program Spec
`aap1_30e59bce48153a721dd29b459548dafc98271f6eef4236c07a8569b70acd0100`
freezes three Lanes, 18 Rounds/calls, 54 proposals, 36 admissions, 72 local
rescue Trials, 180 adaptive Qlib calls, a 12-object Union limit, 48 validation
Qlib calls and five final Survivors.

## 8. Formal Alpha research result

All three Lanes completed six Rounds. The Program made 18 Agent calls,
received 36 proposals, admitted 19, ran 11 local-rescue Trials and made 58
adaptive Qlib calls. Ten distinct Factor families were attempted.
Monotonic and tail archetypes were each attempted nine times.

The early-stop minimums were satisfied before termination: 18 Rounds and
calls, ten families, all Lanes complete, 19 admissions and both archetypes
attempted. Agent, Planner, Memories, parameters and archetypes then closed
before locked validation opened.

Union Lock
`aausl1_47e18224e6c1d15d7cb8f66aa689e785e08eab24c6cb96c81ad787751d27d239`
contains nine immutable objects: four monotonic and five tail. It records
validation reads equal to zero at publication.

## 9. Locked validation and multiple testing

The Program performed archetype-specific 2021–2024 validation on all nine
locked objects. Thirty-two validation Qlib reads were persisted across the
completed run/recovery boundary. Validation changed no formula, parameter,
orientation, archetype, Agent input, Planner input, Memory or shortlist rank.

Every object failed its unchanged archetype gate and/or global FDR. The
smallest raw primary p-value was 0.018619; after the single global
Benjamini–Hochberg family across both archetypes, its adjusted q-value was
0.138617, above the frozen 10% threshold.

Multiple-testing object is
`amtc1_fae10b7f2dafe0d81552a68e3d34226f12050cb6492a7b0045d7f7011d2dd7d1`.
Program Report is
`aapr1_e344e138cb76bd1c0307920426b879c0b0a1019b4e3083cc3f373a739df4f6e3`
with state `completed_no_validation_survivor`.

Because there is no Survivor, final Candidate Locks, Registry writes,
2025/2026H1 reports and Fresh Locks are all zero. These survivor-only
operations were not invoked.

## 10. Immutable diagnostic Program attempt

The first persisted Program Spec
`aap1_dd9044314fe66166b44e05f7e6a10fd54d95b0d6083a70702b3a61916c42f197`
remains immutable diagnostic evidence. It completed 18 calls and 36 proposals
but reached zero adaptive Qlib calls because admitted evaluation encountered
a general date-type boundary and the Agent prompt omitted the required
dataset-kind instruction.

The final formal revision is 1.0.1. The minimal general corrections normalize
matrix/signal dates, state the existing dataset kind in the prompt, normalize
NumPy booleans before JSON persistence, isolate disposable recovery caches,
and rehydrate completed Validation without repeated Qlib. No earlier Artifact
was rewritten and no research threshold or protocol changed.

## 11. Artifact Store, recovery and replay

Factory and Program cold inspection reconstruct Specs, proposals, admissions,
materializations, Catalog, archetype contract, Lanes, Agent responses,
Development Locks, Union Lock, validations, multiple-testing result, failures
and terminal reports from the Artifact Store.

Store integrity is healthy with Missing 0 and Unreferenced 0. Terminal resume
and exact replay return zero Feature/Alpha Agent calls, Factor/Strategy/
Combined Optimization calls, Qlib calls, Tushare/network calls, Feature/
Registry/Fresh/Promotion writes, new Artifacts and new Blobs.

## 12. Tests executed

- Focused Factory/Program/Campaign/Store/Context suite: 99 passed with
  `--no-cov`.
- Context Bootstrap: 42 bounded checks passed.
- All 119 Project Context JSON documents, including this Run Manifest, parsed.
- New modules and CLIs passed `py_compile`.
- Factory and Program formal cold validation passed.
- Factory and Program terminal resume and exact replay passed with zero calls
  and writes.
- `git diff --check` passed.

The first broad invocation exposed two stale assertions that still required
the current task to be `QM2-R2-003`; 97 tests passed and two failed. The
bounded context validator and its regression test were updated to require
`QM2-R2-004` and its authoritative handoff markers, after which all 99 passed.

## 13. Architecture, security and data-lineage impact

This change introduces one Feature Factory and one archetype-aware orchestration
layer while reusing the canonical DSL, existing formal Qlib evaluator,
Registry boundary and Artifact Store. It does not create a fourth research
chain or change the market-data authority.

The Feature path physically separates label-free 2019–2020 admission from
Alpha evaluation. Alpha Agent/Planner/Memory receive only 2019–2020;
2021–2024 opens after immutable selection; 2025/2026H1 are survivor-only;
Fresh remains isolated. No credentials or secrets are persisted.

## 14. Files and important symbols

Core packages:

- `autonomous_technical_feature_factory`: Factory models, Agent schema,
  grammar, admission, materialization, Catalog and orchestration.
- `archetype_alpha_program`: archetype/program models, schemas, evaluation,
  FDR and orchestration.
- Artifact Store enum/schema mappings for the 15 new immutable Artifact kinds.
- Two CLIs, two focused test modules, one frozen contract and synchronized
  Project Memory.

Important symbols include `AutonomousTechnicalFeatureFactorySpecV1`,
`TechnicalTerminalFeatureGrammarV1`, `FeatureAdmissionService`,
`AlphaArchetypeContractV1`, `ArchetypeAwareProgramSpecV1`,
`ArchetypeEvaluationService`, factory/program execute, resume, validate and
replay entry points.

## 15. Known limitations

- Locked Validation is retrospective project evidence, not Fresh or Frozen
  Test evidence.
- The authorized v1 DSL lacks `rolling_sum`, `rolling_corr` and `log1p`; the
  factory rejects them rather than inventing semantics.
- The formal factory admitted only Trend Geometry features; the other target
  feature families remain uncovered.
- The formal Program produced zero Survivors, so Registry/report/Fresh
  success paths retain test coverage but no formal-run success evidence.
- Artifact Store/runtime remains local single-process/single-host.
- Existing Qlib wrappers emit optional PostgreSQL/COS warnings before the
  verified local formal Qlib path completes.

## 16. Compatibility, rollback and remaining work

Historical Campaigns, Programs, Candidates, Shortlists, Validations and
Registry states remain immutable. Rollback is the single task commit;
immutable research artifacts remain retained. The task contract authorizes no
successor, so none is recommended here.

## 17. Git/workspace

The task creates one independent commit, does not amend and does not push.
Post-commit Planner evidence is finalized after commit.
