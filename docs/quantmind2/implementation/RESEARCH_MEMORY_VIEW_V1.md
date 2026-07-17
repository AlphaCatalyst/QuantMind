# Research Memory View v1

## Authority

Research memory is an Agent feedback view, not Project Architecture Memory, the Implementation Ledger, Registry authority, or formal evidence. Campaign Control creates it; Agents consume it read-only.

## Allowed Fields

The sanitized view may contain structural fingerprints or Template IDs, tested parameter-range summaries, mechanical success/failure counts, aggregate formal pass/reject counts without metrics, Template families, common admission failures, allowed Development Feature names, known limitations, and contaminated Development summary feedback with an explicit warning.

## Redacted Fields and Threat Model

The view excludes Frozen metric values, result IDs, candidate ranks, daily series, rows, raw/model labels, Feature Values, credentials, absolute paths, private user information, and concrete promotion comparisons. A `frozen_rejected` entry may be represented only as `not_promoted`. This prevents the next Agent iteration from optimizing against held-out evidence or reconstructing protected observations.

## Registry Sanitization

Raw Registry files are never passed to a provider. Control derives only bounded structural fingerprints and safe aggregate facts. Optional research evidence is not provider authority and its filesystem locations are omitted.

## Iteration Memory

Memory is deterministically ordered. Feedback identifies the Proposal and nullable aggregate Development mean RankIC/RankICIR, with the statement that it is adaptive, contaminated, and neither Validation nor Frozen evidence. Rejection reasons are bounded and contain no raw provider output.

## No Chain of Thought

The system stores concise rationale and structured fields only. It does not request, persist, or expose hidden reasoning. Provider request/response identity is represented by hashes plus a usage summary where available.

## Agent Read-only Boundary

Memory cannot initiate execution, consume trial budget, change Campaign state, write Registry data, or promote a Factor. Those actions remain in deterministic Control and existing execution services.
