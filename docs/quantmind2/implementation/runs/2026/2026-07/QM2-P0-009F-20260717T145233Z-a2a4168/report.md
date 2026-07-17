# QM2-P0-009F Implementation Report

## Task Summary

QM2-P0-009F records complete Git-derived `changed_files` correction evidence
for immutable Run `QM2-P0-009-20260717T141500Z-34dfa6e`. The target Report,
Manifest, commit, Fresh Validation implementation, research controls and
results remain unchanged.

## Goal, Scope, and Explicit Non-goals

The scope is Git diff/blob verification, a strict correction Artifact and
Schema, a `corrects` relationship, omission-prevention guard, tests, Project
Memory, and this Run. There is no target Run rewrite or amend, Agent call,
Optimization, Development or Fresh evaluation, Watermark refresh, Registry
change, promotion, database migration, production database access, dependency,
lockfile, API, UI, model, signal, Qlib or backtest change.

## Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch/base: `master` / `a2a416898181b6269217e75012e66ad7ebc4c395`
- Dirty before: false; unrelated dirty files: none.
- Target base/containing commits: `34dfa6eb50d7bd9405c3d3bdf0019aa84f9de432`
  / `a2a416898181b6269217e75012e66ad7ebc4c395`.

## Historical Failure Reproduction

The formal Planner returned exit code 2, `validated=false`, `indexable=false`,
mandatory failure `changed_files`, and Evidence Gap `GIT_INCONSISTENT`. There
were no warnings or parser errors. This failure remains intentional after the
correction because the target Run is immutable.

## Git Reconstruction and Classification

`git diff --name-status -M` over the target base-to-containing interval is the
sole path/status authority. Exact before/after SHA-256 values come from raw
`git show <commit>:<path>` bytes. The target Manifest itself is excluded only
from business ChangedFiles, as required by Manifest v2.

- Recorded business entries: 12
- Verified business entries: 35
- Missing entries: 23
- Unexpected entries: 0
- Hash mismatches: 0
- Change-type mismatches: 0
- Canonical verified inventory SHA-256:
  `0433d5e114c61ab1f6efb4c2aaaa0bbc0574163968833fd9c3c802d94380a6f6`

The strict Artifact stores recorded/actual paths, all missing entries, the full
sorted verified inventory, classifications, immutable target hashes and
unchanged Fresh Validation identities.

## Omission Root Cause and Prevention

Root cause is manual inventory omission: the QM2-P0-009 Manifest was assembled
with a representative 12-entry `changed_files` list while its integrity path
inventory correctly named the wider commit. The producer behaved as designed;
the formal post-commit Planner detected the discrepancy. No producer semantic
change is needed.

The implementation contract now states that no task may report `completed`
until the committed Run passes Planner with `validated=true`, `indexable=true`,
zero gaps and zero warnings. The correction tool independently reconstructs
Git statuses and raw blob hashes; tests cover add/modify/delete/rename, missing,
unexpected, hash/type mismatch, stable ordering and canonical hashing. It never
rewrites a published Manifest.

## Correction Semantics and Relationship

The original Run remains Git-inconsistent and non-indexable. This Run carries
one relationship of type `corrects` to the original Run. It does not supersede,
replace, reexecute or mutate the target. PostgreSQL indexes correction evidence
as a query projection only; a dependency fixture retains the exact target Run
ID without pretending the target passed Git validation.

## Fresh Validation Identity Invariance

The following remain byte/identity unchanged:

- Candidate Lock `fvcl_716d7465285f7a8f541924877aa3acde9e90a38efe7d10dea2e20d6874063c7b`
- Exposure Ledger `rdel_56d95b77f42f5b9784badaf3558e92e375d87be9cc1194143e334aba3e55f5ff`
- Protocol `fvp_93163e1b4f82b52154bf0472b1cd165916f8ecae722ab851dd7fc4210bb5a867`
- Watermark `fdw_3459fb5a20fb60707c6bf001dc194a931cfea7cddf250de2a099cba97efaa248`
- Registry `frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5`
- Locked Factors `fi_a472a369...f46e7`, `fi_85428fbe...100b7`, and
  `fi_79b37070...02516`.

Eligible dates remain zero, state remains `awaiting_first_fresh_date`, no real
Fresh Result exists, and promotion candidate/approved/active remain 0/0/0.

## Tests and Verification

Focused correction and Context tests passed pre-commit with the one deliberate
009F containing-commit test skipped. Full relevant Fresh/Admission/Registry/
Campaign/Validation/Optimization/DSL/Dataset/Manifest/Indexer/Context
regression, JSON parsing, `py_compile`, Context Bootstrap and `git diff --check`
are recorded in the Manifest. After the single commit, the original Run is
rechecked as failed, while this Run must pass Planner, complete all 11 Domain
families, and pass isolated PostgreSQL index/exact replay with container cleanup.

## API, Database, Configuration, Security, and Compatibility

No API, database schema, production data, configuration, dependency or lockfile
changed. The Artifact contains repository-relative paths, public identities and
hashes only. Existing Manifest/Planner/Indexer semantics are unchanged. Rollback
is a revert of this additive correction commit; it cannot affect the immutable
target Run or research artifacts.

## Known Limitations and Recommended Next Task

The target Run remains permanently non-indexable; consumers must display the
separate correction relationship. Future large Fresh accrual/results still need
durable storage. The only recommended task is
`QM2-P0-010 — Persistent Research Artifact Store v1`. `QM2-FV-001` remains
conditional on at least 60 post-lock mature dates.

## Git and Artifact Index

This Run is prepared as `completed_uncommitted`, `result_commit=null`, then
committed once with `docs(qm2): record fresh validation manifest correction`.
No amend or push is authorized. Artifacts are the strict correction JSON,
Schema, this Report and Manifest v2.
