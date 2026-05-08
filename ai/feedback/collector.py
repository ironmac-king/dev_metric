"""
反馈收集器 - 收集用户点赞点踩反馈
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json
from datetime import datetime
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ai.config.logging_config import get_logger

logger = get_logger("ai.feedback_collector")


class FeedbackType(Enum):
    """反馈类型"""
    POSITIVE = 1   # 点赞
    NEGATIVE = -1  # 点踩
    NO_FEEDBACK = 0


class FeedbackSource(Enum):
    """反馈来源"""
    USER = "user"      # 用户评价
    AUTO = "auto"     # 自动检测
    SILENT = "silent"  # 沉默用户


@dataclass
class FeedbackRecord:
    """反馈记录"""
    session_id: str
    turn_index: int
    feedback_source: str
    feedback: int
    fail_reason: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    raw_llm_output: Optional[str] = None
    clarification_type: Optional[str] = None
    clarification_question: Optional[str] = None
    user_response: Optional[str] = None
    missing_fields: Optional[Dict[str, Any]] = None
    metric_id: Optional[int] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "feedback_source": self.feedback_source,
            "feedback": self.feedback,
            "fail_reason": self.fail_reason,
            "context_snapshot": json.dumps(self.context_snapshot, ensure_ascii=False) if self.context_snapshot else None,
            "raw_llm_output": self.raw_llm_output,
            "clarification_type": self.clarification_type,
            "clarification_question": self.clarification_question,
            "user_response": self.user_response,
            "missing_fields": json.dumps(self.missing_fields, ensure_ascii=False) if self.missing_fields else None,
            "metric_id": self.metric_id,
            "created_at": self.created_at or datetime.now().isoformat(),
        }


class FeedbackCollector:
    """反馈收集器"""

    def __init__(self):
        self._feedback_cache: List[FeedbackRecord] = []
        self._db = None

    def _get_db_connection(self):
        """获取数据库连接"""
        if self._db is None:
            try:
                import psycopg2
                self._db = psycopg2.connect(
                    host=os.getenv("PG_HOST", "localhost"),
                    port=os.getenv("PG_PORT", "5432"),
                    user=os.getenv("PG_USER", "postgres"),
                    password=os.getenv("PG_PASSWORD"),
                    database=os.getenv("PG_DATABASE", "dev_metric")
                )
            except Exception as e:
                logger.info(f"数据库连接失败: {e}")
                return None
        return self._db

    def _persist_feedback(self, record: FeedbackRecord) -> bool:
        """写入数据库"""
        db = self._get_db_connection()
        if not db:
            logger.info(f"无法连接数据库，反馈仅保留在内存")
            return False

        try:
            cursor = db.cursor()
            sql = """
                INSERT INTO clarification_feedback
                (session_id, turn_index, feedback_source, feedback, fail_reason,
                 context_snapshot, raw_llm_output, clarification_type, clarification_question,
                 user_response, missing_fields, metric_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                record.session_id,
                record.turn_index,
                record.feedback_source,
                record.feedback,
                record.fail_reason,
                json.dumps(record.context_snapshot, ensure_ascii=False) if record.context_snapshot else None,
                record.raw_llm_output,
                record.clarification_type,
                record.clarification_question,
                record.user_response,
                json.dumps(record.missing_fields, ensure_ascii=False) if record.missing_fields else None,
                record.metric_id,
                record.created_at or datetime.now().isoformat()
            ))
            db.commit()
            cursor.close()
            logger.info(f"[FeedbackCollector] 已写入数据库: session={record.session_id}")
            return True
        except Exception as e:
            logger.error(f"[FeedbackCollector] 写入数据库失败: {e}")
            return False

    def record_user_feedback(
        self,
        session_id: str,
        turn_index: int,
        feedback: FeedbackType,
        metric_id: Optional[int] = None,
        clarification_type: Optional[str] = None,
        clarification_question: Optional[str] = None,
        user_response: Optional[str] = None,
        missing_fields: Optional[Dict[str, Any]] = None,
        context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> FeedbackRecord:
        """
        记录用户反馈（点赞/点踩）

        Args:
            session_id: 会话 ID
            turn_index: 对话轮次
            feedback: 反馈类型（POSITIVE/NEGATIVE）
            metric_id: 关联指标 ID
            clarification_type: 追问类型
            clarification_question: 追问内容
            user_response: 用户响应
            missing_fields: 缺失字段
            context_snapshot: 上下文快照

        Returns:
            FeedbackRecord: 反馈记录
        """
        record = FeedbackRecord(
            session_id=session_id,
            turn_index=turn_index,
            feedback_source=FeedbackSource.USER.value,
            feedback=feedback.value,
            metric_id=metric_id,
            clarification_type=clarification_type,
            clarification_question=clarification_question,
            user_response=user_response,
            missing_fields=missing_fields,
            context_snapshot=context_snapshot,
            created_at=datetime.now().isoformat(),
        )

        self._feedback_cache.append(record)
        self._persist_feedback(record)

        logger.info(f"[FeedbackCollector] 记录用户反馈: session={session_id}, feedback={feedback.name}")
        return record

    def record_auto_feedback(
        self,
        session_id: str,
        turn_index: int,
        fail_reason: str,
        clarification_type: Optional[str] = None,
        clarification_question: Optional[str] = None,
        metric_id: Optional[int] = None,
        context_snapshot: Optional[Dict[str, Any]] = None,
        raw_llm_output: Optional[str] = None,
    ) -> FeedbackRecord:
        """
        记录自动检测到的失败

        Args:
            session_id: 会话 ID
            turn_index: 对话轮次
            fail_reason: 失败原因
            clarification_type: 追问类型
            clarification_question: 追问内容
            metric_id: 关联指标 ID
            context_snapshot: 上下文快照
            raw_llm_output: LLM 原始输出

        Returns:
            FeedbackRecord: 反馈记录
        """
        record = FeedbackRecord(
            session_id=session_id,
            turn_index=turn_index,
            feedback_source=FeedbackSource.AUTO.value,
            feedback=FeedbackType.NO_FEEDBACK.value,
            fail_reason=fail_reason,
            clarification_type=clarification_type,
            clarification_question=clarification_question,
            metric_id=metric_id,
            context_snapshot=context_snapshot,
            raw_llm_output=raw_llm_output,
            created_at=datetime.now().isoformat(),
        )

        self._feedback_cache.append(record)
        self._persist_feedback(record)

        logger.info(f"[FeedbackCollector] 记录自动失败: session={session_id}, fail_reason={fail_reason}")
        return record

    def record_silent_user(
        self,
        session_id: str,
        turn_index: int,
        clarification_question: Optional[str] = None,
        clarification_type: Optional[str] = None,
        metric_id: Optional[int] = None,
    ) -> FeedbackRecord:
        """
        记录沉默用户（追问后离开）

        Args:
            session_id: 会话 ID
            turn_index: 对话轮次
            clarification_question: 追问内容
            clarification_type: 追问类型
            metric_id: 关联指标 ID

        Returns:
            FeedbackRecord: 反馈记录
        """
        record = FeedbackRecord(
            session_id=session_id,
            turn_index=turn_index,
            feedback_source=FeedbackSource.SILENT.value,
            feedback=FeedbackType.NO_FEEDBACK.value,
            clarification_type=clarification_type,
            clarification_question=clarification_question,
            metric_id=metric_id,
            created_at=datetime.now().isoformat(),
        )

        self._feedback_cache.append(record)
        self._persist_feedback(record)

        logger.info(f"[FeedbackCollector] 记录沉默用户: session={session_id}")
        return record

    def get_session_feedback_stats(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话反馈统计

        Args:
            session_id: 会话 ID

        Returns:
            统计信息
        """
        session_feedback = [f for f in self._feedback_cache if f.session_id == session_id]

        if not session_feedback:
            return {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "silent": 0,
                "auto": 0,
            }

        return {
            "total": len(session_feedback),
            "positive": sum(1 for f in session_feedback if f.feedback == FeedbackType.POSITIVE.value),
            "negative": sum(1 for f in session_feedback if f.feedback == FeedbackType.NEGATIVE.value),
            "silent": sum(1 for f in session_feedback if f.feedback_source == FeedbackSource.SILENT.value),
            "auto": sum(1 for f in session_feedback if f.feedback_source == FeedbackSource.AUTO.value),
        }


# 全局单例
_feedback_collector = None

def get_feedback_collector() -> FeedbackCollector:
    """获取全局反馈收集器"""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector()
    return _feedback_collector
