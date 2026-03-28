-- 意图向量表：存储意图模板的向量表示，用于语义相似度匹配
CREATE TABLE IF NOT EXISTS intent_embeddings (
    id SERIAL PRIMARY KEY,
    intent_id INTEGER NOT NULL REFERENCES intent_templates(id) ON DELETE CASCADE,
    intent_type VARCHAR(32) NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1536),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(intent_id)
);

-- 创建索引加速相似度搜索
CREATE INDEX IF NOT EXISTS idx_intent_embeddings_embedding ON intent_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 创建意图类型的索引
CREATE INDEX IF NOT EXISTS idx_intent_embeddings_intent_type ON intent_embeddings(intent_type);
