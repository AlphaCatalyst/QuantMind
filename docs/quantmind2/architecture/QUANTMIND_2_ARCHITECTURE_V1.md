# QuantMind 2.0 Architecture v1

Status: frozen  
Effective date: 2026-07-14

## Platform flow

```text
Project Knowledge / Context
           ↓
Research Goal → Research Agent → Factor DSL / Canonical IR
           → Factor Optimization → Factor Validation → Factor Registry
           → Single Factor Path or Feature Snapshot / Existing LightGBM Path
           → Unified Signal Artifact → Existing Qlib Backtest → Risk Analysis
```

Data Foundation is orthogonal and authoritative:

```text
TongDaXin Provider → Immutable Raw Data → Normalization → Dataset Snapshot
→ Factor / Feature Materialization → Parquet and Qlib consumer views
```

Experiment Management binds Candidate, Optimization Trial, Materialization,
Validation Result, Model, Signal, Backtest Result, Run, Artifact, code version,
environment, data snapshot, and random seed.

## Single factor path

```text
Validated Factor Instance
→ Factor Value Materialization
→ direction normalization and versioned Score Transform
→ immutable Signal Artifact
→ existing QlibBacktestService
→ existing RiskAnalyzer
```

## Multi-factor path

```text
Feature-eligible Factor Instances
→ immutable Feature Snapshot
→ existing QuantMind LightGBM
→ Prediction Signal Artifact
→ existing QlibBacktestService
→ existing RiskAnalyzer
```

## Frozen boundaries

- Agent proposes a hypothesis, parameterized structure, explanation, and
  lineage. It cannot choose final parameters or change Registry approval state.
- Canonical DSL AST is the authority for standard formula factors. v1 supports
  window, factor-internal weight, and signal threshold parameters and performs
  no structure evolution.
- Python factors are a future controlled extension and remain Docker-only.
- Factor, Model, and Portfolio Optimization are distinct domains.
- Formal performance and risk conclusions require real Qlib; Factor Lab
  SimpleTopK remains a fast research filter.
- Agent, Optimizer, and Campaign Memory cannot access Frozen Test. Observation
  of Frozen Test closes parameter tuning for that Experiment.
- Research Memory, Project Architecture Memory, and Implementation Ledger are
  separate authorities.

## Immutable identities

Factor Definition, Factor Template, Factor Instance, Candidate, Optimization
Trial, Dataset Snapshot, Factor Value Materialization, Validation Result,
Feature Snapshot, Model, Signal Artifact, Backtest Result, Experiment, Run, and
Artifact are separate records. No mutable JSON document may collapse or
overwrite these identities.
