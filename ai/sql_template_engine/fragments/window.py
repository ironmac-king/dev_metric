"""Window 片段 - 窗口函数"""
from typing import Dict, Any, List
from .base import SQLFragment


class WindowFragment(SQLFragment):
    """窗口函数片段"""

    def __init__(self, window_type: str):
        self.window_type = window_type  # "LAG", "RANK", "YoY"

    def render(self, context: Dict[str, Any]) -> str:
        # field: 含 alias（用于 SELECT 列表），raw_field: 不含 alias（用于窗口函数计算）
        # alias: 字段别名（如 SPEND），用于 YoY 自连接场景的列访问
        field = context.get("field", "*")
        raw_field = context.get("raw_field", field)
        alias = context.get("alias", "metric_value")
        date_col = context.get("date_column", "FDATE")

        if self.window_type == "LAG":
            # 只输出分析列，不输出 metric_value（由 MeasureFragment 输出）
            return f"""LAG({raw_field}, 1) OVER (ORDER BY {date_col}) AS prev_value,
    {raw_field} - LAG({raw_field}, 1) OVER (ORDER BY {date_col}) AS diff,
    ROUND(({raw_field} - LAG({raw_field}, 1) OVER (ORDER BY {date_col})) / NULLIF(LAG({raw_field}, 1) OVER (ORDER BY {date_col}), 0) * 100, 2) AS mom_rate"""

        elif self.window_type == "RANK":
            return f"""RANK() OVER (ORDER BY {raw_field} DESC) AS rank_num,
    ROUND({raw_field} / SUM({raw_field}) OVER () * 100, 2) AS pct_of_total"""

        elif self.window_type == "YoY":
            # YoY 自连接需要用 alias 列名访问（因为是表的自连接，列名就是 alias）
            return f"""t1.{date_col} AS date,
    t1.{alias} AS current_value,
    t2.{alias} AS last_year_value,
    t1.{alias} - t2.{alias} AS diff_value,
    ROUND((t1.{alias} - t2.{alias}) / NULLIF(t2.{alias}, 0) * 100, 2) AS yoy_rate"""

        return ""

    def required_context(self) -> List[str]:
        return ["field", "raw_field", "alias", "date_column"]
