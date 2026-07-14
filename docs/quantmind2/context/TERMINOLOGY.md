# Terminology

- **Factor Definition**: stable economic identity and family of a factor.
- **Factor Template**: parameterized Canonical DSL AST.
- **Factor Instance**: immutable template plus bound parameters.
- **Candidate**: Agent proposal; it has no approval authority.
- **Optimization Trial**: one parameter assignment and objective observation.
- **Dataset Snapshot**: published, immutable authority for research data.
- **Materialization**: computed factor values for one instance and snapshot.
- **Validation Result**: immutable evidence for one materialization and policy.
- **Feature Snapshot**: locked training matrix and factor/version references.
- **Signal Artifact**: immutable, lagged, versioned score consumed by Qlib.
- **Research Memory**: Agent-facing research summaries without Frozen Test.
- **Project Architecture Memory**: charter, architecture, ADRs, constraints.
- **Implementation Ledger**: immutable semantic record of implementation tasks.
- **Frozen Test**: access-controlled final evaluation data that closes tuning.
- **Decision Layer**: Research Skill, Campaign Orchestrator Skill, and Research
  Agent that propose hypotheses and next research actions. It is not an
  executor or approval authority; its boundary ends at a `ResearchDecision`.
- **Control Layer**: policy and coordination layer that validates Decisions,
  permissions, state, budgets, duplication, data access, Runs, dispatch, and
  recovery. It is not a source of financial hypotheses; it separates proposal
  semantics from deterministic service calls.
- **Execution Layer**: versioned services that execute approved deterministic
  tasks and return facts. It is not an autonomous researcher or promotion
  authority; it consumes only Control Layer dispatches.
- **ResearchDecision**: immutable Decision Layer proposal containing one
  allowed action, rationale, evidence, parameter/budget suggestions, and
  context IDs. It is not a command, Run, result, or Registry transition.
- **Decision Validator**: planned Control Layer component that validates a
  ResearchDecision's schema and cross-object policies before Run creation. It
  is not a research evaluator or execution service.
- **Code Orchestrator**: planned bounded Control Layer authority for the real
  loop, persistent state, permissions, budget, retries, idempotency,
  concurrency, Run/Artifact coordination, dispatch, and recovery. It is not a
  Skill, prompt, hypothesis generator, or deterministic compute service.
- **Execution Service**: deterministic, versioned capability such as DSL,
  optimization, validation, Registry, LightGBM, Qlib, or Risk. It is not
  allowed to choose the next research action; it returns structured facts.
- **Visible Research Memory**: visibility-filtered, lineage-bound summaries
  returned to the Decision Layer after result persistence. It is not the
  authoritative result store and must never expose Frozen Test details.
