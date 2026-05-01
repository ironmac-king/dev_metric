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
import json
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai.config.logging_config import get_logger
from ai.config.runtime import get_go_api_base
from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
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

# Go 后端日志 API 地址
GO_ASK_ANALYSIS_LOG_URL = "http://localhost:8080/api/v1/internal/ask-analysis/logs/v2"


def _refresh_semantic_snapshot_for_request() -> None:
    service = get_semantic_snapshot_service()
    try:
        service.get_active_snapshot(force_refresh=True)
    except Exception as exc:
        logger.warning(f"[V2 Semantic] refresh failed: {exc}")


async def _send_log_to_go(
    user_id: str,
    session_id: str,
    question: str,
    answer: str,
    intent: str,
    success: bool,
    fail_stage: str,
    fail_reason: str,
    thinking_steps: List[Any],
    sql: str,
    mql_json: str,
) -> bool:
    """发送日志到 Go 后端 AskAnalysisLog 表（带重试机制）"""
    # P2-11 fix: 添加 3 次重试 + 指数退避
    MAX_RETRIES = 3
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"[V2 Log] 开始发送日志(尝试 {attempt + 1}/{MAX_RETRIES}): question={question[:30] if question else 'empty'}...")
            # 序列化 thinking_steps
            steps_json = json.dumps([
                {
                    "step": s.step,
                    "status": s.status,
                    "content": s.content or "",
                    "timestamp": s.timestamp or "",
                    "llm_used": s.llm_used,
                    "duration_ms": s.duration_ms,
                    "source": s.source,
                    "entities": s.entities,
                    "needs_clarification": s.needs_clarification,
                    "clarification_message": s.clarification_message or "",
                    "clarification_options": s.clarification_options or [],
                }
                for s in thinking_steps
            ], ensure_ascii=False)

            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "question": question,
                "answer": answer,
                "intent": intent,
                "success": success,
                "fail_stage": fail_stage,
                "fail_reason": fail_reason,
                "suggestion": "",
                "thinking_steps": steps_json,
                "sql": sql,
                "mql_json": mql_json,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(GO_ASK_ANALYSIS_LOG_URL, json=payload)
                if response.status_code == 200:
                    logger.info(f"[V2 Log] 成功发送到 Go API: session_id={session_id}")
                    return True
                else:
                    logger.warning(f"[V2 Log] Go API 返回错误: {response.status_code} {response.text}")
                    last_error = f"status={response.status_code}"
        except Exception as e:
            logger.warning(f"[V2 Log] 发送失败(尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            last_error = str(e)

        # 指数退避：1s, 2s, 4s
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(1 * (attempt + 1))

    logger.error(f"[V2 Log] 发送日志失败，已重试 {MAX_RETRIES} 次: {last_error}")
    return False


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
    analysis: Optional[Dict[str, Any]] = None  # 触发分析结果
    mode: Optional[str] = "direct"  # "direct" or "triggered"


# ==================== 会话落库辅助函数 ====================

def _save_v2_session_to_db(
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    sql: str,
    result_data: Any,
    comparison_results: Any,
) -> None:
    """
    将 V2 会话保存到 PostgreSQL（ask_session_summaries + ask_messages 表）
    """
    try:
        import psycopg2
        import json

        conn = psycopg2.connect(
            host="192.168.1.225",
            port=5432,
            database="dev_metric",
            user="postgres",
            password="admin123",
        )

        now = datetime.now()

        # 序列化 result_data
        result_data_str = ""
        if result_data is not None:
            try:
                result_data_str = json.dumps(result_data, ensure_ascii=False, default=str)
            except Exception:
                result_data_str = ""

        # 序列化 comparison_results
        comparison_str = ""
        if comparison_results is not None:
            try:
                comparison_str = json.dumps(comparison_results, ensure_ascii=False, default=str)
            except Exception:
                comparison_str = ""

        with conn:
            with conn.cursor() as cur:
                # Upsert ask_session_summaries
                cur.execute("""
                    INSERT INTO ask_session_summaries (session_id, title, first_question, message_count, starred, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, 2, false, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        updated_at = EXCLUDED.updated_at,
                        message_count = ask_session_summaries.message_count + 2
                """, (
                    session_id,
                    question[:128] if question else "",
                    question,
                    user_id,
                    now,
                    now,
                ))

                # 插入用户消息
                cur.execute("""
                    INSERT INTO ask_messages (session_id, role, content, sql, result_data, comparison_results, created_at)
                    VALUES (%s, 'user', %s, '', '', '', %s)
                """, (session_id, question, now))

                # 插入助手消息
                cur.execute("""
                    INSERT INTO ask_messages (session_id, role, content, sql, result_data, comparison_results, created_at)
                    VALUES (%s, 'assistant', %s, %s, %s, %s, %s)
                """, (session_id, answer, sql or "", result_data_str, comparison_str, now))

        conn.close()
        logger.info(f"[_save_v2_session_to_db] 会话已保存: session_id={session_id}")
    except Exception as e:
        logger.warning(f"[_save_v2_session_to_db] 保存失败: {e}")


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
        _refresh_semantic_snapshot_for_request()
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
            analysis=result_state.analysis,
            mode="triggered" if result_state.analysis else "direct",
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
            _saved_filters = [(f.field, f.value) for f in result_state.mql.filters] if result_state.mql.filters else []
            _saved_session_info = f"session_id={session_id}, saved_metric={result_state.mql.metric.name if result_state.mql.metric else None}, saved_dims={[(d.type, d.value) for d in result_state.mql.dimensions] if result_state.mql.dimensions else []}, saved_filters={_saved_filters}"
            logger.info(f"[V2] 保存 MQL 到 session: {_saved_session_info}")

        # 保存会话到 PostgreSQL（ask_session_summaries + ask_messages）
        if result_state and result_state.answer:
            _save_v2_session_to_db(
                session_id=session_id,
                user_id=req.user_id,
                question=req.question,
                answer=result_state.answer or "",
                sql=result_state.sql or "",
                result_data=result_state.sql_result.data if result_state.sql_result else None,
                comparison_results=result_state.context_cache.get("comparison_results") if result_state.context_cache else None,
            )

        # 发送日志到 Go 后端
        try:
            intent_val = ""
            if result_state and result_state.mql and hasattr(result_state.mql, 'intent') and result_state.mql.intent:
                intent_val = result_state.mql.intent.value if hasattr(result_state.mql.intent, 'value') else str(result_state.mql.intent)

            mql_json_str = ""
            if result_state and result_state.mql:
                try:
                    mql_json_str = json.dumps(result_state.mql.to_dict() if hasattr(result_state.mql, 'to_dict') else {}, ensure_ascii=False)
                except Exception:
                    mql_json_str = ""

            success = bool(result_state and result_state.answer)
            fail_stage = ""
            fail_reason = ""
            if not success:
                fail_stage = result_state.error if (result_state and result_state.error) else "no_answer"
                fail_reason = fail_stage

            await _send_log_to_go(
                user_id=req.user_id,
                session_id=session_id,
                question=req.question,
                answer=result_state.answer if result_state else "",
                intent=intent_val,
                success=success,
                fail_stage=fail_stage,
                fail_reason=fail_reason,
                thinking_steps=result_state.thinking_steps if result_state else [],
                sql=result_state.sql if result_state else "",
                mql_json=mql_json_str,
            )
        except Exception as log_err:
            logger.warning(f"[V2] 发送日志失败: {log_err}")

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

        # 发送错误日志到 Go 后端
        try:
            await _send_log_to_go(
                user_id=req.user_id,
                session_id=session_id,
                question=req.question,
                answer=f"处理出错: {str(e)}",
                intent="",
                success=False,
                fail_stage="exception",
                fail_reason=str(e),
                thinking_steps=[],
                sql="",
                mql_json="",
            )
        except Exception as log_err:
            logger.warning(f"[V2] 发送异常日志失败: {log_err}")

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

            _refresh_semantic_snapshot_for_request()

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
                logger.info(f"[V2 Stream] 检查 THINKING 事件: step={step_name}, thinking='{step_state.get('thinking')}'")
                if step_state.get("thinking"):
                    logger.info(f"[V2 Stream] 发送 THINKING 事件: step={step_name}, thinking='{step_state.get('thinking')}'")
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
                        "columns": step_state.get("columns", []),
                        "multi_metric_data": step_state.get("multi_metric_data", []),
                        "dimensional_data": step_state.get("dimensional_data", {}),
                        "category": step_state.get("category", ""),
                        "analysis": step_state.get("analysis"),
                        "health_score": step_state.get("health_score"),
                    }).to_sse()

                # 发送回答（一旦就绪）
                if step_state.get("answer"):
                    yield StreamEvent(SSSEvent.ANSWER_READY, {
                        "answer": step_state["answer"],
                        "suggestions": step_state.get("suggestions", []),
                        "clarification_options": step_state.get("clarification_options", []),
                        "clarification_message": step_state.get("clarification_message", ""),
                        "analysis": step_state.get("analysis"),
                        "mode": step_state.get("mode", "direct"),
                        "multi_metric_data": step_state.get("multi_metric_data", []),
                        "dimensional_data": step_state.get("dimensional_data", {}),
                        "category": step_state.get("category", ""),
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

            # 发送日志到 Go 后端
            if state:
                try:
                    # 获取最终状态
                    answer = getattr(state, 'answer', '') or ''
                    sql = getattr(state, 'sql', '') or ''
                    mql = getattr(state, 'mql', None)
                    thinking_steps = getattr(state, 'thinking_steps', []) or []
                    intent = ""
                    if mql and hasattr(mql, 'intent') and mql.intent:
                        intent = mql.intent.value if hasattr(mql.intent, 'value') else str(mql.intent)

                    # 序列化和获取 MQL JSON
                    mql_json_str = ""
                    if mql:
                        try:
                            mql_json_str = json.dumps(mql.to_dict() if hasattr(mql, 'to_dict') else {}, ensure_ascii=False)
                        except Exception:
                            mql_json_str = ""

                    # 判断成功失败
                    error_val = getattr(state, 'error', None)
                    has_answer = bool(answer and answer.strip())
                    success = has_answer and not error_val

                    logger.info(f"[V2 Stream] 准备发送日志: session_id={session_id}, success={success}, has_answer={has_answer}, answer_len={len(answer)}, thinking_steps={len(thinking_steps)}")

                    # 发送日志
                    await _send_log_to_go(
                        user_id=req.user_id,
                        session_id=session_id,
                        question=req.question,
                        answer=answer,
                        intent=intent,
                        success=success,
                        fail_stage="stream_completed" if has_answer else (error_val or "no_answer"),
                        fail_reason=error_val if not has_answer else "",
                        thinking_steps=thinking_steps,
                        sql=sql,
                        mql_json=mql_json_str,
                    )
                except Exception as log_err:
                    logger.warning(f"[V2 Stream] 发送日志失败: {log_err}")

            # 保存会话到 PostgreSQL
            if state and answer:
                try:
                    sql_result = getattr(state, 'sql_result', None)
                    result_data = sql_result.data if sql_result and hasattr(sql_result, 'data') else None
                    context_cache = getattr(state, 'context_cache', None)
                    comparison_results = context_cache.get("comparison_results") if context_cache else None
                    _save_v2_session_to_db(
                        session_id=session_id,
                        user_id=req.user_id,
                        question=req.question,
                        answer=answer,
                        sql=sql,
                        result_data=result_data,
                        comparison_results=comparison_results,
                    )
                except Exception as db_err:
                    logger.warning(f"[V2 Stream] 保存会话到数据库失败: {db_err}")

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
                columns = sql_result.columns if sql_result and hasattr(sql_result, 'columns') else []
                total = sql_result.total if sql_result and hasattr(sql_result, 'total') else 0

                # 获取 answer 和 suggestions
                answer = getattr(state_update, 'answer', '') or ''
                suggestions = []
                if hasattr(state_update, 'context_cache') and state_update.context_cache:
                    suggestions = state_update.context_cache.get("suggestions", [])

                # 获取触发分析结果
                analysis = getattr(state_update, 'analysis', None)
                mode = "triggered" if analysis else "direct"

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

                # 调试日志：检查 thinking 内容
                logger.info(f"[_stream_graph] step={step_name}, thinking_steps count={len(thinking_steps)}, last_thinking={last_thinking}")
                if last_thinking:
                    logger.info(f"[_stream_graph] last_thinking.content='{last_thinking.content}'")

                yield step_name, {
                    "thinking": last_thinking.content if last_thinking and hasattr(last_thinking, 'content') else '',
                    "entities": last_thinking.entities if last_thinking and hasattr(last_thinking, 'entities') else [],
                    "llm_used": last_thinking.llm_used if last_thinking and hasattr(last_thinking, 'llm_used') else False,
                    "source": last_thinking.source if last_thinking and hasattr(last_thinking, 'source') else None,
                    "sql": getattr(state_update, 'sql', '') or '',
                    "result_data": result_data,
                    "columns": columns,
                    "total": total,
                    "duration_ms": last_thinking.duration_ms if last_thinking and hasattr(last_thinking, 'duration_ms') else 0,
                    "answer": answer,
                    "suggestions": suggestions,
                    # 传递触发分析结果
                    "analysis": analysis,
                    "mode": mode,
                    # 传递多指标下钻数据（用于报告渲染）
                    "multi_metric_data": getattr(state_update, 'multi_metric_data', []),
                    "dimensional_data": getattr(state_update, 'dimensional_data', {}),
                    "category": getattr(state_update, 'category', ''),
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

    # ========== 占比查询：返回占比列名而不是单独的指标名 ==========
    # 当有 molecule_metric 和 denominator_metric 时，说明这是占比查询
    # SQL 会生成一个占比列，列名是 "退款数量占销量比重"
    # 不应该返回 ["退款数量", "销量"]，否则前端会错误映射列名
    molecule_metric = getattr(mql, 'molecule_metric', None)
    denominator_metric = getattr(mql, 'denominator_metric', None)
    if molecule_metric and denominator_metric:
        mol_name = getattr(molecule_metric, 'name', '') or ''
        den_name = getattr(denominator_metric, 'name', '') or ''
        if mol_name and den_name:
            return [f"{mol_name}占{den_name}比重"]
        elif mol_name:
            return [f"{mol_name}占比"]
    # =================================================================

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


# ==================== 会话历史接口 ====================

@router.get("/history/{session_id}")
async def get_v2_history(session_id: str):
    """
    获取 V2 会话历史

    从 PostgreSQL 读取 ask_session_summaries 和 ask_messages 表
    """
    try:
        import psycopg2
        import json

        conn = psycopg2.connect(
            host="192.168.1.225",
            port=5432,
            database="dev_metric",
            user="postgres",
            password="admin123",
        )

        # 1. 查会话摘要
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id, title, first_question, message_count, starred, user_id, created_at, updated_at "
                "FROM ask_session_summaries WHERE session_id = %s",
                (session_id,)
            )
            row = cur.fetchone()
            session_meta = None
            if row:
                session_meta = {
                    "session_id": row[0],
                    "title": row[1],
                    "first_question": row[2],
                    "message_count": row[3],
                    "starred": row[4],
                    "user_id": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                    "updated_at": row[7].isoformat() if row[7] else None,
                }

        # 2. 查消息列表
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, sql, result_data, comparison_results, created_at "
                "FROM ask_messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,)
            )
            rows = cur.fetchall()
            messages = []
            for r in rows:
                result_data = None
                if r[3]:
                    try:
                        result_data = json.loads(r[3])
                    except:
                        pass
                comparison_results = None
                if r[4]:
                    try:
                        comparison_results = json.loads(r[4])
                    except:
                        pass
                messages.append({
                    "role": r[0],
                    "content": r[1],
                    "sql": r[2],
                    "result_data": result_data,
                    "comparison_results": comparison_results,
                    "created_at": r[5].isoformat() if r[5] else None,
                })

        conn.close()

        return {
            "sessions": [session_meta] if session_meta else [],
            "session_id": session_id,
            "messages": messages,
        }

    except Exception as e:
        logger.error(f"[get_v2_history] 获取会话历史失败: {e}")
        return {
            "sessions": [],
            "session_id": session_id,
            "messages": [],
            "error": str(e),
        }


# ==================== 波动分析接口 ====================

class VolatilityRequest(BaseModel):
    """波动分析请求"""
    metric_name: str                          # 指标名称
    data: List[Dict[str, Any]]              # 数据列表，格式：[{date: "2024-01-01", value: 1000, dimension: "京东"}, ...]
    time_range: Optional[Dict[str, str]] = None  # 时间范围
    dimension_key: str = "dimension"         # 维度字段名


@router.post("/v2/volatility/stream")
async def volatility_analysis_stream(req: VolatilityRequest):
    """
    波动分析流式接口

    使用 SSE 流式输出分析结果：
    1. volatility_overview - 基础统计
    2. volatility_chart - 图表数据
    3. volatility_dims - 维度贡献
    4. volatility_llm_reasoning - LLM 推理过程
    5. volatility_root - 根因归类
    6. volatility_done - 完成
    """
    from .nodes.volatility_analyzer import VolatilityAnalyzer

    logger.info(f"[Volatility Stream] 收到分析请求: metric={req.metric_name}, data_count={len(req.data)}")

    analyzer = VolatilityAnalyzer()

    async def generate_sse():
        """生成 SSE 流"""
        try:
            async for event in analyzer.analyze_stream(
                metric_name=req.metric_name,
                data=req.data,
                time_range=req.time_range,
                dimension_key=req.dimension_key
            ):
                yield event.to_sse()
                await asyncio.sleep(0.05)  # 让浏览器有时间渲染

            # 发送空数据表示流结束
            yield b"event: volatility_done\ndata: {}\n\n"

        except Exception as e:
            logger.error(f"[Volatility Stream] 分析失败: {e}")
            yield StreamEvent(SSSEvent.ERROR, {
                "error": f"分析失败: {str(e)}"
            }).to_sse()

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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
