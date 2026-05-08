-- 初始化数据库表结构
-- PostgreSQL

-- 创建数据库（需要超级用户执行）
-- CREATE DATABASE dev_metric;

-- 指标定义表
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    seq_no INTEGER,
    metric_code VARCHAR(64) UNIQUE NOT NULL,
    domain VARCHAR(64),
    category_1 VARCHAR(64),
    category_2 VARCHAR(64),
    category_3 VARCHAR(64),
    name VARCHAR(128) NOT NULL,
    name_en VARCHAR(128),
    metric_type VARCHAR(32),
    business_definition TEXT,
    business_rule TEXT,
    applicable_scope VARCHAR(256),
    statistics_rule TEXT,
    unit VARCHAR(32),
    common_dimensions VARCHAR(256),
    org_level VARCHAR(64),
    frequency VARCHAR(32),
    technical_rule TEXT,
    data_format VARCHAR(32),
    precision VARCHAR(32),
    owner_dept VARCHAR(128),
    status VARCHAR(32) DEFAULT '在用',
    publish_date DATE,
    expire_date DATE,
    starrocks_sql TEXT,
    query_params JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 告警规则表
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES metrics(id),
    name VARCHAR(128) NOT NULL,
    condition_type VARCHAR(32) NOT NULL,
    threshold_value DECIMAL(20,4) NOT NULL,
    duration INTEGER DEFAULT 0,
    dingtalk_webhook VARCHAR(512),
    dingtalk_secret VARCHAR(128),
    notify_status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 告警记录表
CREATE TABLE IF NOT EXISTS alert_records (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES alert_rules(id),
    metric_id INTEGER REFERENCES metrics(id),
    trigger_value DECIMAL(20,4),
    threshold_value DECIMAL(20,4),
    status SMALLINT DEFAULT 0,
    message TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    resolved_at TIMESTAMP
);

-- LLM 配置表
CREATE TABLE IF NOT EXISTS llm_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    provider VARCHAR(32) NOT NULL,
    api_url VARCHAR(512) NOT NULL,
    api_key VARCHAR(256) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    is_default SMALLINT DEFAULT 0,
    extra_config JSONB,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 维度表
CREATE TABLE IF NOT EXISTS dimensions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    values JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 业务术语映射表
CREATE TABLE IF NOT EXISTS business_terms (
    id SERIAL PRIMARY KEY,
    term VARCHAR(128) UNIQUE NOT NULL,
    metric_ids INTEGER[],
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 指标-维度关联表
CREATE TABLE IF NOT EXISTS metric_dimensions (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES metrics(id),
    dimension_id INTEGER REFERENCES dimensions(id)
);

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    dept VARCHAR(128),
    dept_id INTEGER,
    role VARCHAR(32) DEFAULT 'user',
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Token 黑名单表
CREATE TABLE IF NOT EXISTS refresh_token_blacklist (
    id SERIAL PRIMARY KEY,
    token_jti VARCHAR(64) UNIQUE NOT NULL,
    revoked_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL
);

-- SQL 审计日志表
CREATE TABLE IF NOT EXISTS sql_audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    sql_text TEXT NOT NULL,
    metric_id INTEGER,
    execute_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status SMALLINT,
    error_msg TEXT,
    ip_address VARCHAR(45)
);

-- StarRocks 数据源配置表
CREATE TABLE IF NOT EXISTS starrocks_tables (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER REFERENCES metrics(id),
    source_table VARCHAR(128),
    source_sql TEXT,
    sync_config JSONB,
    last_sync_time TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_metrics_domain ON metrics(domain);
CREATE INDEX IF NOT EXISTS idx_metrics_status ON metrics(status);
CREATE INDEX IF NOT EXISTS idx_alert_rules_metric_id ON alert_rules(metric_id);
CREATE INDEX IF NOT EXISTS idx_alert_records_rule_id ON alert_records(rule_id);
CREATE INDEX IF NOT EXISTS idx_sql_audit_logs_user_id ON sql_audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_sql_audit_logs_execute_time ON sql_audit_logs(execute_time);

-- 插入默认管理员用户 (密码: admin123)
INSERT INTO users (username, password_hash, dept, dept_id, role, status)
VALUES ('admin', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZRGdjGj/n3.rsJ7/8tEyN8v5z2V0y', '技术部', 1, 'admin', 1)
ON CONFLICT (username) DO NOTHING;

-- 插入默认 LLM 配置
INSERT INTO llm_configs (name, provider, api_url, api_key, model_name, is_default, status)
VALUES ('腾讯云 DeepSeek', 'tencent', 'https://api.tencent.com', '', 'deepseek-3.2', 1, 1)
ON CONFLICT DO NOTHING;
