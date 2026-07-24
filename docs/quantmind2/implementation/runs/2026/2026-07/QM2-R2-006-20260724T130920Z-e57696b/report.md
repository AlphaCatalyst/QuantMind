# QM2-R2-006 Implementation Report

## 1. Task summary

Task `QM2-R2-006 — Technical DSL Expansion and Novel Research Space Cycle v1`
extends the existing Factor DSL and technical Feature Factory without creating
a parallel research stack. It publishes a bounded operator contract, six
research primitives, Factory 002 and Feature Catalog v3, then runs the existing
Supervisor through Research Cycle 002.

The formal cycle completed. It expanded the unlabeled Feature space and ran a
full retrospective Alpha Program, but no object passed the unchanged historical
candidate gates.

## 2. Goal and scope

The implementation:

- audits and contracts six deterministic PIT rolling operators;
- explicitly rejects seven wider operators;
- derives six PIT primitives from existing authoritative fields;
- adds Factory v2 with frozen budgets and label-free admission;
- freezes Technical Feature Catalog v3;
- lets the existing Alpha Program consume Catalog v3;
- adds a retrospective-only Alpha output mode;
- extends the existing Supervisor with Cycle 002, queue/state/report artifacts,
  conditional Fresh locking, global stop controls, recovery and replay;
- adds CLI commands, tests, contracts and Project Memory.

## 3. Explicit non-goals

No new market field, Tushare request, market-network request, dependency,
lockfile, Strategy Optimization, Combined Optimization, full Factor search,
historical gate reduction, FDR reduction, automatic Promotion, trading, API,
UI, database migration, Cycle 003 or production Feature state was introduced.

## 4. Preflight state

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `e57696b977ee21fbca6d3e7fa01ce4bc434ef49f`
- Worktree: clean
- Unrelated dirty files: none
- Factor Lab: read-only and unchanged
- Credential handling: environment presence was checked without printing,
  hashing or persisting any token value

## 5. Operator feasibility and contract

The existing typed AST, parser, compiler, executor and canonical serializer
were extended in place. Authorized operators are `rolling_sum`,
`rolling_corr`, `rolling_median`, `rolling_quantile`, `rolling_skew` and
`rolling_argmax_age`.

All use trailing same-symbol windows with `min_periods=window`, deterministic
float execution and no implicit fill. Correlation returns NaN for either
near-zero-variance side. Quantile is a non-optimizable DSL constant restricted
to 0.20, 0.50 or 0.80. Skew uses a deterministic population central-moment
ratio and returns NaN for near-constant windows. Argmax age selects the most
recent tied maximum.

`rolling_cov`, `rolling_kurt`, `where`, `if_else`, `group_neutralize`,
`industry_neutralize` and `rolling_regression` remain rejected. The authority
is `TECHNICAL_DSL_OPERATOR_EXTENSION_V1.md` and its JSON Schema.

Formal artifacts:

- Operator Extension:
  `tdoe1_2e208b964434c062d67ba19e14f8b4d3e22227dad9ca09362ff005d41c2da668`
- Operator Validation:
  `tdov1_af8b2e83c83b5d5beab1f32613ac0b303d143f8648002f815f3462ba7e87857f`

## 6. Primitive Catalog v2

The formal 188,070-row, 100-symbol, 2018-09-03..2026-06-23 Feature matrix
contains the required adjusted OHLC, volume, amount, VWAP, adjustment factor,
daily return and authorized daily-basic fields. No field was downloaded.

Six research-only primitives were materialized:

- `overnight_gap`, coverage 0.999468;
- `intraday_return`, coverage 1.0;
- `high_low_range`, coverage 0.999468;
- `close_location_value`, coverage 0.999516;
- `close_vs_vwap`, coverage 1.0;
- `turnover_pressure`, coverage 0.989897.

The VWAP primitive explicitly aligns raw VWAP with `adj_factor` before
comparison to adjusted close. Zero denominators return NaN. Primitive Catalog:
`tpc2_b9f6112bec9f5524d8d14eb0ff8d40244c0e143557d49c1676c2630686387208`.

## 7. Feature Factory v2

Factory Spec
`atffs2_b1d4fa8fbbe036129b7f8b60e3e6b7dcd025f80b67a9781d1d5b3ddb2fdf5628`
freezes 10 Agent calls, 30 proposals, 20 admissions, 20 materializations and
one repair attempt per call. Agent input excludes labels, performance,
backtests, candidates and Fresh evidence.

The formal run used 10 Agent calls, generated 26 proposals, admitted and
materialized 20 features, used zero repair attempts and read zero labels.
Failures were limited to primitive-count and window-parameter bounds.
Structural and numeric novelty were checked against Catalog v2.

Catalog v3
`tfc3_b903c85e328d359181c18ce3444d458a41ee970be8b2f6b79eff83cc6d523aea`
is frozen with 20 new and 22 total research terminal features, all explicitly
unavailable for production.

## 8. Supervisor Research Cycle 002

The existing Supervisor Spec
`arsv1_1d07cf5c773e0fef1c7855b874235405e8c1e0e247caa1f4af51876aecabd14e`
was retained. Cycle 002:

```text
Operator/Primitive audit
→ Factory 002
→ Catalog v3
→ Archetype-aware Alpha Program
→ Retrospective Candidate Gate
→ conditional Fresh Lock/Cohort
→ incremental-data decision
```

Research Cycle:
`arc2_78b9b6c5dbddb90dd37aaf75755a1b88cf24070a604d0313be0f39ce0cbd3266`.

Research-space Report:
`rser1_995457ec9281d656a4c601ad6b7bd88b728efc7a107109c2a4bf265ff00469de`.

## 9. Alpha Program result

Alpha Program
`aap1_619471b79e409ab5280b5bcb4a7d5345d6ba8d0dae676c37328b3d1d2758c410`
completed 18 frozen-archetype rounds. It made 18 Agent calls, received 36 Alpha
proposals, admitted 18 objects, ran 48 adaptive and 20 locked-validation Qlib
calls, used six local-rescue trials and made no Factor, Strategy or Combined
Optimization call.

Terminal Report
`aapr1_fef58cf347dd37c126022793342cfa95df94efed2306ebd76f3c47d4c73a838d`
contains zero retrospective survivors. Historical evidence remains
`retrospective_research_only`.

## 10. Candidate, Fresh and stop semantics

The formal Cycle produced:

- Retrospective Candidates: 0;
- Fresh Locks: 0;
- Fresh Cohorts: 0;
- Registry writes: 0;
- Promotion writes: 0.

No incremental market collection was required. Global stop is false because
the Feature dimension was non-empty even though the Candidate dimension
remained empty. The terminal state is
`waiting_for_fresh_data_or_novel_space`; no Cycle 003 is created.

## 11. Runtime counts

Combined formal counts are:

- Feature/Alpha Agent calls: 10/18;
- Feature/Alpha proposals: 26/36;
- Feature/Alpha admissions: 20/18;
- Feature materializations: 20;
- Qlib calls: 68;
- Tushare/network calls: 0/0;
- Candidate/Fresh/Registry/Promotion writes: all 0.

The existing local Qlib wrapper emitted optional PostgreSQL model-resolution
and COS path warnings before using the supplied local authority. All 68 Qlib
calls completed through the real Qlib path.

## 12. Store, checkpoint, recovery and replay

Every operator audit, primitive publication, Factory Spec, Agent call,
admission, Catalog, Alpha round and final Supervisor state is represented by
immutable Store artifacts or existing component checkpoints.

Store integrity is healthy with Missing 0 and Unreferenced 0. Cold recovery
from a new work root reconstructed 1,637 files and validated Cycle 002 with
zero evidence gaps. Terminal resume and exact replay returned zero operator,
primitive, Agent, Qlib, Tushare, network, Feature, Candidate, Fresh, Registry,
Promotion, Artifact and Blob writes.

## 13. Tests executed

- Operator/DSL/Factory/Alpha/Supervisor focused regression:
  115 passed, 2 environment-gated real-Snapshot tests skipped.
- New technical expansion tests: 23 passed.
- Formal Factory 002: passed with 10 Agent calls, 26 proposals and 20
  admissions/materializations.
- Formal Cycle 002: passed with 18 Alpha calls and 68 real Qlib calls.
- Resume, exact replay and cold recovery: passed with all replay counters zero.
- Context Bootstrap, JSON parsing, Python compilation, Git inventory and
  `git diff --check`: executed during finalization.

## 14. Architecture, security and lineage impact

The change reuses the canonical Factor DSL, Feature Factory, Alpha Program,
Supervisor, Artifact Store, Tushare authority and Qlib. It adds versioned
operator, primitive, Factory, Catalog, Cycle and Report lineage without
creating a second research system.

Agent visibility stays label-free at the Feature layer. Historical Alpha
results cannot become validated, approved, active, production or Fresh
evidence. Tokens and market data are absent from repository artifacts.

## 15. Known limitations

- Cycle 002 found no Retrospective Candidate, so no new Fresh-Lock/Cohort
  success path occurred.
- Existing Qlib wrappers still emit unavailable optional PostgreSQL/COS
  resolution warnings before successful local execution.
- Runtime and Artifact Store remain single-host and single-process.
- The operator extension is deliberately narrow; conditional, neutralization,
  regression, covariance and kurtosis nodes remain unavailable.
- Catalog v3 features are research-only and have no production authorization.

## 16. Compatibility and rollback

Existing Factor DSL nodes, Factory v1, Catalog v2, historical Alpha execution,
Supervisor Cycle 001 and all historical artifacts remain valid and immutable.
The Alpha Program defaults to its prior behavior unless `retrospective_only`
is explicitly selected.

Rollback is a revert of the single task commit. Content-addressed research
artifacts remain immutable evidence and are not deleted by source rollback.

## 17. Git and workspace

This Run is prepared against base
`e57696b977ee21fbca6d3e7fa01ce4bc434ef49f` as one independent commit with
message `feat(qm2): expand technical research space`. It does not amend or
push. Post-commit Planner evidence is finalized after commit. No successor
task is authorized.
