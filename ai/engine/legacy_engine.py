"""Legacy 引擎 - 封装现有对话逻辑"""
import re
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import httpx

from ai.engine.base import ConversationEngine
from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import conversation_nodes
from ai.client.metric_client import MetricClient
from ai.feedback.auto_detector import get_auto_fail_detector
from ai.feedback.collector import get_feedback_collector
from ai.config.logging_config import get_logger

logger = get_logger("ai.engine.legacy")

GO_API_BASE = "http://localhost:8080"


class LegacyEngine(ConversationEngine):
    """封装现有 main.py ask_question 逻辑的引擎"""

    def __init__(self):
        self.sessions = {}
        self.session_metadata = {}
        self.metric_client = MetricClient()

    async def process(
        self,
        question: str,
        session_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """处理对话请求 - 复用 main.py 逻辑"""
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

        # 清除上一轮的错误状态
        prev_clarification_type = getattr(state, 'clarification_type', None)
        prev_clarification_message = getattr(state, 'clarification_message', None)
        state.needs_clarification = False
        state.clarification_message = None
        state.clarification_type = None
        state.matched_metrics = None
        state.error = None
        state.comparison_results = None
        state.sql_result = None
        state._prev_clarification_type = prev_clarification_type
        state._prev_clarification_message = prev_clarification_message
        state.entities.pop("dimension", None)
        if hasattr(state, '_intent_confirmed_from_context'):
            try:
                delattr(state, '_intent_confirmed_from_context')
            except (ValueError, AttributeError):
                pass
        state.thinking_steps = []

        # 添加用户消息
        state.messages.append(ConversationMessage(
            role="user",
            content=question
        ))

        # 保存用户消息到 Go 后端
        self._save_message_to_go(session_id, "user", question)

        try:
            # === 意图识别 ===
            intent_updates = conversation_nodes.intent_node(state)
            state.current_intent = intent_updates.get("current_intent")
            state.entities.update(intent_updates.get("entities", {}))

            # === 实体链接 ===
            entity_updates = conversation_nodes.entity_node(state)
            new_entities = entity_updates.get("entities", {})
            for key in ["metric_name", "metric_code", "unit", "starrocks_sql"]:
                if key in new_entities and new_entities[key] is None:
                    state.entities.pop(key, None)
                    del new_entities[key]
            state.entities.update(new_entities)

            # === SQL 生成 ===
            sql_updates = conversation_nodes.sql_gen_node(state)
            state.generated_sql = sql_updates.get("generated_sql")
            state.sql_params = sql_updates.get("sql_params", {})
            if "intent_is_metadata_query" in sql_updates:
                state.intent_is_metadata_query = sql_updates.get("intent_is_metadata_query")
            if sql_updates.get("applied_defaults"):
                state.applied_defaults = sql_updates.get("applied_defaults")
            if sql_updates.get("needs_clarification"):
                state.needs_clarification = True
                state.clarification_message = sql_updates.get("clarification_message")
                state.clarification_type = sql_updates.get("clarification_type")
                state.matched_metrics = sql_updates.get("matched_metrics")

            # === 执行查询 ===
            page_size = min(page_size, 1000)
            offset = (page - 1) * page_size
            if state.generated_sql and state.generated_sql not in ["METADATA_QUERY", "NONE"]:
                sql = state.generated_sql
                sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', sql, flags=re.IGNORECASE)
                sql = re.sub(r'\s+OFFSET\s+\d+', '', sql, flags=re.IGNORECASE)
                sql = re.sub(r'\s+', ' ', sql).strip()
                sql = f"{sql} LIMIT {page_size} OFFSET {offset}"
                state.generated_sql = sql
                logger.info(f"分页查询: page={page}, page_size={page_size}, offset={offset}")

            execute_updates = await conversation_nodes.execute_node(state)

            # === 对比计算 ===
            comparison_updates = await conversation_nodes.comparison_node(state)

            # === 生成回答 ===
            response_updates = conversation_nodes.response_node(state)

            # === 自动失败检测 ===
            auto_detector = get_auto_fail_detector()
            fail_result = auto_detector.detect_failure(
                state=state,
                result=state.sql_result,
                error=state.error
            )

            if fail_result.is_failure:
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

            # 获取当前 SQL
            current_sql = state.generated_sql if state.generated_sql and state.generated_sql != "METADATA_QUERY" else None

            # 添加助手消息
            assistant_content = response_updates.get("answer", "抱歉，我无法回答这个问题。")
            state.messages.append(ConversationMessage(
                role="assistant",
                content=assistant_content,
                sql=current_sql
            ))

            # 保存助手消息
            self._save_message_to_go(
                session_id, "assistant", assistant_content, current_sql,
                result_data=response_updates.get("result_data"),
                comparison_results=response_updates.get("comparison_results"),
                drill_down_dims=self._get_drill_down_dims(state),
                breadcrumbs=[],
                metric_code=state.entities.get("metric_code") or getattr(state, 'current_metric_code', None)
            )

            # 更新会话元数据
            if session_id in self.session_metadata:
                self.session_metadata[session_id]["updated_at"] = datetime.now().isoformat()

            # 准备思考步骤
            thinking_steps = []
            for step in state.thinking_steps:
                thinking_steps.append({
                    "step": step.step,
                    "status": step.status,
                    "content": step.content,
                    "timestamp": step.timestamp.isoformat() if step.timestamp else None,
                    "llm_used": step.llm_used
                })

            # 构建响应
            return {
                "session_id": session_id,
                "answer": response_updates.get("answer", "抱歉，我无法回答这个问题。"),
                "suggest": response_updates.get("suggest_questions", []),
                "sql": current_sql,
                "thinking_steps": thinking_steps if thinking_steps else None,
                "needs_clarification": getattr(state, 'needs_clarification', None),
                "clarification_message": getattr(state, 'clarification_message', None),
                "clarification_type": getattr(state, 'clarification_type', None),
                "matched_metrics": getattr(state, 'matched_metrics', None),
                "dimension_value_candidates": getattr(state, 'dimension_value_candidates', None),
                "dimension_value_matched_text": getattr(state, 'dimension_value_matched_text', None),
                "drill_down_dims": self._get_drill_down_dims(state),
                "breadcrumbs": [],
                "result_data": self._rename_result_columns(
                    response_updates.get("result_data") if isinstance(response_updates.get("result_data"), list) else None,
                    self._get_metric_name_for_result(state)
                ),
                "total": self._extract_result_total(state.sql_result),
                "page": page,
                "page_size": page_size,
                "comparison_results": getattr(state, 'comparison_results', None),
                "metric_code": state.entities.get("metric_code") or getattr(state, 'current_metric_code', None)
            }

        except Exception as e:
            logger.error(f"LegacyEngine 处理出错: {e}")
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

    def _get_metric_name_for_result(self, state: ConversationState) -> Dict[str, str]:
        """获取指标字段名到中文名称的映射"""
        field_name_map = {}
        try:
            all_metrics = self.metric_client.get_all_metrics()
        except:
            return field_name_map

        target_metric_code = None
        ctx = getattr(state, 'conversation_context', None)
        if ctx:
            target_metric_code = getattr(ctx, 'current_metric_code', None)
        if not target_metric_code:
            target_metric_code = state.entities.get("metric_code")
        if not target_metric_code and hasattr(state, 'metric_id') and state.metric_id:
            for m in all_metrics:
                if str(m.get("id")) == str(state.metric_id):
                    target_metric_code = m.get("metric_code")
                    break

        target_metric = None
        if target_metric_code:
            for m in all_metrics:
                if m.get("metric_code") == target_metric_code:
                    target_metric = m
                    break

        if target_metric:
            starrocks_sql = target_metric.get("starrocks_sql", "") or ""
            field_matches = re.findall(r'(?:sum\()?\s*([\w]+)\s*\)?\s*(?:as\s*`?([\w]+)`?)?', starrocks_sql, re.IGNORECASE)
            if any(m[1] for m in field_matches):
                field_matches = [m[1] if m[1] else m[0] for m in field_matches]
            metric_name = target_metric.get("name", target_metric_code)
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

    def _get_drill_down_dims(self, state: ConversationState) -> Optional[List[Dict[str, str]]]:
        """获取下钻维度"""
        drill_down_dims = getattr(state, 'drill_down_dims', None)
        if drill_down_dims:
            return drill_down_dims
        generated_sql = getattr(state, 'generated_sql', None)
        if not generated_sql or generated_sql in ["METADATA_QUERY", "NONE"]:
            return None

        metric_code = state.entities.get("metric_code")
        if not metric_code:
            return None

        # 获取当前分组维度，用于过滤（统一转大写避免大小写问题）
        current_dimension = (state.entities.get("dimension") or "").upper()

        # 时间维度列表 - 不作为下钻维度
        time_dimension_keywords = ["日", "月", "年", "周", "天", "DAY", "MONTH", "YEAR", "WEEK"]

        try:
            metric = self.metric_client.get_metric_by_code(metric_code)
            if metric:
                dimensions = metric.get("dimensions", [])
                if dimensions:
                    filtered_dims = []
                    for d in dimensions:
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

                # Fallback: 使用 common_dimensions（逗号分隔的维度名列表）
                common_dims = metric.get("common_dimensions", "")
                if common_dims:
                    dim_names = [d.strip() for d in common_dims.split("、") if d.strip()]
                    # 获取该表的所有维度配置，建立 dimension_name -> column_name 映射
                    table_name = metric.get("starrocks_table") or ""
                    # 如果 starrocks_table 为空，从 starrocks_sql 提取表名
                    if not table_name:
                        import re
                        sql = metric.get("starrocks_sql", "")
                        match = re.search(r'FROM\s+([^\s;]+)', sql, re.IGNORECASE)
                        if match:
                            table_name = match.group(1)
                    all_dim_configs = []
                    if table_name:
                        all_dim_configs = self.metric_client.get_dimension_configs(table_name)
                    dim_name_to_col = {}
                    for cfg in all_dim_configs:
                        if cfg.get("status") == 1:
                            dim_name_to_col[cfg["dimension_name"]] = cfg["column_name"]

                    # "品类"等通用维度名需要展开为具体的 GROUP_1/2/3
                    category_aliases = {"品类": ["一级品类", "二级品类", "三级品类"]}

                    filtered = []
                    for name in dim_names:
                        if name.upper() in time_dimension_keywords or name.upper() == current_dimension:
                            continue
                        # 检查是否是通用维度名的别名
                        if name in category_aliases:
                            for alias in category_aliases[name]:
                                col = dim_name_to_col.get(alias)
                                if col:
                                    filtered.append({"dimension_name": alias, "dimension_field": col})
                        else:
                            # 尝试直接匹配 dimension_name 或作为 column_name
                            col = dim_name_to_col.get(name) or name
                            filtered.append({"dimension_name": name, "dimension_field": col})
                    return filtered if filtered else None
        except:
            pass
        return None

    async def get_state(self, session_id: str) -> Optional[ConversationState]:
        return self.sessions.get(session_id)
