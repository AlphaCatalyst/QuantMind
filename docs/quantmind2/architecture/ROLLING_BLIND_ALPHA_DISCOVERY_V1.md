# Rolling 60-Day Blind Alpha Discovery v1

## Authority and scope

This contract records the `QM2-R3-001` implementation of historical rolling
blind validation and bounded continuous Alpha discovery. It extends the
existing Autonomous Research Supervisor; it is not a parallel research
system. Evidence produced here is `historical_rolling_blind` or
`historical_pseudo_fresh`, never real Fresh evidence.

The runtime reuses the canonical Tushare Dataset/Feature authority, Factor DSL,
Technical Feature Catalog v3, existing LightGBM training chain, formal Qlib
backtest service and immutable Artifact Store.

## Frozen partitions

- Discovery: `2019-01-02..2021-12-31`.
- Requested Blind Pool: `2022-01-04..2026-07-23`.
- Window size: exactly 60 official A-share trading sessions.
- Windows are contiguous and non-overlapping.
- An incomplete final tail is excluded.
- The complete Window Set is published before the first Agent call.

The canonical Qlib consumption view available to Batch 001 ended on
`2026-06-24`. It therefore produced 18 complete windows ending on
`2026-06-23`; the one-session `2026-06-24` tail was excluded. No synthetic
calendar dates were added.

## Isolation boundary

Agent, Planner and adaptive Failure Memory may read only Discovery-period
results, static DSL/Feature/PIT contracts, structural duplicates and unlabeled
admission/data-quality/PIT failures. They may not read any rolling Blind
metric, status, failure reason, 2025/2026 slice, or existing real Fresh result.
Window results are written only after the Candidate Batch Lock and are visible
only to final validation/reporting and the Blind Submission Ledger.

## Discovery lanes

The DSL lane accepts simple one-factor or two-to-three-Terminal structures with
a predeclared monotonic or top-tail Archetype. It uses explicit default
parameters first and permits at most one local-neighbor rescue after default
failure. Full parameter search, Strategy Optimization, Combined Optimization
and regime-gate search are disabled.

The model lane builds fixed, unlabeled Feature Bundle hypotheses from existing
technical families and trains the existing canonical LightGBM configuration.
It uses the frozen three seeds as an equal ensemble. It does not optimize model
hyperparameters, choose a best seed, change the Label, or select Feature
membership from Blind performance.

## Fixed strategy

All Discovery and Blind Qlib evidence uses `topk=20`, `n_drop=5`,
`rebalance_interval=10`, equal weight, one-session signal lag, open execution
and CSI300 benchmark.

## Candidate Batch Lock

`RollingBlindCandidateBatchLockV1` freezes members, formula/model configuration,
parameters, orientation, Archetype, Label, Feature Bundle, seeds, strategy,
primary statistic and Discovery ordering. Both Agent and Planner are closed at
publication and `blind_window_reads_before_publish` must equal zero.

## Blind execution and gate

Every locked object runs every complete window without early stopping. A model
window trains only on observations strictly before the window start and keeps
the same Bundle, LightGBM configuration and three seeds.

The monotonic/model primary statistic is mean daily official-label RankIC. The
tail primary statistic is non-overlapping ten-session Top20 minus
observable-universe spread.

The immutable gate requires at least 12 complete windows, positive primary
metric in at least 70% of windows, positive primary median, worst-20% primary
mean greater than `-0.01`, positive CSI300 excess in at least 60% of windows,
positive CSI300 excess median, turnover median no greater than 30, best-ten-day
contribution median no greater than 35%, and unchanged configuration. Missing
or non-finite metrics fail closed.

## Statistical control

Each candidate receives a one-sided window-level test of mean primary metric
greater than zero. All submitted candidates from both lanes share one
Benjamini-Hochberg family with `q=0.10`. A Survivor requires both the complete
gate and adjusted q-value no greater than 0.10.

## Survivor and Fresh boundary

A Survivor is written only as `research_registered` with
`rolling_blind_passed=true`, `historical_pseudo_fresh=true`,
`real_fresh_validated=false` and `production_eligible=false`. Only a Survivor
may receive a new no-backfill real Fresh Lock whose first eligible date is
strictly later than the latest market data at lock time. This flow has no
approval, activation, production, trading or Promotion authority.

## Batch 001 formal result

- Batch:
  `rbdb1_6ca989dfab231a2b57fb3679d2dbca8006a370bc082d1b6b2f55840479f88851`.
- Window Set:
  `rbws1_4e8166c3a9d5699d39cac1a776165a311d1b2a6da85eb3c02187cd9405c16259`.
- Candidate Lock:
  `rbcbl1_616dfc39faca7136ccc8a04f20f02b83792baa85e286b6f0be6a794ce7aba705`.
- Research Report:
  `rbrr1_8c19f12bca2e6f78256054b000b9af19e254ec9032389af609f4fa057d2a4121`.
- Status: `completed_no_blind_survivor`.
- 24 rounds, 18 Agent calls, 42 proposals, 24 admissions, 18 structural
  rejections, four local rescue trials and six fixed model hypotheses.
- Two fixed-model candidates were locked and both completed all 18 windows.
- 36 Blind window evaluations, 126 model fits and 64 formal Qlib calls.
- Both candidates failed the unchanged rolling gate and global BH; zero
  Survivors and zero new Fresh Locks were written.
- Agent/Planner/Failure Memory feedback, Strategy/Combined Optimization,
  Registry, Promotion, automatic Batch 002 and manual planning/intervention
  counts are all zero.
- Store integrity is healthy with zero missing or unreferenced Blobs.

## Recovery and replay

Window Set, every Agent round, Candidate Lock, every candidate/window result,
multiple testing, Search Exposure, Submission Ledger and terminal Report are
immutable checkpoints. Resume resolves existing checkpoints from descriptor
lineage as well as current parent references.

Cold validation materializes the complete terminal evidence set and requires a
healthy Store. Exact replay performs zero Agent, model-training, Qlib, Tushare,
network, candidate, Survivor, Fresh Lock, Registry, Promotion, Artifact and
Blob writes.

## Non-goals

- No real Fresh claim or automatic Batch 002.
- No full Factor, model, Strategy or Combined Optimization.
- No new Label or model type.
- No Blind feedback to research generation.
- No gate relaxation after zero Survivors.
- No modification to existing Fresh candidates, locks, cohort, heartbeat,
  LaunchAgent or immutable runtime deployment.
