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
"""
import time
import json
from typing import Dict, Any, Literal, Optional, Tuple
from datetime import datetime

from ai.config.logging_config import get_logger
from .schema import V2State, MQLSchema, MQLDimension, push_history
from .observability import get_tracer, create_trace_context
from ai.client.metric_client import MetricClient

logger = get_logger("ai.llm_v2.graph")


async def _preload_metric_info(state: V2State) -> None:
    """
    预加载指标信息到 context_cache（优化：提前调用 MetricClient）

    在 context_enhancer 阶段提前获取 starrocks_sql 等关键字段，
    存入 state.context_cache["metric_info_cache"]，
    供后续 mql_generator / sql_generator / mql_semantic_validator 复用，
    避免重复的 HTTP 调用。
    """
    try:
        metric = state.inherited_mql.metric if state.inherited_mql else None
        if not metric or not metric.name:
            return

        client = MetricClient()
        # 通过名称查找，获取完整的 starrocks_sql 等信息
        metric_info = client.get_metric_by_name(metric.name)
        if metric_info:
            state.context_cache["metric_info_cache"] = metric_info
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
            result = await router.route(state.question, state.inherited_mql)

            # 更新状态
            if result.get("mql"):
                state.mql = result["mql"]
                span.set_attribute("mql.intent", result["mql"].intent.value)

            # 处理泛指维度 vs 真正追问的区分
            if result.get("needs_clarification"):
                if result.get("is_generic"):
                    # 泛指维度：继续执行，返回默认数据 + 追问引导
                    state.is_generic_result = True
                    state.context_cache["clarification_message"] = result.get("clarification_message", "")
                    state.context_cache["clarification_options"] = result.get("clarification_options", [])

                    # 当有 default_dimension 时，将其应用到 state.mql.dimensions
                    default_dim = result.get("default_dimension", "")
                    if default_dim and state.mql and not state.mql.dimensions:
                        dim = MQLDimension(type=default_dim, value=None)
                        state.mql.dimensions = [dim]
                        logger.info(f"[intent_router] 应用 default_dimension: {default_dim} -> mql.dimensions")

                    logger.info(f"[intent_router] 设置 is_generic_result=True, clarification_options={result.get('clarification_options', [])}")
                    state.add_thinking_step(
                        "intent_router",
                        status="generic_dimension",
                        content=f"泛指维度，使用默认值继续执行: {result.get('default_dimension', '')}",
                        llm_used=True,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                    span.set_attribute("result.type", "generic_dimension")
                else:
                    # 真正需要用户输入的追问，中断流程
                    state.error = "needs_clarification"
                    state.add_thinking_step(
                        "intent_router",
                        status="requires_clarification",
                        content=result.get("clarification_message", ""),
                        llm_used=True,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                    span.set_attribute("result.type", "clarification_needed")
            else:
                state.add_thinking_step(
                    "intent_router",
                    status="completed",
                    content=f"意图: {state.mql.intent.value if state.mql else 'unknown'}",
                    llm_used=True,
                    duration_ms=int((time.time() - start_time) * 1000),
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
            state.context_cache["similar_cases"] = rag_result["similar_cases"]
        if rag_result.get("suggested_mql"):
            state.context_cache["suggested_mql"] = rag_result["suggested_mql"]

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

        # 获取 RAG 上下文
        rag_context = state.context_cache.get("similar_cases", [])

        # 生成 MQL
        mql = await generator.generate(
            question=state.question,
            rag_context=rag_context,
            inherited_mql=state.inherited_mql,
        )

        # 保存到历史栈
        if mql:
            # 保留 intent_router 设置的 order_by（mql_generator 可能没有设置）
            inherited_order_by = state.mql.order_by if state.mql else None
            # 保留 intent_router 设置的 dimensions（mql_generator 的 LLM 可能丢失维度信息）
            inherited_dimensions = state.mql.dimensions if state.mql and state.mql.dimensions else []
            state.mql = mql
            if inherited_order_by and not mql.order_by:
                mql.order_by = inherited_order_by
                logger.info(f"[mql_generator] 保留 intent_router 设置的 order_by: {inherited_order_by.direction}")
            if not mql.dimensions and inherited_dimensions:
                mql.dimensions = inherited_dimensions
                logger.info(f"[mql_generator] 保留 intent_router 设置的 dimensions: {[d.type for d in inherited_dimensions]}")
            push_history(state, json.dumps(mql.to_dict(), ensure_ascii=False))

        state.add_thinking_step(
            "mql_generator",
            status="completed",
            content=f"MQL 生成成功: intent={mql.intent.value if mql else 'unknown'}",
            llm_used=True,
            duration_ms=int((time.time() - start_time) * 1000),
        )

    except Exception as e:
        logger.error(f"[mql_generator] 错误: {e}")
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
                state.context_cache["quality_warnings"] = warnings

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


async def result_analyzer(state: V2State) -> V2State:
    """
    步骤 10: 结果分析智能体
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
            clarification_message=state.context_cache.get("clarification_message", ""),
            clarification_options=state.context_cache.get("clarification_options", []),
        )

        state.answer = result.get("answer", "")
        state.context_cache["suggestions"] = result.get("suggestions", [])
        if result.get("anomalies"):
            state.context_cache["anomalies"] = result.get("anomalies")
        # 保存结构化的追问选项（供前端渲染按钮）
        if result.get("clarification_options"):
            state.context_cache["clarification_options"] = result.get("clarification_options")
            state.context_cache["clarification_message"] = result.get("clarification_message", "")

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


def route_after_quality(state: V2State) -> Literal["result_analyzer", "mql_generator"]:
    """
    数据质量检查后的路由
    - 检查通过 → result_analyzer
    - 检查失败 → 回 mql_generator 重试
    """
    if state.error == "data_quality_error":
        return "mql_generator"

    return "result_analyzer"


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
    builder.add_node("sql_generator", sql_generator)
    builder.add_node("sql_security_auditor", sql_security_auditor)
    builder.add_node("sql_executor", sql_executor)
    builder.add_node("data_quality_checker", data_quality_checker)
    builder.add_node("result_analyzer", result_analyzer)
    builder.add_node("state_manager", state_manager)

    # 设置入口
    builder.set_entry_point("intent_router")

    # 定义边
    # 1. intent_router → context_enhancer（正常流程）
    builder.add_edge("intent_router", "context_enhancer")

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

    # 7. mql_semantic_validator → sql_generator（成功时）
    builder.add_edge("mql_semantic_validator", "sql_generator")

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
            "result_analyzer": "result_analyzer",
        }
    )

    # 12. result_analyzer → state_manager
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
            logger.info(f"[ainvoke] 需要追问，中断流程")
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
            logger.info(f"[astream] 需要追问，中断流程")
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
