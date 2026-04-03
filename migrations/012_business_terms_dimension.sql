-- migrations/012_business_terms_dimension.sql
-- 扩展 business_terms 表支持维度值别名

-- 添加维度字段
ALTER TABLE business_terms ADD COLUMN IF NOT EXISTS dimension_field VARCHAR(64);
ALTER TABLE business_terms ADD COLUMN IF NOT EXISTS dimension_value VARCHAR(256);

-- 创建索引加速查询
CREATE INDEX IF NOT EXISTS idx_business_terms_dimension ON business_terms(dimension_field, dimension_value);

-- 示例数据：有线网卡的别名映射
INSERT INTO business_terms (term, dimension_field, dimension_value, description)
VALUES ('有线网', 'GROUP_3', '有线网卡', '有线网卡简称')
ON CONFLICT (term) DO UPDATE SET
    dimension_field = EXCLUDED.dimension_field,
    dimension_value = EXCLUDED.dimension_value;
