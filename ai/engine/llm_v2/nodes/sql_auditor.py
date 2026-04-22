"""
步骤 7: SQL 安全审计

职责：
- 检查 SQL 是否有危险操作
- 防止 SQL 注入
"""
import re
from typing import Tuple
from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.sql_auditor")


class SQLSecurityAuditor:
    """
    SQL 安全审计器

    检查 SQL 是否有危险操作。
    """

    # 危险关键词
    DANGEROUS_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
        "--", "/*", "*/", ";--",
    ]

    # 允许的表名（白名单）
    ALLOWED_TABLES = [
        "ids.IDS_AMZ_COMPREHENSIVE_DI",
        "dws.DWS_IMC_BUSINESSREPORT",
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

        # 4. 检查表名（如果有）
        table_match = re.search(r'FROM\s+([^\s;]+)', sql, re.IGNORECASE)
        if table_match:
            table_name = table_match.group(1).strip()
            # 暂时不限制表名，因为可能有动态表名
            # if table_name not in self.ALLOWED_TABLES:
            #     return False, f"不允许查询表: {table_name}"

        # 5. 检查是否有多余的分号
        if ";" in sql.replace("';'", ""):
            logger.warning(f"[SQLSecurityAuditor] 检测到多余分号: {sql}")

        return True, ""
