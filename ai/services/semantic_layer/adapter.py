"""
语义服务层适配器

将语义服务层的 ParseResult 适配到 Graph 节点需要的格式
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from typing import Dict, Any, Optional

from ai.config.logging_config import get_logger
from ai.services.semantic_layer import SemanticLayerService, get_semantic_layer_service

logger = get_logger("semantic_layer.adapter")


class SemanticLayerAdapter:
    """
    语义服务层适配器

    将语义服务层的 ParseResult 适配到 Graph 节点需要的格式

    Graph 节点期望的返回格式：
    {
        "mql": MQLSchema,
        "needs_clarification": bool,
        "clarification_message": str,
        "clarification_options": list,
        "source": str,
        "drilldown_type": str,
        ...
    }
    """

    def __init__(self):
        self._service = None

    @property
    def service(self) -> SemanticLayerService:
        if self._service is None:
            self._service = get_semantic_layer_service()
        return self._service

    def parse_for_graph(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        解析查询并适配到 Graph 格式

        Args:
            query: 用户问题
            context: 上下文

        Returns:
            Graph 格式的解析结果
        """
        # 1. 调用语义服务层解析
        parse_result = self.service.parse_query(query)

        # 记录语义层监控指标
        self._record_metrics(parse_result)

        # 2. 转换为 Graph 需要的格式
        if parse_result.intent == "unknown":
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": "抱歉，我无法理解您的问题，请换一种问法。",
                "clarification_options": [],
                "source": "semantic_layer_failed",
                "error": parse_result.error,
            }

        # 3. 构建 MQLSchema（复用 intent_router 的逻辑）
        mql = self._build_mql_from_parse_result(parse_result, query)
        logger.info(f"[SemanticLayerAdapter] parse_result.metric_name={parse_result.metric_name}, parse_result.entities count={len(parse_result.entities)}, parse_result.entities={parse_result.entities}")

        # 4. 检测是否需要追问（泛指维度等）
        needs_clarification, clarification_message, clarification_options = self._check_needs_clarification(
            mql, parse_result, query
        )

        return {
            "mql": mql,
            "needs_clarification": needs_clarification,
            "clarification_message": clarification_message,
            "clarification_options": clarification_options,
            "source": "semantic_layer",
            "parse_result": parse_result,
            "drilldown_type": parse_result.drilldown_type,
        }

    def _record_metrics(self, parse_result) -> None:
        """记录语义层监控指标"""
        try:
            # 获取 parse_method (local_model/snapshot/rule/llm)
            engine = parse_result.parse_method or "unknown"
            # 映射 parse_method 到标准引擎名称
            engine_map = {
                "local_model": "local_model",
                "snapshot": "snapshot",
                "rule": "rule",
                "llm": "llm",
                "local": "local_model",
            }
            engine = engine_map.get(engine, engine)

            from ai.engine.llm_v2.metrics import get_performance_tracker
            tracker = get_performance_tracker()
            tracker.record_semantic_layer(
                engine=engine,
                confidence=parse_result.confidence,
                needs_clarification=(parse_result.intent == "unknown"),
            )
        except Exception as e:
            logger.warning(f"[SemanticLayerAdapter] 记录监控指标失败: {e}")

    def _build_mql_from_parse_result(
        self,
        parse_result,
        query: str
    ):
        """从 ParseResult 构建 MQLSchema"""
        from ai.engine.llm_v2.schema import (
            MQLSchema,
            MQLMetric,
            MQLIntent,
            TimeRange,
            MQLDimension,
            ComparisonSpec,
        )

        mql = MQLSchema()
        mql.original_question = query

        # 意图
        intent_map = {
            "query_value": MQLIntent.QUERY_VALUE,
            "query_trend": MQLIntent.QUERY_TREND,
            "query_comparison": MQLIntent.QUERY_COMPARISON,
            "query_ranking": MQLIntent.QUERY_RANKING,
            "query_drilldown": MQLIntent.QUERY_VALUE,
            "query_anomaly": MQLIntent.QUERY_TREND,
        }
        mql.intent = intent_map.get(parse_result.intent, MQLIntent.QUERY_VALUE)

        # 指标
        if parse_result.metric_name:
            mql.metric = MQLMetric(
                name=parse_result.metric_name,
                code=parse_result.metric_code,
            )

        # 时间
        if parse_result.time_expr:
            mql.time = TimeRange(original=parse_result.time_expr)

        # 维度
        for dim in parse_result.dimensions:
            if isinstance(dim, dict):
                mql_dim = MQLDimension(
                    type=dim.get("type", ""),
                    value=dim.get("value"),
                )
                mql.dimensions.append(mql_dim)

        # 对比类型
        if parse_result.comparison_types:
            mql.comparison = ComparisonSpec(
                enabled=True,
                types=parse_result.comparison_types,
                compare_period_start="",
                compare_period_end="",
            )
            # 如果有对比类型且当前意图不是 comparison，改为 comparison
            if mql.intent != MQLIntent.QUERY_COMPARISON:
                mql.intent = MQLIntent.QUERY_COMPARISON

        return mql

    def _check_needs_clarification(
        self,
        mql,
        parse_result,
        query: str
    ) -> tuple[bool, str, list]:
        """
        检查是否需要追问

        Returns:
            (needs_clarification, clarification_message, clarification_options)
        """
        # 如果是泛指维度，需要追问
        # 例如："按品类查看" 需要确认具体是哪个品类

        # TODO: 实现泛指维度检测逻辑
        # 目前简化处理：如果有维度但没有具体值，可能需要追问

        return False, "", []


# 单例
_adapter: Optional[SemanticLayerAdapter] = None


def get_semantic_layer_adapter() -> SemanticLayerAdapter:
    """获取语义服务层适配器"""
    global _adapter
    if _adapter is None:
        _adapter = SemanticLayerAdapter()
    return _adapter
