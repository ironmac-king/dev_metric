-- 移除 semantic_metrics 表的 calculated_config 列（该字段未实际使用）
ALTER TABLE semantic_metrics DROP COLUMN IF EXISTS calculated_config;
