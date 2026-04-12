"""GroupBy 片段 - 分组"""
from typing import Dict, Any, List, Optional
from .base import SQLFragment


class GroupByFragment(SQLFragment):
    """分组片段 - 有 dimension 用 dimension，无则用 date_column"""

    def render(self, context: Dict[str, Any]) -> str:
        dimension = context.get("dimension")
        if dimension:
            return f"GROUP BY {dimension}"
        # 无 dimension 时默认按日期分组
        date_col = context.get("date_column", "FDATE")
        return f"GROUP BY {date_col}"

    def required_context(self) -> List[str]:
        return ["date_column"]
