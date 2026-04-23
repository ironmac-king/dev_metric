"""
V2 路由入口

提供 /api/v1/llm-ask/v2 接口

V2 使用 LangGraph 11 步闭环架构：
  intent_router → context_enhancer → mql_generator → mql_syntax_validator
      → mql_semantic_validator → sql_generator → sql_security_auditor
      → sql_executor → data_quality_checker → result_analyzer → state_manager
"""
import time
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai.config.logging_config import get_logger
from .schema import V2State, MQLSchema, create_v2_state
from .graph import get_v2_graph
from .streaming import (
    StreamEvent,
    SSSEvent,
    get_streaming_generator,
    clear_streaming_generator,
)
from .metrics import get_performance_tracker

logger = get_logger("ai.llm_v2.router")

router = APIRouter(prefix="/api/v1/llm-ask", tags=["LLM.V2"])

# V2 Session 存储：保存每个 session_id 对应的上轮 MQL（用于多轮对话上下文继承）
v2_session_mql: Dict[str, MQLSchema] = {}


class AskRequestV2(BaseModel):
    """V2 问数请求"""
    question: str
    session_id: Optional[str] = None
    user_id: str = "default"
    page: int = 1
    page_size: int = 100


class ThinkingStepResponse(BaseModel):
    """思考步骤响应"""
    step: str
    status: str
    content: Optional[str] = None
    timestamp: Optional[str] = None
    llm_used: bool = False
    duration_ms: int = 0
    source: Optional[str] = None
    entities: list = []
    needs_clarification: bool = False
    clarification_message: Optional[str] = ""
    clarification_options: List[Dict[str, Any]] = []


class AskResponseV2(BaseModel):
    """V2 问数响应"""
    session_id: str
    answer: str
    sql: Optional[str] = None
    mql: Optional[Dict[str, Any]] = None
    suggest: List[str] = []
    thinking_steps: List[ThinkingStepResponse] = []
    needs_clarification: bool = False
    clarification_message: Optional[str] = None
    clarification_options: Optional[List[Dict[str, Any]]] = None  # 追问选项
    error: Optional[str] = None
    result_data: Optional[List[Dict[str, Any]]] = None
    total: int = 0
    metric_name: Optional[str] = None  # 指标名称（用于图表 tooltip）


@router.post("/v2", response_model=AskResponseV2)
async def ask_question_v2(req: AskRequestV2):
    """
    V2 智能问数接口

    使用 LangGraph 11 步闭环架构
    """
    start_time = time.time()
    session_id = req.session_id or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    logger.info(f"[V2] 收到问题: {req.question[:50]}..., session_id={session_id}, request_id={request_id}")

    # 获取性能追踪器
    tracker = get_performance_tracker()

    try:
        # 1. 初始化 V2State
        state = create_v2_state(
            session_id=session_id,
            user_id=req.user_id,
            question=req.question,
            created_at=datetime.now().isoformat(),
        )

        # 恢复上轮 MQL（用于多轮对话上下文继承）
        inherited_mql = v2_session_mql.get(session_id)
        if inherited_mql:
            state.inherited_mql = inherited_mql
            logger.info(f"[V2] 恢复上轮 MQL: session_id={session_id}, intent={inherited_mql.intent.value if inherited_mql else 'N/A'}, metric={inherited_mql.metric.name if inherited_mql and inherited_mql.metric else None}, dims={[(d.type, d.value) for d in inherited_mql.dimensions] if inherited_mql and inherited_mql.dimensions else None}")
        else:
            logger.info(f"[V2] 未找到上轮 MQL: session_id={session_id}, v2_session_mql keys={list(v2_session_mql.keys())}")

        # 2. 获取 V2 Graph
        v2_graph = get_v2_graph()

        if not v2_graph._graph:
            return AskResponseV2(
                session_id=session_id,
                answer="V2 架构未初始化，请先安装 langgraph",
                sql="",
                suggest=[],
                error="graph_not_initialized",
            )

        # 3. 执行 Graph（异步）
        result_state = await v2_graph.ainvoke(state)

        # 4. 检查是否需要追问
        needs_clarification = False
        clarification_message = None

        if result_state.error == "needs_clarification":
            needs_clarification = True
            # 优先从 context_cache 读取追问消息（intent_router 设置的）
            clarification_message = result_state.context_cache.get("clarification_message") or result_state.answer
        elif result_state.is_generic_result:
            # 泛指维度：流程已继续执行，但需要显示追问标签让用户切换级别
            needs_clarification = True
            clarification_message = result_state.context_cache.get("clarification_message", "")

        # 5. 提取建议
        suggestions = result_state.context_cache.get("suggestions", [])
        if not suggestions:
            suggestions = _generate_default_suggestions(result_state)

        # 6. 构建响应
        response = AskResponseV2(
            session_id=session_id,
            answer=result_state.answer or "抱歉，我无法回答这个问题",
            sql=result_state.sql,
            mql=result_state.mql.to_dict() if result_state.mql else None,
            suggest=suggestions,
            thinking_steps=[
                ThinkingStepResponse(
                    step=s.step,
                    status=s.status,
                    content=s.content,
                    timestamp=s.timestamp,
                    llm_used=s.llm_used,
                    duration_ms=s.duration_ms,
                    source=s.source,
                    entities=s.entities,
                    needs_clarification=s.needs_clarification,
                    clarification_message=s.clarification_message,
                    clarification_options=s.clarification_options,
                )
                for s in result_state.thinking_steps
            ],
            needs_clarification=needs_clarification,
            clarification_message=clarification_message,
            clarification_options=result_state.context_cache.get("clarification_options") if needs_clarification else None,
            error=result_state.error if not result_state.answer else None,
            result_data=result_state.sql_result.data if result_state.sql_result else None,
            total=result_state.sql_result.total if result_state.sql_result else 0,
            metric_name=_get_metric_name(result_state.mql) if result_state.mql else None,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 记录性能
        tracker.record_request(
            request_id=request_id,
            session_id=session_id,
            question=req.question,
            start_time=start_time,
            end_time=time.time(),
            success=bool(result_state.answer),
            error=result_state.error if not result_state.answer else None,
        )

        # 记录节点耗时
        for step in result_state.thinking_steps:
            tracker.record_node(step.step, step.duration_ms, step.status == "completed")

        logger.info(f"[V2] 回答完成: {response.answer[:50]}..., 耗时 {duration_ms}ms")

        # 保存当前 MQL 到 session store（用于多轮对话上下文继承）
        _saved_session_info = f"session_id={session_id}, keys={list(v2_session_mql.keys())}"
        if result_state and result_state.mql:
            v2_session_mql[session_id] = result_state.mql
            _saved_session_info = f"session_id={session_id}, saved_metric={result_state.mql.metric.name if result_state.mql.metric else None}, saved_dims={[(d.type, d.value) for d in result_state.mql.dimensions] if result_state.mql.dimensions else []}"
            logger.info(f"[V2] 保存 MQL 到 session: {_saved_session_info}")

        return response

    except Exception as e:
        logger.error(f"[V2] 处理出错: {e}")
        import traceback
        traceback.print_exc()

        # 记录错误
        tracker.record_request(
            request_id=request_id,
            session_id=session_id,
            question=req.question,
            start_time=start_time,
            end_time=time.time(),
            success=False,
            error=str(e),
        )

        return AskResponseV2(
            session_id=session_id,
            answer=f"处理出错: {str(e)}",
            sql="",
            suggest=["请尝试换一种问法"],
            error=str(e),
        )


@router.post("/v2/stream")
async def ask_question_v2_stream(req: AskRequestV2):
    """
    V2 流式问数接口

    使用 SSE 流式输出思考过程和回答
    """
    session_id = req.session_id or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    logger.info(f"[V2 Stream] 收到问题: {req.question[:50]}..., session_id={session_id}")

    # 获取流式生成器
    streamer = get_streaming_generator(session_id)

    async def generate_sse():
        """生成 SSE 流"""
        start_time = time.time()
        tracker = get_performance_tracker()

        try:
            # 发送连接事件
            yield StreamEvent(SSSEvent.CONNECTED, {
                "request_id": request_id,
                "session_id": session_id,
                "question": req.question,
            }).to_sse()

            # 初始化状态
            state = create_v2_state(
                session_id=session_id,
                user_id=req.user_id,
                question=req.question,
                created_at=datetime.now().isoformat(),
            )

            # 恢复上轮 MQL（用于多轮对话上下文继承）
            inherited_mql = v2_session_mql.get(session_id)
            if inherited_mql:
                state.inherited_mql = inherited_mql
                logger.info(f"[V2 Stream] 恢复上轮 MQL: session_id={session_id}, intent={inherited_mql.intent.value if inherited_mql else 'N/A'}")

            # 获取 Graph
            v2_graph = get_v2_graph()
            if not v2_graph._graph:
                yield StreamEvent(SSSEvent.ERROR, {
                    "error": "V2 架构未初始化"
                }).to_sse()
                return

            # 流式执行
            async for step_name, step_state in _stream_graph(v2_graph, state):
                # 发送步骤开始
                yield StreamEvent(SSSEvent.STEP_START, {
                    "step": step_name,
                }).to_sse()
                await asyncio.sleep(0.05)  # 让浏览器有时间渲染当前步骤

                # 发送步骤完成
                yield StreamEvent(SSSEvent.STEP_COMPLETE, {
                    "step": step_name,
                    "duration_ms": step_state.get("duration_ms", 0),
                }).to_sse()
                await asyncio.sleep(0.05)  # 让浏览器有时间渲染当前步骤

                # 发送思考内容
                if step_state.get("thinking"):
                    yield StreamEvent(SSSEvent.THINKING, {
                        "step": step_name,
                        "content": step_state["thinking"],
                        "entities": step_state.get("entities", []),
                        "llm_used": step_state.get("llm_used", False),
                        "source": step_state.get("source"),
                        "mql": step_state.get("mql"),
                        "needs_clarification": step_state.get("needs_clarification", False),
                        "clarification_message": step_state.get("clarification_message", ""),
                        "clarification_options": step_state.get("clarification_options", []),
                        "original_question": step_state.get("original_question", ""),
                    }).to_sse()
                    await asyncio.sleep(0.05)  # 让浏览器有时间渲染当前步骤

                # 发送 SQL（一旦就绪）
                if step_state.get("sql"):
                    yield StreamEvent(SSSEvent.SQL_READY, {
                        "sql": step_state["sql"],
                    }).to_sse()

                # 发送结果（一旦就绪）
                if step_state.get("result_data"):
                    yield StreamEvent(SSSEvent.RESULT_READY, {
                        "result_data": step_state["result_data"],
                        "total": step_state.get("total", 0),
                        "metric_name": step_state.get("metric_name", ""),
                        "metric_names": step_state.get("metric_names", []),
                    }).to_sse()

                # 发送回答（一旦就绪）
                if step_state.get("answer"):
                    yield StreamEvent(SSSEvent.ANSWER_READY, {
                        "answer": step_state["answer"],
                        "suggestions": step_state.get("suggestions", []),
                        "clarification_options": step_state.get("clarification_options", []),
                        "clarification_message": step_state.get("clarification_message", ""),
                    }).to_sse()

            # 发送完成事件
            yield StreamEvent(SSSEvent.DONE, {
                "duration_ms": int((time.time() - start_time) * 1000),
            }).to_sse()

        except Exception as e:
            logger.error(f"[V2 Stream] 错误: {e}")
            yield StreamEvent(SSSEvent.ERROR, {
                "error": str(e),
            }).to_sse()

        finally:
            # 保存当前 MQL 到 session store（用于下一轮多轮对话）
            if state and state.mql:
                v2_session_mql[session_id] = state.mql
                logger.info(f"[V2 Stream] 保存 MQL 到 session: session_id={session_id}, intent={state.mql.intent.value if state.mql else 'N/A'}, dimensions={[d.type for d in state.mql.dimensions] if state.mql.dimensions else []}")
            # 清理流式生成器
            clear_streaming_generator(session_id)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_graph(graph, state: V2State):
    """
    流式执行 Graph

    Yields:
        (step_name, step_state)
    """
    try:
        logger.info(f"[_stream_graph] 开始流式执行")
        # 使用 V2Graph 的 astream 方法（手动顺序执行并 yield 每步状态）
        async for state_update in graph.astream(state):
            step_name = getattr(state_update, 'current_step', '') or ''
            logger.info(f"[_stream_graph] state_update received, current_step={step_name}")
            if step_name:
                # 从 state_update 提取 thinking_steps
                thinking_steps = getattr(state_update, 'thinking_steps', []) or []
                last_thinking = thinking_steps[-1] if thinking_steps else None

                sql_result = getattr(state_update, 'sql_result', None)
                result_data = sql_result.data if sql_result and hasattr(sql_result, 'data') else None
                total = sql_result.total if sql_result and hasattr(sql_result, 'total') else 0

                # 获取 answer 和 suggestions
                answer = getattr(state_update, 'answer', '') or ''
                suggestions = []
                if hasattr(state_update, 'context_cache') and state_update.context_cache:
                    suggestions = state_update.context_cache.get("suggestions", [])

                # 检查是否泛指维度需要追问
                is_generic = getattr(state_update, 'is_generic_result', False)
                # 从 last_thinking（ThinkingStep 对象）获取追问信息
                clarification_message = getattr(last_thinking, 'clarification_message', '') if last_thinking else ""
                clarification_options = getattr(last_thinking, 'clarification_options', []) if last_thinking else []
                original_question = getattr(last_thinking, 'original_question', '') if last_thinking else ""

                # 获取 metric_name
                metric_name = _get_metric_name(state_update.mql) if hasattr(state_update, 'mql') and state_update.mql else ''
                metric_names = _get_metric_names(state_update.mql) if hasattr(state_update, 'mql') and state_update.mql else []
                logger.info(f"[_stream_graph] result_ready metric_name={metric_name}, metric_names={metric_names}")

                # 获取 MQL JSON（用于前端展示）
                mql_json = None
                if hasattr(state_update, 'mql') and state_update.mql:
                    try:
                        mql_json = state_update.mql.to_dict()
                    except Exception:
                        mql_json = None

                yield step_name, {
                    "thinking": last_thinking.content if last_thinking and hasattr(last_thinking, 'content') else '',
                    "entities": last_thinking.entities if last_thinking and hasattr(last_thinking, 'entities') else [],
                    "llm_used": last_thinking.llm_used if last_thinking and hasattr(last_thinking, 'llm_used') else False,
                    "source": last_thinking.source if last_thinking and hasattr(last_thinking, 'source') else None,
                    "sql": getattr(state_update, 'sql', '') or '',
                    "result_data": result_data,
                    "total": total,
                    "duration_ms": last_thinking.duration_ms if last_thinking and hasattr(last_thinking, 'duration_ms') else 0,
                    "answer": answer,
                    "suggestions": suggestions,
                    # 传递追问信息
                    "needs_clarification": getattr(last_thinking, 'needs_clarification', is_generic),
                    "clarification_message": clarification_message,
                    "clarification_options": clarification_options,
                    "original_question": original_question,
                    # 传递指标名供前端 tooltip 使用（占比查询时从 molecule_metric 获取）
                    "metric_name": metric_name,
                    # 传递多指标名称数组（供表格表头使用）
                    "metric_names": metric_names,
                    # 传递 MQL JSON（供 mql_semantic_validator 步骤展示）
                    "mql": mql_json,
                }
        logger.info(f"[_stream_graph] 流式执行完成")
    except Exception as e:
        logger.error(f"[_stream_graph] 错误: {e}")
        import traceback
        traceback.print_exc()
        raise

def _get_metric_name(mql) -> str:
    """获取指标名称（支持占比查询的 molecule_metric）"""
    if not mql:
        return ''

    # 优先从 mql.metric 获取
    metric = getattr(mql, 'metric', None)
    if metric:
        name = getattr(metric, 'name', '') or ''
        if name:
            return name

    # 占比查询时，从 molecule_metric 获取
    molecule_metric = getattr(mql, 'molecule_metric', None)
    if molecule_metric:
        mol_name = getattr(molecule_metric, 'name', '') or ''
        if mol_name:
            # 尝试构造占比名称：分子 + "占比" 或 "占" + 分母
            denom_metric = getattr(mql, 'denominator_metric', None)
            if denom_metric:
                den_name = getattr(denom_metric, 'name', '') or ''
                if den_name:
                    return f"{mol_name}占{den_name}比重"
            return f"{mol_name}占比"

    return ''


def _get_metric_names(mql) -> list:
    """获取所有指标名称（支持多指标）"""
    if not mql:
        return []

    names = []
    # 优先从 mql.metric 获取（单个指标）
    metric = getattr(mql, 'metric', None)
    if metric:
        name = getattr(metric, 'name', '') or ''
        if name:
            names.append(name)

    # 多指标：从 mql.metrics 数组获取
    metrics = getattr(mql, 'metrics', None)
    if metrics:
        for m in metrics:
            name = getattr(m, 'name', '') or ''
            if name and name not in names:
                names.append(name)

    return names


def _get_step_thinking(state: V2State) -> str:
    """从状态获取步骤思考内容"""
    if state.thinking_steps:
        last_step = state.thinking_steps[-1]
        return last_step.content or f"完成 {last_step.step}"
    return ""


def _get_step_duration(state: V2State) -> int:
    """从状态获取步骤耗时"""
    if state.thinking_steps:
        last_step = state.thinking_steps[-1]
        return last_step.duration_ms
    return 0


@router.get("/v2/health")
async def v2_health():
    """V2 健康检查"""
    try:
        v2_graph = get_v2_graph()
        tracker = get_performance_tracker()
        stats = tracker.get_stats()

        return {
            "status": "ok",
            "graph_initialized": v2_graph._graph is not None,
            "performance": {
                "avg_duration_ms": stats["request"]["avg_duration_ms"],
                "p95_duration_ms": stats["request"]["p95_duration_ms"],
                "cache_hit_rate": stats["cache"]["l1_hit_rate"],
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/v2/stats")
async def v2_stats():
    """V2 性能统计"""
    tracker = get_performance_tracker()
    return tracker.get_stats()


@router.post("/v2/benchmark")
async def run_benchmark(sample_size: int = None):
    """
    运行基准测试

    Args:
        sample_size: 采样数量（默认全部 50 条）
    """
    from .metrics import BenchmarkRunner
    from .graph import get_v2_graph

    tracker = get_performance_tracker()
    runner = BenchmarkRunner(tracker)

    v2_graph = get_v2_graph()
    if not v2_graph._graph:
        raise HTTPException(status_code=500, detail="V2 Graph 未初始化")

    try:
        results = await runner.run(v2_graph, sample_size=sample_size)
        return results
    except Exception as e:
        logger.error(f"[Benchmark] 运行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v2/clear-cache")
async def clear_cache():
    """清除缓存"""
    from .cache import get_mql_sql_cache

    cache = get_mql_sql_cache()
    cache._l1.clear()
    cache._l2.clear()
    return {"message": "缓存已清除"}


def _generate_default_suggestions(state: V2State) -> List[str]:
    """生成默认建议"""
    if not state.mql:
        return [
            "本月销售额是多少",
            "查看销售趋势",
            "对比上月数据",
        ]

    suggestions = []

    # 根据意图生成建议
    intent = state.mql.intent.value if state.mql.intent else ""

    if intent == "query_value":
        suggestions = [
            "查看趋势变化",
            "对比同比/环比",
            "按维度分析",
        ]
    elif intent == "query_trend":
        suggestions = [
            "对比上月",
            "对比去年同期",
            "查看占比分布",
        ]
    elif intent == "query_comparison":
        suggestions = [
            "查看趋势变化",
            "按维度分析",
        ]
    elif intent == "query_ranking":
        suggestions = [
            "查看更多排名",
            "查看占比分布",
        ]
    elif intent == "query_ratio":
        suggestions = [
            "查看详细数据",
            "对比各维度占比",
        ]
    else:
        suggestions = [
            "本月销售额是多少",
            "查看销售趋势",
            "对比上月数据",
        ]

    return suggestions
