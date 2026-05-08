-- 启用 pgvector 扩展（用于向量检索，支持语义相似度匹配）
-- 需要 superuser 权限
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展是否启用
-- SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
