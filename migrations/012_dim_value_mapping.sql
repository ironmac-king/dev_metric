-- migrations/012_dim_value_mapping.sql
-- 库表：ids.dim_value_mapping
-- 描述：StarRocks 维度值映射表，用于"维度值识别与过滤"功能

-- 创建库（如果不存在）
CREATE DATABASE IF NOT EXISTS ids;

-- 创建维度值映射表
CREATE TABLE IF NOT EXISTS ids.dim_value_mapping (
    dimension_field VARCHAR(64) NOT NULL COMMENT '维度字段名',
    dimension_value VARCHAR(256) NOT NULL COMMENT '维度值',
    dimension_value_pinyin VARCHAR(256) COMMENT '拼音首字母',
    frequency BIGINT DEFAULT 0 COMMENT '查询频次',
    last_used DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '最后使用时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(dimension_value),
    INDEX idx_field_value (dimension_field, dimension_value)
) ENGINE=OLAP
DUPLICATE KEY(dimension_field)
DISTRIBUTED BY HASH(dimension_field) BUCKETS 10;

-- 授权（切换到 admin 用户执行）
-- GRANT SELECT ON ids.dim_value_mapping TO 'ugreen_ai_ids'@'%';
