# QM2-P0-011BF Implementation Report

## 1. Task Summary

- Task: `QM2-P0-011BF` — 2026H1 Locked-factor Signal Missingness Audit and Deterministic Re-run
- Result: `blocked`
- Diagnostic work: complete
- Deterministic Qlib rerun: correctly not executed because the unchanged signal missingness gate still fails
- Base commit: `d115ff929c7c64fdf4d64f6cc01bec0163347659`
- Implementation Run: `QM2-P0-011BF-20260719T153305Z-d115ff9`

## 2. Goal

Reconstruct the exact propagation of missing values from the locked Dataset and
Features through both locked Factor DSL expressions, immutable Factor Values,
orientation, cross-sectional normalization, equal-weight combination, the
Dataset-derived Qlib consumer view, and the formal pre-backtest gate. A Qlib
rerun was permitted only after a proven implementation defect was minimally
repaired and the unchanged missingness ratio became at most 20%.

## 3. Scope

- Read-only audit of the fixed 100-symbol historical experiment
  `hae_5e4b11baed63c300d5c3964b8480ad3115f8864e096a1610c5afc5db0ab3fedd`.
- Read-only audit of its two locked Factor Instances and the original blocked
  Qlib Backtest Artifact.
- Layered 2025 and 2026H1 missingness attribution.
- Immutable audit and blocked-followup Artifact types, Store publication,
  integrity validation, cold recovery, and exact replay.
- Project Memory and focused regression coverage.

## 4. Explicit Non-goals

No Agent call, candidate creation, Optimization, Trial replacement, orientation
change, factor parameter change, universe change, fill, threshold relaxation,
strategy change, promotion, modification of an earlier Artifact, or conclusion
about 2026H1 factor performance. The 2019–2025 formal results were not rerun or
overwritten.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `d115ff929c7c64fdf4d64f6cc01bec0163347659`
- Working tree: clean
- Unrelated dirty files: none
- Expected locked experiment, Qlib result, universe, Dataset, Factor Values,
  Artifact Store Inventory, and Qlib consumer view were present.
- Factor Lab was not read or modified by the runtime.

## 6. What Changed

Added a deterministic audit module and offline entry point that reconstruct the
locked signal path without mutation. Added immutable
`signal_missingness_audit` and `historical_backtest_followup` Artifact kinds and
their bounded completeness validation. Added a focused synthetic regression
that proves source-Feature attribution without fill. Published a repository
summary, an implementation contract, and updated Project Memory.

No source Feature, Dataset Snapshot, Factor Template, Factor Instance, Factor
Values, signal protocol, Qlib strategy, quality threshold, or earlier research
Artifact was changed.

## 7. Why It Changed

The original formal gate reported 35.17% missing values but did not preserve the
full layer-by-layer evidence needed to distinguish absent rows, source Feature
missingness, DSL warm-up, normalization propagation, combination propagation,
and Qlib alignment loss. The new audit makes that distinction reproducible and
prevents a data-source limitation from being disguised as a factor-performance
result or an implementation repair.

## 8. Frozen Denominator Reconstruction

The original gate is exactly:

```text
observed signal rows     10,867
finite signal cells       7,045
NaN signal cells          3,822
NaN ratio               35.170700285267326%
```

Its denominator is the rows observed after the formal signal range/lag path;
it is not the complete universe-date grid. The complete 100 x 111 grid is:

```text
expected signal cells    11,100
observed source rows     10,867
missing rows                233
NaN or absent cells       4,055
full-grid missing ratio  36.53153153153153%
```

Both locked candidates and their strict equal-weight combination have the same
2026H1 observed-row missing mask. Per-day, per-symbol, per-month, and
rebalance/non-rebalance distributions are preserved in the audit Artifact's
Parquet/JSON evidence.

## 9. Layer Results

### Layer A — Universe and calendar

- Locked universe: 100 symbols; expected dates: 111; expected cells: 11,100.
- Observed symbols: 98; observed rows: 10,867.
- `SH600837` and `SH601989` are absent for all 111 dates: 222 missing rows.
- Eleven additional rows are absent across two symbols and ten dates.
- Dataset and Qlib consumer calendars cover the requested horizon; the Qlib
  view is not truncated at 2026-05-20 and has a 2026-06-24 sentinel.

### Layer B — source Features

- `mom_ret_1d`: 10,867 / 10,867 finite in 2026H1.
- `style_idio_vol_20`: 7,045 finite and 3,822 missing on observed rows.
- The missing `style_idio_vol_20` values affect all 98 observed symbols across
  39 dates. Its first valid 2026 date is 2026-03-09.
- `style_beta_20`, an upstream source Feature in the existing generator, first
  becomes valid on 2026-02-02. Production-wide 2026 source data exhibits the
  same pattern; it is not introduced by the bounded Dataset.

### Layer C — DSL nodes

Exact trace evaluation of every terminal, lag/delta/rolling, arithmetic, and
cross-sectional node shows that `style_idio_vol_20` contributes all 3,822
observed-row NaNs. DSL rolling, delta, `cs_rank`, and `cs_zscore` nodes add zero
2026H1 NaNs. No unexpected operator warm-up is introduced in this period.

### Layer D — Factor Values

Each locked Factor Values Artifact contains exactly 180,241 expected keys:
duplicate 0, missing 0, extra 0. Schema, `trade_date`, symbol normalization,
Dataset lineage, and Manifest identity are valid. Exact recomputation matches
the immutable bytes. Each candidate has 23,871 finite and zero NaN observed
rows in 2025, versus 7,045 finite and 3,822 NaN observed rows in 2026H1.

### Layer E — signal normalization and combination

Orientation multiplication adds zero NaNs. Daily cross-sectional z-score adds
zero NaNs beyond its Factor input. The frozen strict two-factor equal-weight
intersection adds zero NaNs because both masks are identical. No single-factor
fallback or fill is used.

### Layer F — Qlib consumer view and precheck

The Dataset-derived Qlib view has 100 instrument records, spans 2019-01-02 to
2026-06-24, and covers the requested formal period. Symbol/date normalization,
join shape, timezone/date values, score column, and index naming agree with the
formal adapter. Open has 10,867 finite observed rows and 233 absent-grid rows.
The signal join loses zero rows and adds zero NaNs; no `dropna` occurs before
the gate. Each formal signal input has 10,867 rows, 3,822 NaNs, 111 dates, and
98 observed instruments.

## 10. 2025 Control

| Layer | 2025 NaN / missing | 2026H1 NaN / missing | Increment |
| --- | ---: | ---: | ---: |
| Expected-grid row absence | 329 / 24,200 | 233 / 11,100 | different horizon |
| Source Feature on observed rows | 0 / 23,871 | 3,822 / 10,867 | +3,822 |
| DSL-added NaN | 0 | 0 | 0 |
| Orientation-added NaN | 0 | 0 | 0 |
| Combination-added NaN | 0 | 0 | 0 |
| Qlib join/alignment-added NaN | 0 | 0 | 0 |

The same locked candidate semantics are fully finite on all observed 2025 rows.
The change is isolated to 2026 source availability rather than the general DSL,
combination, or Qlib implementation.

## 11. Root-cause Classification

| Classification | Cells | Symbols | Dates | Repair allowed | Research semantics |
| --- | ---: | ---: | ---: | --- | --- |
| `EXPECTED_UNIVERSE_ABSENCE` | 222 | 2 | 111 | no | deleting symbols would change the lock |
| `SOURCE_ROW_MISSING` | 11 | 2 | 10 | no proven safe repair | filling/invention forbidden |
| `SOURCE_FEATURE_MISSING` | 3,822 | 98 | 39 | no | replacing authoritative values changes data semantics |
| `UNRESOLVED_DATA_QUALITY` | overlaps source Feature evidence | 98 | 39 | no in this task | generation provenance is insufficient |
| `IMPLEMENTATION_DEFECT` | 0 | 0 | 0 | not applicable | none proven |
| `QLIB_VIEW_TRUNCATION` / `QLIB_JOIN_LOSS` | 0 | 0 | 0 | not applicable | none present |
| `COMBINATION_NAN_PROPAGATION` | 0 | 0 | 0 | not applicable | none added |

The existing generator's beta-then-residual-rolling construction is consistent
with a two-stage 39-date year-boundary cold start, but the available provenance
does not establish a semantics-preserving way to reconstruct authoritative
values. This is therefore evidence of source Feature missingness plus unresolved
data quality, not a proven implementation defect.

## 12. Repair and Deterministic Rerun Decision

No permitted implementation or join defect was found, so no production-data
repair was made. The unchanged formal ratio remains 3,822 / 10,867 = 35.1707%,
above the frozen 20% threshold. Qlib calls: 0. No 2026H1 formal return, Sharpe,
drawdown, turnover, or cost result exists. The blocked condition is source-data
availability and must not be interpreted as factor performance.

## 13. Important Classes / Functions / Documents

- `audit_locked_signals`: complete immutable signal-path reconstruction.
- `_trace_expression`: node-level Factor DSL missingness attribution.
- `ArtifactKind.SIGNAL_MISSINGNESS_AUDIT` and
  `ArtifactKind.HISTORICAL_BACKTEST_FOLLOWUP`: bounded Store identities.
- `validate_historical_artifact`: completeness validation for both new kinds.
- `SIGNAL_MISSINGNESS_AUDIT_V1.md`: diagnostic and prohibition contract.

## 14. Runtime Flow

Locked Store Artifacts are cold-recovered, verified, and read; expected
universe-date grids and observed source rows are compared; required Features and
DSL nodes are traced; Factor Values are key/schema/lineage/recomputation checked;
orientation, normalization, combination, and Qlib alignment are reconstructed;
root causes and the unchanged gate decision are written to staged immutable
directories; content IDs are calculated; staged directories are atomically
published; Store import, inventory, cold recovery, and exact replay are verified.

## 15. API, Database, Configuration, and Dependency Changes

- HTTP APIs: none.
- Database migrations or production database access: none.
- Runtime configuration: none.
- Project dependency or lockfile changes: none.
- An ephemeral offline `uv` test environment reused cached packages; it made no
  repository dependency or lockfile change.

## 16. Architecture Impact

This adds diagnostic evidence around the existing locked research path; it does
not change the research path. It conforms to Dataset Snapshot authority,
immutable lineage, real-Qlib-only formal conclusions, and the separation of
Agent, Factor Optimization, and backtest responsibilities. The Artifact Store
can now retain a failed quality-gate diagnosis and follow-up without overwriting
the original partial experiment.

## 17. Security and Data Lineage Impact

No secret, network credential, external model response, production database, or
untrusted code execution was used. Every audit record binds the source
experiment, locked Factor Instance/Values, Dataset, Qlib consumer view, and
original Qlib result. Original Artifact IDs and bytes remain unchanged.

## 18. Tests Executed and Results

1. Focused historical experiment suite: `6 passed`.
2. An earlier relevant Artifact Store, DSL, Optimization, Validation, Registry,
   Fresh Validation, and historical experiment run completed with `127 passed,
   8 skipped`. After the audit evidence was expanded, the final equivalent run
   completed `126 passed, 1 failed, 8 skipped`: only the unchanged
   `test_concurrent_same_artifact_is_one_descriptor` failed.
3. The first broad command did not collect tests because the ephemeral command
   omitted `jsonschema`; the corrected offline command included the cached
   existing requirement and passed. This was an environment setup error, not a
   product test failure.
4. Audit execution: both candidates, combination, 2025 control, Qlib alignment,
   and root-cause assertions passed.
5. Store import/inventory: 97 Artifacts, 372 blobs, `healthy`, missing 0,
   unreferenced 0.
6. Cold recovery: both new Artifact types passed formal validation.
7. Exact replay: both imports returned `exact_existing=true`, new blobs 0 and
   new bytes 0.
8. Manifest v2 and Context tests: `40 passed`. Their first invocation exposed a
   stale Project Memory assertion for the former `QM2-P0-012F` handoff; the
   assertion was updated to the public `completion_status` contract and the
   locked-audit facts, then the complete suite passed.
9. Context Bootstrap: 42 checks passed; all 89 QuantMind 2 JSON files parsed;
   `py_compile` and `git diff --check` passed.
10. Post-commit Planner results are recorded after the immutable commit in the
    final handoff response; the committed Manifest itself is not rewritten.
11. The concurrent-import failure reproduced twice when targeted. The same
    test passed once against an archived `d115ff9` base tree, confirming its
    timing-sensitive nature; the relevant suite excluding that single
    out-of-scope test passed `120 passed, 8 skipped, 1 deselected`. No Artifact
    Store importer/receipt production code was changed.

## 19. Artifact Index

- Audit: `artifact-store://sma_33979ef548d1a5f8ae72b3bbb500063f6c251679e5cd52203a0382b66cba9b64`
- Blocked follow-up: `artifact-store://hbf_fc927bcf0a7fd26b38adde8dc14da1fbc76a7b2acb3ed676b5deb3c07b16e1f1`
- Store inventory: `artifact-store://sai_39e85260407a110f9bc2636caf30962db65fe21604cdfffcdda31ec2154142f2`
- Repository audit summary:
  `docs/quantmind2/research/historical_agent_experiments/QM2-P0-011BF/audit_summary.json`

An earlier content-addressed draft audit/follow-up pair from this same Run was
published before per-date Feature evidence and the explicit overlapping
`UNRESOLVED_DATA_QUALITY` record were added. The Store preserves those immutable
draft bytes; they are not the current repository-referenced audit. This is why
the final Inventory grows from the 93-artifact baseline to 97 rather than 95.

## 20. Known Limitations

- The authoritative 2026 source lacks `style_idio_vol_20` for 39 dates across
  all 98 observed locked symbols; its upstream generation provenance is not
  sufficient for an allowed deterministic correction.
- Two locked symbols have no rows and eleven additional grid rows are absent.
- No formal 2026H1 Qlib performance result exists because the quality gate fails.
- This diagnostic does not classify the economic cause of delisting, suspension,
  or source absence where authoritative metadata is unavailable.
- The pre-existing Artifact Store concurrent same-artifact import test can race
  between descriptor publication and Receipt payload accounting, yielding an
  immutable Receipt ID conflict. It is outside this task's permitted repair
  scope and remains unresolved.

## 21. Compatibility, Migration, and Rollback

The new Artifact enum values are additive and earlier Store records remain
valid. Removing the added audit module, CLI, kinds, validators, tests, contract,
summary, and Project Memory update rolls back repository behavior; immutable
Store blobs may remain unreferenced only if a later explicit Store retention
operation permits it. No Dataset, Factor, model, Qlib, database, or API migration
is required.

## 22. Remaining Work

Resolve the upstream 2026 Feature-generation provenance and data-authority issue
under a separately authorized data task. A new formal Qlib backtest is not
allowed until an independently authorized, semantics-preserving correction
produces a frozen signal missingness ratio at or below 20%.

## 23. Recommended Next Task

None is authorized by this task. The current state remains blocked on source
Feature availability; this run does not silently create a repair or promotion
task.

## 24. Git / Workspace State

The task is prepared as one independent commit with suggested message:
`fix(qm2): audit 2026 signal missingness`. It is not amended and is not pushed.
The final result commit and post-commit clean state are recorded after commit in
the finalized Manifest and handoff evidence.
