"""
MetricClient - LLM.V1 指标客户端
封装 Go API 调用，获取指标元数据
"""
import logging
from typing import Dict, List, Any, Optional

from ai.client.metric_client import MetricClient as BaseMetricClient

logger = logging.getLogger("ai.llm_v1.metric_client")


class MetricClient:
    """
    LLM.V1 指标客户端

    职责：
    1. 调用 Go API 获取指标元数据
    2. 缓存指标列表和维度配置
    3. 提供简洁的接口给各节点使用
    """

    def __init__(self):
        self._client = BaseMetricClient(base_url="http://localhost:8080")
        self._metrics_cache = None
        self._dimensions_cache = None
        self._terms_cache = None

    def get_all_metrics(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有指标

        Args:
            force_reload: 是否强制重新加载

        Returns:
            指标列表
        """
        if force_reload or self._metrics_cache is None:
            try:
                self._metrics_cache = self._client.get_all_metrics()
                logger.info(f"[MetricClient] 加载 {len(self._metrics_cache)} 个指标")
            except Exception as e:
                logger.error(f"[MetricClient] 获取指标列表失败: {e}")
                self._metrics_cache = []
        return self._metrics_cache

    def get_metric_by_code(self, metric_code: str) -> Optional[Dict[str, Any]]:
        """
        根据 metric_code 获取指标详情

        Args:
            metric_code: 指标代码，如 "MKI-02-0001"

        Returns:
            指标详情，包含 starrocks_sql、dimensions 等
        """
        try:
            return self._client.get_metric_by_code(metric_code)
        except Exception as e:
            logger.error(f"[MetricClient] 获取指标详情失败: {e}")
            return None

    def get_metric_by_name(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        根据指标名称获取指标（模糊匹配）

        Args:
            metric_name: 指标名称

        Returns:
            匹配的指标详情
        """
        metrics = self.get_all_metrics()
        metric_name_lower = metric_name.lower()

        # 先尝试精确匹配
        for m in metrics:
            name = m.get("name", "")
            if name and metric_name_lower == name.lower():
                return m

        # 再尝试包含匹配（双向）
        best_match = None
        best_score = 0

        # 核心业务关键词及其权重
        core_keywords_with_weight = {
            '广告': 5, '点击': 15, '转化': 10, '销量': 10, '销售': 8, '收入': 8, '利润': 10, '成本': 10,
            '花费': 5, '退款': 15, '退货': 15, '会话': 15, '访问': 10, '页面': 10, '订单': 8, '客单价': 15,
            '产出': 10, 'ROAS': 20, 'CPC': 20, 'CPA': 20, 'ACOS': 20, 'CTR': 20, 'CVR': 20,
        }
        core_keywords = list(core_keywords_with_weight.keys())

        for m in metrics:
            name = m.get("name", "")
            name_en = m.get("name_en", "")

            name_lower = name.lower() if name else ""
            name_en_lower = name_en.lower() if name_en else ""

            score = 0

            # 中文名匹配
            if name_lower:
                # 完全包含检查
                if metric_name_lower in name_lower or name_lower in metric_name_lower:
                    score = max(score, min(len(metric_name_lower), len(name_lower)) * 3)

                # 如果名称完全相同（exact match），额外加分确保优先
                # 这是最重要的信号：用户/LLM明确指定了某个metric
                if name_lower == metric_name_lower:
                    score += 50

                # 增强：如果指标名比查询词长，且以查询词结尾，这是更具体的metric
                # 例如：输入"会话量"（但可能是LLM从"B2BAPP会话量"截断的），"B2BAPP会话量"比"会话量"更具体
                # 但 exact match 的优先级更高，所以这个增强只在 exact match 不存在时才有意义
                if len(name_lower) > len(metric_name_lower) and name_lower.endswith(metric_name_lower):
                    score += 40  # 更具体metric的加分，但低于exact match

                # 核心关键词匹配（带权重）
                metric_core = [(k, core_keywords_with_weight[k]) for k in core_keywords if k in metric_name_lower]
                name_core = [k for k in core_keywords if k in name_lower]

                # 计算关键词重叠分数
                for k, w in metric_core:
                    if k in name_core:
                        score += w

                # 额外检查：所有核心关键词是否都在目标中（严格匹配）
                if all(k in name_lower for k, _ in metric_core if k in core_keywords):
                    score += 20

            # 英文名匹配
            if name_en_lower:
                if metric_name_lower in name_en_lower or name_en_lower in metric_name_lower:
                    score = max(score, min(len(metric_name_lower), len(name_en_lower)) * 4)
                if metric_name_lower == name_en_lower:
                    score = max(score, 100)

            if score > best_score:
                best_score = score
                best_match = m

        # 只有匹配分数超过阈值才返回
        if best_score >= 10:
            return best_match

        return None

    def get_all_dimensions(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有维度

        Args:
            force_reload: 是否强制重新加载

        Returns:
            维度列表
        """
        if force_reload or self._dimensions_cache is None:
            try:
                self._dimensions_cache = self._client.get_all_dimensions()
                logger.info(f"[MetricClient] 加载 {len(self._dimensions_cache)} 个维度")
            except Exception as e:
                logger.error(f"[MetricClient] 获取维度列表失败: {e}")
                self._dimensions_cache = []
        return self._dimensions_cache

    def get_dimension_configs(self, table_name: str = None) -> List[Dict[str, Any]]:
        """
        获取维度配置

        Args:
            table_name: 表名（可选）

        Returns:
            维度配置列表
        """
        try:
            return self._client.get_dimension_configs(table_name)
        except Exception as e:
            logger.error(f"[MetricClient] 获取维度配置失败: {e}")
            return []

    def get_all_terms(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有业务术语（同义词）

        Args:
            force_reload: 是否强制重新加载

        Returns:
            术语列表
        """
        if force_reload or self._terms_cache is None:
            try:
                self._terms_cache = self._client.get_all_terms()
                logger.info(f"[MetricClient] 加载 {len(self._terms_cache)} 个业务术语")
            except Exception as e:
                logger.error(f"[MetricClient] 获取业务术语失败: {e}")
                self._terms_cache = []
        return self._terms_cache

    def build_dimension_map(self) -> Dict[str, str]:
        """
        构建维度映射表：中文名 → 列名

        Returns:
            维度映射字典
        """
        dimension_configs = self.get_dimension_configs()
        dimension_map = {}

        for config in dimension_configs:
            dimension_name = config.get("dimension_name", "")
            column_name = config.get("column_name", "")
            if dimension_name and column_name:
                dimension_map[dimension_name] = column_name

        logger.info(f"[MetricClient] 构建维度映射表: {len(dimension_map)} 个映射")
        return dimension_map

    def build_reverse_dimension_map(self) -> Dict[str, str]:
        """
        构建反向维度映射表：列名 → 中文名

        Returns:
            反向映射字典
        """
        dimension_configs = self.get_dimension_configs()
        reverse_map = {}

        for config in dimension_configs:
            dimension_name = config.get("dimension_name", "")
            column_name = config.get("column_name", "")
            if dimension_name and column_name:
                reverse_map[column_name] = dimension_name

        return reverse_map

    def build_business_terms_map(self) -> Dict[str, str]:
        """
        构建业务术语映射表：同义词 → 标准名

        Returns:
            术语映射字典
        """
        terms = self.get_all_terms()
        terms_map = {}

        for term in terms:
            synonym = term.get("synonym", "")
            standard_name = term.get("standard_name", "")
            if synonym and standard_name:
                terms_map[synonym] = standard_name

        logger.info(f"[MetricClient] 构建业务术语映射表: {len(terms_map)} 个映射")
        return terms_map

    def search_metrics(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索指标（按名称或代码）

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的指标列表
        """
        metrics = self.get_all_metrics()
        keyword_lower = keyword.lower()
        results = []

        for m in metrics:
            name = m.get("name", "")
            name_en = m.get("name_en", "")
            code = m.get("metric_code", "")

            if (name and keyword_lower in name.lower()) or \
               (name_en and keyword_lower in name_en.lower()) or \
               (code and keyword_lower in code.lower()):
                results.append(m)

        return results


# 全局实例
_metric_client: Optional[MetricClient] = None


def get_metric_client() -> MetricClient:
    """获取指标客户端单例"""
    global _metric_client
    if _metric_client is None:
        _metric_client = MetricClient()
    return _metric_client
