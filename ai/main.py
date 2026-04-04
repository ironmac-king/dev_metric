"""
Python AI 服务 - 智能问数
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import httpx

from ai.graph.state import ConversationState, ConversationMessage
from ai.graph.nodes import conversation_nodes
from ai.feedback.auto_detector import get_auto_fail_detector, FailReason
from ai.feedback.collector import get_feedback_collector, FeedbackType
from ai.feedback.analyzer import get_feedback_analyzer
from ai.feedback.rule_optimizer import get_rule_optimizer
from ai.config.logging_config import setup_logging, get_logger
from ai.engine import get_engine
from ai.engine.rule_engine import RuleEngine

# 初始化日志
setup_logging()
logger = get_logger("ai")

# Go 后端地址
GO_API_BASE = "http://localhost:8080"

def save_message_to_go(session_id: str, role: str, content: str, sql: str = None,
                      result_data: Any = None, comparison_result: Any = None,
                      drill_down_dims: Any = None, breadcrumbs: Any = None,
                      metric_code: str = None):
    """保存消息到 Go 后端（Redis + PostgreSQL）"""
    try:
        payload = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "sql": sql or "",
            "result_data": json.dumps(result_data) if result_data is not None else "",
            "comparison_result": json.dumps(comparison_result) if comparison_result is not None else "",
            "drill_down_dims": json.dumps(drill_down_dims) if drill_down_dims is not None else "",
            "breadcrumbs": json.dumps(breadcrumbs) if breadcrumbs is not None else "",
            "metric_code": metric_code or ""
        }
        with httpx.Client(timeout=5) as client:
            client.post(f"{GO_API_BASE}/api/v1/ask/messages", json=payload)
    except Exception as e:
        logger.warning(f"保存消息到 Go 失败: {e}")

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
    page: int = 1
    page_size: int = 10
    engine_type: Optional[str] = "legacy"  # "legacy" 或 "langgraph"
    user_id: Optional[str] = "default"  # 用户ID，用于日志隔离


class ThinkingStepResponse(BaseModel):
    """思考步骤响应"""
    step: str
    status: str
    content: Optional[str] = None
    timestamp: Optional[str] = None
    llm_used: bool = False


class AskResponse(BaseModel):
    session_id: str
    answer: str
    suggest: List[str]
    sql: Optional[str] = None
    thinking_steps: Optional[List[ThinkingStepResponse]] = None
    needs_clarification: Optional[bool] = None
    clarification_message: Optional[str] = None
    clarification_type: Optional[str] = None
    matched_metrics: Optional[List[Dict[str, Any]]] = None
    dimension_value_candidates: Optional[List[Dict[str, Any]]] = None  # 维度值候选
    dimension_value_matched_text: Optional[str] = None  # 匹配维度值时的原始文本
    drill_down_dims: Optional[List[Dict[str, str]]] = None
    breadcrumbs: Optional[List[Dict[str, str]]] = None
    result_data: Optional[List[Dict[str, Any]]] = None  # SQL 查询结果
    total: Optional[int] = None  # 总记录数
    page: Optional[int] = None  # 当前页
    page_size: Optional[int] = None  # 每页条数
    comparison_result: Optional[Dict[str, Any]] = None  # 同比环比结果
    metric_code: Optional[str] = None  # 当前指标代码


def _extract_result_data(sql_result) -> Optional[List[Dict[str, Any]]]:
    """从 SQL 执行结果中提取数据列表"""
    if sql_result is None:
        return None
    if isinstance(sql_result, list):
        return sql_result
    if isinstance(sql_result, dict):
        # Go 返回格式: {"data": [...], "count": N}
        data = sql_result.get("data", {})
        if isinstance(data, list):
            return data
        # 嵌套格式: {"data": {"data": [...], "count": N}}
        if isinstance(data, dict):
            return data.get("data")
    return None


def _extract_result_total(sql_result) -> Optional[int]:
    """从 SQL 执行结果中提取总数"""
    if sql_result is None:
        return None
    if isinstance(sql_result, dict):
        # Go 返回格式: {"data": [...], "count": N}
        if "count" in sql_result:
            return sql_result.get("count")
        # 嵌套格式: {"data": {"data": [...], "count": N}}
        data = sql_result.get("data", {})
        if isinstance(data, dict):
            return data.get("count")
    return None


def _get_metric_name_for_result(state: ConversationState, metric_client: MetricClient) -> Dict[str, str]:
    """获取指标字段名到中文名称的映射，用于结果列名替换"""
    field_name_map = {}

    # 获取所有指标
    try:
        all_metrics = metric_client.get_all_metrics()
    except:
        return field_name_map

    # 确定要查找的指标代码
    target_metric_code = None

    # 优先从 conversation_context 获取
    ctx = getattr(state, 'conversation_context', None)
    if ctx:
        target_metric_code = getattr(ctx, 'current_metric_code', None)

    # 如果没有，从 state.entities 获取
    if not target_metric_code:
        target_metric_code = state.entities.get("metric_code")

    # 如果还是没有，从 state.metric_id 获取
    if not target_metric_code and hasattr(state, 'metric_id') and state.metric_id:
        for m in all_metrics:
            if str(m.get("id")) == str(state.metric_id):
                target_metric_code = m.get("metric_code")
                break

    # 找到对应的指标
    target_metric = None
    if target_metric_code:
        for m in all_metrics:
            if m.get("metric_code") == target_metric_code:
                target_metric = m
                break

    if target_metric:
        # 从 starrocks_sql 中提取字段名
        starrocks_sql = target_metric.get("starrocks_sql", "") or ""
        import re
        # 匹配 sum(XXX) 或 XXX as YYY 等模式
        field_matches = re.findall(r'(?:sum\()?\s*([\w]+)\s*\)?\s*(?:as\s*`?([\w]+)`?)?', starrocks_sql, re.IGNORECASE)
        # 如果有别名对，提取别名；否则提取字段名
        if any(m[1] for m in field_matches):
            field_matches = [m[1] if m[1] else m[0] for m in field_matches]
        metric_name = target_metric.get("name", target_metric_code)
        for field in field_matches:
            field_upper = field.upper()
            if field_upper not in field_name_map:
                field_name_map[field_upper] = metric_name

    return field_name_map


def _rename_result_columns(result_data: Optional[List[Dict[str, Any]]], metric_name_map: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    """替换结果中的指标列名为中文名称"""
    if not result_data or not metric_name_map:
        return result_data

    renamed_data = []
    for row in result_data:
        new_row = {}
        for k, v in row.items():
            # 跳过对比相关字段
            if k in ('comparison_value', 'change_rate'):
                new_row[k] = v
            # 替换指标列名
            elif k in metric_name_map:
                new_row[metric_name_map[k]] = v
            else:
                new_row[k] = v
        renamed_data.append(new_row)
    return renamed_data


def _get_drill_down_dims(state) -> List[Dict[str, str]]:
    """获取可下钻的维度列表"""
    try:
        import re
        from ai.client.metric_client import MetricClient

        # 从 state.entities 获取 starrocks_sql
        starrocks_sql = state.entities.get("starrocks_sql", "")
        if not starrocks_sql:
            return []

        # 从 SQL 提取表名
        match = re.search(r'FROM\s+([^\s;]+)', starrocks_sql, re.IGNORECASE)
        if not match:
            return []

        table_name = match.group(1)

        # 获取维度配置
        metric_client = MetricClient()
        dim_configs = metric_client.get_dimension_configs(table_name)

        # 返回可用维度（排除时间维度）
        result = []
        time_dims = ["日", "月", "年", "day", "month", "year", "时间"]
        for cfg in dim_configs:
            if cfg.get("status") == 1 and cfg.get("dimension_name") not in time_dims:
                result.append({
                    "dimension_name": cfg["dimension_name"],
                    "column_name": cfg["column_name"]
                })

        return result

    except Exception as e:
        logger.error(f"获取下钻维度失败: {e}")
        return []


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """智能问数接口 - 支持引擎切换 A/B Test"""
    # 获取或创建会话 ID
    session_id = req.session_id or str(uuid.uuid4())

    # 获取引擎
    engine_type = req.engine_type or "legacy"
    engine = get_engine(engine_type)
    logger = get_logger("ai.main")
    logger.info(f"[ask_question] engine_type={engine_type}, question={req.question[:50]}")

    try:
        # 调用引擎处理
        result = await engine.process(
            question=req.question,
            session_id=session_id,
            page=req.page,
            page_size=req.page_size
        )

        # 异步写入分析日志（不阻塞响应）
        import asyncio
        from ai.client.metric_client import MetricClient

        async def write_analysis_log():
            try:
                # 分析结果，确定成功/失败状态
                needs_clarification = result.get("needs_clarification", False)
                answer = result.get("answer", "")
                thinking_steps_data = result.get("thinking_steps") or []

                # 判断成功：不是追问状态，且回答不包含明显的失败提示
                is_success = not needs_clarification and "抱歉" not in answer and "无法" not in answer

                # 确定失败阶段和原因
                fail_stage = ""
                fail_reason = ""
                suggestion = ""

                if not is_success:
                    # 从 thinking_steps 提取失败信息
                    for step in thinking_steps_data:
                        if isinstance(step, dict):
                            status = step.get("status", "")
                            if status in ("requires_clarification", "error", "failed"):
                                # 提取阶段名
                                step_name = step.get("step", "")
                                if "意图" in step_name:
                                    fail_stage = "intent"
                                elif "实体" in step_name or "指标" in step_name:
                                    fail_stage = "entity"
                                elif "SQL" in step_name or "sql" in step_name.lower():
                                    fail_stage = "sql"
                                elif "执行" in step_name or "查询" in step_name:
                                    fail_stage = "execute"
                                else:
                                    fail_stage = "unknown"

                                fail_reason = step.get("content", "") or ""
                                break

                    # 如果没有从 thinking_steps 获取到，使用 clarification_message
                    if not fail_reason:
                        fail_reason = result.get("clarification_message", "") or answer

                    # 根据 fail_stage 提供建议
                    if fail_stage == "intent":
                        suggestion = "可在「意图配置」页面添加更多匹配模式或提高优先级"
                    elif fail_stage == "entity":
                        suggestion = "请检查指标名称是否正确，或在「指标管理」中添加对应指标"
                    elif fail_stage == "sql":
                        suggestion = "请检查 SQL 模板配置是否正确，或在「意图配置」中添加新的公式语法"
                    elif fail_stage == "execute":
                        suggestion = "请检查 StarRocks 连接配置和数据是否存在"

                # 序列化 thinking_steps
                import json
                thinking_steps_json = json.dumps(thinking_steps_data, ensure_ascii=False, default=str)

                # 获取意图
                current_intent = result.get("current_intent", "") or ""

                # 写入日志
                metric_client = MetricClient()
                metric_client.create_analysis_log(
                    user_id=req.user_id or "default",
                    session_id=session_id,
                    question=req.question,
                    intent=current_intent,
                    success=is_success,
                    fail_stage=fail_stage,
                    fail_reason=fail_reason,
                    suggestion=suggestion,
                    thinking_steps=thinking_steps_json
                )
            except Exception as log_err:
                logger.warning(f"写入分析日志失败: {log_err}")

        # 启动异步任务（不等待完成）
        asyncio.create_task(write_analysis_log())

        # 更新会话元数据
        if session_id in session_metadata:
            session_metadata[session_id]["updated_at"] = datetime.now().isoformat()
        elif session_id not in session_metadata:
            session_metadata[session_id] = {
                "id": session_id,
                "title": req.question[:20] + "..." if len(req.question) > 20 else req.question,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

        # 准备思考步骤
        thinking_steps = []
        for step in result.get("thinking_steps") or []:
            if isinstance(step, dict):
                thinking_steps.append(ThinkingStepResponse(
                    step=step.get("step", ""),
                    status=step.get("status", ""),
                    content=step.get("content"),
                    timestamp=step.get("timestamp"),
                    llm_used=step.get("llm_used", False)
                ))

        return AskResponse(
            session_id=result.get("session_id", session_id),
            answer=result.get("answer", "抱歉，我无法回答这个问题。"),
            suggest=result.get("suggest", []),
            sql=result.get("sql"),
            thinking_steps=thinking_steps if thinking_steps else None,
            needs_clarification=result.get("needs_clarification"),
            clarification_message=result.get("clarification_message"),
            clarification_type=result.get("clarification_type"),
            matched_metrics=result.get("matched_metrics"),
            dimension_value_candidates=result.get("dimension_value_candidates"),
            dimension_value_matched_text=result.get("dimension_value_matched_text"),
            drill_down_dims=result.get("drill_down_dims"),
            breadcrumbs=result.get("breadcrumbs") or [],
            result_data=result.get("result_data"),
            total=result.get("total"),
            page=result.get("page", req.page),
            page_size=result.get("page_size", req.page_size),
            comparison_result=result.get("comparison_result"),
            metric_code=result.get("metric_code")
        )

    except Exception as e:
        logger.error(f"ask_question 处理出错: {e}")
        import traceback
        traceback.print_exc()
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


class DrillDownRequest(BaseModel):
    """下钻请求"""
    session_id: str
    dimension_names: List[str]
    metric_code: str
    current_sql: str
    current_group_by: Optional[str] = None
    page: int = 1
    page_size: int = 10
    comparison_type: Optional[str] = None  # 环比: "环比", 同比: "同比"


@app.post("/api/v1/ask/drill_down")
async def drill_down_question(req: DrillDownRequest):
    """下钻维度查询"""
    from ai.sql_gen.generator import SQLGenerator
    from ai.client.metric_client import MetricClient
    import re
    import json

    try:
        # 1. 从 current_sql 提取 table_name
        sql = req.current_sql
        match = re.search(r'FROM\s+([^\s;]+)', sql, re.IGNORECASE)
        if not match:
            return {"session_id": req.session_id, "answer": "无法解析 SQL 中的表名", "sql": None}
        table_name = match.group(1)

        # 2. 获取维度配置
        metric_client = MetricClient()
        dim_configs = metric_client.get_dimension_configs(table_name)

        # 获取指标中文名称 - 通过 starrocks_sql 建立字段名到指标名的映射
        metric_name_map = {}
        try:
            all_metrics = metric_client.get_all_metrics()
            target_metric = None
            # 找到当前指标
            if req.metric_code:
                for m in all_metrics:
                    if m.get("metric_code") == req.metric_code:
                        target_metric = m
                        break
            # 从 starrocks_sql 提取字段名并建立映射
            if target_metric:
                starrocks_sql = target_metric.get("starrocks_sql", "") or ""
                # 匹配 "sum(xxx) as alias" 或 "xxx as alias" 或 "sum(xxx)"
                # SQL关键字列表（排除这些）
                sql_keywords = {'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'OFFSET', 'HAVING', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'IN', 'NOT', 'NULL', 'AS', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'ALL', 'DWS'}
                # 只匹配 sum(xxx) as alias 这种模式，忽略其他
                sum_alias_matches = re.findall(r'sum\s*\(\s*(\w+)\s*\)\s*as\s*`?(\w+)`?', starrocks_sql, re.IGNORECASE)
                metric_name = target_metric.get("name", req.metric_code)
                for orig_field, alias_field in sum_alias_matches:
                    key = alias_field.upper()
                    if key and key not in sql_keywords:
                        metric_name_map[key] = metric_name
            logger.info(f"[drill_down] metric_name_map={metric_name_map}, metric_code={req.metric_code}")
        except Exception as e:
            logger.warning(f"获取指标名称失败: {e}")

        # 构建列名到中文维度名的映射（用于结果列名替换）
        col_to_dim_name = {}
        for cfg in dim_configs:
            if cfg.get("status") == 1:
                col_to_dim_name[cfg["column_name"]] = cfg["dimension_name"]

        # 3. 找到选中维度的 column_name
        dim_map = {}
        for cfg in dim_configs:
            if cfg.get("status") == 1 and cfg.get("dimension_name") in req.dimension_names:
                dim_map[cfg["dimension_name"]] = cfg["column_name"]

        # 4. 改造 SQL
        # 使用更可靠的方式：先找到 FROM 位置，然后找到 GROUP BY 位置（如果有）
        # 这样可以正确处理 GROUP BY 后面有多个列的情况

        # 找到 FROM 位置
        from_match = re.search(r'\s+FROM\s+', sql, re.IGNORECASE)
        if not from_match:
            return {"session_id": req.session_id, "answer": "无法解析 SQL 中的 FROM", "sql": None}
        from_pos = from_match.start()

        # 找到 GROUP BY 位置（在 FROM 之后）
        group_by_pos = -1
        remaining_sql = sql[from_pos:]
        group_by_match = re.search(r'\s+GROUP\s+BY\s+', remaining_sql, re.IGNORECASE)
        if group_by_match:
            group_by_pos = from_pos + group_by_match.start()

        # 提取各部分
        select_and_from = sql[:from_pos]  # SELECT ... FROM
        after_from = sql[from_match.end():]  # 表名和之后的内容

        if group_by_pos >= 0:
            # 有 GROUP BY：提取表名+WHERE 和 GROUP BY 部分
            table_and_where = sql[from_match.end():group_by_pos]
            group_by_clause = sql[group_by_pos:]
        else:
            # 没有 GROUP BY
            table_and_where = after_from
            group_by_clause = ""

        # 清理 table_and_where 中的 LIMIT/OFFSET（如果有的话）
        table_and_where = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', table_and_where, flags=re.IGNORECASE).strip()
        table_and_where = re.sub(r'\s+OFFSET\s+\d+', '', table_and_where, flags=re.IGNORECASE).strip()

        # 构建新的维度列（去重）
        new_dim_columns = []
        for dim_name in req.dimension_names:
            if dim_name in dim_map:
                col = dim_map[dim_name]
                if col not in new_dim_columns:
                    new_dim_columns.append(col)

        if not new_dim_columns:
            return {"session_id": req.session_id, "answer": "未找到有效的维度列", "sql": None}

        # 分析 SELECT 部分，提取列名
        select_match = re.match(r'SELECT\s+(.+)', select_and_from, re.IGNORECASE)
        if not select_match:
            return {"session_id": req.session_id, "answer": "无法解析 SELECT", "sql": None}
        select_content = select_match.group(1).strip()

        # 判断是否有聚合函数
        has_aggregate = any(kw in select_content.upper() for kw in ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN('])

        # 检查原 SELECT 中是否已包含这些维度列
        existing_cols = [c.strip().split()[0] for c in select_content.split(',')]  # 去掉 AS 别名
        cols_to_add = [col for col in new_dim_columns if col not in existing_cols]

        # 构建新的 SELECT
        if has_aggregate:
            if cols_to_add:
                new_select = f"SELECT {', '.join(cols_to_add)}, {select_content}"
            else:
                new_select = f"SELECT {select_content}"
        else:
            if cols_to_add:
                new_select = f"SELECT {', '.join(cols_to_add)}, {select_content}"
            else:
                new_select = f"SELECT {select_content}"

        # 构建新的 GROUP BY（使用所有维度列，不只是新增的）
        agg_funcs = ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN(']
        group_by_cols = []
        for col in select_content.split(','):
            col_stripped = col.strip()
            col_upper = col_stripped.upper()
            if any(agg in col_upper for agg in agg_funcs):
                continue
            col_name = col_stripped.split()[0]  # 去掉 AS 别名
            if col_name.upper() not in ['FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT', '']:
                if col_name not in group_by_cols:
                    group_by_cols.append(col_name)
        for col in cols_to_add:
            if col not in group_by_cols:
                group_by_cols.append(col)

        # 组合新的 SQL
        new_sql = f"{new_select} FROM {table_and_where}"
        if group_by_cols:
            new_sql = f"{new_sql} GROUP BY {', '.join(group_by_cols)}"

        # 添加分页 LIMIT（最大1000条）
        page_size = min(req.page_size, 1000)
        offset = (req.page - 1) * page_size
        new_sql = f"{new_sql} LIMIT {page_size} OFFSET {offset}"

        # 5. 执行查询
        sql_generator = SQLGenerator()
        result = await sql_generator.execute(new_sql, {})

        # 6. 生成回答 - 提取实际数据列表
        data_list = []
        if isinstance(result, dict):
            data_list = result.get("data", {}).get("data", []) if isinstance(result.get("data"), dict) else []
        elif isinstance(result, list):
            data_list = result

        if data_list and len(data_list) > 0:
            # 构建答案文本
            lines = []
            for row in data_list[:10]:  # 最多显示10条
                row_str = " | ".join([f"{k}: {v}" for k, v in row.items()])
                lines.append(row_str)

            answer = "按维度汇总结果：\n" + "\n".join(lines)
            if len(data_list) > 10:
                answer += f"\n... 还有 {len(data_list) - 10} 条数据"
        else:
            answer = "暂无数据"
            data_list = []

        # 6.5 对比计算（环比上月/同比去年）- T+1数据逻辑
        comparison_result_data = None
        # 如果没有传入 comparison_type，但从 SQL 中能提取到时间，推断对比类型
        # 如果时间是3月（本月是4月），推断为同比去年3月
        if not req.comparison_type and data_list:
            date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", sql)
            if date_match:
                current_month = int(date_match.group(2))
                if current_month in [1, 2, 3]:  # 1-3月，推断为同比（因为去年同期数据可能更完整）
                    req.comparison_type = "同比"
                    logger.info(f"[drill_down] 自动推断 comparison_type: {req.comparison_type} (当前月份 {current_month})")

        if req.comparison_type and data_list:
            logger.info(f"[drill_down] 开始对比计算: comparison_type={req.comparison_type}, data_list长度={len(data_list)}")
            # 从当前SQL中提取时间条件，确定当前周期
            # T+1: 今天是4月2号，能查到的数据是4月1号的
            # 环比上月: 3月1号 (上月第一天)
            # 同比去年: 去年4月1号 (去年同月第一天)
            from datetime import datetime, timedelta
            import calendar

            # 从SQL中提取日期
            date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", sql)
            if date_match:
                current_year, current_month, current_day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                # T+1: 当前数据实际是昨天
                current_date = datetime(current_year, current_month, current_day) - timedelta(days=1)
                logger.info(f"[drill_down] 提取的日期: {current_year}-{current_month:02d}-{current_day:02d}, 减去T+1后天: {current_date}")
            else:
                # 默认为昨天
                current_date = datetime.now() - timedelta(days=1)
                logger.info(f"[drill_down] 无法提取日期，使用默认: {current_date}")

            # 计算对比周期
            if req.comparison_type == "环比":
                # 环比上月: 取上月第一天
                if current_date.month == 1:
                    comp_year = current_date.year - 1
                    comp_month = 12
                else:
                    comp_year = current_date.year
                    comp_month = current_date.month - 1
                comp_day = 1  # 月份第一天
            else:
                # 同比去年: 取去年同月第一天
                comp_year = current_date.year - 1
                comp_month = current_date.month
                comp_day = 1  # 月份第一天

            comparison_date = f"{comp_year}-{comp_month:02d}-{comp_day:02d}"
            # 对比周期的结束日期：使用原始结束日期的日部分，但年份改为对比年份
            from calendar import monthrange
            comp_month_days = monthrange(comp_year, comp_month)[1]
            original_end_day = current_date.day  # 原始结束日期的日
            comp_end_day = min(original_end_day, comp_month_days)  # 不能超过对比月的最大天数
            comparison_end_date = f"{comp_year}-{comp_month:02d}-{comp_end_day:02d}"

            # 构建对比SQL: 把开始时间改为对比周期，把结束时间改为对比周期的结束
            comparison_sql = re.sub(
                r"(\w+)\s*>=\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?",
                f"\\1 >= '{comparison_date}'",
                new_sql,
                flags=re.IGNORECASE
            )
            comparison_sql = re.sub(
                r"(\w+)\s*<=\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?",
                f"\\1 <= '{comparison_end_date}'",
                comparison_sql,
                flags=re.IGNORECASE
            )
            # 移除 LIMIT/OFFSET（保留完整的对比周期数据，不要 LIMIT 1）
            comparison_sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', comparison_sql, flags=re.IGNORECASE)
            comparison_sql = re.sub(r'\s+OFFSET\s+\d+', '', comparison_sql, flags=re.IGNORECASE)

            logger.info(f"[drill_down] 对比SQL: {comparison_sql}")

            # 执行对比查询
            try:
                comp_result = await sql_generator.execute(comparison_sql, {})
                logger.info(f"[drill_down] 对比查询结果: {comp_result}")
                comp_data_list = []
                if isinstance(comp_result, dict):
                    comp_data_list = comp_result.get("data", {}).get("data", []) if isinstance(comp_result.get("data"), dict) else []
                    logger.info(f"[drill_down] 提取的comp_data_list长度: {len(comp_data_list)}")
                elif isinstance(comp_result, list):
                    comp_data_list = comp_result
                    logger.info(f"[drill_down] comp_result是list，长度: {len(comp_data_list)}")

                if comp_data_list:
                    # 用维度列作为key，建立对比数据的索引
                    comp_index = {}
                    for row in comp_data_list:
                        # 构建维度key
                        dim_key_parts = []
                        for dim_name in req.dimension_names:
                            if dim_name in dim_map and dim_map[dim_name] in row:
                                dim_key_parts.append(f"{dim_map[dim_name]}:{row.get(dim_map[dim_name])}")
                        if dim_key_parts:
                            dim_key = "|".join(dim_key_parts)
                            comp_index[dim_key] = row

                    # 为每个当前行匹配对比数据
                    for row in data_list:
                        dim_key_parts = []
                        for dim_name in req.dimension_names:
                            if dim_name in dim_map and dim_map[dim_name] in row:
                                dim_key_parts.append(f"{dim_map[dim_name]}:{row.get(dim_map[dim_name])}")
                        if dim_key_parts:
                            dim_key = "|".join(dim_key_parts)
                            if dim_key in comp_index:
                                comp_row = comp_index[dim_key]
                                # 提取指标值 - 修复: 大小写不匹配问题
                                row_upper_keys = {k.upper(): k for k in row.keys()}
                                comp_upper_keys = {k.upper(): k for k in comp_row.keys()}
                                for metric_col in metric_name_map.keys():
                                    row_key = row_upper_keys.get(metric_col)
                                    comp_key = comp_upper_keys.get(metric_col)
                                    if row_key and comp_key:
                                        current_val = row.get(row_key)
                                        comp_val = comp_row.get(comp_key)
                                        if current_val is not None and comp_val is not None:
                                            try:
                                                current_num = float(str(current_val).replace(",", ""))
                                                comp_num = float(str(comp_val).replace(",", ""))
                                                if comp_num != 0:
                                                    change_rate = (current_num - comp_num) / comp_num * 100
                                                    # 使用中文列名，根据 comparison_type 决定前缀
                                                    if req.comparison_type == "同比":
                                                        row["去年同期"] = comp_val
                                                        row["同比变化率"] = round(change_rate, 2)
                                                    else:
                                                        row["上月同期"] = comp_val
                                                        row["环比变化率"] = round(change_rate, 2)
                                            except (ValueError, TypeError):
                                                pass
                                        break

                    # 计算总体对比 - 累加所有行的指标值
                    total_current = 0
                    total_comp = 0
                    # 修复: 大小写不匹配问题 - 将 row 的 key 转为大写后匹配
                    for row in data_list:
                        row_upper_keys = {k.upper(): k for k in row.keys()}
                        for metric_col in metric_name_map.keys():
                            original_key = row_upper_keys.get(metric_col)
                            if original_key:
                                try:
                                    total_current += float(str(row.get(original_key, 0)).replace(",", ""))
                                except (ValueError, TypeError):
                                    pass
                                break  # 每个row找到一个metric col即可

                    for row in comp_data_list:
                        row_upper_keys = {k.upper(): k for k in row.keys()}
                        for metric_col in metric_name_map.keys():
                            original_key = row_upper_keys.get(metric_col)
                            if original_key:
                                try:
                                    total_comp += float(str(row.get(original_key, 0)).replace(",", ""))
                                except (ValueError, TypeError):
                                    pass
                                break  # 每个row找到一个metric col即可

                    comparison_result_data = {
                        "comparison_type": req.comparison_type,
                        "comparison_date": comparison_date,
                        "current_total": total_current,
                        "comparison_total": total_comp,
                    }
                    if total_comp != 0:
                        total_change_rate = (total_current - total_comp) / total_comp * 100
                        comparison_result_data["change_rate"] = round(total_change_rate, 2)
                        comparison_result_data["total_change_rate"] = round(total_change_rate, 2)
                    logger.info(f"[drill_down] 对比结果: {comparison_result_data}")
            except Exception as e:
                logger.error(f"[drill_down] 对比计算失败: {e}")

        # 7. 获取剩余可下钻维度（排除已选的）
        remaining_dims = [
            {"dimension_name": cfg["dimension_name"], "column_name": cfg["column_name"]}
            for cfg in dim_configs
            if cfg.get("status") == 1 and cfg["dimension_name"] not in req.dimension_names
        ]

        # 8. 构建面包屑
        breadcrumbs = [
            {"name": name, "value": col}
            for name, col in zip(req.dimension_names, new_dim_columns)
        ]

        # 提取总数
        total = _extract_result_total(result)

        # 替换 result_data 中的列名为中文名称（维度名或指标名）
        if data_list:
            renamed_data_list = []
            for row in data_list:
                new_row = {}
                for k, v in row.items():
                    # 跳过对比相关字段（稍后单独处理）
                    if k.endswith('_comparison_value') or k.endswith('_change_rate'):
                        new_row[k] = v
                    # 替换维度列名为中文维度名
                    elif k in col_to_dim_name:
                        new_row[col_to_dim_name[k]] = v
                    # 替换指标列名为中文指标名（大小写不敏感）
                    elif k.upper() in metric_name_map:
                        new_row[metric_name_map[k.upper()]] = v
                    else:
                        new_row[k] = v

                logger.info(f"[drill_down] col_to_dim_name={col_to_dim_name}, metric_name_map={metric_name_map}")
                logger.info(f"[drill_down] new_row after rename: {new_row}")

                # 固定列顺序：保持原始顺序，追加对比列
                comparison_cols = ['去年同期', '同比变化率']
                final_row = {}
                # 先添加已处理的列（保持原始顺序）
                for k, v in new_row.items():
                    if k not in comparison_cols:
                        final_row[k] = v
                # 追加对比列
                for col in comparison_cols:
                    if col in new_row:
                        final_row[col] = new_row[col]
                renamed_data_list.append(final_row)
            logger.info(f"[drill_down] final_row order: {list(final_row.keys())}")
            data_list = renamed_data_list

        # 构建返回
        response = {
            "session_id": req.session_id,
            "answer": answer,
            "sql": new_sql,
            "drill_down_dims": remaining_dims,
            "breadcrumbs": breadcrumbs,
            "result_data": data_list[:20] if data_list else None,
            "total": total,
            "page": req.page,
            "page_size": page_size,
            "metric_code": req.metric_code
        }

        if comparison_result_data:
            response["comparison_result"] = comparison_result_data

        # 保存下钻结果到 Redis/PostgreSQL
        save_message_to_go(
            req.session_id, "assistant",
            response.get("answer", ""),
            response.get("sql"),
            result_data=response.get("result_data"),
            comparison_result=response.get("comparison_result"),
            drill_down_dims=response.get("drill_down_dims"),
            breadcrumbs=response.get("breadcrumbs"),
            metric_code=response.get("metric_code")
        )

        return response

    except Exception as e:
        logger.error(f"下钻处理失败: {e}")
        return {
            "session_id": req.session_id,
            "answer": f"下钻处理出错: {str(e)}",
            "sql": None,
            "drill_down_dims": [],
            "breadcrumbs": [],
            "result_data": None
        }


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


@app.post("/api/v1/admin/reload-config")
async def reload_config():
    """重新加载指标配置"""
    from ai.graph.nodes import conversation_nodes
    try:
        # 重新初始化 RuleEngine
        conversation_nodes.rule_engine = RuleEngine()

        # 清除 IntentNode 的公式语法配置缓存
        from ai.graph.nodes import IntentNode
        if hasattr(IntentNode, '_formula_syntax_loaded'):
            IntentNode._formula_syntax_loaded = False
        if hasattr(IntentNode, '_formula_syntax_cache'):
            IntentNode._formula_syntax_cache = []

        logger.info("指标配置已重新加载")
        return {"success": True, "message": "配置已重新加载"}
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/v1/prompt/generate")
async def generate_prompt(request: Request):
    """AI 生成或优化 Prompt"""
    from ai.engine.llm import get_llm_engine

    body = await request.json()
    current_prompt = body.get("current_prompt", "")
    task_name = body.get("task_name", "自然语言转结构化实体")
    task_description = body.get("task_description", "意图识别、实体提取、时间解析")
    mode = body.get("mode", "improve")  # "improve" or "regenerate"

    llm_engine = get_llm_engine()
    result = llm_engine.generate_prompt_improvement(
        current_prompt=current_prompt,
        task_name=task_name,
        task_description=task_description,
        mode=mode
    )

    if result:
        return {"code": 0, "data": {"prompt": result}}
    else:
        return {"code": 500, "message": "Prompt 生成失败"}, 500


@app.post("/internal/generate-embeddings")
async def generate_embeddings(request: Request):
    """内部接口：接收文本列表，返回阿里 embedding 向量"""
    from ai.engine.alibaba_embedding import alibaba_embedding

    body = await request.json()
    texts = body.get("texts", [])

    if not texts:
        return {"code": 0, "data": []}

    try:
        import asyncio
        vectors = await asyncio.to_thread(alibaba_embedding.embed, texts)
        data = [{"text": text, "embedding": vec} for text, vec in zip(texts, vectors)]
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": 500, "message": str(e)}, 500


def load_semantic_vectors():
    """启动时加载语义向量"""
    from ai.engine.semantic_search import semantic_search
    logger.info("正在加载语义向量")
    semantic_search.ensure_loaded()
    logger.info("语义向量加载完成")


if __name__ == "__main__":
    import uvicorn
    # 启动每日调度器
    from ai.scheduler import start_daily_scheduler
    start_daily_scheduler()
    # 加载语义向量
    load_semantic_vectors()
    logger.info("AI 服务已启动，调度器运行中")
    uvicorn.run(app, host="0.0.0.0", port=8081)
