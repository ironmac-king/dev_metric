CREATE TABLE IF NOT EXISTS metric_embeddings (
    id SERIAL PRIMARY KEY,
    metric_id INTEGER NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    metric_code VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1536),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_id)
);

-- 创建索引加速相似度搜索
CREATE INDEX IF NOT EXISTS idx_metric_embeddings_embedding ON metric_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 创建指标编号的索引
CREATE INDEX IF NOT EXISTS idx_metric_embeddings_code ON metric_embeddings(metric_code);
