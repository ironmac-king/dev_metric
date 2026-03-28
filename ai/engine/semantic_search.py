"""
语义搜索模块 - 基于 pgvector 的向量相似度搜索
"""
import httpx
from typing import List, Dict, Any, Optional, Tuple
from ai.engine.embedding_client import embedding_client


class SemanticSearch:
    """语义搜索 - 意图/指标向量搜索"""

    # 相似度阈值
    HIGH_THRESHOLD = 0.85   # >0.85 直接确认
    MEDIUM_THRESHOLD = 0.70  # 0.70-0.85 LLM确认
    LOW_THRESHOLD = 0.0     # <0.70 LLM兜底

    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base

    def search_intent(self, query: str, top_k: int = 5) -> Tuple[Optional[str], float]:
        """
        搜索相似意图

        Returns:
            (意图类型, 相似度) 如果找到返回意图类型，否则返回 None
        """
        # 1. 生成查询向量
        query_embedding = embedding_client.embed_single(query)
        if not query_embedding:
            return None, 0.0

        # 2. 调用 Go API 搜索
        try:
            response = httpx.post(
                f"{self.api_base}/api/v1/nlp/semantic-search/intent",
                json={"embedding": query_embedding, "top_k": top_k},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    results = data.get("data", [])
                    if results:
                        best = results[0]
                        return best.get("intent_type"), best.get("similarity", 0.0)
        except Exception as e:
            print(f"[SemanticSearch] 搜索意图失败: {e}")

        return None, 0.0

    def search_metric(self, query: str, top_k: int = 5) -> Tuple[Optional[Dict], float]:
        """
        搜索相似指标

        Returns:
            (指标信息 dict, 相似度) 如果找到返回指标信息，否则返回 None
        """
        # 1. 生成查询向量
        query_embedding = embedding_client.embed_single(query)
        if not query_embedding:
            return None, 0.0

        # 2. 调用 Go API 搜索
        try:
            response = httpx.post(
                f"{self.api_base}/api/v1/nlp/semantic-search/metric",
                json={"embedding": query_embedding, "top_k": top_k},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    results = data.get("data", [])
                    if results:
                        best = results[0]
                        return {
                            "metric_id": best.get("metric_id"),
                            "metric_code": best.get("metric_code"),
                            "metric_name": best.get("text", "").split()[0] if best.get("text") else "",
                        }, best.get("similarity", 0.0)
        except Exception as e:
            print(f"[SemanticSearch] 搜索指标失败: {e}")

        return None, 0.0

    def match_intent(self, query: str) -> Tuple[Optional[str], str]:
        """
        匹配意图 - 三层降级

        Returns:
            (意图类型, 匹配级别) 匹配级别: "high", "medium", "low", "none"
        """
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
        """
        匹配指标 - 三层降级

        Returns:
            (指标信息, 匹配级别)
        """
        metric_info, similarity = self.search_metric(query)

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