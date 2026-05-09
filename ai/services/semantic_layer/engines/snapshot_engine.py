"""
语义快照引擎

封装 SemanticSnapshotService，提供语义快照解析能力
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from ai.config.logging_config import get_logger
from ai.services.semantic_snapshot_service import get_semantic_snapshot_service

from .base import BaseEngine
from ..api import ParseResult, Entity

logger = get_logger("semantic_layer.snapshot_engine")


@dataclass
class MetricInfo:
    """指标信息"""
    metric_code: str
    name: str
    display_name: str
    unit: Optional[str] = None
    table: Optional[str] = None
    field: Optional[str] = None
    starrocks_sql: Optional[str] = None


@dataclass
class DimensionInfo:
    """维度信息"""
    dimension_code: str
    display_name: str
    column_name: str
    values: List[str]
    hierarchy_level: Optional[int] = None


class SnapshotEngine(BaseEngine):
    """
    语义快照引擎

    提供：
    - 指标解析 (resolve_metric)
    - 维度解析 (resolve_dimension)
    - 维度值搜索 (search_dimension_values)
    - 指标能力查询 (get_metric_capability)
    - 时间表达式解析
    - 对比类型检测
    """

    def __init__(self):
        super().__init__("snapshot_engine")
        self._snap_service = None

    def _init(self):
        """初始化"""
        self._snap_service = get_semantic_snapshot_service()
        logger.info("[SnapshotEngine] 初始化成功")

    def parse(self, query: str, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        用语义快照解析查询

        适用于：本地模型未命中的查询，走快照解析
        """
        self._ensure_init()

        try:
            # 1. 解析指标
            metric_result = self.resolve_metric(query)

            # 2. 解析维度
            dim_result = self.resolve_dimension(query)

            # 3. 检测对比类型
            comparison_types = self._detect_comparison(query)

            # 4. 提取时间表达式
            time_expr = self._extract_time_expr(query)

            # 5. 计算置信度
            confidence = self._calc_confidence(
                has_metric=metric_result is not None,
                has_dimension=dim_result is not None,
                has_comparison=len(comparison_types) > 0,
                has_time=time_expr is not None
            )

            # 6. 判断意图
            intent = self._detect_intent(
                query=query,
                has_comparison=len(comparison_types) > 0,
                has_dimension=dim_result is not None,
                has_metric=metric_result is not None
            )

            # 构建维度列表
            dimensions = []
            if dim_result:
                dimensions.append({
                    "type": dim_result.get("dimension_type", ""),
                    "value": dim_result.get("dimension_value")
                })

            return ParseResult(
                intent=intent,
                confidence=confidence,
                entities=[],
                metric_name=metric_result.get("name") if metric_result else None,
                metric_code=metric_result.get("metric_code") if metric_result else None,
                dimensions=dimensions,
                time_expr=time_expr,
                comparison_types=comparison_types,
                parse_method="snapshot",
                raw_result={
                    "metric_result": metric_result,
                    "dim_result": dim_result,
                }
            )

        except Exception as e:
            logger.error(f"[SnapshotEngine] parse error: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="snapshot_error",
                error=str(e)
            )

    def resolve_metric(self, query: str) -> Optional[MetricInfo]:
        """
        解析指标

        Args:
            query: 用户问题

        Returns:
            MetricInfo 或 None
        """
        self._ensure_init()

        try:
            result = self._snap_service.resolve_metric(query)
            if not result:
                return None

            return MetricInfo(
                metric_code=result.get("metric_code", ""),
                name=result.get("name", ""),
                display_name=result.get("display_name", result.get("name", "")),
                unit=result.get("unit"),
                table=result.get("starrocks_table"),
                field=result.get("starrocks_field"),
                starrocks_sql=result.get("starrocks_sql"),
            )
        except Exception as e:
            logger.warning(f"[SnapshotEngine] resolve_metric error: {e}")
            return None

    def resolve_dimension(self, query: str) -> Optional[Dict[str, Any]]:
        """
        解析维度

        Args:
            query: 用户问题

        Returns:
            维度信息 dict 或 None
        """
        self._ensure_init()

        try:
            result = self._snap_service.resolve_dimension(query)
            return result
        except Exception as e:
            logger.warning(f"[SnapshotEngine] resolve_dimension error: {e}")
            return None

    def search_dimension_values(
        self,
        query: str,
        limit: int = 20,
        column_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索维度值

        Args:
            query: 搜索词
            limit: 返回数量限制
            column_name: 限定列名

        Returns:
            维度值列表
        """
        self._ensure_init()

        try:
            return self._snap_service.search_dimension_values(query, limit, column_name)
        except Exception as e:
            logger.warning(f"[SnapshotEngine] search_dimension_values error: {e}")
            return []

    def get_metric_capability(
        self,
        snapshot: Optional[Dict[str, Any]],
        metric_code: str
    ) -> Dict[str, Any]:
        """
        获取指标能力

        Args:
            snapshot: 语义快照
            metric_code: 指标编码

        Returns:
            指标能力配置
        """
        self._ensure_init()

        return self._snap_service.get_metric_capability(snapshot, metric_code)

    def recommend_next_questions(
        self,
        metric_code: str,
        metric_name: str,
        scene_type: str = "simple_query"
    ) -> List[str]:
        """
        推荐下一步问题

        Args:
            metric_code: 指标编码
            metric_name: 指标名称
            scene_type: 场景类型

        Returns:
            推荐问题列表
        """
        self._ensure_init()

        try:
            from ai.engine.llm_v2.schema import MQLSchema
            mql = MQLSchema()
            mql.metric.name = metric_name
            mql.metric.code = metric_code
            return self._snap_service.recommend_next_questions(mql, scene_type)
        except Exception as e:
            logger.warning(f"[SnapshotEngine] recommend_next_questions error: {e}")
            return []

    def recommend_actions(
        self,
        scene_type: str = "simple_query",
        target_scene_type: str = "drilldown",
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        推荐动作

        Args:
            scene_type: 场景类型
            target_scene_type: 目标场景类型
            limit: 返回数量限制

        Returns:
            动作列表
        """
        self._ensure_init()

        try:
            return self._snap_service.recommend_actions(scene_type, target_scene_type, limit)
        except Exception as e:
            logger.warning(f"[SnapshotEngine] recommend_actions error: {e}")
            return []

    def _detect_comparison(self, query: str) -> List[str]:
        """检测对比类型"""
        comparison_types = []
        query_lower = query.lower()

        if "同比" in query or "yoy" in query_lower:
            comparison_types.append("同比")
        if "环比" in query or "mom" in query_lower:
            comparison_types.append("环比")

        return comparison_types

    def _extract_time_expr(self, query: str) -> Optional[str]:
        """提取时间表达式"""

        # 优先匹配 年+月 组合（如 "今年3月"、"去年12月"、"2025年7月"）
        year_month = re.search(r'(今年|去年|明年|\d{4}年)\s*(\d{1,2})月', query)
        if year_month:
            return year_month.group(0).replace(" ", "")

        # 匹配 单独N月（无年份前缀）
        standalone_month = re.search(r'(?<![今去明\d年])\s*(\d{1,2})月', query)
        if standalone_month:
            return standalone_month.group(0).strip()

        # 匹配季度组合（如 "今年一季度"、"去年Q3"）
        quarter = re.search(r'(今年|去年|明年|\d{4}年)\s*(一季度|二季度|三季度|四季度|[Qq]\d)', query)
        if quarter:
            return quarter.group(0).replace(" ", "")

        # 单独时间词
        time_patterns = [
            "近7天", "近30天", "最近7天", "最近30天", "近3个月",
            "本月", "上月", "下月",
            "今年", "去年", "明年",
            "一季度", "二季度", "三季度", "四季度",
            "今天", "昨天", "明天",
            "上周", "本周", "下周",
        ]

        for pattern in time_patterns:
            if pattern in query:
                return pattern
        return None

    def _calc_confidence(
        self,
        has_metric: bool,
        has_dimension: bool,
        has_comparison: bool,
        has_time: bool
    ) -> float:
        """计算置信度"""
        confidence = 0.3  # 基础分

        if has_metric:
            confidence += 0.3
        if has_dimension:
            confidence += 0.15
        if has_comparison:
            confidence += 0.15
        if has_time:
            confidence += 0.1

        return min(confidence, 1.0)

    def _detect_intent(
        self,
        query: str,
        has_comparison: bool,
        has_dimension: bool,
        has_metric: bool
    ) -> str:
        """检测意图"""
        query_lower = query.lower()

        # 排名关键词
        if any(kw in query_lower for kw in ["排名", "前几", "top", "最少", "最多"]):
            return "query_ranking"

        # 对比
        if has_comparison or any(kw in query_lower for kw in ["对比", "比较"]):
            return "query_comparison"

        # 下钻
        if has_dimension and has_metric:
            return "drilldown"

        # 趋势
        if any(kw in query_lower for kw in ["趋势", "变化", "走势"]):
            return "query_trend"

        # 默认
        return "query_value"
