"""
V2 LangGraph StateGraph 编排

实现 11 步闭环：
  intent_router → context_enhancer → mql_generator → mql_syntax_validator
      → mql_semantic_validator → sql_generator → sql_security_auditor
      → sql_executor → data_quality_checker → result_analyzer → state_manager

关键特性：
- 条件边分支（失败循环）
- Checkpoint 状态持久化
- 多轮对话状态管理
- 链路追踪（OpenTelemetry）
- 独立语义层支持（USE_SEMANTIC_LAYER=1 启用）
"""
import os
import time
import json
from typing import Dict, Any, Literal, Optional, Tuple
from datetime import datetime

from ai.config.logging_config import get_logger
from ai.config.runtime import get_go_api_base
from .schema import V2State, MQLSchema, MQLDimension, push_history, MQLIntent
from .observability import get_tracer, create_trace_context
from ai.client.metric_client import MetricClient
from ai.services.semantic_snapshot_service import get_semantic_snapshot_service

logger = get_logger("ai.llm_v2.graph")


def _extract_entities_from_mql(mql) -> list:
    """从 MQLSchema 提取实体列表，供 thinking_steps 展示"""
    entities = []
    if not mql:
        return entities
    # 指标实体
    if mql.metric and mql.metric.name:
        entities.append({"type": "METRIC", "text": mql.metric.name})
    # 时间实体
    if mql.time and mql.time.original:
        entities.append({"type": "TIME", "text": mql.time.original})
    # 维度实体
    for dim in (mql.dimensions or []):
        if dim.type:
            entities.append({"type": "DIMENSION", "text": dim.type})
    # 过滤器实体
    for f in (mql.filters or []):
        entities.append({"type": "FILTER", "text": f"{f.field} {f.operator} {f.value}"})
    return entities


async def _preload_metric_info(state: V2State) -> None:
    """
    预热指标信息查询链路。

    历史上这里会把结果写入 context_cache["metric_info_cache"]，但当前
    LLM.V2 链路里已经没有读者。保留这次查询仅用于兼容观察和日志，
    不再向状态里写入未使用缓存字段。
    """
    try:
        metric = state.inherited_mql.metric if state.inherited_mql else None
        if not metric or not metric.name:
            return

        client = MetricClient()
        # 通过名称查找，获取完整的 starrocks_sql 等信息
        metric_info = client.get_metric_by_name(metric.name)
        if metric_info:
            logger.info(f"[_preload_metric_info] 预加载指标: name={metric.name}, code={metric_info.get('metric_code')}")
    except Exception as e:
        logger.warning(f"[_preload_metric_info] 预加载失败: {e}")

async def intent_router(state: V2State):
    """
    步骤 1: 意图路由智能体
    - 识别用户意图（query_value / query_trend / query_comparison 等）
    - 判断是否需要追问

    这是一个 async generator，会 yield 多个中间状态来实现流式输出。
    """
    from .nodes.intent_router import IntentRouter

    start_time = time.time()
    state.current_step = "intent_router"

    # 先 yield 一个"开始理解意图"的状态
    state.add_thinking_step(
        "intent_router",
        status="in_progress",
        content="正在理解用户意图...",
        llm_used=False,
        duration_ms=0,
    )
    yield state

    # 链路追踪
    tracer = get_tracer()
    with tracer.start_span_context("intent_router") as span:
        span.set_attribute("question", state.question[:100])
        span.set_attribute("session_id", state.session_id)

        try:
            router = IntentRouter()
            # 检查是否启用独立语义层
            use_semantic_layer = os.getenv("USE_SEMANTIC_LAYER", "0") == "1"
            if use_semantic_layer:
                logger.info("[intent_router] ★★★ 启用独立语义层进行解析")
            result = await router.route(state.question, state.inherited_mql, use_semantic_layer=use_semantic_layer)

            # 空值保护：route() 不应返回 None，但加保护防止崩溃
            if result is None:
                logger.error("[intent_router] route() 返回 None，视为解析失败")
                state.error = "intent_router returned None"
                state.add_thinking_step(
                    "intent_router",
                    status="failed",
                    content="意图解析异常，请重试",
                    llm_used=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                yield state
                return

            # 更新状态
            if result.get("mql"):
                state.mql = result["mql"]
                span.set_attribute("mql.intent", result["mql"].intent.value)

            # 保存 source（followup / llm / local_model）用于后续节点判断
            if result.get("source"):
                state.source = result["source"]

            # 保存 drilldown_type（用于四类下钻）
            if result.get("drilldown_type"):
                state.context_cache.drilldown_type = result["drilldown_type"]
                logger.info(f"[intent_router] 保存 drilldown_type: {result['drilldown_type']}")

            # 处理泛指维度 vs 真正追问的区分
            if result.get("needs_clarification"):
                # 泛指维度 or 真正追问：都中断流程，返回追问让用户选择
                state.error = "needs_clarification"
                state.context_cache.clarification_message = result.get("clarification_message", "")
                state.context_cache.clarification_options = result.get("clarification_options", [])

                # 泛指维度：设置 is_generic_result 标记
                if result.get("is_generic"):
                    state.is_generic_result = True
                    logger.info(f"[intent_router] 泛指维度触发追问: is_generic=True, clarification_options={result.get('clarification_options', [])}")
                else:
                    logger.info(f"[intent_router] 追问触发: clarification_options={result.get('clarification_options', [])}")

                state.add_thinking_step(
                    "intent_router",
                    status="requires_clarification",
                    content=result.get("clarification_message", ""),
                    llm_used=True,
                    duration_ms=int((time.time() - start_time) * 1000),
                    source="llm",
                    entities=_extract_entities_from_mql(state.mql),
                    needs_clarification=True,
                    clarification_message=result.get("clarification_message", ""),
                    clarification_options=result.get("clarification_options", []),
                    original_question=result.get("original_question", ""),
                )
                span.set_attribute("result.type", "clarification_needed")
            else:
                # 寒暄：直接设置回答，跳过后续 SQL 链路
                if state.mql and state.mql.intent == MQLIntent.GREETING:
                    state.answer = '你好！我是智能问数助手，可以帮你查询业务指标数据。比如你可以问我：「近30天销售额是多少」、「各SKU利润排名」等。'
                    logger.info("[intent_router] 寒暄意图，跳过后续节点")
                state.add_thinking_step(
                    "intent_router",
                    status="completed",
                    content=f"意图: {state.mql.intent.value if state.mql else 'unknown'}",
                    llm_used=True,
                    duration_ms=int((time.time() - start_time) * 1000),
                    source=result.get("source"),
                    entities=_extract_entities_from_mql(state.mql),
                )
                span.set_attribute("result.type", "completed")

        except Exception as e:
            logger.error(f"[intent_router] 错误: {e}")
            state.error = str(e)
            span.set_status("error", str(e))
            state.add_thinking_step(
                "intent_router",
                status="failed",
                content=f"错误: {str(e)}",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    yield state


async def context_enhancer(state: V2State) -> V2State:
    """
    步骤 2: 上下文增强节点（RAG）
    - 从历史查询中检索相似案例
    - 增强当前查询上下文
    """
    from .nodes.context_enhancer import ContextEnhancer

    start_time = time.time()
    state.current_step ="context_enhancer"

    try:
        enhancer = ContextEnhancer()

        # 如果有继承的 MQL，合并上下文
        if state.inherited_mql:
            context = {
                "metric": state.inherited_mql.metric,
                "time": state.inherited_mql.time,
                "dimensions": state.inherited_mql.dimensions,
            }
        else:
            context = {}

        # RAG 检索
        rag_result = await enhancer.enhance(state.question, context)

        # 更新上下文缓存
        if rag_result.get("similar_cases"):
            state.context_cache.similar_cases = rag_result["similar_cases"]

        # RAG 模板复用标记（>0.90 相似度时跳过 mql_generator）
        if rag_result.get("direct_reuse"):
            state.context_cache["direct_reuse"] = True
            state.context_cache["suggested_mql"] = rag_result.get("suggested_mql")
            state.context_cache["suggested_sql"] = rag_result.get("suggested_sql")

        # 预加载 metric_info（优化：提前调用 MetricClient，后续节点可复用缓存）
        await _preload_metric_info(state)

        state.add_thinking_step(
            "context_enhancer",
            status="completed",
            content=f"检索到 {len(rag_result.get('similar_cases', []))} 个相似案例",
            llm_used=False,  # RAG 不走 LLM
            duration_ms=int((time.time() - start_time) * 1000),
        )

    except Exception as e:
        logger.error(f"[context_enhancer] 错误: {e}")
        state.error =str(e)
        state.add_thinking_step(
            "context_enhancer",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def mql_generator(state: V2State) -> V2State:
    """
    步骤 3: MQL 生成智能体
    - 将自然语言转换为 MQL
    """
    from .nodes.mql_generator import MQLGenerator

    start_time = time.time()
    state.current_step ="mql_generator"

    try:
        generator = MQLGenerator()

        # RAG 模板复用：>0.90 相似度时直接复用历史 MQL，跳过 LLM
        if state.context_cache and state.context_cache.get("direct_reuse"):
            suggested_mql = state.context_cache.get("suggested_mql")
            if suggested_mql:
                state.mql = suggested_mql
                state.source = "rag_reuse"
                push_history(state, json.dumps(suggested_mql.to_dict(), ensure_ascii=False))
                state.add_thinking_step(
                    "mql_generator",
                    status="completed",
                    content=f"RAG 模板复用: intent={suggested_mql.intent.value}",
                    llm_used=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                    source="rag_reuse",
                    entities=_extract_entities_from_mql(suggested_mql),
                )
                logger.info("[mql_generator] RAG 模板复用，跳过 LLM 生成")
                return state

        # 获取 RAG 上下文
        rag_context = state.context_cache.similar_cases or []

        # 当 intent_router 已经构建出可直接使用的 MQL 时，传入该结果跳过 LLM 调用
        source = getattr(state, 'source', '')
        logger.info(f"[mql_generator] state.source={source!r}, state.mql.metric.name={state.mql.metric.name if state.mql and state.mql.metric else None}, state.mql.metrics count={len(state.mql.metrics) if state.mql and state.mql.metrics else 0}, state.mql.metrics={[(m.name, m.code) for m in (state.mql.metrics or [])] if state.mql and state.mql.metrics else []}")
        intent_router_mql = state.mql if source in (
            'local_model',
            'semantic_layer',  # 语义层已解析，直接使用
            'drilldown',
            'followup',
            'followup_add_metric',
            'followup_add_dimension',
            'followup_remove_metric',
            'followup_remove_dimension',
            'followup_replace_metric',
            'followup_comp',
            'followup_time',
            'followup_reset',
            'followup_correction',  # 纠错追问
            'rag_reuse',  # RAG 模板复用
        ) else None

        # 生成 MQL
        mql = await generator.generate(
            question=state.question,
            rag_context=rag_context,
            inherited_mql=state.inherited_mql,
            intent_router_mql=intent_router_mql,
        )

        # 保存到历史栈
        if mql:
            # 保留 intent_router 设置的 order_by（mql_generator 可能没有设置）
            inherited_order_by = state.mql.order_by if state.mql else None
            # 保留 intent_router 设置的 dimensions（mql_generator 的 LLM 可能丢失维度信息）
            inherited_dimensions = state.mql.dimensions if state.mql and state.mql.dimensions else []
            # 保留 intent_router 设置的 filters（mql_generator 的 LLM 可能丢失 filters）
            inherited_filters = state.mql.filters if state.mql and state.mql.filters else []
            # 保留 intent_router 设置的 comparison（追问场景：环比/同比）
            inherited_comparison = state.mql.comparison if state.mql and state.mql.comparison else None
            # 保留 intent_router 设置的 calculation_patterns
            inherited_calculation_patterns = state.mql.calculation_patterns if state.mql and state.mql.calculation_patterns else []
            # 保留 intent_router 设置的 time（追问场景：时间范围必须继承）
            inherited_time = state.mql.time if state.mql and state.mql.time else None
            logger.info(f"[mql_generator] 保存继承状态: inherited_comparison={inherited_comparison}, inherited_time={inherited_time}, inherited_dimensions={[(d.type, d.value) for d in inherited_dimensions] if inherited_dimensions else []}, is_followup={getattr(state, 'source', '')}")
            state.mql = mql
            if inherited_order_by and not mql.order_by:
                mql.order_by = inherited_order_by
                logger.info(f"[mql_generator] 保留 intent_router 设置的 order_by: {inherited_order_by.direction}")
            # ========== 修复：只有当前问题包含维度关键词时才继承上轮维度 ==========
            # 如果当前问题没有提到任何维度关键词，即使新 MQL 无维度也不继承
            # 但是：如果是追问（source=followup），必须继承维度
            try:
                from ai.services.dimension_service import DimensionService
                dim_keywords = DimensionService().get_keywords()
            except Exception:
                dim_keywords = ["品类", "渠道", "店铺", "国家", "平台", "区域", "城市", "品牌", "商品",
                                "区域", "国家", "站点", "店铺", "广告", "活动", "客户"]
            current_has_dim_keyword = any(kw in state.question for kw in dim_keywords)
            # 检查继承的 dimension value 是否出现在当前问题中
            inherited_dim_value_in_question = any(
                dim.value and dim.value in state.question
                for dim in inherited_dimensions
            )
            # 追问场景（source=followup）：始终保留维度，不走下面的清除逻辑
            is_followup = getattr(state, 'source', '') == 'followup'
            if not mql.dimensions and inherited_dimensions and not current_has_dim_keyword and not inherited_dim_value_in_question and not is_followup:
                logger.warning(f"[mql_generator] 当前问题无维度关键词，清除继承的 dimensions: {[d.type for d in inherited_dimensions]}")
                inherited_dimensions = []
            # =========================================================================
            if not mql.dimensions and inherited_dimensions:
                mql.dimensions = inherited_dimensions
                logger.info(f"[mql_generator] 保留 intent_router 设置的 dimensions: {[d.type for d in inherited_dimensions]}")
            # 保留 intent_router 设置的 filters（去重）
            # 规则：field AND value 同时匹配才算重复
            # 如果 corrected 和 user 重复，移除 corrected（优先保留 user）
            for f in inherited_filters:
                # 如果 corrected 和 user 重复，移除 corrected filter
                if hasattr(f, 'source') and f.source == "user":
                    # 移除已存在的 corrected filter（同 field）
                    mql.filters = [
                        ex for ex in mql.filters
                        if not (hasattr(ex, 'field') and ex.field == f.field and
                                hasattr(ex, 'source') and ex.source == "corrected")
                    ]
                    logger.info(f"[mql_generator] 移除与 user filter 重复的 corrected filter: {f.field}")
                already_exists = any(
                    (hasattr(ex, 'field') and ex.field == f.field and hasattr(ex, 'value') and ex.value == f.value)
                    for ex in (mql.filters or [])
                )
                if not already_exists:
                    mql.filters.append(f)
                    logger.info(f"[mql_generator] 保留 intent_router 设置的 filter: {f.field}={f.value}")
            # 保留 intent_router 设置的 comparison（追问场景）
            # 如果是追问(source=followup)，强制恢复 comparison（因为 LLM 对短文本可能不返回 comparison）
            is_followup = getattr(state, 'source', '') == 'followup'
            logger.info(f"[mql_generator] 恢复 comparison: inherited_comparison={inherited_comparison}, mql.comparison={mql.comparison}, is_followup={is_followup}")
            if is_followup and inherited_comparison:
                # 追问场景：强制恢复
                mql.comparison = inherited_comparison
                logger.info(f"[mql_generator] 追问场景恢复 comparison from intent_router: types={inherited_comparison.types}, enabled={inherited_comparison.enabled}")
            elif inherited_comparison and not mql.comparison:
                # 非追问场景：只有新 MQL 没有 comparison 时才恢复
                mql.comparison = inherited_comparison
                logger.info(f"[mql_generator] 恢复 comparison from intent_router: types={inherited_comparison.types}, enabled={inherited_comparison.enabled}")
            # 保留继承的时间范围（追问场景：时间范围必须继承，否则分析 SQL 无法生成）
            # 注意：mql.time 可能存在但 start/end 为空，需要检查 start 是否有效
            mql_time_invalid = not mql.time or not (mql.time.start or mql.time.end)
            if inherited_time and mql_time_invalid:
                mql.time = inherited_time
                logger.info(f"[mql_generator] 恢复 inherited_time: {inherited_time.start} ~ {inherited_time.end}")
            # 如果有 comparison 但没有 calculation_patterns，根据 comparison.types 转换
            if mql.comparison and mql.comparison.enabled and not mql.calculation_patterns:
                from .schema import CalculationPattern
                for ctype in (mql.comparison.types or []):
                    if ctype in ["同比", "yoy"]:
                        mql.calculation_patterns.append(CalculationPattern.YOY)
                        logger.info(f"[mql_generator] 从 comparison.types 转换 YOY: calculation_patterns={mql.calculation_patterns}")
                    elif ctype in ["环比", "mom"]:
                        mql.calculation_patterns.append(CalculationPattern.MOM)
                        logger.info(f"[mql_generator] 从 comparison.types 转换 MOM: calculation_patterns={mql.calculation_patterns}")
            push_history(state, json.dumps(mql.to_dict(), ensure_ascii=False))

        state.add_thinking_step(
            "mql_generator",
            status="completed",
            content=f"MQL 生成成功: intent={mql.intent.value if mql else 'unknown'}",
            llm_used=True,
            duration_ms=int((time.time() - start_time) * 1000),
            source="llm",
            entities=_extract_entities_from_mql(mql),
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[mql_generator] 错误: {e}\n{tb}")
        state.error =str(e)
        state.add_thinking_step(
            "mql_generator",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=True,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def mql_syntax_validator(state: V2State) -> V2State:
    """
    步骤 4: MQL 语法验证
    - 验证 MQL JSON Schema 合法性
    """
    from .nodes.mql_validator import MQLSyntaxValidator

    start_time = time.time()
    state.current_step ="mql_syntax_validator"

    try:
        validator = MQLSyntaxValidator()
        is_valid, error_msg = validator.validate_syntax(state.mql)

        if not is_valid:
            state.error =f"mql_syntax_error: {error_msg}"
            state.retry_count +=1

            state.add_thinking_step(
                "mql_syntax_validator",
                status="failed",
                content=f"语法错误: {error_msg}",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        else:
            state.add_thinking_step(
                "mql_syntax_validator",
                status="completed",
                content="MQL 语法验证通过",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    except Exception as e:
        logger.error(f"[mql_syntax_validator] 错误: {e}")
        state.error =f"mql_syntax_error: {str(e)}"
        state.retry_count +=1
        state.add_thinking_step(
            "mql_syntax_validator",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def mql_semantic_validator(state: V2State) -> V2State:
    """
    步骤 5: MQL 语义验证
    - 验证指标、维度、时间等是否有效
    """
    from .nodes.mql_validator import MQLSemanticValidator

    start_time = time.time()
    state.current_step ="mql_semantic_validator"

    try:
        validator = MQLSemanticValidator()
        is_valid, error_msg = await validator.validate_semantic(state.mql)

        if not is_valid:
            state.error =f"mql_semantic_error: {error_msg}"
            state.retry_count +=1

            state.add_thinking_step(
                "mql_semantic_validator",
                status="failed",
                content=f"语义错误: {error_msg}",
                llm_used=True,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        else:
            state.add_thinking_step(
                "mql_semantic_validator",
                status="completed",
                content="MQL 语义验证通过",
                llm_used=True,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    except Exception as e:
        logger.error(f"[mql_semantic_validator] 错误: {e}")
        state.error =f"mql_semantic_error: {str(e)}"
        state.retry_count +=1
        state.add_thinking_step(
            "mql_semantic_validator",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=True,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def slot_clarifier(state: V2State) -> V2State:
    """
    步骤 5.5: 槽位消解
    - 检测 MQL 中缺失的必要槽位（指标、时间、维度）
    - 生成追问消息和选项
    """
    from .nodes.slot_clarifier import SlotClarifier

    start_time = time.time()
    state.current_step = "slot_clarifier"

    try:
        clarifier = SlotClarifier()
        result = clarifier.check(state.mql)

        needs_clarification = False
        clarification_message = ""
        clarification_options = []

        if result and result.get("needs_clarification"):
            state.needs_clarification = True
            state.clarification_message = result["message"]
            state.clarification_options = result.get("options", [])
            needs_clarification = True
            clarification_message = result["message"]
            clarification_options = result.get("options", [])
            logger.info(f"[slot_clarifier] 追问: {result['message']}, missing={result.get('missing_slots')}")

        state.add_thinking_step(
            "slot_clarifier",
            status="completed",
            content=f"槽位检查: {'需要追问' if result else '完整'}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
            needs_clarification=needs_clarification,
            clarification_message=clarification_message,
            clarification_options=clarification_options,
        )
    except Exception as e:
        logger.warning(f"[slot_clarifier] 槽位检查失败(非阻断): {e}")

    return state


async def sql_generator(state: V2State) -> V2State:
    """
    步骤 6: SQL 生成节点
    - 将 MQL 转换为 SQL
    """
    from .nodes.sql_generator import SQLGeneratorNode

    start_time = time.time()
    state.current_step ="sql_generator"

    try:
        generator = SQLGeneratorNode()
        logger.info(f"[sql_generator] cross_metric: {state.mql.cross_metric if state.mql else None}")
        logger.info(f"[sql_generator] mql.metric: {state.mql.metric.name if state.mql and state.mql.metric else None}")
        sql_result = await generator.generate(state.mql)

        state.sql =sql_result.get("sql", "")
        state.sql_result =sql_result.get("sql_result")

        state.add_thinking_step(
            "sql_generator",
            status="completed",
            content=f"SQL 生成成功: {state.sql[:100]}..." if len(state.sql) > 100 else f"SQL 生成成功: {state.sql}",
            llm_used=False,  # SQL 生成走确定性规则
            duration_ms=int((time.time() - start_time) * 1000),
        )

    except Exception as e:
        logger.error(f"[sql_generator] 错误: {e}")
        state.error =f"sql_generation_error: {str(e)}"
        state.add_thinking_step(
            "sql_generator",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def sql_security_auditor(state: V2State) -> V2State:
    """
    步骤 7: SQL 安全审计
    - 检查 SQL 是否有危险操作
    """
    from .nodes.sql_auditor import SQLSecurityAuditor

    start_time = time.time()
    state.current_step ="sql_security_auditor"

    try:
        auditor = SQLSecurityAuditor()
        is_safe, error_msg = auditor.audit(state.sql)

        if not is_safe:
            state.error =f"sql_security_error: {error_msg}"
            state.add_thinking_step(
                "sql_security_auditor",
                status="failed",
                content=f"安全审计失败: {error_msg}",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            # 步骤 7 失败 → 直接拒绝
            return state
        else:
            state.add_thinking_step(
                "sql_security_auditor",
                status="completed",
                content="SQL 安全审计通过",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    except Exception as e:
        logger.error(f"[sql_security_auditor] 错误: {e}")
        state.error =f"sql_security_error: {str(e)}"
        state.add_thinking_step(
            "sql_security_auditor",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def sql_executor(state: V2State) -> V2State:
    """
    步骤 8: SQL 执行节点
    - 执行 SQL 查询
    """
    from .nodes.sql_executor import SQLExecutor

    start_time = time.time()
    state.current_step ="sql_executor"

    try:
        executor = SQLExecutor()
        result = await executor.execute(state.sql, state.mql)

        state.sql_result =result

        duration = int((time.time() - start_time) * 1000)
        if result.is_success():
            state.add_thinking_step(
                "sql_executor",
                status="completed",
                content=f"SQL 执行成功，返回 {len(result.data)} 条数据，耗时 {duration}ms",
                llm_used=False,
                duration_ms=duration,
            )
        else:
            state.error =f"sql_execution_error: {result.error}"
            state.add_thinking_step(
                "sql_executor",
                status="failed",
                content=f"SQL 执行失败: {result.error}",
                llm_used=False,
                duration_ms=duration,
            )

    except Exception as e:
        logger.error(f"[sql_executor] 错误: {e}")
        state.error =f"sql_execution_error: {str(e)}"
        state.add_thinking_step(
            "sql_executor",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def data_quality_checker(state: V2State) -> V2State:
    """
    步骤 9: 数据质量检查
    - 检查查询结果是否为空、异常值等
    """
    from .nodes.quality_checker import DataQualityChecker

    start_time = time.time()
    state.current_step ="data_quality_checker"

    try:
        checker = DataQualityChecker()
        is_valid, warnings = checker.check(state.sql_result)

        if not is_valid:
            state.error ="data_quality_error"
            state.retry_count +=1

            state.add_thinking_step(
                "data_quality_checker",
                status="failed",
                content=f"数据质量问题: {', '.join(warnings)}",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        else:
            if warnings:
                logger.warning(f"[data_quality_checker] 数据质量警告: {warnings}")

            state.add_thinking_step(
                "data_quality_checker",
                status="completed",
                content="数据质量检查通过" if not warnings else f"数据质量警告: {', '.join(warnings)}",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    except Exception as e:
        logger.error(f"[data_quality_checker] 错误: {e}")
        state.error =f"data_quality_error: {str(e)}"
        state.retry_count +=1
        state.add_thinking_step(
            "data_quality_checker",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


def _calc_previous_period(mql) -> tuple:
    """根据 MQL time 计算上一期的开始/结束日期

    支持：
    - 季度：Q1 2026 (2026-01-01~2026-03-31) → Q4 2025 (2025-10-01~2025-12-31)
    - 月份：2026-01 (2026-01-01~2026-01-31) → 2025-12 (2025-12-01~2025-12-31)
    - 年份：2026 → 2025
    """
    if not mql or not mql.time:
        return None, None

    t = mql.time
    start_str = t.start or ""
    end_str = t.end or ""

    import re
    from datetime import datetime, timedelta
    import calendar

    month_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", start_str)
    if not month_match:
        return None, None

    year = int(month_match.group(1))
    month = int(month_match.group(2))
    day = int(month_match.group(3))

    # 季度判断：day=1 且月份是 1/4/7/10
    if day == 1 and month in [1, 4, 7, 10]:
        # 季度 → 上一季度（Q1→Q4上年, Q2→Q1, Q3→Q2, Q4→Q3）
        quarter_to_prev = {
            1: (year - 1, 10, 1, 12, 31),   # Q1 → Q4 of prev year (Oct1-Dec31)
            4: (year, 1, 1, 3, 31),          # Q2 → Q1 (Jan1-Mar31)
            7: (year, 4, 1, 6, 30),          # Q3 → Q2 (Apr1-Jun30)
            10: (year, 7, 1, 9, 30),         # Q4 → Q3 (Jul1-Sep30)
        }
        if month in quarter_to_prev:
            py, pm, pd, qe_month, qe_day = quarter_to_prev[month]
            prev_start = f"{py}-{pm:02d}-{pd:02d}"
            prev_end = f"{py}-{qe_month:02d}-{qe_day:02d}"
            logger.info(f"[_calc_previous_period] 季度 {year}-Q{(month-1)//3+1 if month != 1 else 4} → prev {prev_start}~{prev_end}")
            return prev_start, prev_end

    # 月份判断：start 是月首
    if day == 1:
        max_day = calendar.monthrange(year, month)[1]
        if end_str == f"{year}-{month:02d}-{max_day:02d}":
            # 完整月 → 上一完整月
            if month == 1:
                prev_year, prev_month = year - 1, 12
            else:
                prev_year, prev_month = year, month - 1
            prev_max_day = calendar.monthrange(prev_year, prev_month)[1]
            prev_start = f"{prev_year}-{prev_month:02d}-01"
            prev_end = f"{prev_year}-{prev_month:02d}-{prev_max_day:02d}"
            logger.info(f"[_calc_previous_period] 完整月 {year}-{month:02d} → {prev_year}-{prev_month:02d}")
            return prev_start, prev_end

        # partial month（当月未结束，如 4月1-26）：对齐到上月同期同天数
        # 例如 4月1-26 vs 3月1-26，保证口径一致
        current_max_day = calendar.monthrange(year, month)[1]
        is_partial = end_str != f"{year}-{month:02d}-{current_max_day:02d}"
        if is_partial:
            # 提取 end 的 day 作为对比基准
            end_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", end_str)
            if end_match:
                end_day = int(end_match.group(3))
                if month == 1:
                    prev_year, prev_month = year - 1, 12
                else:
                    prev_year, prev_month = year, month - 1
                prev_max_day = calendar.monthrange(prev_year, prev_month)[1]
                prev_start = f"{prev_year}-{prev_month:02d}-01"
                prev_end = f"{prev_year}-{prev_month:02d}-{min(end_day, prev_max_day):02d}"
                logger.info(f"[_calc_previous_period] partial月 {year}-{month:02d}(day={end_day}) → {prev_year}-{prev_month:02d}(day={min(end_day, prev_max_day)})")
                return prev_start, prev_end

    # 跨月/跨年范围判断：如果 start 和 end 不是同一月份/年份，说明是跨期范围
    # 例如 2026-01-01~2026-04-27 → 2025-09-05~2025-12-31（按相同天数往前推）
    if year and start_str and end_str:
        end_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", end_str)
        if end_match:
            end_year = int(end_match.group(1))
            end_month = int(end_match.group(2))
            end_day = int(end_match.group(3))
            # 如果 start 和 end 不是同一月份（跨月范围），按相同天数往前推
            if year != end_month or day != 1 or end_day != calendar.monthrange(end_year, end_month)[1]:
                # 计算时间跨度天数
                start_dt = datetime(year, month, day)
                end_dt = datetime(end_year, end_month, end_day)
                days_diff = (end_dt - start_dt).days
                # 按相同天数往前推
                prev_start_dt = start_dt - timedelta(days=days_diff)
                prev_end_dt = end_dt - timedelta(days=days_diff)
                prev_start = prev_start_dt.strftime("%Y-%m-%d")
                prev_end = prev_end_dt.strftime("%Y-%m-%d")
                logger.info(f"[_calc_previous_period] 跨期范围 {year}-{month:02d}~{end_year}-{end_month:02d} (days={days_diff}) → {prev_start}~{prev_end}")
                return prev_start, prev_end

    return None, None


async def trigger_analyzer(state: V2State) -> V2State:
    """
    步骤 10: 触发分析智能体
    - 检查是否需要触发分析
    - 生成 AnalysisOutput
    """
    from .nodes.trigger_analyzer import TriggerAnalyzer, TriggerResult, AnalysisOutput

    start_time = time.time()
    state.current_step = "trigger_analyzer"

    try:
        analyzer = TriggerAnalyzer()

        logger.info(f"[trigger_analyzer] ENTRY: sql_result={'exists' if state.sql_result else 'None'}, data={'exists' if state.sql_result and state.sql_result.data else 'None'}")

        # 构建 result dict（从 sql_result 提取）
        result_dict = {
            "data": state.sql_result.data if state.sql_result else [],
            "mom_change": None,  # None = 没有 MoM 数据
            "yoy_change": None,  # None = 没有 YoY 数据
            "current_value": 0,
        }

        # 尝试从数据中提取 mom/yoy（支持多种字段名）
        if state.sql_result and state.sql_result.data:
            first_row = state.sql_result.data[0]
            logger.info(f"[trigger_analyzer] first_row keys: {list(first_row.keys())}")
            # mom_change: 优先使用 mom_change（MoM SQL 才会有），不接受 change_rate
            mom_val = first_row.get("mom_change") or first_row.get("环比变化") or first_row.get("环比")
            if mom_val is not None:
                try:
                    # 处理百分比字符串（如 "-17.01%" 或 "17.01%"）
                    mom_str = str(mom_val).replace("%", "").replace(",", "")
                    result_dict["mom_change"] = float(mom_str)
                except (ValueError, TypeError):
                    result_dict["mom_change"] = float(mom_val or 0)
            # yoy_change: 优先 yoy_change，其次 change_rate（YoY SQL 返回的字段名）
            yoy_val = first_row.get("yoy_change") or first_row.get("change_rate") or first_row.get("同比变化") or first_row.get("同比")
            if yoy_val is not None:
                try:
                    yoy_str = str(yoy_val).replace("%", "").replace(",", "")
                    result_dict["yoy_change"] = float(yoy_str)
                except (ValueError, TypeError):
                    result_dict["yoy_change"] = float(yoy_val or 0)
            # current_value: 优先使用 current_val（SQL 别名），然后是 value
            if "current_val" in first_row:
                result_dict["current_value"] = float(first_row.get("current_val") or 0)
            elif "value" in first_row:
                result_dict["current_value"] = float(first_row.get("value") or 0)

        logger.info(f"[trigger_analyzer] result_dict: mom_change={result_dict['mom_change']}, yoy_change={result_dict['yoy_change']}, current_value={result_dict['current_value']}")

        # 如果有 YoY 数据但没有 MoM 数据，自动查环比（上一期）
        # 条件：用户明确要环比（mql.has_mom）且当前期有有效数据（current_value > 0）
        if (result_dict["mom_change"] is None
                and result_dict["current_value"] > 0 and (state.mql.has_mom if state.mql else False)):
            # MoM 计算：查询上一期并计算变化率（仅在当前期有有效数据时）
            try:
                prev_start, prev_end = _calc_previous_period(state.mql)
                if prev_start and prev_end:
                    starrocks_sql = (state.mql.metric.starrocks_sql or "") if state.mql and state.mql.metric else ""
                    import re
                    sum_match = re.search(r"SUM\s*\(\s*([A-Z_]+)\s*\)", starrocks_sql or "", re.IGNORECASE)
                    if sum_match:
                        metric_field = sum_match.group(1)
                        table_match = re.search(r"FROM\s+([a-zA-Z0-9_\.]+)", starrocks_sql, re.IGNORECASE)
                        table_name = table_match.group(1) if table_match else "ids.IDS_AMZ_COMPREHENSIVE_DI"
                        dim_filters = []
                        if state.mql and state.mql.dimensions:
                            for dim in state.mql.dimensions:
                                if dim.column and dim.value:
                                    dim_filters.append(f"{dim.column} = '{dim.value}'")
                        where_parts = [f"FDATE >= '{prev_start}'", f"FDATE <= '{prev_end}'"]
                        where_parts.extend(dim_filters)
                        where_clause = " AND ".join(where_parts)
                        prev_sql = f"SELECT SUM({metric_field}) AS prev_val FROM {table_name} WHERE {where_clause}"
                        import httpx
                        async with httpx.AsyncClient(timeout=30) as client:
                            resp = await client.post(
                                f"{get_go_api_base()}/api/v1/query/execute",
                                json={"sql": prev_sql, "timeout": 30},
                            )
                            data = resp.json()
                            if data.get("code") == 0 and data.get("data"):
                                inner_data = data["data"]
                                rows = inner_data.get("data") if isinstance(inner_data, dict) else inner_data
                                if rows and len(rows) > 0:
                                    prev_val = float(rows[0].get("prev_val") or rows[0].get("SUM(ORDERED_PRODUCTSALES)") or 0)
                                    if prev_val > 0:
                                        mom = (result_dict["current_value"] - prev_val) / prev_val * 100
                                        result_dict["mom_change"] = round(mom, 2)
                                        logger.info(f"[trigger_analyzer] MoM 计算成功: current={result_dict['current_value']}, prev={prev_val}, mom={result_dict['mom_change']}%")
            except Exception as e:
                logger.warning(f"[trigger_analyzer] 计算MoM失败: {e}")
        else:
            logger.info(f"[trigger_analyzer] 跳过 MoM 计算: mom_change={result_dict['mom_change']}, current={result_dict['current_value']}, has_mom={state.mql.has_mom if state.mql else False}")

        # P0-3 fix: 设置 session_state 用于 ContextTrigger
        if state.mql and state.mql.metric:
            state.session_state = {
                "last_query_type": "metric",
                "last_metric": state.mql.metric.name if hasattr(state.mql.metric, 'name') else None,
                "last_metric_code": state.mql.metric.code if hasattr(state.mql.metric, 'code') else None,
                "last_time": state.mql.time.original if state.mql.time and hasattr(state.mql.time, 'original') else None,
                "last_dimensions": [d.type for d in state.mql.dimensions] if state.mql.dimensions else [],
            }

        # 获取会话状态（用于 ContextTrigger）
        session_state = state.session_state if state.session_state else {}
        # 确保 state.session_state 被初始化（否则修改 local session_state 不会影响原始对象）
        if not state.session_state:
            state.session_state = session_state

        # 注入 metric_capability + mql_slots 到 session_state（语义快照驱动分析）
        snapshot = state._snapshot or {}
        metric_code = state.mql.metric.code if (state.mql and state.mql.metric) else ""
        # 如果 metric_code 为空，尝试通过 MetricClient 按 name 查找
        if not metric_code and state.mql and state.mql.metric and state.mql.metric.name:
            from ai.client.metric_client import MetricClient
            mc = MetricClient()
            info = mc.get_metric_by_name(state.mql.metric.name)
            if info:
                metric_code = info.get("metric_code", "")
        if metric_code:
            snap_svc = get_semantic_snapshot_service()
            cap = snap_svc.get_metric_capability(snapshot, metric_code)
            session_state["metric_capability"] = cap

        # MQL 槽位（供 trigger_analyzer 生成分析 SQL）
        if state.mql:
            mql_slots = {
                "time": {
                    "start": state.mql.time.start if state.mql.time else None,
                    "end": state.mql.time.end if state.mql.time else None,
                },
                "dimensions": [
                    {"type": d.type, "value": d.value, "column": d.column}
                    for d in state.mql.dimensions
                ] if state.mql.dimensions else [],
                "filters": [
                    {"field": f.field, "op": f.operator.value if hasattr(f.operator, 'value') else str(f.operator), "value": f.value}
                    for f in state.mql.filters
                ] if state.mql.filters else [],
            }
            session_state["mql_slots"] = mql_slots

        # 传递 drilldown_type 到 trigger_analyzer
        drilldown_type = state.context_cache.drilldown_type
        if drilldown_type:
            session_state["drilldown_type"] = drilldown_type
            state.session_state = session_state
            # 设置多指标模式标记，用于后续 ReportGeneratorNode 调用
            state.multi_metric_mode = True
            state.drilldown_category = drilldown_type
            logger.info(f"[trigger_analyzer] 多指标下钻模式: category={drilldown_type}")

        # ============================================================
        # 多指标下钻模式：调用 ReportGeneratorNode 生成分析报告
        # ============================================================
        drilldown_category = state.drilldown_category
        if state.multi_metric_mode:
            from .nodes.report_generator import ReportGeneratorNode
            try:
                report_gen = ReportGeneratorNode()

                # 1. 执行该 category 下所有模板，合并结果
                merged_data = await report_gen.execute_all_templates(
                    category=drilldown_category,
                    time_range={
                        "start": state.mql.time.start if state.mql and state.mql.time else "",
                        "end": state.mql.time.end if state.mql and state.mql.time else "",
                    },
                    inherited_mql=state.inherited_mql,
                )

                # 检查是否有有意义的维度数据
                dim_data = merged_data.get("dimensional_data", {})
                has_meaningful_dim_data = any(
                    dim_data.get(key) for key in ["by_site", "by_category", "by_platform", "by_asin"]
                )
                scalar_metrics = merged_data.get("scalar_metrics", {})

                if not merged_data or (not has_meaningful_dim_data and not scalar_metrics):
                    # 没有获取到有意义的分析数据，不调用 LLM 生成报告（避免幻觉）
                    logger.warning(f"[trigger_analyzer] 多指标下钻模式: 未获取到有意义的数据，跳过综合分析")
                    state.analysis = None
                    state.multi_metric_data = []
                    state.dimensional_data = {}
                    # ✶ 修复：仍然设置 category，让前端能显示下钻按钮
                    state.category = drilldown_category or ""
                else:
                    # 2. LLM 生成分析报告
                    analysis = await report_gen.generate_analysis(
                        multi_metric_data=merged_data,
                        category=drilldown_category,
                        time_range={
                            "start": state.mql.time.start if state.mql and state.mql.time else "",
                            "end": state.mql.time.end if state.mql and state.mql.time else "",
                        }
                    )

                    # 3. 格式化多指标数据
                    multi_metric_data = report_gen.format_multi_metric_data(merged_data)
                    dimensional_data = report_gen.get_dimensional_data(merged_data)

                    state.analysis = analysis
                    state.multi_metric_data = multi_metric_data
                    state.dimensional_data = dimensional_data
                    state.category = drilldown_category

                    logger.info(
                        f"[trigger_analyzer] 多指标下钻分析完成: "
                        f"category={state.category}, "
                        f"metrics={len(multi_metric_data)}, "
                        f"issues={len(analysis.get('issues', []))}"
                    )

                state.add_thinking_step(
                    "trigger_analyzer",
                    status="completed",
                    content=f"多指标下钻分析: {drilldown_category}",
                    llm_used=True,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                return state

            except Exception as e:
                import traceback
                logger.error(f"[trigger_analyzer] 多指标下钻分析失败: {e}")
                logger.error(f"[trigger_analyzer] 堆栈: {traceback.format_exc()}")
                state.analysis = None
                state.multi_metric_data = []
                state.dimensional_data = {}
                state.category = drilldown_category
                state.add_thinking_step(
                    "trigger_analyzer",
                    status="completed",
                    content=f"多指标下钻分析失败: {str(e)}",
                    llm_used=True,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                return state

        # ============================================================
        # 普通触发分析模式
        # ============================================================

        # 检查触发器
        try:
            trigger_result = await analyzer.check_triggers(
                mql=state.mql,
                result=result_dict,
                state=session_state
            )
        except Exception as call_e:
            import traceback
            logger.error(f"[trigger_analyzer] check_triggers 直接异常: {call_e}")
            logger.error(f"[trigger_analyzer] 堆栈: {traceback.format_exc()}")
            raise  # 重新抛出，不吞掉

        if trigger_result.should_analyze:
            # 生成 AnalysisOutput
            try:
                analysis_output = await analyzer.generate_output(
                    trigger_result=trigger_result,
                    mql=state.mql,
                    result=result_dict
                )
                state.analysis = analysis_output.to_dict()
                state.one_sentence_summary = analysis_output.summary or ""
                parts = [analysis_output.summary] if analysis_output.summary else []
                for b in (analysis_output.breakdown or [])[:3]:
                    dim_name = b.get("dimension", "")
                    impact = b.get("impact", "")
                    if dim_name:
                        parts.append(f"{dim_name}：{impact}" if impact else dim_name)
                state.analysis_summary = "；".join(parts)

                if trigger_result.drilldown_options:
                    first_option = trigger_result.drilldown_options[0]
                    params = first_option.get("params", {})
                    if "check" in params:
                        state.category = params["check"]

            except Exception as e:
                import traceback
                logger.error(f"[trigger_analyzer] 生成分析输出失败: {e}")
                logger.error(f"[trigger_analyzer] 堆栈: {traceback.format_exc()}")
                state.analysis = None

            state.add_thinking_step(
                "trigger_analyzer",
                status="completed",
                content=f"触发分析: {trigger_result.trigger_type.value if trigger_result.trigger_type else 'unknown'} - {trigger_result.trigger_reason}",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            logger.info(f"[trigger_analyzer] 触发分析命中: {trigger_result.trigger_type}")
        else:
            state.analysis = None
            # 即使 should_analyze=False，如果 analysis_data 有有效 KPI，也构造 summary
            analysis_data = getattr(trigger_result, 'analysis_data', None) or {}
            kpi = analysis_data.get("kpi") or {}
            if kpi.get("mom") is not None or kpi.get("yoy") is not None:
                metric_name = state.mql.metric.name if (state.mql and state.mql.metric) else ""
                mom = kpi.get("mom")
                yoy = kpi.get("yoy")
                if mom is not None and yoy is not None:
                    state.one_sentence_summary = f"{metric_name}环比{mom*100:.1f}%，同比{yoy*100:.1f}%"
                elif mom is not None:
                    direction = "下降" if mom < 0 else "上涨"
                    state.one_sentence_summary = f"{metric_name}环比{direction}{abs(mom)*100:.1f}%"
                elif yoy is not None:
                    direction = "下降" if yoy < 0 else "上涨"
                    state.one_sentence_summary = f"{metric_name}同比{direction}{abs(yoy)*100:.1f}%"
                else:
                    state.one_sentence_summary = ""
                # 详细摘要包含 KPI 信息
                state.analysis_summary = state.one_sentence_summary
            elif state.mql and state.mql.intent and state.mql.intent.value == "query_trend":
                # 趋势查询但无 YoY/MoM：从渲染 SQL 数据构造趋势摘要
                metric_name = state.mql.metric.name if (state.mql and state.mql.metric) else "指标"
                rows = result_dict.get("data", [])
                # 收集数值列（跳过月份字符串列）
                metric_col = None
                for k in (rows[0].keys() if rows else []):
                    if k not in ("月份", "MONTHS", "FDATE", "date", "时间", "time", "dummy"):
                        metric_col = k
                        break
                values = []
                for row in rows:
                    if metric_col and row.get(metric_col) is None:
                        continue
                    for k, v in row.items():
                        if k in ("月份", "MONTHS", "FDATE", "date", "时间", "time"):
                            continue
                        try:
                            values.append(float(str(v).replace(",", "")))
                        except (ValueError, TypeError):
                            continue
                if len(values) >= 2:
                    first, last = values[0], values[-1]
                    change = (last - first) / first * 100 if first != 0 else 0
                    direction = "下降" if change < 0 else "上升"
                    state.one_sentence_summary = f"{metric_name}整体趋势{direction}，较期初{abs(change):.1f}%"
                    state.analysis_summary = state.one_sentence_summary
                else:
                    state.one_sentence_summary = ""
                    state.analysis_summary = ""
            else:
                state.one_sentence_summary = ""
                state.analysis_summary = ""

            # 维度探索：多行数据 + group by 维度 → 调用 generate_output
            rows = result_dict.get("data", [])
            if rows and len(rows) > 1 and state.mql and state.mql.dimensions and any(dim.value is None and dim.column for dim in state.mql.dimensions):
                try:
                    from ai.engine.llm_v2.nodes.trigger_analyzer import TriggerResult, TriggerType, Priority
                    dim_trigger_result = TriggerResult(
                        should_analyze=True,
                        trigger_type=TriggerType.GENERIC_QUERY,
                        trigger_reason="多维度数据展示",
                        priority=Priority.P1,
                        affected_dimensions=[],
                        drilldown_options=[]
                    )
                    dim_trigger_result.analysis_data = {
                        "data": rows,
                        "total": len(rows),
                        "kpi": {},
                        "is_dimension_exploration": True,
                        "attribution_data": analysis_data.get("attribution_data")
                    }
                    analysis_output = await analyzer.generate_output(dim_trigger_result, state.mql, {"data": rows})
                    if analysis_output:
                        state.analysis = analysis_output.to_dict()
                        state.one_sentence_summary = analysis_output.summary or ""
                        state.analysis_summary = analysis_output.summary or ""
                except Exception as e:
                    import traceback
                    logger.warning(f"[trigger_analyzer] 维度探索 generate_output 失败: {e}, 堆栈: {traceback.format_exc()}")

            state.add_thinking_step(
                "trigger_analyzer",
                status="completed",
                content="无触发分析",
                llm_used=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            logger.info("[trigger_analyzer] 无触发分析")

    except Exception as e:
        import traceback
        logger.error(f"[trigger_analyzer] 错误: {e}")
        logger.error(f"[trigger_analyzer] 堆栈: {traceback.format_exc()}")
        state.analysis = None
        state.add_thinking_step(
            "trigger_analyzer",
            status="completed",
            content=f"触发分析跳过: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    # 传递 mom/yoy 到 state（供 SSE result_ready 事件使用）
    # 优先用 result_dict 中计算好的值；若为 None，则从 state.analysis.kpi 提取（trigger_analyzer 算过）
    if result_dict.get("mom_change") is not None:
        state.mom_change = result_dict["mom_change"]
    elif state.analysis and state.analysis.get("kpi", {}).get("mom") is not None:
        state.mom_change = state.analysis["kpi"]["mom"]

    if result_dict.get("yoy_change") is not None:
        state.yoy_change = result_dict["yoy_change"]
    elif state.analysis and state.analysis.get("kpi", {}).get("yoy") is not None:
        state.yoy_change = state.analysis["kpi"]["yoy"]

    return state


async def result_analyzer(state: V2State) -> V2State:
    """
    步骤 11: 结果分析智能体
    - 分析查询结果，生成回答
    """
    from .nodes.result_analyzer import ResultAnalyzer

    start_time = time.time()
    state.current_step ="result_analyzer"

    try:
        analyzer = ResultAnalyzer()
        result = await analyzer.analyze(
            mql=state.mql,
            sql_result=state.sql_result,
            question=state.question,
            is_generic_result=state.is_generic_result,
            clarification_message=state.context_cache.clarification_message or "",
            clarification_options=state.context_cache.clarification_options or [],
            analysis=state.analysis,
        )

        state.answer = result.get("answer", "")
        state.supplementary_info = result.get("supplementary_info", [])
        state.context_cache.suggestions = result.get("suggestions", [])
        state.explanation = result.get("explanation")  # 可解释性信息
        if result.get("kpi_tooltip"):
            state.kpi_tooltip = result["kpi_tooltip"]
        if result.get("dim_mom_data"):
            state.dim_mom_data = result["dim_mom_data"]
        logger.info(f"[result_analyzer] saved supplementary_info={state.supplementary_info}, suggestions_count={len(state.context_cache.suggestions)}")
        # 保存结构化的追问选项（供前端渲染按钮）
        if result.get("clarification_options"):
            state.context_cache.clarification_options = result.get("clarification_options")
            state.context_cache.clarification_message = result.get("clarification_message", "")

        state.add_thinking_step(
            "result_analyzer",
            status="completed",
            content=f"生成回答: {state.answer[:50]}..." if len(state.answer) > 50 else f"生成回答: {state.answer}",
            llm_used=True,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    except Exception as e:
        logger.error(f"[result_analyzer] 错误: {e}")
        state.error =f"result_analysis_error: {str(e)}"
        state.add_thinking_step(
            "result_analyzer",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=True,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


async def state_manager(state: V2State) -> V2State:
    """
    步骤 11: 状态更新节点
    - 更新会话状态
    - 保存历史记录
    """
    from .nodes.state_manager import StateManager

    start_time = time.time()
    state.current_step ="state_manager"

    try:
        manager = StateManager()
        await manager.update(state)

        state.add_thinking_step(
            "state_manager",
            status="completed",
            content="状态更新完成",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    except Exception as e:
        logger.error(f"[state_manager] 错误: {e}")
        # 状态管理失败不阻塞流程
        state.add_thinking_step(
            "state_manager",
            status="failed",
            content=f"错误: {str(e)}",
            llm_used=False,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return state


# ==================== 边定义 ====================

def should_retry_mql(state: V2State) -> Literal["mql_generator", "error"]:
    """
    判断是否需要重试 MQL 生成
    - 步骤 4/5 失败 → 回步骤 3 重试（最多 3 次）
    """
    if state.retry_count >= state.max_retries:
        logger.warning(f"[边判断] 重试次数已达上限 ({state.max_retries})，终止流程")
        return "error"

    # 检查是否是 MQL 相关的错误
    if state.error and ("mql" in state.error.lower() or "syntax" in state.error.lower()):
        return "mql_generator"

    return "error"


def should_retry_quality(state: V2State) -> Literal["mql_generator", "end"]:
    """
    判断数据质量失败后的处理
    - 步骤 9 失败 → 回步骤 3 重试或结束
    """
    if state.error == "data_quality_error" and state.retry_count < state.max_retries:
        return "mql_generator"

    # 数据质量问题不重试，直接结束
    return "end"


def route_after_auditor(state: V2State) -> Literal["sql_executor", "error"]:
    """
    SQL 安全审计后的路由
    - 审计失败 → 直接拒绝（error）
    """
    if state.error and "sql_security_error" in state.error:
        return "error"

    return "sql_executor"


def route_after_quality(state: V2State) -> Literal["trigger_analyzer", "mql_generator"]:
    """
    数据质量检查后的路由
    - 检查通过 → trigger_analyzer → result_analyzer
    - 检查失败 → 回 mql_generator 重试
    """
    if state.error == "data_quality_error":
        return "mql_generator"

    return "trigger_analyzer"


# ==================== 构建 Graph ====================

def create_v2_graph():
    """
    创建 V2 LangGraph StateGraph

    返回编译好的 graph，可调用 .invoke() 或 .stream()
    """
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        logger.error("[create_v2_graph] 请安装 langgraph: pip install langgraph")
        raise ImportError("需要安装 langgraph: pip install langgraph")

    from .schema import V2State

    # 创建 StateGraph
    builder = StateGraph(V2State)

    # 添加节点
    builder.add_node("intent_router", intent_router)
    builder.add_node("context_enhancer", context_enhancer)
    builder.add_node("mql_generator", mql_generator)
    builder.add_node("mql_syntax_validator", mql_syntax_validator)
    builder.add_node("mql_semantic_validator", mql_semantic_validator)
    builder.add_node("slot_clarifier", slot_clarifier)
    builder.add_node("sql_generator", sql_generator)
    builder.add_node("sql_security_auditor", sql_security_auditor)
    builder.add_node("sql_executor", sql_executor)
    builder.add_node("data_quality_checker", data_quality_checker)
    builder.add_node("trigger_analyzer", trigger_analyzer)
    builder.add_node("result_analyzer", result_analyzer)
    builder.add_node("state_manager", state_manager)

    # 设置入口
    builder.set_entry_point("intent_router")

    # 定义边
    # 1. intent_router → 条件边（寒暄/追问直接结束，否则继续 context_enhancer）
    def route_after_intent_router(state: V2State) -> str:
        # 寒暄意图：跳过后续 SQL 链路
        if state.mql and state.mql.intent == MQLIntent.GREETING:
            return "end"
        # 追问/泛指维度：直接结束
        if state.error:
            return "end"
        return "context_enhancer"

    builder.add_conditional_edges(
        "intent_router",
        route_after_intent_router,
        {
            "context_enhancer": "context_enhancer",
            "end": END,
        }
    )

    # 2. context_enhancer → mql_generator
    builder.add_edge("context_enhancer", "mql_generator")

    # 3. mql_generator → mql_syntax_validator
    builder.add_edge("mql_generator", "mql_syntax_validator")

    # 4. mql_syntax_validator → 条件边（失败回 mql_generator，成功去语义验证）
    builder.add_conditional_edges(
        "mql_syntax_validator",
        should_retry_mql,
        {
            "mql_generator": "mql_generator",
            "error": END,
        }
    )

    # 5. mql_syntax_validator → mql_semantic_validator（成功时）
    builder.add_edge("mql_syntax_validator", "mql_semantic_validator")

    # 6. mql_semantic_validator → 条件边（失败回 mql_generator）
    builder.add_conditional_edges(
        "mql_semantic_validator",
        should_retry_mql,
        {
            "mql_generator": "mql_generator",
            "error": END,
        }
    )

    # 7. mql_semantic_validator → slot_clarifier（成功时）
    builder.add_edge("mql_semantic_validator", "slot_clarifier")

    # 7.5. slot_clarifier → 条件边（需要追问则结束，否则继续 sql_generator）
    def route_after_slot_clarifier(state: V2State) -> str:
        if state.needs_clarification:
            return "clarify"
        return "sql_generator"

    builder.add_conditional_edges(
        "slot_clarifier",
        route_after_slot_clarifier,
        {
            "sql_generator": "sql_generator",
            "clarify": END,
        }
    )

    # 8. sql_generator → sql_security_auditor
    builder.add_edge("sql_generator", "sql_security_auditor")

    # 9. sql_security_auditor → 条件边（失败直接拒绝）
    builder.add_conditional_edges(
        "sql_security_auditor",
        route_after_auditor,
        {
            "sql_executor": "sql_executor",
            "error": END,
        }
    )

    # 10. sql_executor → data_quality_checker
    builder.add_edge("sql_executor", "data_quality_checker")

    # 11. data_quality_checker → 条件边
    builder.add_conditional_edges(
        "data_quality_checker",
        route_after_quality,
        {
            "mql_generator": "mql_generator",
            "trigger_analyzer": "trigger_analyzer",
        }
    )

    # 12. trigger_analyzer → result_analyzer
    builder.add_edge("trigger_analyzer", "result_analyzer")

    # 13. result_analyzer → state_manager
    builder.add_edge("result_analyzer", "state_manager")

    # 13. state_manager → END
    builder.add_edge("state_manager", END)

    # 编译
    graph = builder.compile()

    logger.info("[create_v2_graph] V2 LangGraph 创建成功")
    return graph


class V2Graph:
    """
    V2 Graph 封装类

    提供高级接口：
    - invoke: 同步调用
    - stream: 流式调用
    - reset: 重置状态
    """

    _instance: Optional["V2Graph"] = None
    _graph = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 Graph"""
        try:
            self._graph = create_v2_graph()
            logger.info("[V2Graph] 初始化完成")
        except ImportError as e:
            logger.error(f"[V2Graph] 初始化失败: {e}")
            self._graph = None

    def invoke(self, state: V2State) -> V2State:
        """
        同步调用 Graph（节点为 async 时会报错，请使用 ainvoke）

        Args:
            state: V2State 初始状态

        Returns:
            V2State: 最终状态
        """
        if not self._graph:
            raise RuntimeError("V2Graph 未初始化，请先安装 langgraph")

        return self._graph.invoke(state)

    async def ainvoke(self, state: V2State) -> V2State:
        """
        异步调用 Graph（用于 async 节点）

        简单顺序执行，不使用 LangGraph 的状态管理，
        以避免 ainvoke 的状态合并问题。

        Args:
            state: V2State 初始状态

        Returns:
            V2State: 最终状态
        """
        # intent_router 是 async generator，需要用 async for 迭代
        loop_count = 0
        async for sub_state in intent_router(state):
            loop_count += 1
            logger.info(f"[ainvoke] intent_router yield #{loop_count}: is_generic_result={getattr(sub_state, 'is_generic_result', False)}")
            state = sub_state

        logger.info(f"[ainvoke] intent_router 循环结束, loop_count={loop_count}, state.is_generic_result={getattr(state, 'is_generic_result', 'MISSING_ATTR')}")

        # 泛指维度不需要在这里中断，intent_router 已经设置了默认维度
        # 继续执行让用户先看到数据，追问引导在 result_analyzer 中附加

        # 真正需要追问的才中断
        if state.error == "needs_clarification":
            state.needs_clarification = True
            if hasattr(state.context_cache, 'clarification_message') and state.context_cache.clarification_message:
                state.clarification_message = state.context_cache.clarification_message
            logger.info(f"[ainvoke] 需要追问，中断流程")
            return state

        # 寒暄意图：直接返回问候，跳过后续 SQL 链路
        if state.mql and state.mql.intent == MQLIntent.GREETING:
            logger.info(f"[ainvoke] 寒暄意图，中断流程，返回问候")
            return state

        state = await context_enhancer(state)
        state = await mql_generator(state)

        # MQL 语法验证失败检查
        if state.error and "mql_syntax_error" in state.error:
            # 重试逻辑
            if state.retry_count < state.max_retries:
                state.error = ""  # 清除错误，重试
                state = await mql_generator(state)
            return state

        state = await mql_semantic_validator(state)

        # MQL 语义验证失败检查
        if state.error and "mql_semantic_error" in state.error:
            if state.retry_count < state.max_retries:
                state.error = ""
                state = await mql_generator(state)
                state = await mql_semantic_validator(state)
            return state

        # 槽位消解检查
        state = await slot_clarifier(state)
        if state.needs_clarification:
            logger.info(f"[ainvoke] 槽位缺失需要追问，中断流程")
            return state

        state = await sql_generator(state)
        state = await sql_security_auditor(state)

        # SQL 安全审计失败检查
        if state.error and "sql_security_error" in state.error:
            return state

        state = await sql_executor(state)

        # SQL 执行失败检查
        if state.error and "sql_execution_error" in state.error:
            return state

        state = await data_quality_checker(state)

        # 数据质量检查失败检查
        if state.error == "data_quality_error":
            if state.retry_count < state.max_retries:
                state.error = ""
                state = await mql_generator(state)
                state = await sql_generator(state)
                state = await sql_executor(state)
            return state

        # 触发分析
        state = await trigger_analyzer(state)

        state = await result_analyzer(state)
        state = await state_manager(state)

        return state

    async def astream(self, state: V2State):
        """
        异步流式调用 Graph

        手动顺序执行节点并在每步后 yield，避免 LangGraph astream 的状态合并问题。

        Yields:
            V2State: 中间状态
        """
        if not self._graph:
            raise RuntimeError("V2Graph 未初始化，请先安装 langgraph")

        # 顺序执行节点并 yield 每步状态
        # intent_router 是 async generator，需要用 async for 迭代
        loop_count = 0
        async for sub_state in intent_router(state):
            loop_count += 1
            logger.info(f"[astream] intent_router yield #{loop_count}: is_generic_result={getattr(sub_state, 'is_generic_result', False)}")
            yield sub_state
            state = sub_state

        logger.info(f"[astream] intent_router 循环结束, loop_count={loop_count}, state.is_generic_result={getattr(state, 'is_generic_result', 'MISSING_ATTR')}")

        # 泛指维度不需要在这里中断，intent_router 已经设置了默认维度
        # 继续执行让用户先看到数据，追问引导在 result_analyzer 中附加
        if state.error == "needs_clarification":
            state.needs_clarification = True
            if hasattr(state.context_cache, 'clarification_message') and state.context_cache.clarification_message:
                state.clarification_message = state.context_cache.clarification_message
            logger.info(f"[astream] 需要追问，中断流程")
            yield state
            return

        # 寒暄意图：直接返回问候，跳过后续 SQL 链路
        if state.mql and state.mql.intent == MQLIntent.GREETING:
            logger.info(f"[astream] 寒暄意图，中断流程，返回问候")
            yield state
            return

        state = await context_enhancer(state)
        yield state

        state = await mql_generator(state)
        yield state

        if state.error and "mql_syntax_error" in state.error:
            if state.retry_count < state.max_retries:
                state.error = ""
                state = await mql_generator(state)
            yield state
            return

        state = await mql_semantic_validator(state)
        yield state

        if state.error and "mql_semantic_error" in state.error:
            if state.retry_count < state.max_retries:
                state.error = ""
                state = await mql_generator(state)
                state = await mql_semantic_validator(state)
            yield state
            return

        # 槽位消解检查
        state = await slot_clarifier(state)
        yield state
        if state.needs_clarification:
            logger.info(f"[astream] 槽位缺失需要追问，中断流程")
            return

        state = await sql_generator(state)
        yield state

        state = await sql_security_auditor(state)
        yield state

        if state.error and "sql_security_error" in state.error:
            yield state
            return

        state = await sql_executor(state)
        yield state

        if state.error and "sql_execution_error" in state.error:
            yield state
            return

        state = await data_quality_checker(state)
        yield state

        if state.error == "data_quality_error":
            if state.retry_count < state.max_retries:
                state.error = ""
                state = await mql_generator(state)
                state = await sql_generator(state)
                state = await sql_executor(state)
            yield state
            return

        # 触发分析
        state = await trigger_analyzer(state)
        yield state

        state = await result_analyzer(state)
        yield state

        state = await state_manager(state)
        yield state

    def stream(self, state: V2State):
        """
        同步流式调用 Graph

        Yields:
            V2State: 中间状态
        """
        if not self._graph:
            raise RuntimeError("V2Graph 未初始化，请先安装 langgraph")

        # 使用同步方式执行（简化版）
        for state in self._graph.stream(state):
            yield state

    def reset(self, session_id: str):
        """
        重置会话状态

        Args:
            session_id: 会话 ID
        """
        # TODO: 清除 Checkpoint
        logger.info(f"[V2Graph] 重置会话: {session_id}")


def get_v2_graph() -> V2Graph:
    """获取 V2Graph 单例"""
    return V2Graph()
