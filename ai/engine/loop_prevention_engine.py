"""
防循环追问引擎
检测是否陷入循环追问，包括：语义相似、同一槽位连续追问、总轮次超限
"""
import time
from typing import Optional, List
from dataclasses import dataclass
from ai.config.logging_config import get_logger

logger = get_logger("ai.loop_prevention_engine")


@dataclass
class LoopDetectionResult:
    """循环检测结果"""
    is_loop: bool
    reason: str = ""  # semantic_similarity / consecutive_same_slot / max_turns_exceeded
    suggested_action: str = ""  # apply_default_or_stop / stop_clarification
    fallback_value: Optional[str] = None


class LoopPreventionEngine:
    """防循环追问引擎"""

    def __init__(self):
        self.similarity_threshold: float = 0.85  # 语义相似度阈值
        self.max_consecutive_clarifications: int = 3  # 单槽位最大连续追问次数
        self.max_total_clarifications: int = 5  # 总最大追问次数
        self._conversation_history: List[dict] = []  # 近期对话历史

    def detect_loop(
        self,
        state: "ConversationState",
        current: "SlotClarification"
    ) -> LoopDetectionResult:
        """
        检测是否陷入循环追问

        Args:
            state: 对话状态
            current: 当前槽位追问

        Returns:
            LoopDetectionResult: 循环检测结果
        """
        # 规则1：同一槽位连续追问检测
        slot_turns = getattr(state, "_slot_turns", {}) or {}
        consecutive = slot_turns.get(current.slot_name, 0)
        if consecutive >= self.max_consecutive_clarifications:
            logger.info(f"[LoopPrevention] 检测到同一槽位连续追问: slot={current.slot_name}, turns={consecutive}")
            return LoopDetectionResult(
                is_loop=True,
                reason="consecutive_same_slot",
                suggested_action="apply_default_or_stop",
                fallback_value=current.default_value or (current.allowed_values[0] if current.allowed_values else None)
            )

        # 规则2：总轮次检测
        total_clarifications = len(getattr(state, "_asked_slots", []) or [])
        if total_clarifications >= self.max_total_clarifications:
            logger.info(f"[LoopPrevention] 检测到总追问轮次超限: {total_clarifications}")
            return LoopDetectionResult(
                is_loop=True,
                reason="max_turns_exceeded",
                suggested_action="stop_clarification",
                fallback_value=None
            )

        # 规则3：语义相似检测（当前追问与近期消息）
        if self._check_semantic_similarity(state, current.question):
            logger.info(f"[LoopPrevention] 检测到语义相似")
            return LoopDetectionResult(
                is_loop=True,
                reason="semantic_similarity",
                suggested_action="apply_default_or_stop",
                fallback_value=current.default_value or (current.allowed_values[0] if current.allowed_values else None)
            )

        return LoopDetectionResult(is_loop=False)

    def _check_semantic_similarity(self, state: "ConversationState", current_question: str) -> bool:
        """检查当前追问是否与近期消息语义相似"""
        try:
            # 获取近期消息（最后5条）
            messages = getattr(state, "messages", []) or []
            recent_contents = []
            for msg in messages[-5:]:
                content = getattr(msg, "content", "") or ""
                if content:
                    recent_contents.append(content)

            # 计算与每条消息的相似度（简单字符重叠检测）
            current_lower = current_question.lower()
            for msg_content in recent_contents:
                msg_lower = msg_content.lower()
                # 简单检测：是否有大量字符重叠
                if self._compute_overlap_ratio(current_lower, msg_lower) > self.similarity_threshold:
                    return True

            return False
        except Exception as e:
            logger.warning(f"[LoopPrevention] 语义相似检测异常: {e}")
            return False

    def _compute_overlap_ratio(self, text1: str, text2: str) -> float:
        """计算两个文本的字符重叠率"""
        if not text1 or not text2:
            return 0.0

        set1 = set(text1)
        set2 = set(text2)

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def record_clarification(self, state: "ConversationState", slot_name: str):
        """记录一次追问，用于后续检测"""
        # 更新 _slot_turns
        if not hasattr(state, "_slot_turns") or state._slot_turns is None:
            state._slot_turns = {}
        state._slot_turns[slot_name] = state._slot_turns.get(slot_name, 0) + 1

        # 更新 _asked_slots
        if not hasattr(state, "_asked_slots") or state._asked_slots is None:
            state._asked_slots = []
        state._asked_slots.append(slot_name)

        logger.debug(f"[LoopPrevention] 记录追问: slot={slot_name}, turns={state._slot_turns.get(slot_name)}, total={len(state._asked_slots)}")

    def reset_for_new_turn(self, state: "ConversationState"):
        """在新的一轮对话开始时重置某些状态"""
        # 可选：清除某些临时状态
        pass
