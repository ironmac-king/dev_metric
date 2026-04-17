"""
MetricIndex - 指标语义检索
基于 pgvector 的指标向量相似度搜索
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from ..metric_client import get_metric_client

logger = logging.getLogger("ai.llm_v1.metric_index")


@dataclass
class MetricInfo:
    """指标信息"""
    metric_code: str
    name: str
    name_en: Optional[str] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    business_definition: Optional[str] = None
    business_rule: Optional[str] = None
    technical_rule: Optional[str] = None
    starrocks_sql: Optional[str] = None
    common_dimensions: Optional[str] = None  # 逗号分隔的中文维度名
    unit: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)  # 同义词列表


@dataclass
class SearchResult:
    """检索结果"""
    metric_info: MetricInfo
    similarity: float


class MetricIndex:
    """
    指标语义检索

    策略：
    1. 关键词匹配：先用指标名称/代码做精确匹配
    2. 语义检索：TODO: 调用 Embedding API 向量搜索
    3. 返回最相关的指标
    """

    def __init__(self):
        self._metric_client = None

    def _get_metric_client(self):
        """获取指标客户端"""
        if self._metric_client is None:
            self._metric_client = get_metric_client()
        return self._metric_client

    async def search_metric(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """
        搜索最相关的指标

        Args:
            query: 用户查询（自然语言）
            top_k: 返回数量

        Returns:
            按相似度排序的指标列表
        """
        logger.info(f"[MetricIndex] 搜索指标: query={query}, top_k={top_k}")

        metric_client = self._get_metric_client()

        # Step 1: 关键词精确匹配
        search_results = metric_client.search_metrics(query)

        # Step 2: TODO: 语义向量搜索
        # 如果关键词匹配结果不够，进行语义搜索
        # embedding = await self._get_embedding(query)
        # vector_results = await self._search_by_vector(embedding, top_k)

        # Step 3: 合并结果
        results = []
        for m in search_results[:top_k]:
            metric_info = self._convert_to_metric_info(m)
            results.append(SearchResult(
                metric_info=metric_info,
                similarity=1.0,  # 精确匹配为 1.0
            ))

        logger.info(f"[MetricIndex] 搜索结果: {len(results)} 个指标")
        return results

    def _convert_to_metric_info(self, metric_dict: Dict[str, Any]) -> MetricInfo:
        """将 API 返回的指标字典转换为 MetricInfo"""
        return MetricInfo(
            metric_code=metric_dict.get("metric_code", ""),
            name=metric_dict.get("name", ""),
            name_en=metric_dict.get("name_en"),
            domain=metric_dict.get("domain"),
            category=metric_dict.get("category"),
            business_definition=metric_dict.get("business_definition"),
            business_rule=metric_dict.get("business_rule"),
            technical_rule=metric_dict.get("technical_rule"),
            starrocks_sql=metric_dict.get("starrocks_sql"),
            common_dimensions=metric_dict.get("common_dimensions"),
            unit=metric_dict.get("unit"),
            synonyms=[],  # TODO: 从 business_terms 获取
        )

    async def get_metric_context(self, metric_code: str) -> Optional[MetricInfo]:
        """
        获取指标详情上下文
        用于填充 Prompt 的指标信息

        Args:
            metric_code: 指标代码

        Returns:
            指标详细信息（包含同义词、定义、关联等）
        """
        logger.info(f"[MetricIndex] 获取指标上下文: metric_code={metric_code}")

        metric_client = self._get_metric_client()
        metric_dict = metric_client.get_metric_by_code(metric_code)

        if not metric_dict:
            return None

        # TODO: 获取同义词
        # terms = metric_client.get_all_terms()
        # synonyms = [t.get("synonym") for t in terms if t.get("standard_name") == metric_code]

        metric_info = self._convert_to_metric_info(metric_dict)
        return metric_info

    def build_metric_context_for_prompt(
        self,
        metric_info: MetricInfo,
        include_synonyms: bool = True,
        include_rules: bool = True,
    ) -> str:
        """
        构建用于 Prompt 的指标上下文文本

        Args:
            metric_info: 指标信息
            include_synonyms: 是否包含同义词
            include_rules: 是否包含业务/技术口径

        Returns:
            格式化的上下文文本
        """
        parts = []

        # 基本信息
        parts.append(f"### 指标基本信息")
        parts.append(f"- 指标名称：{metric_info.name}")
        if metric_info.name_en:
            parts.append(f"- 英文名称：{metric_info.name_en}")
        if metric_info.metric_code:
            parts.append(f"- 指标代码：{metric_info.metric_code}")
        if metric_info.unit:
            parts.append(f"- 单位：{metric_info.unit}")

        # 可用维度
        if metric_info.common_dimensions:
            parts.append(f"- 可用维度：{metric_info.common_dimensions}")

        # 业务定义
        if include_rules and metric_info.business_definition:
            parts.append(f"- 业务定义：{metric_info.business_definition}")

        # 业务口径
        if include_rules and metric_info.business_rule:
            parts.append(f"- 业务口径：{metric_info.business_rule}")

        # 技术口径
        if include_rules and metric_info.technical_rule:
            parts.append(f"- 技术口径：{metric_info.technical_rule}")

        # 同义词
        if include_synonyms and metric_info.synonyms:
            parts.append(f"- 同义词：{', '.join(metric_info.synonyms)}")

        return "\n".join(parts)


# 全局实例
_metric_index: Optional[MetricIndex] = None


def get_metric_index() -> MetricIndex:
    """获取指标索引单例"""
    global _metric_index
    if _metric_index is None:
        _metric_index = MetricIndex()
    return _metric_index
