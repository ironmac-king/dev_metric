"""
LLM Query Engine - 基于 QueryState JSON 的对话引擎

使用 LLM 生成 QueryState，通过 QueryBuilder 生成 SQL
"""
from datetime import datetime
from typing import Dict, Any, Optional
from ai.engine.base import ConversationEngine
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import conversation_nodes
from ai.client.metric_client import MetricClient
from ai.sql_gen.generator import SQLGenerator
from ai.sql_gen.query_builder import QueryBuilder, QueryState, TimeSpec, ComparisonSpec, PaginationSpec
from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_query_engine")


class LLMQueryEngine(ConversationEngine):
    """
    LLM Query Engine - 使用 LLM 生成 QueryState

    流程:
    1. query_state_node - LLM 生成 QueryState
    2. sql_build_node - 使用 QueryBuilder 生成 SQL
    3. execute_node - 执行 SQL
    4. response_node - 生成回答
    """

    def __init__(self):
        self.sessions: Dict[str, ConversationState] = {}
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
        self.metric_client = MetricClient()
        self.sql_generator = SQLGenerator()

    async def process(
        self,
        question: str,
        session_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """处理对话请求"""
        # 获取或创建会话
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationState(session_id=session_id)
            self.session_metadata[session_id] = {
                "id": session_id,
                "title": question[:20] + "..." if len(question) > 20 else question,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

        state = self.sessions[session_id]
        state.thinking_steps = []

        # 添加用户消息
        state.messages.append(ConversationMessage(
            role="user",
            content=question
        ))

        try:
            # === Step 1: LLM 生成 QueryState ===
            query_state_result = conversation_nodes.query_state_node(state)
            if query_state_result.get("needs_clarification"):
                return await self._build_clarification_response(state, query_state_result)

            query_state = query_state_result.get("query_state", {})
            state._query_state = query_state

            # === Step 2: 使用 QueryBuilder 生成 SQL ===
            builder = QueryBuilder()

            # 构建 QueryState 对象
            metric_info = query_state.get("metric", {})
            time_info = query_state.get("time", {})

            # 补充 metric 元数据
            metric_code = metric_info.get("code")
            if metric_code:
                metric = self.metric_client.get_metric_by_code(metric_code)
                if metric:
                    metric_info["starrocks_table"] = metric.get("starrocks_table")
                    metric_info["starrocks_sql"] = metric.get("starrocks_sql")
                    metric_info["unit"] = metric.get("unit")

            # 构建 QueryState
            from ai.sql_gen.query_builder import QueryDimension
            dims = []
            for d in query_state.get("dimensions", []):
                dims.append(QueryDimension(
                    type=d.get("type", ""),
                    column=d.get("column", ""),
                    field=d.get("field", ""),
                    value=d.get("value")
                ))

            qstate = QueryState(
                version="1.0",
                session_id=session_id,
                intent=query_state.get("intent", "query_value"),
                confidence=query_state.get("confidence", 0.9),
                metric=metric_info,
                time=TimeSpec(
                    type=time_info.get("type", "date_range"),
                    start=time_info.get("start"),
                    end=time_info.get("end"),
                    original_expr=time_info.get("original_expr")
                ),
                dimensions=dims,
                pagination=PaginationSpec(page=page, page_size=page_size),
                comparison=ComparisonSpec(
                    enabled=query_state.get("comparison", {}).get("enabled", False),
                    types=query_state.get("comparison", {}).get("types", [])
                )
            )

            # 生成 SQL
            sql_result = builder.build_sql(qstate)
            generated_sql = sql_result.get("sql", "")
            comparison_sqls = sql_result.get("comparison_sqls", [])

            # 记录 SQL 生成步骤
            for step in sql_result.get("thinking_steps", []):
                from ai.graph.state import ThinkingStep
                state.thinking_steps.append(ThinkingStep(
                    step=step.get("step", ""),
                    status=step.get("status", "completed"),
                    content=step.get("detail", "")
                ))

            # === Step 3: 执行 SQL ===
            sql_result_data = None
            total = 0
            if generated_sql and generated_sql not in ["METADATA_QUERY", "NONE"]:
                result = await self.sql_generator.execute(generated_sql, {})
                if result:
                    data = result.get("data", {})
                    if isinstance(data, dict):
                        sql_result_data = data.get("data", [])
                        total = data.get("count", len(sql_result_data) if sql_result_data else 0)
                    elif isinstance(data, list):
                        sql_result_data = data
                        total = len(data)

            # === Step 4: 执行对比 SQL ===
            comparison_results = []
            for comp_sql_info in comparison_sqls:
                comp_sql = comp_sql_info.get("sql", "")
                if comp_sql:
                    comp_result = await self.sql_generator.execute(comp_sql, {})
                    if comp_result:
                        comp_data = comp_result.get("data", {})
                        if isinstance(comp_data, dict):
                            comp_result_data = comp_data.get("data", [])
                        elif isinstance(comp_data, list):
                            comp_result_data = comp_data
                        else:
                            comp_result_data = []

                        # 计算对比值
                        total_current = sum(float(row.get(list(row.keys())[-1], 0)) for row in (sql_result_data or []) if row)
                        total_comp = sum(float(row.get(list(row.keys())[-1], 0)) for row in comp_result_data if row)

                        if total_comp != 0:
                            change_rate = (total_current - total_comp) / total_comp * 100
                        else:
                            change_rate = 0

                        comparison_results.append({
                            "comparison_type": comp_sql_info.get("type"),
                            "current_value": total_current,
                            "comparison_value": total_comp,
                            "change_rate": round(change_rate, 2),
                            "period_start": comp_sql_info.get("period_start"),
                            "period_end": comp_sql_info.get("period_end")
                        })

            # === Step 5: 生成回答 ===
            answer = self._generate_answer(state, query_state, sql_result_data, comparison_results)

            return {
                "session_id": session_id,
                "answer": answer,
                "sql": generated_sql,
                "thinking_steps": [
                    {"step": s.step, "status": s.status, "content": s.content}
                    for s in state.thinking_steps
                ],
                "result_data": sql_result_data[:20] if sql_result_data else None,
                "total": total,
                "page": page,
                "page_size": page_size,
                "comparison_results": comparison_results if comparison_results else None,
                "metric_code": metric_code,
                "needs_clarification": False
            }

        except Exception as e:
            logger.error(f"[LLMQueryEngine] 处理出错: {e}")
            return {
                "session_id": session_id,
                "answer": f"处理出错: {str(e)}",
                "needs_clarification": False
            }

    def _generate_answer(
        self,
        state: ConversationState,
        query_state: Dict[str, Any],
        result_data: Any,
        comparison_results: list
    ) -> str:
        """生成回答文本"""
        metric_name = query_state.get("metric", {}).get("name", "指标")
        intent = query_state.get("intent", "query_value")

        if not result_data:
            return f"抱歉，{metric_name}暂无数据"

        # 简单汇总
        if isinstance(result_data, list) and len(result_data) > 0:
            if len(result_data) == 1:
                # 单条数据
                row = result_data[0]
                values = [v for v in row.values() if v is not None]
                metric_value = values[-1] if values else 0
                return f"{metric_name}为{metric_value}"
            else:
                # 多条数据，只显示第一条的关键信息
                first_row = result_data[0]
                comp_text = ""
                if comparison_results:
                    for cr in comparison_results:
                        change = cr.get("change_rate", 0)
                        symbol = "增长" if change > 0 else "下降"
                        comp_text += f"，{cr['comparison_type']}{symbol}{abs(change):.1f}%"

                # 返回第一条数据的关键值
                return f"{metric_name}查询完成，共{len(result_data)}条数据{comp_text}"

        return f"{metric_name}查询完成"

    async def _build_clarification_response(
        self,
        state: ConversationState,
        clarification_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建追问响应"""
        return {
            "session_id": state.session_id,
            "answer": clarification_result.get("clarification_message", "需要更多信息"),
            "needs_clarification": True,
            "clarification_message": clarification_result.get("clarification_message"),
            "clarification_type": clarification_result.get("clarification_type"),
            "thinking_steps": [
                {"step": s.step, "status": s.status, "content": s.content}
                for s in state.thinking_steps
            ]
        }

    async def get_state(self, session_id: str) -> Optional[ConversationState]:
        """获取会话状态"""
        return self.sessions.get(session_id)
