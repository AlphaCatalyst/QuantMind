# ADR-0009: Decision–Control–Execution Separation

- ADR ID: ADR-0009
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.research_skill`, `quantmind2.decision_validator`, `quantmind2.code_orchestrator`, `quantmind2.experiment_manager`, `quantmind2.factor_optimization`, `quantmind2.factor_validation`
- Related Implementation Runs: `QM2-P0-001G-20260714T142514Z-05c2db2`

## Context

AI factor research needs probabilistic judgment to form hypotheses, but the
same actor must not also own authority, persistent loop state, budgets,
idempotency, deterministic execution, and interpretation of results. Combining
decision and execution makes a proposal indistinguishable from an observed
fact. Combining control and execution leaves policy scattered across services.

The official V7 Factor Lab provides bounded rounds, checkpoints, budgets,
candidate generation, Docker execution, validation, and memory. It does not
provide the target `ResearchDecision` proposal boundary: generated Candidates
still include complete `factor_impl.py`, the Agent chooses structure and
concrete parameters together, and driver/runner code combines research-choice,
loop-control, dispatch, and result-feedback responsibilities.

## Decision

QuantMind 2.0 separates research into three layers.

### Decision Layer

The Decision Layer consists of Research Skill, Campaign Orchestrator Skill,
and Research Agent. It understands the Research Goal, proposes financial
hypotheses, creates or revises Factor Templates, diagnoses whether a problem is
structural, parametric, data-related, or cost-related, chooses the next
structured research action, and cites rationale and evidence.

Its output is a `ResearchDecision` proposal, never an execution result. It must
not write Registry state, create terminal database records, enumerate a
parameter space, access Frozen Test, skip Validation Gates, call Qlib directly,
declare a factor valid or production, loop without a bound, enlarge its own
budget, mutate formal Artifacts, or bypass the Code Orchestrator.

### Control Layer

The Control Layer consists of the Research Decision Contract, Decision
Validator, Bounded Code Orchestrator, State Machine, Permission Guard, Budget
Controller, Idempotency/Deduplication Controller, and Experiment/Run
Coordinator.

It validates schema, actor permission, campaign and target state, budget,
duplication, and Frozen Test restrictions. It creates Experiment, Run, and
Artifact references; dispatches deterministic services; handles timeout,
retry, failure, and recovery; persists execution facts; and returns a visible
result summary to the Decision Layer.

It must not invent financial hypotheses, silently change a Factor AST, choose
a new research direction for the Agent, create new formula logic from metrics,
or reinterpret execution results as financial theory.

### Execution Layer

The Execution Layer consists of DSL, Factor Compute, Factor Optimization,
Factor Validation, Factor Registry, Feature Snapshot, existing LightGBM Model,
Signal, existing Qlib Backtest, and Risk services.

Each service executes an approved deterministic task, returns structured facts,
binds versions/data/environment/Artifacts, and obeys state, permission, and data
access restrictions. It must not form hypotheses, start another research round,
modify formula structure from results, bypass the Control Layer, access
unauthorized data, or turn a metric into a promotion decision.

### Governing rule

> Agent可以决定“建议尝试什么”，但不能决定“尝试已经成功”。
> 执行层可以证明“发生了什么”，但不能自行发明“下一步研究什么”。
> Code Orchestrator是两者之间唯一受控边界。

The Code Orchestrator is in the Control Layer because it owns authority,
persistent state transitions, budgets, concurrency, retries, idempotency,
dispatch, and recovery. A Skill or Markdown runbook may describe research
method and campaign stages, but cannot be the sole loop executor or persistent
state machine.

## Parameter Search Boundary

A Skill may propose parameter roles and economically reasonable ranges. It may
not try individual combinations. Factor Optimization owns window,
factor-internal weight, and signal-threshold Trials. Code creates, executes,
records, and deduplicates every Trial. Agent-visible summaries exclude Frozen
Test. One Trial cannot mix parameter search with structure modification.

## Current Gap

- 【代码确认】`agent_research/minimal_research_driver.py` uses
  `MinimalAgentResearchDriver._generate_validated`, `_materialize_session_candidate`,
  `_execute`, and `_round_feedback` to generate full source packages, execute
  them, and feed metrics plus implementation text into later prompts.
- 【代码确认】`orchestrator/batch_draft_prompt_builder.py` explicitly requests a
  `factor_impl.py` ABI and embeds research heuristics and memory guidance.
- 【代码确认】`agent_research/bounded_campaign_runner.py` owns loop selection,
  budget checks, CLI dispatch, persistence, stopping, and next-mode selection,
  but consumes Candidates rather than a formal decision proposal.
- 【代码确认】`orchestrator/execution_backend_interface.py` provides a controlled
  Docker-first `ExecutionBackendGateway`, while the caller still supplies an
  execution request derived from the Python-first Candidate contract.
- 【代码确认】`productization/bounded_v7_session_orchestrator.py` has explicit
  session/candidate states and checkpoints, but no Decision Validator or
  `ResearchDecision` admission transition.
- 【代码确认】Factor Optimization is not an independent execution service;
  Agent-generated implementations combine structure and concrete parameters.
- 【目标架构决策】Candidate, Decision, Execution Request, Execution Result, and
  promotion evidence are separate objects with separate authority.
- 【未来改造要求】V7 donor capabilities require controlled migration behind
  the ResearchDecision/Code Orchestrator boundary; this ADR implements no such
  runtime migration.

## Consequences

- Every Agent-initiated action must enter through a validated
  `ResearchDecision`.
- Execution facts cannot imply promotion; Registry transitions retain separate
  policy authority.
- Retry and deduplication are Control Layer behavior, not Agent prompting.
- Execution services become deterministic and independently testable.
- Visible Research Memory contains allowed summaries only and cannot expose
  Frozen Test details.

## Alternatives Considered

- **Decision plus execution only:** rejected because permission, budgets,
  state, idempotency, retries, and recovery would have no authoritative owner.
- **Agent-owned loop state:** rejected because probabilistic model output is not
  a durable state machine and cannot guarantee bounded, idempotent recovery.
- **Execution-service auto-progression:** rejected because deterministic
  services must not invent research intent from metrics.
- **Markdown as orchestrator:** rejected because prose cannot be the sole
  authority for concurrent, persistent, recoverable state transitions.

## Non-goals

This ADR does not implement a Skill runtime, Decision Validator, Code
Orchestrator v2, database, API, DSL, optimization, validation, Registry, TDX,
LightGBM change, Qlib change, or UI.
