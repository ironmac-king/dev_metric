"""
步骤 6: SQL 生成节点

职责：
- 将 MQL 转换为 SQL
- 应用业务规则
- 自动关联表
"""
import re
from enum import Enum
from typing import Dict, Any, List, Optional
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
        """构建 SQL

        当检测到 yoy/mom 模式时，使用简单的 CASE WHEN 方式（不依赖窗口函数）
        其他情况使用 CTE Jinja2 模板渲染
        """
        # 检测是否只有 yoy/mom 模式（不需要窗口函数）
        patterns = mql.calculation_patterns or []
        pattern_values = [p.value if isinstance(p, Enum) else str(p) for p in patterns]
        has_period_comparison = any(p in ["yoy", "mom"] for p in pattern_values)
        has_window_only = all(p in ["yoy", "mom"] for p in pattern_values)

        # 如果只有 yoy/mom，使用简单 CASE WHEN 方式（不需要窗口函数）
        if has_period_comparison and has_window_only:
            return self._generate_period_comparison_sql(mql, pattern_values)

        # 其他情况使用 CTE Jinja2 模板
        semantic_json = self._mql_to_semantic(mql)
        from ..semantic_renderer import SemanticRenderer
        renderer = SemanticRenderer()
        return renderer.render(semantic_json)

    def _compute_mom_period(self, start_dt, end_dt_adjusted):
        """
        计算 MoM（环比）对比期。

        规则（按优先级）：
        1. quarter_complete：完整季度 → 上个季度（天数对齐）
        2. month_complete：完整月份 → 上个月（天数对齐）
        3. is_short_ytd：YTD 早期（1/1 开始但 period_days < 90）→ Q4 同期（天数对齐）
        4. is_ytd：跨季度 YTD → Q4 完整范围
        5. else：未完成周期 → 上月同期（天数对齐）
        """
        import calendar
        from datetime import timedelta

        # 月份是否完成
        _, month_last_day = calendar.monthrange(end_dt_adjusted.year, end_dt_adjusted.month)
        month_complete = end_dt_adjusted.day >= month_last_day

        # 季度是否完成
        month = end_dt_adjusted.month
        quarter_end_month = 3 if month <= 3 else (6 if month <= 6 else (9 if month <= 9 else 12))
        _, quarter_last_day = calendar.monthrange(end_dt_adjusted.year, quarter_end_month)
        quarter_complete = (end_dt_adjusted.month == quarter_end_month and end_dt_adjusted.day >= quarter_last_day)

        # 周期天数
        period_days = (end_dt_adjusted - start_dt).days + 1

        # YTD 判断
        is_ytd = (start_dt.month == 1 and start_dt.day == 1 and end_dt_adjusted.month < 12)
        is_short_ytd = is_ytd and period_days < 90

        if quarter_complete:
            mom_start = start_dt - relativedelta(months=3)
            mom_end = end_dt_adjusted - relativedelta(months=3)
        elif month_complete:
            mom_start = start_dt - relativedelta(months=1)
            mom_end = end_dt_adjusted - relativedelta(months=1)
        elif is_short_ytd:
            last_year_end = end_dt_adjusted.replace(year=end_dt_adjusted.year - 1, month=12, day=31)
            mom_start = last_year_end - timedelta(days=period_days - 1)
            mom_end = last_year_end
        elif is_ytd and not is_short_ytd:
            mom_start = end_dt_adjusted.replace(year=end_dt_adjusted.year - 1, month=10, day=1)
            mom_end = end_dt_adjusted.replace(year=end_dt_adjusted.year - 1, month=12, day=31)
        else:
            mom_start = start_dt - relativedelta(months=1)
            mom_end = end_dt_adjusted - relativedelta(months=1)

        return mom_start, mom_end

    def _generate_period_comparison_sql(self, mql: MQLSchema, pattern_values: List[str]) -> str:
        """
        生成周期对比 SQL（同比/环比）

        原理：每个周期汇总成一个值，不需要窗口函数
        当前期和对比期通过 CASE WHEN 分离
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # 1. 获取时间范围
        time_start = mql.time.start if mql.time else None
        time_end = mql.time.end if mql.time else None
        if not time_start or not time_end:
            semantic_json = self._mql_to_semantic(mql)
            from ..semantic_renderer import SemanticRenderer
            renderer = SemanticRenderer()
            return renderer.render(semantic_json)

        try:
            start_dt = datetime.strptime(time_start, "%Y-%m-%d")
            end_dt = datetime.strptime(time_end, "%Y-%m-%d")
        except:
            semantic_json = self._mql_to_semantic(mql)
            from ..semantic_renderer import SemanticRenderer
            renderer = SemanticRenderer()
            return renderer.render(semantic_json)

        # 2. 结束日期不能超过昨天
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt_adjusted = end_dt
        if end_dt >= today:
            end_dt_adjusted = today - relativedelta(days=1)

        # 3. 计算对比期
        supports_yoy = "yoy" in pattern_values
        supports_mom = "mom" in pattern_values

        # 当前期（不变）
        current_start = time_start
        current_end = end_dt_adjusted.strftime("%Y-%m-%d")

        # 同比：去年同期（去年同周期，始终计算）
        if supports_yoy:
            yoy_start = start_dt - relativedelta(years=1)
            yoy_end = end_dt_adjusted - relativedelta(years=1)
        else:
            yoy_start = yoy_end = None

        # 环比：复用统一计算逻辑
        if supports_mom:
            mom_start, mom_end = self._compute_mom_period(start_dt, end_dt_adjusted)
        else:
            mom_start = mom_end = None

        # 4. 获取表名和指标字段
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]
        metric_field = "ORDERED_PRODUCTSALES"
        metric_alias = mql.metric.name if mql.metric and mql.metric.name else "value"
        if mql.metric and mql.metric.starrocks_sql:
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()
            metric_field = parsed.expression
            metric_alias = mql.metric.name or parsed.alias
        elif mql.metric and mql.metric.field:
            metric_field = mql.metric.field

        # 5. 构建 filter
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filter_parts = []

        # 时间范围：包含所有对比期
        min_start = current_start
        if mom_start and str(mom_start.strftime("%Y-%m-%d")) < min_start:
            min_start = mom_start.strftime("%Y-%m-%d")
        if yoy_start and str(yoy_start.strftime("%Y-%m-%d")) < min_start:
            min_start = yoy_start.strftime("%Y-%m-%d")
        filter_parts.append(f"FDATE >= '{min_start}'")
        filter_parts.append(f"FDATE <= '{current_end}'")

        # 从 mql.filters 获取显式过滤器
        for f in mql.filters:
            op_raw = f.operator.value if hasattr(f.operator, 'value') else str(f.operator)
            op_val = OP_MAP.get(op_raw, op_raw)
            filter_parts.append(f"{f.field} {op_val} '{f.value}'")

        # 从有具体值的维度生成过滤器
        for dim in mql.dimensions:
            if dim.value:
                col = dim.column if dim.column else self._get_dimension_column(dim.type)
                if col:
                    filter_parts.append(f"{col} = '{dim.value}'")

        filter_sql = " AND ".join(filter_parts)

        # 6. 构建 CASE WHEN 列
        cases = []
        # 当前期
        cases.append(f"SUM(CASE WHEN FDATE >= '{current_start}' AND FDATE <= '{current_end}' THEN {metric_field} ELSE 0 END) AS {metric_alias}_raw")
        # 环比
        if supports_mom:
            cases.append(f"SUM(CASE WHEN FDATE >= '{mom_start.strftime('%Y-%m-%d')}' AND FDATE <= '{mom_end.strftime('%Y-%m-%d')}' THEN {metric_field} ELSE 0 END) AS mom_val")
        # 同比
        if supports_yoy:
            cases.append(f"SUM(CASE WHEN FDATE >= '{yoy_start.strftime('%Y-%m-%d')}' AND FDATE <= '{yoy_end.strftime('%Y-%m-%d')}' THEN {metric_field} ELSE 0 END) AS yoy_val")

        # 7. 收集维度列（无具体值的维度进 SELECT 和 GROUP BY）
        dim_cols = []
        for dim in mql.dimensions:
            if dim.value:
                continue  # 有具体值的维度已经作为 filter
            col = dim.column if dim.column else self._get_dimension_column(dim.type)
            if col and col not in dim_cols:
                dim_cols.append(col)

        # 7. 构建 SELECT
        select_parts = []
        if dim_cols:
            select_parts.append(", ".join(dim_cols))
        select_parts.extend(cases)

        # 8. 构建 GROUP BY
        group_by = f"GROUP BY {', '.join(dim_cols)}" if dim_cols else ""

        # 9. 构建基础 SQL
        base_sql = f"""
SELECT
    {','.join(select_parts)}
FROM {tables[0]}
WHERE {filter_sql}
{group_by}
"""

        # 10. 如果需要百分比变化，用子查询包装（因为不能在同层 SELECT 引用列别名）
        if supports_mom or supports_yoy:
            change_cols = []
            if supports_mom:
                change_cols.append(
                    f"CASE WHEN t.{metric_alias}_raw > 0 AND t.mom_val > 0 "
                    f"THEN CONCAT(IF(t.{metric_alias}_raw - t.mom_val >= 0, '+', ''), "
                    f"CAST((t.{metric_alias}_raw - t.mom_val) / t.mom_val * 100 AS VARCHAR), '%') "
                    f"ELSE NULL END AS mom_change"
                )
            if supports_yoy:
                change_cols.append(
                    f"CASE WHEN t.{metric_alias}_raw > 0 AND t.yoy_val > 0 "
                    f"THEN CONCAT(IF(t.{metric_alias}_raw - t.yoy_val >= 0, '+', ''), "
                    f"CAST((t.{metric_alias}_raw - t.yoy_val) / t.yoy_val * 100 AS VARCHAR), '%') "
                    f"ELSE NULL END AS yoy_change"
                )

            # 基础列（维度列 + 值列，只包含实际存在的列）
            value_cols = [f'{metric_alias}_raw']
            if supports_mom:
                value_cols.append('mom_val')
            if supports_yoy:
                value_cols.append('yoy_val')

            if dim_cols:
                all_cols = [f"t.{c}" for c in dim_cols] + [f"t.{c}" for c in value_cols]
                sql = f"""
SELECT {', '.join(all_cols)}, {', '.join(change_cols)}
FROM (
{base_sql}
) t
"""
            else:
                all_cols = [f"t.{c}" for c in value_cols]
                sql = f"""
SELECT {', '.join(all_cols)}, {', '.join(change_cols)}
FROM (
{base_sql}
) t
"""
        else:
            sql = base_sql

        logger.info(f"[_generate_period_comparison_sql] SQL: {sql[:500]}")
        return sql

    # =========================================================================
    # CTE Jinja2 渲染（Phase 3-4）
    # =========================================================================

    def _mql_to_semantic(self, mql: MQLSchema) -> dict:
        """
        将 MQLSchema 转换为语义 JSON，供 SemanticRenderer 渲染 CTE SQL

        数据流：
        1. 从 starrocks_sql 提取 agg_expression（原子指标）
        2. 从 calculation_patterns 生成 calculated_metrics
        3. 收集 dimensions / filters / joins 等
        """
        # 1. 表名
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 2. Calculated metrics（从 calculation_patterns 映射，需先构建以判断是否需要时间列）
        calculated_metrics: List[dict] = []
        for p in (mql.calculation_patterns or []):
            pval = p.value if isinstance(p, Enum) else str(p)
            if pval == "yoy":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": "yoy_val", "op": "yoy", "args": [metric_name]})
            elif pval == "mom":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": "mom_val", "op": "mom", "args": [metric_name]})
            elif pval == "running_sum":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": f"{metric_name}_running_sum", "op": "running_sum", "args": [metric_name]})
            elif pval == "ranking":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": f"{metric_name}_rank", "op": "rank", "args": [metric_name]})
            elif pval == "partition_ratio":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": f"{metric_name}_ratio", "op": "partition_ratio", "args": [metric_name]})
            elif pval == "ma7":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": f"{metric_name}_ma7", "op": "ma7", "args": [metric_name]})
            elif pval == "wow":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": "wow_val", "op": "wow", "args": [metric_name]})
            elif pval == "percentage":
                metric_name = mql.metric.name if mql.metric else ""
                if metric_name:
                    calculated_metrics.append({"name": f"{metric_name}_pct", "op": "percentage", "args": [metric_name]})

        # 3. 维度列
        # - 有具体值的维度 → 只当 filter，不进 GROUP BY
        # - 无具体值的维度 → 进 GROUP BY
        # - 时间维度 → 根据范围跨度决定粒度后加入
        dimensions: List[str] = []
        date_col_candidates = {self.COL_DATE, "DT", "DATE", "STAT_DATE"}
        dt_column = self.COL_DATE
        for dim in mql.dimensions:
            col = dim.column if dim.column else self._get_dimension_column(dim.type)
            if col in date_col_candidates:
                dt_column = col
            # 有具体值的维度不进 GROUP BY（已作为 filter）
            if dim.value:
                continue
            if col and col not in dimensions:
                dimensions.append(col)

        # 时间粒度判断：跨月范围用 MONTHS，否则用 FDATE
        time_dim_col = self.COL_DATE
        if mql.time and mql.time.start and mql.time.end:
            try:
                from datetime import datetime
                start_dt = datetime.strptime(mql.time.start, "%Y-%m-%d")
                end_dt = datetime.strptime(mql.time.end, "%Y-%m-%d")
                days = (end_dt - start_dt).days
                if days > 31:
                    # 跨月用 MONTHS 列（但如果有 yoy/mom 窗口函数，仍需 FDATE 做 ORDER BY）
                    has_window_func = any(
                        p.value in ("yoy", "mom", "wow", "ma7", "running_sum")
                        for p in (mql.calculation_patterns or [])
                        if hasattr(p, 'value')
                    )
                    if not has_window_func:
                        time_dim_col = self.COL_MONTHS
                        logger.info(f"[SQLGenerator] 时间范围 {days} 天，使用 MONTHS 聚合")
                    else:
                        logger.info(f"[SQLGenerator] 时间范围 {days} 天，但有窗口函数，使用 FDATE")
            except Exception:
                pass

        # 时间维度加入（当没有显式维度，或所有显式维度都有具体值时，作为 GROUP BY 维度）
        # 注意：如果有 yoy/mom 等窗口函数，需要 YEAR + MONTHS 进行正确的同比/环比计算
        has_window_func = any(
            p.value in ("yoy", "mom", "wow", "ma7", "running_sum")
            for p in (mql.calculation_patterns or [])
            if hasattr(p, 'value')
        )
        if has_window_func:
            # 有窗口函数时用 MONTHS 作为时间维度（用于 GROUP BY 和窗口函数 ORDER BY）
            # 同时确保 YEARS 在 dimensions 中，这样 LAG(12) 可以正确获取去年同月
            time_dim_col = self.COL_MONTHS
            if self.COL_YEARS not in dimensions:
                dimensions.append(self.COL_YEARS)
            if self.COL_MONTHS not in dimensions:
                dimensions.append(self.COL_MONTHS)
        elif time_dim_col not in dimensions:
            if not mql.dimensions or all(dim.value for dim in mql.dimensions):
                dimensions.append(time_dim_col)

        # 4. 原子指标
        metrics: List[dict] = []
        if mql.metric and mql.metric.starrocks_sql:
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()
            metrics.append({
                "name": mql.metric.name or parsed.alias,
                "agg_expression": parsed.expression,
            })
        elif mql.metric:
            agg = mql.metric.aggregation.value if hasattr(mql.metric.aggregation, 'value') else str(mql.metric.aggregation)
            field = mql.metric.field or "ORDERED_PRODUCTSALES"
            metrics.append({
                "name": mql.metric.name or field,
                "agg_expression": f"{agg}({field})",
            })

        # 5. Filter（OperatorType → SQL 操作符映射）
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filters: List[dict] = []
        # 5a. 从 mql.filters 获取显式过滤器
        for f in mql.filters:
            op_raw = f.operator.value if hasattr(f.operator, 'value') else str(f.operator)
            op_val = OP_MAP.get(op_raw, op_raw)
            filters.append({
                "field": f.field,
                "op": op_val,
                "value": f.value,
            })

        # 5b. 从有具体值的维度生成过滤器
        for dim in mql.dimensions:
            if dim.value:
                col = dim.column if dim.column else self._get_dimension_column(dim.type)
                if col:
                    filters.append({
                        "field": col,
                        "op": "=",
                        "value": dim.value,
                    })

        # 5c. 从时间范围生成过滤器
        # 注意：始终用 FDATE 做日期过滤（即使 dt_column 是 MONTHS，用于窗口函数）
        if mql.time and mql.time.start and mql.time.end:
            filters.append({
                "field": self.COL_DATE,
                "op": ">=",
                "value": mql.time.start,
            })
            filters.append({
                "field": self.COL_DATE,
                "op": "<=",
                "value": mql.time.end,
            })

        # 6. Order by
        order_by: List[str] = []
        if mql.order_by and mql.order_by.field:
            order_by.append(f"{mql.order_by.field} {mql.order_by.direction}")

        # 7. Limit
        limit = 1000
        if mql.top_n > 0:
            limit = mql.top_n
        elif mql.pagination and mql.pagination.page_size:
            limit = mql.pagination.page_size

        return {
            "tables": tables,
            "dimensions": dimensions,
            "metrics": metrics,
            "filters": filters,
            "calculated_metrics": calculated_metrics,
            "joins": [],
            "order_by": order_by,
            "limit": limit,
            "time_params": {},
            "dt_column": dt_column,
        }

    def generate_analysis_sql(self, mql: MQLSchema, metric_capability: Dict[str, Any]) -> str:
        """
        根据 metric_capability 生成分析用 SQL

        同比环比计算逻辑：
        - 当前期数据：按原时间范围查询
        - 对比期数据：在同一个 SQL 中通过 CASE WHEN 分离当前期和对比期
        - 避免了窗口函数 LAG() 的复杂性（不需要按日期 group by 后再跨行计算）
        """
        import copy
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        cap = metric_capability or {}

        # 1. 深拷贝 mql
        mql_copy = copy.deepcopy(mql)

        # 2. 获取时间范围
        time_start = mql.time.start if mql.time else None
        time_end = mql.time.end if mql.time else None

        if not time_start or not time_end:
            semantic_json = self._mql_to_semantic(mql_copy)
            from ..semantic_renderer import SemanticRenderer
            renderer = SemanticRenderer()
            return renderer.render(semantic_json)

        # 3. 解析时间范围
        try:
            start_dt = datetime.strptime(time_start, "%Y-%m-%d")
            end_dt = datetime.strptime(time_end, "%Y-%m-%d")
        except:
            semantic_json = self._mql_to_semantic(mql_copy)
            from ..semantic_renderer import SemanticRenderer
            renderer = SemanticRenderer()
            return renderer.render(semantic_json)

        # 4. 结束日期不能超过昨天（当天数据可能不完整）
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt_adjusted = end_dt
        if end_dt >= today:
            end_dt_adjusted = today - relativedelta(days=1)
            logger.info(f"[generate_analysis_sql] 结束日期调整为昨天: {end_dt_adjusted.strftime('%Y-%m-%d')}")

        # 5. 计算对比期时间范围（基于调整后的结束日期）
        # 同比：去年同期（去年同周期）
        yoy_start = start_dt - relativedelta(years=1)
        yoy_end = end_dt_adjusted - relativedelta(years=1)

        # 环比：复用统一计算逻辑
        mom_start, mom_end = self._compute_mom_period(start_dt, end_dt_adjusted)

        # 6. 构建表名
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 7. 获取指标字段
        metric_field = "ORDERED_PRODUCTSALES"
        metric_alias = mql.metric.name if mql.metric and mql.metric.name else "value"
        if mql.metric and mql.metric.starrocks_sql:
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()
            metric_field = parsed.expression
            metric_alias = mql.metric.name or parsed.alias
        elif mql.metric and mql.metric.field:
            metric_field = mql.metric.field

        # 8. 构建 filters（始终用 FDATE 过滤）
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filters = []

        # 扩展时间范围到对比期（包含去年）
        min_start = min(time_start, yoy_start.strftime("%Y-%m-%d"), mom_start.strftime("%Y-%m-%d"))
        filters.append({"field": self.COL_DATE, "op": ">=", "value": min_start})
        filters.append({"field": self.COL_DATE, "op": "<=", "value": end_dt_adjusted.strftime("%Y-%m-%d")})

        # 从 mql.filters 获取显式过滤器
        for f in mql.filters:
            op_raw = f.operator.value if hasattr(f.operator, 'value') else str(f.operator)
            op_val = OP_MAP.get(op_raw, op_raw)
            filters.append({"field": f.field, "op": op_val, "value": f.value})

        # 从有具体值的维度生成过滤器
        for dim in mql.dimensions:
            if dim.value:
                col = dim.column if dim.column else self._get_dimension_column(dim.type)
                if col:
                    filters.append({"field": col, "op": "=", "value": dim.value})

        # 9. 构建 SQL（不使用窗口函数，简洁的 CASE WHEN 方式）
        filter_sql = " AND ".join([f"{f['field']} {f['op']} '{f['value']}'" for f in filters])

        # CASE WHEN 分离当前期和对比期
        current_case = f"SUM(CASE WHEN {self.COL_DATE} >= '{time_start}' AND {self.COL_DATE} <= '{end_dt_adjusted.strftime('%Y-%m-%d')}' THEN {metric_field} ELSE 0 END) AS {metric_alias}_raw"
        mom_case = f"SUM(CASE WHEN {self.COL_DATE} >= '{mom_start.strftime('%Y-%m-%d')}' AND {self.COL_DATE} <= '{mom_end.strftime('%Y-%m-%d')}' THEN {metric_field} ELSE 0 END) AS mom_val"
        yoy_case = f"SUM(CASE WHEN {self.COL_DATE} >= '{yoy_start.strftime('%Y-%m-%d')}' AND {self.COL_DATE} <= '{yoy_end.strftime('%Y-%m-%d')}' THEN {metric_field} ELSE 0 END) AS yoy_val"

        sql = f"""
SELECT
    {current_case},
    {mom_case},
    {yoy_case}
FROM {tables[0]}
WHERE {filter_sql}
"""
        logger.info(f"[generate_analysis_sql] 同比环比 SQL: {sql[:300]}")
        return sql

    def _mql_to_semantic_for_analysis(self, mql: MQLSchema, metric_capability: Dict[str, Any], calculation_patterns: List[str]) -> dict:
        """
        构建分析用的 semantic JSON

        与 _mql_to_semantic 的区别：
        1. 时间范围自动扩展到包含同比/环比所需的历史数据
        2. calculation_patterns 根据 metric_capability 决定
        """
        cap = metric_capability or {}

        # 1. 表名
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 2. Calculated metrics（从 calculation_patterns 生成）
        calculated_metrics: List[dict] = []
        for p in calculation_patterns:
            metric_name = mql.metric.name if mql.metric else ""
            if p == "yoy" and metric_name:
                calculated_metrics.append({"name": "yoy_val", "op": "yoy", "args": [metric_name]})
            elif p == "mom" and metric_name:
                calculated_metrics.append({"name": "mom_val", "op": "mom", "args": [metric_name]})
            elif p == "running_sum" and metric_name:
                calculated_metrics.append({"name": f"{metric_name}_running_sum", "op": "running_sum", "args": [metric_name]})

        # 3. 维度列（分析用，通常不需要时间维度做 GROUP BY）
        dimensions: List[str] = []
        dt_column = self.COL_DATE
        has_time_dim = False
        for dim in mql.dimensions:
            col = dim.column if dim.column else self._get_dimension_column(dim.type)
            if col in {self.COL_DATE, "DT", "DATE", "STAT_DATE", self.COL_MONTHS}:
                dt_column = col
                has_time_dim = True
            # 有具体值的维度不进 GROUP BY
            if dim.value:
                continue
            if col and col not in dimensions:
                dimensions.append(col)

        # 如果没有任何时间维度，根据时间范围跨度决定 dt_column
        # 关键：如果有 yoy/mom/窗口函数，必须用 MONTHS 聚合（不是 FDATE）
        # 这样 LAG(12) 才能正确获取去年同月（12 个月前）
        has_window_pattern = any(p in ["yoy", "mom", "running_sum"] for p in calculation_patterns)
        if not has_time_dim:
            if mql.time and mql.time.start and mql.time.end:
                try:
                    from datetime import datetime
                    start_dt = datetime.strptime(mql.time.start, "%Y-%m-%d")
                    end_dt = datetime.strptime(mql.time.end, "%Y-%m-%d")
                    days = (end_dt - start_dt).days
                    if days > 31 or has_window_pattern:
                        dt_column = self.COL_MONTHS
                        # 必须将 MONTHS 和 YEARS 加入 dimensions，确保 GROUP BY YEAR, MONTHS
                        # 这样 LAG(12) 可以正确获取去年同月（同一月份，12行前）
                        if self.COL_YEARS not in dimensions:
                            dimensions.append(self.COL_YEARS)
                        if self.COL_MONTHS not in dimensions:
                            dimensions.append(self.COL_MONTHS)
                        logger.info(f"[SQLGenerator] 时间范围 {days} 天 + 窗口函数={has_window_pattern}，使用 MONTHS+YEARS 聚合")
                    else:
                        dt_column = self.COL_DATE
                except Exception:
                    pass
        elif has_window_pattern and self.COL_MONTHS not in dimensions:
            # 已有时间维度但有窗口函数，确保 YEARS 和 MONTHS 都在 dimensions 中
            if self.COL_YEARS not in dimensions:
                dimensions.append(self.COL_YEARS)
            if self.COL_MONTHS not in dimensions:
                dimensions.append(self.COL_MONTHS)

        # 4. 时间范围（用 FDATE 过滤，覆盖今年和去年，确保 LAG 窗口函数能正确工作）
        time_start = None
        time_end = None
        if mql.time:
            time_end = mql.time.end
            time_start = mql.time.start

            # 如果需要 yoy，扩展时间范围到去年（但用 FDATE 过滤，不要替换时间范围）
            if cap.get("supports_yoy") and time_start and time_end:
                try:
                    from datetime import datetime
                    start_dt = datetime.strptime(time_start, "%Y-%m-%d")
                    # 扩展到去年1月1日
                    start_dt = start_dt.replace(year=start_dt.year - 1)
                    time_start = start_dt.strftime("%Y-%m-%d")
                    logger.info(f"[SQLGenerator] 扩展时间范围用于同比（FDATE过滤）: {time_start} ~ {time_end}")
                except Exception as e:
                    logger.warning(f"[SQLGenerator] 时间范围扩展失败: {e}")

        # 5. 原子指标
        metrics: List[dict] = []
        if mql.metric and mql.metric.starrocks_sql:
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()
            metrics.append({
                "name": mql.metric.name or parsed.alias,
                "agg_expression": parsed.expression,
            })
        elif mql.metric:
            agg = mql.metric.aggregation.value if hasattr(mql.metric.aggregation, 'value') else str(mql.metric.aggregation)
            field = mql.metric.field or "ORDERED_PRODUCTSALES"
            metrics.append({
                "name": mql.metric.name or field,
                "agg_expression": f"{agg}({field})",
            })

        # 6. Filter
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filters: List[dict] = []

        # 6a. 从 mql.filters 获取显式过滤器
        for f in mql.filters:
            op_raw = f.operator.value if hasattr(f.operator, 'value') else str(f.operator)
            op_val = OP_MAP.get(op_raw, op_raw)
            filters.append({
                "field": f.field,
                "op": op_val,
                "value": f.value,
            })

        # 6b. 从有具体值的维度生成过滤器
        for dim in mql.dimensions:
            if dim.value:
                col = dim.column if dim.column else self._get_dimension_column(dim.type)
                if col:
                    filters.append({
                        "field": col,
                        "op": "=",
                        "value": dim.value,
                    })

        # 6c. 从时间范围生成过滤器
        # 注意：始终用 FDATE 做日期过滤，即使 dt_column 是 MONTHS（用于聚合）
        # 因为 FDATE 是 YYYY-MM-DD 格式，可以正确做日期范围过滤
        if time_start and time_end:
            filters.append({
                "field": self.COL_DATE,
                "op": ">=",
                "value": time_start,
            })
            filters.append({
                "field": self.COL_DATE,
                "op": "<=",
                "value": time_end,
            })

        # 7. Order by
        order_by: List[str] = []
        if mql.order_by and mql.order_by.field:
            order_by.append(f"{mql.order_by.field} {mql.order_by.direction}")

        # 8. Limit
        limit = 1000

        return {
            "tables": tables,
            "dimensions": dimensions,
            "metrics": metrics,
            "filters": filters,
            "calculated_metrics": calculated_metrics,
            "joins": [],
            "order_by": order_by,
            "limit": limit,
            "time_params": {},
            "dt_column": dt_column,
        }

