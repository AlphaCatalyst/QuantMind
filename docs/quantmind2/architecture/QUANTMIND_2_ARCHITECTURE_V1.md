# QuantMind 2.0 Architecture v1

Status: frozen  
Effective date: 2026-07-14

## Platform flow

```text
Project Knowledge / Context
           ↓
Research Goal → Research Skill / Agent → ResearchDecision
           → Decision Validator → Bounded Code Orchestrator
           → Execution Services → Structured Result
           → Visible Research Memory → next ResearchDecision
           → Factor DSL / Canonical IR
           → Factor Optimization → Factor Validation → Factor Registry
           → Single Factor Path or Feature Snapshot / Existing LightGBM Path
           → Unified Signal Artifact → Existing Qlib Backtest → Risk Analysis
```

Data Foundation is orthogonal and authoritative:

```text
Tushare Pro Provider → Immutable Raw Data → Normalization → Dataset Snapshot
→ Factor / Feature Materialization → Parquet and Qlib consumer views
```

Provider selection is amended by accepted ADR-0011, which supersedes
ADR-0003 without changing the remaining Architecture v1 boundaries.

Experiment Management binds Candidate, Optimization Trial, Materialization,
Validation Result, Model, Signal, Backtest Result, Run, Artifact, code version,
environment, data snapshot, and random seed.

## Decision Layer

The Decision Layer contains Research Skill, Campaign Orchestrator Skill, and
Research Agent. It interprets the Research Goal, proposes hypotheses and
parameterized structures, diagnoses visible evidence, and selects the next
allowed proposal. Its formal output is `ResearchDecision` as defined by
`RESEARCH_DECISION_CONTRACT_V1.md`.

The Decision Layer proposes what to try. It cannot claim success, write
Registry state, enumerate parameter combinations, access Frozen Test, invoke
Qlib, enlarge budgets, mutate formal Artifacts, or bypass the Control Layer.

## Control Layer

The Control Layer contains the Research Decision Contract, Decision Validator,
Bounded Code Orchestrator, State Machine, Permission Guard, Budget Controller,
Idempotency/Deduplication Controller, and Experiment/Run Coordinator.

It validates proposals, permissions, state, budgets, duplication, and Frozen
Test restrictions; creates Run and Artifact references; dispatches services;
persists facts; and returns visibility-filtered summaries. Code Orchestrator is
the only controlled boundary between research judgment and deterministic
execution. Skills and Markdown may describe method and phases, but cannot own
the real loop or persistent state machine.

## Execution Layer

The Execution Layer contains DSL, Factor Compute, Factor Optimization, Factor
Validation, Factor Registry, Feature Snapshot, existing LightGBM, Signal,
existing Qlib Backtest, and Risk services. These services execute approved,
deterministic tasks and return structured facts with immutable lineage. They do
not invent hypotheses, start a next round, change formula structure, bypass
control, or turn metrics into promotion decisions.

The accepted governing boundary is ADR-0009:

> Agent可以决定“建议尝试什么”，但不能决定“尝试已经成功”。
> 执行层可以证明“发生了什么”，但不能自行发明“下一步研究什么”。
> Code Orchestrator是两者之间唯一受控边界。

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
