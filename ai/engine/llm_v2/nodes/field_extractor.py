"""
字段提取器 - 统一解析 starrocks_sql

职责：
- 从 starrocks_sql 提取字段/表达式/别名
- 统一散落在各处的重复字段提取逻辑
"""
import re
from dataclasses import dataclass
from typing import Optional

logger = None  # 延迟初始化避免循环导入


def _get_logger():
    global logger
    if logger is None:
        from ai.config.logging_config import get_logger
        logger = get_logger("ai.llm_v2.field_extractor")
    return logger


@dataclass
class ParsedField:
    """解析结果容器"""
    expression: str      # 完整表达式（可直接用于 SELECT）
    alias: str          # SQL 别名
    bare_field: str     # 裸字段（不含聚合，用于 CASE WHEN）
    aggregation: str     # 聚合函数名（SUM/AVG/COUNT/MAX/MIN）
    is_compound: bool   # 是否为复合指标


class FieldExtractor:
    """
    统一字段解析器

    设计原则：
    1. 一次性解析 starrocks_sql，所有信息并行提取
    2. 不重复解析同一个 starrocks_sql
    3. 统一处理简单/复合指标的区分逻辑
    """

    # 预编译正则
    AGG_PATTERN = re.compile(r'(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)', re.IGNORECASE)
    # 支持反引号、单引号、双引号包裹的别名
    ALIAS_PATTERN = re.compile(r'AS\s+[`\'\"\[\]]?([\w\u4e00-\u9fff]+)[`\'\"\"\]]?', re.IGNORECASE)
    FROM_PATTERN = re.compile(r'\s+FROM\s+', re.IGNORECASE | re.DOTALL)
    COMPOUND_KEYWORDS = ["IFNULL", "ISNULL", "COALESCE", "/", "*", "-"]

    def __init__(self, metric):
        """
        Args:
            metric: MQLMetric 对象
        """
        self.metric = metric
        self._starrocks_sql = getattr(metric, 'starrocks_sql', None) or ""
        self._default_field = getattr(metric, 'field', None) or "ORDERED_PRODUCTSALES"
        self._aggregation = getattr(metric, 'aggregation', None) or "SUM"
        if hasattr(self._aggregation, 'value'):
            self._aggregation = self._aggregation.value

    @property
    def starrocks_sql(self) -> str:
        return self._starrocks_sql

    def parse(self) -> ParsedField:
        """
        执行完整解析，返回 ParsedField

        Returns:
            ParsedField: 包含 expression, alias, bare_field, aggregation, is_compound
        """
        sql = self._starrocks_sql.strip()

        if not sql:
            return self._default_parsed()

        is_compound = self._is_compound(sql)
        sql_upper = sql.upper()

        # 情况1：SELECT ... FROM ... 完整格式
        if sql_upper.startswith('SELECT'):
            expr, alias = self._extract_from_select_sql(sql, sql_upper)
        # 情况2：裸聚合或字段名
        else:
            expr, alias = self._extract_from_bare_sql(sql, sql_upper)

        # 提取裸字段（不含聚合）
        bare_field = self._extract_bare_field(expr, sql_upper)

        # 提取聚合函数类型
        aggregation = self._detect_aggregation(expr)

        return ParsedField(
            expression=expr,
            alias=alias,
            bare_field=bare_field,
            aggregation=aggregation,
            is_compound=is_compound
        )

    def extract_raw(self) -> str:
        """
        提取裸字段（不含聚合），用于 CASE WHEN

        Returns:
            str: 裸字段表达式，如 "PAGEVIEWS_TOTAL" 或 "IFNULL(a,0)-IFNULL(b,0)"
        """
        return self.parse().bare_field

    def extract_full(self) -> tuple:
        """
        提取完整表达式和别名，用于 SELECT 子句

        Returns:
            tuple: (expression: str, alias: str)
        """
        parsed = self.parse()
        return parsed.expression, parsed.alias

    def extract_alias(self) -> str:
        """
        只提取别名

        Returns:
            str: SQL 别名
        """
        return self.parse().alias

    def _is_compound(self, sql: str) -> bool:
        """判断是否复合指标"""
        sql_upper = sql.upper()
        return any(kw in sql_upper for kw in self.COMPOUND_KEYWORDS)

    def _extract_from_select_sql(self, sql: str, sql_upper: str) -> tuple:
        """
        从 SELECT expr AS alias FROM ... 提取表达式和别名

        处理嵌套 FROM（如 IFNULL 函数内的 FROM 字段名）
        策略：用正则的 FROM_PATTERN 分割，取最后一个 part 前面所有内容
        """
        parts = self.FROM_PATTERN.split(sql)
        if len(parts) >= 2:
            select_and_alias = ' FROM '.join(parts[:-1])
        else:
            select_and_alias = sql

        # 提取 AS 别名
        alias_match = self.ALIAS_PATTERN.search(select_and_alias)
        alias = alias_match.group(1) if alias_match else self._default_field

        # 提取表达式（去掉 AS alias 部分）
        if alias_match:
            expr = select_and_alias[:alias_match.start()].strip()
        else:
            expr = select_and_alias

        # 去掉开头的 SELECT
        if expr.upper().startswith('SELECT'):
            expr = expr[6:].strip()

        # 如果是复合指标，保留完整表达式；否则返回聚合函数形式
        if not self._is_compound(sql):
            # 简单指标：尝试提取聚合函数内的字段
            agg_match = self.AGG_PATTERN.search(expr)
            if agg_match:
                agg, field = agg_match.groups()
                expr = f"{agg}({field})"

        return expr, alias

    def _extract_from_bare_sql(self, sql: str, sql_upper: str) -> tuple:
        """
        从裸聚合或字段名提取

        Args:
            sql: 原始 SQL 字符串
            sql_upper: 大写版本的 SQL
        """
        agg_match = self.AGG_PATTERN.search(sql)
        if agg_match:
            agg, field = agg_match.groups()
            expr = agg_match.group(0)  # e.g., "SUM(REFUND_QTY)"
            alias = field
            return expr, alias

        # 裸字段名，直接返回 SUM 包装
        expr = f"SUM({sql})"
        alias = sql
        return expr, alias

    def _extract_bare_field(self, expr: str, sql_upper: str) -> str:
        """
        从表达式提取裸字段（不含聚合）

        用于 CASE WHEN 条件聚合，因为外层 SUM 会做聚合。
        """
        # 如果是复合指标，返回完整表达式（不含外层 SUM）
        if self._is_compound(sql_upper if 'sql_upper' in locals() else self._starrocks_sql.upper()):
            return expr

        # 简单指标：提取聚合函数内的字段
        agg_match = self.AGG_PATTERN.search(expr)
        if agg_match:
            return agg_match.group(2)

        # 回退：返回原始表达式（去除非字母数字下划线）
        return re.sub(r'[^\w]', '', expr).strip('_') or self._default_field

    def _detect_aggregation(self, expr: str) -> str:
        """检测聚合函数类型"""
        agg_match = self.AGG_PATTERN.search(expr)
        if agg_match:
            return agg_match.group(1).upper()
        return self._aggregation or "SUM"

    def _default_parsed(self) -> ParsedField:
        """无 starrocks_sql 时的默认值"""
        field = self._default_field
        expr = f"{self._aggregation}({field})"
        return ParsedField(
            expression=expr,
            alias=field,
            bare_field=field,
            aggregation=self._aggregation,
            is_compound=False
        )

    @staticmethod
    def extract_molecule(starrocks_sql: str, default_field: str = "REFUND_QTY") -> str:
        """
        从占比 SQL 提取分子表达式

        例如：
        - "SELECT SUM(a)/SUM(b) AS RATIO FROM ..." → "SUM(a)"
        - "SELECT SUM(IFNULL(x,0))/SUM(IFNULL(y,0)) AS RATIO FROM ..." → "SUM(IFNULL(x,0))"
        """
        if not starrocks_sql:
            return default_field

        sql = starrocks_sql.strip()
        sql_upper = sql.upper()

        # 复合占比 SQL：提取 / 前面的表达式
        if '/' in sql_upper:
            # M6 fix: 扩展正则支持嵌套括号和更多聚合函数（COUNT_DISTINCT等）
            # 使用 \(.*?\) 非贪婪匹配来支持嵌套括号
            match = re.search(
                r'(?:^|[+\-*\s])(\(?\s*(?:SUM|AVG|COUNT|MAX|MIN|COUNT_DISTINCT)\s*\(.*?\))(?:\s*/|$)',
                sql_upper, re.IGNORECASE | re.DOTALL
            )
            if match:
                return match.group(1)

        # 非占比形式：回退到普通字段提取
        extractor = FieldExtractor.__new__(FieldExtractor)
        extractor._starrocks_sql = starrocks_sql
        extractor._default_field = default_field
        extractor._aggregation = "SUM"
        return extractor.extract_raw()

    @staticmethod
    def extract_denominator(starrocks_sql: str, default_field: str = "ORDERED_PRODUCTSALES") -> str:
        """
        从占比 SQL 提取分母表达式

        例如：
        - "SELECT SUM(a)/SUM(b) AS RATIO FROM ..." → "SUM(b)"
        """
        if not starrocks_sql:
            return default_field

        sql = starrocks_sql.strip()
        sql_upper = sql.upper()

        # 复合占比 SQL：提取 / 后面的表达式
        if '/' in sql_upper:
            # M6 fix: 扩展正则支持嵌套括号和更多聚合函数（COUNT_DISTINCT等）
            match = re.search(
                r'/\s*(\(?\s*(?:SUM|AVG|COUNT|MAX|MIN|COUNT_DISTINCT)\s*\(.*?\))',
                sql_upper, re.IGNORECASE | re.DOTALL
            )
            if match:
                return match.group(1)

        # 非占比形式：回退到普通字段提取
        extractor = FieldExtractor.__new__(FieldExtractor)
        extractor._starrocks_sql = starrocks_sql
        extractor._default_field = default_field
        extractor._aggregation = "SUM"
        return extractor.extract_raw()
