"""GroupBy 片段 - 分组"""
from typing import Dict, Any, List, Optional
from .base import SQLFragment


class GroupByFragment(SQLFragment):
    """分组片段 - 有 dimension 用 dimension，无则用 date_column"""

    def render(self, context: Dict[str, Any]) -> str:
        dimension = context.get("dimension")
        # 时间维度词（日/月/年）不是真正的分组维度，应该用 date_column
        time_words = {"日", "月", "年", "天", "周", "day", "month", "year", "week"}
        if dimension and dimension.lower() not in time_words:
            return dimension
        # 无有效 dimension 时默认按日期分组
        date_col = context.get("date_column", "FDATE")
        return date_col

    def required_context(self) -> List[str]:
        return ["date_column"]
