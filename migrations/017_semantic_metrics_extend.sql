-- 017_semantic_metrics_extend.sql
-- 为 semantic_metrics 表增加 CTE 渲染所需字段
-- 用于三层 CTE SQL 生成引擎

ALTER TABLE semantic_metrics
    ADD COLUMN IF NOT EXISTS agg_expression VARCHAR(500),
    ADD COLUMN IF NOT EXISTS metric_type VARCHAR(20) DEFAULT 'atomic',
    ADD COLUMN IF NOT EXISTS calculated_config JSONB DEFAULT '{}'::jsonb;
