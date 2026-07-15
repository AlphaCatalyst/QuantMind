-- QuantMind 2.0 Implementation Ledger, version 0001.
-- Transaction ownership and history insertion belong to the migration runner.
CREATE SCHEMA IF NOT EXISTS quantmind2;

CREATE TABLE IF NOT EXISTS quantmind2._schema_migrations (
    version VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    up_checksum CHAR(64) NOT NULL,
    down_checksum CHAR(64) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    runner_version VARCHAR(32) NOT NULL,
    CONSTRAINT pk_qm2_schema_migrations PRIMARY KEY (version),
    CONSTRAINT ck_qm2_schema_migrations_version_nonempty CHECK (btrim(version) <> ''),
    CONSTRAINT ck_qm2_schema_migrations_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_qm2_schema_migrations_up_checksum CHECK (up_checksum ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_schema_migrations_down_checksum CHECK (down_checksum ~ '^[0-9A-Fa-f]{64}$')
);

CREATE TABLE quantmind2.implementation_tasks (
    task_id VARCHAR(255) NOT NULL,
    parent_task_id VARCHAR(255),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    scope JSONB NOT NULL,
    explicit_non_goals JSONB NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_qm2_tasks PRIMARY KEY (task_id),
    CONSTRAINT ck_qm2_tasks_status CHECK (status IN ('planned', 'ready', 'running', 'completed', 'partial', 'blocked', 'cancelled')),
    CONSTRAINT ck_qm2_tasks_parent_differs CHECK (parent_task_id IS NULL OR parent_task_id <> task_id),
    CONSTRAINT ck_qm2_tasks_version_positive CHECK (version >= 1),
    CONSTRAINT ck_qm2_tasks_title_nonempty CHECK (btrim(title) <> ''),
    CONSTRAINT ck_qm2_tasks_objective_nonempty CHECK (btrim(objective) <> ''),
    CONSTRAINT ck_qm2_tasks_scope_array CHECK (jsonb_typeof(scope) = 'array'),
    CONSTRAINT ck_qm2_tasks_non_goals_array CHECK (jsonb_typeof(explicit_non_goals) = 'array'),
    CONSTRAINT fk_qm2_tasks_parent FOREIGN KEY (parent_task_id) REFERENCES quantmind2.implementation_tasks (task_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_tasks_created ON quantmind2.implementation_tasks (created_at);
CREATE INDEX ix_qm2_tasks_parent ON quantmind2.implementation_tasks (parent_task_id);
CREATE INDEX ix_qm2_tasks_status ON quantmind2.implementation_tasks (status);

CREATE TABLE quantmind2.implementation_runs (
    implementation_run_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    repository_root VARCHAR(255) NOT NULL,
    branch VARCHAR(255) NOT NULL,
    base_commit CHAR(40) NOT NULL,
    result_commit CHAR(40),
    task_status VARCHAR(32) NOT NULL,
    completion_level VARCHAR(32) NOT NULL,
    verification_level VARCHAR(32) NOT NULL,
    workspace_dirty_before BOOLEAN NOT NULL,
    workspace_dirty_after BOOLEAN NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    agent_type VARCHAR(255) NOT NULL,
    manifest_schema_version VARCHAR(255) NOT NULL,
    manifest_path TEXT NOT NULL,
    manifest_hash CHAR(64),
    report_path TEXT NOT NULL,
    report_hash CHAR(64),
    source_bundle_hash CHAR(64),
    git_diff_hash CHAR(64),
    consistency_status VARCHAR(32) NOT NULL,
    canonical_status VARCHAR(32) NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    CONSTRAINT pk_qm2_runs PRIMARY KEY (implementation_run_id),
    CONSTRAINT ck_qm2_runs_status CHECK (task_status IN ('running', 'completed_uncommitted', 'partial_uncommitted', 'completed_committed', 'partial_committed', 'failed', 'blocked', 'cancelled')),
    CONSTRAINT ck_qm2_runs_completion CHECK (completion_level IN ('none', 'partial', 'complete')),
    CONSTRAINT ck_qm2_runs_verification CHECK (verification_level IN ('not_verified', 'static_checks', 'targeted_tests', 'integration_tests', 'full_relevant_tests')),
    CONSTRAINT ck_qm2_runs_consistency CHECK (consistency_status IN ('unverified', 'consistent', 'warning', 'error', 'stale')),
    CONSTRAINT ck_qm2_runs_canonical_status CHECK (canonical_status IN ('noncanonical', 'candidate', 'canonical', 'rejected')),
    CONSTRAINT ck_qm2_runs_version_positive CHECK (version >= 1),
    CONSTRAINT ck_qm2_runs_base_commit_format CHECK (base_commit ~ '^[0-9A-Fa-f]{40}$'),
    CONSTRAINT ck_qm2_runs_result_commit_format CHECK (result_commit IS NULL OR result_commit ~ '^[0-9A-Fa-f]{40}$'),
    CONSTRAINT ck_qm2_runs_manifest_hash_format CHECK (manifest_hash IS NULL OR manifest_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_runs_report_hash_format CHECK (report_hash IS NULL OR report_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_runs_source_hash_format CHECK (source_bundle_hash IS NULL OR source_bundle_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_runs_diff_hash_format CHECK (git_diff_hash IS NULL OR git_diff_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_runs_time_order CHECK (completed_at IS NULL OR completed_at >= started_at),
    CONSTRAINT ck_qm2_runs_terminal_time CHECK ((task_status = 'running' AND completed_at IS NULL) OR (task_status <> 'running' AND completed_at IS NOT NULL)),
    CONSTRAINT ck_qm2_runs_committed_result CHECK (task_status NOT IN ('completed_committed', 'partial_committed') OR result_commit IS NOT NULL),
    CONSTRAINT ck_qm2_runs_uncommitted_result CHECK (task_status NOT IN ('completed_uncommitted', 'partial_uncommitted') OR result_commit IS NULL),
    CONSTRAINT ck_qm2_runs_completed_level CHECK (task_status NOT IN ('completed_committed', 'completed_uncommitted') OR completion_level = 'complete'),
    CONSTRAINT ck_qm2_runs_partial_level CHECK (task_status NOT IN ('partial_committed', 'partial_uncommitted') OR completion_level = 'partial'),
    CONSTRAINT ck_qm2_runs_canonical_gate CHECK (canonical_status <> 'canonical' OR (task_status = 'completed_committed' AND completion_level = 'complete' AND consistency_status = 'consistent' AND result_commit IS NOT NULL)),
    CONSTRAINT ck_qm2_runs_failure_noncanonical CHECK (task_status NOT IN ('failed', 'blocked', 'cancelled') OR canonical_status <> 'canonical'),
    CONSTRAINT fk_qm2_runs_task FOREIGN KEY (task_id) REFERENCES quantmind2.implementation_tasks (task_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_runs_canonical ON quantmind2.implementation_runs (canonical_status);
CREATE INDEX ix_qm2_runs_consistency ON quantmind2.implementation_runs (consistency_status);
CREATE INDEX ix_qm2_runs_result_commit ON quantmind2.implementation_runs (result_commit);
CREATE INDEX ix_qm2_runs_started ON quantmind2.implementation_runs (started_at);
CREATE INDEX ix_qm2_runs_status ON quantmind2.implementation_runs (task_status);
CREATE INDEX ix_qm2_runs_task ON quantmind2.implementation_runs (task_id);
CREATE INDEX ix_qm2_runs_task_started ON quantmind2.implementation_runs (task_id, started_at);

CREATE TABLE quantmind2.implementation_run_relationships (
    relationship_id VARCHAR(255) NOT NULL,
    source_run_id VARCHAR(255) NOT NULL,
    target_run_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(32) NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_qm2_rels PRIMARY KEY (relationship_id),
    CONSTRAINT uq_qm2_rels_source_target_type UNIQUE (source_run_id, target_run_id, relationship_type),
    CONSTRAINT ck_qm2_rels_distinct_runs CHECK (source_run_id <> target_run_id),
    CONSTRAINT ck_qm2_rels_type CHECK (relationship_type IN ('finalizes', 'corrects', 'supersedes', 'depends_on', 'retries', 'continues')),
    CONSTRAINT ck_qm2_rels_reason_nonempty CHECK (btrim(reason) <> ''),
    CONSTRAINT fk_qm2_rels_source_run FOREIGN KEY (source_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT,
    CONSTRAINT fk_qm2_rels_target_run FOREIGN KEY (target_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_rels_source ON quantmind2.implementation_run_relationships (source_run_id);
CREATE INDEX ix_qm2_rels_source_type ON quantmind2.implementation_run_relationships (source_run_id, relationship_type);
CREATE INDEX ix_qm2_rels_target ON quantmind2.implementation_run_relationships (target_run_id);
CREATE INDEX ix_qm2_rels_target_type ON quantmind2.implementation_run_relationships (target_run_id, relationship_type);
CREATE INDEX ix_qm2_rels_type ON quantmind2.implementation_run_relationships (relationship_type);

CREATE TABLE quantmind2.implementation_changed_files (
    changed_file_id VARCHAR(255) NOT NULL,
    implementation_run_id VARCHAR(255) NOT NULL,
    path TEXT NOT NULL,
    change_type VARCHAR(32) NOT NULL,
    before_hash CHAR(64),
    after_hash CHAR(64),
    previous_path TEXT,
    CONSTRAINT pk_qm2_files PRIMARY KEY (changed_file_id),
    CONSTRAINT uq_qm2_files_run_path_type UNIQUE (implementation_run_id, path, change_type),
    CONSTRAINT ck_qm2_files_path_nonempty CHECK (btrim(path) <> ''),
    CONSTRAINT ck_qm2_files_change_type CHECK (change_type IN ('added', 'modified', 'deleted', 'renamed', 'unchanged')),
    CONSTRAINT ck_qm2_files_before_hash CHECK (before_hash IS NULL OR before_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_files_after_hash CHECK (after_hash IS NULL OR after_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_files_added_shape CHECK (change_type <> 'added' OR (before_hash IS NULL AND after_hash IS NOT NULL AND previous_path IS NULL)),
    CONSTRAINT ck_qm2_files_deleted_shape CHECK (change_type <> 'deleted' OR (before_hash IS NOT NULL AND after_hash IS NULL AND previous_path IS NULL)),
    CONSTRAINT ck_qm2_files_modified_shape CHECK (change_type <> 'modified' OR (before_hash IS NOT NULL AND after_hash IS NOT NULL AND before_hash <> after_hash AND previous_path IS NULL)),
    CONSTRAINT ck_qm2_files_renamed_shape CHECK (change_type <> 'renamed' OR (previous_path IS NOT NULL AND btrim(previous_path) <> '' AND previous_path <> path)),
    CONSTRAINT ck_qm2_files_unchanged_shape CHECK (change_type <> 'unchanged' OR (before_hash IS NOT NULL AND after_hash IS NOT NULL AND before_hash = after_hash AND previous_path IS NULL)),
    CONSTRAINT ck_qm2_files_previous_path_scope CHECK (change_type = 'renamed' OR previous_path IS NULL),
    CONSTRAINT fk_qm2_files_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_files_change_type ON quantmind2.implementation_changed_files (change_type);
CREATE INDEX ix_qm2_files_path ON quantmind2.implementation_changed_files (path);
CREATE INDEX ix_qm2_files_previous_path ON quantmind2.implementation_changed_files (previous_path);
CREATE INDEX ix_qm2_files_run ON quantmind2.implementation_changed_files (implementation_run_id);
CREATE INDEX ix_qm2_files_run_path ON quantmind2.implementation_changed_files (implementation_run_id, path);

CREATE TABLE quantmind2.implementation_changed_symbols (
    changed_symbol_id VARCHAR(255) NOT NULL,
    implementation_run_id VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    qualified_name VARCHAR(512) NOT NULL,
    symbol_type VARCHAR(32) NOT NULL,
    change_type VARCHAR(32) NOT NULL,
    CONSTRAINT pk_qm2_symbols PRIMARY KEY (changed_symbol_id),
    CONSTRAINT uq_qm2_symbols_run_file_name UNIQUE (implementation_run_id, file_path, qualified_name),
    CONSTRAINT ck_qm2_symbols_file_nonempty CHECK (btrim(file_path) <> ''),
    CONSTRAINT ck_qm2_symbols_name_nonempty CHECK (btrim(qualified_name) <> ''),
    CONSTRAINT ck_qm2_symbols_symbol_type CHECK (symbol_type IN ('module', 'class', 'function', 'method', 'constant', 'schema', 'table', 'endpoint', 'document', 'unknown')),
    CONSTRAINT ck_qm2_symbols_change_type CHECK (change_type IN ('added', 'modified', 'deleted', 'renamed')),
    CONSTRAINT fk_qm2_symbols_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_symbols_file ON quantmind2.implementation_changed_symbols (file_path);
CREATE INDEX ix_qm2_symbols_name ON quantmind2.implementation_changed_symbols (qualified_name);
CREATE INDEX ix_qm2_symbols_run ON quantmind2.implementation_changed_symbols (implementation_run_id);
CREATE INDEX ix_qm2_symbols_run_file ON quantmind2.implementation_changed_symbols (implementation_run_id, file_path);
CREATE INDEX ix_qm2_symbols_symbol_type ON quantmind2.implementation_changed_symbols (symbol_type);

CREATE TABLE quantmind2.implementation_test_executions (
    test_execution_id VARCHAR(255) NOT NULL,
    implementation_run_id VARCHAR(255) NOT NULL,
    command TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    skipped_count INTEGER NOT NULL,
    not_run_reason TEXT,
    artifact_uri TEXT,
    artifact_hash CHAR(64),
    CONSTRAINT pk_qm2_tests PRIMARY KEY (test_execution_id),
    CONSTRAINT uq_qm2_tests_run_id UNIQUE (implementation_run_id, test_execution_id),
    CONSTRAINT ck_qm2_tests_command_nonempty CHECK (btrim(command) <> ''),
    CONSTRAINT ck_qm2_tests_purpose_nonempty CHECK (btrim(purpose) <> ''),
    CONSTRAINT ck_qm2_tests_status CHECK (status IN ('passed', 'failed', 'skipped', 'not_run')),
    CONSTRAINT ck_qm2_tests_counts_nonnegative CHECK (passed_count >= 0 AND failed_count >= 0 AND skipped_count >= 0),
    CONSTRAINT ck_qm2_tests_passed_shape CHECK (status <> 'passed' OR failed_count = 0),
    CONSTRAINT ck_qm2_tests_failed_shape CHECK (status <> 'failed' OR failed_count > 0),
    CONSTRAINT ck_qm2_tests_not_run_shape CHECK ((status = 'not_run' AND not_run_reason IS NOT NULL AND btrim(not_run_reason) <> '') OR (status <> 'not_run' AND not_run_reason IS NULL)),
    CONSTRAINT ck_qm2_tests_artifact_hash CHECK (artifact_hash IS NULL OR artifact_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT fk_qm2_tests_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_tests_run ON quantmind2.implementation_test_executions (implementation_run_id);
CREATE INDEX ix_qm2_tests_run_status ON quantmind2.implementation_test_executions (implementation_run_id, status);
CREATE INDEX ix_qm2_tests_status ON quantmind2.implementation_test_executions (status);

CREATE TABLE quantmind2.implementation_artifacts (
    artifact_id VARCHAR(255) NOT NULL,
    implementation_run_id VARCHAR(255) NOT NULL,
    artifact_type VARCHAR(255) NOT NULL,
    path_or_uri TEXT NOT NULL,
    content_hash CHAR(64),
    schema_version VARCHAR(255),
    size_bytes BIGINT,
    CONSTRAINT pk_qm2_artifacts PRIMARY KEY (artifact_id),
    CONSTRAINT uq_qm2_artifacts_run_id UNIQUE (implementation_run_id, artifact_id),
    CONSTRAINT ck_qm2_artifacts_type_nonempty CHECK (btrim(artifact_type) <> ''),
    CONSTRAINT ck_qm2_artifacts_location_nonempty CHECK (btrim(path_or_uri) <> ''),
    CONSTRAINT ck_qm2_artifacts_content_hash CHECK (content_hash IS NULL OR content_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_qm2_artifacts_size_nonnegative CHECK (size_bytes IS NULL OR size_bytes >= 0),
    CONSTRAINT fk_qm2_artifacts_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_artifacts_content_hash ON quantmind2.implementation_artifacts (content_hash);
CREATE INDEX ix_qm2_artifacts_run ON quantmind2.implementation_artifacts (implementation_run_id);
CREATE INDEX ix_qm2_artifacts_run_type ON quantmind2.implementation_artifacts (implementation_run_id, artifact_type);
CREATE INDEX ix_qm2_artifacts_type ON quantmind2.implementation_artifacts (artifact_type);

CREATE TABLE quantmind2.implementation_component_references (
    implementation_run_id VARCHAR(255) NOT NULL,
    component_id VARCHAR(255) NOT NULL,
    impact_type VARCHAR(32) NOT NULL,
    CONSTRAINT pk_qm2_component_refs PRIMARY KEY (implementation_run_id, component_id),
    CONSTRAINT ck_qm2_component_refs_id_nonempty CHECK (btrim(component_id) <> ''),
    CONSTRAINT ck_qm2_component_refs_impact_type CHECK (impact_type IN ('introduced', 'modified', 'deprecated', 'removed', 'verified', 'documented', 'unaffected')),
    CONSTRAINT fk_qm2_component_refs_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_component_refs_component ON quantmind2.implementation_component_references (component_id);
CREATE INDEX ix_qm2_component_refs_component_impact ON quantmind2.implementation_component_references (component_id, impact_type);
CREATE INDEX ix_qm2_component_refs_impact ON quantmind2.implementation_component_references (impact_type);

CREATE TABLE quantmind2.implementation_adr_references (
    implementation_run_id VARCHAR(255) NOT NULL,
    adr_id VARCHAR(32) NOT NULL,
    relation VARCHAR(32) NOT NULL,
    CONSTRAINT pk_qm2_adr_refs PRIMARY KEY (implementation_run_id, adr_id),
    CONSTRAINT ck_qm2_adr_refs_id_format CHECK (adr_id ~ '^ADR-[0-9]{4}$'),
    CONSTRAINT ck_qm2_adr_refs_relation CHECK (relation IN ('implements', 'conforms_to', 'documents', 'supersedes', 'affected_by')),
    CONSTRAINT fk_qm2_adr_refs_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_adr_refs_adr ON quantmind2.implementation_adr_references (adr_id);
CREATE INDEX ix_qm2_adr_refs_adr_relation ON quantmind2.implementation_adr_references (adr_id, relation);
CREATE INDEX ix_qm2_adr_refs_relation ON quantmind2.implementation_adr_references (relation);

CREATE TABLE quantmind2.implementation_limitations (
    limitation_id VARCHAR(255) NOT NULL,
    implementation_run_id VARCHAR(255) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    component_id VARCHAR(255),
    description TEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    CONSTRAINT pk_qm2_limitations PRIMARY KEY (limitation_id),
    CONSTRAINT uq_qm2_limitations_run_id UNIQUE (implementation_run_id, limitation_id),
    CONSTRAINT ck_qm2_limitations_severity CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    CONSTRAINT ck_qm2_limitations_component_nonempty CHECK (component_id IS NULL OR btrim(component_id) <> ''),
    CONSTRAINT ck_qm2_limitations_description_nonempty CHECK (btrim(description) <> ''),
    CONSTRAINT ck_qm2_limitations_status CHECK (status IN ('open', 'accepted', 'resolved', 'superseded')),
    CONSTRAINT fk_qm2_limitations_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_limitations_component ON quantmind2.implementation_limitations (component_id);
CREATE INDEX ix_qm2_limitations_component_status ON quantmind2.implementation_limitations (component_id, status);
CREATE INDEX ix_qm2_limitations_run ON quantmind2.implementation_limitations (implementation_run_id);
CREATE INDEX ix_qm2_limitations_run_status ON quantmind2.implementation_limitations (implementation_run_id, status);
CREATE INDEX ix_qm2_limitations_severity ON quantmind2.implementation_limitations (severity);
CREATE INDEX ix_qm2_limitations_status ON quantmind2.implementation_limitations (status);

CREATE TABLE quantmind2.implementation_recommended_tasks (
    recommendation_id VARCHAR(255) NOT NULL,
    implementation_run_id VARCHAR(255) NOT NULL,
    next_task_id VARCHAR(255) NOT NULL,
    priority VARCHAR(16) NOT NULL,
    reason TEXT NOT NULL,
    CONSTRAINT pk_qm2_recommendations PRIMARY KEY (recommendation_id),
    CONSTRAINT uq_qm2_recommendations_run_id UNIQUE (implementation_run_id, recommendation_id),
    CONSTRAINT ck_qm2_recommendations_task_nonempty CHECK (btrim(next_task_id) <> ''),
    CONSTRAINT ck_qm2_recommendations_priority CHECK (priority IN ('P0', 'P1', 'P2')),
    CONSTRAINT ck_qm2_recommendations_reason_nonempty CHECK (btrim(reason) <> ''),
    CONSTRAINT fk_qm2_recommendations_run FOREIGN KEY (implementation_run_id) REFERENCES quantmind2.implementation_runs (implementation_run_id) ON DELETE RESTRICT
);
CREATE INDEX ix_qm2_recommendations_priority ON quantmind2.implementation_recommended_tasks (priority);
CREATE INDEX ix_qm2_recommendations_run ON quantmind2.implementation_recommended_tasks (implementation_run_id);
CREATE INDEX ix_qm2_recommendations_run_priority ON quantmind2.implementation_recommended_tasks (implementation_run_id, priority);
CREATE INDEX ix_qm2_recommendations_task ON quantmind2.implementation_recommended_tasks (next_task_id);
CREATE INDEX ix_qm2_recommendations_task_priority ON quantmind2.implementation_recommended_tasks (next_task_id, priority);
