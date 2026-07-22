# QM2-R1-010 Implementation Report

## 1. Task summary

Task `QM2-R1-010 — Breadth-Gated Momentum Overlay and Fresh Forward Protocol
v1` completed the pre-registered historical mechanism diagnostic and began a
strict no-backfill Fresh observation. The formal terminal state is
`fresh_evidence_accumulating`; it is not support, rejection, Promotion or a
new Candidate.

## 2. Goal and scope

The implementation keeps immutable Signal D and tests only the frozen
narrow/weak breadth hypothesis. It introduces Gate/Fresh contracts, fixed
U/G/R diagnostic paths, incremental Tushare collection, bounded incremental
feature computation, minimum-evidence classification, six Store artifact
kinds, cold recovery, exact replay, CLI, tests and Project Memory updates.

## 3. Explicit non-goals

No Agent call, new Factor, Signal D change, Factor/Strategy/Combined/Gate
optimization, threshold or state search, Candidate mutation, Registry write,
Promotion, LightGBM work, full-history redownload or Qlib replacement occurred.

## 4. Preflight state

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `705033c820828f5dbfd26805507c8a9771014c0d`
- Worktree before: clean
- Unrelated dirty files: none
- Credential: `TUSHARE_TOKEN` present; its value, prefix, suffix and hash were
  never printed or persisted.

## 5. Frozen identities and PIT timing

Signal D remains
`lfmsa1_a4a99da30ef0dc99a03270bc5688f3edbe66bf944f899795d11aacf83a8e2262`
with formula `0.5*cs_zscore(momentum_120_20) +
0.5*cs_zscore(residual_momentum_60)`. R1-009 diagnostic and classification
identities remain unchanged.

The formal `build_regimes` contract was recovered. Its returned breadth state
at session `t` already uses raw breadth at `t-1` and past-only expanding
thresholds. Runtime consumes that state directly. A second shift would be a
contract-breaking two-session lag and is explicitly forbidden.

## 6. Gate pre-registration and Fresh lock

Before any post-2026-06-23 network call, the runtime published:

- Breadth contract `bmc1_e250a45e...798db`;
- Breadth dataset binding `bmd1_13b1077e...ad4a2`;
- Gate Spec `bmgs1_4cb24dc3...aec343`;
- Fresh Lock `bgmfl1_80313cd9...436b60`.

The Store receipts were created with `network_calls=0`. Only formal `narrow`
maps to `narrow_or_weak`; neutral and broad are off. Gate transitions affect G
only at scheduled ten-session rebalances. Gate-off clears risk holdings and
cash earns zero.

## 7. Historical path results

All periods are retrospective, contaminated and not Fresh evidence. Returns
are cumulative net returns; excess is versus CSI300. Turnover is summed
one-way-plus-one-way weight turnover and costs are currency units on 1,000,000
initial capital under the bounded CnExchange cost model.

| Period | Path | Net return | CSI300 excess | Sharpe | Max drawdown | Turnover | Cost |
|---|---|---:|---:|---:|---:|---:|---:|
| 2021 | U | 4.37% | 11.01% | 0.298 | -28.39% | 9.3 | 9,393 |
| 2021 | G | 9.57% | 16.21% | 0.600 | -16.74% | 10.6 | 10,956 |
| 2021 | R | -1.88% | 4.76% | -0.102 | -14.79% | 0 | 0 |
| 2022 | U | -20.86% | 0.08% | -1.088 | -28.01% | 11.2 | 11,312 |
| 2022 | G | -7.43% | 13.51% | -0.517 | -15.53% | 12.4 | 12,274 |
| 2022 | R | -9.73% | 11.21% | -0.733 | -14.05% | 0 | 0 |
| 2023 | U | -2.81% | 10.09% | -0.063 | -18.79% | 10.7 | 10,807 |
| 2023 | G | -5.81% | 7.09% | -0.602 | -12.74% | 14.0 | 14,140 |
| 2023 | R | 3.00% | 15.90% | 0.408 | -10.98% | 0 | 0 |
| 2024 | U | 29.41% | 16.59% | 1.120 | -16.11% | 9.2 | 9,292 |
| 2024 | G | 27.19% | 14.38% | 2.900 | -1.30% | 9.2 | 9,542 |
| 2024 | R | 0.60% | -12.22% | 0.125 | -5.88% | 0 | 0 |
| 2025 | U | -0.97% | -22.16% | 0.033 | -13.81% | 10.6 | 10,706 |
| 2025 | G | 3.18% | -18.01% | 0.438 | -5.11% | 10.3 | 10,403 |
| 2025 | R | 7.42% | -13.77% | 1.110 | -3.04% | 0 | 0 |
| 2026H1 | U | -16.37% | -20.64% | -2.633 | -20.80% | 4.7 | 4,747 |
| 2026H1 | G | -9.82% | -14.09% | -1.854 | -13.13% | 6.6 | 6,416 |
| 2026H1 | R | 1.52% | -2.76% | 0.305 | -6.45% | 0 | 0 |

Conditional selection alpha G minus R is 11.44%, 2.30%, -8.81%, 26.60%,
-4.24% and -11.33% for 2021 through 2026H1. Gate-on mean RankIC is positive
in each displayed period, and gate-on Q10-universe ranges from 0.272% to
0.477%, but investable G-minus-R fails in 2023, 2025 and 2026H1.

## 8. Contribution and episodes

Across the full diagnostic history, Always-On contribution compounded over
Gate-on sessions is +81.56% and Gate-off contribution is -12.23%. There are
453 Gate-on days in 82 episodes; mean/median/maximum episode length is
5.52/2.5/26 sessions. This supports a historical regime concentration
mechanism, not a Fresh predictive conclusion. In particular, 2025 and 2026H1
show that positive cross-sectional diagnostics need not create positive
conditional investable alpha.

## 9. Incremental market data and features

After the Lock existed in the Store, 68 Tushare calls collected only
`trade_cal`, `daily`, `adj_factor`, `daily_basic` and `index_daily` from
2026-06-24 through the latest available date. Snapshot
`tims1_a59e3127...9168c` contains 22 open sessions, 22 checkpoints, zero
duplicate endpoint keys, zero missing adjustment factors and valid symbol
mapping. No full-history redownload occurred.

Historical rows were used only as rolling warm-up. The incremental computation
materialized only `momentum_120_20`, `residual_momentum_60`, Signal D and the
formal breadth inputs. It generated no new feature definition and counted no
pre-2026-06-24 row as Fresh evidence.

## 10. Fresh observation and status

The final observation is `bgmfo1_6cdb7685...0abaf`; assessment is
`bgmfa1_22d8424e...349cd`.

- completed Fresh return sessions: 20;
- Fresh rebalance dates: 2;
- completed ten-session holding windows: 2;
- Gate-on trading days: 12;
- Gate-on rebalance dates: 2.

Interim U and G net return are both +1.909%; R is -4.568%; conditional
selection alpha is +6.477%. G maximum drawdown is -1.398%, turnover 0.9 and
cost 909. Gate-on RankIC is +0.02812, Q10-universe +0.2341% and hit rate
58.33%.

These values are observation-only. The immutable minimums are 60 trading
days, five completed holding windows, 20 Gate-on days and three Gate-on
rebalances. Because all four are not met, the only legal status is
`fresh_evidence_accumulating`.

## 11. Artifact Store and replay

Canonical replay restores Signal D, Gate Spec, historical diagnostic revision 2, Fresh
Lock, incremental snapshot, Fresh observation revision 2 and Fresh assessment
revision 2: seven artifacts in total. Inventory is `sai_2817ba87...ac272`; integrity is healthy,
Missing 0 and Unreferenced 0. Exact replay reports Agent, Factor/Strategy/
Combined Optimization, Tushare, network, Qlib, Registry, Promotion, new
Artifact and new Blob counts all zero.

Earlier same-task observation revisions remain immutable. They are not
overwritten; canonical replay selects the highest explicit computation
revision.

## 12. Files and technical implementation

The new `breadth_gated_momentum` package separates protocol identities,
artifact publication/validation and runtime execution. The CLI exposes all
ten required commands and has no token argument. Artifact Store enums,
validators and runtime cache routes include the six new kinds. Focused tests
cover immutable identity, formal lag semantics, active states, paths, cash,
episodes, Fresh lock and threshold statuses, credential safety, immutable
revision, no Registry/Promotion crossing and CLI surface.

Project Memory records the accumulating state and forbids describing interim
metrics as support. No API, database, migration, dependency, lockfile,
configuration, Factor Registry, model, Electron or production trading code
changed.

## 13. Tests and verification

- Focused suite: 13 passed.
- Relevant Store/runtime/momentum/context regression: final result recorded in
  the Manifest.
- Real Gate/Lock, historical diagnostic, incremental fetch, incremental
  features, Fresh observation, cold recovery and exact replay completed.
- All QuantMind2 JSON parses, Python compilation, Context Bootstrap and Git
  diff checks are required before commit.
- Factor Lab source remains read-only; its required summary is verified before
  commit.

## 14. Security, lineage and architecture impact

The token is environment-only and is absent from code, CLI, reports,
Manifests and Store artifacts. Lineage binds the immutable source signal,
R1-009 diagnosis/classification, formal breadth contract, fixed universe,
authority, Gate, Lock, incremental snapshot, observation and assessment.
Research Memory, Optimization and Candidate selection cannot consume Fresh
results. This adds a bounded research component without changing frozen
architecture or accepted ADRs.

## 15. Known limitations

- Fresh evidence is far below the minimum sample policy and cannot support or
  reject the overlay.
- Historical path execution is a bounded CnExchange-cost mechanism diagnostic,
  not a replacement for a formal Qlib conclusion.
- The first incremental snapshot has only 22 market sessions and 20 completed
  return sessions.
- Incremental collection is manually invoked and single-process; no scheduler,
  distributed backend or late-revision monitor is added.
- Existing fixed-universe settlement limitations remain unchanged.

## 16. Compatibility, rollback and next work

Rollback is a revert of the single task commit. Immutable Store artifacts are
retained as historical evidence and are not deleted or overwritten. The old
Signal D, Qlib results, Candidates and Registries remain compatible and
unchanged. No successor task is recommended or authorized by this task.

## 17. Git/workspace state

The task will be committed once as
`feat(qm2): add breadth gated momentum forward protocol`, without amend or
push. Post-commit Planner validation and final clean-worktree evidence are
recorded after the commit.
