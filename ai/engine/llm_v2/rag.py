"""
V2 RAG（检索增强生成）实现

提供：
1. Embedding 生成
2. 向量存储（PostgreSQL pgvector）
3. 相似度搜索
"""
import json
import httpx
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.rag")

# ==================== Embedding 生成 ====================

class EmbeddingGenerator:
    """
    Embedding 生成器

    使用阿里 text-embedding-v2 生成向量。
    """

    def __init__(self):
        self._api_key = None
        self._base_url = "https://dashscope.aliyuncs.com/api/v1"
        self._model = "text-embedding-v2"
        self._dimensions = 1536

    def _get_api_key(self) -> str:
        """获取 API Key"""
        if self._api_key:
            return self._api_key

        import os
        self._api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not self._api_key:
            logger.warning("[EmbeddingGenerator] DASHSCOPE_API_KEY 未设置")
        return self._api_key

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        生成 Embedding 向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        api_key = self._get_api_key()
        if not api_key:
            logger.warning("[EmbeddingGenerator] 无法生成 embedding，API Key 为空")
            return [[0.0] * self._dimensions for _ in texts]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self._base_url}/services/embeddings/text-embedding",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "input": {"texts": texts},
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    embeddings = []
                    for item in result.get("data", []):
                        embeddings.append(item.get("embedding", []))
                    logger.debug(f"[EmbeddingGenerator] 生成 {len(embeddings)} 个向量")
                    return embeddings
                else:
                    logger.error(f"[EmbeddingGenerator] API 错误: {response.status_code}, {response.text}")
                    return [[0.0] * self._dimensions for _ in texts]

        except Exception as e:
            logger.error(f"[EmbeddingGenerator] 生成失败: {e}")
            return [[0.0] * self._dimensions for _ in texts]

    async def embed_single(self, text: str) -> List[float]:
        """
        生成单个文本的 Embedding

        Args:
            text: 文本

        Returns:
            向量
        """
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else [0.0] * self._dimensions


# ==================== 向量存储 ====================

class VectorStore:
    """
    向量存储

    使用 PostgreSQL pgvector 存储和搜索向量。
    """

    def __init__(self):
        self._embedding_generator = EmbeddingGenerator()
        self._pg_conn = None
        self._init_pg()

    def _init_pg(self):
        """初始化 PostgreSQL 连接"""
        try:
            import psycopg2
            self._pg_conn = psycopg2.connect(
                host="192.168.1.225",
                port=5432,
                database="metrics",
                user="metrics",
                password="metrics123",
            )
            logger.info("[VectorStore] PostgreSQL 连接成功")
        except Exception as e:
            logger.warning(f"[VectorStore] PostgreSQL 连接失败: {e}，RAG 将不可用")
            self._pg_conn = None

    async def add(self, texts: List[str], metadata: List[Dict[str, Any]] = None) -> bool:
        """
        添加向量

        Args:
            texts: 文本列表
            metadata: 元数据列表

        Returns:
            是否成功
        """
        if not self._pg_conn:
            return False

        try:
            # 生成 embedding
            embeddings = await self._embedding_generator.embed(texts)

            # 批量插入
            with self._pg_conn.cursor() as cur:
                for i, (text, embedding) in enumerate(zip(texts, embeddings)):
                    meta = metadata[i] if metadata and i < len(metadata) else {}

                    # 转换为 JSONB
                    meta_json = json.dumps(meta, ensure_ascii=False)

                    # 计算向量维度
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

                    cur.execute(
                        """
                        INSERT INTO query_embeddings (text, embedding, metadata)
                        VALUES (%s, %s::vector, %s)
                        """,
                        (text, embedding_str, meta_json)
                    )

            self._pg_conn.commit()
            logger.info(f"[VectorStore] 添加 {len(texts)} 条向量")
            return True

        except Exception as e:
            logger.error(f"[VectorStore] 添加向量失败: {e}")
            self._pg_conn.rollback()
            return False

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_conditions: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索相似向量

        Args:
            query: 查询文本
            top_k: 返回数量
            filter_conditions: 过滤条件

        Returns:
            相似结果列表
        """
        if not self._pg_conn:
            logger.warning("[VectorStore] PostgreSQL 未连接，无法搜索")
            return []

        try:
            # 生成查询向量
            query_embedding = await self._embedding_generator.embed_single(query)
            query_embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            # 构建 SQL
            sql = """
                SELECT text, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM query_embeddings
                WHERE 1=1
            """
            params = [query_embedding_str]

            # 添加过滤条件
            if filter_conditions:
                for key, value in filter_conditions.items():
                    sql += f" AND metadata->>%s = %s"
                    params.extend([key, str(value)])

            sql += f"""
                ORDER BY embedding <=> %s::vector
                LIMIT {top_k}
            """
            params.append(query_embedding_str)

            # 执行查询
            with self._pg_conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    "text": row[0],
                    "metadata": row[1],
                    "similarity": float(row[2]) if row[2] else 0.0,
                })

            logger.debug(f"[VectorStore] 搜索到 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"[VectorStore] 搜索失败: {e}")
            return []

    async def find_similar_queries(
        self,
        question: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        查找相似的历史查询

        Args:
            question: 当前问题
            top_k: 返回数量

        Returns:
            相似查询列表
        """
        results = await self.search(question, top_k=top_k)

        # 只返回相似度 > 0.7 的
        return [r for r in results if r["similarity"] > 0.7]


# ==================== RAG 服务 ====================

_embedding_generator: Optional[EmbeddingGenerator] = None
_vector_store: Optional[VectorStore] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """获取 Embedding 生成器单例"""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator


def get_vector_store() -> VectorStore:
    """获取向量存储单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


async def rag_retrieve(question: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    RAG 检索

    Args:
        question: 用户问题
        top_k: 返回数量

    Returns:
        相似案例列表
    """
    try:
        vector_store = get_vector_store()
        results = await vector_store.find_similar_queries(question, top_k=top_k)
        return results
    except Exception as e:
        logger.error(f"[rag_retrieve] 检索失败: {e}")
        return []


async def rag_index(question: str, mql_dict: Dict[str, Any], sql: str = "") -> bool:
    """
    RAG 索引

    将问答对存入向量数据库。

    Args:
        question: 用户问题
        mql_dict: MQL 字典
        sql: 生成的 SQL

    Returns:
        是否成功
    """
    try:
        vector_store = get_vector_store()
        metadata = {
            "question": question,
            "mql": mql_dict,
            "sql": sql,
            "indexed_at": datetime.now().isoformat(),
        }
        success = await vector_store.add([question], [metadata])
        return success
    except Exception as e:
        logger.error(f"[rag_index] 索引失败: {e}")
        return False
