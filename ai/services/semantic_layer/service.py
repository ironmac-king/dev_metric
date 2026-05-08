"""
语义服务层 - 统一API实现 (增强版)

提供统一的语义理解能力，整合本地模型、语义快照、规则引擎
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

import time
from typing import Optional, List, Dict, Any
from dataclasses import asdict

from ai.config.logging_config import get_logger
from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
from ai.engine.llm_v2.nodes.local_intent_model import get_local_intent_model, LOCAL_TO_MQL_INTENT

from .api import (
    ParseResult,
    ValidationResult,
    RecommendResult,
    RecommendContext,
    SemanticContext,
    Entity,
    EnrichResult,
    EnrichStage,
)
from .router import SemanticRouter, get_semantic_router

logger = get_logger("semantic_layer.service")


class SemanticLayerService:
    """
    语义服务层统一接口

    整合：
    - 本地模型（意图识别 + NER）
    - 语义快照（指标解析 + 维度解析 + 能力查询）
    - 规则引擎（时间解析 + 对比类型检测）
    - 语义路由（智能选择引擎）
    """

    def __init__(self):
        self._router = None
        self._snap_service = None
        self._initialized = False

    def _ensure_init(self):
        """延迟初始化"""
        if self._initialized:
            return

        # 初始化路由
        self._router = get_semantic_router()

        # 初始化语义快照服务
        self._snap_service = get_semantic_snapshot_service()

        self._initialized = True

    def parse_query(
        self,
        query: str,
        context: Optional[SemanticContext] = None
    ) -> ParseResult:
        """
        解析用户查询（统一入口）

        Args:
            query: 用户问题
            context: 语义上下文（可选）

        Returns:
            ParseResult: 解析结果
        """
        self._ensure_init()

        start_time = time.time()

        try:
            # 通过路由智能选择引擎
            result = self._router.route(query)

            # 补充指标编码（用语义快照）
            if result.metric_name and not result.metric_code:
                metric_info = self._snap_service.resolve_metric(result.metric_name)
                if metric_info:
                    result.metric_code = metric_info.get("metric_code")

            logger.info(
                f"[SemanticLayerService.parse_query] query='{query[:30]}...', "
                f"intent={result.intent}, confidence={result.confidence:.2f}, "
                f"method={result.parse_method}, duration={int((time.time()-start_time)*1000)}ms"
            )

            return result

        except Exception as e:
            logger.error(f"[SemanticLayerService] parse_query 错误: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="error",
                error=str(e),
            )

    def parse_query_local_only(
        self,
        query: str,
        context: Optional[SemanticContext] = None
    ) -> ParseResult:
        """
        仅用本地模型解析（不走路由）

        Args:
            query: 用户问题
            context: 语义上下文（可选）

        Returns:
            ParseResult: 解析结果
        """
        self._ensure_init()

        try:
            from .engines.local_model_engine import LocalModelEngine
            engine = LocalModelEngine()
            return engine.parse(query, context)
        except Exception as e:
            logger.error(f"[SemanticLayerService] parse_query_local_only 错误: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="error",
                error=str(e),
            )

    def parse_query_snapshot_only(
        self,
        query: str,
        context: Optional[SemanticContext] = None
    ) -> ParseResult:
        """
        仅用语义快照解析（不走路由）

        Args:
            query: 用户问题
            context: 语义上下文（可选）

        Returns:
            ParseResult: 解析结果
        """
        self._ensure_init()

        try:
            from .engines.snapshot_engine import SnapshotEngine
            engine = SnapshotEngine()
            return engine.parse(query, context)
        except Exception as e:
            logger.error(f"[SemanticLayerService] parse_query_snapshot_only 错误: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="error",
                error=str(e),
            )

    def validate_semantic(
        self,
        parse_result: ParseResult,
        context: Optional[SemanticContext] = None
    ) -> ValidationResult:
        """
        验证语义有效性

        Args:
            parse_result: parse_query 的结果
            context: 语义上下文

        Returns:
            ValidationResult: 验证结果
        """
        self._ensure_init()

        errors = []
        warnings = []

        # 1. 检查指标是否存在
        metric_exists = True
        if parse_result.metric_name:
            metric_info = self._snap_service.resolve_metric(parse_result.metric_name)
            if not metric_info:
                errors.append(f"指标 '{parse_result.metric_name}' 不存在")
                metric_exists = False
            else:
                # 补充 StarRocks SQL
                parse_result.raw_result["starrocks_sql"] = metric_info.get("starrocks_sql")

        # 2. 检查维度是否有效
        dimensions_valid = True
        for dim in parse_result.dimensions:
            dim_type = dim.get("type", "")
            if dim_type:
                dim_code = self._snap_service.resolve_dimension_code(dim_type)
                if not dim_code:
                    warnings.append(f"维度类型 '{dim_type}' 不在语义快照中")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            metric_exists=metric_exists,
            dimensions_valid=dimensions_valid,
            errors=errors,
            warnings=warnings,
            starrocks_sql=parse_result.raw_result.get("starrocks_sql"),
        )

    def enrich(
        self,
        parse_result: ParseResult,
        mql: Optional[Any] = None,
        stage: str = "mql_generation",
        trigger_type: Optional[str] = None
    ) -> EnrichResult:
        """
        统一语义增强入口

        封装所有 SemanticSnapshotService 调用，根据 stage 返回不同的增强内容

        Args:
            parse_result: parse_query() 的结果
            mql: MQLSchema 对象（可选）
            stage: 增强阶段，可选值：
                - "intent_router": 排名维度选项、泛指维度检测
                - "mql_generation": prompt 增强内容（维度映射、同义词等）
                - "validation": 验证结果 + starrocks_sql
                - "result_analysis": 指标能力
                - "trigger_analysis": 场景关键词、下钻分类
            trigger_type: 触发器类型（trigger_analysis 时需要）

        Returns:
            EnrichResult: 语义增强结果
        """
        self._ensure_init()

        result = EnrichResult()

        try:
            if stage == EnrichStage.INTENT_ROUTER.value or stage == "intent_router":
                self._enrich_for_intent_router(result)
            elif stage == EnrichStage.MQL_GENERATION.value or stage == "mql_generation":
                self._enrich_for_mql_generation(result)
            elif stage == EnrichStage.VALIDATION.value or stage == "validation":
                self._enrich_for_validation(result, parse_result)
            elif stage == EnrichStage.RESULT_ANALYSIS.value or stage == "result_analysis":
                self._enrich_for_result_analysis(result, parse_result)
            elif stage == EnrichStage.TRIGGER_ANALYSIS.value or stage == "trigger_analysis":
                self._enrich_for_trigger_analysis(result, trigger_type)
            else:
                logger.warning(f"[SemanticLayerService] enrich() 未知 stage: {stage}")

            return result

        except Exception as e:
            logger.error(f"[SemanticLayerService] enrich() 错误: {e}")
            return result

    def _enrich_for_intent_router(self, result: EnrichResult):
        """intent_router 阶段增强"""
        result.ranking_dimension_options = self._snap_service.list_dimension_options()

    def _enrich_for_mql_generation(self, result: EnrichResult):
        """mql_generation 阶段增强"""
        result.dimension_name_to_code_map = self._snap_service.get_dimension_name_to_code_map()
        result.business_term_maps = self._snap_service.get_business_term_maps()[0] if self._snap_service.get_business_term_maps() else None
        result.synonym_context = self._snap_service.get_dimension_synonym_context(limit=20)
        result.dimension_values_context = self._snap_service.get_dimension_values_context()
        result.level_keywords = self._snap_service.get_level_keywords()
        result.dimension_fallback_map = self._snap_service.get_dimension_fallback_map()

    def _enrich_for_validation(self, result: EnrichResult, parse_result: ParseResult):
        """validation 阶段增强"""
        if parse_result.metric_name:
            metric_info = self._snap_service.resolve_metric(parse_result.metric_name)
            if metric_info:
                result.starrocks_sql = metric_info.get("starrocks_sql")
                result.is_valid = True
            else:
                result.is_valid = False
                result.errors.append(f"指标 '{parse_result.metric_name}' 不存在")

    def _enrich_for_result_analysis(self, result: EnrichResult, parse_result: ParseResult):
        """result_analysis 阶段增强"""
        snapshot = self._snap_service.get_active_snapshot()
        if snapshot and parse_result.metric_code:
            capabilities = snapshot.get("capabilities", {})
            metric_cap = capabilities.get(parse_result.metric_code, {})
            result.metric_capability = metric_cap

    def _enrich_for_trigger_analysis(self, result: EnrichResult, trigger_type: Optional[str] = None):
        """trigger_analysis 阶段增强"""
        if trigger_type:
            result.scene_keywords = self._snap_service.get_scene_keywords(trigger_type)
            result.scene_drilldown_categories = self._snap_service.get_scene_drilldown_categories(trigger_type)

    def recommend(
        self,
        context: RecommendContext
    ) -> RecommendResult:
        """
        统一推荐入口

        Args:
            context: 推荐上下文，包含 stage、parse_result、data_result、trigger_type

        Returns:
            RecommendResult: 推荐结果
        """
        self._ensure_init()

        result = RecommendResult()

        try:
            if context.stage == "result_analysis":
                # 获取推荐问题
                if context.parse_result:
                    try:
                        from ai.engine.llm_v2.schema import MQLSchema
                        mql = MQLSchema()
                        if context.parse_result.metric_name:
                            mql.metric.name = context.parse_result.metric_name
                        if context.parse_result.metric_code:
                            mql.metric.code = context.parse_result.metric_code

                        scene_type = "simple_query"
                        suggestions = self._snap_service.recommend_next_questions(mql, scene_type)
                        result.next_questions.extend(suggestions)
                    except Exception as e:
                        logger.warning(f"[SemanticLayerService] recommend_next_questions 失败: {e}")

            elif context.stage == "trigger_analysis":
                # 获取推荐动作
                if context.trigger_type:
                    try:
                        actions = self._snap_service.recommend_actions(context.trigger_type)
                        result.actions.extend(actions)
                    except Exception as e:
                        logger.warning(f"[SemanticLayerService] recommend_actions 失败: {e}")

            return result

        except Exception as e:
            logger.error(f"[SemanticLayerService] recommend() 错误: {e}")
            return result


# ============== 单例模式 ==============

_semantic_layer_service: Optional[SemanticLayerService] = None


def get_semantic_layer_service() -> SemanticLayerService:
    """获取语义服务层单例"""
    global _semantic_layer_service
    if _semantic_layer_service is None:
        _semantic_layer_service = SemanticLayerService()
    return _semantic_layer_service
