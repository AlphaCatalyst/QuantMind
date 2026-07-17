# Research Decision Runtime v1

## Schema

ResearchDecision v1 is a closed JSON object with schema version, Agent-supplied placeholder Decision ID, Goal ID, iteration, concise hypothesis summary, proposals, and stop recommendation. A Proposal contains a full DSL v1 Template, explicit parameter roles/search spaces, concise rationale and expected behavior, novelty claim, risks, and invalidation conditions.

## Untrusted Response

The parser accepts one plain JSON object up to 64 KiB. It rejects prose outside JSON, Markdown fences, unknown fields, NaN/Infinity, unsafe paths/URLs, executable or command-like content, secret-like assignments, and protected control/evidence keys. Parsing never executes content.

## Validation and Admission

Control checks Goal/iteration, proposal count, DSL closed schema, allowed terminals/operators, parameter declarations/roles, explicit search spaces, and remaining trial budget. Existing DSL compilation supplies lookahead/type/depth/node admission. A failed Proposal is recorded independently; other valid Proposals may continue.

## Novelty

The structural fingerprint binds the operator tree, Feature terminals, and parameter positions while abstracting bound values, defaults, ranges, Template names, output names, and descriptions. Add and multiply inputs are sorted canonically. Registry and current-Campaign fingerprints are rejected before Optimization and consume no Trial budget.

## System-generated Identity

The Agent cannot select formal identities. Control ignores its Decision ID placeholder and creates `rd_<sha256>` from Goal ID, iteration, provider/model, canonical proposals, summary, and stop recommendation. DSL, Optimization, Factor Values, Registry, Campaign, and Result identities remain owned by their formal engines.

## External Provider Safety

Codex runs ephemeral and read-only with an allowlisted environment, strict output schema, timeout, bounded response, and one repair attempt. Requests contain only the Goal safe view, sanitized memory, DSL shape summary, allowed terminals/operators, and budgets. No secret, Authorization header, raw row, label, absolute path, Registry file, or formal evidence detail is logged or transmitted.

## Rejection and Authority

Rejected output creates structured failure events and no execution. A valid Decision is advisory: only Campaign Control can admit a Template, spend budget, call Optimization or Development evaluation, publish artifacts, or append research-only Registry entries.
