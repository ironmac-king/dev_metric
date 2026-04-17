"""
LLM.V1 路由入口
POST /api/v1/llm-ask
"""
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from .nodes.lu_node import get_lu_node, LUOutput
from .nodes.sf_node import get_sf_node, SFOutput
from .nodes.sql_node import get_sql_node, SQLOutput
from .nodes.ck_node import get_ck_node, CKOutput
from .nodes.ex_node import get_ex_node, EXOutput
from .nodes.rv_node import get_rv_node, RVOutput
from .nodes.chart_node import get_chart_node, ChartOutput
from .nodes.rs_node import get_rs_node, RSOutput
from .state.session_store import get_session_store, ConversationMessage
from .config_loader import get_config_loader

logger = logging.getLogger("ai.llm_v1.router")

router = APIRouter(prefix="/api/v1", tags=["llm_v1"])


def _map_result_data_columns(data: list, columns: list, slots: Dict[str, Any] = None) -> list:
    """
    将 result_data 的列名从数据库列名映射为中文展示名
    只映射 reverse_map 中存在的列，其他列（指标列、派生列）保持不变
    """
    if not data:
        return data

    # 获取反向映射（只包含维度列）
    config_loader = get_config_loader()
    reverse_map = config_loader.get_reverse_dimension_map()

    # 构建列名映射 (column_name -> display_name)，只映射存在的
    col_map = {}
    for col in columns:
        if col in reverse_map:
            col_map[col] = reverse_map[col]
        else:
            # 不在映射表中的列（如指标列、派生列）保持原名
            col_map[col] = col

    # 如果有 slots，添加指标列的映射（ORDERED_PRODUCTSALES → 销售额）
    if slots and slots.get("metric_code"):
        metric_code = slots.get("metric_code")
        metric = config_loader.get_metric_by_code(metric_code)
        if metric:
            metric_name = metric.get("name", "")
            if metric_name:
                # starrocks_sql 格式: SELECT SUM(ORDERED_PRODUCTSALES) AS ORDERED_PRODUCTSALES FROM ...
                # 提取 SUM() 中的字段名
                import re
                starrocks_sql = metric.get("starrocks_sql", "")
                matches = re.findall(r'SUM\s*\(\s*(\w+)\s*\)', starrocks_sql, re.IGNORECASE)
                for field in matches:
                    field_upper = field.upper()
                    if field_upper in col_map:
                        col_map[field_upper] = metric_name
    elif slots and slots.get("metric"):
        # metric_code 为空但有 metric name，尝试通过 metric name 查找
        metric_name = slots.get("metric")
        metric = config_loader.get_metric_by_name(metric_name)
        if metric:
            import re
            starrocks_sql = metric.get("starrocks_sql", "")
            matches = re.findall(r'SUM\s*\(\s*(\w+)\s*\)', starrocks_sql, re.IGNORECASE)
            for field in matches:
                field_upper = field.upper()
                if field_upper in col_map:
                    col_map[field_upper] = metric.get("name", metric_name)

    # 转换每一行
    result = []
    for row in data:
        new_row = {}
        for key, value in row.items():
            new_key = col_map.get(key, key)
            new_row[new_key] = value
        result.append(new_row)

    return result


# 测试端点
@router.get("/llm-ask/debug/reverse-map")
async def debug_reverse_map():
    """调试：查看 reverse_map 内容"""
    config_loader = get_config_loader()
    reverse_map = config_loader.get_reverse_dimension_map()
    return {"reverse_map": reverse_map, "keys_sample": list(reverse_map.keys())[:10]}


@router.get("/llm-ask/test")
async def test_result_data():
    """测试 result_data 字段是否被正确返回"""
    test_data = [
        {"店铺": "A", "销售额": 100},
        {"店铺": "B", "销售额": 200}
    ]
    return LLMAskResponse(
        session_id="test",
        answer="test answer",
        sql="SELECT 1",
        result_data=test_data,
        thinking_steps=[],
        chart_config={},
        suggestions=[],
        anomaly_warnings=[],
        needs_clarification=False,
    )


class LLMAskRequest(BaseModel):
    """LLM.V1 请求"""
    question: str
    session_id: Optional[str] = None


class LLMAskResponse(BaseModel):
    """LLM.V1 响应"""
    session_id: str
    answer: str
    sql: str
    result_data: list = []
    thinking_steps: list = []
    chart_config: Dict[str, Any] = {}
    suggestions: list = []
    anomaly_warnings: list = []
    needs_clarification: bool = False
    clarification_type: Optional[str] = None
    clarification_message: Optional[str] = None


@router.post("/llm-ask", response_model=LLMAskResponse)
async def llm_ask(request: LLMAskRequest) -> LLMAskResponse:
    """
    LLM.V1 智能问数入口

    八节点管道：
    LU → SF → SQL → CK → EX → RV → CHART → RS
    """
    logger.info(f"[LLM.V1] 收到请求: question={request.question}, session_id={request.session_id}")

    # 生成 session_id
    session_id = request.session_id or generate_session_id()

    try:
        # ========== Node 1: LU 意图识别 ==========
        lu_node = get_lu_node()
        lu_output = await lu_node.process(request.question, session_id)

        # 检查是否需要澄清
        if lu_output.needs_clarification:
            return LLMAskResponse(
                session_id=session_id,
                answer="",
                sql="",
                chart_config={},
                suggestions=[],
                anomaly_warnings=[],
                needs_clarification=True,
                clarification_type=lu_output.clarification_type,
                clarification_message=lu_output.clarification_message,
            )

        # ========== Node 2: SF 要素校验 ==========
        sf_node = get_sf_node()
        sf_output = await sf_node.process(lu_output, session_id)

        # ========== Node 3: SQL 生成 ==========
        sql_node = get_sql_node()
        sql_output = await sql_node.process(sf_output)

        # ========== Node 4: CK 纠错 ==========
        ck_node = get_ck_node()
        ck_output = await ck_node.process(sql_output)

        # 如果纠错后有修正 SQL，使用修正后的
        final_sql = ck_output.corrected_sql if ck_output.corrected_sql else sql_output.sql

        # ========== Node 5: EX 执行 ==========
        ex_node = get_ex_node()
        ex_output = await ex_node.process(ck_output)

        # ========== Node 6: RV 验证 ==========
        rv_node = get_rv_node()
        rv_output = await rv_node.process(ex_output, lu_output.slots)

        # ========== Node 7: CHART 可视化 ==========
        chart_node = get_chart_node()
        chart_output = await chart_node.process(ex_output, rv_output, lu_output.slots)

        # ========== Node 8: RS 报告生成 ==========
        rs_node = get_rs_node()
        rs_output = await rs_node.process(
            ex_output, rv_output, chart_output, lu_output.slots, session_id
        )

        # 转换 result_data 列名为中文展示名
        mapped_result_data = _map_result_data_columns(
            list(ex_output.data) if ex_output.data else [],
            ex_output.columns,
            lu_output.slots
        )

        return LLMAskResponse(
            session_id=session_id,
            answer=rs_output.answer,
            sql=rs_output.sql,
            result_data=mapped_result_data,
            thinking_steps=rs_output.thinking_steps,
            chart_config=rs_output.chart_config,
            suggestions=rs_output.suggestions,
            anomaly_warnings=rs_output.anomaly_warnings,
            needs_clarification=False,
        )

    except Exception as e:
        logger.error(f"[LLM.V1] 处理异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.post("/llm-ask/clear")
async def llm_ask_clear(session_id: str) -> Dict[str, Any]:
    """清除会话"""
    session_store = get_session_store()
    session_store.clear_session(session_id)
    return {"code": 0, "message": "会话已清除"}


@router.get("/llm-ask/history/{session_id}")
async def llm_ask_history(session_id: str) -> Dict[str, Any]:
    """获取会话历史"""
    session_store = get_session_store()
    state = session_store.get_session(session_id)
    if not state:
        return {"code": 0, "data": {"messages": []}}

    messages = []
    for msg in state.history:
        messages.append({
            "role": msg.role,
            "content": msg.content,
            "sql": msg.sql or "",
            "answer": msg.answer or "",
            "chart_config": msg.chart_config,
            "result_data": msg.result_data,
            "thinking_steps": msg.thinking_steps or [],
            "suggestions": msg.suggestions or [],
            "created_at": msg.created_at,
        })

    return {"code": 0, "data": {"messages": messages}}


def generate_session_id() -> str:
    """生成会话ID"""
    import uuid
    return str(uuid.uuid4())
