"""
SQLExampleRetriever - SQL 示例检索器
支持冷启动（预置种子 SQL）和运行时检索（sql_audit_logs）
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("ai.llm_v1.sql_example_retriever")


@dataclass
class SQLExample:
    """SQL 示例"""
    question: str  # 示例问题
    sql: str       # 对应的 SQL
    metric_code: Optional[str] = None  # 关联的指标代码
    dimension: Optional[str] = None    # 关联的维度
    intent_type: Optional[str] = None  # 意图类型


# ==================== 预置种子 SQL ====================

SEED_SQL_EXAMPLES: List[SQLExample] = [
    # 场景1：基础指标查询（无维度）
    SQLExample(
        question="本月销售额是多少？",
        sql="SELECT SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31'",
        metric_code="MKI-02-0001",
        intent_type="query_value",
    ),
    SQLExample(
        question="上周订单量是多少？",
        sql="SELECT SUM(ORDERED_UNITS) AS `订单量` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-09' AND FDATE <= '2026-03-15'",
        metric_code="MKI-02-0002",
        intent_type="query_value",
    ),

    # 场景2：单维度查询
    SQLExample(
        question="本月各平台销售额是多少？",
        sql="SELECT PLATFORM, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY PLATFORM",
        metric_code="MKI-02-0001",
        dimension="PLATFORM",
        intent_type="query_value",
    ),
    SQLExample(
        question="本月各店铺销售额是多少？",
        sql="SELECT FSITE, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY FSITE",
        metric_code="MKI-02-0001",
        dimension="FSITE",
        intent_type="query_value",
    ),
    SQLExample(
        question="本月各一级品类销售额是多少？",
        sql="SELECT GROUP_1, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY GROUP_1",
        metric_code="MKI-02-0001",
        dimension="GROUP_1",
        intent_type="query_value",
    ),
    SQLExample(
        question="本月各三级品类销售额是多少？",
        sql="SELECT GROUP_3, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY GROUP_3",
        metric_code="MKI-02-0001",
        dimension="GROUP_3",
        intent_type="query_value",
    ),

    # 场景3：多维度组合查询
    SQLExample(
        question="本月各平台各店铺销售额是多少？",
        sql="SELECT PLATFORM, FSITE, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY PLATFORM, FSITE",
        metric_code="MKI-02-0001",
        dimension="PLATFORM,FSITE",
        intent_type="query_value",
    ),
    SQLExample(
        question="本月各一级品类各三级品类销售额是多少？",
        sql="SELECT GROUP_1, GROUP_3, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY GROUP_1, GROUP_3",
        metric_code="MKI-02-0001",
        dimension="GROUP_1,GROUP_3",
        intent_type="query_value",
    ),

    # 场景4：带筛选条件的查询
    SQLExample(
        question="本月销售额超过10万的店铺有哪些？",
        sql="SELECT FSITE, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY FSITE HAVING SUM(ORDERED_PRODUCTSALES) > 100000",
        metric_code="MKI-02-0001",
        dimension="FSITE",
        intent_type="query_value",
    ),

    # 场景5：排名查询（Top N）
    SQLExample(
        question="本月销售额前10的店铺是多少？",
        sql="SELECT FSITE, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31' GROUP BY FSITE ORDER BY SUM(ORDERED_PRODUCTSALES) DESC LIMIT 10",
        metric_code="MKI-02-0001",
        dimension="FSITE",
        intent_type="query_ranking",
    ),

    # 场景6：时间趋势查询
    SQLExample(
        question="近7天每日销售额是多少？",
        sql="SELECT FDATE, SUM(ORDERED_PRODUCTSALES) AS `销售额` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-09' AND FDATE <= '2026-03-15' GROUP BY FDATE ORDER BY FDATE",
        metric_code="MKI-02-0001",
        intent_type="query_trend",
    ),

    # 场景7：平均客单价
    SQLExample(
        question="本月平均客单价是多少？",
        sql="SELECT AVG(ORDERED_PRODUCTSALES / ORDERED_UNITS) AS `平均客单价` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-03-31'",
        metric_code="MKI-02-0003",
        intent_type="query_value",
    ),

    # 场景8：同比查询（当月 vs 去年同月）
    SQLExample(
        question="本月销售额同比去年怎么样？",
        sql="""SELECT
    t1.MONTHS,
    t1.current_sales AS `本月销售额`,
    t2.last_year_sales AS `去年同期销售额`,
    ROUND((t1.current_sales - t2.last_year_sales) / t2.last_year_sales * 100, 2) AS `同比增长率(%)`
FROM (
    SELECT MONTHS, SUM(ORDERED_PRODUCTSALES) AS current_sales
    FROM ids.IDS_AMZ_COMPREHENSIVE_DI
    WHERE FDATE >= '2026-04-01' AND FDATE <= '2026-04-30'
    GROUP BY MONTHS
) t1
LEFT JOIN (
    SELECT MONTHS, SUM(ORDERED_PRODUCTSALES) AS last_year_sales
    FROM ids.IDS_AMZ_COMPREHENSIVE_DI
    WHERE FDATE >= '2025-04-01' AND FDATE <= '2025-04-30'
    GROUP BY MONTHS
) t2 ON t1.MONTHS = t2.MONTHS""",
        metric_code="MKI-02-0001",
        intent_type="compare",
    ),

    # 场景9：环比查询（当月 vs 上月）
    SQLExample(
        question="本月销售额环比上月怎么样？",
        sql="""SELECT
    MONTHS,
    sales AS `本月销售额`,
    LAG(sales) OVER (ORDER BY MONTHS) AS `上月销售额`,
    ROUND((sales - LAG(sales) OVER (ORDER BY MONTHS)) / LAG(sales) OVER (ORDER BY MONTHS) * 100, 2) AS `环比增长率(%)`
FROM (
    SELECT MONTHS, SUM(ORDERED_PRODUCTSALES) AS sales
    FROM ids.IDS_AMZ_COMPREHENSIVE_DI
    WHERE FDATE >= '2026-03-01' AND FDATE <= '2026-04-30'
    GROUP BY MONTHS
) t
ORDER BY MONTHS""",
        metric_code="MKI-02-0001",
        intent_type="compare",
    ),

    # 场景10：比例/占比计算（两个指标相除）
    SQLExample(
        question="各店铺退款率是多少？",
        sql="SELECT FSITE, ROUND(SUM(fqty_tk) / SUM(ORDER_QTY) * 100, 2) AS `退款率(%)` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-04-01' AND FDATE <= '2026-04-30' GROUP BY FSITE",
        metric_code=None,
        dimension="FSITE",
        intent_type="query_value",
    ),
    SQLExample(
        question="各平台退款数量占销量的比例？",
        sql="SELECT PLATFORM, ROUND(SUM(fqty_tk) / SUM(ORDER_QTY) * 100, 2) AS `退款占比(%)` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-04-01' AND FDATE <= '2026-04-30' GROUP BY PLATFORM",
        metric_code=None,
        dimension="PLATFORM",
        intent_type="query_value",
    ),
    SQLExample(
        question="各品类退款金额占销售额的比例？",
        sql="SELECT GROUP_1, ROUND(SUM(fqty_tk) / SUM(ORDERED_PRODUCTSALES) * 100, 2) AS `退款金额占比(%)` FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE FDATE >= '2026-04-01' AND FDATE <= '2026-04-30' GROUP BY GROUP_1",
        metric_code=None,
        dimension="GROUP_1",
        intent_type="query_value",
    ),
]


class SQLExampleRetriever:
    """
    SQL 示例检索器

    检索策略：
    1. 精确匹配：同指标 + 同维度 → 直接返回
    2. 模糊匹配：同指标 + 不同维度 → 返回该指标的多种维度组合
    3. 冷启动：使用预置种子 SQL
    4. 语义匹配：从 sql_audit_logs 检索相似问题（后续实现）
    """

    def __init__(self):
        self._seed_examples = SEED_SQL_EXAMPLES

    def retrieve(
        self,
        question: str,
        metric_code: Optional[str] = None,
        dimension: Optional[str] = None,
        intent_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[SQLExample]:
        """
        检索最相关的 SQL 示例

        Args:
            question: 用户问题
            metric_code: 指标代码（可选）
            dimension: 维度（可选）
            intent_type: 意图类型（可选）
            top_k: 返回数量

        Returns:
            相关的 SQL 示例列表
        """
        results: List[SQLExample] = []

        # 1. 精确匹配：同指标 + 同维度
        if metric_code and dimension:
            exact_matches = [
                ex for ex in self._seed_examples
                if ex.metric_code == metric_code and ex.dimension == dimension
            ]
            if exact_matches:
                results.extend(exact_matches[:top_k])
                return results[:top_k]

        # 2. 模糊匹配：同指标
        if metric_code:
            metric_matches = [
                ex for ex in self._seed_examples
                if ex.metric_code == metric_code
            ]
            # 按维度多样性排序
            seen_dimensions = set()
            for ex in metric_matches:
                dim_key = ex.dimension or "none"
                if dim_key not in seen_dimensions:
                    seen_dimensions.add(dim_key)
                    results.append(ex)
            if results:
                return results[:top_k]

        # 3. 意图类型匹配
        if intent_type:
            intent_matches = [
                ex for ex in self._seed_examples
                if ex.intent_type == intent_type
            ]
            for ex in intent_matches:
                if ex not in results:
                    results.append(ex)
            if results:
                return results[:top_k]

        # 4. 冷启动兜底：返回预置种子 SQL
        if not results:
            logger.info("[SQLExampleRetriever] 无匹配，返回预置种子 SQL")
            results = self._seed_examples[:top_k]

        return results[:top_k]

    def get_seed_examples(self) -> List[SQLExample]:
        """获取所有预置种子 SQL"""
        return self._seed_examples

    def format_examples_for_prompt(self, examples: List[SQLExample]) -> str:
        """
        将 SQL 示例格式化为 Prompt 文本

        Returns:
            格式化的示例文本
        """
        if not examples:
            return "（暂无 SQL 示例）"

        lines = []
        for i, ex in enumerate(examples, 1):
            lines.append(f"### 示例{i}")
            lines.append(f"Q: {ex.question}")
            lines.append(f"SQL: {ex.sql}")
            lines.append("")

        return "\n".join(lines)


# 全局实例
_sql_example_retriever: Optional[SQLExampleRetriever] = None


def get_sql_example_retriever() -> SQLExampleRetriever:
    """获取 SQL 示例检索器单例"""
    global _sql_example_retriever
    if _sql_example_retriever is None:
        _sql_example_retriever = SQLExampleRetriever()
    return _sql_example_retriever
