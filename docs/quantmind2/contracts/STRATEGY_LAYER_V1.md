# Strategy Layer Contract v1

Status: implemented by `QM2-P0-016`.

## Fixed V1 protocol

The formal strategy is long-only `topk_dropout`, TopK 20, n_drop 5,
five-session weekly rebalance and equal target weights. It binds the Tushare
Fixed-100 Universe, Tushare Qlib View, open-price execution, one-session signal
lag, explicit CnExchange costs and the canonical CSI300 benchmark.

The object boundary is:

```text
UnifiedSignalArtifact
→ StrategySpec
→ StrategyExecutionPlan
→ PortfolioTargetArtifact
→ existing Qlib formal result
→ StrategyBacktestResult
```

Portfolio Target rows are desired rebalance weights, never actual fills.
Actual positions, orders, trades, NAV and metrics are separate result fields.
The reused historical Qlib result stores actual positions but does not expose
the pre-trade target weights produced inside TopKDropout; therefore target to
actual-target equality is explicitly `not_verifiable_from_source_qlib_result`
instead of inferred from positions.

The formal execution chain remains `QlibBacktestService →
RedisRecordingStrategy → SimulatorExecutor → CnExchange`. No simplified
backtester exists in this layer. Historical results were imported only from
Store artifact `tqb_ea39d0378a835a3b609dacef769e4bf47708be004c703243d44375c95075d768`.

## Canonicality

Absolute strategy and CSI300-relative results are canonical execution
evidence because the termination audit proves all four strategies were flat
before the affected security terminations. Fixed-100 2025 and full-period
benchmark-relative metrics remain noncanonical and `usable_for_decision=false`.
All strategy inputs remain `research_diagnostic`; results are usable for
research but not parameter optimization, Promotion or production.

The final Registry is
`srr_a2d226d4ca751100256a3d6332ed5576c29c40c53a3a78a634fbdffef74ea503`.
It has four `backtest_completed` entries and zero approved or active entries.

## Historical diagnostic results

| Signal | Net return | Annualized | Sharpe | Max drawdown | CSI300 excess |
|---|---:|---:|---:|---:|---:|
| `fi_d877…` | 91.90% | 9.50% | 0.362 | -33.75% | 26.24% |
| `fi_e0fb…` | 72.47% | 7.88% | 0.406 | -21.06% | 6.80% |
| `fi_8f557…` | 25.86% | 3.25% | 0.088 | -24.94% | -39.80% |
| equal weight | 82.45% | 8.73% | 0.474 | -19.07% | 16.79% |

The combination has the best Sharpe and lowest drawdown, but does not exceed
the best single Factor's total return or CSI300 excess. These observations did
not change any parameter.
