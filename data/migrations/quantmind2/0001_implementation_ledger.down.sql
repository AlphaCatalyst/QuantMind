-- QuantMind 2.0 Implementation Ledger, version 0001 rollback.
-- Transaction ownership, latest-version checks, checksum checks, and the
-- explicit destructive-operation gate belong to the migration runner.
DROP TABLE quantmind2.implementation_recommended_tasks;
DROP TABLE quantmind2.implementation_limitations;
DROP TABLE quantmind2.implementation_adr_references;
DROP TABLE quantmind2.implementation_component_references;
DROP TABLE quantmind2.implementation_artifacts;
DROP TABLE quantmind2.implementation_test_executions;
DROP TABLE quantmind2.implementation_changed_symbols;
DROP TABLE quantmind2.implementation_changed_files;
DROP TABLE quantmind2.implementation_run_relationships;
DROP TABLE quantmind2.implementation_runs;
DROP TABLE quantmind2.implementation_tasks;

DELETE FROM quantmind2._schema_migrations WHERE version = '0001';

DO $qm2$
BEGIN
    IF EXISTS (SELECT 1 FROM quantmind2._schema_migrations) THEN
        RAISE EXCEPTION 'cannot remove migration infrastructure while versions remain';
    END IF;
END
$qm2$;

DROP TABLE quantmind2._schema_migrations;
DROP SCHEMA quantmind2;
