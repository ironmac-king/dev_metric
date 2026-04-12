"""Window 片段 - 窗口函数"""
from typing import Dict, Any, List
from .base import SQLFragment


class WindowFragment(SQLFragment):
    """窗口函数片段"""

    def __init__(self, window_type: str):
        self.window_type = window_type  # "LAG", "RANK", "YoY"

    def render(self, context: Dict[str, Any]) -> str:
        field = context.get("field", "*")
        date_col = context.get("date_column", "FDATE")

        if self.window_type == "LAG":
            return f"""{field} AS metric_value,
    LAG({field}, 1) OVER (ORDER BY {date_col}) AS prev_value,
    {field} - LAG({field}, 1) OVER (ORDER BY {date_col}) AS diff,
    ROUND(({field} - LAG({field}, 1) OVER (ORDER BY {date_col})) / NULLIF(LAG({field}, 1) OVER (ORDER BY {date_col}), 0) * 100, 2) AS mom_rate"""

        elif self.window_type == "RANK":
            return f"""{field} AS metric_value,
    RANK() OVER (ORDER BY {field} DESC) AS rank_num,
    ROUND({field} / SUM({field}) OVER () * 100, 2) AS pct_of_total"""

        elif self.window_type == "YoY":
            return f"""t1.{date_col} AS date,
    t1.{field} AS current_value,
    t2.{field} AS last_year_value,
    t1.{field} - t2.{field} AS diff_value,
    ROUND((t1.{field} - t2.{field}) / NULLIF(t2.{field}, 0) * 100, 2) AS yoy_rate"""

        return ""

    def required_context(self) -> List[str]:
        return ["field", "date_column"]
