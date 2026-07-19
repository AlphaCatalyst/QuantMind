# QM2-P0-011B Implementation Report

## 1. Task Result

`partial`. The fixed-universe Dataset, four real Agent rounds, bounded factor
Optimization, pre-evaluation Round Locks, 2021–2024 next-year evaluation,
selection through 2024, 2025 holdout, formal Qlib/CnExchange backtests,
combination, robustness, Store publication, cold recovery and exact replay
completed. The unchanged Qlib signal-quality gate rejected all locked 2026H1
signals because NaN coverage was 35.17% versus the 20% maximum.

## 2. Preflight and Scope

- Repository: QuantMind main, branch `master`.
- Base: `d2bd494192f6a8849d58029c68a391daa4dbcd8b`.
- Dirty before: no; unrelated dirty files: none.
- Store baseline: `sai_820983db...e5e68`, 79 artifacts / 339 blobs.
- Canonical Registry: `frs_9f61af9b...92052`, 20 entries, promotion /
  approved / active = 0 / 0 / 0.
- Factor Lab was not written by this task. At final verification its official
  `/tmp` directory contained only a `__pycache__` file and no source files, so
  the previously recorded normalized digest `f8986f27...f2635` could not be
  reverified. No Factor Lab code was consumed by this experiment.
- No LightGBM, Fresh control, production Registry, promotion, live trading,
  dependency or lockfile change.

## 3. Universe and Dataset Reality

Universe `ful_e899c9ce...df2651` is Scheme A: mean
`style_ln_mv_float` across the first 20 observed 2019 sessions, at least 15
valid observations, descending top 100. It has exactly 100 unique locked
symbols and no replacement/reselection. The source-file SHA-256 for 2019 is
`b5b457af...07aef`.

Dataset `fuhd_734dae...f95fb` binds production annual files 2019–2026,
Label Contract `lc_f4cc31c4...5b744`, Feature Snapshot
`ds_9ffe9553...fee00`, raw/model labels and sample weights. Annual row counts
are 24,341; 24,285; 24,242; 24,191; 24,200; 24,146; 23,969; and 10,867.
2026H1 contains 98 observed symbols; the two absent symbols were not replaced.

Qlib consumer view `qcv_211a189...d9d2` derives from this Dataset, not vice
versa. It retains raw OHLC, volume, amount and factor, uses no quote forward
fill, and adds an empty 2026-06-24 calendar boundary sentinel solely because
the existing service backs off one physical end-calendar session.

## 4. Historical As-of Memory and Agent Rounds

Field-level controls reject daily IC/labels, paths, Fresh/Frozen evidence,
current/future evaluation and 2025/2026 holdout. Every candidate's parameters
and orientation were selected on its research window and published in an
immutable Round Lock before the evaluation year opened.

| Round | Research | Eval | Proposed | Admitted | Trials | Mean next-year RankIC |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | 2019–2020 | 2021 | 3 | 2 | 4 | 0.02346 |
| 2 | 2019–2021 | 2022 | 3 | 0 | 0 | unavailable |
| 3 | 2019–2022 | 2023 | 3 | 1 | 6 | 0.03963 |
| 4 | 2019–2023 | 2024 | 3 | 2 | 4 | -0.01127 |

The formal run used four real `openai_codex_cli` calls with explicit
`gpt-5.6-terra`. An initial unpublised Dataset preflight used four more calls;
it exposed missing Qlib exchange columns and was discarded before Store
publication. Total calls equal the task ceiling of eight. Formal Optimization
used 14 Trials, below 48.

## 5. Final Selection and Factor Metrics

Selection used only eligible evaluation years through 2024. Two factors passed;
no third factor was forced through the gates:

- `fi_f081f972...d7be4` (momentum acceleration / idiosyncratic-volatility
  penalty): eligible-year mean RankIC 0.02034, 2 positive RankIC years and 2
  positive net-excess years.
- `fi_d825122e...e4430e` (smoothed momentum / idiosyncratic-volatility
  penalty): mean RankIC 0.01495, 4 positive RankIC years and 3 positive
  net-excess years.

Annual RankIC for the first is 0.0131, -0.0092, 0.0052, 0.0126, 0.0396,
0.0011, 0.0259 and 0.0515 (2019..2026H1). The second is 0.0134, -0.0090,
0.0057, 0.0125, 0.0398, 0.0018, 0.0263 and 0.0508. The 2026H1 IC uses only
available rows and does not override the Qlib coverage failure.

## 6. Formal Qlib Results

The main path is the real `QlibBacktestService → RedisRecordingStrategy →
SimulatorExecutor → CnExchange`. Redis logging was replaced with a no-op only
to avoid external side effects; strategy, execution, quote constraints and
cost calculation were unchanged. CnExchange deal values and costs were
observed without changing return values.

| Strategy | Full return | Fixed-100 excess | Sharpe | Max drawdown | Turnover | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `fi_f081...` | 62.48% | -20.17% | 0.338 | -19.55% | 190.60x | 152,648 |
| `fi_d825...` | 62.45% | -20.20% | 0.339 | -19.92% | 189.31x | 151,130 |
| equal-weight combo | 63.22% | -19.43% | 0.344 | -20.03% | 189.89x | 151,723 |

The combo annual net returns for 2019–2025 are 14.28%, -3.26%, 2.83%,
-8.23%, 12.31%, 49.86% and 2.57%. Annual fixed-universe excess is -20.56,
-23.18, -2.73, +0.32, +14.65, +22.72 and -4.51 percentage points.

2025 therefore did not lose money, but all selected strategies lost about
4.4–4.5 percentage points to the fixed-universe benchmark. 2026H1 returned no
formal portfolio result: score NaN was 35.17%, above the unchanged 20% gate.

## 7. Robustness and Concentration

Diagnostics did not feed Agent or reselection. Combo long-period results were:
TopK10 22.06% / Sharpe 0.058 / drawdown -23.68%; TopK30 73.45% / 0.400 /
-18.67%; daily 69.63% / 0.377 / -21.56%; 2x costs 52.09% / 0.273 /
-20.89%. Top-10 absolute position exposure was about 29% for every main
strategy. Removing the ten best return days makes cumulative return negative
(-3.3% to -4.3%), so return concentration risk is material. The 2024 result is
also a large share of total performance, indicating regime dependency.

## 8. Agent Improvement Assessment

Classification is `mixed`:

- Round 3 improved next-year RankIC over Round 1, so aggregate failure memory
  can lead to a better structure.
- Round 2 admitted nothing and Round 4 regressed to negative mean RankIC, so
  improvement is not monotonic or reliable.
- The two selected factors are extremely similar in annual RankIC and Qlib
  behavior; the equal-weight combo improves full return and Sharpe only
  marginally and worsens drawdown. Diversification evidence is weak.
- The Round 4 candidates should stop: both had negative 2024 RankIC and failed
  the cross-year final gate.
- Net excess is negative over the full period and in 2025. The experiment does
  not demonstrate persistent post-cost alpha and is consistent with historical
  regime dependence rather than durable Agent learning.

## 9. Registry, Store, Recovery and Replay

Historical final Experiment `hae_5e4b11ba...3fedd`, Qlib result
`qbr_b8be0692...f9dc0`, holdout `hhr_0f1dfbc...b4566` and assessment
`aia_944b2a5...eef0` are separate from Canonical Registry. Production Registry
writes and promotion writes are zero.

Fourteen new artifacts advanced Store Inventory to
`sai_8ee9085f...c4ee`: 93 artifacts / 357 blobs, healthy. A new empty cache
materialized and Domain-validated the final Experiment. Exact replay returned
exact-existing for all 14 artifacts, with Agent/Optimization/Qlib/Registry
calls and new artifacts/blobs all zero.

## 10. Files and Architecture Impact

Added the independent `historical_agent_experiment` domain: protocol, universe
selection, Dataset construction, as-of memory, immutable artifacts, historical
orchestrator, factor analysis, Qlib consumer adapter and formal batch runner.
Artifact Store recognizes the eight historical kinds through a formal domain
validator. Tests cover immutable 100-symbol identity, future-memory rejection,
pre-holdout selection and orientation-locked signal materialization.

This adds no API, database, UI, model, Fresh or live-trading behavior. Dataset
Snapshot remains authoritative, Qlib remains the formal portfolio engine, and
all historical evidence remains non-promotional.

## 11. Tests and Limitations

Focused tests, Artifact Store regressions, Python compilation, JSON parsing,
Context Bootstrap, diff checks and Store integrity were executed. Formal Qlib
ran 43 completed pre-2026 calls plus the explicitly recorded 2026H1 gate
rejections. The existing production Qlib tree ended at 2026-05-20, so this task
used the immutable Dataset-derived consumer view.

Known limitations: 2026H1 formal portfolio metrics are absent; Qlib's result
trade count depends on Redis logging, so exact turnover/cost evidence comes
from non-mutating CnExchange instrumentation; industry contribution is not
reported because no trusted position-to-industry return attribution artifact
exists; the current retrospective dataset may still contain vendor
retrospective revisions even though the universe rule itself is as-of 2019.
The official Factor Lab `/tmp` source is no longer intact and remains a
separate durability risk.

## 12. Rollback and Git State

Rollback is a single revert of this task commit; immutable Store artifacts are
not deleted and remain non-production historical evidence. No dependency,
lockfile, migration, API or config rollback is required. Suggested commit:
`feat(qm2): run fixed-universe agent backtest`. No push is performed.
