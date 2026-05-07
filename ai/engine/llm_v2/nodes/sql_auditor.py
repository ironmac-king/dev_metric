"""
步骤 7: SQL 安全审计

职责：
- 检查 SQL 是否有危险操作
- 防止 SQL 注入
- 表名/字段名白名单校验
"""
import re
from typing import Tuple, Set
from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.sql_auditor")

# SQL 关键字（用于字段提取时排除）
SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "NOT", "IN",
    "GROUP", "BY", "ORDER", "ASC", "DESC", "HAVING", "LIMIT", "OFFSET",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "ON", "AS",
    "WITH", "CTE", "CASE", "WHEN", "THEN", "ELSE", "END",
    "SUM", "AVG", "COUNT", "MAX", "MIN", "NULLIF", "IFNULL", "COALESCE",
    "CAST", "ABS", "ROUND", "LAG", "LEAD", "OVER", "PARTITION", "ROWS",
    "BETWEEN", "UNBOUNDED", "PRECEDING", "FOLLOWING", "RANK", "ROW_NUMBER",
    "DISTINCT", "ALL", "TRUE", "FALSE", "NULL", "IS", "LIKE",
    "UNION", "EXCEPT", "INTERSECT", "EXISTS",
    "DATE_TRUNC", "DATE_ADD", "LAST_DAY", "INTERVAL", "MONTH", "DAY", "YEAR",
    "IF", "DOUBLE", "INT", "FLOAT", "STRING",
}


class SQLSecurityAuditor:
    """
    SQL 安全审计器

    检查 SQL 是否有危险操作，校验表名和字段名白名单。
    """

    # 危险关键词
    DANGEROUS_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
        ";--",
    ]

    # 允许的表名（白名单）
    ALLOWED_TABLES = [
        "IDS_AMZ_COMPREHENSIVE_DI",
        "DWS_IMC_BUSINESSREPORT",
    ]

    def audit(self, sql: str) -> Tuple[bool, str]:
        """
        审计 SQL

        Args:
            sql: SQL 语句

        Returns:
            (is_safe, error_message)
        """
        if not sql:
            return False, "SQL 为空"

        sql_upper = sql.upper()

        # 1. 检查危险关键词
        for keyword in self.DANGEROUS_KEYWORDS:
            if keyword in sql_upper:
                return False, f"禁止的关键词: {keyword}"

        # 2. 检查是否包含注释
        if "--" in sql or "/*" in sql:
            return False, "禁止的注释风格"

        # 3. 检查是否以 SELECT 或 WITH (CTE) 开头
        stripped = sql_upper.strip()
        if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
            return False, "只允许 SELECT 查询"

        # 4. 检查是否有多余的分号
        if ";" in sql.replace("';'", ""):
            logger.warning(f"[SQLSecurityAuditor] 检测到多余分号: {sql}")

        # 5. 表名白名单校验（排除 CTE 名）
        cte_names = set(re.findall(r'\b(\w+)\s+AS\s*\(', sql, re.IGNORECASE))
        table_matches = re.findall(r'\bFROM\s+([a-zA-Z_][\w.]*(?:\.[a-zA-Z_][\w.]*)?)', sql, re.IGNORECASE)
        table_matches += re.findall(r'\bJOIN\s+([a-zA-Z_][\w.]*(?:\.[a-zA-Z_][\w.]*)?)', sql, re.IGNORECASE)
        allowed_tables_upper = {t.upper() for t in self.ALLOWED_TABLES}
        for t in table_matches:
            t_name = t.split(".")[-1]
            # 跳过 CTE 名
            if t_name.upper() in {c.upper() for c in cte_names}:
                continue
            if t_name.upper() not in allowed_tables_upper:
                return False, f"不允许查询表: {t}"

        # 6. 字段名校验：模式检查（防注入）+ 未知字段告警
        allowed_fields = self._get_allowed_fields()
        fields_in_sql = self._extract_fields(sql)
        for f in fields_in_sql:
            # 6a. 模式检查：字段名必须是合法标识符
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', f):
                return False, f"非法字段名格式: {f}"
            # 6b. 如果白名单非空，对未知字段告警（不阻断，避免误杀）
            if allowed_fields and f.upper() not in allowed_fields:
                logger.warning(f"[SQLSecurityAuditor] 未知字段(仅告警): {f}")

        return True, ""

    def _get_allowed_fields(self) -> Set[str]:
        """从语义快照 + 维度映射获取允许的字段集合"""
        fields = set()

        # 从语义快照获取指标字段
        try:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            snap = get_semantic_snapshot_service()
            snapshot = snap.get_active_snapshot()
            if snapshot:
                payload = snapshot.get("payload", snapshot)
                metrics = payload.get("metrics", {})
                for metric_data in metrics.values():
                    if isinstance(metric_data, dict):
                        if metric_data.get("starrocks_field"):
                            fields.add(metric_data["starrocks_field"].upper())
                        # 从 starrocks_sql 中提取所有字段
                        if metric_data.get("starrocks_sql"):
                            sql_fields = self._extract_fields(metric_data["starrocks_sql"])
                            for sf in sql_fields:
                                fields.add(sf.upper())
        except Exception as e:
            logger.warning(f"[SQLSecurityAuditor] 加载快照字段失败: {e}")

        # 从维度映射获取字段
        try:
            from .sql_generator import SQLGeneratorNode
            for col in SQLGeneratorNode.DIMENSION_COLUMN_MAP.values():
                fields.add(col.upper())
        except Exception:
            pass

        # 时间列
        fields.update({"FDATE", "MONTHS", "YEARS", "WEEKS", "QUARTERS"})

        # CTE 别名列（calc_layer 输出的列）
        fields.update({"BASE"})

        return fields

    def _extract_fields(self, sql: str) -> list:
        """提取 SQL 中的字段名（排除 SQL 关键字、别名和纯数字）

        策略：
        1. 提取 FROM/JOIN 后的表名（已单独处理）
        2. 提取 WHERE/GROUP BY/ORDER BY/HAVING 中的字段名
        3. 提取聚合函数内的字段名（如 SUM(field)）
        4. 排除 AS 后面的别名
        """
        fields = set()

        # 1. 提取 WHERE/GROUP BY/ORDER BY/HAVING 中的字段
        # WHERE field = 'xxx' 或 GROUP BY field 或 ORDER BY field
        for clause in ["WHERE", "GROUP BY", "ORDER BY", "HAVING"]:
            pattern = rf'\b{clause}\s+([^;]+)'
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                # 提取标识符
                tokens = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', match)
                for t in tokens:
                    if t.upper() not in SQL_KEYWORDS:
                        fields.add(t.upper())

        # 2. 提取聚合函数内的字段名: SUM(field), COUNT(field), etc.
        agg_pattern = r'\b(?:SUM|AVG|COUNT|MAX|MIN|LAG|LEAD)\s*\(\s*(?:DISTINCT\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\)'
        agg_matches = re.findall(agg_pattern, sql, re.IGNORECASE)
        for m in agg_matches:
            if m.upper() not in SQL_KEYWORDS:
                fields.add(m.upper())

        # 3. 提取 CASE WHEN 中的字段: CASE WHEN field > 0 THEN ...
        case_pattern = r'\bCASE\s+WHEN\s+([A-Za-z_][A-Za-z0-9_]*)\s*[>=<]'
        case_matches = re.findall(case_pattern, sql, re.IGNORECASE)
        for m in case_matches:
            if m.upper() not in SQL_KEYWORDS:
                fields.add(m.upper())

        # 4. 排除 AS 后面的别名
        # SELECT ... AS alias -> alias 不应被校验
        as_pattern = r'\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\b'
        aliases = set(re.findall(as_pattern, sql, re.IGNORECASE))
        aliases_upper = {a.upper() for a in aliases}
        fields = fields - aliases_upper

        return list(fields)
