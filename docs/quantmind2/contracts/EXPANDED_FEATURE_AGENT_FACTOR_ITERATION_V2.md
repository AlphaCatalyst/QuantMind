# Expanded-feature Agent Factor Iteration v2

## Status and evidence class

- Task: `QM2-R1-001`
- Status: implemented and executed
- Provider authority: `tushare-pro-v1`
- Experiment type: `retrospective_adaptive_factor_research`
- Runtime: `store_required`
- Agent: `openai_codex_cli`, model `gpt-5.6-terra`
- Predictive claim: false
- Promotion/production eligibility: false

This protocol is retrospective research. The 2025 and 2026H1 periods were
already observed by earlier tasks. They are opened only after the Candidate
Lock and remain `retrospective_report_only`, not Fresh Validation or Frozen
Test evidence.

## Authority and boundaries

The source market history is the immutable Tushare Fixed-500 normalized-bars
Artifact. Expanded features are materialized only for the existing immutable
Fixed-100 lock. The experiment makes no Tushare network call and never reads
retired QuantMind market data. It does not change the universe, labels,
benchmark, execution costs, Registry promotion state or strategy parameters.

The fixed execution contract is TopK 20, n_drop 5, five-trade-date rebalance,
equal weights, one-trade-date signal lag, open execution and CSI300 through
`QlibBacktestService -> RedisRecordingStrategy -> SimulatorExecutor ->
CnExchange`. Fixed-100-relative metrics are noncanonical and unavailable to
selection or Agent feedback.

## Existing-factor audit

Before any Agent call, `ExistingFactorDefinitionAuditV1` reconstructs each of
the three existing factors from formal Unified Signal and historical Round
Lock Artifacts. It freezes Template/Instance IDs, canonical AST and readable
DSL, inputs, parameter schema and selected values, orientation, value Artifact,
lineage, structural fingerprint, hypothesis, risks and human explanation.
Failure to recover all three definitions blocks the Campaign.

The reconstructed formulas are:

1. `cs_rank((rolling_mean(mom_ret_1d,window=momentum_window) /
   (liq_volume_ratio_5 * (absolute(style_beta_20) + 1))))`
2. `cs_zscore((rolling_mean(liq_volume_ratio_5,window=liquidity_window) -
   absolute(style_beta_20)))`
3. `cs_rank((rolling_max(mom_ret_1d,window=peak_window) /
   (rolling_mean(style_idio_vol_20,window=peak_window) + 1)))`

## Feature Catalog v2

Twenty-six price/volume candidates are computed without fill and evaluated by
coverage, PIT semantics and redundancy. The allowlist is capped at 24. The
formal catalog selected:

`mom_ret_1d`, `liq_volume_ratio_5`, `style_beta_20`,
`style_idio_vol_20`, `amihud_illiquidity_20`, `mom_ret_20d`,
`gap_return_1d`, `mom_ret_5d`, `turnover_mean_5`,
`intraday_range_1d`, `volatility_5d`, `amount_ratio_20`, `log_circ_mv`,
`downside_volatility_20d`, `price_vs_ma_5`, `price_vs_ma_20`,
`volatility_20d`, `turnover_mean_20`, `liq_volume_ratio_20`,
`amount_ratio_5`, `price_vs_ma_60`, `style_beta_60`, `mom_ret_60d`, and
`volatility_60d`.

All selected features pass overall finite coverage >= 90%, annual 2021--2024
coverage >= 85%, Infinity = 0 and duplicate key = 0 on the real Dataset. The
Catalog records source columns, canonical formula, lookback, min periods,
ddof, grouping/sort, adjustment semantics, no-fill policy, warm-up, PIT
statement and dtype. Feature computation is continuous across calendar years.
The Dataset is Parquet/Zstandard and uses float32 after quality calculation.

## Redundancy gate

`FeatureAndFactorRedundancyGateV1` normalizes parameter positions,
commutative add/multiply order and a root negate/orientation flip. Exact
structural or equivalence matches to the existing three factors or an earlier
Candidate are rejected. High empirical correlation remains visible as
`redundancy_risk=high` and is penalized by ordering; it is not silently
discarded when the structure differs.

## Campaign and Fold isolation

The bounded Campaign runs at most six rounds. Each round permits two Agent
calls including repair, three proposals, two admitted Templates, eight Trials
per Template and 16 Trials total. Task ceilings are 12 Agent calls, 12 admitted
Templates and 96 Trials. Structure comes from the Agent; only factor-internal
lookback and weight parameters are searched by Control.

Every admitted Template completes four independent expanding-window locks:

1. research 2019--2020, evaluate 2021;
2. research 2019--2021, evaluate 2022;
3. research 2019--2022, evaluate 2023;
4. research 2019--2023, evaluate 2024.

Each Fold selects its parameters and orientation only from that Fold's
research interval. All Evaluation years are retained. The Agent Memory exposes
only aggregate failure information through 2024; it contains no daily label,
daily IC/return, stock contribution, 2025/2026H1 result, or noncanonical
Fixed-100-relative metric.

## Eligibility and ordering

Eligibility requires four valid Folds, >=90% finite coverage, no Infinity,
at least three positive-RankIC Folds, positive median RankIC, worst RankIC
above -0.01, at least two positive CSI300-net-excess Folds, positive median
CSI300 net excess, formal cost, turnover below the median of formal weak-factor
evidence, and maximum correlation to the existing factors below 0.90.

Ordering is the frozen stable lexicographic order: positive RankIC Fold count,
positive CSI300-excess Fold count, median/worst RankIC, median/worst CSI300
excess, return without best ten days, absolute drawdown, turnover, old-factor
correlation, redundancy risk and Factor Instance ID. Later report periods
cannot enter the key.

## Formal result

The run completed all six rounds with 6 real Agent calls, 12 admitted
Templates, 38 factor-parameter Trials and 50 formal Qlib calls. Rounds did not
continuously improve. One Candidate passed all gates:

- Template: `ft_e05bf43fe114790376fb10d27499f43f848cf536b34e1e3f9485c5eb0157d8c7`
- Instance: `fi_e2dd60578eb2d4a08b83096b53a549c3e8375768b0496adc5d14ed2be0d8576f`
- DSL: `cs_rank((rolling_mean(amount_ratio_5,window=change_window) /
  (absolute(delta(price_vs_ma_60,periods=change_window)) + 1)))`
- Fold-selected window: 15 in each independently selected Fold
- Positive RankIC Folds: 3/4
- Positive CSI300-net-excess Folds: 4/4
- Median/worst RankIC: 0.001440 / -0.004723
- Median/worst CSI300 net excess: 0.168770 / 0.099099
- Median turnover: 35.317120
- Maximum old-factor correlation: 0.275733

The Candidate is locked only as `research_registered`. Contract revision 2
adds the readable canonical DSL to the immutable Lock and explicitly
supersedes, rather than overwrites, the preliminary Lock/Assessment/Experiment.

## Later-period report

In 2025 the locked factor has mean RankIC 0.012743, net return 10.83%, CSI300
return 21.75%, CSI300 net excess -10.91 points, Sharpe 0.675, drawdown -7.11%,
turnover 32.58 and best-ten-days contribution 19.87%.

In 2026H1 it has mean RankIC 0.012733, net return -16.56%, CSI300 return
4.27%, CSI300 net excess -20.84 points, Sharpe -2.735, drawdown -17.94%,
turnover 16.94 and best-ten-days contribution 13.37%.

The result is classified `mixed`: historical Fold stability and independence
improved, but CSI300-relative performance failed in both already-observed
later periods. It is a research candidate worth future explicitly authorized
strategy validation, not a validated or production Alpha.

## Artifact and replay contract

Formal v2 Artifact kinds are existing-factor audit, feature catalog, feature
Dataset, round result, Candidate Lock, assessment and experiment. Store
integrity must be healthy with zero missing and unreferenced blobs. Cold
recovery validates every original and superseding Artifact. Exact replay
chooses the unique highest contract revision and must report zero Agent,
Optimization, Qlib, network, Promotion, new Artifact and new blob counts.
