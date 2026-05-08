-- 反馈系统增强字段
-- PostgreSQL

-- clarification_feedback 表新增字段
ALTER TABLE clarification_feedback ADD COLUMN IF NOT EXISTS user_actions JSONB;
ALTER TABLE clarification_feedback ADD COLUMN IF NOT EXISTS intent_confidence DECIMAL(3,2);
ALTER TABLE clarification_feedback ADD COLUMN IF NOT EXISTS response_time_ms INTEGER;

-- 添加注释
COMMENT ON COLUMN clarification_feedback.user_actions IS '用户行为日志（如追问后修改问题、点击按钮等）';
COMMENT ON COLUMN clarification_feedback.intent_confidence IS '意图识别置信度';
COMMENT ON COLUMN clarification_feedback.response_time_ms IS '响应耗时（毫秒）';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_feedback_created ON clarification_feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_fail_reason ON clarification_feedback(fail_reason);
CREATE INDEX IF NOT EXISTS idx_feedback_session_created ON clarification_feedback(session_id, created_at);
