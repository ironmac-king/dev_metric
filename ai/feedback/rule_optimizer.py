"""
规则优化器 - 基于负反馈生成优化建议（不自动应用）
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ai.config.logging_config import get_logger

logger = get_logger("ai.rule_optimizer")


@dataclass
class OptimizationSuggestion:
    """优化建议"""
    suggestion_type: str  # add_intent_pattern, modify_pattern, add_synonym
    target_table: str     # intent_templates, business_terms 等
    target_id: Optional[int]
    original_value: Optional[str]
    suggested_value: str
    fail_count: int
    confidence: float
    reason: str


class RuleOptimizer:
    """基于反馈生成优化建议（不自动应用，只存储供管理员审核）"""

    def __init__(self):
        self._db = None
        self.analyzer = None
        # 延迟导入避免循环依赖
        from ai.feedback.analyzer import FeedbackAnalyzer
        self.analyzer = FeedbackAnalyzer()

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

    def daily_analysis(self) -> List[OptimizationSuggestion]:
        """
        每日分析 - 分析昨天的负反馈，生成优化建议

        Returns:
            List[OptimizationSuggestion]: 生成的优化建议列表
        """
        logger.info("[RuleOptimizer] 开始每日分析...")

        # 1. 获取昨天的负反馈
        feedbacks = self.analyzer.get_negative_feedbacks(days=1)
        if not feedbacks:
            logger.info("[RuleOptimizer] 昨日无负反馈")
            return []

        logger.info(f"[RuleOptimizer] 获取到 {len(feedbacks)} 条负反馈")

        # 2. 分析失败模式
        patterns = self.analyzer.analyze_failure_patterns(feedbacks)
        logger.info(f"[RuleOptimizer] 高频失败词: {patterns['high_freq_terms'][:5]}")
        logger.info(f"[RuleOptimizer] 高频失败意图: {patterns['high_freq_intents'][:5]}")

        # 3. 生成优化建议（不自动应用，只存储）
        suggestions = self._generate_suggestions(patterns, feedbacks)

        # 4. 存入数据库
        saved_count = self._save_suggestions(suggestions)
        logger.info(f"[RuleOptimizer] 每日分析完成，生成 {saved_count} 条优化建议")

        return suggestions

    def _generate_suggestions(
        self,
        patterns: Dict[str, Any],
        feedbacks: List
    ) -> List[OptimizationSuggestion]:
        """
        生成优化建议

        Args:
            patterns: 失败模式分析结果
            feedbacks: 原始负反馈列表

        Returns:
            List[OptimizationSuggestion]: 优化建议列表
        """
        suggestions = []

        # 1. 高频失败词 -> 建议补充意图模板
        for term, count in patterns["high_freq_terms"]:
            if count >= 3:  # 出现3次以上
                # 检查是否已存在相同的待审核建议
                if self._is_duplicate_suggestion(term):
                    continue

                suggestions.append(OptimizationSuggestion(
                    suggestion_type="add_intent_pattern",
                    target_table="intent_templates",
                    target_id=None,
                    original_value=None,
                    suggested_value=term,
                    fail_count=count,
                    confidence=min(count / 10, 0.90),
                    reason=f"近1天出现 {count} 次失败，建议添加为意图匹配模式"
                ))

        # 2. 高频失败意图 -> 建议优化对应意图模板
        for intent, count in patterns["high_freq_intents"]:
            if count >= 3:
                # 查找是否有对应的意图模板
                target_id = self._find_intent_template_id(intent)
                if target_id:
                    suggestions.append(OptimizationSuggestion(
                        suggestion_type="modify_pattern",
                        target_table="intent_templates",
                        target_id=target_id,
                        original_value=intent,
                        suggested_value=f"{intent}_v2",
                        fail_count=count,
                        confidence=min(count / 15, 0.85),
                        reason=f"意图 '{intent}' 失败率较高，建议优化匹配模式"
                    ))

        # 3. 高频追问类型 -> 建议添加同义词或扩展词
        for clar_type, count in patterns["high_freq_clarification_types"]:
            if count >= 5:  # 出现5次以上
                # 尝试从负反馈中提取用户实际想问的词
                actual_terms = self._extract_actual_terms(feedbacks, clar_type)
                for term in actual_terms:
                    if self._is_duplicate_suggestion(term):
                        continue

                    suggestions.append(OptimizationSuggestion(
                        suggestion_type="add_synonym",
                        target_table="business_terms",
                        target_id=None,
                        original_value=None,
                        suggested_value=term,
                        fail_count=count,
                        confidence=min(count / 20, 0.80),
                        reason=f"'{clar_type}' 类型追问常见，建议添加业务术语 '{term}' 及其同义词"
                    ))

        return suggestions

    def _is_duplicate_suggestion(self, term: str) -> bool:
        """检查是否已存在相同的待审核建议"""
        db = self._get_db_connection()
        if not db:
            return False

        try:
            cursor = db.cursor()
            sql = """
                SELECT COUNT(*) FROM optimization_suggestions
                WHERE suggested_value = %s AND status IN ('pending', 'applied')
            """
            cursor.execute(sql, (term,))
            count = cursor.fetchone()[0]
            cursor.close()
            return count > 0
        except Exception as e:
            logger.info(f"检查重复建议失败: {e}")
            return False

    def _find_intent_template_id(self, intent: str) -> Optional[int]:
        """查找意图模板ID"""
        db = self._get_db_connection()
        if not db:
            return None

        try:
            cursor = db.cursor()
            sql = """
                SELECT id FROM intent_templates
                WHERE intent = %s OR name LIKE %s
                LIMIT 1
            """
            cursor.execute(sql, (intent, f"%{intent}%"))
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except Exception as e:
            logger.info(f"查找意图模板失败: {e}")
            return None

    def _extract_actual_terms(
        self,
        feedbacks: List,
        clarification_type: str
    ) -> List[str]:
        """从负反馈中提取用户实际想问的词"""
        terms = []
        for fb in feedbacks:
            if fb.clarification_type != clarification_type:
                continue

            # 从 context_snapshot 中提取 metric_name
            if fb.context_snapshot:
                metric_name = fb.context_snapshot.get("metric_name")
                if metric_name and len(metric_name) >= 2:
                    terms.append(metric_name)

            # 从用户问题中提取
            if fb.user_question:
                question = fb.user_question.strip()
                if len(question) >= 2:
                    terms.append(question[:10])

        return list(set(terms))[:5]  # 去重，最多返回5个

    def _save_suggestions(
        self,
        suggestions: List[OptimizationSuggestion]
    ) -> int:
        """保存建议到数据库"""
        if not suggestions:
            return 0

        db = self._get_db_connection()
        if not db:
            logger.info("[RuleOptimizer] 无法连接数据库")
            return 0

        saved_count = 0
        try:
            cursor = db.cursor()
            sql = """
                INSERT INTO optimization_suggestions
                (suggestion_type, target_table, target_id, original_value,
                 suggested_value, fail_count, confidence, status, reason, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW())
            """

            for suggestion in suggestions:
                cursor.execute(sql, (
                    suggestion.suggestion_type,
                    suggestion.target_table,
                    suggestion.target_id,
                    suggestion.original_value,
                    suggestion.suggested_value,
                    suggestion.fail_count,
                    suggestion.confidence,
                    suggestion.reason
                ))
                saved_count += 1

            db.commit()
            cursor.close()
            logger.info(f"已保存 {saved_count} 条建议到数据库")
        except Exception as e:
            logger.info(f"保存建议失败: {e}")
            db.rollback()

        return saved_count

    def apply_suggestion(self, suggestion_id: int, applied_by: str = "admin") -> bool:
        """
        应用优化建议

        Args:
            suggestion_id: 建议ID
            applied_by: 操作用户

        Returns:
            bool: 是否成功
        """
        db = self._get_db_connection()
        if not db:
            return False

        try:
            cursor = db.cursor()

            # 获取建议详情
            cursor.execute(
                "SELECT * FROM optimization_suggestions WHERE id = %s",
                (suggestion_id,)
            )
            suggestion = cursor.fetchone()
            if not suggestion:
                logger.info(f"建议 {suggestion_id} 不存在")
                cursor.close()
                return False

            suggestion_type = suggestion[1]  # suggestion_type
            target_table = suggestion[2]    # target_table
            target_id = suggestion[3]        # target_id
            suggested_value = suggestion[5]  # suggested_value
            original_value = suggestion[4]   # original_value

            # 根据建议类型执行不同的应用逻辑
            if suggestion_type == "add_intent_pattern":
                # 添加新的意图模板
                self._apply_add_intent_pattern(cursor, suggested_value)
            elif suggestion_type == "modify_pattern":
                # 修改现有意图模板
                self._apply_modify_pattern(cursor, target_id, suggested_value)
            elif suggestion_type == "add_synonym":
                # 添加同义词
                self._apply_add_synonym(cursor, target_table, suggested_value)

            # 更新建议状态为已应用
            cursor.execute("""
                UPDATE optimization_suggestions
                SET status = 'applied', applied_at = NOW(), applied_by = %s
                WHERE id = %s
            """, (applied_by, suggestion_id))

            db.commit()
            cursor.close()
            logger.info(f"已应用建议 {suggestion_id}")
            return True
        except Exception as e:
            logger.info(f"应用建议失败: {e}")
            db.rollback()
            return False

    def _apply_add_intent_pattern(self, cursor, pattern: str):
        """添加新的意图模板"""
        # 检查是否已存在
        cursor.execute(
            "SELECT id FROM intent_templates WHERE patterns LIKE %s",
            (f"%{pattern}%",)
        )
        if cursor.fetchone():
            logger.info(f"意图模板已存在: {pattern}")
            return

        # 插入新模板（默认配置）
        cursor.execute("""
            INSERT INTO intent_templates (name, intent, patterns, priority, response, status)
            VALUES (%s, 'query_value', %s, 5, '您好，我来帮您查询', 1)
        """, (f"自动添加_{pattern}", pattern))
        logger.info(f"[RuleOptimizer] 添加意图模板: {pattern}")

    def _apply_modify_pattern(self, cursor, target_id: int, new_value: str):
        """修改现有意图模板"""
        if not target_id:
            return

        cursor.execute("""
            UPDATE intent_templates
            SET patterns = CONCAT(patterns, ',', %s)
            WHERE id = %s
        """, (new_value, target_id))
        logger.info(f"[RuleOptimizer] 修改意图模板 {target_id}: 添加模式 {new_value}")

    def _apply_add_synonym(self, cursor, target_table: str, term: str):
        """添加同义词"""
        # 先检查是否已存在
        cursor.execute(
            "SELECT id FROM business_terms WHERE term_name = %s",
            (term,)
        )
        if cursor.fetchone():
            logger.info(f"业务术语已存在: {term}")
            return

        cursor.execute("""
            INSERT INTO business_terms (term_name, synonyms, status)
            VALUES (%s, %s, 1)
        """, (term, term))  # 同义词默认和术语名相同
        logger.info(f"[RuleOptimizer] 添加业务术语: {term}")

    def ignore_suggestion(self, suggestion_id: int) -> bool:
        """
        忽略优化建议

        Args:
            suggestion_id: 建议ID

        Returns:
            bool: 是否成功
        """
        db = self._get_db_connection()
        if not db:
            return False

        try:
            cursor = db.cursor()
            cursor.execute("""
                UPDATE optimization_suggestions
                SET status = 'ignored'
                WHERE id = %s
            """, (suggestion_id,))
            db.commit()
            cursor.close()
            logger.info(f"已忽略建议 {suggestion_id}")
            return True
        except Exception as e:
            logger.info(f"忽略建议失败: {e}")
            return False


# 全局单例
_rule_optimizer = None


def get_rule_optimizer() -> RuleOptimizer:
    """获取全局规则优化器"""
    global _rule_optimizer
    if _rule_optimizer is None:
        _rule_optimizer = RuleOptimizer()
    return _rule_optimizer
