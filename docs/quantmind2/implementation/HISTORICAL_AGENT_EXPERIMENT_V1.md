# Historical Agent Experiment v1

This contract governs bounded retrospective Agent iteration. It is not Fresh
Validation and has no production Registry or promotion authority.

The immutable control sequence is `FixedUniverseLock → Historical Dataset →
HistoricalAsOfResearchMemory → external Agent → factor-only Optimization →
HistoricalRoundCandidateLock → next-year aggregate evaluation`. Four rounds
use research ends 2020, 2021, 2022 and 2023 and evaluation years 2021–2024.
Each round permits at most two Agent calls, three Proposals, two admitted
Templates, six Trials per Template and twelve total Trials.

Memory may contain the feature/operator catalog, earlier Templates, rejection
reasons, structure fingerprints and already-opened annual aggregates. It may
not contain daily labels/IC, paths, current/future evaluation, 2025/2026
holdout, Fresh or Frozen evidence. Candidate parameter and orientation are
selected from the research window and locked before the next-year data opens.

The portfolio contract is the existing `QlibBacktestService`,
`RedisRecordingStrategy`, `SimulatorExecutor` and `CnExchange`: TopK 20,
`n_drop=5`, equal weight, five-trading-day rebalance, T+1 signal lag, open
execution and the existing A-share commission, tax, transfer, impact, price
limit, suspension and round-lot behavior. Dataset Snapshot is authoritative;
the Qlib binary tree is a derived consumer view. Missing quotes are NaN and are
never forward-filled or replaced.

Final selection uses only evidence through 2024 and locks at most three
candidates. 2025 and 2026H1 are opened once and never fed to Agent, Optimizer
or selection. Historical results live in `HistoricalAgentExperimentRegistry`
artifacts and cannot change Canonical Registry status.

Store artifact kinds are `fixed_universe_lock`,
`fixed_universe_historical_dataset`, `historical_round_lock`,
`historical_round_evaluation`, `qlib_backtest_result`,
`historical_holdout_result`, `agent_iteration_assessment` and
`historical_agent_experiment`. Exact replay resolves the final experiment and
must make zero Agent, Optimization, Qlib and Registry calls and create zero
artifacts/blobs.
