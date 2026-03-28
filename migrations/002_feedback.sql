-- 反馈驱动优化系统表
-- PostgreSQL

-- 追问反馈表（增强版）
CREATE TABLE IF NOT EXISTS clarification_feedback (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    turn_index INTEGER NOT NULL,
    feedback_source VARCHAR(32) NOT NULL DEFAULT 'user',
    fail_reason VARCHAR(64),
    context_snapshot JSONB,
    raw_llm_output TEXT,
    clarification_type VARCHAR(32),
    clarification_question TEXT,
    user_response TEXT,
    feedback SMALLINT DEFAULT 0,
    missing_fields JSONB,
    metric_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_feedback_session ON clarification_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_source ON clarification_feedback(feedback_source);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON clarification_feedback(clarification_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON clarification_feedback(created_at);

-- 追问模板表（版本管理）
CREATE TABLE IF NOT EXISTS clarification_templates (
    id SERIAL PRIMARY KEY,
    clarification_type VARCHAR(32) NOT NULL,
    template_version INTEGER NOT NULL DEFAULT 1,
    template_content TEXT NOT NULL,
    variables JSONB,
    test_cases JSONB,
    quality_metrics JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    UNIQUE(clarification_type, template_version)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_template_type ON clarification_templates(clarification_type);
CREATE INDEX IF NOT EXISTS idx_template_active ON clarification_templates(is_active);

-- 插入默认追问模板
INSERT INTO clarification_templates (clarification_type, template_version, template_content, variables, is_active, description) VALUES
('metric_missing', 1,
'你是一个 BI 查询助手 的对话策略专家。请严格按以下规则输出 JSON。

## 追问类型枚举（必须使用以下之一）
- metric_missing: 指标缺失（用户没说具体指标）
- time_range_missing: 时间范围缺失（没说昨天/本周/本月等）
- dimension_missing: 维度缺失（没说按地区/部门/产品分组）
- filter_condition_missing: 过滤条件缺失（没说只看某类订单/某个产品）
- action_intent_ambiguous: 操作意图模糊（不确定要查、改、还是导出）
- term_ambiguous: 术语歧义（同一个词有多个含义）
- scope_too_broad: 范围太宽（问题太泛化）
- high_risk_operation: 高风险操作（涉及删除、覆盖等）
- permission_required: 权限不足
- costly_query_warning: 高成本查询预警
- default_value_confirmation: 默认值确认（系统假设了默认值需用户确认）
- implicit_need_discovery: 隐含需求挖掘（用户可能需要但没说）

## 规则
1. 如果用户意图明确且所有必要信息已提供，返回 needs_clarification: false。
2. 如果缺少关键信息，返回 needs_clarification: true，并提出一个**具体、简洁、一次只问一个问题**的追问。
3. 追问时必须指定 clarification_type（使用上述枚举之一）。
4. 优先追问最重要的缺失字段。

## 当前状态
- 已识别指标: {metric_name}
- 已识别时间范围: {time_range}
- 已识别维度: {dimension}
- 缺少信息: {missing_fields}
- 已追问过的字段: {asked_fields}

## 对话历史
{history_summary}

## 已知默认值
- time_range 默认值: last_7_days（最近7天）
- dimension 默认值: all（不分维度）

## 输出格式（必须是合法 JSON，无其他内容）
{{"needs_clarification": true/false, "clarification_type": "追问类型枚举", "question": "追问内容（如果需要）", "reason": "原因", "missing_fields": [], "suggested_defaults": {{"字段名": "默认值"}}}}

请输出JSON：',
'["metric_name", "time_range", "dimension", "missing_fields", "asked_fields", "history_summary"]',
true,
'指标缺失追问模板 v1'),

('time_range_missing', 1,
'你是一个 BI 查询助手 的对话策略专家。请严格按以下规则输出 JSON。

用户问题：{question}
当前指标：{metric_name}
时间范围：{time_range}

## 规则
1. 如果用户意图明确且所有必要信息已提供，返回 needs_clarification: false。
2. 如果缺少关键信息，返回 needs_clarification: true，并提出一个**具体、简洁、一次只问一个问题**的追问。
3. 优先使用自然语言追问，不要列举选项。

## 输出格式（必须是合法 JSON，无其他内容）
{{"needs_clarification": true/false, "clarification_type": "time_range_missing", "question": "追问内容", "reason": "原因", "suggested_defaults": {{"time_range": "last_7_days"}}}

请输出JSON：',
'["question", "metric_name", "time_range"]',
true,
'时间范围缺失追问模板 v1'),

('no_data', 1,
'你是一个 BI 查询助手 的对话策略专家。请分析查询结果为空的原因并提供建议。

## 当前状态
- 指标: {metric_name}
- 时间范围: {time_range}
- SQL: {sql}
- 结果: {result}

## 可能原因
1. 指标在该时间段内确实没有数据
2. 时间范围设置错误
3. 数据同步延迟
4. 查询条件过于严格

## 输出格式（必须是合法 JSON，无其他内容）
{{"needs_clarification": true, "clarification_type": "no_data", "question": "追问内容", "reason": "原因", "suggested_alternatives": ["建议1", "建议2"]}}

请输出JSON：',
'["metric_name", "time_range", "sql", "result"]',
true,
'无数据反馈追问模板 v1');
