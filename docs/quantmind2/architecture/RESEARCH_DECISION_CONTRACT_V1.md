# Research Decision Contract v1

Status: accepted architecture contract

Related decision: `ADR-0009`

## 1. Contract Role

`ResearchDecision` is the only formal proposal sent from the Decision Layer to
the Control Layer. It is a proposal, not a command, execution result, approval,
or Registry transition. The Control Layer may accept it, reject it, or request
revision.

A Decision cannot directly change Registry state, contain Frozen Test data,
claim execution-generated IDs that do not exist, or cite invented evidence.
Every `evidence_ref` must resolve to an existing Artifact or an allowed result
summary before dispatch.

## 2. Fields

| Field | Meaning | Boundary |
| --- | --- | --- |
| `decision_id` | Caller-created immutable proposal ID | Used as an idempotency key; not an execution Run ID |
| `decision_schema_version` | Contract version, `1.0.0` | Does not select service implementation version |
| `campaign_id` | Existing campaign scope | Must resolve and allow the requested action |
| `experiment_id` | Existing Experiment scope | Must not be fabricated by an Agent |
| `round_id` | Current decision round | Identifies context, not execution completion |
| `actor_type` | `research_skill`, `campaign_orchestrator_skill`, or `research_agent` | Permission Guard maps actor type and identity to actions |
| `action` | One allowed v1 action | No arbitrary service or method names |
| `target_type` | Campaign, family, template, or instance kind | Must match the action |
| `target_id` | Existing target ID, or null only for creation | Never an anticipated result/Artifact ID |
| `rationale` | Financial and diagnostic reason | Mandatory; not proof of success |
| `evidence_refs` | Existing Artifact/result-summary references | Must be visible to the actor and Frozen-Test-free |
| `requested_parameters` | Structure revision, parameter roles, or range suggestions | Suggestions only; no approved search space |
| `requested_budget` | Requested trial/time/compute ceiling | Controller may reduce or reject it; Agent cannot expand it |
| `expected_outcome` | Falsifiable expected observation | Not a guaranteed metric or promotion claim |
| `created_at` | UTC creation timestamp | Proposal time, not execution time |

The machine contract is
`architecture/schemas/research_decision_v1.schema.json`. Its validation level
is the repository's bounded zero-dependency JSON Schema subset, not a complete
general Draft 2020-12 implementation.

## 3. Allowed Actions

### CREATE_TEMPLATE

- Use when: proposing a new parameterized Factor Template from a research
  hypothesis.
- Required input: rationale, expected outcome, template proposal, parameter
  roles, and evidence references; `target_id` is null.
- Control checks: actor permission, campaign state, DSL/schema admission,
  novelty/duplicate policy, and budget for creation processing.
- Success state: a new draft Template version and Run/Artifact references.
- Failure: rejected or revision-required Decision; no Template terminal state.
- Forbidden side effects: final parameter binding, validated Factor creation,
  production Registry write, execution, or backtest.

### REVISE_TEMPLATE

- Use when: evidence supports a structural revision of an existing Template.
- Required input: parent Template ID, revision proposal, rationale, evidence.
- Control checks: parent exists and is revisable, proposal is structurally
  distinct, permission and campaign state allow revision.
- Success state: a new draft Template version referencing its parent.
- Failure: original Template remains unchanged; Decision is rejected or needs
  revision.
- Forbidden side effects: overwriting the parent, binding final parameters, or
  combining the revision with an Optimization Trial.

### REQUEST_OPTIMIZATION

- Use when: an admitted Template has parameter roles needing search.
- Required input: Template target, parameter roles, economically reasonable
  range suggestions, objective summary, requested budget.
- Control checks: Template eligibility, allowed parameter roles, validated
  Search Space, remaining budget, duplication, dataset access, Frozen Test ban.
- Success state: an Optimization Run is created and deterministic Trials may be
  dispatched.
- Failure: no Trial is created, or the request is revision-required.
- Forbidden side effects: Agent enumeration of combinations, structure change,
  direct best-parameter declaration, or Frozen Test use.

### REQUEST_VALIDATION

- Use when: a selected immutable Factor Instance and Materialization are ready
  for an allowed validation stage.
- Required input: Factor Instance target, evidence refs, requested validation
  stage and budget.
- Control checks: target/materialization lineage, state, policy, dataset access,
  duplicate validation, and Frozen Test authorization.
- Success state: a Validation Run is created and an allowed validation service
  is dispatched.
- Failure: no result or Registry transition is fabricated; retry follows policy.
- Forbidden side effects: choosing a Frozen Test interval, seeing restricted
  details, or promoting the Factor from the Decision.

### ARCHIVE_TEMPLATE

- Use when: continued research on a Template is no longer justified.
- Required input: Template target, stopping rationale, evidence.
- Control checks: permission, target state, active dependents, and archive
  policy.
- Success state: an approved archive transition request is recorded; history
  and Artifacts remain immutable.
- Failure: Template remains in its prior state.
- Forbidden side effects: deletion, Artifact mutation, or cascading promotion
  changes.

### STOP_FAMILY

- Use when: a Factor Family should receive no further exploration in the
  current Campaign.
- Required input: family target, stop reason, evidence.
- Control checks: actor permission, campaign/family state, conflicting active
  Runs, and stop-policy rules.
- Success state: family exploration is closed for the Campaign and the reason
  is persisted.
- Failure: no running work is silently cancelled outside policy.
- Forbidden side effects: deletion of family history or cross-campaign ban.

### STOP_CAMPAIGN

- Use when: objective, budget, safety, or evidence supports ending a Campaign.
- Required input: campaign target, stop reason, evidence.
- Control checks: campaign state, actor permission, active Run handling, and
  sealing requirements.
- Success state: controller seals Campaign state, Runs, and Artifact references.
- Failure: Campaign remains in its previous recoverable state.
- Forbidden side effects: deleting evidence, impersonating successful
  completion, or skipping required final persistence.

## 4. Decision Validation Pipeline

| Step | Input | Output | Failure state | Owner | Retry | New Run? |
| --- | --- | --- | --- | --- | --- | --- |
| Schema Validation | Raw Decision JSON and v1 schema | Parsed proposal | `rejected_schema` | Decision Validator | Only with revised Decision | No |
| Actor Permission Check | Proposal, actor identity, policy | Authorized proposal | `rejected_permission` | Permission Guard | No, unless authority changes | No |
| Campaign State Check | Campaign ID/state and action | Campaign-admissible proposal | `rejected_campaign_state` | State Machine | After valid state change | No |
| Target State Check | Target identity/version/state | Target-admissible proposal | `rejected_target_state` | State Machine | After valid state change or revision | No |
| Budget Check | Requested budget and remaining ledger | Approved/reduced ceiling | `rejected_budget` | Budget Controller | Revised lower request only | No |
| Duplicate / Idempotency Check | Decision ID and semantic fingerprint | New or replay classification | `conflict_duplicate` | Idempotency Controller | Exact replay returns prior result | No |
| Frozen Test Access Check | Actor, action, dataset policy, evidence refs | Allowed data scope | `rejected_frozen_test_access` | Permission Guard | No within same unauthorized flow | No |
| Experiment / Run Creation | Accepted proposal and approved budget | Immutable Run and Artifact slots | `control_persistence_failed` | Experiment/Run Coordinator | Safe idempotent retry | Yes |
| Execution Service Dispatch | Run task and approved inputs | Dispatch receipt | `dispatch_failed` or `timed_out` | Code Orchestrator | Policy-bound retry using same Run/attempt lineage | No new logical Run; attempt recorded |
| Result Persistence | Structured service result and Artifact hashes | Immutable execution facts | `result_persistence_failed` or `outcome_unknown` | Experiment/Run Coordinator | Reconcile before retry | No |
| Visible Result Summary | Persisted facts and visibility policy | Frozen-Test-free summary | `summary_withheld` | Code Orchestrator | Rebuild from persisted facts | No |
| Research Memory Update | Visible summary and lineage | Versioned memory entry | `memory_update_failed` | Research Memory adapter under Control Layer | Idempotent retry | No |

Only the Experiment/Run Creation step creates a new logical execution Run.
Retries remain attempts under that Run unless policy explicitly creates a new
Decision and Run.

## 5. Skill, Markdown, and Code Boundary

### Skill

Defines research method, economic reasoning, how to read visible results, how
to select the next proposal, and how to emit `ResearchDecision`.

### Markdown Orchestrator

Describes campaign phases, available actions, stopping criteria, and decision
context. It is documentation and guidance, not a live state authority.

### Code Orchestrator

Owns the actual loop, persistent state, budget, retries, timeout, idempotency,
concurrency, permissions, Experiment/Run/Artifact creation, service dispatch,
and recovery.

> Markdown不能成为唯一循环执行器，也不能承担持久状态机职责。

## 6. Parameter Optimization Boundary

- Skill proposes parameter roles and economic range suggestions.
- Skill never iterates concrete combinations.
- Factor Optimization searches `window`, factor-internal `weight`, and signal
  `threshold` under the controller-approved Search Space and budget.
- Every Trial is code-generated, executed, persisted, and deduplicated.
- Agent sees only permitted summaries.
- Frozen Test never enters the Skill loop.
- Structure revision and parameter search cannot share one Trial.

## 7. Frozen Test and Promotion Boundary

Frozen Test references and details are rejected from Decisions, evidence
visibility, requested parameters, and Agent memory. Only an authorized final
Validation Run can access Frozen Test. A metric or execution-service result is
evidence, not a promotion instruction. Registry state changes require their own
policy-controlled transition.

## 8. Current V7 Gap

- 【代码确认】`MinimalAgentResearchDriver._generate_validated` asks the model for
  a Candidate containing `source_files`; `_response_schema` requires
  `factor_impl.py`, `factor_spec.json`, and `rationale.md`.
- 【代码确认】`MinimalAgentResearchDriver._round_feedback` includes prior
  implementation source and metrics in the next prompt context.
- 【代码确认】`BatchDraftPromptBuilder` specifies the complete
  `compute_factor(panel, ctx)` Python ABI and extensive research heuristics.
- 【代码确认】`BoundedCampaignRunner.run`, `choose_next_mode`, `_execute_session`,
  and `_record_session` combine loop state, budget, dispatch, result selection,
  and memory updates.
- 【代码确认】`BoundedV7SessionOrchestrator` provides useful deterministic state
  and checkpoint controls, and `ExecutionBackendGateway.execute` enforces the
  Docker boundary, but neither consumes a formal `ResearchDecision`.
- 【代码确认】`HardenedEvaluator.run_hardened_evaluation` emits research-only
  metrics and a gate preview; it is not an isolated Frozen Test authority.
- 【目标架构决策】Decision, control admission, deterministic task, result, and
  promotion are independent semantic objects.
- 【未来改造要求】Migrate selected V7 capabilities behind the contract without
  treating the current Python-first pipeline as already compliant.

## 9. Non-implementation Notice

This document is an architecture contract only. There is no ResearchDecision
Python model, Decision Validator, Skill runtime, Code Orchestrator v2, state
machine, permission engine, budget service, or persistence implementation in
this task.
