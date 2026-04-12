"""Where 片段 - 时间过滤"""
from typing import Dict, Any, List
from .base import SQLFragment


class WhereFragment(SQLFragment):
    """时间过滤片段"""

    def render(self, context: Dict[str, Any]) -> str:
        date_col = context.get("date_column", "FDATE")
        start = context.get("start_date", "2026-01-01")
        end = context.get("end_date", "2026-04-12")
        return f"{date_col} BETWEEN '{start}' AND '{end}'"

    def required_context(self) -> List[str]:
        return ["date_column", "start_date", "end_date"]
