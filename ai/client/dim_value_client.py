"""
维度值查询客户端 - StarRocks 高速查询
"""
from typing import List, Dict, Optional
import httpx
from ai.config.logging_config import get_logger

logger = get_logger("ai.dim_value_client")


class DimValueClient:
    """维度值查询客户端"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    def search_dimension_values(
        self,
        query: str,
        dimension_field: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, any]]:
        """
        搜索维度值 - 分层匹配

        Args:
            query: 用户输入片段
            dimension_field: 指定维度字段，为空则搜索所有
            limit: 返回数量

        Returns:
            [{"dimension_field": "GROUP_3", "dimension_value": "有线网卡", "match_type": "exact|prefix|fuzzy"}]
        """
        try:
            response = httpx.get(
                f"{self.base_url}/api/v1/dimension-values/search",
                params={"query": query, "dimension_field": dimension_field, "limit": limit},
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("data", [])
            return []
        except Exception as e:
            logger.error(f"[DimValueClient] 查询失败: {e}")
            return []

    def increment_frequency(self, dimension_field: str, dimension_value: str):
        """用户选择后增加频次"""
        try:
            httpx.post(
                f"{self.base_url}/api/v1/dimension-values/frequency",
                json={"dimension_field": dimension_field, "dimension_value": dimension_value},
                timeout=3
            )
        except Exception as e:
            logger.error(f"[DimValueClient] 频次更新失败: {e}")