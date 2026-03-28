"""
反馈分析器 - 模式挖掘和统计分析
"""
from typing import Dict, Any, List, Optional
from collections import Counter
from dataclasses import dataclass
import json
import os


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
                    password=os.getenv("PG_PASSWORD", "admin123"),
                    database=os.getenv("PG_DATABASE", "dev_metric")
                )
            except Exception as e:
                print(f"[FeedbackAnalyzer] 数据库连接失败: {e}")
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
        # TODO: 从数据库查询实际数据
        # 示例 SQL:
        # SELECT
        #     COUNT(*) as total,
        #     SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as success,
        #     SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as fail,
        #     SUM(CASE WHEN feedback_source = 'silent' THEN 1 ELSE 0 END) as silent
        # FROM clarification_feedback
        # WHERE clarification_type = ?

        # 临时返回示例数据
        return ClarificationStats(
            total=100,
            success=45,
            fail=15,
            silent=40,
            success_rate=45.0,
            fail_rate=15.0,
            silent_rate=40.0
        )

    def get_fail_reason_distribution(self) -> List[FailReasonStats]:
        """
        获取失败原因分布

        Returns:
            List[FailReasonStats]: 失败原因统计列表
        """
        # TODO: 从数据库查询实际数据
        # 示例 SQL:
        # SELECT fail_reason, COUNT(*) as count
        # FROM clarification_feedback
        # WHERE feedback_source = 'auto' AND fail_reason IS NOT NULL
        # GROUP BY fail_reason
        # ORDER BY count DESC

        # 临时返回示例数据
        return [
            FailReasonStats(fail_reason="no_data", count=35, percentage=50.0),
            FailReasonStats(fail_reason="no_metric", count=20, percentage=28.6),
            FailReasonStats(fail_reason="sql_error", count=10, percentage=14.3),
            FailReasonStats(fail_reason="intent_fail", count=5, percentage=7.1),
        ]

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
        # TODO: 从数据库查询实际数据
        # 示例 SQL:
        # SELECT missing_fields, COUNT(*) as freq,
        #        SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as fail_count
        # FROM clarification_feedback
        # WHERE feedback = -1 AND missing_fields IS NOT NULL
        # GROUP BY missing_fields
        # ORDER BY freq DESC
        # LIMIT ?

        # 临时返回示例数据
        return [
            MissingFieldsPattern(
                missing_fields='["time_range"]',
                frequency=45,
                fail_count=10,
                fail_rate=22.2
            ),
            MissingFieldsPattern(
                missing_fields='["metric_name", "time_range"]',
                frequency=30,
                fail_count=12,
                fail_rate=40.0
            ),
            MissingFieldsPattern(
                missing_fields='["dimension"]',
                frequency=20,
                fail_count=3,
                fail_rate=15.0
            ),
        ]

    def get_clarification_success_rate_by_type(self) -> Dict[str, float]:
        """
        获取各类型追问的成功率

        Returns:
            Dict[str, float]: 类型 -> 成功率
        """
        # TODO: 从数据库查询实际数据
        # 示例 SQL:
        # SELECT clarification_type,
        #        ROUND(SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as success_rate
        # FROM clarification_feedback
        # GROUP BY clarification_type
        # ORDER BY success_rate

        # 临时返回示例数据
        return {
            "metric_missing": 65.5,
            "time_range_missing": 78.2,
            "dimension_missing": 72.0,
            "no_data": 45.0,
            "sql_error": 30.0,
        }

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
        """
        # TODO: 从数据库查询实际数据
        # 示例 SQL:
        # SELECT cf.session_id, cf.clarification_question, cf.created_at,
        #        (SELECT COUNT(*) FROM messages m
        #         WHERE m.session_id = cf.session_id
        #           AND m.role = 'user'
        #           AND m.created_at > cf.created_at
        #           AND m.created_at < cf.created_at + INTERVAL '5 minute') as followup_count
        # FROM clarification_feedback cf
        # WHERE cf.feedback_source = 'auto' AND cf.feedback = 0
        # HAVING followup_count = 0

        # 临时返回示例数据
        return [
            {
                "session_id": "sess_001",
                "clarification_question": "请问您想查询哪个时间段的销售额？",
                "created_at": "2026-03-28T10:30:00",
                "threshold_minutes": threshold_minutes,
            },
            {
                "session_id": "sess_002",
                "clarification_question": "需要按什么维度查看？",
                "created_at": "2026-03-28T10:25:00",
                "threshold_minutes": threshold_minutes,
            },
        ]

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
            print("[FeedbackAnalyzer] 无法连接数据库")
            return []

        try:
            cursor = db.cursor()
            sql = f"""
                SELECT id, session_id, turn_index, fail_reason, clarification_type,
                       clarification_question, context_snapshot, user_response, created_at
                FROM clarification_feedback
                WHERE created_at >= NOW() - INTERVAL '{days} days'
                  AND (feedback = -1 OR (feedback = 0 AND fail_reason IS NOT NULL))
                ORDER BY created_at DESC
                LIMIT {limit}
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()

            feedbacks = []
            for row in rows:
                context = None
                if row[6]:
                    try:
                        context = json.loads(row[6])
                    except:
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
            print(f"[FeedbackAnalyzer] 查询负反馈失败: {e}")
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
            print("[FeedbackAnalyzer] 无法连接数据库")
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
            print(f"[FeedbackAnalyzer] 查询优化建议失败: {e}")
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
        # TODO: 从数据库查询实际数据
        # 示例 SQL:
        # SELECT context_snapshot, raw_llm_output, created_at
        # FROM clarification_feedback
        # WHERE fail_reason = ?
        # ORDER BY created_at DESC
        # LIMIT ?

        # 临时返回示例数据
        return [
            {
                "session_id": "sess_003",
                "context_snapshot": {
                    "metric_name": "广告转化率",
                    "time_range": None,
                    "entities": {"metric_name": "广告转化率"}
                },
                "raw_llm_output": '{"needs_clarification": true, "question": "请问您想查询哪个时间范围？"}',
                "created_at": "2026-03-28T11:00:00",
            },
        ]

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
