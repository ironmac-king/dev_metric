"""
语义搜索模块 - 基于内存向量相似度搜索
使用 sklearn 的余弦相似度，支持直连 PostgreSQL pgvector
"""
from typing import List, Dict, Any, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import httpx
import json
import os
from ai.engine.embedding_client import embedding_client, alibaba_embedding_client
from ai.client.http_client import get_http_client


class SemanticSearch:
    """语义搜索 - 内存向量搜索"""

    # 相似度阈值
    HIGH_THRESHOLD = 0.85   # >0.85 直接确认
    MEDIUM_THRESHOLD = 0.55  # 0.55-0.85 LLM确认 (降低以支持中文近义词)
    LOW_THRESHOLD = 0.0     # <0.55 LLM兜底

    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base
        # 内存向量存储
        self._intent_vectors: Dict[str, np.ndarray] = {}  # text -> embedding
        self._intent_types: Dict[str, str] = {}  # text -> intent_type
        self._metric_vectors: Dict[str, np.ndarray] = {}  # metric_code -> embedding
        self._metric_info: Dict[str, Dict] = {}  # metric_code -> info
        self._dim_value_vectors: Dict[str, np.ndarray] = {}  # dimension_value -> embedding
        self._dim_value_info: Dict[str, Dict] = {}  # dimension_value -> info
        self._initialized = False
        self._loading = False

    def load_intent_vectors(self, intents: List[Dict[str, Any]]):
        """加载意图向量到内存"""
        for item in intents:
            text = item.get("text", "")
            intent_type = item.get("intent_type", "")
            embedding = item.get("embedding", [])

            if text and embedding and len(embedding) > 0:
                self._intent_vectors[text] = np.array(embedding)
                self._intent_types[text] = intent_type

        self._initialized = True
        print(f"[SemanticSearch] 加载了 {len(self._intent_vectors)} 个意图向量")

    def load_metric_vectors(self, metrics: List[Dict[str, Any]]):
        """加载指标向量到内存"""
        for item in metrics:
            metric_code = item.get("metric_code", "")
            text = item.get("text", "")
            embedding = item.get("embedding", [])
            info = item.get("info", {})

            if metric_code and embedding and len(embedding) > 0:
                self._metric_vectors[metric_code] = np.array(embedding)
                self._metric_info[metric_code] = {
                    "text": text,
                    "info": info
                }

        print(f"[SemanticSearch] 加载了 {len(self._metric_vectors)} 个指标向量")

    def ensure_loaded(self):
        """确保向量已加载（懒加载）"""
        if self._initialized or self._loading:
            return

        self._loading = True
        try:
            # 优先从 PostgreSQL pgvector 加载
            self._load_vectors_from_pgvector()
        except Exception as e:
            print(f"[SemanticSearch] 加载向量失败: {e}")
        finally:
            self._loading = False

    def _load_vectors_from_api(self):
        """从 Go API 加载向量数据"""
        try:
            client = get_http_client()
            # 加载意图向量
            response = client.get(f"{self.api_base}/api/v1/nlp/vectors/intents", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    intents = data.get("data", [])
                    self.load_intent_vectors(intents)

            # 加载指标向量
            response = client.get(f"{self.api_base}/api/v1/nlp/vectors/metrics", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    metrics = data.get("data", [])
                    self.load_metric_vectors(metrics)

        except Exception as e:
            print(f"[SemanticSearch] 从API加载向量失败: {e}")

    def _load_vectors_from_pgvector(self):
        """从 PostgreSQL pgvector 加载向量"""
        try:
            import psycopg2

            DATABASE_URL = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:admin123@192.168.1.225:5432/dev_metric"
            )

            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 加载意图向量
            cur.execute("SELECT text, intent_type, embedding FROM intent_embeddings")
            for row in cur.fetchall():
                text, intent_type, embedding_str = row
                embedding = json.loads(embedding_str)
                self._intent_vectors[text] = np.array(embedding)
                self._intent_types[text] = intent_type

            # 加载指标向量（只加载status='在用'的指标，避免停用指标干扰）
            cur.execute("""
                SELECT me.metric_code, me.text, me.embedding
                FROM metric_embeddings me
                JOIN metrics m ON me.metric_code = m.metric_code
                WHERE m.status = '在用'
            """)
            for row in cur.fetchall():
                metric_code, text, embedding_str = row
                embedding = json.loads(embedding_str)
                self._metric_vectors[metric_code] = np.array(embedding)
                self._metric_info[metric_code] = {"text": text}

            # 加载维度值向量
            cur.execute("SELECT dimension_value, dimension_field, dimension_type, embedding FROM dim_value_embeddings")
            for row in cur.fetchall():
                dim_value, dim_field, dim_type, embedding_str = row
                embedding = json.loads(embedding_str)
                self._dim_value_vectors[dim_value] = np.array(embedding)
                self._dim_value_info[dim_value] = {
                    "dimension_field": dim_field,
                    "dimension_type": dim_type
                }

            cur.close()
            conn.close()
            self._initialized = True
            print(f"[SemanticSearch] 从 PG 加载了 {len(self._intent_vectors)} 意图向量, {len(self._metric_vectors)} 指标向量, {len(self._dim_value_vectors)} 维度值向量")

        except Exception as e:
            print(f"[SemanticSearch] 从PG加载向量失败: {e}")
            # 降级到 API 加载
            self._load_vectors_from_api()

    def search_intent(self, query: str, top_k: int = 5) -> Tuple[Optional[str], float]:
        """
        搜索相似意图

        Returns:
            (意图类型, 相似度) 如果找到返回意图类型，否则返回 None
        """
        self.ensure_loaded()

        if not self._intent_vectors:
            return None, 0.0

        # 生成查询向量（使用阿里 embedding，与 PG 中存储的向量一致）
        query_embedding = alibaba_embedding_client.embed_single(query)
        if query_embedding is None or len(query_embedding) == 0:
            return None, 0.0

        query_vec = np.array(query_embedding).reshape(1, -1)

        # 计算所有向量的相似度
        best_intent = None
        best_similarity = 0.0

        for text, vec in self._intent_vectors.items():
            vec = vec.reshape(1, -1)
            sim = cosine_similarity(query_vec, vec)[0][0]
            if sim > best_similarity:
                best_similarity = sim
                best_intent = self._intent_types.get(text)

        return best_intent, float(best_similarity)

    def search_metric(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        搜索相似指标，支持返回多个候选（混合排序）

        混合排序公式：
        score = 向量相似度 × 0.3 + 使用频率归一化分数 × 0.5 + 核心指标加成 × 0.2

        Args:
            query: 用户问题
            top_k: 返回的候选数量，默认5

        Returns:
            [{
                "metric_code": "MKI-02-0001",
                "metric_name": "销售额",
                "similarity": 0.85,
                "info": {}
            }, ...]
        """
        self.ensure_loaded()

        if not self._metric_vectors:
            return []

        # 生成查询向量（使用阿里 embedding，与 PG 中存储的向量一致）
        query_embedding = alibaba_embedding_client.embed_single(query)
        if query_embedding is None or len(query_embedding) == 0:
            return []

        query_vec = np.array(query_embedding).reshape(1, -1)

        # 获取使用频率和核心指标配置
        usage_freq = self._get_usage_frequency()
        core_metrics = self._get_core_metrics()

        # 计算所有向量的相似度，收集所有候选
        candidates = []
        max_freq = max(usage_freq.values()) if usage_freq else 1

        for code, vec in self._metric_vectors.items():
            vec = vec.reshape(1, -1)
            sim = cosine_similarity(query_vec, vec)[0][0]
            info = self._metric_info.get(code, {})

            # 从 text 字段提取指标名称（第一个词）
            metric_name = ""
            if info.get("text"):
                metric_name = info.get("text", "").split()[0] if " " in info.get("text", "") else info.get("text", "")

            # 混合评分
            # 1. 向量相似度分数 (0-1)
            sim_score = float(sim)

            # 2. 使用频率归一化分数 (0-1)
            freq = usage_freq.get(code, 0)
            freq_score = freq / max_freq if max_freq > 0 else 0

            # 3. 核心指标加成 (0 或 0.2)
            is_core = 1 if code in core_metrics else 0
            core_score = is_core * 0.2

            # 综合分数
            hybrid_score = sim_score * 0.3 + freq_score * 0.5 + core_score

            candidates.append({
                "metric_code": code,
                "metric_name": metric_name,
                "similarity": float(sim),
                "hybrid_score": hybrid_score,
                "info": info.get("info", {}),
            })

        # 按混合分数降序排序
        candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        # 返回 Top-K
        return candidates[:top_k]

    def _get_usage_frequency(self) -> Dict[str, int]:
        """获取各指标的使用频率（从 sql_audit_logs 表统计）"""
        try:
            import psycopg2
            DATABASE_URL = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:admin123@192.168.1.225:5432/dev_metric"
            )
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 统计 sql_audit_logs 中各指标被查询的次数
            # sql_audit_logs 表的 metric_id 对应 metrics 表的 id，再获取 metric_code
            cur.execute("""
                SELECT m.metric_code, COUNT(*) as cnt
                FROM sql_audit_logs l
                JOIN metrics m ON l.metric_id = m.id
                WHERE l.metric_id IS NOT NULL
                GROUP BY m.metric_code
                ORDER BY cnt DESC
            """)
            freq = {row[0]: row[1] for row in cur.fetchall()}

            cur.close()
            conn.close()
            return freq
        except Exception as e:
            print(f"[SemanticSearch] 获取使用频率失败: {e}")
            return {}

    def _get_core_metrics(self) -> set:
        """获取核心指标集合"""
        try:
            import psycopg2
            DATABASE_URL = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:admin123@192.168.1.225:5432/dev_metric"
            )
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 获取 is_core=1 的指标
            cur.execute("SELECT metric_code FROM metrics WHERE is_core = 1")
            core = {row[0] for row in cur.fetchall()}

            cur.close()
            conn.close()
            return core
        except Exception as e:
            print(f"[SemanticSearch] 获取核心指标失败: {e}")
            return {}

    def search_dimension_value(self, query: str, top_k: int = 5) -> Tuple[List[Dict], float]:
        """
        搜索相似维度值

        Returns:
            ([{"dimension_field": "GROUP_3", "dimension_value": "智能云存储", ...}], 最高相似度)
        """
        self.ensure_loaded()

        if not self._dim_value_vectors:
            return [], 0.0

        # 生成查询向量
        query_embedding = alibaba_embedding_client.embed_single(query)
        if query_embedding is None or len(query_embedding) == 0:
            return [], 0.0

        query_vec = np.array(query_embedding).reshape(1, -1)

        # 计算所有向量的相似度
        results = []
        best_similarity = 0.0

        for dim_value, vec in self._dim_value_vectors.items():
            vec = vec.reshape(1, -1)
            sim = cosine_similarity(query_vec, vec)[0][0]
            if sim > 0.5:  # 只返回相似度 > 0.5 的结果
                info = self._dim_value_info.get(dim_value, {})
                results.append({
                    "dimension_value": dim_value,
                    "dimension_field": info.get("dimension_field", ""),
                    "dimension_type": info.get("dimension_type", ""),
                    "similarity": float(sim)
                })
                if sim > best_similarity:
                    best_similarity = sim

        # 按相似度降序排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k], float(best_similarity)

    def load_dimension_value_vectors(self, force_reload: bool = False):
        """
        从 ids.dim_value_mapping 加载维度值向量
        如果 force_reload=True，强制重新生成并存储
        """
        import psycopg2
        import time

        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:admin123@192.168.1.225:5432/dev_metric"
        )

        # 检查是否需要加载（避免重复加载）
        if not force_reload and self._dim_value_vectors:
            print(f"[SemanticSearch] 维度值向量已加载，跳过 (已有 {len(self._dim_value_vectors)} 条)")
            return

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 检查表中是否有数据
            cur.execute("SELECT COUNT(*) FROM dim_value_embeddings")
            count = cur.fetchone()[0]

            if count > 0 and not force_reload:
                # 从 PG 加载已有向量
                cur.execute("SELECT dimension_value, dimension_field, dimension_type, embedding FROM dim_value_embeddings")
                for row in cur.fetchall():
                    dim_value, dim_field, dim_type, embedding_str = row
                    embedding = json.loads(embedding_str)
                    self._dim_value_vectors[dim_value] = np.array(embedding)
                    self._dim_value_info[dim_value] = {
                        "dimension_field": dim_field,
                        "dimension_type": dim_type
                    }
                print(f"[SemanticSearch] 从 PG 加载了 {len(self._dim_value_vectors)} 个维度值向量")
                cur.close()
                conn.close()
                return

            # 需要重新生成向量
            print("[SemanticSearch] 开始从 StarRocks 加载维度值数据...")

            # 通过 Go API 获取维度值（查询一些常见维度值）
            # 这里简化处理：直接查询 StarRocks 的 ids.dim_value_mapping 表
            # 由于没有直接连接，我们使用一个简化的方法：使用已知的维度值
            # 实际生产中应该添加一个 Go API 来批量导出

            # 暂时跳过，等待 Go API 支持
            print("[SemanticSearch] 维度值向量加载需要 Go API 支持批量导出，暂时跳过")
            cur.close()
            conn.close()

        except Exception as e:
            print(f"[SemanticSearch] 加载维度值向量失败: {e}")

    def ensure_dim_value_loaded(self):
        """确保维度值向量已加载（懒加载）"""
        if not self._dim_value_vectors:
            self.load_dimension_value_vectors()

    def match_intent(self, query: str) -> Tuple[Optional[str], str]:
        """匹配意图 - 三层降级"""
        intent_type, similarity = self.search_intent(query)

        if similarity > self.HIGH_THRESHOLD:
            return intent_type, "high"
        elif similarity > self.MEDIUM_THRESHOLD:
            return intent_type, "medium"
        elif similarity > self.LOW_THRESHOLD:
            return intent_type, "low"
        else:
            return None, "none"

    def match_metric(self, query: str) -> Tuple[Optional[Dict], str]:
        """匹配指标 - 三层降级（返回单个最佳匹配）"""
        candidates = self.search_metric(query, top_k=1)

        if not candidates:
            return None, "none"

        metric_info = candidates[0]
        similarity = metric_info.get("similarity", 0)

        if similarity > self.HIGH_THRESHOLD:
            return metric_info, "high"
        elif similarity > self.MEDIUM_THRESHOLD:
            return metric_info, "medium"
        elif similarity > self.LOW_THRESHOLD:
            return metric_info, "low"
        else:
            return None, "none"


# 全局实例
semantic_search = SemanticSearch()