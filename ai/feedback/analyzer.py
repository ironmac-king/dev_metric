"""
反馈分析器 - 模式挖掘和统计分析
"""
from typing import Dict, Any, List, Optional
from collections import Counter
from dataclasses import dataclass
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ai.config.logging_config import get_logger

logger = get_logger("ai.feedback_analyzer")


@dataclass
class ClarificationStats:
    """追问统计"""
    total: int
    success: int
    fail: int
    silent: int
    success_rate: float
    fail_rate: float
    silent_rate: float


@dataclass
class MissingFieldsPattern:
    """缺失字段组合模式"""
    missing_fields: str
    frequency: int
    fail_count: int
    fail_rate: float


@dataclass
class FailReasonStats:
    """失败原因统计"""
    fail_reason: str
    count: int
    percentage: float


@dataclass
class NegativeFeedback:
    """负反馈记录"""
    id: int
    session_id: str
    turn_index: int
    fail_reason: Optional[str]
    clarification_type: Optional[str]
    clarification_question: Optional[str]
    context_snapshot: Optional[Dict[str, Any]]
    user_question: Optional[str]
    created_at: str


@dataclass
class FailurePattern:
    """失败模式"""
    term: str
    count: int
    pattern_type: str  # intent_term, clarification_term, missing_term


class FeedbackAnalyzer:
    """反馈分析器 - 模式挖掘和统计分析"""

    def __init__(self):
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

    def get_clarification_stats(
        self,
        clarification_type: Optional[str] = None
    ) -> ClarificationStats:
        """
        获取追问统计

        Args:
            clarification_type: 追问类型筛选

        Returns:
            ClarificationStats: 追问统计
        """
        db = self._get_db_connection()
        if not db:
            return ClarificationStats(total=0, success=0, fail=0, silent=0,
                                      success_rate=0, fail_rate=0, silent_rate=0)

        try:
            cursor = db.cursor()
            if clarification_type:
                sql = """
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as success,
                           SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as fail,
                           SUM(CASE WHEN feedback_source = 'silent' THEN 1 ELSE 0 END) as silent
                    FROM clarification_feedback
                    WHERE clarification_type = %s
                """
                cursor.execute(sql, (clarification_type,))
            else:
                sql = """
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as success,
                           SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as fail,
                           SUM(CASE WHEN feedback_source = 'silent' THEN 1 ELSE 0 END) as silent
                    FROM clarification_feedback
                """
                cursor.execute(sql)

            row = cursor.fetchone()
            cursor.close()

            total = row[0] or 0
            success = row[1] or 0
            fail = row[2] or 0
            silent = row[3] or 0

            return ClarificationStats(
                total=total,
                success=success,
                fail=fail,
                silent=silent,
                success_rate=(success / total * 100) if total > 0 else 0,
                fail_rate=(fail / total * 100) if total > 0 else 0,
                silent_rate=(silent / total * 100) if total > 0 else 0
            )
        except Exception as e:
            logger.info(f"查询追问统计失败: {e}")
            return ClarificationStats(total=0, success=0, fail=0, silent=0,
                                      success_rate=0, fail_rate=0, silent_rate=0)

    def get_fail_reason_distribution(self) -> List[FailReasonStats]:
        """
        获取失败原因分布

        Returns:
            List[FailReasonStats]: 失败原因统计列表
        """
        db = self._get_db_connection()
        if not db:
            return []

        try:
            cursor = db.cursor()
            sql = """
                SELECT fail_reason, COUNT(*) as count
                FROM clarification_feedback
                WHERE feedback_source = 'auto' AND fail_reason IS NOT NULL
                GROUP BY fail_reason
                ORDER BY count DESC
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()

            total = sum(row[1] for row in rows)
            return [
                FailReasonStats(
                    fail_reason=row[0],
                    count=row[1],
                    percentage=(row[1] / total * 100) if total > 0 else 0
                )
                for row in rows
            ]
        except Exception as e:
            logger.info(f"查询失败原因分布失败: {e}")
            return []

    def get_missing_fields_patterns(
        self,
        limit: int = 20
    ) -> List[MissingFieldsPattern]:
        """
        获取高频缺失字段组合模式

        Args:
            limit: 返回数量限制

        Returns:
            List[MissingFieldsPattern]: 缺失字段组合列表
        """
        db = self._get_db_connection()
        if not db:
            return []

        try:
            cursor = db.cursor()
            sql = """
                SELECT missing_fields, COUNT(*) as freq,
                       SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as fail_count
                FROM clarification_feedback
                WHERE feedback = -1 AND missing_fields IS NOT NULL
                GROUP BY missing_fields
                ORDER BY freq DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            cursor.close()

            return [
                MissingFieldsPattern(
                    missing_fields=row[0],
                    frequency=row[1],
                    fail_count=row[2] or 0,
                    fail_rate=(row[2] or 0) / row[1] * 100 if row[1] > 0 else 0
                )
                for row in rows
            ]
        except Exception as e:
            logger.info(f"查询缺失字段模式失败: {e}")
            return []

    def get_clarification_success_rate_by_type(self) -> Dict[str, float]:
        """
        获取各类型追问的成功率

        Returns:
            Dict[str, float]: 类型 -> 成功率
        """
        db = self._get_db_connection()
        if not db:
            return {}

        try:
            cursor = db.cursor()
            sql = """
                SELECT clarification_type,
                       ROUND(SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as success_rate
                FROM clarification_feedback
                WHERE clarification_type IS NOT NULL
                GROUP BY clarification_type
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()

            return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.info(f"查询追问成功率失败: {e}")
            return {}

    def get_silent_user_sessions(
        self,
        threshold_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        检测沉默用户（追问后离开）

        Args:
            threshold_minutes: 阈值（分钟）

        Returns:
            List[Dict[str, Any]]: 沉默会话列表

        Note: 当前 sessions 在内存中，需要会话持久化才能支持此功能
        """
        # 当前 sessions 在内存中不支持查询，返回空列表
        # 未来需要会话持久化到数据库才能实现此功能
        return []

    def get_low_success_rate_types(
        self,
        threshold: float = 50.0
    ) -> List[Dict[str, Any]]:
        """
        获取低成功率的追问类型（需要优先优化）

        Args:
            threshold: 成功率阈值

        Returns:
            List[Dict[str, Any]]: 需要优化的类型列表
        """
        stats = self.get_clarification_success_rate_by_type()
        return [
            {"clarification_type": k, "success_rate": v}
            for k, v in stats.items()
            if v < threshold
        ]

    def get_negative_feedbacks(
        self,
        days: int = 1,
        limit: int = 100
    ) -> List[NegativeFeedback]:
        """
        获取近N天的负反馈（反馈为-1或自动检测失败）

        Args:
            days: 近几天
            limit: 返回数量限制

        Returns:
            List[NegativeFeedback]: 负反馈列表
        """
        db = self._get_db_connection()
        if not db:
            logger.warning("[FeedbackAnalyzer] 无法连接数据库")
            return []

        try:
            cursor = db.cursor()
            sql = """
                SELECT id, session_id, turn_index, fail_reason, clarification_type,
                       clarification_question, context_snapshot, user_response, created_at
                FROM clarification_feedback
                WHERE created_at >= NOW() - INTERVAL %s
                  AND (feedback = -1 OR (feedback = 0 AND fail_reason IS NOT NULL))
                ORDER BY created_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (f"{days} days", limit))
            rows = cursor.fetchall()
            cursor.close()

            feedbacks = []
            for row in rows:
                context = None
                if row[6]:
                    try:
                        context = json.loads(row[6])
                    except Exception:
                        pass

                feedbacks.append(NegativeFeedback(
                    id=row[0],
                    session_id=row[1],
                    turn_index=row[2],
                    fail_reason=row[3],
                    clarification_type=row[4],
                    clarification_question=row[5],
                    context_snapshot=context,
                    user_question=row[7],
                    created_at=str(row[8]) if row[8] else ""
                ))
            return feedbacks
        except Exception as e:
            logger.info(f"查询负反馈失败: {e}")
            return []

    def analyze_failure_patterns(
        self,
        feedbacks: List[NegativeFeedback]
    ) -> Dict[str, Any]:
        """
        分析失败模式，统计高频失败词和高频意图

        Args:
            feedbacks: 负反馈列表

        Returns:
            Dict[str, Any]: 失败模式分析结果
        """
        if not feedbacks:
            return {
                "high_freq_terms": [],
                "high_freq_intents": [],
                "high_freq_clarification_types": [],
                "total_count": 0
            }

        # 统计失败词（从用户问题和上下文中提取）
        term_counter = Counter()
        intent_counter = Counter()
        clarification_counter = Counter()

        for fb in feedbacks:
            # 从 context_snapshot 中提取指标名
            if fb.context_snapshot:
                metric_name = fb.context_snapshot.get("metric_name")
                if metric_name:
                    term_counter[metric_name] += 1

            # 从用户问题中提取关键词
            if fb.user_question:
                # 简单分词：取前5个字作为词组
                question = fb.user_question.strip()
                if len(question) >= 2:
                    term_counter[question[:10]] += 1

            # 统计失败原因
            if fb.fail_reason:
                intent_counter[fb.fail_reason] += 1

            # 统计追问类型
            if fb.clarification_type:
                clarification_counter[fb.clarification_type] += 1

        # 获取高频项（出现3次以上）
        high_freq_terms = [(term, count) for term, count in term_counter.most_common(20) if count >= 3]
        high_freq_intents = [(term, count) for term, count in intent_counter.most_common(10) if count >= 2]
        high_freq_clarification_types = [(term, count) for term, count in clarification_counter.most_common(10) if count >= 2]

        return {
            "high_freq_terms": high_freq_terms,
            "high_freq_intents": high_freq_intents,
            "high_freq_clarification_types": high_freq_clarification_types,
            "total_count": len(feedbacks)
        }

    def get_unhandled_suggestions(self) -> List[Dict[str, Any]]:
        """
        获取待审核的优化建议（status = 'pending'）

        Returns:
            List[Dict[str, Any]]: 待审核建议列表
        """
        db = self._get_db_connection()
        if not db:
            logger.warning("[FeedbackAnalyzer] 无法连接数据库")
            return []

        try:
            cursor = db.cursor()
            sql = """
                SELECT id, suggestion_type, target_table, target_id,
                       original_value, suggested_value, fail_count, confidence,
                       reason, created_at
                FROM optimization_suggestions
                WHERE status = 'pending'
                ORDER BY confidence DESC, fail_count DESC
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()

            suggestions = []
            for row in rows:
                suggestions.append({
                    "id": row[0],
                    "suggestion_type": row[1],
                    "target_table": row[2],
                    "target_id": row[3],
                    "original_value": row[4],
                    "suggested_value": row[5],
                    "fail_count": row[6],
                    "confidence": float(row[7]) if row[7] else 0.0,
                    "reason": row[8],
                    "created_at": str(row[9]) if row[9] else ""
                })
            return suggestions
        except Exception as e:
            logger.info(f"查询优化建议失败: {e}")
            return []

    def analyze_failure_context(
        self,
        fail_reason: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        分析特定失败原因的上下文

        Args:
            fail_reason: 失败原因
            limit: 返回数量

        Returns:
            List[Dict[str, Any]]: 失败案例列表
        """
        db = self._get_db_connection()
        if not db:
            return []

        try:
            cursor = db.cursor()
            sql = """
                SELECT session_id, context_snapshot, raw_llm_output, created_at
                FROM clarification_feedback
                WHERE fail_reason = %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (fail_reason, limit))
            rows = cursor.fetchall()
            cursor.close()

            results = []
            for row in rows:
                context = None
                if row[1]:
                    try:
                        context = json.loads(row[1])
                    except Exception:
                        pass

                results.append({
                    "session_id": row[0],
                    "context_snapshot": context,
                    "raw_llm_output": row[2],
                    "created_at": str(row[3]) if row[3] else None
                })
            return results
        except Exception as e:
            logger.info(f"查询失败上下文失败: {e}")
            return []

    def generate_optimization_suggestions(self) -> List[str]:
        """
        生成优化建议

        Returns:
            List[str]: 优化建议列表
        """
        suggestions = []

        # 1. 分析低成功率类型
        low_rate_types = self.get_low_success_rate_types(threshold=50.0)
        if low_rate_types:
            suggestions.append(
                f"【高优】以下追问类型成功率低于 50%，需要优化: "
                f"{', '.join([t['clarification_type'] for t in low_rate_types])}"
            )

        # 2. 分析高频失败模式
        patterns = self.get_missing_fields_patterns(limit=5)
        high_fail_patterns = [p for p in patterns if p.fail_rate > 30]
        if high_fail_patterns:
            suggestions.append(
                f"【高优】以下缺失字段组合失败率超过 30%: "
                f"{', '.join([p.missing_fields for p in high_fail_patterns])}"
            )

        # 3. 分析沉默用户
        silent_users = self.get_silent_user_sessions()
        if len(silent_users) > 10:
            suggestions.append(
                f"【中优】沉默用户较多 ({len(silent_users)} 个会话)，追问效果需提升"
            )

        # 4. 分析失败原因分布
        fail_dist = self.get_fail_reason_distribution()
        if fail_dist:
            top_fail = fail_dist[0]
            suggestions.append(
                f"【数据质量】主要失败原因: {top_fail.fail_reason} ({top_fail.percentage:.1f}%)，"
                f"建议优先改善该场景"
            )

        if not suggestions:
            suggestions.append("当前系统表现良好，暂无需紧急优化的问题")

        return suggestions


# 全局单例
_feedback_analyzer = None

def get_feedback_analyzer() -> FeedbackAnalyzer:
    """获取全局反馈分析器"""
    global _feedback_analyzer
    if _feedback_analyzer is None:
        _feedback_analyzer = FeedbackAnalyzer()
    return _feedback_analyzer
