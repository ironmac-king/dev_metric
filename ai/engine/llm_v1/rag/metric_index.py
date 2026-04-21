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

    def _remove_time_expressions(self, text: str) -> str:
        """
        移除时间相关表达，保留指标相关词

        例如：
        - "上个月未税收入是多少" → "未税收入是多少"
        - "2026年3月份销售额" → "销售额"
        """
        # 时间词列表（按长度降序排列，避免部分匹配问题）
        time_patterns = [
            # 年月表达
            "2026年", "2025年", "2024年",
            # 月份表达
            "本月", "上月", "下月",
            # 带"个"的月份表达（需按长度降序，"上个月"要在"上月"前面）
            "上个月", "本月",
            # 近N天
            "近7天", "近30天", "近15天", "近10天", "近60天",
            # 周相关
            "上周", "本周", "下周",
            # 日相关
            "昨天", "今天", "明天",
            # 其他时间词
            "月份", "年度", "季度",
            # 日期前缀
            "2026-", "2025-", "2024-",
        ]

        result = text
        for pattern in time_patterns:
            result = result.replace(pattern, "")

        # 清理多余空格
        result = " ".join(result.split())
        return result

    def _apply_synonym_replacement(self, text: str) -> str:
        """
        应用同义词替换，将用户表达转换为标准指标名

        策略：
        1. 优先匹配更长的同义词，避免部分匹配问题
        2. 检查标准词是否已在文本中，避免对已替换的词再次替换

        例如：
        - "不含税收入" → "未税收入"
        - "净收入" → "未税收入"
        """
        from ..config_loader import get_config_loader
        config_loader = get_config_loader()
        business_terms = config_loader.get_config().business_terms

        # 调试日志：打印 business_terms 前 20 个 key 及其长度
        logger.info(f"[MetricIndex] business_terms 共 {len(business_terms)} 条")
        if business_terms:
            sample_keys = list(business_terms.keys())[:10]
            logger.info(f"[MetricIndex] business_terms 样本 keys: {sample_keys}")

        # 按长度降序排列同义词，优先匹配更长的词
        sorted_terms = sorted(business_terms.items(), key=lambda x: len(x[0]), reverse=True)

        # 调试日志：打印排序后的前 10 个
        logger.info(f"[MetricIndex] 排序后同义词（前10个）:")
        for i, (synonym, standard) in enumerate(sorted_terms[:10]):
            found = "✓" if synonym in text else "✗"
            logger.info(f"  [{i}] len={len(synonym)} '{synonym}' -> '{standard}' [in text: {found}]")

        result = text
        replaced = False
        for synonym, standard in sorted_terms:
            if synonym in result:
                # 重要：如果标准词已经在文本中存在，跳过此次替换（避免链式反应）
                # 例如：退款数量 → 退款金额数量，但"退款金额"已存在则不再替换
                if standard in result:
                    logger.info(f"[MetricIndex] 跳过同义词替换: '{synonym}' -> '{standard}'，因为标准词已在文本中")
                    continue
                result = result.replace(synonym, standard)
                logger.info(f"[MetricIndex] 同义词替换: '{synonym}' -> '{standard}'")
                replaced = True
                break  # 只替换第一个匹配的同义词（最长匹配）

        if not replaced:
            logger.info(f"[MetricIndex] 无同义词可替换")

        return result

    async def search_metric(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """
        搜索最相关的指标（分阶段检索策略）

        Stage 1: 完整问句搜索
        Stage 2: 移除时间词后搜索
        Stage 3: 同义词替换后再搜索
        Stage 4: get_metric_by_name 模糊匹配兜底

        Args:
            query: 用户查询（自然语言）
            top_k: 返回数量

        Returns:
            按相似度排序的指标列表
        """
        logger.info(f"[MetricIndex] 搜索指标: query={query}, top_k={top_k}")

        metric_client = self._get_metric_client()

        # 初始化已存在的结果集合（用于去重）
        existing_codes: set = set()

        # ===== Stage 1: 完整问句搜索 =====
        search_results = metric_client.search_metrics(query)
        logger.info(f"[MetricIndex] Stage1 完整问句搜索: {len(search_results)} 个结果")
        existing_codes = {m.get("metric_code") for m in search_results}

        # ===== Stage 2: 移除时间词后搜索 =====
        if len(search_results) < top_k:
            query_no_time = self._remove_time_expressions(query)
            if query_no_time and query_no_time != query:
                logger.info(f"[MetricIndex] Stage2 移除时间词: '{query}' -> '{query_no_time}'")
                results2 = metric_client.search_metrics(query_no_time)
                logger.info(f"[MetricIndex] Stage2 移除时间词搜索: {len(results2)} 个结果")

                # 合并结果（去重）
                for m in results2:
                    if m.get("metric_code") not in existing_codes:
                        search_results.append(m)
                        existing_codes.add(m.get("metric_code"))

        # ===== Stage 3: 同义词替换后再搜索 =====
        if len(search_results) < top_k:
            # 先对移除时间词后的结果进行同义词替换
            query_no_time = self._remove_time_expressions(query)
            query_synonym = self._apply_synonym_replacement(query_no_time if query_no_time else query)
            if query_synonym and query_synonym != query_no_time:
                logger.info(f"[MetricIndex] Stage3 同义词替换: '{query_no_time}' -> '{query_synonym}'")
                results3 = metric_client.search_metrics(query_synonym)
                logger.info(f"[MetricIndex] Stage3 同义词替换搜索: {len(results3)} 个结果")

                # 合并结果（去重）
                for m in results3:
                    if m.get("metric_code") not in existing_codes:
                        search_results.append(m)
                        existing_codes.add(m.get("metric_code"))

        # ===== Stage 4: get_metric_by_name 模糊匹配兜底 =====
        if len(search_results) < top_k:
            logger.info(f"[MetricIndex] Stage4 开始模糊匹配兜底, 当前已有 {len(search_results)} 个结果")
            fuzzy_result = metric_client.get_metric_by_name(query)
            if fuzzy_result and fuzzy_result.get("metric_code") not in existing_codes:
                logger.info(f"[MetricIndex] Stage4 模糊匹配兜底: {fuzzy_result.get('metric_code')}")
                search_results.append(fuzzy_result)

        # 限制返回数量
        search_results = search_results[:top_k]

        # 转换为 SearchResult
        results = []
        for m in search_results:
            metric_info = self._convert_to_metric_info(m)
            results.append(SearchResult(
                metric_info=metric_info,
                similarity=1.0,  # 精确匹配为 1.0
            ))

        logger.info(f"[MetricIndex] 最终搜索结果: {len(results)} 个指标")
        for r in results:
            logger.info(f"  - {r.metric_info.name} ({r.metric_info.metric_code})")

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
