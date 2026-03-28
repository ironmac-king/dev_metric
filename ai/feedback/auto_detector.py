"""
自动失败检测 - 检测"回答不上来"的场景
"""
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json


class FailReason(Enum):
    """失败原因枚举"""
    NO_METRIC = "no_metric"           # 指标不存在
    NO_DATA = "no_data"               # 指标无数据
    SQL_ERROR = "sql_error"           # SQL 执行失败
    INTENT_FAIL = "intent_fail"       # 意图识别失败
    TIMEOUT = "timeout"                # LLM 响应超时
    UNKNOWN = "unknown"                # 未知错误


@dataclass
class FailDetectionResult:
    """失败检测结果"""
    is_failure: bool
    fail_reason: Optional[FailReason]
    message: str
    context_for_debug: Dict[str, Any]


class AutoFailDetector:
    """自动检测回答失败"""

    def __init__(self):
        self.intent_confidence_threshold = 0.3

    def detect_failure(
        self,
        state: Any,
        result: Any = None,
        error: Optional[str] = None
    ) -> FailDetectionResult:
        """
        检测失败原因

        Args:
            state: ConversationState 对话状态
            result: 查询结果
            error: 错误信息

        Returns:
            FailDetectionResult: 失败检测结果
        """
        # 1. 指标不存在
        if state.entities.get("metric_name") and not state.entities.get("metric_id"):
            if self._metric_not_found_in_kb(state.entities["metric_name"]):
                return FailDetectionResult(
                    is_failure=True,
                    fail_reason=FailReason.NO_METRIC,
                    message=f"指标「{state.entities['metric_name']}」在知识库中不存在",
                    context_for_debug=self._build_context_snapshot(state)
                )

        # 2. 指标无数据
        if state.metric_id and result is None and not error:
            return FailDetectionResult(
                is_failure=True,
                fail_reason=FailReason.NO_DATA,
                message=f"指标「{state.entities.get('metric_name', '未知')}」在指定时间范围内无数据",
                context_for_debug=self._build_context_snapshot(state)
            )

        # 3. SQL 执行失败
        if error and self._is_sql_error(error):
            return FailDetectionResult(
                is_failure=True,
                fail_reason=FailReason.SQL_ERROR,
                message=f"SQL 执行失败: {error}",
                context_for_debug=self._build_context_snapshot(state)
            )

        # 4. 意图识别失败
        if state.current_intent == "unknown" and hasattr(state, 'intent_confidence'):
            if state.intent_confidence < self.intent_confidence_threshold:
                return FailDetectionResult(
                    is_failure=True,
                    fail_reason=FailReason.INTENT_FAIL,
                    message=f"无法识别用户意图（置信度: {state.intent_confidence}）",
                    context_for_debug=self._build_context_snapshot(state)
                )

        # 5. LLM 超时
        if error and "timeout" in error.lower():
            return FailDetectionResult(
                is_failure=True,
                fail_reason=FailReason.TIMEOUT,
                message=f"LLM 响应超时",
                context_for_debug=self._build_context_snapshot(state)
            )

        # 没有检测到失败
        return FailDetectionResult(
            is_failure=False,
            fail_reason=None,
            message="未检测到失败",
            context_for_debug={}
        )

    def _metric_not_found_in_kb(self, metric_name: str) -> bool:
        """检查指标是否在知识库中"""
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            metrics = client.get_all_metrics()
            # 检查是否有指标名称匹配
            for m in metrics:
                if m.get("name") == metric_name or m.get("name_en") == metric_name:
                    return False  # 找到了
            return True  # 没找到
        except Exception as e:
            print(f"[AutoFailDetector] 检查指标失败: {e}")
            return True  # 检查失败时保守返回 True

    def _is_sql_error(self, error: str) -> bool:
        """判断是否为 SQL 相关错误"""
        sql_keywords = [
            "sql", "syntax", "query", "database",
            "starrocks", "postgres", "mysql",
            "select", "from", "where"
        ]
        error_lower = error.lower()
        return any(keyword in error_lower for keyword in sql_keywords)

    def _build_context_snapshot(self, state: Any) -> Dict[str, Any]:
        """构建上下文快照用于调试"""
        return {
            "session_id": state.session_id,
            "current_intent": state.current_intent,
            "entities": state.entities,
            "generated_sql": state.generated_sql,
            "metric_id": state.metric_id,
            "error": getattr(state, 'error', None),
            "needs_clarification": state.needs_clarification,
            "message_count": len(state.messages),
        }

    def record_auto_feedback(
        self,
        state: Any,
        fail_reason: FailReason,
        context_snapshot: Dict[str, Any],
        raw_llm_output: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        记录自动检测到的失败反馈

        Args:
            state: ConversationState
            fail_reason: 失败原因
            context_snapshot: 上下文快照
            raw_llm_output: LLM 原始输出

        Returns:
            反馈记录字典
        """
        # TODO: 实际写入数据库
        feedback_record = {
            "session_id": state.session_id,
            "turn_index": len(state.messages) // 2,  # 粗略计算轮次
            "feedback_source": "auto",
            "fail_reason": fail_reason.value,
            "context_snapshot": json.dumps(context_snapshot, ensure_ascii=False),
            "raw_llm_output": raw_llm_output,
            "clarification_type": getattr(state, 'clarification_type', None),
            "clarification_question": getattr(state, 'clarification_message', None),
            "feedback": 0,  # 自动检测默认为无反馈
            "metric_id": state.metric_id,
        }

        # TODO: 写入 PostgreSQL clarification_feedback 表
        # self.db.insert("clarification_feedback", feedback_record)

        print(f"[AutoFailDetector] 记录自动失败反馈: {fail_reason.value}")
        return feedback_record


# 全局单例
_auto_fail_detector = None

def get_auto_fail_detector() -> AutoFailDetector:
    """获取全局自动失败检测器"""
    global _auto_fail_detector
    if _auto_fail_detector is None:
        _auto_fail_detector = AutoFailDetector()
    return _auto_fail_detector
