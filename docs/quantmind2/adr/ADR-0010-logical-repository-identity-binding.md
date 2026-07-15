# ADR-0010: Logical Repository Identity Binding

- ADR ID: ADR-0010
- Status: accepted
- Date: 2026-07-15
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.project_knowledge`
- Related Implementation Runs: `QM2-P0-002B-20260715T090630Z-d33f281`

## Context

`ImplementationRun.repository_root` is a persisted cross-machine identity. The
v1 Manifest field with the same name contains the absolute checkout path used
during execution. An absolute path is machine-specific and therefore cannot be
copied into the logical identity without corrupting cross-machine lineage.

## Decision

Ledger `ImplementationRun.repository_root` remains the stable logical
repository identity, such as `quantmind-main` or `factor-lab-v7`.

Every indexing invocation must explicitly bind one caller-supplied logical
repository ID to one absolute local Git worktree root. The binding validates
that the supplied path is exactly the worktree root. It never derives identity
from the current directory, directory name, username, remote URL, report prose,
Manifest execution path, or similarity heuristics.

The v1 Manifest absolute path remains informational execution evidence. It is
not the logical identity and is not persisted into the Domain identity field.
No machine-specific binding configuration is committed. Git remote data may be
future optional evidence but cannot select the logical identity.

## Consequences

- Indexing is intentionally impossible without an explicit trusted binding.
- The same logical repository can be indexed from different checkout paths.
- A local path cannot silently create a second repository identity.
- Manifest v1 remains readable without pretending that its absolute path has
  cross-machine authority.

## Alternatives Considered

- **Persist the Manifest absolute path:** rejected because it is machine-local.
- **Infer from directory basename:** rejected because names are not unique.
- **Infer from Git remote:** rejected because remotes may be absent, mutable,
  duplicated, or credential-bearing.
- **Infer from report text or repository URL similarity:** rejected because
  prose and heuristics are not identity authority.

## Non-goals

This ADR does not define a central repository catalog, remote verification,
Manifest v2, API, UI, watcher, webhook, production database configuration, or
Factor Lab indexing.

