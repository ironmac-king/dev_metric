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
from ..schema import MQLSchema, MQLMetric, MQLDimension, TimeRange, TimeType, SQLResult, CalculationPattern, CrossMetricSpec, MQLIntent
from .field_extractor import FieldExtractor

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
        # 使用 MQLSchema 的 has_mom/has_yoy 属性统一判断
        if mql.has_mom or mql.has_yoy:
            logger.info(f"[_build_sql] 进入 YoY/MoM 模式: has_mom={mql.has_mom}, has_yoy={mql.has_yoy}")
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
        # 重要：如果没有 GROUP BY（只有聚合列），必须加 LIMIT 防止返回大量数据
        limit_clause = self._build_limit(mql)
        if not limit_clause and not group_by_clause:
            # 没有 GROUP BY 时，默认加 LIMIT 10 防止返回过多数据
            limit_clause = "LIMIT 10"
            logger.info(f"[_build_sql] 无 GROUP BY，自动添加 LIMIT 10")

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

        # 3.5 检测是否为复合指标（ratio），如果是则不加 GROUP BY（避免嵌套聚合）
        is_compound_a = 'CASE' in metric_a_sql.upper() and ('/' in metric_a_sql.upper())

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
        is_compound_b = 'CASE' in metric_b_sql.upper() and ('/' in metric_b_sql.upper())

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
        # 如果是复合指标（已含聚合），CTE 不需要 GROUP BY；否则需要
        group_a = "" if is_compound_a else f"GROUP BY {dim_group}"
        group_b = "" if is_compound_b else f"GROUP BY {dim_group}"
        sql = f"""
WITH metric_a AS (
    SELECT {dim_select}, {metric_a_sql} AS {metric_a_alias}
    FROM {self.DEFAULT_TABLE}
    WHERE {where_in_cte}
    {group_a}
),
metric_b AS (
    SELECT {dim_select}, {metric_b_sql} AS {metric_b_alias}
    FROM {self.DEFAULT_TABLE}
    WHERE {where_in_cte}
    {group_b}
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

    @staticmethod
    def _deduplicate_dimensions(dimensions: list) -> list:
        """去除 dimensions 中 (type, value) 相同的重复项"""
        seen: set = set()
        result = []
        for dim in dimensions:
            key = (dim.type, dim.value)
            if key not in seen:
                seen.add(key)
                result.append(dim)
        return result

    def _build_comparison_period_where(self, start: str, end: str, mql: MQLSchema) -> str:
        """构建对比周期 WHERE 条件（时间 + mql.filters + mql.dimensions 过滤）"""
        if not start or not end:
            return ""
        filter_parts = []
        for f in mql.filters:
            if f.field and f.value is not None:
                op = f.operator.value if hasattr(f.operator, 'value') else f.operator
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
        dim_filter_parts = []
        for dim in mql.dimensions:
            if dim.value:
                col = dim.column or self._get_dimension_column(dim.type)
                if col:
                    safe_col = self._validate_field_name(col)
                    dim_filter_parts.append(f"{safe_col} = '{self._sanitize_value(dim.value)}'")
        time_cond = f"(FDATE >= '{start}' AND FDATE <= '{end}')"
        all_parts = filter_parts + dim_filter_parts
        if all_parts:
            return f"({time_cond} AND {' AND '.join(all_parts)})"
        return time_cond

    def _build_mom_sql(self, mql: MQLSchema) -> str:
        """构建 MoM/YOY 对比 SQL

        使用条件聚合在一个查询中计算当前周期和对比周期的值。
        """
        logger.info(f"[_build_mom_sql] Building MoM/YOY SQL")

        # 0. 去除 mql.dimensions 中的重复项（相同 type + value 只保留一个）
        mql.dimensions = self._deduplicate_dimensions(mql.dimensions)
        logger.info(f"[_build_mom_sql] 去重后维度: {[(d.type, d.value) for d in mql.dimensions]}")

        # 1. 获取业务维度列（不包括 YEARS, MONTHS）
        # 注意：只有当维度没有具体值时才加入 GROUP BY
        # 如果维度有具体值（如 GROUP_2 = '智能云存储'），已经通过 WHERE 过滤，不需要 GROUP BY
        dim_columns = []
        dim_columns_for_groupby = []  # 用于 GROUP BY 的维度列（即使有值也要加进去）
        for dim in mql.dimensions:
            col = dim.column
            if not col:
                col = self._get_dimension_column(dim.type)
            if col:
                # 无论是否有值，都收集到 dim_columns_for_groupby（用于 GROUP BY）
                dim_columns_for_groupby.append(col)
                # 只有当维度没有具体值时才加入 dim_columns（用于 SELECT 和 GROUP BY）
                if not dim.value:
                    dim_columns.append(col)
                    logger.info(f"[_build_mom_sql] 维度 {col} 无具体值，加入 GROUP BY")
                else:
                    logger.info(f"[_build_mom_sql] 维度 {col} = '{dim.value}' 有具体值，不加入 SELECT/GROUP BY dim_columns")

        # 2. 获取当前周期时间条件
        current_where = self._build_where(mql)
        if current_where.upper().startswith("WHERE"):
            current_where = current_where[5:].strip()
        current_where_sql = f"WHERE {current_where}" if current_where else "WHERE 1=1"

        # 3. 分别获取 MoM 和 YoY 对比周期时间条件
        # 无论时间跨度如何，都同时计算 MoM 和 YoY（用户要求同时返回两者）
        mom_start = ""
        mom_end = ""
        yoy_start = ""
        yoy_end = ""

        # 从 current_where 提取当前周期的 start 和 end
        import re
        start_match = re.search(r"FDATE >= '(\d{4}-\d{2}-\d{2})'", current_where)
        end_match = re.search(r"FDATE <= '(\d{4}-\d{2}-\d{2})'", current_where)
        current_start_dt = None
        current_end_dt = None
        day_count = 0
        if start_match and end_match:
            try:
                from datetime import datetime, timedelta
                current_start_dt = datetime.strptime(start_match.group(1), "%Y-%m-%d")
                current_end_dt = datetime.strptime(end_match.group(1), "%Y-%m-%d")
                day_count = (current_end_dt - current_start_dt).days + 1
            except Exception:
                pass

        # 使用 MQLSchema 的 has_mom/has_yoy 属性判断是否需要环比/同比计算
        # has_mom_compare/has_yoy_compare 是基于是否成功推断出对比周期
        has_mom = mql.has_mom
        has_yoy = mql.has_yoy

        # 如果有 mql.comparison 的指定时间，优先使用
        if mql.comparison:
            if mql.comparison.compare_period_start and mql.comparison.compare_period_end:
                # 用户指定了对比时间，根据 patterns 决定是 MoM 还是 YoY
                if has_mom:
                    mom_start = mql.comparison.compare_period_start
                    mom_end = mql.comparison.compare_period_end
                if has_yoy:
                    yoy_start = mql.comparison.compare_period_start
                    yoy_end = mql.comparison.compare_period_end

        # 如果没有指定对比时间，自动推断
        if current_start_dt and current_end_dt:
            # 推断 MoM（环比上月）：无论时间跨度如何，都计算 MoM
            if has_mom:
                try:
                    from datetime import timedelta
                    import calendar
                    # 环比上月：上月 1 日到对应天数
                    # 例如 4-01~4-21（21天）→ 3-01~3-20
                    prev_month_start = current_start_dt - timedelta(days=1)
                    prev_month_start = prev_month_start.replace(day=1)
                    prev_month_max_day = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
                    prev_end_day = min(day_count, prev_month_max_day)
                    mom_start = prev_month_start.strftime("%Y-%m-%d")
                    mom_end = prev_month_start.replace(day=prev_end_day).strftime("%Y-%m-%d")
                    logger.info(f"[_build_mom_sql] Inferred MoM: current {current_start_dt.date()}~{current_end_dt.date()} ({day_count}天), compare {mom_start} to {mom_end}")
                except Exception as e:
                    logger.warning(f"[_build_mom_sql] 推断 MoM 失败: {e}")

            # 推断 YoY（同比去年同期）：始终计算
            if has_yoy:
                try:
                    prev_year_start = current_start_dt.replace(year=current_start_dt.year - 1)
                    prev_year_end = current_end_dt.replace(year=current_end_dt.year - 1)
                    yoy_start = prev_year_start.strftime("%Y-%m-%d")
                    yoy_end = prev_year_end.strftime("%Y-%m-%d")
                    logger.info(f"[_build_mom_sql] Inferred YoY: current {current_start_dt.date()}~{current_end_dt.date()} ({day_count}天), compare {yoy_start} to {yoy_end}")
                except Exception as e:
                    logger.warning(f"[_build_mom_sql] 推断 YoY 失败: {e}")

        # 4. 获取指标的原始字段表达式（用于条件聚合，不需要外层聚合函数）
        metric_field_sql = self._extract_raw_metric_expression(mql.metric)
        if not metric_field_sql:
            return f"SELECT 'ERROR: 指标无 starrocks_sql' AS error"

        # 4.5 检测是否复合指标（包含除法，需要拆分子分母分别聚合）
        is_compound_metric = '/' in metric_field_sql.upper() and metric_field_sql.strip().upper().startswith('CASE')
        molecule_field = None  # 裸字段（不含 SUM），用于条件聚合内层
        denominator_field = None
        if is_compound_metric:
            starrocks_sql = (mql.metric.starrocks_sql or "") if mql.metric else ""
            if starrocks_sql:
                molecule_expr, denominator_expr = self._extract_compound_parts(starrocks_sql)
                if molecule_expr and denominator_expr:
                    molecule_field = molecule_expr
                    denominator_field = denominator_expr
                    logger.info(f"[_build_mom_sql] 复合指标(CASE WHEN): 分子={molecule_field}, 分母={denominator_field}")
                else:
                    # 解析失败，降级为简单指标（用原始 CASE WHEN 做条件聚合）
                    is_compound_metric = False
                    logger.warning(f"[_build_mom_sql] 复合指标解析失败，降级为简单指标模式")
            if not molecule_field:
                is_compound_metric = False
        else:
            logger.info(f"[_build_mom_sql] 简单指标: metric_field_sql={metric_field_sql}")

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

        # 6. 构建 MoM 和 YoY 对比周期条件
        # 注意：where_mom 和 where_yoy 必须包含与 current_where 相同的 filters 和 dimensions，否则对比基数不一致

        # 构建 MoM 和 YoY 的对比条件
        where_mom = self._build_comparison_period_where(mom_start, mom_end, mql) if mom_start and mom_end else ""
        where_yoy = self._build_comparison_period_where(yoy_start, yoy_end, mql) if yoy_start and yoy_end else ""

        has_mom_compare = bool(where_mom)
        has_yoy_compare = bool(where_yoy)

        # 提取纯时间条件（用于 WHERE）
        import re
        time_pattern = r"(FDATE >= '(\d{4}-\d{2}-\d{2})' AND FDATE <= '(\d{4}-\d{2}-\d{2})')"
        time_match = re.search(time_pattern, current_cond)
        if time_match:
            current_time_only = time_match.group(1)
        else:
            current_time_only = current_cond

        # ========================================================
        # 构建最终 SQL：同时支持 MoM 和 YoY
        # ========================================================

        # 用于 GROUP BY 的列：包括无值的维度列
        dim_select = ", ".join(dim_columns)
        dim_group = dim_select
        has_dim_groupby = bool(dim_columns)

        logger.info(f"[_build_mom_sql] dim_columns={dim_columns}, has_dim_groupby={has_dim_groupby}")

        # ========================================================
        # 构建最终 SQL：统一使用 mql.has_mom/has_yoy 控制输出列
        # has_mom_compare/has_yoy_compare 控制是否有对比周期数据
        # ========================================================

        # 构建当前值表达式（总是需要）
        curr_val = self._build_value_expr(
            current_cond if has_dim_groupby else current_time_only,
            metric_field_sql, is_compound_metric, molecule_field, denominator_field
        )

        # 构建对比周期表达式（仅当有对比周期时）
        mom_val = mom_chg = yoy_val = yoy_chg = None
        if has_mom_compare:
            mom_val = self._build_value_expr(where_mom, metric_field_sql, is_compound_metric, molecule_field, denominator_field)
            mom_chg = self._build_change_expr(
                current_cond if has_dim_groupby else current_time_only,
                where_mom, metric_field_sql, is_compound_metric, molecule_field, denominator_field
            )
        if has_yoy_compare:
            yoy_val = self._build_value_expr(where_yoy, metric_field_sql, is_compound_metric, molecule_field, denominator_field)
            yoy_chg = self._build_change_expr(
                current_cond if has_dim_groupby else current_time_only,
                where_yoy, metric_field_sql, is_compound_metric, molecule_field, denominator_field
            )

        # 构建 SELECT 列（根据是否请求了环比/同比决定输出哪些列）
        select_parts = []
        if has_dim_groupby:
            select_parts.append(dim_select)
        select_parts.append(f"{curr_val} AS \"当前值\"")
        if has_mom:
            if mom_val:
                select_parts.append(f"{mom_val} AS \"环比值\"")
                select_parts.append(f"{mom_chg} AS \"环比变化\"")
            else:
                select_parts.append("NULL AS \"环比值\"")
                select_parts.append("NULL AS \"环比变化\"")
        if has_yoy:
            if yoy_val:
                select_parts.append(f"{yoy_val} AS \"同比值\"")
                select_parts.append(f"{yoy_chg} AS \"同比变化\"")
            else:
                select_parts.append("NULL AS \"同比值\"")
                select_parts.append("NULL AS \"同比变化\"")
        select_clause = ",\n       ".join(select_parts)

        # 构建 WHERE 子句
        where_parts = [f"( {current_cond} )"]
        if has_mom_compare:
            where_parts.append(f"( {where_mom} )")
        if has_yoy_compare:
            where_parts.append(f"( {where_yoy} )")
        where_clause = "\n   OR ".join(where_parts)

        # 构建最终 SQL
        sql_parts = [f"SELECT {select_clause}", f"FROM {self.DEFAULT_TABLE}", f"WHERE {where_clause}"]
        if has_dim_groupby:
            sql_parts.append(f"GROUP BY {dim_group}")
            sql_parts.append(f"ORDER BY {dim_group}")
            sql_parts.append("LIMIT 20")

        sql = "\n".join(sql_parts)

        logger.info(f"[_build_mom_sql] SQL: {sql[:300]}")
        return sql

    @staticmethod
    def _extract_compound_parts(starrocks_sql: str) -> tuple:
        """
        从 CASE WHEN 复合指标 SQL 提取分子和分母表达式（不含聚合函数包装）

        CASE WHEN 格式：
            SELECT CASE WHEN SUM(...) = 0 THEN 0
            ELSE (分子算术表达式) / SUM(分母字段) END AS alias FROM ...

        例如：
            分子：SUM(IFNULL(ORDERED_PRODUCTSALES, 0)) - SUM(IFNULL(COSTFEESS, 0))
            分母：SUM(IFNULL(ORDERED_PRODUCTSALES, 0))

        Returns:
            tuple: (molecule_field, denominator_field) 不含外层 SUM()
            例如: ("SUM(IFNULL(ORDERED_PRODUCTSALES, 0)) - SUM(IFNULL(COSTFEESS, 0))",
                   "SUM(IFNULL(ORDERED_PRODUCTSALES, 0))")
            如果解析失败返回 (None, None)
        """
        if not starrocks_sql:
            return None, None

        import re

        # 直接用正则匹配 "ELSE (分子算术) / SUM(分母)" 模式
        # 分子可能包含嵌套括号，用 lazy quantifier 匹配
        # 结构: ELSE (arith) / SUM(col) END
        import re

        # 匹配 ELSE (分子) / SUM(分母内容) 的模式
        # 非贪婪匹配 (.+?) 会在第一个 ) / SUM( 处停止，正好是外层 ELSE 的闭合
        m = re.search(
            r'ELSE\s*\((.+?)\)\s*/\s*(SUM|AVG|COUNT|MAX|MIN)\s*\(([^)]+)\)\s*END',
            starrocks_sql, re.IGNORECASE | re.DOTALL
        )
        if not m:
            return None, None

        raw_molecule = m.group(1)  # "(SUM(IFNULL(ORD...)) - SUM(IFNULL(COSTFEESS, 0)))"
        func_name = m.group(2).upper()
        denom_inner = m.group(3)  # "IFNULL(ORDERED_PRODUCTSALES, 0)"

        # 去掉分子最外层括号（分子算术表达式被包在括号里）
        # 例如: "(SUM(a) - SUM(b))" -> "SUM(a) - SUM(b)"
        molecule_clean = raw_molecule
        if raw_molecule.startswith('(') and raw_molecule.endswith(')'):
            # 验证括号是否配对
            depth = 0
            for ch in raw_molecule[1:-1]:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth < 0:
                        break
            if depth == 0:
                molecule_clean = raw_molecule[1:-1]

        # 去掉分子和分母中的 SUM/AVG/COUNT/MAX/MIN 包装（用于条件聚合，外层 SUM 会做聚合）
        def strip_aggregates(text: str) -> str:
            """去掉所有 SUM/AVG/COUNT/MAX/MIN 包装"""
            pattern = r'(SUM|AVG|COUNT|MAX|MIN)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)'
            while True:
                new_text = re.sub(pattern, r'\2', text, flags=re.IGNORECASE)
                if new_text == text:
                    break
                text = new_text
            return text

        molecule_clean = strip_aggregates(molecule_clean)
        denominator_full = strip_aggregates(f"{func_name}({denom_inner})")

        logger.info(f"[_extract_compound_parts] molecule={molecule_clean}, denominator={denominator_full}")
        return molecule_clean, denominator_full

    def _build_value_expr(self, cond: str, metric_field_sql: str,
                          is_compound: bool, molecule_field: str = None, denominator_field: str = None) -> str:
        """构建值表达式（兼容简单指标和复合指标）

        简单指标：SUM(CASE WHEN cond THEN metric_field_sql ELSE 0 END)
        复合指标：CASE WHEN SUM(...分子...) = 0 THEN 0 ELSE SUM(...分子...) / NULLIF(SUM(...分母...), 0) END
        """
        if is_compound and molecule_field and denominator_field:
            return (
                f"CASE WHEN SUM(CASE WHEN {cond} THEN {molecule_field} ELSE 0 END) = 0 THEN 0 "
                f"ELSE ROUND(SUM(CASE WHEN {cond} THEN {molecule_field} ELSE 0 END) / "
                f"NULLIF(SUM(CASE WHEN {cond} THEN {denominator_field} ELSE 0 END), 0), 4) END"
            )
        else:
            return f"SUM(CASE WHEN {cond} THEN {metric_field_sql} ELSE 0 END)"

    def _build_change_expr(self, current_cond: str, compare_cond: str,
                           metric_field_sql: str, is_compound: bool,
                           molecule_field: str = None, denominator_field: str = None) -> str:
        """构建变化率表达式

        简单指标：(当前值 - 对比值) / 对比值 * 100
        复合指标：(当前率 - 对比率) / 对比率 * 100
        """
        if is_compound and molecule_field and denominator_field:
            # 分子分母分别聚合后外层做除法
            curr_num = f"SUM(CASE WHEN {current_cond} THEN {molecule_field} ELSE 0 END)"
            curr_den = f"NULLIF(SUM(CASE WHEN {current_cond} THEN {denominator_field} ELSE 0 END), 0)"
            comp_num = f"SUM(CASE WHEN {compare_cond} THEN {molecule_field} ELSE 0 END)"
            comp_den = f"NULLIF(SUM(CASE WHEN {compare_cond} THEN {denominator_field} ELSE 0 END), 0)"
            return (
                f"CASE WHEN {comp_den} IS NULL OR {comp_den} = 0 THEN NULL "
                f"ELSE ROUND((({curr_num} / {curr_den}) - ({comp_num} / {comp_den})) / ({comp_num} / {comp_den}) * 100, 2) END"
            )
        else:
            curr = f"SUM(CASE WHEN {current_cond} THEN {metric_field_sql} ELSE 0 END)"
            comp = f"SUM(CASE WHEN {compare_cond} THEN {metric_field_sql} ELSE 0 END)"
            return (
                f"CASE WHEN {comp} > 0 "
                f"THEN ROUND(({curr} - {comp}) / {comp} * 100, 2) "
                f"ELSE NULL END"
            )

    def _extract_raw_metric_expression(self, metric: MQLMetric) -> str:
        """从 metric 的 starrocks_sql 提取原始字段表达式（不含聚合函数）

        用于条件聚合（CASE WHEN 内部），因为外层 SUM 会做聚合。

        Returns:
            str: 原始字段表达式，如 "IFNULL(a,0)-IFNULL(b,0)"
        """
        if not metric:
            return "ORDERED_PRODUCTSALES"

        expr = metric.starrocks_sql or ""
        import re
        # 提取 SELECT 和 FROM 之间的表达式
        match = re.search(r'SELECT\s+(.+?)\s+FROM', expr, re.IGNORECASE | re.DOTALL)
        if not match:
            return FieldExtractor(metric).extract_raw()

        full_expr = match.group(1).strip()

        # 去掉 AS alias 别名部分（保留括号内的表达式）
        # 例如 "(SUM(a) - SUM(b)) AS xxx" -> "(SUM(a) - SUM(b))"
        full_expr = re.sub(r'\s+AS\s+[\w"]+\s*$', '', full_expr, flags=re.IGNORECASE)

        def strip_aggregates(text: str) -> str:
            """去掉所有 SUM/AVG/COUNT/MAX/MIN 包装，保留括号内的内容"""
            pattern = r'(SUM|AVG|COUNT|MAX|MIN)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)'
            while True:
                new_text = re.sub(pattern, r'\2', text, flags=re.IGNORECASE)
                if new_text == text:
                    break
                text = new_text
            return text

        # 去掉外层括号（如果整个表达式被包在括号里）
        result = full_expr
        while result.startswith('(') and result.endswith(')'):
            # 验证括号是否配对
            depth = 0
            for ch in result[1:-1]:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth < 0:
                        break
            if depth == 0:
                result = result[1:-1]
            else:
                break

        stripped = strip_aggregates(result)
        logger.info(f"[_extract_raw_metric_expression] {full_expr} -> {stripped}")
        return stripped

    def _extract_metric_expression(self, metric: MQLMetric, prefix: str) -> tuple:
        """从 metric 的 starrocks_sql 提取聚合表达式和别名

        Returns:
            (expression: str, alias: str)
            expression: 直接可用于 SELECT 的聚合表达式，如 "SUM(TOTALORDERS)"
            alias: SQL 别名，如 "metric_a"
        """
        if not metric:
            field = "ORDERED_PRODUCTSALES"
            return f"SUM({field})", prefix

        extractor = FieldExtractor(metric)
        expr, alias = extractor.extract_full()

        # 如果提取的别名等于默认字段，用 prefix 覆盖
        if alias == extractor._default_field:
            alias = prefix

        return expr, alias

    def _build_select(self, mql: MQLSchema) -> str:
        """构建 SELECT 子句"""
        logger.info(f"[_build_select] starrocks_sql={mql.metric.starrocks_sql[:80] if mql.metric and mql.metric.starrocks_sql else 'EMPTY'}")
        select_parts = []

        # 添加维度列（去重）
        # 只有维度没有具体值时才加入 SELECT（否则已在 WHERE 过滤）
        seen_dim_cols = set()
        for dim in mql.dimensions:
            col = dim.column if dim.column else self._get_dimension_column(dim.type)
            if col and col not in seen_dim_cols and not dim.value:
                seen_dim_cols.add(col)
                select_parts.append(col)

        # 如果有时间过滤，确保时间列加入 SELECT
        # QUERY_TREND 根据时间范围决定粒度，QUERY_RANKING 不按时间拆分
        if mql.intent == MQLIntent.QUERY_TREND and mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            if mql.time.days <= 31:
                if "FDATE" not in select_parts:
                    select_parts.append("FDATE")
            else:
                if self.COL_MONTHS not in select_parts:
                    select_parts.append(f"MONTH(FDATE) AS MONTHS")
        elif mql.intent != MQLIntent.QUERY_RANKING:
            if mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
                if self.COL_MONTHS not in select_parts:
                    select_parts.append(f"MONTH(FDATE) AS MONTHS")

        # 检查是否有维度分组（GROUP_X 等）- 有维度分组时不需要日期范围字段
        has_dimension_group = any(
            (dim.type and dim.type.startswith('GROUP_')) or dim.type in ('REGION', 'PLATFORM', 'FSITE', 'FCOUNTRY', 'FBRAND', 'FPRODUCTLINE')
            for dim in mql.dimensions
        )

        # 只有在没有维度分组时才添加日期范围（方便前端显示）
        if not has_dimension_group and "FDATE_START" not in " ".join(select_parts):
            # 时间序列查询添加日期范围
            if mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
                if self.COL_MONTHS in " ".join(select_parts):
                    select_parts.append(f"MIN(FDATE) AS FDATE_START")
                    select_parts.append(f"MAX(FDATE) AS FDATE_END")

        # 检查占比模式（percentage）：生成 分子 * 100.0 / 分母 SQL
        has_percentage = any(
            (p.value if isinstance(p, Enum) else p) == CalculationPattern.PERCENTAGE.value
            for p in mql.calculation_patterns
        )
        # 优先使用主指标已有的 starrocks_sql（如果已经包含占比计算）
        if has_percentage and mql.metric and mql.metric.starrocks_sql:
            starrocks_sql = mql.metric.starrocks_sql.strip()
            # 如果 starrocks_sql 已经包含除法（占比计算），需要加 *100 转为百分比
            if '/' in starrocks_sql.upper():
                extractor = FieldExtractor(mql.metric)
                expr, alias = extractor.extract_full()
                # 如果 starrocks_sql 已经有了 *100 或 /100（已经是百分比），不再乘
                sql_upper = starrocks_sql.upper()
                if '* 100' not in sql_upper and '/ 100' not in sql_upper and '*100' not in sql_upper:
                    ratio_expr = f"ABS({expr} * 100.0)"
                    select_parts.append(f"{ratio_expr} AS {alias}")
                    logger.info(f"[_build_select] 占比模式（使用主指标starrocks_sql）: {ratio_expr}")
                else:
                    select_parts.append(f"{expr} AS {alias}")
                    logger.info(f"[_build_select] 占比模式（使用主指标starrocks_sql，已含百分比）: {expr}")
            elif mql.molecule_metric and mql.denominator_metric:
                # starrocks_sql 不包含除法，但有 molecule/denominator 时构造
                mol = mql.molecule_metric
                den = mql.denominator_metric
                mol_sql = mol.starrocks_sql or ""
                den_sql = den.starrocks_sql or ""
                mol_expr = FieldExtractor.extract_molecule(mol_sql) if mol_sql else (mol.field or "REFUND_QTY")
                den_expr = FieldExtractor.extract_denominator(den_sql) if den_sql else (den.field or "ORDERED_PRODUCTSALES")

                def _ensure_sum(expr):
                    stripped = expr.strip().upper()
                    if any(stripped.startswith(agg) for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN(']):
                        return expr
                    return f"SUM({expr})"

                ratio_expr = f"ABS({_ensure_sum(mol_expr)} * 100.0 / {_ensure_sum(den_expr)})"
                if mol.name and den.name:
                    ratio_name = f"{mol.name}占{den.name}比重"
                elif mol.name:
                    ratio_name = f"{mol.name}占比"
                else:
                    ratio_name = "占比"
                select_parts.append(f"{ratio_expr} AS {ratio_name}")
                logger.info(f"[_build_select] 占比模式: {mol_expr} * 100.0 / {den_expr}")
        elif has_percentage and mql.molecule_metric and mql.denominator_metric:
            # 回退：没有主指标 starrocks_sql，用 molecule/denominator 构造
            mol = mql.molecule_metric
            den = mql.denominator_metric
            mol_sql = mol.starrocks_sql or ""
            den_sql = den.starrocks_sql or ""

            mol_expr = FieldExtractor.extract_molecule(mol_sql) if mol_sql else (mol.field or "REFUND_QTY")
            den_expr = FieldExtractor.extract_denominator(den_sql) if den_sql else (den.field or "ORDERED_PRODUCTSALES")

            def _ensure_sum(expr):
                stripped = expr.strip().upper()
                if any(stripped.startswith(agg) for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN(']):
                    return expr
                return f"SUM({expr})"

            ratio_expr = f"ABS({_ensure_sum(mol_expr)} * 100.0 / {_ensure_sum(den_expr)})"

            if mol.name and den.name:
                ratio_name = f"{mol.name}占{den.name}比重"
            elif mol.name:
                ratio_name = f"{mol.name}占比"
            else:
                ratio_name = "占比"

            # ========== 根本修复：占比别名也加双引号支持中文 ==========
            select_parts.append(f"{ratio_expr} AS \"{ratio_name}\"")
            logger.info(f"[_build_select] 占比模式: {mol_expr} * 100.0 / {den_expr} AS \"{ratio_name}\"")
        # 添加指标列
        elif mql.metric:
            # 使用 FieldExtractor 统一解析
            extractor = FieldExtractor(mql.metric)
            expr, alias = extractor.extract_full()
            # ========== 根本修复：直接使用 metric.name 作为中文别名 ==========
            # 避免 starrocks_sql 中没有中文别名导致的列名映射错误
            chinese_name = mql.metric.name if mql.metric.name else alias
            select_parts.append(f"{expr} AS \"{chinese_name}\"")
            logger.info(f"[_build_select] 指标表达式: {expr} AS \"{chinese_name}\"")

        # 多指标支持：处理 mql.metrics 中的额外指标
        # 按 code 去重，避免同一指标的不同名称变体（如"毛利"和"销售毛利"）重复添加
        seen_metric_codes = set()
        if mql.metric and mql.metric.code:
            seen_metric_codes.add(mql.metric.code)
        for i, metric in enumerate(mql.metrics):
            if not metric or not metric.name:
                continue
            # 跳过与主指标同名的项
            if mql.metric and metric.name == mql.metric.name:
                continue
            # 按 code 去重：跳过与已添加指标 code 相同的项
            if metric.code and metric.code in seen_metric_codes:
                logger.info(f"[_build_select] 多指标[{i}] '{metric.name}' code={metric.code} 已存在，跳过")
                continue
            if metric.code:
                seen_metric_codes.add(metric.code)
            logger.info(f"[_build_select] 多指标[{i}]: {metric.name}")

            # 使用 FieldExtractor 统一解析
            extractor = FieldExtractor(metric)
            expr, alias = extractor.extract_full()
            # ========== 根本修复：直接使用 metric.name 作为中文别名 ==========
            chinese_name = metric.name if metric.name else alias
            select_parts.append(f"{expr} AS \"{chinese_name}\"")

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

        # 维度过滤（去重）
        seen_dim_filter = set()
        for dim in mql.dimensions:
            if dim.value:
                # 优先使用 column，如果为空则从类型映射获取
                col = dim.column
                if not col:
                    col = self._get_dimension_column(dim.type)
                if col:
                    # 去重：(col, value) 组合重复则跳过
                    filter_key = (col, dim.value)
                    if filter_key in seen_dim_filter:
                        continue
                    seen_dim_filter.add(filter_key)
                    # 验证列名（col 来自 DIMENSION_COLUMN_MAP，应该是安全的）
                    safe_col = self._validate_field_name(col)
                    where_parts.append(f"{safe_col} = '{self._sanitize_value(dim.value)}'")

        if where_parts:
            return "WHERE " + " AND ".join(where_parts)
        return ""

    def _parse_relative_time(self, original: str, mql=None) -> str:
        """解析相对时间表达式，返回 SQL 时间条件，并同步更新 mql.time.start/end"""
        from ai.engine.time_parser import TimeParser
        from datetime import datetime

        logger.info(f"[_parse_relative_time] 收到时间表达式: '{original}'")

        result = TimeParser().parse(original)
        if result and result.get('start') and result.get('end'):
            start, end = result['start'], result['end']
        else:
            # 无法解析，默认本月
            today = datetime.now()
            start = f"{today.year}-{today.month:02d}-01"
            end = today.strftime("%Y-%m-%d")
            logger.warning(f"[_parse_relative_time] 无法解析 '{original}'，降级为本月: {start}~{end}")

        if mql and hasattr(mql, 'time') and mql.time:
            mql.time.start = start
            mql.time.end = end
            logger.info(f"[_parse_relative_time] 已设置 mql.time: {start}~{end}")

        return f"{self.COL_DATE} >= '{start}' AND {self.COL_DATE} <= '{end}'"

    def _build_group_by(self, mql: MQLSchema) -> str:
        """构建 GROUP BY 子句"""
        group_by_parts = []
        seen_cols = set()  # 去重

        # 添加维度列
        # 只有维度没有具体值时才加入 GROUP BY（否则已在 WHERE 过滤）
        for dim in mql.dimensions:
            # 优先使用 column，如果为空则从类型映射获取
            col = dim.column if dim.column else self._get_dimension_column(dim.type)
            if col and col not in seen_cols and not dim.value:
                seen_cols.add(col)
                group_by_parts.append(col)

        # 如果有时间过滤，确保时间列加入 GROUP BY
        # QUERY_RANKING 不按时间拆分，其他意图根据时间范围决定粒度
        if mql.intent == MQLIntent.QUERY_RANKING:
            # 排名查询：只按维度分组，不按时间拆分
            pass
        elif mql.intent == MQLIntent.QUERY_TREND and mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            # 趋势查询：根据时间范围决定粒度
            # 一个月内按日分组，超过一个月按月分组（避免数据太稀疏或太密集）
            if mql.time.days <= 31:
                if "FDATE" not in group_by_parts:
                    group_by_parts.append("FDATE")
            else:
                if self.COL_MONTHS not in group_by_parts:
                    group_by_parts.append("MONTH(FDATE)")
        elif mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            # 其他意图：按月分组
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
            # 回退：用 molecule/denominator 名称构造
            mol = mql.molecule_metric
            den = mql.denominator_metric
            if mol.name and den.name:
                ratio_name = f"{mol.name}占{den.name}比重"
            elif mol.name:
                ratio_name = f"{mol.name}占比"
            else:
                ratio_name = "占比"
            logger.info(f"[_build_order_by] 占比模式，按占比别名排序: {ratio_name}")
            return f"ORDER BY \"{ratio_name}\" DESC"
        # ===========================================

        # ========== QUERY_TREND 模式：按时间排序 ==========
        if mql.intent == MQLIntent.QUERY_TREND and mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            # 趋势查询按时间升序（从早到晚）
            if mql.time.days <= 31:
                return "ORDER BY FDATE ASC"
            return "ORDER BY MONTHS ASC"
        # ============================================

        # 默认按指标降序（有 GROUP BY 时必须用聚合函数）
        if mql.metric and (mql.dimensions or is_ranking):
            direction = "DESC"
            if mql.order_by and mql.order_by.direction:
                direction = mql.order_by.direction

            # 使用 FieldExtractor 统一解析
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()

            # 复合指标使用中文别名排序（加双引号）
            if parsed.is_compound:
                chinese_name = mql.metric.name if mql.metric.name else parsed.alias
                logger.info(f"[_build_order_by] 复合指标使用中文别名排序: {chinese_name}")
                return f"ORDER BY \"{chinese_name}\" {direction}"
            else:
                # 简单指标：ORDER BY 必须用聚合函数，使用裸字段
                bare_field = parsed.bare_field or "ORDERED_PRODUCTSALES"
                logger.info(f"[_build_order_by] 简单指标使用聚合排序: SUM({bare_field})")
                return f"ORDER BY SUM({bare_field}) {direction}"

        # 时间维度查询按时间排序（近7天、近12个月等）
        if mql.time and mql.time.type in (TimeType.ABSOLUTE_MONTH, TimeType.RELATIVE, TimeType.DATE_RANGE):
            # 趋势查询始终按时间升序排序（从早到晚）
            if mql.intent == MQLIntent.QUERY_TREND:
                # 按FDATE分组时用FDATE排序，按MONTH分组时用MONTH排序
                if mql.time.days <= 31:
                    return "ORDER BY FDATE ASC"
                return "ORDER BY MONTHS ASC"
            # 其他意图：按指标降序
            return "ORDER BY SUM(ORDERED_PRODUCTSALES) DESC"

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
