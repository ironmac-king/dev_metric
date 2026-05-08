"""片段组装器 - 生成完整 SQL"""
from typing import List, Dict, Any, Optional
from .fragments.base import SQLFragment


class FragmentComposer:
    """片段组装器 - 生成完整 SQL"""

    def __init__(self):
        self.fragments: List[SQLFragment] = []

    def add(self, fragment: SQLFragment) -> "FragmentComposer":
        """添加片段，支持链式调用"""
        self.fragments.append(fragment)
        return self

    def render(self, context: Dict[str, Any]) -> str:
        """渲染所有片段为完整 SQL"""
        table = context.get("table", "metric_table")
        metric_code = context.get("metric_code", "")

        # 收集各部分
        select_parts = []
        where_parts = []
        group_by_parts = []
        window_parts = []
        order_by_parts = []

        for f in self.fragments:
            rendered = f.render(context)
            if not rendered:
                continue

            # 根据片段类型分类收集
            fragment_type = type(f).__name__
            if fragment_type == "MeasureFragment":
                select_parts.append(rendered)
            elif fragment_type == "WhereFragment":
                where_parts.append(rendered)
            elif fragment_type == "GroupByFragment":
                group_by_parts.append(rendered)
            elif fragment_type == "WindowFragment":
                window_parts.append(rendered)
            else:
                # 其他片段默认加入 SELECT
                select_parts.append(rendered)

        # 构建完整 SQL
        sql_parts = []

        # SELECT 子句
        all_select_parts = select_parts[:]
        # Window 片段的输出作为 SELECT 列
        if window_parts:
            all_select_parts.extend(window_parts)

        if all_select_parts:
            sql_parts.append(f"SELECT {', '.join(all_select_parts)}")
        else:
            sql_parts.append("SELECT *")

        # FROM 子句
        sql_parts.append(f"FROM {table}")

        # WHERE 子句
        if where_parts:
            sql_parts.append(f"WHERE {' AND '.join(where_parts)}")

        # GROUP BY 子句
        if group_by_parts:
            sql_parts.append(f"GROUP BY {', '.join(group_by_parts)}")

        # ORDER BY 子句
        if order_by_parts:
            sql_parts.append(f"ORDER BY {', '.join(order_by_parts)}")

        return "\n".join(sql_parts)

    def clear(self) -> "FragmentComposer":
        """清空所有片段"""
        self.fragments = []
        return self
