"""
V2 流式输出

提供 SSE (Server-Sent Events) 流式输出支持。

使用场景：
- 慢查询时先返回部分结果
- LLM 生成时边生成边返回
- 思考过程可视化
"""
import asyncio
import json
import time
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime

from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.streaming")


# ==================== SSE 事件类型 ====================

class SSSEvent:
    """SSE 事件类型"""

    # 连接事件
    CONNECTED = "connected"
    HEARTBEAT = "heartbeat"

    # 处理阶段事件
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_ERROR = "step_error"

    # 结果事件
    THINKING = "thinking"      # 思考过程
    SQL_READY = "sql_ready"     # SQL 已生成
    RESULT_READY = "result_ready"  # 结果已就绪
    ANSWER_READY = "answer_ready"  # 回答已就绪

    # 最终事件
    DONE = "done"
    ERROR = "error"


# ==================== 流式事件 ====================

class StreamEvent:
    """流式事件"""

    def __init__(
        self,
        event: str,
        data: Dict[str, Any],
        timestamp: Optional[str] = None,
    ):
        self.event = event
        self.data = data
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_sse(self) -> str:
        """转换为 SSE 格式"""
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event": self.event,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# ==================== 流式输出生成器 ====================

class StreamingGenerator:
    """
    流式输出生成器

    支持：
    - 阶段进度流
    - LLM 输出流
    - SSE 格式输出
    """

    def __init__(self):
        self._events: List[StreamEvent] = []

    def add_event(self, event: str, data: Dict[str, Any]) -> None:
        """添加事件"""
        self._events.append(StreamEvent(event, data))
        logger.debug(f"[StreamingGenerator] 事件: {event}, data={data}")

    def add_thinking(self, step: str, content: str) -> None:
        """添加思考事件"""
        self.add_event(SSSEvent.THINKING, {
            "step": step,
            "content": content,
        })

    def add_step_start(self, step: str) -> None:
        """添加步骤开始事件"""
        self.add_event(SSSEvent.STEP_START, {
            "step": step,
        })

    def add_step_complete(self, step: str, duration_ms: int = 0) -> None:
        """添加步骤完成事件"""
        self.add_event(SSSEvent.STEP_COMPLETE, {
            "step": step,
            "duration_ms": duration_ms,
        })

    def add_step_error(self, step: str, error: str) -> None:
        """添加步骤错误事件"""
        self.add_event(SSSEvent.STEP_ERROR, {
            "step": step,
            "error": error,
        })

    def add_sql_ready(self, sql: str) -> None:
        """添加 SQL 就绪事件"""
        self.add_event(SSSEvent.SQL_READY, {
            "sql": sql,
        })

    def add_result_ready(
        self,
        result_data: List[Dict[str, Any]] = None,
        total: int = 0,
        metric_name: str = '',
        metric_names: list = None,
        multi_metric_data: List[Dict[str, Any]] = None,
        dimensional_data: Dict[str, List[Dict[str, Any]]] = None,
        category: str = '',
        analysis: Dict[str, Any] = None,
        **kwargs
    ) -> None:
        """
        添加结果就绪事件

        Args:
            result_data: SQL 查询结果
            total: 总条数
            metric_name: 指标名称
            metric_names: 指标名称列表
            multi_metric_data: 多指标下钻数据列表
            dimensional_data: 维度下钻数据（站点/品类/平台/ASIN 排名）
            category: 下钻类别 (sales/ad/inventory/cost)
            analysis: 分析报告内容
        """
        if result_data is None:
            result_data = []
        if multi_metric_data is None:
            multi_metric_data = []
        if metric_names is None:
            metric_names = []
        if dimensional_data is None:
            dimensional_data = {}

        # 从 analysis 中提取 health_score
        health_score = None
        if analysis and isinstance(analysis, dict):
            health_score = analysis.get("health_score")

        self.add_event(SSSEvent.RESULT_READY, {
            "result_data": result_data[:20] if result_data else [],  # 限制返回条数
            "total": total,
            "metric_name": metric_name,
            "metric_names": metric_names,
            "multi_metric_data": multi_metric_data,
            "dimensional_data": dimensional_data,
            "category": category,
            "analysis": analysis,
            "health_score": health_score,
            **kwargs
        })

    def add_answer_ready(self, answer: str, suggestions: List[str] = None) -> None:
        """添加回答就绪事件"""
        self.add_event(SSSEvent.ANSWER_READY, {
            "answer": answer,
            "suggestions": suggestions or [],
        })

    def add_done(self, final_state: Dict[str, Any]) -> None:
        """添加完成事件"""
        self.add_event(SSSEvent.DONE, final_state)

    def add_error(self, error: str) -> None:
        """添加错误事件"""
        self.add_event(SSSEvent.ERROR, {
            "error": error,
        })

    async def stream_sse(self) -> AsyncGenerator[str, None]:
        """
        流式输出 SSE 格式

        Yields:
            SSE 格式的事件字符串
        """
        # 发送连接事件
        yield StreamEvent(SSSEvent.CONNECTED, {
            "message": "Connected to V2 streaming",
            "timestamp": datetime.now().isoformat(),
        }).to_sse()

        # 发送事件
        for event in self._events:
            yield event.to_sse()

            # 短暂延迟，避免发送过快
            await asyncio.sleep(0.01)

        # 发送心跳
        yield StreamEvent(SSSEvent.HEARTBEAT, {
            "timestamp": datetime.now().isoformat(),
        }).to_sse()

    async def stream_llm(
        self,
        prompt: str,
        llm_engine,
    ) -> AsyncGenerator[str, None]:
        """
        流式输出 LLM 生成内容

        Args:
            prompt: 提示词
            llm_engine: LLM 引擎

        Yields:
            LLM 返回的文本片段
        """
        try:
            start_time = time.time()
            first_token_time = None

            async for chunk in llm_engine.stream(prompt):
                if first_token_time is None:
                    first_token_time = time.time()
                    logger.info(f"[StreamingGenerator] 首 token 延迟: {(first_token_time - start_time)*1000:.0f}ms")

                yield chunk

            total_time = time.time() - start_time
            logger.info(f"[StreamingGenerator] LLM 流式完成, 总耗时: {total_time*1000:.0f}ms")

        except Exception as e:
            logger.error(f"[StreamingGenerator] LLM 流式失败: {e}")
            yield f"LLM 调用出错: {str(e)}"


# ==================== 流式处理辅助 ====================

async def stream_graph_steps(
    graph,
    initial_state,
    on_step_start=None,
    on_step_complete=None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式处理 Graph 步骤

    Args:
        graph: LangGraph
        initial_state: 初始状态
        on_step_start: 步骤开始回调
        on_step_complete: 步骤完成回调

    Yields:
        中间状态
    """
    try:
        async for state in graph.astream(initial_state):
            step = state.get("current_step", "")

            if step:
                if on_step_start:
                    await on_step_start(step)

                yield {
                    "type": "step",
                    "step": step,
                    "state": state,
                }

                if on_step_complete and state.get("thinking_steps"):
                    # 找到当前步骤的思考步骤
                    for ts in reversed(state["thinking_steps"]):
                        if ts.step == step:
                            await on_step_complete(step, ts.duration_ms)
                            break

    except Exception as e:
        logger.error(f"[stream_graph_steps] 错误: {e}")
        yield {
            "type": "error",
            "error": str(e),
        }


# ==================== 全局生成器工厂 ====================

_streaming_generators: Dict[str, StreamingGenerator] = {}


def get_streaming_generator(session_id: str) -> StreamingGenerator:
    """获取流式生成器"""
    if session_id not in _streaming_generators:
        _streaming_generators[session_id] = StreamingGenerator()
    return _streaming_generators[session_id]


def clear_streaming_generator(session_id: str) -> None:
    """清除流式生成器"""
    if session_id in _streaming_generators:
        del _streaming_generators[session_id]
