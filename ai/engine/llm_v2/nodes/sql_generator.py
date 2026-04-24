"""
步骤 6: SQL 生成节点

职责：
- 将 MQL 转换为 SQL
- 应用业务规则
- 自动关联表
"""
import re
from enum import Enum
from typing import Dict, Any
from ai.config.logging_config import get_logger
from ai.client.metric_client import MetricClient
from ..schema import MQLSchema, MQLMetric, MQLDimension, TimeRange, TimeType, SQLResult, CalculationPattern, CrossMetricSpec

logger = get_logger("ai.llm_v2.sql_generator")


class SQLGeneratorNode:
    """
    SQL 生成节点

    使用确定性规则将 MQL 转换为 SQL。
    不走 LLM，保证 SQL 生成的可控性。
    """

    # ========== 常量定义 ==========
    # 默认表名
    DEFAULT_TABLE = "ids.IDS_AMZ_COMPREHENSIVE_DI"

    # 时间维度列名
    COL_DATE = "FDATE"
    COL_MONTHS = "MONTHS"
    COL_YEARS = "YEARS"
    COL_WEEKS = "WEEKS"
    COL_QUARTERS = "QUARTERS"

    # 复合指标关键词（用于检测 starrocks_sql 是否为复合指标）
    COMPOUND_KEYWORDS = ["IFNULL", "ISNULL", "COALESCE", "-", "*", "/"]

    # 允许的聚合函数
    ALLOWED_AGGREGATIONS = {"SUM", "AVG", "COUNT", "MAX", "MIN"}

    # 维度类型到数据库列名的映射
    # 同时支持英文和中文 key，从 dimension_configs 表加载
    DIMENSION_COLUMN_MAP = {
        # 英文 key
        "CATEGORY": "GROUP_3",
        "SHOP": "FSITE",
        "SITE": "FSITE",
        "PLATFORM": "PLATFORM",
        "CHANNEL": "FCHANNEL",
        "SKU": "SKU",
        "ASIN": "ASIN",
        "COUNTRY": "FCOUNTRY",
        "REGION": "FREGION",
        "BRAND": "FBRANDS",
        "PRODUCT_LINE": "FPRODUCTLINE",
        "AD_TYPE": "FADTYPE",
        "DAY": "FDATE",
        "MONTH": "MONTHS",
        "YEAR": "YEARS",
        "WEEK": "WEEKS",
        # 中文 key（泛指）
        "品类": "GROUP_3",
        "类目": "GROUP_3",
        "商品类": "GROUP_3",
        "产品类": "GROUP_3",
        "店铺": "FSITE",
        "站点": "FSITE",
        "平台": "PLATFORM",
        "渠道": "FCHANNEL",
        "商品": "SKU",
        "产品": "SKU",
        "品牌": "FBRANDS",
        "国家": "FCOUNTRY",
        "地区": "FREGION",
        "区域": "FREGION",
        # 时间语义 key（天/周/月/年）← LLM 输出高层语义，代码负责映射
        "天": "FDATE",
        "日": "FDATE",
        "月": "MONTHS",
        "年": "YEARS",
        "周": "WEEKS",
        "季度": "QUARTERS",
        "日期": "FDATE",
        "时间": "FDATE",
        "时间粒度": "FDATE",
        # 具体品类级别
        "一级品类": "GROUP_1",
        "二级品类": "GROUP_2",
        "三级品类": "GROUP_3",
        "四级品类": "GROUP_4",
        # 品类级别（数字形式，LLM 直接返回）
        "GROUP_1": "GROUP_1",
        "GROUP_2": "GROUP_2",
        "GROUP_3": "GROUP_3",
        "GROUP_4": "GROUP_4",
    }

    # 允许的字段名模式（字母、数字、下划线）
    ALLOWED_FIELD_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    def __init__(self):
        self._metric_client = MetricClient()
        self._load_dimension_type_mappings()

    def _load_dimension_type_mappings(self) -> None:
        """从 Go API 加载全局维度类型映射，合并到 DIMENSION_COLUMN_MAP"""
        try:
            mappings = self._metric_client.get_dimension_type_mappings()
            for m in mappings:
                if m.get("status") == 1 and m.get("dimension_type") and m.get("column_name"):
                    dim_type = m["dimension_type"]
                    col_name = m["column_name"]
                    # API 返回的映射应覆盖硬编码（API 是最新配置）
                    self.DIMENSION_COLUMN_MAP[dim_type] = col_name
                    logger.info(f"[SQLGenerator] 加载维度映射: {dim_type} -> {col_name}")
            logger.info(f"[SQLGenerator] 共加载 {len(mappings)} 个维度类型映射")
        except Exception as e:
            logger.warning(f"[SQLGenerator] 加载维度类型映射失败，使用硬编码映射: {e}")

    def _validate_field_name(self, field: str) -> str:
        """验证字段名，防止 SQL 注入

        Args:
            field: 字段名

        Returns:
            验证通过的字段名

        Raises:
            ValueError: 字段名不合法
        """
        if not field or not self.ALLOWED_FIELD_PATTERN.match(field):
            logger.warning(f"[SQLGenerator] 非法字段名已拒绝: {field}")
            raise ValueError(f"非法字段名: {field}")
        return field

    def _sanitize_value(self, value: Any) -> str:
        """清洗值，防止 SQL 注入

        Args:
            value: 要清洗的值

        Returns:
            清洗后的值字符串
        """
        if value is None:
            return "NULL"
        # 字符串：转义单引号（SQL 标准）
        if isinstance(value, str):
            return value.replace("'", "''")
        return str(value)

    def _get_dimension_column(self, dim_type: str) -> str:
        """获取维度对应的数据库列名

        尝试多种匹配方式：
        1. 原始值
        2. 大写
        3. 小写
        """
        if not dim_type:
            return ""

        # 尝试原始值
        if dim_type in self.DIMENSION_COLUMN_MAP:
            return self.DIMENSION_COLUMN_MAP[dim_type]

        # 尝试大写
        upper = dim_type.upper()
        if upper in self.DIMENSION_COLUMN_MAP:
            return self.DIMENSION_COLUMN_MAP[upper]

        # 尝试小写
        lower = dim_type.lower()
        if lower in self.DIMENSION_COLUMN_MAP:
            return self.DIMENSION_COLUMN_MAP[lower]

        # 未找到映射时，如果输入看起来像列名（全大写），直接返回
        # 这样可以处理 LLM 直接返回列名（如 FPRODUCTLINE）的情况
        if dim_type.isupper():
            return dim_type

        return ""

    async def generate(self, mql: MQLSchema) -> Dict[str, Any]:
        """
        生成 SQL

        Args:
            mql: MQLSchema 实例

        Returns:
            {
                "sql": str,
                "sql_result": SQLResult,
            }
        """
        logger.info(f"[SQLGenerator] 生成 SQL: intent={mql.intent.value if mql.intent else 'unknown'}")

        try:
            # 1. 构建 SQL
            sql = self._build_sql(mql)

            # 2. 构建 SQLResult
            sql_result = SQLResult(
                sql=sql,
                params={},
                executed=False,
            )

            return {
                "sql": sql,
                "sql_result": sql_result,
            }

        except Exception as e:
            logger.error(f"[SQLGenerator] 错误: {e}")
            return {
                "sql": "",
                "sql_result": SQLResult(sql="", error=str(e)),
            }

    def _build_sql(self, mql: MQLSchema) -> str:
        """构建 SQL"""
        # 跨指标对比：生成自连接 SQL
        if mql.cross_metric and mql.cross_metric.metric_name:
            return self._build_cross_metric_sql(mql)

        # MoM/YOY 对比：生成双时间段 SQL
        if mql.calculation_patterns:
            from ..schema import CalculationPattern
            def _is_mom(p):
                if isinstance(p, CalculationPattern):
                    return p == CalculationPattern.MOM or p.value == "mom"
                return str(p).lower() == "mom"
            def _is_yoy(p):
                if isinstance(p, CalculationPattern):
                    return p == CalculationPattern.YOY or p.value == "yoy"
                return str(p).lower() == "yoy"
            has_mom = any(_is_mom(p) for p in mql.calculation_patterns)
            has_yoy = any(_is_yoy(p) for p in mql.calculation_patterns)
            if has_mom or has_yoy:
                return self._build_mom_sql(mql)

        # 1. 确定表名
        table = mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE

        # 2. 构建 SELECT 子句
        select_clause = self._build_select(mql)

        # 3. 构建 FROM 子句
        from_clause = f"FROM {table}"

        # 4. 构建 WHERE 子句
        where_clause = self._build_where(mql)

        # 5. 构建 GROUP BY 子句
        group_by_clause = self._build_group_by(mql)

        # 6. 构建 ORDER BY 子句
        order_by_clause = self._build_order_by(mql)

        # 7. 构建 LIMIT 子句
        limit_clause = self._build_limit(mql)

        # 8. 拼接 SQL
        sql_parts = [select_clause, from_clause]
        if where_clause:
            sql_parts.append(where_clause)
        if group_by_clause:
            sql_parts.append(group_by_clause)
        if order_by_clause:
            sql_parts.append(order_by_clause)
        if limit_clause:
            sql_parts.append(limit_clause)

        return "\n".join(sql_parts)

    def _build_cross_metric_sql(self, mql: MQLSchema) -> str:
        """构建跨指标对比 SQL（CTE 自连接）

        思路：将每个指标的 starrocks_sql 转换为带维度的聚合子查询，
        再通过 CTE/子查询 JOIN 在一起，最后应用比较条件过滤。
        """
        logger.info(f"[_build_cross_metric_sql] cross_metric={mql.cross_metric.metric_name}, operator={mql.cross_metric.operator}")

        # 1. 获取维度列
        dim_columns = []
        for dim in mql.dimensions:
            col = dim.column
            if not col:
                col = self._get_dimension_column(dim.type)
            if col:
                dim_columns.append(col)
        if not dim_columns:
            dim_columns = ["YEARS", "MONTHS"]

        dim_select = ", ".join(dim_columns)
        dim_group = ", ".join(dim_columns)
        dim_join = " AND ".join([f"a.{c} = b.{c}" for c in dim_columns])

        # 2. 获取 WHERE 条件（时间等）
        where_clause = self._build_where(mql)
        if where_clause.upper().startswith("WHERE"):
            where_clause = where_clause[5:].strip()
        where_sql = f"WHERE {where_clause}" if where_clause else ""

        # 3. 获取指标 A（主指标）的聚合表达式
        metric_a_name = mql.metric.name if mql.metric else ""
        metric_a_sql, metric_a_alias = self._extract_metric_expression(mql.metric, "metric_a")
        if not metric_a_sql:
            return f"SELECT 'ERROR: 主指标 {metric_a_name} 无 starrocks_sql' AS error"

        # 4. 获取指标 B（对比指标）的聚合表达式
        metric_b_name = mql.cross_metric.metric_name
        metric_b_info = self._metric_client.get_metric_by_name(metric_b_name)
        if not metric_b_info or not metric_b_info.get("starrocks_sql"):
            return f"SELECT 'ERROR: 对比指标 {metric_b_name} 未找到' AS error"
        # 构建一个临时 MQLMetric 用于提取
        metric_b = MQLMetric(
            name=metric_b_name,
            starrocks_sql=metric_b_info.get("starrocks_sql", ""),
            field=metric_b_info.get("starrocks_field", ""),
        )
        metric_b_sql, metric_b_alias = self._extract_metric_expression(metric_b, "metric_b")

        # 5. 比较运算符
        op = mql.cross_metric.operator
        op_map = {"lt": "<", "gt": ">", "eq": "=", "lte": "<=", "gte": ">="}
        sql_op = op_map.get(op, "<")

        # 6. 拼接完整 SQL（CTE 方式）
        # 注意：WHERE 条件必须在每个 CTE 内部都应用，否则子查询结果不对
        # 当 where_clause 为空时，使用 1=1 作为占位条件，避免语法错误
        where_cond = where_clause[5:].strip() if where_clause.upper().startswith("WHERE") else where_clause
        where_in_cte = where_cond if where_cond else "1=1"
        # SELECT 子句中维度列需要加表前缀 a.
        dim_select_a = ", ".join([f"a.{c}" for c in dim_columns])
        sql = f"""
WITH metric_a AS (
    SELECT {dim_select}, {metric_a_sql} AS {metric_a_alias}
    FROM {self.DEFAULT_TABLE}
    WHERE {where_in_cte}
    GROUP BY {dim_group}
),
metric_b AS (
    SELECT {dim_select}, {metric_b_sql} AS {metric_b_alias}
    FROM {self.DEFAULT_TABLE}
    WHERE {where_in_cte}
    GROUP BY {dim_group}
)
SELECT {dim_select_a}, a.{metric_a_alias} AS {metric_a_alias}, b.{metric_b_alias} AS {metric_b_alias}
FROM metric_a a
INNER JOIN metric_b b ON {dim_join}
WHERE a.{metric_a_alias} {sql_op} b.{metric_b_alias}
ORDER BY {dim_group}
LIMIT 20
""".strip()
        logger.info(f"[_build_cross_metric_sql] SQL: {sql[:300]}")
        return sql

    def _build_mom_sql(self, mql: MQLSchema) -> str:
        """构建 MoM/YOY 对比 SQL

        使用条件聚合在一个查询中计算当前周期和对比周期的值。
        """
        logger.info(f"[_build_mom_sql] Building MoM/YOY SQL")

        # 0. 去除 mql.dimensions 中的重复项（相同 type + value 只保留一个）
        seen_dims = set()
        unique_dimensions = []
        for dim in mql.dimensions:
            dim_key = (dim.type, dim.value)
            if dim_key not in seen_dims:
                seen_dims.add(dim_key)
                unique_dimensions.append(dim)
        mql.dimensions = unique_dimensions
        logger.info(f"[_build_mom_sql] 去重后维度: {[(d.type, d.value) for d in mql.dimensions]}")

        # 1. 获取业务维度列（不包括 YEARS, MONTHS）
        # 注意：只有当维度没有具体值时才加入 GROUP BY
        # 如果维度有具体值（如 GROUP_2 = '智能云存储'），已经通过 WHERE 过滤，不需要 GROUP BY
        dim_columns = []
        for dim in mql.dimensions:
            col = dim.column
            if not col:
                col = self._get_dimension_column(dim.type)
            if col:
                # 只有当维度没有具体值时才加入 GROUP BY
                if not dim.value:
                    dim_columns.append(col)
                    logger.info(f"[_build_mom_sql] 维度 {col} 无具体值，加入 GROUP BY")
                else:
                    logger.info(f"[_build_mom_sql] 维度 {col} = '{dim.value}' 有具体值，不加入 GROUP BY")

        # 2. 获取当前周期时间条件
        current_where = self._build_where(mql)
        if current_where.upper().startswith("WHERE"):
            current_where = current_where[5:].strip()
        current_where_sql = f"WHERE {current_where}" if current_where else "WHERE 1=1"

        # 3. 获取对比周期时间条件
        compare_start = ""
        compare_end = ""
        if mql.comparison:
            compare_start = mql.comparison.compare_period_start or ""
            compare_end = mql.comparison.compare_period_end or ""

        # 如果没有对比时间，根据 MoM/YOY 自行推断
        if not compare_start or not compare_end:
            from ..schema import CalculationPattern
            def _is_mom(p):
                if isinstance(p, CalculationPattern):
                    return p == CalculationPattern.MOM or p.value == "mom"
                return str(p).lower() == "mom"
            has_mom = any(_is_mom(p) for p in mql.calculation_patterns)
            # 如果当前周期超过60天（约2个月），"环比呢"应该用YoY而不是MoM
            # 因为跨多月的情况下，MoM环比意义不大
            period_too_long_for_mom = False
            if has_mom and current_where:
                # 从 current_where 提取当前周期的 start 和 end
                import re
                start_match = re.search(r"FDATE >= '(\d{4}-\d{2}-\d{2})'", current_where)
                end_match = re.search(r"FDATE <= '(\d{4}-\d{2}-\d{2})'", current_where)
                if start_match and end_match:
                    try:
                        from datetime import datetime, timedelta
                        start_dt = datetime.strptime(start_match.group(1), "%Y-%m-%d")
                        end_dt = datetime.strptime(end_match.group(1), "%Y-%m-%d")
                        day_count = (end_dt - start_dt).days + 1
                        if day_count > 60:
                            period_too_long_for_mom = True
                            logger.info(f"[_build_mom_sql] 当前周期{day_count}天>60天，跳过MoM，使用YoY")
                    except Exception:
                        pass

            if has_mom and current_where and not period_too_long_for_mom:
                # 从 current_where 提取当前周期的 start 和 end
                # current_where 格式: "FDATE >= '2026-04-01' AND FDATE <= '2026-04-21'"
                import re
                start_match = re.search(r"FDATE >= '(\d{4}-\d{2}-\d{2})'", current_where)
                end_match = re.search(r"FDATE <= '(\d{4}-\d{2}-\d{2})'", current_where)
                if start_match and end_match:
                    try:
                        from datetime import datetime, timedelta
                        start_dt = datetime.strptime(start_match.group(1), "%Y-%m-%d")
                        end_dt = datetime.strptime(end_match.group(1), "%Y-%m-%d")
                        day_count = (end_dt - start_dt).days + 1  # 当前周期天数

                        # 环比上月：上月 1 日到对应天数
                        # 例如 4-01~4-21（21天）→ 3-01~3-20
                        # 上月 1 日 = 当前月 1 日往前推 1 个月
                        prev_month_start = start_dt - timedelta(days=1)
                        # 清理日期，只保留到月（day=1）
                        prev_month_start = prev_month_start.replace(day=1)
                        # 上月 end = 上月 1 日 + (day_count - 1) 天，但要确保不超过上月最大天数
                        import calendar
                        prev_month_max_day = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
                        prev_end_day = min(day_count, prev_month_max_day)
                        compare_start = prev_month_start.strftime("%Y-%m-%d")
                        compare_end = prev_month_start.replace(day=prev_end_day).strftime("%Y-%m-%d")
                        logger.info(f"[_build_mom_sql] Inferred MoM: current {start_dt.date()}~{end_dt.date()} ({day_count}天), compare {compare_start} to {compare_end}")
                    except Exception as e:
                        logger.warning(f"[_build_mom_sql] 推断 MoM 失败: {e}")

            # YOY 同比：去年同期（保持相同天数）
            def _is_yoy(p):
                if isinstance(p, CalculationPattern):
                    return p == CalculationPattern.YOY or p.value == "yoy"
                return str(p).lower() == "yoy"
            has_yoy = any(_is_yoy(p) for p in mql.calculation_patterns)
            # 如果 has_mom 但 period 太长被跳过，也应该进入 YoY
            has_mom_but_period_too_long = has_mom and period_too_long_for_mom
            if (has_yoy or has_mom_but_period_too_long) and current_where and not compare_start:
                # 还没有 compare_start，说明 MoM 没匹配或不是 MoM
                import re
                start_match = re.search(r"FDATE >= '(\d{4}-\d{2}-\d{2})'", current_where)
                end_match = re.search(r"FDATE <= '(\d{4}-\d{2}-\d{2})'", current_where)
                if start_match and end_match:
                    try:
                        from datetime import datetime, timedelta
                        start_dt = datetime.strptime(start_match.group(1), "%Y-%m-%d")
                        end_dt = datetime.strptime(end_match.group(1), "%Y-%m-%d")
                        day_count = (end_dt - start_dt).days + 1

                        # 同比：去年同期
                        # 例如 2026-04-01~04-21 → 2025-04-01~04-21
                        prev_year_start = start_dt.replace(year=start_dt.year - 1)
                        prev_year_end = end_dt.replace(year=end_dt.year - 1)
                        compare_start = prev_year_start.strftime("%Y-%m-%d")
                        compare_end = prev_year_end.strftime("%Y-%m-%d")
                        logger.info(f"[_build_mom_sql] Inferred YoY: current {start_dt.date()}~{end_dt.date()} ({day_count}天), compare {compare_start} to {compare_end}")
                    except Exception as e:
                        logger.warning(f"[_build_mom_sql] 推断 YoY 失败: {e}")

        # 4. 获取指标的原始字段表达式（用于条件聚合，不需要外层聚合函数）
        metric_field_sql = self._extract_raw_metric_expression(mql.metric)
        if not metric_field_sql:
            return f"SELECT 'ERROR: 指标无 starrocks_sql' AS error"

        # 5. 构建 MoM SQL - 使用条件聚合避免 JOIN 问题
        # 关键：如果没有业务维度（dim_columns 为空），不按 MONTHS 分组，
        #      让两个月的数据直接聚合在一起计算 change_rate
        current_cond = current_where[6:].strip() if current_where.upper().startswith('WHERE') else current_where

        # ========== 提取纯时间条件（用于 WHERE 的 OR 部分） ==========
        # current_cond 包含 time + filters + dimensions，需要分离
        # 时间条件格式: FDATE >= '...' AND FDATE <= '...'
        import re
        time_pattern = r"(FDATE >= '(\d{4}-\d{2}-\d{2})' AND FDATE <= '(\d{4}-\d{2}-\d{2})')"
        time_match = re.search(time_pattern, current_cond)
        if time_match:
            current_time_cond = time_match.group(1)  # e.g., "FDATE >= '2026-04-01' AND FDATE <= '2026-04-23'"
        else:
            current_time_cond = current_cond  # fallback
        # =====================================================================

        # 6. 构建对比周期条件（只有当对比周期有效时才添加）
        # 注意：compare_where 必须包含与 current_where 相同的 filters 和 dimensions，否则对比基数不一致
        has_valid_compare = bool(compare_start and compare_end)
        if has_valid_compare:
            # 从 mql.filters 构建过滤条件（使用安全方法防止 SQL 注入）
            filter_parts = []
            for f in mql.filters:
                if f.field and f.value is not None:
                    op = f.operator.value if hasattr(f.operator, 'value') else f.operator
                    # 验证字段名，防止注入
                    safe_field = self._validate_field_name(f.field)
                    if op == "eq":
                        filter_parts.append(f"{safe_field} = '{self._sanitize_value(f.value)}'")
                    elif op == "gt":
                        filter_parts.append(f"{safe_field} > '{self._sanitize_value(f.value)}'")
                    elif op == "lt":
                        filter_parts.append(f"{safe_field} < '{self._sanitize_value(f.value)}'")
                    elif op == "in":
                        values = f.value if isinstance(f.value, list) else [f.value]
                        safe_values = "', '".join([self._sanitize_value(v) for v in values])
                        filter_parts.append(f"{safe_field} IN ('{safe_values}')")
                    elif op == "between":
                        if isinstance(f.value, list) and len(f.value) == 2:
                            filter_parts.append(f"{safe_field} BETWEEN '{self._sanitize_value(f.value[0])}' AND '{self._sanitize_value(f.value[1])}'")

            # 维度过滤（用于确保 compare 周期也有维度过滤）
            dim_filter_parts = []
            for dim in mql.dimensions:
                if dim.value:
                    col = dim.column
                    if not col:
                        col = self._get_dimension_column(dim.type)
                    if col:
                        safe_col = self._validate_field_name(col)
                        dim_filter_parts.append(f"{safe_col} = '{self._sanitize_value(dim.value)}'")

            time_cond = f"(FDATE >= '{compare_start}' AND FDATE <= '{compare_end}')"
            # 合并 filter 和 dimension
            all_filter_parts = filter_parts + dim_filter_parts
            if all_filter_parts:
                filter_cond = " AND ".join(all_filter_parts)
                compare_where = f"({time_cond} AND {filter_cond})"
            else:
                compare_where = time_cond
        else:
            # 没有有效对比周期时，compare_where 为空字符串，后续 SQL 构建会处理
            compare_where = ""

        # ========== 构建 WHERE 条件 ==========
        # 重要：WHERE 必须只包含时间条件，不能加维度！
        # 因为我们需要扫描所有维度值的数据，然后通过 GROUP BY 聚合到特定维度
        # 如果 WHERE 加了维度，就会漏掉其他维度值的数据
        #
        # CASE WHEN 条件需要同时包含时间+维度，因为每个 SUM 要分别计算正确
        # current_cond 本身已经包含时间+维度（来自 _build_where），所以 CASE WHEN 直接用它即可

        # 提取纯时间条件（用于 WHERE）
        import re
        time_pattern = r"(FDATE >= '(\d{4}-\d{2}-\d{2})' AND FDATE <= '(\d{4}-\d{2}-\d{2})')"
        time_match = re.search(time_pattern, current_cond)
        if time_match:
            current_time_only = time_match.group(1)
        else:
            current_time_only = current_cond

        # WHERE 只用纯时间条件
        where_current = current_time_only
        where_compare = f"(FDATE >= '{compare_start}' AND FDATE <= '{compare_end}')" if has_valid_compare else ""
        # ========================================================

        if dim_columns:
            # 有业务维度，按业务维度 + MONTHS 分组
            dim_select = ", ".join(dim_columns)
            dim_group = dim_select
            # 添加 MONTHS 到分组，用于区分月份
            select_clause = f"{dim_select}, MONTHS"
            group_clause = f"{dim_group}, MONTHS"

            # 根据是否有有效对比周期构建不同的 SQL
            if has_valid_compare:
                sql = f"""
SELECT {select_clause},
       SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) AS current_val,
       SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END) AS compare_val,
       CASE WHEN SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END) > 0
            THEN ROUND((SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) - SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END)) / SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END) * 100, 2)
            ELSE NULL END AS change_rate,
       CASE WHEN SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) > SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END)
            THEN '增长'
            WHEN SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) < SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END)
            THEN '下降'
            ELSE '持平' END AS trend
FROM {self.DEFAULT_TABLE}
WHERE ( {current_cond} )
   OR ( {compare_where} )
GROUP BY {group_clause}
ORDER BY {dim_group}, MONTHS
LIMIT 20
""".strip()
            else:
                # 没有有效对比周期，只查当前周期
                sql = f"""
SELECT {select_clause},
       SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) AS current_val,
       NULL AS compare_val,
       NULL AS change_rate,
       NULL AS trend
FROM {self.DEFAULT_TABLE}
WHERE ( {current_cond} )
GROUP BY {group_clause}
ORDER BY {dim_group}, MONTHS
LIMIT 20
""".strip()
        else:
            # 没有业务维度，直接对比两个月（不去 GROUP BY MONTHS）
            # 两个月的数据会聚合在一起，直接计算 change_rate
            if has_valid_compare:
                sql = f"""
SELECT
       SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) AS current_val,
       SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END) AS compare_val,
       CASE WHEN SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END) > 0
            THEN ROUND((SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) - SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END)) / SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END) * 100, 2)
            ELSE NULL END AS change_rate,
       CASE WHEN SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) > SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END)
            THEN '增长'
            WHEN SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) < SUM(CASE WHEN {compare_where} THEN {metric_field_sql} ELSE 0 END)
            THEN '下降'
            ELSE '持平' END AS trend
FROM {self.DEFAULT_TABLE}
WHERE ( {current_cond} )
   OR ( {compare_where} )
""".strip()
            else:
                # 没有有效对比周期，只查当前周期
                sql = f"""
SELECT
       SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END) AS current_val,
       NULL AS compare_val,
       NULL AS change_rate,
       NULL AS trend
FROM {self.DEFAULT_TABLE}
WHERE ( {current_cond} )
""".strip()

        logger.info(f"[_build_mom_sql] SQL: {sql[:300]}")
        return sql

    def _extract_raw_metric_expression(self, metric: MQLMetric) -> str:
        """从 metric 的 starrocks_sql 提取原始字段表达式（不含聚合函数）

        用于条件聚合（CASE WHEN 内部），因为外层 SUM 会做聚合。

        Returns:
            str: 原始字段表达式，如 "PAGEVIEWS_TOTAL" 或 "IFNULL(a,0)-IFNULL(b,0)"
        """
        if not metric or not metric.starrocks_sql:
            return metric.field if metric else "ORDERED_PRODUCTSALES"

        starrocks_sql = metric.starrocks_sql.strip()

        # 检查是否是复合指标（包含 IFNULL/ISNULL/COALESCE 或算术运算符）
        if any(kw in starrocks_sql.upper() for kw in self.COMPOUND_KEYWORDS):
            # 复合指标：提取 SELECT 和 FROM 之间的表达式
            expr_match = re.search(r'SELECT\s+(.+?)\s+AS\s+[\w\u4e00-\u9fff]+\s+FROM', starrocks_sql, re.IGNORECASE | re.DOTALL)
            if expr_match:
                expr = expr_match.group(1).strip()
                logger.info(f"[_extract_raw_metric_expression] 复合指标: {expr}")
                return expr
            # 回退：用 split 提取
            parts = re.split(r'\s+FROM\s+', starrocks_sql, flags=re.IGNORECASE)
            if len(parts) >= 2:
                select_part = ' FROM '.join(parts[:-1])
                alias_match = re.search(r'\s+AS\s+([\w\u4e00-\u9fff]+)\s*$', select_part, re.IGNORECASE)
                if alias_match:
                    expr = select_part[:alias_match.start()].strip()
                    if expr.upper().startswith('SELECT'):
                        expr = expr[6:].strip()
                    logger.info(f"[_extract_raw_metric_expression] 复合指标split: {expr}")
                    return expr

        # 简单指标：提取 SUM/AVG/COUNT/MAX/MIN (field) 中的 field
        match = re.search(r'(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)', starrocks_sql, re.IGNORECASE)
        if match:
            field = match.group(2)
            logger.info(f"[_extract_raw_metric_expression] 简单指标字段: {field}")
            return field

        # 回退：使用默认字段
        logger.warning(f"[_extract_raw_metric_expression] 无法提取字段，使用默认: {metric.field}")
        return metric.field or "ORDERED_PRODUCTSALES"

    def _extract_metric_expression(self, metric: MQLMetric, prefix: str) -> tuple:
        """从 metric 的 starrocks_sql 提取聚合表达式和别名

        Returns:
            (expression: str, alias: str)
            expression: 直接可用于 SELECT 的聚合表达式，如 "SUM(TOTALORDERS)"
            alias: SQL 别名，如 "metric_a"
        """
        if not metric or not metric.starrocks_sql:
            field = metric.field if metric else "ORDERED_PRODUCTSALES"
            agg = "SUM"
            if metric and metric.aggregation:
                agg = metric.aggregation.value if hasattr(metric.aggregation, 'value') else metric.aggregation
            return f"{agg}({field})", prefix

        starrocks_sql = metric.starrocks_sql.strip()

        # 尝试提取 AS 别名
        alias_match = re.search(r'AS\s+([\w\u4e00-\u9fff]+)', starrocks_sql, re.IGNORECASE)
        alias = alias_match.group(1) if alias_match else prefix

        # 检查是否是复合指标（包含 IFNULL/ISNULL/COALESCE 或算术运算符）
        if any(kw in starrocks_sql.upper() for kw in self.COMPOUND_KEYWORDS):
            # 复合指标：从 "SELECT expr AS alias FROM ..." 提取 expr
            expr_match = re.search(r'SELECT\s+(.+?)\s+AS\s+[\w\u4e00-\u9fff]+\s+FROM', starrocks_sql, re.IGNORECASE | re.DOTALL)
            if expr_match:
                expr = expr_match.group(1).strip()
                return expr, alias
            # 如果上面的正则匹配失败（因为 " AS " 可能写成 ")AS" 没有空格），
            # 用 split 方案：按 " FROM " 分割（注意 IFNULL 内的 " FROM " 不会匹配因为有前缀空格）
            parts = re.split(r'\s+FROM\s+', starrocks_sql, flags=re.IGNORECASE)
            if len(parts) >= 2:
                select_and_alias = ' FROM '.join(parts[:-1])  # 第一部分是 SELECT ... AS alias
                # 在 select_and_alias 中找 " AS " 分隔符（别名前面可能有空格）
                # 用更宽松的正则：支持 " AS " 或 ")AS" 等情况
                alias_match2 = re.search(r'\s+AS\s+([\w\u4e00-\u9fff]+)\s*$', select_and_alias, re.IGNORECASE)
                if alias_match2:
                    alias = alias_match2.group(1)
                    inner = select_and_alias[:alias_match2.start()].strip()
                    if inner.upper().startswith('SELECT'):
                        inner = inner[6:].strip()
                    return inner, alias
                else:
                    # 还是找不到 AS，试一下不用 \s+ 的宽松匹配
                    # 找最后一个 " AS " 或 ")AS" 模式
                    alt_match = re.search(r'AS\s+([\w\u4e00-\u9fff]+)\s*$', select_and_alias, re.IGNORECASE)
                    if alt_match:
                        alias = alt_match.group(1)
                        inner = select_and_alias[:alt_match.start()].strip()
                        if inner.upper().startswith('SELECT'):
                            inner = inner[6:].strip()
                        return inner, alias
            # 兜底：去掉开头的 SELECT 和结尾的 FROM alias 部分
            sql_clean = starrocks_sql.strip()
            if sql_clean.upper().startswith('SELECT'):
                sql_clean = sql_clean[6:].strip()
            from_idx = sql_clean.upper().rfind(' FROM ')
            if from_idx > 0:
                sql_clean = sql_clean[:from_idx].strip()
            as_idx = sql_clean.upper().rfind(' AS ')
            if as_idx > 0:
                expr = sql_clean[:as_idx].strip()
            else:
                expr = sql_clean
            return expr, alias
        else:
            # 简单指标：提取 SUM/AVG/COUNT/MAX/MIN (field)
            match = re.search(r'(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)', starrocks_sql, re.IGNORECASE)
            if match:
                agg, field = match.groups()
                return f"{agg}({field})", alias
            # 回退
            field = metric.field if metric else "ORDERED_PRODUCTSALES"
            return f"SUM({field})", alias

    def _build_select(self, mql: MQLSchema) -> str:
        """构建 SELECT 子句"""
        logger.info(f"[_build_select] starrocks_sql={mql.metric.starrocks_sql[:80] if mql.metric and mql.metric.starrocks_sql else 'EMPTY'}")
        select_parts = []

        # 添加维度列
        for dim in mql.dimensions:
            if dim.column:
                select_parts.append(dim.column)
            else:
                col = self._get_dimension_column(dim.type)
                if col:
                    select_parts.append(col)

        # 如果有时间过滤且是月粒度查询，确保 MONTHS 加入 SELECT（让时间在结果中可见）
        # 使用 MONTH(FDATE) 格式化月份，如 "2月"
        if mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            if self.COL_MONTHS not in select_parts:
                select_parts.append(f"MONTH(FDATE) AS MONTHS")
            # 同时添加日期范围（方便前端显示）
            if "MONTH(FDATE)" in " ".join(select_parts) and "FDATE_START" not in " ".join(select_parts):
                select_parts.append(f"MIN(FDATE) AS FDATE_START")
                select_parts.append(f"MAX(FDATE) AS FDATE_END")

        # 检查占比模式（percentage）：生成 分子 * 100.0 / 分母 SQL
        has_percentage = any(
            (p.value if isinstance(p, Enum) else p) == CalculationPattern.PERCENTAGE.value
            for p in mql.calculation_patterns
        )
        if has_percentage and mql.molecule_metric and mql.denominator_metric:
            # 使用分子/分母指标生成占比 SQL
            mol = mql.molecule_metric
            den = mql.denominator_metric

            # 从 starrocks_sql 解析字段（优先，因为 validator 已填充）
            def _extract_field_from_sql(starrocks_sql, default_field):
                if not starrocks_sql:
                    return default_field
                sql_upper = starrocks_sql.strip().upper()
                # 匹配 SUM(xxx) 或 COUNT(xxx) 等聚合函数
                match = re.search(r'(?:SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)', sql_upper)
                if match:
                    return match.group(1)
                # 匹配 SUM(xxx) AS alias 或直接字段
                match = re.search(r'SELECT\s+.*?\s+AS\s+([\w\u4e00-\u9fff]+)\s*FROM', sql_upper, re.DOTALL)
                if match:
                    alias = match.group(1)
                    # 如果 alias 等于默认字段，可能是真实字段名
                    return alias
                return default_field

            # 从 starrocks_sql 解析完整表达式（用于占比计算）
            # 关键：对于复合指标（如 SUM(IFNULL(...)) 或 a/b），需要提取完整的原始表达，
            # 而不是再次包装聚合函数，�l剔会导致 SUM(SUM(...)) 括号嵌埋问题
            def _extract_raw_expression(starrocks_sql, default_field):
                if not starrocks_sql:
                    return default_field
                sql_upper = starrocks_sql.strip().upper()
                # 情况1: 以 SELECT 开头 - 尝试提取完整表达式
                if sql_upper.startswith('SELECT'):
                    # 检查是否是复合指标（包含 /, *, IFNULL, ISNULL, COALESCE）
                    if any(kw in sql_upper for kw in ['/', '*', 'IFNULL', 'ISNULL', 'COALESCE']):
                        # 复合指标：从 SELECT expr AS alias FROM ... 提取 expr
                        match = re.search(r'SELECT\s+(.+?)\s+AS\s+[`\[]?[\w\u4e00-\u9fff]+[`\]]?\s+FROM', sql_upper, re.IGNORECASE | re.DOTALL)
                        if match:
                            expr = match.group(1).strip()
                            logger.info(f'[_build_select] 占比复合指标 expr: {expr}')
                            return expr
                        # 回退：按 FROM 分割
                        parts = re.split(r'\s+FROM\s+', sql_upper, flags=re.IGNORECASE)
                        if len(parts) >= 2:
                            select_part = ' FROM '.join(parts[:-1])
                            if select_part.upper().startswith('SELECT'):
                                select_part = select_part[6:].strip()
                            alias_match = re.search(r'\s+AS\s+[\w\u4e00-\u9fff]+\s*$', select_part, re.IGNORECASE)
                            if alias_match:
                                select_part = select_part[:alias_match.start()].strip()
                            return select_part
                    # 非复合 SELECT：提取聚合函数内的字段
                    match = re.search(r'(?:SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)', sql_upper)
                    if match:
                        return match.group(1)
                    return default_field
                # 情况2: 裸字段名（如 "REFUND_QTY"）- 直接返回
                # 这种情况下 _ensure_sum 会负责包装 SUM
                if not any(kw in sql_upper for kw in ['(', 'SELECT', 'FROM', 'WHERE', 'CASE']):
                    return starrocks_sql.strip()
                # 情况3: 其他情况（如 "SUM(REFUND_QTY)" 不带 SELECT/FROM）
                match = re.search(r'(?:SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)', sql_upper)
                if match:
                    return match.group(1)
                return default_field

            # 当 molecule_metric 的 starrocks_sql 为空时，从主指标的 starrocks_sql 解析分子/分母表达式
            # 这是核心修复：避免 LLM 生成的 name 不匹配数据库时，用了错误的默认字段
            def _extract_from_main_metric(main_sql, target="molecule"):
                """从主指标的 starrocks_sql 解析分子或分母表达式"""
                if not main_sql:
                    return None
                sql_upper = main_sql.strip().upper()
                if not sql_upper.startswith('SELECT'):
                    return None
                # 匹配 "分子: SUM(xxx)" 或 "分母: / SUM(yyy)" 模式
                if target == "分子":
                    # 找 / 前面的聚合表达式（分子）
                    match = re.search(r'(?:^|[+\-*/\s])(\(?\s*(?:SUM|AVG|COUNT|MAX|MIN)\s*\([^)]+\))', sql_upper, re.IGNORECASE)
                    if match:
                        expr = match.group(1).strip()
                        logger.info(f"[_build_select] 从主指标SQL解析分子: {expr}")
                        return expr
                elif target == "分母":
                    # 找 / 后面的聚合表达式（分母）
                    match = re.search(r'/\s*(\(?\s*(?:SUM|AVG|COUNT|MAX|MIN)\s*\([^)]+\))', sql_upper, re.IGNORECASE)
                    if match:
                        expr = match.group(1).strip()
                        logger.info(f"[_build_select] 从主指标SQL解析分母: {expr}")
                        return expr
                return None
                return None

            # 优先使用各自 metric 的 starrocks_sql（validator 已填充），否则从主指标 SQL 解析
            mol_sql = mol.starrocks_sql or _extract_from_main_metric(mql.metric.starrocks_sql if mql.metric else None, "分子")
            den_sql = den.starrocks_sql or _extract_from_main_metric(mql.metric.starrocks_sql if mql.metric else None, "分母")
            mol_expr = _extract_raw_expression(mol_sql, mol.field or "REFUND_QTY")
            den_expr = _extract_raw_expression(den_sql, den.field or "ORDERED_PRODUCTSALES")
            # 生成占比表达式（使用 ABS 取绝对值，因为退款数据可能是负数）
            # 如果是简单字段（非聚合表达式），需要包装 SUM()
            def _ensure_sum(expr):
                stripped = expr.strip().upper()
                if any(stripped.startswith(agg) for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN(']):
                    return expr
                return f"SUM({expr})"
            ratio_expr = f"ABS({_ensure_sum(mol_expr)} * 100.0 / {_ensure_sum(den_expr)})"
            # 构造占比名称：分子 + "占" + 分母 + "比重"
            if mol.name and den.name:
                ratio_name = f"{mol.name}占{den.name}比重"
            elif mol.name:
                ratio_name = f"{mol.name}占比"
            else:
                ratio_name = "占比"
            select_parts.append(f"{ratio_expr} AS {ratio_name}")
            logger.info(f"[_build_select] 占比模式: {mol_expr} * 100.0 / {den_expr}")
        # 添加指标列
        elif mql.metric:
            logger.info(f"[_build_select] metric.starrocks_sql={repr(mql.metric.starrocks_sql[:80] if mql.metric.starrocks_sql else '')}, metric.field={repr(mql.metric.field)}")
            metric_field = mql.metric.field or "ORDERED_PRODUCTSALES"
            metric_agg = mql.metric.aggregation.value if hasattr(mql.metric.aggregation, 'value') else mql.metric.aggregation

            # 如果有 starrocks_sql，解析字段
            if mql.metric.starrocks_sql:
                starrocks_sql = mql.metric.starrocks_sql.strip()
                logger.info(f"[_build_select] starrocks_sql: {starrocks_sql[:200]}")

                # 检测是否是复合指标（包含 / 或 * 或 IFNULL/ISNULL）
                if '/' in starrocks_sql or '*' in starrocks_sql or 'IFNULL' in starrocks_sql.upper():
                    # 复合指标：提取完整的 SELECT ... AS alias 表达式
                    # 用 split 而非正则来处理嵌套 FROM（如 IFNULL 函数内的 FROM 字段名）
                    # "SELECT sum(IFNULL(units_ordered, 0) - IFNULL(totalunits, 0)) AS alias FROM table"
                    #                           ^^^^^^^^^^^^^^^^ 这些 FROM 只是字段名，不是 SQL FROM 子句
                    parts = re.split(r'\s+FROM\s+', starrocks_sql, flags=re.IGNORECASE)
                    if len(parts) >= 2:
                        # 最后一个 part 是 FROM 子句，前面所有 part 拼起来是 SELECT ... AS alias
                        select_and_alias = ' FROM '.join(parts[:-1])  # 还原，不丢失内容
                        # 从 select_and_alias 中提取 AS alias 和 inner_expr
                        alias_match = re.search(r'\s+AS\s+([\w\u4e00-\u9fff]+)\s*$', select_and_alias, re.IGNORECASE)
                        if alias_match:
                            alias = alias_match.group(1)
                            inner_expr = select_and_alias[:alias_match.start()].strip()
                            # 去掉开头的 SELECT 关键字
                            if inner_expr.upper().startswith('SELECT'):
                                inner_expr = inner_expr[6:].strip()
                            logger.info(f"[_build_select] 复合指标split提取成功: inner_expr={inner_expr}, alias={alias}")
                            select_parts.append(f"{inner_expr} AS {alias}")
                        else:
                            logger.warning(f"[_build_select] 复合指标提取alias失败，回退到默认值")
                            select_parts.append(f"{metric_agg}({metric_field})")
                    else:
                        logger.warning(f"[_build_select] 复合指标split失败，回退到默认值")
                        select_parts.append(f"{metric_agg}({metric_field})")
                else:
                    # 简单指标：匹配单个聚合函数
                    match = re.search(r'(?:SELECT\s+[^,]*,\s*)?(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)\s*(?:AS\s*`?(\w+)`?)?', starrocks_sql, re.IGNORECASE)
                    if match:
                        agg, field, alias = match.groups()
                        logger.info(f"[_build_select] 正则匹配成功: agg={agg}, field={field}, alias={alias}")
                        if alias:
                            select_parts.append(f"{agg}({field}) AS {alias}")
                        else:
                            select_parts.append(f"{agg}({field})")
                    else:
                        logger.warning(f"[_build_select] 正则匹配失败，回退到默认值: metric_field={metric_field}")
                        select_parts.append(f"{metric_agg}({metric_field})")
            else:
                logger.warning(f"[_build_select] starrocks_sql 为空，使用默认值: metric_field={metric_field}")
                select_parts.append(f"{metric_agg}({metric_field})")

        # 多指标支持：处理 mql.metrics 中的额外指标
        for i, metric in enumerate(mql.metrics):
            if not metric or not metric.name:
                continue
            # 跳过与主指标相同的项
            if mql.metric and metric.name == mql.metric.name:
                continue
            logger.info(f"[_build_select] 多指标[{i}]: {metric.name}, starrocks_sql={metric.starrocks_sql[:80] if metric.starrocks_sql else 'EMPTY'}")

            metric_field = metric.field or "ORDERED_PRODUCTSALES"
            metric_agg = metric.aggregation.value if hasattr(metric.aggregation, 'value') else (metric.aggregation or "SUM")

            if metric.starrocks_sql:
                starrocks_sql = metric.starrocks_sql.strip()
                # 尝试提取字段
                match = re.search(r'(?:SELECT\s+[^,]*,\s*)?(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)\s*(?:AS\s*`?(\w+)`?)?', starrocks_sql, re.IGNORECASE)
                if match:
                    agg, field, alias = match.groups()
                    if alias:
                        select_parts.append(f"{agg}({field}) AS {alias}")
                    else:
                        select_parts.append(f"{agg}({field})")
                else:
                    # 回退
                    select_parts.append(f"{metric_agg}({metric_field})")
            else:
                select_parts.append(f"{metric_agg}({metric_field})")

        # 如果没有选择任何列，添加占位符
        if not select_parts:
            select_parts.append("1 AS placeholder")

        return f"SELECT {', '.join(select_parts)}"

    def _build_where(self, mql: MQLSchema) -> str:
        """构建 WHERE 子句"""
        where_parts = []

        # 时间条件
        if mql.time:
            if mql.time.type in (TimeType.DATE_RANGE, TimeType.ABSOLUTE_MONTH, TimeType.ABSOLUTE_QUARTER, TimeType.ABSOLUTE_YEAR):
                # date_range、absolute_month、absolute_quarter、absolute_year 都使用 start/end
                if mql.time.start:
                    where_parts.append(f"FDATE >= '{mql.time.start}'")
                if mql.time.end:
                    where_parts.append(f"FDATE <= '{mql.time.end}'")
            elif mql.time.type == TimeType.RELATIVE:
                # 优先使用已计算的 start/end（来自 MQL generator 的 TimeParser.parse）
                # 避免重新解析导致日期被 datetime.now() 覆盖
                if mql.time.start and mql.time.end:
                    where_parts.append(f"FDATE >= '{mql.time.start}'")
                    where_parts.append(f"FDATE <= '{mql.time.end}'")
                elif mql.time.original:
                    # 只有在没有 start/end 时才重新解析
                    date_range = self._parse_relative_time(mql.time.original, mql)
                    where_parts.append(date_range)

        # 筛选条件
        for filter_obj in mql.filters:
            if filter_obj.field and filter_obj.value is not None:
                op = filter_obj.operator.value if hasattr(filter_obj.operator, 'value') else filter_obj.operator
                # 验证字段名，防止注入
                safe_field = self._validate_field_name(filter_obj.field)
                if op == "eq":
                    where_parts.append(f"{safe_field} = '{self._sanitize_value(filter_obj.value)}'")
                elif op == "gt":
                    where_parts.append(f"{safe_field} > '{self._sanitize_value(filter_obj.value)}'")
                elif op == "lt":
                    where_parts.append(f"{safe_field} < '{self._sanitize_value(filter_obj.value)}'")
                elif op == "in":
                    values = filter_obj.value if isinstance(filter_obj.value, list) else [filter_obj.value]
                    safe_values = "', '".join([self._sanitize_value(v) for v in values])
                    where_parts.append(f"{safe_field} IN ('{safe_values}')")
                elif op == "between":
                    if isinstance(filter_obj.value, list) and len(filter_obj.value) == 2:
                        where_parts.append(f"{safe_field} BETWEEN '{self._sanitize_value(filter_obj.value[0])}' AND '{self._sanitize_value(filter_obj.value[1])}'")

        # 维度过滤
        for dim in mql.dimensions:
            if dim.value:
                # 优先使用 column，如果为空则从类型映射获取
                col = dim.column
                if not col:
                    col = self._get_dimension_column(dim.type)
                if col:
                    # 验证列名（col 来自 DIMENSION_COLUMN_MAP，应该是安全的）
                    safe_col = self._validate_field_name(col)
                    where_parts.append(f"{safe_col} = '{self._sanitize_value(dim.value)}'")

        if where_parts:
            return "WHERE " + " AND ".join(where_parts)
        return ""

    def _parse_relative_time(self, original: str, mql=None) -> str:
        """解析相对时间表达式，同时设置 mql.time.start/end 供前端显示"""
        import re
        from datetime import datetime, timedelta
        from calendar import monthrange

        logger.info(f"[_parse_relative_time] 收到时间表达式: '{original}'")

        today = datetime.now()

        # 用于设置 mql.time.start/end
        computed_start = None
        computed_end = None

        def set_date_range(start_date, end_date):
            """设置 mql.time.start/end（如果提供了 mql）"""
            nonlocal computed_start, computed_end
            computed_start = start_date.strftime("%Y-%m-%d") if isinstance(start_date, datetime) else str(start_date)
            computed_end = end_date.strftime("%Y-%m-%d") if isinstance(end_date, datetime) else str(end_date)
            logger.info(f"[set_date_range] Setting time: start={computed_start}, end={computed_end}, mql has time: {mql and hasattr(mql, 'time')}")
            if mql and hasattr(mql, 'time'):
                mql.time.start = computed_start
                mql.time.end = computed_end
                logger.info(f"[set_date_range] After setting, mql.time.start={mql.time.start}, mql.time.end={mql.time.end}")

        def get_date_range_sql(start_date, end_date):
            """返回 SQL 字符串并设置 computed_start/end"""
            set_date_range(start_date, end_date)
            return f"{self.COL_DATE} >= '{computed_start}' AND {self.COL_DATE} <= '{computed_end}'"

        # ===== 辅助函数 =====
        def get_month_start(year, month):
            return datetime(year, month, 1)

        def get_month_end(year, month):
            _, last_day = monthrange(year, month)
            return datetime(year, month, last_day)

        def get_quarter_start(year, quarter):
            month = (quarter - 1) * 3 + 1
            return datetime(year, month, 1)

        def get_quarter_end(year, quarter):
            month = quarter * 3
            _, last_day = monthrange(year, month)
            return datetime(year, month, last_day)

        # ===== 本周/上周/下周的基准计算 =====
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        this_sunday = this_monday + timedelta(days=6)

        # ===== 今日/昨天/明天系列 =====
        # 今日/今天
        if "今日" in original or "今天" in original:
            return get_date_range_sql(today, today)

        # 昨日/昨天
        if "昨日" in original or "昨天" in original:
            yesterday = today - timedelta(days=1)
            return get_date_range_sql(yesterday, yesterday)

        # 前日/前天
        if "前日" in original or "前天" in original:
            day_before_yesterday = today - timedelta(days=2)
            return get_date_range_sql(day_before_yesterday, day_before_yesterday)

        # 大前日/大前天
        if "大前日" in original or "大前天" in original:
            day = today - timedelta(days=3)
            return get_date_range_sql(day, day)

        # 明日/明天
        if "明日" in original or "明天" in original:
            tomorrow = today + timedelta(days=1)
            return get_date_range_sql(tomorrow, tomorrow)

        # 后日/后天
        if "后日" in original or "后天" in original:
            day = today + timedelta(days=2)
            return get_date_range_sql(day, day)

        # 大后日/大后天
        if "大后日" in original or "大后天" in original:
            day = today + timedelta(days=3)
            return get_date_range_sql(day, day)

        # ===== 近N天 =====
        # 近一年 -> 近12个月（提前转换）
        if "近一年" in original:
            original = original.replace("近一年", "近12个月")
        # 近半年 -> 近6个月
        if "近半年" in original:
            original = original.replace("近半年", "近6个月")
        # 半年（不是"近半年"）-> 近6个月
        elif "半年" in original:
            original = original.replace("半年", "近6个月")

        match = re.search(r'近(\d+)天', original)
        if match:
            days = int(match.group(1))
            start = today - timedelta(days=days-1)
            return get_date_range_sql(start, today)

        # ===== 近N个月 =====
        match = re.search(r'近(\d+)个月', original)
        if match:
            months = int(match.group(1))
            # 计算开始月份：往回推 N-1 个月（因为包含本月）
            target_month = today.month - months + 1
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            start = get_month_start(target_year, target_month)
            return get_date_range_sql(start, today)

        # ===== 本周/上周/下周 =====
        # 本周
        if "本周" in original or "本周初" in original:
            return get_date_range_sql(this_monday, today)

        # 上周
        if "上周" in original:
            last_monday = this_monday - timedelta(days=7)
            last_sunday = last_monday + timedelta(days=6)
            return get_date_range_sql(last_monday, last_sunday)

        # 上上周（上上周 = 上周的上周）
        if "上上周" in original:
            last_monday = this_monday - timedelta(days=14)
            last_sunday = last_monday + timedelta(days=6)
            return get_date_range_sql(last_monday, last_sunday)

        # 下周
        if "下周" in original:
            next_monday = this_monday + timedelta(days=7)
            next_sunday = next_monday + timedelta(days=6)
            return get_date_range_sql(next_monday, next_sunday)

        # 下下周（下下周 = 下周的下周）
        if "下下周" in original:
            next_monday = this_monday + timedelta(days=14)
            next_sunday = next_monday + timedelta(days=6)
            return get_date_range_sql(next_monday, next_sunday)

        # 周末
        if "周末" in original:
            # 本周末（如果今天已经是周末则返回今天，否则返回本周日）
            return get_date_range_sql(this_sunday, this_sunday)

        # ===== 本月/上月/下月 =====
        # 本月
        if "本月" in original:
            return get_date_range_sql(get_month_start(today.year, today.month), today)

        # 上上个月（必须优先于"上月"检查，避免"上上个月"被误判为"上月"）
        if "上上个月" in original or "上上月" in original:
            # 上上月 = 上上个月 = 上月的上个月 = 上月再往前一个月
            if today.month <= 2:
                month = 12 + today.month - 2
                year = today.year - 1
            else:
                month = today.month - 2
                year = today.year
            start = get_month_start(year, month)
            end = get_month_end(year, month)
            return get_date_range_sql(start, end)

        # 上月
        if "上月" in original:
            if today.month == 1:
                start = get_month_start(today.year - 1, 12)
                end = get_month_end(today.year - 1, 12)
            else:
                start = get_month_start(today.year, today.month - 1)
                end = get_month_end(today.year, today.month - 1)
            return get_date_range_sql(start, end)

        # 下月
        if "下月" in original:
            if today.month == 12:
                start = get_month_start(today.year + 1, 1)
                end = get_month_end(today.year + 1, 1)
            else:
                start = get_month_start(today.year, today.month + 1)
                end = get_month_end(today.year, today.month + 1)
            return get_date_range_sql(start, end)

        # 下下月
        if "下下月" in original:
            if today.month == 11:
                start = get_month_start(today.year + 1, 1)
                end = get_month_end(today.year + 1, 2)
            elif today.month == 12:
                start = get_month_start(today.year + 1, 2)
                end = get_month_end(today.year + 1, 3)
            else:
                start = get_month_start(today.year, today.month + 2)
                end = get_month_end(today.year, today.month + 2)
            return get_date_range_sql(start, end)

        # 月初/月中/月末（相对于本月）
        if "月初" in original:
            start = get_month_start(today.year, today.month)
            return get_date_range_sql(start, today)
        if "月中" in original:
            # 每月15日
            day = min(15, today.day)
            start = datetime(today.year, today.month, day)
            return get_date_range_sql(start, today)
        if "月末" in original or "月末" in original:
            end = get_month_end(today.year, today.month)
            return get_date_range_sql(today.replace(day=1), end)

        # ===== 本季度/上季度/下季度 =====
        current_quarter = (today.month - 1) // 3 + 1

        # 本季度
        if "本季度" in original or "本季" in original:
            start = get_quarter_start(today.year, current_quarter)
            return get_date_range_sql(start, today)

        # 上季度
        if "上季度" in original:
            if current_quarter == 1:
                start = get_quarter_start(today.year - 1, 4)
                end = get_quarter_end(today.year - 1, 4)
            else:
                start = get_quarter_start(today.year, current_quarter - 1)
                end = get_quarter_end(today.year, current_quarter - 1)
            return get_date_range_sql(start, end)

        # 下季度
        if "下季度" in original:
            if current_quarter == 4:
                start = get_quarter_start(today.year + 1, 1)
                end = get_quarter_end(today.year + 1, 1)
            else:
                start = get_quarter_start(today.year, current_quarter + 1)
                end = get_quarter_end(today.year, current_quarter + 1)
            return get_date_range_sql(start, end)

        # 季初/季末
        if "季初" in original:
            start = get_quarter_start(today.year, current_quarter)
            return get_date_range_sql(start, today)
        if "季末" in original:
            end = get_quarter_end(today.year, current_quarter)
            start = get_quarter_start(today.year, current_quarter)
            return get_date_range_sql(start, end)

        # ===== Q1/Q2/Q3/Q4、1季度~4季度 =====
        # Q1-Q4 格式
        quarter_map = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
        for q_name, q_num in quarter_map.items():
            if q_name in original:
                start = get_quarter_start(today.year, q_num)
                end = get_quarter_end(today.year, q_num)
                return get_date_range_sql(start, end)

        # 1季度-4季度 格式
        match = re.search(r'(\d)季度', original)
        if match:
            q_num = int(match.group(1))
            if 1 <= q_num <= 4:
                start = get_quarter_start(today.year, q_num)
                end = get_quarter_end(today.year, q_num)
                return get_date_range_sql(start, end)

        # ===== 本年/去年/明年 =====
        # 本年/今年
        if "本年" in original or "今年" in original:
            start = get_month_start(today.year, 1)
            return get_date_range_sql(start, today)

        # 去年/上年
        if "去年" in original or "上年" in original:
            start = get_month_start(today.year - 1, 1)
            end = get_month_end(today.year - 1, 12)
            return get_date_range_sql(start, end)

        # 明年
        if "明年" in original:
            start = get_month_start(today.year + 1, 1)
            end = get_month_end(today.year + 1, 12)
            return get_date_range_sql(start, end)

        # 前年
        if "前年" in original:
            start = get_month_start(today.year - 2, 1)
            end = get_month_end(today.year - 2, 12)
            return get_date_range_sql(start, end)

        # 后年
        if "后年" in original:
            start = get_month_start(today.year + 2, 1)
            end = get_month_end(today.year + 2, 12)
            return get_date_range_sql(start, end)

        # 年初
        if "年初" in original:
            start = get_month_start(today.year, 1)
            return get_date_range_sql(start, today)

        # 年末/年终
        if "年末" in original or "年终" in original:
            end = get_month_end(today.year, 12)
            return get_date_range_sql(today.replace(month=1, day=1), end)

        # ===== 上半年/下半年 =====
        if "上半年" in original:
            start = get_month_start(today.year, 1)
            end = get_month_end(today.year, 6)
            return get_date_range_sql(start, end)

        if "下半年" in original:
            start = get_month_start(today.year, 7)
            end = get_month_end(today.year, 12)
            return get_date_range_sql(start, end)

        # 去年同期上半年/下半年（去年）
        if "去年同期上半年" in original:
            start = get_month_start(today.year - 1, 1)
            end = get_month_end(today.year - 1, 6)
            return get_date_range_sql(start, end)

        if "去年同期下半年" in original:
            start = get_month_start(today.year - 1, 7)
            end = get_month_end(today.year - 1, 12)
            return get_date_range_sql(start, end)

        # ===== 具体年份 2023年/2024年等 =====
        match = re.search(r'(\d{4})年', original)
        if match:
            year = int(match.group(1))
            start = get_month_start(year, 1)
            end = get_month_end(year, 12)
            return get_date_range_sql(start, end)

        # ===== 同比/环比/同期/去年同期 =====
        # 这些是计算模式，不是简单的时间范围
        # 在 MQL 层处理，这里不转换

        # ===== 默认：本月 =====
        start = get_month_start(today.year, today.month)
        return get_date_range_sql(start, today)

    def _build_group_by(self, mql: MQLSchema) -> str:
        """构建 GROUP BY 子句"""
        group_by_parts = []

        # 添加维度列
        for dim in mql.dimensions:
            # 优先使用 column，如果为空则从类型映射获取
            if dim.column:
                group_by_parts.append(dim.column)
            else:
                col = self._get_dimension_column(dim.type)
                if col:
                    group_by_parts.append(col)

        # 如果有时间过滤且是月粒度查询，确保 MONTH(FDATE) 加入 GROUP BY
        if mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            if self.COL_MONTHS not in group_by_parts:
                group_by_parts.append("MONTH(FDATE)")

        if group_by_parts:
            return "GROUP BY " + ", ".join(group_by_parts)
        return ""

    def _build_order_by(self, mql: MQLSchema) -> str:
        """构建 ORDER BY 子句"""
        # 如果显式指定了排序字段和方向，使用它
        if mql.order_by and mql.order_by.field:
            return f"ORDER BY {mql.order_by.field} {mql.order_by.direction}"

        # 排名查询必须有 ORDER BY（即使没有维度）
        is_ranking = mql.intent and "ranking" in mql.intent.value.lower()

        # ========== 占比模式：按占比别名排序 ==========
        has_percentage = any(
            (p.value if isinstance(p, Enum) else p) == CalculationPattern.PERCENTAGE.value
            for p in mql.calculation_patterns
        )
        if has_percentage and mql.molecule_metric and mql.denominator_metric:
            # 构建占比别名
            mol = mql.molecule_metric
            den = mql.denominator_metric
            if mol.name and den.name:
                ratio_name = f"{mol.name}占{den.name}比重"
            elif mol.name:
                ratio_name = f"{mol.name}占比"
            else:
                ratio_name = "占比"
            logger.info(f"[_build_order_by] 占比模式，按占比别名排序: {ratio_name}")
            return f"ORDER BY {ratio_name} DESC"
        # ===========================================

        # 默认按指标降序（有 GROUP BY 时必须用聚合函数）
        if mql.metric and (mql.dimensions or is_ranking):
            direction = "DESC"
            if mql.order_by and mql.order_by.direction:
                direction = mql.order_by.direction

            metric_alias = "ORDERED_PRODUCTSALES"
            actual_field = None
            if mql.metric.starrocks_sql:
                starrocks_sql = mql.metric.starrocks_sql.strip()
                # 提取别名
                match = re.search(r'AS\s+([\w\u4e00-\u9fff]+)', starrocks_sql, re.IGNORECASE)
                if match:
                    raw_alias = match.group(1)
                    # 安全验证：拒绝包含 SQL 关键字或括号等危险字符的别名
                    # 这些说明正则匹配到了错误的内容（如 SELECT ... AS SUM(...) FROM）
                    if not any(kw in raw_alias.upper() for kw in ['SUM', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'SELECT', '(', ')', '/', '*', '-', '+', '=']):
                        metric_alias = raw_alias
                    else:
                        logger.warning(f"[_build_order_by] 别名 \"{raw_alias}\" 包含危险字符，使用默认值")
                        metric_alias = "ORDERED_PRODUCTSALES"

                # 如果 starrocks_sql 包含复合表达式（包含 /, *, -, IFNULL, ISNULL, COALESCE 等），
                # 则 SELECT 使用完整表达式 AS alias，ORDER BY 也应使用该别名而非提取单列
                # 关键模式：")-IFNULL(" 或 ")-" 表示两个表达式相减 → 用别名排序
                if any(kw in starrocks_sql.upper() for kw in self.COMPOUND_KEYWORDS[:3]):
                    # 排除简单的 IFNULL/ISNULL 单列聚合（如 SUM(IFNULL(col,0))），只对复合表达式用别名
                    simple_isnull = re.search(r'(?:SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(?:IFNULL|ISNULL)\s*\(\s*\w+\s*,', starrocks_sql, re.IGNORECASE)
                    # 排除简单的 ISNULL 单列聚合（如 SUM(ISNULL(col,0))），只对复合表达式用别名
                    simple_isnull = re.search(r'(?:SUM|AVG|COUNT|MAX|MIN)\s*\(\s*ISNULL\s*\(\s*\w+\s*,', starrocks_sql, re.IGNORECASE)
                    if not simple_isnull:
                        logger.info(f"[_build_order_by] 复合指标使用别名排序: {metric_alias}")
                        return f"ORDER BY {metric_alias} {direction}"

                # 尝试提取实际字段用于 ORDER BY
                # 1. IFNULL/ISNULL 内的实际字段名（只匹配简单 IFNULL(col, 0)，复合表达式不用这个路径）
                isnull_match = re.search(r'(IFNULL|ISNULL)\s*\(\s*([\w]+)\s*,', starrocks_sql, re.IGNORECASE)
                if isnull_match:
                    actual_field = isnull_match.group(2)  # 提取 IFNULL( 后面的字段名
                    logger.info(f"[_build_order_by] IFNULL/ISNULL指标，提取字段排序: {actual_field}")
                    return f"ORDER BY SUM({actual_field}) {direction}"

                # 2. 简单的 SUM(col) AS alias - 提取聚合函数内的实际列名
                # 用于 ORDER BY，因为别名在 ORDER BY 中不可用
                agg_match = re.search(r'(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*([\w]+)\s*\)', starrocks_sql, re.IGNORECASE)
                if agg_match:
                    actual_field = agg_match.group(2)  # 如 PAGEVIEWS_TOTAL
                    logger.info(f"[_build_order_by] 提取聚合列用于排序: {actual_field}")
                    return f"ORDER BY SUM({actual_field}) {direction}"

                # 如果提取不到实际字段，回退到直接用别名排序
                logger.info(f"[_build_order_by] 无法提取聚合列，用别名排序: {metric_alias}")
                return f"ORDER BY {metric_alias} {direction}"

            # 有 GROUP BY 时，ORDER BY 必须用聚合函数
            return f"ORDER BY SUM({metric_alias}) {direction}"

        # 时间维度查询按时间排序（近7天、近12个月等）
        if mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            # 按时间升序（从早到晚）
            return "ORDER BY MONTH(FDATE) ASC"

        return ""

    def _build_limit(self, mql: MQLSchema) -> str:
        """构建 LIMIT 子句"""
        if mql.top_n > 0:
            return f"LIMIT {mql.top_n}"
        elif mql.pagination and mql.pagination.page_size:
            return f"LIMIT {mql.pagination.page_size}"
        elif mql.intent and "ranking" in mql.intent.value:
            # 排名查询默认 10 条
            return "LIMIT 10"
        return ""
