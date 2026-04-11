"""
SQL 构建模块 - SQL 模板处理、维度注入
"""
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("ai.nodes")


class SQLBuilder:
    """SQL 构建器"""

    def __init__(self, metric_client=None, dimension_resolver=None):
        self.metric_client = metric_client
        self.dimension_resolver = dimension_resolver

    def apply_dimensions_to_sql(
        self,
        starrocks_sql: str,
        dimensions: Dict[str, Any],
        entities: Dict[str, Any],
        time_info: Optional[Dict]
    ) -> str:
        """
        将维度参数应用到 SQL 模板

        处理：
        1. 时间范围条件
        2. 动态 GROUP BY
        3. 其他维度参数
        4. top N 排名
        """
        adjusted_sql = starrocks_sql
        table_name = self.extract_table_name(starrocks_sql)

        if not time_info and entities.get("time_range"):
            from ai.engine.time_parser import TimeParser
            tp = TimeParser()
            time_info = tp.parse(entities.get("time_range"))

        # 时间范围处理
        if time_info and table_name:
            start_date = time_info.get("start_date")
            end_date = time_info.get("end_date")
            time_type = time_info.get("type", "date_range")

            # 从 dim_configs 获取列名
            dim_configs = {}
            if self.dimension_resolver:
                dim_configs = self.dimension_resolver.get_table_dimensions_cached(table_name)

            if time_type in ("date_range", "relative"):
                col = dim_configs.get("日", {}).get("column_name", "FDATE")
                if start_date and end_date:
                    time_cond = f"{col} >= '{start_date}' AND {col} <= '{end_date}'"
                    if "WHERE" in adjusted_sql.upper():
                        adjusted_sql = adjusted_sql + " AND " + time_cond
                    else:
                        adjusted_sql = adjusted_sql + " WHERE " + time_cond
            elif time_type in ("absolute_month", "quarter"):
                col = dim_configs.get("月", {}).get("column_name", "MONTHS")
                if start_date:
                    time_cond = f"{col} = '{start_date[:7]}'"
                    if "WHERE" in adjusted_sql.upper():
                        adjusted_sql = adjusted_sql + " AND " + time_cond
                    else:
                        adjusted_sql = adjusted_sql + " WHERE " + time_cond

        # GROUP BY 维度处理
        dimension = entities.get("dimension")  # 如 "二级品类"
        if dimension and table_name:
            dim_configs = self.dimension_resolver.get_table_dimensions_cached(table_name) if self.dimension_resolver else {}

            # 解析维度 → 列名
            if dimension in dim_configs:
                column = dim_configs[dimension].get("column_name", dimension)
            else:
                # 模糊匹配选最长
                candidates = [d for d in dim_configs if dimension in d or d in dimension]
                if candidates:
                    matched = max(candidates, key=len)
                    column = dim_configs[matched].get("column_name", matched)
                else:
                    column = dimension

            adjusted_sql = adjusted_sql.replace("{dimension}", column)

            if dimension and "GROUP BY" not in adjusted_sql.upper():
                adjusted_sql = adjusted_sql.rstrip() + f" GROUP BY {column}"
        else:
            adjusted_sql = adjusted_sql.replace("{dimension}", "*")

        # 其他维度参数
        if table_name:
            dim_configs = self.dimension_resolver.get_table_dimensions_cached(table_name) if self.dimension_resolver else {}
        else:
            dim_configs = {}

        for dim_key, dim_value in dimensions.items():
            if dim_key in ["日", "月", "年", "天", "周"]:
                continue
            if dim_key == "dimension":
                continue
            if not dim_value or dim_value in ("all", "__SYNONYM__"):
                continue

            if dim_key in dim_configs:
                column = dim_configs[dim_key].get("column_name", dim_key)
            else:
                column = dim_key

            if "WHERE" in adjusted_sql.upper():
                adjusted_sql = adjusted_sql + f" AND {column} = '{dim_value}'"
            else:
                adjusted_sql = adjusted_sql + f" WHERE {column} = '{dim_value}'"

        # top N 处理
        from ai.engine.time_parser import TimeParser
        tp = TimeParser()
        top_n = tp.extract_top_n(entities.get("time_range", ""))
        if not top_n:
            top_n = tp.extract_top_n(str(entities))

        if top_n and "ORDER BY" not in adjusted_sql.upper() and "LIMIT" not in adjusted_sql.upper():
            # 找 metric 列
            metric_col = "metric_value"
            if "ORDERED_PRODUCTSALES" in adjusted_sql.upper():
                metric_col = "ORDERED_PRODUCTSALES"
            adjusted_sql = adjusted_sql + f" ORDER BY {metric_col} DESC LIMIT {top_n}"

        return adjusted_sql

    def extract_table_name(self, sql: str) -> str:
        """从 SQL 中提取表名"""
        match = re.search(r'FROM\s+([^\s\n;]+)', sql, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def apply_formula_syntax(self, sql: str, formula_config: Dict[str, Any], entities: Dict[str, Any]) -> str:
        """应用公式语法配置"""
        if not formula_config:
            return sql

        template = formula_config.get("template", "")
        if not template:
            return sql

        # 简单替换
        result = template
        for key, value in entities.items():
            if isinstance(value, str):
                result = result.replace(f"{{{key}}}", value)

        return result
