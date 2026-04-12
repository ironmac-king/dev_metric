"""
SQL 模板引擎主入口 - 片段组合模式
意图识别 → 片段组装 → SQL 生成
"""

from typing import Any, Dict, Optional

from .composer import FragmentComposer
from .intent_config import get_composer_for_intent


class SQLTemplateEngine:
    """SQL 模板引擎（片段组合模式）"""

    def __init__(self):
        pass

    def generate_sql(self, intent: str, entities: Dict[str, Any], drill_dims: list = None) -> Optional[str]:
        """生成 SQL"""
        # 构建 context
        context = self._build_context(entities, drill_dims)

        # 获取意图对应的 Composer
        composer = get_composer_for_intent(intent)
        if composer is None:
            return None

        # 渲染 SQL
        return composer.render(context)

    def _build_context(self, entities: Dict[str, Any], drill_dims: list = None) -> Dict[str, Any]:
        """构建渲染上下文"""
        starrocks_sql = entities.get("starrocks_sql", "")

        # 从 starrocks_sql 解析 field, raw_field, alias 和 table
        field, raw_field, alias = self._parse_field(starrocks_sql)
        table = self._parse_table(starrocks_sql)

        # 获取时间信息
        time_info = entities.get("time_info", {})
        start_date = time_info.get("start_date", "2026-01-01")
        end_date = time_info.get("end_date", "2026-04-12")

        # 获取日期列
        date_column = entities.get("date_column", "FDATE")

        # 获取维度
        dimension = entities.get("dimension")
        if drill_dims and len(drill_dims) > 0:
            dimension = drill_dims[0]

        context = {
            "field": field,          # 完整字段表达式（含 alias），用于 SELECT
            "raw_field": raw_field,  # 原始聚合表达式（不含 alias），用于窗口函数
            "alias": alias,          # 字段别名（如 SPEND），用于 YoY 自连接列访问
            "table": table,
            "start_date": start_date,
            "end_date": end_date,
            "date_column": date_column,
            "dimension": dimension,
            "top_n": entities.get("top_n", "10"),
        }

        return context

    def _parse_field(self, starrocks_sql: str) -> tuple:
        """从 starrocks_sql 解析字段，返回 (field, raw_field, alias)"""
        import re
        if not starrocks_sql:
            return "*", "*", "metric_value"
        match = re.search(r'SELECT\s+(.+?)\s+FROM\s+', starrocks_sql, re.IGNORECASE | re.DOTALL)
        if match:
            field = match.group(1).strip()
            # 提取 alias（如 "SUM(SPEND) AS SPEND" -> alias="SPEND"）
            alias_match = re.search(r'\s+AS\s+(\w+)\s*$', field, re.IGNORECASE)
            if alias_match:
                alias = alias_match.group(1)
                # 提取原始字段表达式（去掉 AS alias 部分）
                raw_field = re.sub(r'\s+AS\s+\w+\s*$', '', field, flags=re.IGNORECASE).strip()
            else:
                alias = "metric_value"
                raw_field = field
            return field, raw_field, alias
        return "*", "*", "metric_value"

    def _parse_table(self, starrocks_sql: str) -> str:
        """从 starrocks_sql 解析表名"""
        import re
        if not starrocks_sql:
            return "metric_table"
        match = re.search(r'FROM\s+([^\s;]+)', starrocks_sql, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "metric_table"


# 全局单例
_engine: Optional[SQLTemplateEngine] = None


def get_engine() -> SQLTemplateEngine:
    global _engine
    if _engine is None:
        _engine = SQLTemplateEngine()
    return _engine


def generate_sql(intent: str, entities: Dict[str, Any], drill_dims: list = None) -> Optional[str]:
    """便捷函数"""
    return get_engine().generate_sql(intent, entities, drill_dims)
