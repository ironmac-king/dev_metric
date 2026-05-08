-- 优化建议表 - 存储基于负反馈生成的规则优化建议
-- PostgreSQL

CREATE TABLE IF NOT EXISTS optimization_suggestions (
    id SERIAL PRIMARY KEY,
    suggestion_type VARCHAR(32) NOT NULL,      -- add_intent_pattern, modify_pattern, add_synonym
    target_table VARCHAR(32) NOT NULL,        -- intent_templates, business_terms 等
    target_id INTEGER,                        -- 关联目标ID
    original_value TEXT,                      -- 原值
    suggested_value TEXT NOT NULL,           -- 建议值
    fail_count INTEGER DEFAULT 0,            -- 导致失败的次数
    confidence DECIMAL(3,2) DEFAULT 0.5,    -- 置信度 0.00-1.00
    status VARCHAR(16) DEFAULT 'pending',    -- pending/applied/ignored
    reason TEXT,                             -- 生成建议的原因
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP,
    applied_by VARCHAR(64)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_suggestion_status ON optimization_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestion_type ON optimization_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_suggestion_created ON optimization_suggestions(created_at);
