-- 维度值向量表：存储维度值的向量表示，用于语义相似度匹配
CREATE TABLE IF NOT EXISTS dim_value_embeddings (
    id SERIAL PRIMARY KEY,
    dimension_field VARCHAR(64) NOT NULL,      -- 如 GROUP_3, GROUP_2, SKU
    dimension_value VARCHAR(256) NOT NULL,      -- 如 智能云存储, 有线网卡
    dimension_type VARCHAR(64),                -- 如 品类, 平台, 渠道
    embedding vector(1536),                     -- 阿里 text-embedding-v2 向量维度
    frequency INTEGER DEFAULT 0,                -- 使用频次
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(dimension_field, dimension_value)
);

-- 创建索引加速相似度搜索
CREATE INDEX IF NOT EXISTS idx_dim_value_embedding ON dim_value_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 创建维度字段索引（用于按字段筛选）
CREATE INDEX IF NOT EXISTS idx_dim_value_field ON dim_value_embeddings(dimension_field);
