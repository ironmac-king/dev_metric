"""
Python AI 服务 - 智能问数
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import conversation_nodes
from ai.feedback.auto_detector import get_auto_fail_detector, FailReason
from ai.feedback.collector import get_feedback_collector, FeedbackType
from ai.feedback.analyzer import get_feedback_analyzer
from ai.feedback.rule_optimizer import get_rule_optimizer

app = FastAPI(title="智能问数服务")

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 会话存储 (生产环境用 Redis)
sessions = {}
# 会话元数据
session_metadata = {}


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class ThinkingStepResponse(BaseModel):
    """思考步骤响应"""
    step: str
    status: str
    content: Optional[str] = None
    timestamp: Optional[str] = None


class AskResponse(BaseModel):
    session_id: str
    answer: str
    suggest: List[str]
    sql: Optional[str] = None
    thinking_steps: Optional[List[ThinkingStepResponse]] = None


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """智能问数接口"""
    # 获取或创建会话
    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in sessions:
        sessions[session_id] = ConversationState(session_id=session_id)
        session_metadata[session_id] = {
            "id": session_id,
            "title": req.question[:20] + "..." if len(req.question) > 20 else req.question,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    state = sessions[session_id]

    # 清除上一轮的错误状态，开始新一轮查询
    state.needs_clarification = False
    state.clarification_message = None
    state.error = None
    # 清空思考步骤
    state.thinking_steps = []

    # 添加用户消息
    state.messages.append(ConversationMessage(
        role="user",
        content=req.question
    ))

    # 执行对话流程
    try:
        # 意图识别
        intent_updates = conversation_nodes.intent_node(state)
        state.current_intent = intent_updates.get("current_intent")
        state.entities.update(intent_updates.get("entities", {}))

        # 实体链接
        entity_updates = conversation_nodes.entity_node(state)
        # 使用解包合并而不是update，这样可以处理字段清除的情况
        # 如果entity_node返回的entities中有值为None的字段，表示需要清除
        new_entities = entity_updates.get("entities", {})
        for key in ["metric_name", "metric_code", "metric_id", "unit", "starrocks_sql"]:
            if key in new_entities and new_entities[key] is None:
                # 字段被清除
                state.entities.pop(key, None)
                del new_entities[key]
        state.entities.update(new_entities)

        # SQL 生成
        sql_updates = conversation_nodes.sql_gen_node(state)
        state.generated_sql = sql_updates.get("generated_sql")
        state.sql_params = sql_updates.get("sql_params", {})
        # 处理 intent_is_metadata_query
        if "intent_is_metadata_query" in sql_updates:
            state.intent_is_metadata_query = sql_updates.get("intent_is_metadata_query")
        # 处理默认值应用
        if sql_updates.get("applied_defaults"):
            state.applied_defaults = sql_updates.get("applied_defaults")
        if sql_updates.get("needs_clarification"):
            state.needs_clarification = True
            state.clarification_message = sql_updates.get("clarification_message")
            state.clarification_type = sql_updates.get("clarification_type")
            state.matched_metrics = sql_updates.get("matched_metrics")
            print(f"[DEBUG main] 设置追问状态: clarification_type={state.clarification_type}, matched_metrics数量={len(state.matched_metrics) if state.matched_metrics else 0}")

        # 执行查询
        execute_updates = conversation_nodes.execute_node(state)

        # 生成回答
        response_updates = conversation_nodes.response_node(state)

        # 自动失败检测
        auto_detector = get_auto_fail_detector()
        fail_result = auto_detector.detect_failure(
            state=state,
            result=state.sql_result,
            error=state.error
        )

        if fail_result.is_failure:
            # 记录自动失败反馈
            collector = get_feedback_collector()
            collector.record_auto_feedback(
                session_id=session_id,
                turn_index=len(state.messages) // 2,
                fail_reason=fail_result.fail_reason.value,
                clarification_type=getattr(state, 'clarification_type', None),
                clarification_question=getattr(state, 'clarification_message', None),
                metric_id=state.metric_id,
                context_snapshot=fail_result.context_for_debug,
                raw_llm_output=None
            )

        # 获取当前 SQL（如果助手消息需要显示）
        current_sql = state.generated_sql if state.generated_sql and state.generated_sql != "METADATA_QUERY" else None

        # 添加助手消息
        state.messages.append(ConversationMessage(
            role="assistant",
            content=response_updates.get("answer", "抱歉，我无法回答这个问题。"),
            sql=current_sql
        ))

        # 更新会话元数据
        if session_id in session_metadata:
            session_metadata[session_id]["updated_at"] = datetime.now().isoformat()

        # 准备思考步骤
        thinking_steps = []
        for step in state.thinking_steps:
            thinking_steps.append(ThinkingStepResponse(
                step=step.step,
                status=step.status,
                content=step.content,
                timestamp=step.timestamp.isoformat() if step.timestamp else None
            ))

        return AskResponse(
            session_id=session_id,
            answer=response_updates.get("answer", "抱歉，我无法回答这个问题。"),
            suggest=response_updates.get("suggest_questions", []),
            sql=current_sql,
            thinking_steps=thinking_steps if thinking_steps else None
        )

    except Exception as e:
        return AskResponse(
            session_id=session_id,
            answer=f"处理出错: {str(e)}",
            suggest=["请尝试换一种问法"]
        )


@app.get("/api/v1/ask/history")
async def get_history(session_id: str):
    """获取对话历史"""
    if session_id and session_id in sessions:
        state = sessions[session_id]
        messages = [
            {
                "role": m.role,
                "content": m.content,
                "sql": m.sql,
                "created_at": m.timestamp.isoformat() if m.timestamp else None
            }
            for m in state.messages
        ]
    else:
        messages = []

    # 返回会话列表和当前会话消息
    sessions_list = [
        {
            "id": meta["id"],
            "title": meta["title"],
            "updated_at": meta["updated_at"]
        }
        for meta in sorted(session_metadata.values(), key=lambda x: x["updated_at"], reverse=True)
    ]

    return {
        "sessions": sessions_list,
        "session_id": session_id,
        "messages": messages
    }


@app.post("/api/v1/ask/clear")
async def clear_session(session_id: str):
    """清除会话"""
    if session_id in sessions:
        del sessions[session_id]
    if session_id in session_metadata:
        del session_metadata[session_id]
    return {"message": "会话已清除"}


@app.get("/api/v1/ask/suggest")
async def get_suggest():
    """获取问题建议"""
    return {
        "suggests": [
            "昨天的访客数是多少",
            "本周的订单量",
            "本月销售额趋势",
            "环比上周怎么样",
        ]
    }


class FeedbackRequest(BaseModel):
    session_id: str
    turn_index: int
    feedback: int  # 1=positive, -1=negative


class FeedbackResponse(BaseModel):
    success: bool
    message: str


@app.post("/api/v1/ask/feedback", response_model=FeedbackResponse)
async def submit_feedback(req: FeedbackRequest):
    """提交反馈（点赞/点踩）"""
    collector = get_feedback_collector()

    # 获取会话状态
    state = sessions.get(req.session_id)
    if not state:
        return FeedbackResponse(
            success=False,
            message="会话不存在"
        )

    # 转换反馈值
    feedback_type = FeedbackType.POSITIVE if req.feedback == 1 else FeedbackType.NEGATIVE

    # 记录反馈
    collector.record_user_feedback(
        session_id=req.session_id,
        turn_index=req.turn_index,
        feedback=feedback_type,
        metric_id=state.metric_id,
        clarification_type=getattr(state, 'clarification_type', None),
        clarification_question=getattr(state, 'clarification_message', None),
    )

    return FeedbackResponse(
        success=True,
        message="反馈成功"
    )


# ============ 优化建议管理 API ============

class SuggestionResponse(BaseModel):
    """优化建议响应"""
    id: int
    suggestion_type: str
    target_table: str
    target_id: Optional[int]
    original_value: Optional[str]
    suggested_value: str
    fail_count: int
    confidence: float
    reason: Optional[str]
    created_at: str
    status: str


class ApplyRequest(BaseModel):
    applied_by: str = "admin"


class IgnoreRequest(BaseModel):
    pass


@app.get("/api/v1/feedback/suggestions")
async def get_suggestions():
    """获取待审核的优化建议列表"""
    analyzer = get_feedback_analyzer()
    suggestions = analyzer.get_unhandled_suggestions()

    return {
        "data": [
            SuggestionResponse(
                id=s["id"],
                suggestion_type=s["suggestion_type"],
                target_table=s["target_table"],
                target_id=s["target_id"],
                original_value=s["original_value"],
                suggested_value=s["suggested_value"],
                fail_count=s["fail_count"],
                confidence=s["confidence"],
                reason=s["reason"],
                created_at=s["created_at"],
                status="pending"
            )
            for s in suggestions
        ]
    }


@app.post("/api/v1/feedback/suggestions/{suggestion_id}/apply")
async def apply_suggestion(suggestion_id: int, req: ApplyRequest = ApplyRequest()):
    """应用优化建议"""
    optimizer = get_rule_optimizer()
    success = optimizer.apply_suggestion(suggestion_id, req.applied_by)

    if success:
        return {"success": True, "message": "建议已应用"}
    else:
        return {"success": False, "message": "应用失败"}


@app.post("/api/v1/feedback/suggestions/{suggestion_id}/ignore")
async def ignore_suggestion(suggestion_id: int):
    """忽略优化建议"""
    optimizer = get_rule_optimizer()
    success = optimizer.ignore_suggestion(suggestion_id)

    if success:
        return {"success": True, "message": "已忽略该建议"}
    else:
        return {"success": False, "message": "操作失败"}


@app.post("/api/v1/feedback/analyze")
async def trigger_analysis():
    """手动触发一次分析（用于测试）"""
    from ai.scheduler import get_daily_scheduler
    scheduler = get_daily_scheduler()
    if scheduler:
        scheduler.run_now()
        return {"success": True, "message": "分析已触发"}
    return {"success": False, "message": "调度器未启动"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # 启动每日调度器
    from ai.scheduler import start_daily_scheduler
    start_daily_scheduler()
    print("[启动] AI 服务已启动，调度器运行中...")
    uvicorn.run(app, host="0.0.0.0", port=8081)
