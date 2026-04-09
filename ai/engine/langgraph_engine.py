"""LangGraph 引擎 - 使用 StateGraph 实现"""
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Literal, Union
import httpx

from ai.engine.base import ConversationEngine
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import conversation_nodes
from ai.client.metric_client import MetricClient
from ai.feedback.auto_detector import get_auto_fail_detector
from ai.feedback.collector import get_feedback_collector
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ai.config.logging_config import get_logger

logger = get_logger("ai.engine.langgraph")

GO_API_BASE = "http://localhost:8080"


def create_langgraph_app_with_saver(checkpointer):
    """创建 LangGraph 应用（使用传入的 checkpointer）"""
    workflow = StateGraph(ConversationState)

    # 添加节点
    workflow.add_node("intent", langgraph_intent_node)
    workflow.add_node("entity", langgraph_entity_node)
    workflow.add_node("sql_gen", langgraph_sql_gen_node)
    workflow.add_node("execute", langgraph_execute_node)
    workflow.add_node("comparison", langgraph_comparison_node)
    workflow.add_node("response", langgraph_response_node)

    # 设置入口
    workflow.set_entry_point("intent")

    # 普通边
    workflow.add_edge("intent", "entity")
    workflow.add_edge("entity", "sql_gen")
    workflow.add_edge("execute", "comparison")
    workflow.add_edge("comparison", "response")
    workflow.add_edge("response", END)

    # 条件边：需要追问 vs 继续执行
    workflow.add_conditional_edges(
        "sql_gen",
        should_clarify,
        {
            True: "response",   # 需要追问，等待用户回复
            False: "execute"   # 继续执行查询
        }
    )

    # 编译，使用传入的 MemorySaver 做状态持久化
    return workflow.compile(checkpointer=checkpointer)


def create_langgraph_app():
    """创建 LangGraph 应用（创建新的 MemorySaver）"""
    checkpointer = MemorySaver()
    return create_langgraph_app_with_saver(checkpointer)


def should_clarify(state: ConversationState) -> Literal[True, False]:
    """判断是否需要追问

    注意：对于元数据查询（intent_is_metadata_query=True），
    即使 needs_clarification=True 也需要先执行 execute_node 来获取元数据，
    然后再路由到 response_node。
    """
    if getattr(state, 'needs_clarification', False):
        # 元数据查询需要先执行execute获取数据，即使需要追问也要先执行
        if getattr(state, 'intent_is_metadata_query', False):
            return False  # 先执行，再response
        return True  # 真正需要用户确认的情况
    return False


# === LangGraph 节点函数 ===

def langgraph_intent_node(state: ConversationState) -> Dict[str, Any]:
    """意图识别节点"""
    updates = conversation_nodes.intent_node(state)
    return {
        "current_intent": updates.get("current_intent"),
        "entities": updates.get("entities", {}),
        # 返回 thinking_steps 以便 LangGraph 持久化
        "thinking_steps": state.thinking_steps,
    }


def langgraph_entity_node(state: ConversationState) -> Dict[str, Any]:
    """实体链接节点"""
    updates = conversation_nodes.entity_node(state)

    # 处理 entities 合并（处理字段清除）
    new_entities = updates.get("entities", {})
    for key in ["metric_name", "metric_code", "unit", "starrocks_sql"]:
        if key in new_entities and new_entities[key] is None:
            state.entities.pop(key, None)
            del new_entities[key]

    return {
        "entities": new_entities,
        "needs_clarification": updates.get("needs_clarification", False),
        "clarification_message": updates.get("clarification_message"),
        "clarification_type": updates.get("clarification_type"),
        "matched_metrics": updates.get("matched_metrics"),
        # 返回 thinking_steps 以便 LangGraph 持久化
        "thinking_steps": state.thinking_steps,
    }


def langgraph_sql_gen_node(state: ConversationState) -> Dict[str, Any]:
    """SQL 生成节点 - 使用 QueryBuilder"""
    updates = conversation_nodes.sql_build_node(state)

    # 处理分页
    sql = updates.get("generated_sql")
    if sql and sql not in ["METADATA_QUERY", "NONE"]:
        page_size = min(getattr(state, 'page_size', 10), 1000)
        page = getattr(state, 'page', 1)
        sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+OFFSET\s+\d+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+', ' ', sql).strip()
        sql = f"{sql} LIMIT {page_size} OFFSET {(page - 1) * page_size}"

    # sql_gen_node 可能直接设置 state 属性而不是在返回字典中
    # 例如 clarification_message, clarification_type, matched_metrics
    # 需要同时从 updates 和 state 中获取
    clarification_message = updates.get("clarification_message")
    if clarification_message is None:
        clarification_message = getattr(state, 'clarification_message', None)

    clarification_type = updates.get("clarification_type")
    if clarification_type is None:
        clarification_type = getattr(state, 'clarification_type', None)

    matched_metrics = updates.get("matched_metrics")
    if matched_metrics is None:
        matched_metrics = getattr(state, 'matched_metrics', None)

    needs_clarification = updates.get("needs_clarification", False)
    if not needs_clarification:
        needs_clarification = getattr(state, 'needs_clarification', False)

    return {
        "generated_sql": sql,
        "sql_params": updates.get("sql_params", {}),
        "needs_clarification": needs_clarification,
        "clarification_message": clarification_message,
        "clarification_type": clarification_type,
        "matched_metrics": matched_metrics,
        "applied_defaults": updates.get("applied_defaults", {}),
        "intent_is_metadata_query": getattr(state, 'intent_is_metadata_query', False),
        # 返回 thinking_steps 以便 LangGraph 持久化
        "thinking_steps": state.thinking_steps,
    }


async def langgraph_execute_node(state: ConversationState) -> Dict[str, Any]:
    """执行查询节点"""
    updates = await conversation_nodes.execute_node(state)
    result = {
        "sql_result": updates.get("sql_result"),
        "error": updates.get("error"),
        "last_valid_metric": updates.get("last_valid_metric", {}),
    }
    # 传递 execute_node 直接设置到 state 的字段
    # execute_node 会直接修改 state.xxx，所以需要同步到返回字典
    if updates.get("needs_clarification") is not None:
        result["needs_clarification"] = updates.get("needs_clarification")
    elif getattr(state, 'needs_clarification', False):
        result["needs_clarification"] = getattr(state, 'needs_clarification', False)
    if getattr(state, 'clarification_message', None):
        result["clarification_message"] = getattr(state, 'clarification_message')
    if getattr(state, 'clarification_type', None):
        result["clarification_type"] = getattr(state, 'clarification_type')
    if updates.get("matched_metrics"):
        result["matched_metrics"] = updates.get("matched_metrics")
    elif getattr(state, 'matched_metrics', None):
        result["matched_metrics"] = getattr(state, 'matched_metrics')
    # 返回 thinking_steps 以便 LangGraph 持久化
    result["thinking_steps"] = state.thinking_steps
    return result


async def langgraph_comparison_node(state: ConversationState) -> Dict[str, Any]:
    """对比计算节点"""
    updates = await conversation_nodes.comparison_node(state)
    result =  {
        "comparison_results": updates.get("comparison_results"),
        # 返回 thinking_steps 以便 LangGraph 持久化
        "thinking_steps": state.thinking_steps,
    }
    return result


def langgraph_response_node(state: ConversationState) -> Dict[str, Any]:
    """生成回答节点"""
    updates = conversation_nodes.response_node(state)
    # 保留 state 中的 comparison_results（response_node 某些早期返回可能没有包含它）
    comparison_results = updates.get("comparison_results")
    if comparison_results is None:
        comparison_results = getattr(state, 'comparison_results', None)
    # 缓存到 state 对象，这样 LangGraph 的 reducer 能持久化到 MemorySaver
    state.answer = updates.get("answer", "")
    state.result_data = updates.get("result_data")
    return {
        "answer": state.answer,
        "suggest_questions": updates.get("suggest_questions", []),
        "needs_clarification": updates.get("needs_clarification", False),
        "result_data": state.result_data,
        "comparison_results": comparison_results,
        # 关键：必须返回 conversation_context 才能被 MemorySaver 持久化
        "conversation_context": state.conversation_context,
        # thinking_steps 也需要返回才能被持久化
        "thinking_steps": state.thinking_steps,
    }


class LangGraphEngine(ConversationEngine):
    """基于 LangGraph StateGraph 的对话引擎"""

    # 类变量：所有实例共享同一个 app 和 MemorySaver
    _app = None
    _memory_saver = None

    def __init__(self):
        # 确保 app 只创建一次（所有实例共享同一个 MemorySaver 状态）
        if LangGraphEngine._app is None:
            LangGraphEngine._memory_saver = MemorySaver()
            LangGraphEngine._app = create_langgraph_app_with_saver(LangGraphEngine._memory_saver)
        self.app = LangGraphEngine._app
        self.sessions = {}  # 仅用于兼容，实际用 checkpointer
        self.session_metadata = {}
        self.metric_client = MetricClient()

    async def process(
        self,
        question: str,
        session_id: str,
        page: int = 1,
        page_size: int = 10,
        user_id: str = "default",
        dept_id: int = 0,
        data_filter: str = ""
    ) -> Dict[str, Any]:
        """处理对话请求"""
        config = {"configurable": {"thread_id": session_id}}

        try:
            # 获取当前状态
            current_state = await self.app.aget_state(config)
            logger.info(f"[LangGraphEngine] aget_state session={session_id}, current_state type={type(current_state)}")
            if current_state is not None:
                logger.info(f"[LangGraphEngine] conversation_context in restored state = {current_state.values.get('conversation_context')}")
                logger.info(f"[LangGraphEngine] entities in restored state = {current_state.values.get('entities')}")

            if current_state is None:
                # 新会话 - 初始化状态
                initial_state = {
                    "session_id": session_id,
                    "messages": [],
                    "entities": {},
                    "current_intent": None,
                    "generated_sql": None,
                    "sql_params": {},
                    "metric_id": None,
                    "error": None,
                    "needs_clarification": False,
                    "clarification_message": None,
                    "clarification_type": None,
                    "matched_metrics": None,
                    "suggest_questions": [],
                    "intent_is_metadata_query": False,
                    "explicit_value_query": False,
                    "skip_execution": False,
                    "sql_result": None,
                    "last_valid_metric": {},
                    "asked_fields": [],
                    "pending_clarification": {},
                    "clarification_count": 0,
                    "max_clarification_turns": 3,
                    "default_values": {"time_range": "last_7_days", "dimension": "all"},
                    "applied_defaults": {},
                    "thinking_steps": [],
                    "context": {},
                    "conversation_context": None,
                    "comparison_results": None,
                    "selected_dimension_field": None,
                    "selected_dimension_value": None,
                    "dimension_value_candidates": None,
                    "dimension_value_matched_text": None,
                    "page": page,
                    "page_size": page_size,
                    "user_id": user_id,
                    "dept_id": dept_id,
                    "data_filter": data_filter,
                }
            else:
                # 复用现有状态
                initial_state = current_state.values
                initial_state["page"] = page
                initial_state["page_size"] = page_size
                # 清除上轮状态
                initial_state["needs_clarification"] = False
                initial_state["clarification_message"] = None
                initial_state["clarification_type"] = None
                initial_state["matched_metrics"] = None
                initial_state["error"] = None
                initial_state["comparison_results"] = None
                initial_state["sql_result"] = None
                initial_state["thinking_steps"] = []

            # 添加用户消息
            if "messages" not in initial_state:
                initial_state["messages"] = []
            initial_state["messages"].append(ConversationMessage(
                role="user",
                content=question
            ))

            # 保存用户消息到 Go 后端
            self._save_message_to_go(session_id, "user", question)

            # 执行图
            result = await self.app.ainvoke(initial_state, config=config)

            # 获取最终状态
            final_state = result

            # 构建 ConversationState 对象用于 response_node
            # 因为 ConversationState 不包含 answer/result_data 字段，
            # 需要在 process() 中直接调用 response_node 获取响应
            response_state = ConversationState(
                session_id=final_state.get("session_id", session_id),
                messages=final_state.get("messages", []),
                entities=final_state.get("entities", {}),
                current_intent=final_state.get("current_intent"),
                generated_sql=final_state.get("generated_sql"),
                sql_params=final_state.get("sql_params", {}),
                metric_id=final_state.get("metric_id"),
                error=final_state.get("error"),
                needs_clarification=final_state.get("needs_clarification", False),
                clarification_message=final_state.get("clarification_message"),
                clarification_type=final_state.get("clarification_type"),
                matched_metrics=final_state.get("matched_metrics"),
                suggest_questions=final_state.get("suggest_questions", []),
                intent_is_metadata_query=final_state.get("intent_is_metadata_query", False),
                explicit_value_query=final_state.get("explicit_value_query", False),
                skip_execution=final_state.get("skip_execution", False),
                sql_result=final_state.get("sql_result"),
                last_valid_metric=final_state.get("last_valid_metric", {}),
                asked_fields=final_state.get("asked_fields", []),
                pending_clarification=final_state.get("pending_clarification", {}),
                clarification_count=final_state.get("clarification_count", 0),
                max_clarification_turns=final_state.get("max_clarification_turns", 3),
                default_values=final_state.get("default_values", {"time_range": "last_7_days", "dimension": "all"}),
                applied_defaults=final_state.get("applied_defaults", {}),
                thinking_steps=final_state.get("thinking_steps", []),
                context=final_state.get("context", {}),
                conversation_context=final_state.get("conversation_context"),
                comparison_results=final_state.get("comparison_results"),
                selected_dimension_field=final_state.get("selected_dimension_field"),
                selected_dimension_value=final_state.get("selected_dimension_value"),
                dimension_value_candidates=final_state.get("dimension_value_candidates"),
                dimension_value_matched_text=final_state.get("dimension_value_matched_text"),
                page=final_state.get("page", page),
                page_size=final_state.get("page_size", page_size),
            )

            # 直接调用 response_node 获取响应（不使用 langgraph_response_node，因为它的返回值无法写入 ConversationState）
            # 优化：如果 final_state 已有缓存的 answer/result_data（LangGraph 节点内第一次生成的结果），
            # 说明 graph 内的 response_node 已经执行过，直接复用结果即可
            cached_answer = final_state.get("answer")
            cached_result_data = final_state.get("result_data")
            if cached_answer is not None or cached_result_data is not None:
                response_updates = {
                    "answer": cached_answer or "",
                    "result_data": cached_result_data,
                    "suggest_questions": final_state.get("suggest_questions", []),
                    "needs_clarification": final_state.get("needs_clarification", False),
                }
            else:
                response_updates = conversation_nodes.response_node(response_state)

            # 自动失败检测（需要 ConversationState 对象，创建适配器）
            class StateAdapter:
                """将 dict 适配为支持 .entities .metric_id 等属性的对象"""
                def __init__(self, d):
                    self.__dict__.update(d)
                    self.entities = d.get("entities", {})
                    self.metric_id = d.get("metric_id")
                    self.current_intent = d.get("current_intent")
                    self.generated_sql = d.get("generated_sql")
                    self.error = d.get("error")
                    self.needs_clarification = d.get("needs_clarification")
                    self.messages = d.get("messages", [])
                    self.session_id = d.get("session_id")
            auto_detector = get_auto_fail_detector()
            fail_result = auto_detector.detect_failure(
                state=StateAdapter(final_state),
                result=final_state.get("sql_result"),
                error=final_state.get("error")
            )

            if fail_result.is_failure:
                collector = get_feedback_collector()
                collector.record_auto_feedback(
                    session_id=session_id,
                    turn_index=len(final_state.get("messages", [])) // 2,
                    fail_reason=fail_result.fail_reason.value,
                    clarification_type=final_state.get("clarification_type"),
                    clarification_question=final_state.get("clarification_message"),
                    metric_id=final_state.get("metric_id"),
                    context_snapshot=fail_result.context_for_debug,
                    raw_llm_output=None
                )

            # 获取当前 SQL
            current_sql = final_state.get("generated_sql")
            if current_sql and current_sql in ["METADATA_QUERY", "NONE"]:
                current_sql = None

            # 添加助手消息
            assistant_content = response_updates.get("answer", "抱歉，我无法回答这个问题。")
            if "messages" not in final_state:
                final_state["messages"] = []
            final_state["messages"].append(ConversationMessage(
                role="assistant",
                content=assistant_content,
                sql=current_sql
            ))

            # 保存助手消息
            self._save_message_to_go(
                session_id, "assistant", assistant_content, current_sql,
                result_data=response_updates.get("result_data"),
                comparison_results=response_updates.get("comparison_results"),
                drill_down_dims=self._get_drill_down_dims(final_state),
                breadcrumbs=[],
                metric_code=final_state.get("entities", {}).get("metric_code")
            )

            # 准备思考步骤
            thinking_steps = []
            for step in final_state.get("thinking_steps", []):
                if hasattr(step, 'dict'):
                    thinking_steps.append({
                        "step": step.step,
                        "status": step.status,
                        "content": step.content,
                        "timestamp": step.timestamp.isoformat() if step.timestamp else None,
                        "llm_used": step.llm_used
                    })
                elif isinstance(step, dict):
                    thinking_steps.append(step)

            # 构建响应
            return {
                "session_id": session_id,
                "answer": response_updates.get("answer", "抱歉，我无法回答这个问题。"),
                "suggest": response_updates.get("suggest_questions", []),
                "sql": current_sql,
                "thinking_steps": thinking_steps if thinking_steps else None,
                "needs_clarification": response_updates.get("needs_clarification", final_state.get("needs_clarification")),
                "clarification_message": response_updates.get("clarification_message", final_state.get("clarification_message")),
                "clarification_type": response_updates.get("clarification_type", final_state.get("clarification_type")),
                "matched_metrics": response_updates.get("matched_metrics", final_state.get("matched_metrics")),
                "dimension_value_candidates": final_state.get("dimension_value_candidates"),
                "dimension_value_matched_text": final_state.get("dimension_value_matched_text"),
                "drill_down_dims": self._get_drill_down_dims(final_state),
                "breadcrumbs": [],
                "result_data": self._rename_result_columns(
                    response_updates.get("result_data"),
                    self._get_metric_name_for_result(final_state)
                ),
                "total": self._extract_result_total(final_state.get("sql_result")),
                "page": page,
                "page_size": page_size,
                "comparison_results": response_updates.get("comparison_results", final_state.get("comparison_results")),
                "metric_code": final_state.get("entities", {}).get("metric_code")
            }

        except Exception as e:
            logger.error(f"LangGraphEngine 处理出错: {e}")
            import traceback
            traceback.print_exc()
            return {
                "session_id": session_id,
                "answer": f"处理出错: {str(e)}",
                "suggest": ["请尝试换一种问法"],
                "sql": None,
                "thinking_steps": None,
                "needs_clarification": None,
                "clarification_message": None,
                "clarification_type": None,
                "matched_metrics": None,
                "dimension_value_candidates": None,
                "dimension_value_matched_text": None,
                "drill_down_dims": None,
                "breadcrumbs": None,
                "result_data": None,
                "total": None,
                "page": page,
                "page_size": page_size,
                "comparison_results": None,
                "metric_code": None
            }

    def _save_message_to_go(
        self,
        session_id: str,
        role: str,
        content: str,
        sql: str = None,
        result_data: Any = None,
        comparison_results: Any = None,
        drill_down_dims: Any = None,
        breadcrumbs: Any = None,
        metric_code: str = None
    ):
        """保存消息到 Go 后端"""
        try:
            payload = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "sql": sql or "",
                "result_data": json.dumps(result_data) if result_data is not None else "",
                "comparison_result": json.dumps(comparison_results) if comparison_results is not None else "",
                "drill_down_dims": json.dumps(drill_down_dims) if drill_down_dims is not None else "",
                "breadcrumbs": json.dumps(breadcrumbs) if breadcrumbs is not None else "",
                "metric_code": metric_code or ""
            }
            with httpx.Client(timeout=5) as client:
                client.post(f"{GO_API_BASE}/api/v1/ask/messages", json=payload)
        except Exception as e:
            logger.warning(f"保存消息到 Go 失败: {e}")

    def _extract_result_data(self, sql_result) -> Optional[List[Dict[str, Any]]]:
        """从 SQL 执行结果中提取数据列表"""
        if sql_result is None:
            return None
        if isinstance(sql_result, list):
            return sql_result
        if isinstance(sql_result, dict):
            data = sql_result.get("data", {})
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("data")
        return None

    def _extract_result_total(self, sql_result) -> Optional[int]:
        """从 SQL 执行结果中提取总数"""
        if sql_result is None:
            return None
        if isinstance(sql_result, dict):
            if "count" in sql_result:
                return sql_result.get("count")
            data = sql_result.get("data", {})
            if isinstance(data, dict):
                return data.get("count")
        return None

    def _get_metric_name_for_result(self, state: Dict[str, Any]) -> Dict[str, str]:
        """获取指标字段名到中文名称的映射"""
        field_name_map = {}
        try:
            all_metrics = self.metric_client.get_all_metrics()
        except:
            return field_name_map

        entities = state.get("entities", {})
        metric_code = entities.get("metric_code")

        target_metric = None
        if metric_code:
            for m in all_metrics:
                if m.get("metric_code") == metric_code:
                    target_metric = m
                    break

        if target_metric:
            starrocks_sql = target_metric.get("starrocks_sql", "") or ""
            field_matches = re.findall(r'(?:sum\()?\s*([\w]+)\s*\)?\s*(?:as\s*`?([\w]+)`?)?', starrocks_sql, re.IGNORECASE)
            if any(m[1] for m in field_matches):
                field_matches = [m[1] if m[1] else m[0] for m in field_matches]
            metric_name = target_metric.get("name", metric_code)
            for field in field_matches:
                field_upper = field.upper()
                if field_upper not in field_name_map:
                    field_name_map[field_upper] = metric_name

        return field_name_map

    def _rename_result_columns(self, result_data: Optional[List[Dict[str, Any]]], metric_name_map: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
        """重命名结果列名为中文"""
        if not result_data or not metric_name_map:
            return result_data
        renamed = []
        for row in result_data:
            new_row = {}
            for key, value in row.items():
                new_key = metric_name_map.get(key.upper(), key)
                new_row[new_key] = value
            renamed.append(new_row)
        return renamed

    def _get_drill_down_dims(self, state: Dict[str, Any]) -> Optional[List[Dict[str, str]]]:
        """获取下钻维度"""
        drill_down_dims = state.get("drill_down_dims")
        if drill_down_dims:
            return drill_down_dims

        generated_sql = state.get("generated_sql")
        if not generated_sql or generated_sql in ["METADATA_QUERY", "NONE"]:
            return None

        entities = state.get("entities", {})
        metric_code = entities.get("metric_code")
        if not metric_code:
            return None

        # 获取当前分组维度，用于过滤（统一转大写避免大小写问题）
        current_dimension = entities.get("dimension", "").upper()

        # 时间维度列表 - 不作为下钻维度
        time_dimension_keywords = ["日", "月", "年", "周", "天", "DAY", "MONTH", "YEAR", "WEEK"]

        try:
            metric = self.metric_client.get_metric_by_code(metric_code)
            if metric:
                # 优先从 dimension_configs 表获取维度（按 starrocks_sql 中的表名）
                starrocks_sql = metric.get("starrocks_sql", "")
                if starrocks_sql:
                    # 提取表名（FROM 后到第一个空格或换行）
                    import re
                    match = re.search(r'FROM\s+([^\s\n]+)', starrocks_sql, re.IGNORECASE)
                    if match:
                        table_name = match.group(1).strip()
                        configs = self.metric_client.get_dimension_configs(table_name)
                        if configs:
                            filtered_dims = []
                            for d in configs:
                                if d.get("status") != 1:
                                    continue
                                dim_name = d.get("dimension_name", "")
                                dim_name_upper = dim_name.upper()
                                # 过滤时间维度
                                if dim_name_upper in time_dimension_keywords:
                                    continue
                                # 过滤当前分组维度（忽略大小写）
                                if dim_name_upper == current_dimension:
                                    continue
                                filtered_dims.append({
                                    "dimension_name": dim_name,
                                    "dimension_field": d.get("column_name")
                                })
                            return filtered_dims if filtered_dims else None

                # Fallback: 从 metric_dimensions 获取
                dimensions = metric.get("dimensions", [])
                if dimensions:
                    filtered_dims = []
                    for d in dimensions:
                        dim_name = d.get("dimension_name", "")
                        dim_name_upper = dim_name.upper()
                        if dim_name_upper in time_dimension_keywords:
                            continue
                        if dim_name_upper == current_dimension:
                            continue
                        filtered_dims.append({
                            "dimension_name": dim_name,
                            "dimension_field": d.get("column_name")
                        })
                    return filtered_dims if filtered_dims else None

                # Fallback: 使用 common_dimensions
                common_dims = metric.get("common_dimensions", "")
                if common_dims:
                    dim_names = [d.strip() for d in common_dims.split("、") if d.strip()]
                    filtered = [
                        {"dimension_name": name, "dimension_field": name}
                        for name in dim_names
                        if name.upper() not in time_dimension_keywords and name.upper() != current_dimension
                    ]
                    return filtered if filtered else None
        except Exception as e:
            logger.error(f"获取下钻维度失败: {e}")
        return None

    async def get_state(self, session_id: str) -> Optional[ConversationState]:
        config = {"configurable": {"thread_id": session_id}}
        state = await self.app.aget_state(config)
        return state.values if state else None
