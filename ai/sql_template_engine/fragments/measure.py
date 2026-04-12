"""Measure 片段 - 从 starrocks_sql 解析 field 和 table"""
from typing import Dict, Any, List
from .base import SQLFragment


class MeasureFragment(SQLFragment):
    """Measure 片段，从 starrocks_sql 解析"""

    def render(self, context: Dict[str, Any]) -> str:
        """渲染 SELECT 字段部分"""
        return context.get("field", "*")

    def get_table(self, context: Dict[str, Any]) -> str:
        """获取表名"""
        return context.get("table", "metric_table")

    def required_context(self) -> List[str]:
        return ["field", "table"]