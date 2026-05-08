-- 016_semantic_layer.sql
-- 独立语义层正式建表迁移（包含快照治理审计表）
-- 目标：避免 semantic_* 表和 semantic_snapshot_audits 只依赖 GORM AutoMigrate

CREATE TABLE IF NOT EXISTS semantic_metrics (
    id SERIAL PRIMARY KEY,
    metric_code VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    business_summary TEXT,
    default_aggregation VARCHAR(32),
    default_time_grain VARCHAR(32),
    default_chart_type VARCHAR(32),
    recommended_dimension_codes JSONB DEFAULT '[]'::jsonb,
    preferred_followups JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    status SMALLINT DEFAULT 1,
    version INT DEFAULT 1,
    updated_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_metrics_metric_code ON semantic_metrics(metric_code);

CREATE TABLE IF NOT EXISTS semantic_dimensions (
    id SERIAL PRIMARY KEY,
    dimension_code VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    hierarchy_level INT DEFAULT 0,
    parent_dimension_code VARCHAR(64),
    supports_group_by BOOLEAN DEFAULT TRUE,
    supports_filter BOOLEAN DEFAULT TRUE,
    supports_drilldown BOOLEAN DEFAULT FALSE,
    drilldown_targets JSONB DEFAULT '[]'::jsonb,
    allowed_metric_codes JSONB DEFAULT '[]'::jsonb,
    default_sort_priority INT DEFAULT 0,
    tags JSONB DEFAULT '[]'::jsonb,
    status SMALLINT DEFAULT 1,
    version INT DEFAULT 1,
    updated_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_dimensions_dimension_code ON semantic_dimensions(dimension_code);

CREATE TABLE IF NOT EXISTS semantic_analysis_capabilities (
    id SERIAL PRIMARY KEY,
    subject_type VARCHAR(32) NOT NULL,
    subject_key VARCHAR(64) NOT NULL,
    supports_value BOOLEAN DEFAULT TRUE,
    supports_trend BOOLEAN DEFAULT FALSE,
    supports_comparison BOOLEAN DEFAULT FALSE,
    supports_yoy BOOLEAN DEFAULT FALSE,
    supports_mom BOOLEAN DEFAULT FALSE,
    supports_ranking BOOLEAN DEFAULT FALSE,
    supports_ratio BOOLEAN DEFAULT FALSE,
    supports_attribution BOOLEAN DEFAULT FALSE,
    supports_drilldown BOOLEAN DEFAULT FALSE,
    allowed_modes JSONB DEFAULT '[]'::jsonb,
    constraints_json JSONB DEFAULT '{}'::jsonb,
    status SMALLINT DEFAULT 1,
    version INT DEFAULT 1,
    updated_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_capability_subject
    ON semantic_analysis_capabilities(subject_type, subject_key);

CREATE TABLE IF NOT EXISTS semantic_interaction_policies (
    id SERIAL PRIMARY KEY,
    policy_key VARCHAR(64) NOT NULL,
    scene_type VARCHAR(32) NOT NULL,
    answer_mode VARCHAR(32),
    clarify_priority INT DEFAULT 0,
    max_suggestions INT DEFAULT 3,
    confidence_thresholds JSONB DEFAULT '{}'::jsonb,
    fallback_strategy VARCHAR(64),
    policy_json JSONB DEFAULT '{}'::jsonb,
    status SMALLINT DEFAULT 1,
    version INT DEFAULT 1,
    updated_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_policies_policy_key ON semantic_interaction_policies(policy_key);
CREATE INDEX IF NOT EXISTS idx_semantic_policies_scene_type ON semantic_interaction_policies(scene_type);

CREATE TABLE IF NOT EXISTS semantic_actions (
    id SERIAL PRIMARY KEY,
    action_code VARCHAR(64) NOT NULL,
    label VARCHAR(128) NOT NULL,
    source_scene_type VARCHAR(32),
    target_scene_type VARCHAR(32),
    source_constraints_json JSONB DEFAULT '{}'::jsonb,
    target_payload_template JSONB DEFAULT '{}'::jsonb,
    priority INT DEFAULT 0,
    status SMALLINT DEFAULT 1,
    version INT DEFAULT 1,
    updated_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_actions_action_code ON semantic_actions(action_code);
CREATE INDEX IF NOT EXISTS idx_semantic_actions_source_scene_type ON semantic_actions(source_scene_type);

CREATE TABLE IF NOT EXISTS semantic_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_id VARCHAR(64) NOT NULL,
    version VARCHAR(64) NOT NULL,
    compiled_at TIMESTAMP NOT NULL,
    compiled_by VARCHAR(64),
    payload JSONB,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    release_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_snapshots_snapshot_id ON semantic_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshots_version ON semantic_snapshots(version);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshots_status ON semantic_snapshots(status);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshots_compiled_at ON semantic_snapshots(compiled_at DESC);

CREATE TABLE IF NOT EXISTS semantic_snapshot_audits (
    id SERIAL PRIMARY KEY,
    snapshot_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    before_status VARCHAR(16),
    after_status VARCHAR(16),
    operator VARCHAR(64),
    note TEXT,
    detail_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_audits_snapshot_id ON semantic_snapshot_audits(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_audits_event_type ON semantic_snapshot_audits(event_type);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_audits_created_at ON semantic_snapshot_audits(created_at DESC);
