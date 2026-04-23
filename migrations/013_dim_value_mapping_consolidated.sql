-- migrations/013_dim_value_mapping_consolidated.sql
-- 合并 dimension_configs + dimension_type_mappings 到统一的 dim_value_mapping 表
-- 目标：一张表包含 column_name + dimension_type + dimension_value

-- Step 1: 创建新的 dim_value_mapping 表（PostgreSQL）
CREATE TABLE IF NOT EXISTS dim_value_mapping_new (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(128) NOT NULL DEFAULT 'ids.IDS_AMZ_COMPREHENSIVE_DI',
    column_name VARCHAR(64) NOT NULL,
    dimension_type VARCHAR(64),
    dimension_value VARCHAR(256) NOT NULL DEFAULT '',
    frequency BIGINT DEFAULT 0,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, column_name, dimension_value)
);

CREATE INDEX IF NOT EXISTS idx_dvm_column ON dim_value_mapping_new(column_name);
CREATE INDEX IF NOT EXISTS idx_dvm_type ON dim_value_mapping_new(dimension_type);
CREATE INDEX IF NOT EXISTS idx_dvm_table ON dim_value_mapping_new(table_name);

-- Step 2: 从 dimension_type_mappings 迁移基础维度类型配置
-- 每个 dimension_type → column_name 映射生成一行，dimension_value 为空
INSERT INTO dim_value_mapping_new (table_name, column_name, dimension_type, dimension_value, status)
SELECT
    'ids.IDS_AMZ_COMPREHENSIVE_DI' AS table_name,
    dtm.column_name,
    dtm.dimension_type,
    '' AS dimension_value,
    dtm.status
FROM dimension_type_mappings dtm
WHERE dtm.status = 1
ON CONFLICT (table_name, column_name, dimension_value) DO NOTHING;

-- Step 3: 从 dimension_configs 迁移维度值数据（如果有）
-- dimension_values 字段是 JSON 数组字符串，需要解析
-- 但目前所有 dimension_configs 的 dimension_values 都是 '[]'（空），
-- 所以这步实际不会插入任何数据，但保留此逻辑以备后续
INSERT INTO dim_value_mapping_new (table_name, column_name, dimension_type, dimension_value, status)
SELECT
    dc.starrocks_table AS table_name,
    dc.column_name,
    dc.dimension_name AS dimension_type,
    -- 尝试从 JSON 数组中提取每个 value
    COALESCE(value->>'value', value->>'dimension_value', value::text) AS dimension_value,
    dc.status
FROM dimension_configs dc
CROSS JOIN LATERAL json_array_elements(
    CASE
        WHEN dc.dimension_values IS NOT NULL AND dc.dimension_values != '' AND dc.dimension_values != '[]'::text
        THEN dc.dimension_values::json
        ELSE '[]'::json
    END
) AS value
WHERE value IS NOT NULL
  AND COALESCE(value->>'value', value->>'dimension_value', value::text) IS NOT NULL
  AND COALESCE(value->>'value', value->>'dimension_value', value::text) != ''
ON CONFLICT (table_name, column_name, dimension_value) DO NOTHING;

-- Step 4: 验证数据
SELECT 'dimension_type_mappings 迁移后 dim_value_mapping_new 行数:' AS msg, COUNT(*) AS cnt FROM dim_value_mapping_new;
