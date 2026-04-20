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
from ..schema import MQLSchema, MQLMetric, MQLDimension, TimeRange, TimeType, SQLResult, CalculationPattern

logger = get_logger("ai.llm_v2.sql_generator")


class SQLGeneratorNode:
    """
    SQL 生成节点

    使用确定性规则将 MQL 转换为 SQL。
    不走 LLM，保证 SQL 生成的可控性。
    """

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
        "站点": "FSITECODE",
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

    def __init__(self):
        self._default_table = "ids.IDS_AMZ_COMPREHENSIVE_DI"
        self._metric_client = MetricClient()
        self._load_dimension_type_mappings()

    def _load_dimension_type_mappings(self):
        """从 Go API 加载全局维度类型映射，合并到 DIMENSION_COLUMN_MAP"""
        try:
            mappings = self._metric_client.get_dimension_type_mappings()
            for m in mappings:
                if m.get("status") == 1 and m.get("dimension_type") and m.get("column_name"):
                    dim_type = m["dimension_type"]
                    col_name = m["column_name"]
                    if dim_type not in self.DIMENSION_COLUMN_MAP:
                        self.DIMENSION_COLUMN_MAP[dim_type] = col_name
                        logger.info(f"[SQLGenerator] 加载维度映射: {dim_type} -> {col_name}")
            logger.info(f"[SQLGenerator] 共加载 {len(mappings)} 个维度类型映射")
        except Exception as e:
            logger.warning(f"[SQLGenerator] 加载维度类型映射失败，使用硬编码映射: {e}")

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
        # 1. 确定表名
        table = mql.metric.table if mql.metric and mql.metric.table else self._default_table

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

    def _build_select(self, mql: MQLSchema) -> str:
        """构建 SELECT 子句"""
        select_parts = []

        # 添加维度列
        for dim in mql.dimensions:
            if dim.column:
                select_parts.append(dim.column)
            else:
                col = self._get_dimension_column(dim.type)
                if col:
                    select_parts.append(col)

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
                match = re.search(r'SELECT\s+.*?\s+AS\s+`?(\w+)`?\s+FROM', sql_upper, re.DOTALL)
                if match:
                    alias = match.group(1)
                    # 如果 alias 等于默认字段，可能是真实字段名
                    return alias
                return default_field

            mol_field = _extract_field_from_sql(mol.starrocks_sql, mol.field or "REFUND_QTY")
            den_field = _extract_field_from_sql(den.starrocks_sql, den.field or "ORDERED_PRODUCTSALES")
            mol_agg = mol.aggregation.value if hasattr(mol.aggregation, 'value') else (mol.aggregation or "SUM")
            den_agg = den.aggregation.value if hasattr(den.aggregation, 'value') else (den.aggregation or "SUM")
            # 生成占比表达式
            ratio_expr = f"{mol_agg}({mol_field}) * 100.0 / {den_agg}({den_field})"
            ratio_name = mol.name if mol.name else "占比"
            select_parts.append(f"{ratio_expr} AS {ratio_name}")
            logger.info(f"[_build_select] 占比模式: {mol_agg}({mol_field}) * 100.0 / {den_agg}({den_field})")
        # 添加指标列
        elif mql.metric:
            metric_field = mql.metric.field or "ORDERED_PRODUCTSALES"
            metric_agg = mql.metric.aggregation.value if hasattr(mql.metric.aggregation, 'value') else mql.metric.aggregation

            # 如果有 starrocks_sql，解析字段
            if mql.metric.starrocks_sql:
                starrocks_sql = mql.metric.starrocks_sql.strip()
                logger.info(f"[_build_select] starrocks_sql: {starrocks_sql[:200]}")

                # 检测是否是复合指标（包含 / 或 *）
                if '/' in starrocks_sql or '*' in starrocks_sql:
                    # 复合指标：提取完整的 SELECT ... AS alias 表达式
                    # 例如: SELECT SUM(TOTALSALES)/SUM(TOTALORDERS) AS `AD_AOV` FROM ...
                    # 注意: [^FROM] 匹配 F/R/O/M 单字符，不是字符串 FROM
                    match = re.search(r'SELECT\s+(.+?)\s+AS\s+`?(\w+)`?\s+FROM', starrocks_sql, re.IGNORECASE | re.DOTALL)
                    if match:
                        inner_expr = match.group(1).strip()
                        alias = match.group(2)
                        logger.info(f"[_build_select] 复合指标匹配成功: inner_expr={inner_expr}, alias={alias}")
                        select_parts.append(f"{inner_expr} AS {alias}")
                    else:
                        logger.warning(f"[_build_select] 复合指标正则匹配失败，回退到默认值")
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

        # 如果没有选择任何列，添加占位符
        if not select_parts:
            select_parts.append("1 AS placeholder")

        return f"SELECT {', '.join(select_parts)}"

    def _build_where(self, mql: MQLSchema) -> str:
        """构建 WHERE 子句"""
        where_parts = []

        # 时间条件
        if mql.time:
            if mql.time.type == TimeType.DATE_RANGE:
                if mql.time.start:
                    where_parts.append(f"FDATE >= '{mql.time.start}'")
                if mql.time.end:
                    where_parts.append(f"FDATE <= '{mql.time.end}'")
            elif mql.time.type == TimeType.RELATIVE:
                # 解析相对时间
                if mql.time.original:
                    where_parts.append(self._parse_relative_time(mql.time.original))

        # 筛选条件
        for filter_obj in mql.filters:
            if filter_obj.field and filter_obj.value is not None:
                op = filter_obj.operator.value if hasattr(filter_obj.operator, 'value') else filter_obj.operator
                if op == "eq":
                    where_parts.append(f"{filter_obj.field} = '{filter_obj.value}'")
                elif op == "gt":
                    where_parts.append(f"{filter_obj.field} > '{filter_obj.value}'")
                elif op == "lt":
                    where_parts.append(f"{filter_obj.field} < '{filter_obj.value}'")
                elif op == "in":
                    values = "', '".join(filter_obj.value) if isinstance(filter_obj.value, list) else filter_obj.value
                    where_parts.append(f"{filter_obj.field} IN ('{values}')")
                elif op == "between":
                    if isinstance(filter_obj.value, list) and len(filter_obj.value) == 2:
                        where_parts.append(f"{filter_obj.field} BETWEEN '{filter_obj.value[0]}' AND '{filter_obj.value[1]}'")

        # 维度过滤
        for dim in mql.dimensions:
            if dim.value:
                # 优先使用 column，如果为空则从类型映射获取
                col = dim.column
                if not col:
                    col = self._get_dimension_column(dim.type)
                if col:
                    where_parts.append(f"{col} = '{dim.value}'")

        if where_parts:
            return "WHERE " + " AND ".join(where_parts)
        return ""

    def _parse_relative_time(self, original: str) -> str:
        """解析相对时间表达式"""
        from datetime import datetime, timedelta

        today = datetime.now()

        if "本月" in original:
            start = today.replace(day=1).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return f"FDATE >= '{start}' AND FDATE <= '{end}'"
        elif "上月" in original:
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            start = last_day_last_month.replace(day=1).strftime("%Y-%m-%d")
            end = last_day_last_month.strftime("%Y-%m-%d")
            return f"FDATE >= '{start}' AND FDATE <= '{end}'"
        elif "近7天" in original:
            start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return f"FDATE >= '{start}' AND FDATE <= '{end}'"
        elif "近30天" in original:
            start = (today - timedelta(days=29)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return f"FDATE >= '{start}' AND FDATE <= '{end}'"
        else:
            # 默认本月
            start = today.replace(day=1).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return f"FDATE >= '{start}' AND FDATE <= '{end}'"

    def _build_group_by(self, mql: MQLSchema) -> str:
        """构建 GROUP BY 子句"""
        if not mql.dimensions:
            return ""

        group_by_parts = []
        for dim in mql.dimensions:
            # 优先使用 column，如果为空则从类型映射获取
            if dim.column:
                group_by_parts.append(dim.column)
            else:
                col = self._get_dimension_column(dim.type)
                if col:
                    group_by_parts.append(col)

        if group_by_parts:
            return "GROUP BY " + ", ".join(group_by_parts)
        return ""

    def _build_order_by(self, mql: MQLSchema) -> str:
        """构建 ORDER BY 子句"""
        if mql.order_by and mql.order_by.field:
            return f"ORDER BY {mql.order_by.field} {mql.order_by.direction}"

        # 默认按指标降序（有 GROUP BY 时必须用聚合函数）
        if mql.metric and mql.dimensions:
            metric_alias = "ORDERED_PRODUCTSALES"
            if mql.metric.starrocks_sql:
                # 提取 starrocks_sql 中的别名
                match = re.search(r'AS\s*`?(\w+)`?', mql.metric.starrocks_sql, re.IGNORECASE)
                if match:
                    metric_alias = match.group(1)

                # 如果 starrocks_sql 包含除法（复合指标/ratio），不能用 SUM(alias)
                # 直接用 SELECT 的第一个字段排序（通常是 GROUP BY 的维度列）
                if '/' in mql.metric.starrocks_sql or '*' in mql.metric.starrocks_sql:
                    logger.info(f"[_build_order_by] 复合指标不使用 ORDER BY alias，改用维度排序")
                    return ""

            # 有 GROUP BY 时，ORDER BY 必须用聚合函数
            return f"ORDER BY SUM({metric_alias}) DESC"

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
