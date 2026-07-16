# Factor Values v1 Artifact Contract

## Contract coverage

1. Artifact authority: immutable content, not mutable factor state.
2. Storage layout: one identity directory with three files.
3. Manifest: complete input/output lineage and hashes.
4. Identity: Instance plus Parquet bytes plus schema.
5. Snapshot lineage: exact authoritative Dataset Snapshot ID and keys.
6. Output schema: symbol, trade_date, nullable float64 factor_value.
7. Quality: coverage/cardinality/warm-up/errors/warnings.
8. Atomicity: sibling staging and atomic rename.
9. Exact existing: identical replay accepted, conflict rejected.
10. Validation: identity, hashes, schema, rows, unique/exact keys.
11. Consumer boundary: research artifact only.
12. Deferred IC/backtest: no performance or promotion claim.

Factor Values is a computation artifact, not a Factor definition, validation
result, Registry record or model feature. Its immutable identity is derived from
the Factor Instance ID, deterministic Parquet SHA-256 and declared output
schema.

The manifest records Template, Instance, Dataset Snapshot and engine lineage;
bound parameters; required research features; exact output schema and row
count; and Parquet/quality hashes. `quality.json` records finite/null coverage,
cardinality, date/symbol counts, warm-up and warnings. `values.parquet` contains
one sorted row per Snapshot `symbol,trade_date` key and a nullable float64
`factor_value`.

Publishing uses a sibling staging directory and atomic rename. A target with the
same content identity is immutable: exact replay is accepted, differing content
is rejected. Validation recomputes hashes and identity, reads the authoritative
Dataset Snapshot keys through `load_feature_matrix`, and rejects schema, row,
duplicate-key or lineage mismatch.

This artifact is research evidence only. It does not assert factor quality,
validation eligibility, production status, model value or backtest results.
