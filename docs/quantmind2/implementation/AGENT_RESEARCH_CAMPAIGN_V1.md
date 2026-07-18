# Agent Research Campaign v1

## Scope

This contract implements a bounded research loop from a strict Research Goal through Agent proposals, DSL admission, mechanical Optimization, contaminated Development evaluation, and immutable research-only Registry entries. It does not perform formal Validation, Frozen Test access, promotion, modeling, backtesting, or trading.

## Decision / Control / Execution

- Decision: `ResearchGoal`, sanitized memory, `ResearchAgent`, and strict `ResearchDecision`. It proposes structures only.
- Control: parser, validator, novelty gate, budget, retry, state journal, orchestration, and stop rules.
- Execution: existing Factor DSL, Factor Optimization, Factor Values, the isolated Development evaluator, and Factor Registry.

Execution never calls the Agent. The Agent receives no filesystem path, row, credential, Registry document, or formal evidence detail and has no Registry writer.

## Goal and Agent

`ResearchGoal` v1 is closed, content-addressed as `rg_<sha256>`, and binds the allowed Feature terminals, operators, parameter roles, and campaign bounds. The deterministic baseline is a regression oracle and never represents an LLM. `CodexResearchAgent` is the external adapter: it runs ephemeral/read-only, uses a JSON output schema, an allowlisted environment, a timeout, bounded response bytes, and stores only provider/model, request/response hashes, usage availability, and the structured Decision.

QM2-P0-012 confirms that Provider success is not Decision success: both
bounded Codex calls exited zero, but strict parameter-contract parsing rejected
both responses. The resulting Campaign is immutable partial evidence with no
admission, Trial or Registry change; no third call or relaxed gate is allowed.

QM2-P0-012F adds a deterministic `ProposalParameterContractSummary` generated
from the live DSL parameter-field constants, parameter/role enums, AST role
contexts and Optimization Search Space schema. The Agent designs the AST first,
declares only parameters it uses, and receives mechanically validated Window
and Weight examples. Control requires Template declarations, AST uses, role
assignments and Search Space names to be identical and checks role location,
type, bounds, step and Cartesian budget. Its structured rejection contains the
Proposal index, error code, field path, declared/used/unused/searched names,
role assignments and allowed repair actions. There is still at most one repair.

Codex CLI's strict output-schema subset rejected nested `oneOf`, nested `anyOf`
and `uniqueItems` during three immutable bounded diagnostic Campaigns. Provider
transport therefore uses a closed explicit-values list profile without optional
Template `step`; the Control validator still accepts the formal Optimizer
shapes and enforces all semantic constraints. This is transport compatibility,
not a relaxed Proposal contract.

## Budget and State Machine

Hard Control limits are three iterations, four Agent calls, four proposals per iteration, eight admitted templates, 64 trials, eight failed proposals, 16 failed trials, and one repair attempt. Events persist every transition with event ID, campaign ID, iteration, previous/new state, reason, and UTC time. Supported terminal states include completed, partial, stopped-budget, and stopped-no-novelty; the working journal makes progress visible outside process memory.

## Loop

Each iteration builds sanitized memory, obtains and parses one untrusted Decision, rejects unsafe or duplicate proposals independently, plans explicit-value Optimization, executes real Factor Values, fixes direction on 2022–2024, evaluates 2025, records iteration artifacts, updates memory, and evaluates stop conditions. Add/multiply structural inputs are canonicalized for novelty; names, descriptions, defaults, ranges, and bound values do not establish novelty.

## Development-only Evaluation

`adaptive-development-2025-v1` reads only the pre-existing Development label artifact. Orientation is fixed from 2022–2024 before 2025 metrics are calculated. Every result records `predictive_claim=false`, `adaptive_research_only=true`, `contaminated_period=true`, `eligible_for_registry_promotion=false`, `is_validation_evidence=false`, and `is_frozen_evidence=false`.

## Registry Update

Only Control can append entries, and only with status `research_registered`. The optional `research_evidence` extension binds Campaign, Goal, Decision, and Development identities while enforcing quarantine flags. Legacy Registry Entry serialization omits this optional field, preserving prior Snapshot identities and readability. No Campaign path creates promotion candidates, approvals, or active Factors.

## Artifacts and Replay

Campaigns publish by staging plus atomic rename under `campaigns/<campaign_id>`, inventory every JSON file by SHA-256, reload-validate after publication, and reject content drift. A matching immutable Campaign returns exact-existing before any Agent call, Token use, execution, or Registry mutation. Completed artifacts cannot be appended.

## Real Campaign and Claims

Historical QM2-P0-008 staging lived under `/private/tmp`; formal runtime
artifacts now publish through the immutable Artifact Store and use local paths
only as disposable cache/staging. Baseline and external-provider results are
recorded in their Implementation Runs. No Development statistic is an Alpha
discovery, formal Validation, OOS result, Frozen result, or production claim.

The P0-012F external Campaign `rc_4432a5d3...c04b56` completed with one real
Provider call and no repair, six successful Trials, one contaminated
Development result and Registry successor `frs_9f61af9b...92052`. Its new
Entry is only `research_registered`; promotion, approved and active counts are
zero. Empty-cache recovery and exact-existing replay passed, with replay making
zero Agent, Optimization or Registry-write calls. P0-012 remains a separate
immutable partial Campaign.

## Deferred Formal Validation

Agent-generated `research_registered` instances require a fresh, immutable formal Validation protocol in QM2-P0-009. This task deliberately creates no bridge around that gate.
