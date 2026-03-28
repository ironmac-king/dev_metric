"""
调用 Go 指标平台 API
"""
import httpx
from typing import List, Dict, Any, Optional


class MetricClient:
    """指标平台 API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """获取所有指标"""
        response = httpx.get(f"{self.base_url}/api/v1/metadata/metrics")
        response.raise_for_status()
        return response.json()["data"]

    def get_metric(self, metric_id: int) -> Dict[str, Any]:
        """获取指标详情"""
        response = httpx.get(f"{self.base_url}/api/v1/metadata/metrics/{metric_id}")
        response.raise_for_status()
        return response.json()["data"]

    def get_all_dimensions(self) -> List[Dict[str, Any]]:
        """获取所有维度"""
        response = httpx.get(f"{self.base_url}/api/v1/metadata/dimensions")
        response.raise_for_status()
        return response.json()["data"]

    def get_all_terms(self) -> List[Dict[str, Any]]:
        """获取所有业务术语"""
        response = httpx.get(f"{self.base_url}/api/v1/metadata/terms")
        response.raise_for_status()
        return response.json()["data"]

    def get_metric_data(self, metric_id: int) -> Dict[str, Any]:
        """获取指标数据"""
        response = httpx.get(f"{self.base_url}/api/v1/metrics/{metric_id}/data")
        response.raise_for_status()
        return response.json()["data"]

    async def get_all_metrics_async(self) -> List[Dict[str, Any]]:
        """异步获取所有指标"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/metadata/metrics")
            response.raise_for_status()
            return response.json()["data"]

    def search_metrics(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索指标 - 在名称、定义、口径中模糊匹配
        返回最相关的指标列表
        """
        try:
            metrics = self.get_all_metrics()
            query_lower = query.lower()
            scored = []

            for m in metrics:
                name = (m.get("name") or "").lower()
                name_en = (m.get("name_en") or "").lower()
                business_def = (m.get("business_definition") or "").lower()
                business_rule = (m.get("business_rule") or "").lower()
                tech_rule = (m.get("technical_rule") or "").lower()

                # 计算匹配分数
                score = 0

                # 1. 名称完全匹配（查询词完全等于指标名）
                if query_lower == name:
                    score += 100
                # 2. 名称包含查询词（关键词在名称中）
                elif query_lower in name:
                    score += 20

                # 英文名匹配
                if query_lower == name_en:
                    score += 50
                elif query_lower in name_en:
                    score += 10

                # 4. 定义/口径匹配（需要查询至少3个字符，且完整匹配才加分，避免"费"匹配到"费用"）
                if len(query_lower) >= 3:
                    if query_lower in business_def:
                        score += 5
                    if query_lower in business_rule:
                        score += 3
                    if query_lower in tech_rule:
                        score += 2

                # 5. 字符级模糊匹配（仅当查询长度>=2，且其他匹配分数<10时）
                if score < 10 and len(query_lower) >= 2:
                    query_chars = set(query_lower)
                    name_chars = set(name.replace(" ", ""))
                    if query_chars and name_chars:
                        intersection = query_chars & name_chars
                        # 要求查询中所有字符都出现在名称中
                        if intersection == query_chars:
                            score += 8
                        elif len(intersection) >= len(query_chars) * 0.8:
                            score += 4

                if score > 0:
                    scored.append((score, m))

            # 按分数排序，取前 limit 个
            scored.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in scored[:limit]]
        except Exception as e:
            print(f"[MetricClient] 搜索指标失败: {e}")
            return []
