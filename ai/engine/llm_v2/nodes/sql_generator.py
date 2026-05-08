"""
步骤 6: SQL 生成节点

职责:
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

_VALID_FIELD_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')


def _validate_field_name(field: str) -> str:
    """模块级字段名校验(供 _format_filter_value 使用)"""
    if not field or not _VALID_FIELD_RE.match(field):
        raise ValueError(f"Invalid SQL field name: {field!r}")
    return field


def _format_filter_value(field: str, op: str, value) -> str:
    """根据操作符格式化 SQL 过滤条件,正确处理 IN/BETWEEN 等"""
    _validate_field_name(field)
    op_upper = op.upper().strip()
    if op_upper in ("IN", "NOT IN"):
        # value 可能是逗号分隔字符串或列表
        if isinstance(value, (list, tuple)):
            vals = ", ".join(f"'{v}'" for v in value)
        else:
            vals = ", ".join(f"'{v.strip()}'" for v in str(value).split(","))
        return f"{field} {op_upper} ({vals})"
    elif op_upper == "BETWEEN":
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return f"{field} BETWEEN '{value[0]}' AND '{value[1]}'"
        parts = str(value).split(",")
        if len(parts) >= 2:
            return f"{field} BETWEEN '{parts[0].strip()}' AND '{parts[1].strip()}'"
        return f"{field} BETWEEN '{value}' AND '{value}'"
    else:
        return f"{field} {op_upper} '{value}'"


class SQLGeneratorNode:
    """
    SQL 生成节点

    使用确定性规则将 MQL 转换为 SQL。
    不走 LLM,保证 SQL 生成的可控性。
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

    # 复合指标关键词(用于检测 starrocks_sql 是否为复合指标)
    COMPOUND_KEYWORDS = ["IFNULL", "ISNULL", "COALESCE", "-", "*", "/"]

    # 允许的聚合函数
    ALLOWED_AGGREGATIONS = {"SUM", "AVG", "COUNT", "MAX", "MIN"}

    # 维度类型到数据库列名的映射
    # 同时支持英文和中文 key,从 dimension_configs 表加载
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
        # 中文 key(泛指)
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
        # 时间语义 key(天/周/月/年)← LLM 输出高层语义,代码负责映射
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
        # 品类级别(数字形式,LLM 直接返回)
        "GROUP_1": "GROUP_1",
        "GROUP_2": "GROUP_2",
        "GROUP_3": "GROUP_3",
        "GROUP_4": "GROUP_4",
    }

    # 允许的字段名模式(字母、数字、下划线)
    ALLOWED_FIELD_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    def __init__(self):
        self._metric_client = MetricClient()
        self._load_dimension_type_mappings()

    def _load_dimension_type_mappings(self) -> None:
        """从 Go API 加载全局维度类型映射,合并到 DIMENSION_COLUMN_MAP"""
        try:
            mappings = self._metric_client.get_dimension_type_mappings()
            for m in mappings:
                if m.get("status") == 1 and m.get("dimension_type") and m.get("column_name"):
                    dim_type = m["dimension_type"]
                    col_name = m["column_name"]
                    # API 返回的映射应覆盖硬编码(API 是最新配置)
                    self.DIMENSION_COLUMN_MAP[dim_type] = col_name
                    logger.info(f"[SQLGenerator] 加载维度映射: {dim_type} -> {col_name}")
            logger.info(f"[SQLGenerator] 共加载 {len(mappings)} 个维度类型映射")
        except Exception as e:
            logger.warning(f"[SQLGenerator] 加载维度类型映射失败,使用硬编码映射: {e}")

    def _validate_field_name(self, field: str) -> str:
        """验证字段名,防止 SQL 注入

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
        """清洗值,防止 SQL 注入

        Args:
            value: 要清洗的值

        Returns:
            清洗后的值字符串
        """
        if value is None:
            return "NULL"
        # 字符串:转义单引号(SQL 标准)
        if isinstance(value, str):
            return value.replace("'", "''")
        return str(value)

    def _get_dimension_column(self, dim_type: str) -> str:
        """获取维度对应的数据库列名

        尝试多种匹配方式:
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

        # 未找到映射时,如果输入看起来像列名(全大写),直接返回
        # 这样可以处理 LLM 直接返回列名(如 FPRODUCTLINE)的情况
        if dim_type.isupper():
            return dim_type

        return ""

    def _resolve_formula_field(self, metric_name: str) -> str:
        """从语义快照解析公式指标的分子/分母字段名"""
        try:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            snap = get_semantic_snapshot_service()
            resolved = snap.resolve_metric(metric_name)
            if resolved and resolved.get("starrocks_field"):
                return resolved["starrocks_field"]
        except Exception:
            pass
        return ""

    def _enrich_from_snapshot(self, mql: MQLSchema) -> None:
        """用语义快照兜底补全 MQL 中缺失的指标字段信息"""
        try:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            snap = get_semantic_snapshot_service()
            snapshot = snap.get_active_snapshot()
            if not snapshot:
                return

            def _enrich_one(metric):
                if not metric or not metric.name:
                    return
                if metric.field and metric.table and metric.starrocks_sql:
                    return
                resolved = snap.resolve_metric(metric.name)
                if not resolved:
                    return
                if not metric.table and resolved.get("starrocks_table"):
                    metric.table = resolved["starrocks_table"]
                if not metric.field and resolved.get("starrocks_field"):
                    metric.field = resolved["starrocks_field"]
                if not metric.starrocks_sql and resolved.get("starrocks_sql"):
                    metric.starrocks_sql = resolved["starrocks_sql"]

            _enrich_one(mql.metric)
            for m in (mql.metrics or []):
                _enrich_one(m)
        except Exception as e:
            logger.warning(f"[SQLGenerator] 语义快照兜底补全失败: {e}")

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
            # 0. 语义快照兜底补全(不覆盖已有值)
            self._enrich_from_snapshot(mql)

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

        当检测到 yoy/mom 模式时,使用简单的 CASE WHEN 方式(不依赖窗口函数)
        其他情况使用 CTE Jinja2 模板渲染
        """
        # 检测是否只有 yoy/mom 模式(不需要窗口函数)
        patterns = mql.calculation_patterns or []
        pattern_values = [p.value if isinstance(p, Enum) else str(p) for p in patterns]
        has_period_comparison = any(p in ["yoy", "mom"] for p in pattern_values)
        has_window_only = all(p in ["yoy", "mom"] for p in pattern_values)

        # 如果只有 yoy/mom,使用简单 CASE WHEN 方式(不需要窗口函数)
        if has_period_comparison and has_window_only:
            return self._generate_period_comparison_sql(mql, pattern_values)

        # 其他情况使用 CTE Jinja2 模板
        semantic_json = self._mql_to_semantic(mql)
        from ..semantic_renderer import SemanticRenderer
        renderer = SemanticRenderer()

        # DEBUG: 打印最终 metrics 数量
        final_metrics = semantic_json.get("metrics", [])
        logger.info(f"[_build_sql] 最终 metrics 数量: {len(final_metrics)}, metrics: {[m.get('name') for m in final_metrics]}")

        return renderer.render(semantic_json)

    @staticmethod
    def compute_mom_period(start_dt, end_dt_adjusted):
        """
        计算 MoM(环比)对比期。

        规则(按优先级):
        1. quarter_complete:完整季度 → 上个季度(天数对齐)
        2. month_complete:完整月份 → 上个月(天数对齐)
        3. is_short_ytd:YTD 早期(1/1 开始但 period_days < 90)→ Q4 同期(天数对齐)
        4. is_ytd:跨季度 YTD → Q4 完整范围
        5. else:未完成周期 → 上月同期(天数对齐)
        """
        import calendar
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta

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
            # 跨年YTD(多月累计):滚动周期环比 - 开始结束都减 period_days
            mom_end = end_dt_adjusted - timedelta(days=period_days)
            mom_start = start_dt - timedelta(days=period_days)
        else:
            # 判断是单月内前n天还是多月累计
            # 同月 = 单月 → 上月同期(保持天数对齐)
            # 跨月 = 多月累计 → 滚动周期(开始结束都减 period_days)
            if start_dt.year == end_dt_adjusted.year and start_dt.month == end_dt_adjusted.month:
                # 单月内前n天:上月同期天数对齐
                mom_start = start_dt - relativedelta(months=1)
                mom_end = end_dt_adjusted - relativedelta(months=1)
            else:
                # 多月累计:滚动周期环比 - 开始结束都减 period_days
                mom_end = end_dt_adjusted - timedelta(days=period_days)
                mom_start = start_dt - timedelta(days=period_days)

        return mom_start, mom_end

    def _generate_period_comparison_sql(self, mql: MQLSchema, pattern_values: List[str]) -> str:
        """
        生成周期对比 SQL(同比/环比)

        原理:每个周期汇总成一个值,不需要窗口函数
        当前期和对比期通过 CASE WHEN 分离
        """
        self._enrich_from_snapshot(mql)
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
        except (ValueError, TypeError):
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

        # 当前期(不变)
        current_start = time_start
        current_end = end_dt_adjusted.strftime("%Y-%m-%d")

        # 同比:去年同期(去年同周期,始终计算)
        if supports_yoy:
            yoy_start = start_dt - relativedelta(years=1)
            yoy_end = end_dt_adjusted - relativedelta(years=1)
        else:
            yoy_start = yoy_end = None

        # 环比:复用统一计算逻辑
        if supports_mom:
            mom_start, mom_end = self.compute_mom_period(start_dt, end_dt_adjusted)
        else:
            mom_start = mom_end = None

        # 4. 获取表名和指标字段(支持多指标)
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 收集所有指标:mql.metric + mql.metrics
        all_metrics = []
        if mql.metric and mql.metric.name:
            all_metrics.append(mql.metric)
        for m in (mql.metrics or []):
            if m.name and m.name not in [x.name for x in all_metrics]:
                all_metrics.append(m)

        # 为每个指标提取 field 和 alias
        metric_infos = []
        for m in all_metrics:
            field = getattr(m, 'field', None) or getattr(m, 'name', None) or "ORDERED_PRODUCTSALES"
            alias = m.name
            if m.starrocks_sql:
                extractor = FieldExtractor(m)
                parsed = extractor.parse()
                field = parsed.bare_field
                alias = m.name or parsed.alias
            elif m.field:
                field = m.field
            metric_infos.append({
                "field": field,
                "alias": alias,
                "is_formula": getattr(m, 'is_formula', False),
                "molecule_metric": getattr(m, 'molecule_metric', ''),
                "denominator_metric": getattr(m, 'denominator_metric', ''),
            })

        # 5. 构建 filter
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filter_parts = []

        # 时间范围:包含所有对比期
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
            filter_parts.append(_format_filter_value(f.field, op_val, f.value))

        # 从有具体值的维度生成过滤器
        for dim in mql.dimensions:
            if dim.value:
                col = dim.column if dim.column else self._get_dimension_column(dim.type)
                if col:
                    filter_parts.append(f"{col} = '{dim.value}'")

        filter_sql = " AND ".join(filter_parts)

        # 6. 构建 CASE WHEN 列(多指标)
        cases = []
        for mi in metric_infos:
            mf = mi["field"]
            ma = mi["alias"]
            is_formula = mi.get("is_formula", False)
            mol_metric = mi.get("molecule_metric", "")
            den_metric = mi.get("denominator_metric", "")

            def _build_agg_expr(field, start, end):
                return f"SUM(CASE WHEN FDATE >= '{start}' AND FDATE <= '{end}' THEN {field} ELSE 0 END)"

            # 解析分子/分母字段名
            mol_field = ""
            den_field = ""
            if is_formula and mol_metric and den_metric:
                mol_field = self._resolve_formula_field(mol_metric)
                den_field = self._resolve_formula_field(den_metric)

            def _build_agg_expr(field, start, end):
                return f"SUM(CASE WHEN FDATE >= '{start}' AND FDATE <= '{end}' THEN {field} ELSE 0 END)"

            if is_formula and mol_field and den_field:
                # 公式指标：分子/分母，分母加NULLIF防除零
                def _build_formula_expr(start, end):
                    mol = _build_agg_expr(mol_field, start, end)
                    den = f"NULLIF({_build_agg_expr(den_field, start, end)}, 0)"
                    return f"CAST({mol} AS DOUBLE) / {den}"

                cases.append(f"{_build_formula_expr(current_start, current_end)} AS {ma}_raw")
                if supports_mom:
                    cases.append(f"{_build_formula_expr(mom_start.strftime('%Y-%m-%d'), mom_end.strftime('%Y-%m-%d'))} AS {ma}_mom_val")
                if supports_yoy:
                    cases.append(f"{_build_formula_expr(yoy_start.strftime('%Y-%m-%d'), yoy_end.strftime('%Y-%m-%d'))} AS {ma}_yoy_val")
            else:
                # 普通指标：如果 field 包含除法（如 SUM(A)/SUM(B)），给除数加 NULLIF 防除零
                safe_mf = mf
                if "/" in mf:
                    import re
                    safe_mf = re.sub(r'/\s*(SUM\([^)]+\))', r'/ NULLIF(\1, 0)', mf)
                    if safe_mf == mf:
                        safe_mf = mf.replace("/", "/ NULLIF(") + ", 0)"
                cases.append(f"{_build_agg_expr(safe_mf, current_start, current_end)} AS {ma}_raw")
                if supports_mom:
                    cases.append(f"{_build_agg_expr(safe_mf, mom_start.strftime('%Y-%m-%d'), mom_end.strftime('%Y-%m-%d'))} AS {ma}_mom_val")
                if supports_yoy:
                    cases.append(f"{_build_agg_expr(safe_mf, yoy_start.strftime('%Y-%m-%d'), yoy_end.strftime('%Y-%m-%d'))} AS {ma}_yoy_val")

        # 7. 收集维度列(无具体值的维度进 SELECT 和 GROUP BY)
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

        # 10. 如果需要百分比变化,用子查询包装(多指标支持)
        if supports_mom or supports_yoy:
            change_cols = []
            value_cols = []
            for mi in metric_infos:
                ma = mi["alias"]
                value_cols.append(f'{ma}_raw')
                if supports_mom:
                    value_cols.append(f'{ma}_mom_val')
                    change_cols.append(
                        f"CASE WHEN t.{ma}_mom_val != 0 "
                        f"THEN CONCAT(IF(t.{ma}_raw - t.{ma}_mom_val >= 0, '+', ''), "
                        f"CAST((t.{ma}_raw - t.{ma}_mom_val) / t.{ma}_mom_val * 100 AS VARCHAR), '%') "
                        f"ELSE NULL END AS {ma}_mom_change"
                    )
                if supports_yoy:
                    value_cols.append(f'{ma}_yoy_val')
                    change_cols.append(
                        f"CASE WHEN t.{ma}_yoy_val != 0 "
                        f"THEN CONCAT(IF(t.{ma}_raw - t.{ma}_yoy_val >= 0, '+', ''), "
                        f"CAST((t.{ma}_raw - t.{ma}_yoy_val) / t.{ma}_yoy_val * 100 AS VARCHAR), '%') "
                        f"ELSE NULL END AS {ma}_yoy_change"
                    )

            if dim_cols:
                all_cols = [f"t.{c}" for c in dim_cols] + [f"t.{c}" for c in value_cols]
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
    # CTE Jinja2 渲染(Phase 3-4)
    # =========================================================================

    def _mql_to_semantic(self, mql: MQLSchema) -> dict:
        """
        将 MQLSchema 转换为语义 JSON,供 SemanticRenderer 渲染 CTE SQL

        数据流:
        1. 从 starrocks_sql 提取 agg_expression(原子指标)
        2. 从 calculation_patterns 生成 calculated_metrics
        3. 收集 dimensions / filters / joins 等
        """
        # 1. 表名
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 2. Calculated metrics(从 calculation_patterns 映射,需先构建以判断是否需要时间列)
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
        # - 有具体值的维度 → 只当 filter,不进 GROUP BY
        # - 无具体值的维度 → 进 GROUP BY
        # - 时间维度 → 根据范围跨度决定粒度后加入
        dimensions: List[str] = []
        date_col_candidates = {self.COL_DATE, "DT", "DATE", "STAT_DATE"}
        dt_column = self.COL_DATE
        for dim in mql.dimensions:
            col = dim.column if dim.column else self._get_dimension_column(dim.type)
            if col in date_col_candidates:
                dt_column = col
            # 有具体值的维度不进 GROUP BY(已作为 filter)
            if dim.value:
                continue
            if col and col not in dimensions:
                dimensions.append(col)

        # 时间粒度判断:跨月范围用 MONTHS,否则用 FDATE
        time_dim_col = self.COL_DATE
        question = getattr(mql, 'original_question', '') or ''
        if mql.time and mql.time.start and mql.time.end:
            try:
                from datetime import datetime
                start_dt = datetime.strptime(mql.time.start, "%Y-%m-%d")
                end_dt = datetime.strptime(mql.time.end, "%Y-%m-%d")
                days = (end_dt - start_dt).days
                if days > 31:
                    # 跨月用 MONTHS 列(但如果有 yoy/mom 窗口函数,仍需 FDATE 做 ORDER BY)
                    has_window_func = any(
                        p.value in ("yoy", "mom", "wow", "ma7", "running_sum")
                        for p in (mql.calculation_patterns or [])
                        if hasattr(p, 'value')
                    )
                    if not has_window_func:
                        time_dim_col = self.COL_MONTHS
                        logger.info(f"[SQLGenerator] 时间范围 {days} 天,使用 MONTHS 聚合")
                    else:
                        logger.info(f"[SQLGenerator] 时间范围 {days} 天,但有窗口函数,使用 FDATE")
            except Exception:
                pass

        # 时间维度加入(当没有显式维度,或所有显式维度都有具体值时,作为 GROUP BY 维度)
        # 注意:yoy/mom/running_sum 需要按月粒度(YEARS+MONTHS),ma7/wow 需要按天粒度(FDATE)
        has_monthly_func = any(
            p.value in ("yoy", "mom", "running_sum")
            for p in (mql.calculation_patterns or [])
            if hasattr(p, 'value')
        )
        has_daily_func = any(
            p.value in ("ma7", "wow")
            for p in (mql.calculation_patterns or [])
            if hasattr(p, 'value')
        )

        if has_monthly_func and not has_daily_func:
            # 按月粒度:YEARS + MONTHS
            time_dim_col = self.COL_MONTHS
            if self.COL_YEARS not in dimensions:
                dimensions.append(self.COL_YEARS)
            if self.COL_MONTHS not in dimensions:
                dimensions.append(self.COL_MONTHS)
        elif has_daily_func:
            # 按天粒度:FDATE(ma7 需要每日数据做滑动窗口,wow 需要每日数据做周环比)
            if self.COL_DATE not in dimensions:
                dimensions.append(self.COL_DATE)
        elif time_dim_col not in dimensions:
            # query_trend intent 自动添加时间维度（趋势查询必然需要时间序列）
            intent_val = mql.intent.value if hasattr(mql.intent, 'value') else str(mql.intent)
            if intent_val == "query_trend":
                dimensions.append(time_dim_col)
                logger.info(f"[SQLGenerator] query_trend intent,自动添加 {time_dim_col} 到 GROUP BY")
            else:
                # 只有当用户明确提到时间粒度(如"按天"、"每日"、"按月")时,才将时间列加入 GROUP BY
                time_granularity_keywords = ["按天", "每日", "按日", "每天", "日度", "按月", "每月", "月度", "月均",
                                              "按周", "每周", "周度", "按季", "季度", "按年", "每年", "年度"]
                if any(kw in question for kw in time_granularity_keywords):
                    dimensions.append(time_dim_col)
                    logger.info(f"[SQLGenerator] 用户问题包含时间粒度关键词,添加 {time_dim_col} 到 GROUP BY")

        logger.info(f"[_mql_to_semantic] 最终 dimensions={dimensions}, question='{question}'")

        # 4. 原子指标
        metrics: List[dict] = []
        added_metric_codes: set = set()  # 避免重复指标(如"毛利率"和"销售毛利率"都映射到MKI-02-0094)
        added_metric_names: set = set()  # 避免重复指标名(如"毛利"和"销售毛利"是同一业务指标)

        def _add_metric(m: MQLMetric):
            """将 MQLMetric 添加到 metrics 列表"""
            if not m:
                return
            # 跳过已添加的 metric code(避免重复列)
            if m.code and m.code in added_metric_codes:
                logger.info(f"[_add_metric] 跳过重复code: {m.code} ({m.name})")
                return
            # 跳过已添加的 metric name(业务上同一指标的不同叫法)
            if m.name and m.name in added_metric_names:
                logger.info(f"[_add_metric] 跳过重复name: {m.name} (code={m.code})")
                return
            if m.code:
                added_metric_codes.add(m.code)
            if m.name:
                added_metric_names.add(m.name)
            logger.info(f"[_add_metric] 添加指标: name={m.name}, code={m.code}")

            if m.starrocks_sql:
                extractor = FieldExtractor(m)
                parsed = extractor.parse()
                metrics.append({
                    "name": m.name or parsed.alias,
                    "agg_expression": parsed.expression,
                })
            elif m.name:
                agg = m.aggregation.value if hasattr(m.aggregation, 'value') else str(m.aggregation) if m.aggregation else "SUM"
                field = m.field or m.name or "ORDERED_PRODUCTSALES"
                metrics.append({
                    "name": m.name,
                    "agg_expression": f"{agg}({field})",
                })

        # 主指标
        if mql.metric:
            _add_metric(mql.metric)

        # 附加指标(mql.metrics 中的其他指标,如"销售毛利率"等)
        logger.info(f"[SQLGenerator] mql.metrics 列表: {[(m.name, m.code) for m in (mql.metrics or [])]}")
        for additional_metric in (mql.metrics or []):
            _add_metric(additional_metric)

        logger.info(f"[SQLGenerator] 构建指标列表: main_metric={mql.metric.name if mql.metric else None}, additional_metrics=[{', '.join(m.name for m in (mql.metrics or []) if m.name)}], 最终metrics count={len(metrics)}")
        logger.info(f"[SQLGenerator] 指标详情: {metrics}")

        # 5. Filter(OperatorType → SQL 操作符映射)
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
            # 预处理 IN/BETWEEN 的值格式
            val = f.value
            op_upper = op_val.upper().strip() if isinstance(op_val, str) else ""
            if op_upper in ("IN", "NOT IN"):
                if isinstance(val, (list, tuple)):
                    val = ", ".join(f"'{v}'" for v in val)
                else:
                    val = ", ".join(f"'{v.strip()}'" for v in str(val).split(","))
            elif op_upper == "BETWEEN":
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    val = f"'{val[0]}' AND '{val[1]}'"
                else:
                    parts = str(val).split(",")
                    if len(parts) >= 2:
                        val = f"'{parts[0].strip()}' AND '{parts[1].strip()}'"
                    else:
                        val = f"'{val}' AND '{val}'"
            filters.append({
                "field": f.field,
                "op": op_val,
                "value": val,
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
        # 注意:始终用 FDATE 做日期过滤(即使 dt_column 是 MONTHS,用于窗口函数)
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
        time_dims = {self.COL_DATE, self.COL_MONTHS, self.COL_YEARS, self.COL_WEEKS, self.COL_QUARTERS, "DT", "DATE", "STAT_DATE"}
        if mql.order_by and mql.order_by.field:
            order_by.append(f"{mql.order_by.field} {mql.order_by.direction}")
        elif dimensions:
            first_dim = dimensions[0]
            if first_dim in time_dims:
                # 时间序列查询(如趋势)默认按时间维度排序,确保 result_analyzer 的 first/last 对比正确
                order_by.append(f"{first_dim} ASC")
            else:
                # 非时间维度查询(如品类/站点 breakdown),按销售额降序排列
                if metrics:
                    order_by.append(f"{metrics[0]['name']}_raw DESC")
                else:
                    order_by.append(f"{first_dim} ASC")

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

        同比环比计算逻辑:
        - 当前期数据:按原时间范围查询
        - 对比期数据:在同一个 SQL 中通过 CASE WHEN 分离当前期和对比期
        - 避免了窗口函数 LAG() 的复杂性(不需要按日期 group by 后再跨行计算)
        """
        self._enrich_from_snapshot(mql)
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

        # 4. 结束日期不能超过昨天(当天数据可能不完整)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt_adjusted = end_dt
        if end_dt >= today:
            end_dt_adjusted = today - relativedelta(days=1)
            logger.info(f"[generate_analysis_sql] 结束日期调整为昨天: {end_dt_adjusted.strftime('%Y-%m-%d')}")

        # 5. 计算对比期时间范围(基于调整后的结束日期)
        # 同比:去年同期(去年同周期)
        yoy_start = start_dt - relativedelta(years=1)
        yoy_end = end_dt_adjusted - relativedelta(years=1)

        # 环比:复用统一计算逻辑
        mom_start, mom_end = self.compute_mom_period(start_dt, end_dt_adjusted)

        # 6. 构建表名
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 7. 获取指标字段
        metric_field = (mql.metric.field if mql.metric else None) or (mql.metric.name if mql.metric else None) or "ORDERED_PRODUCTSALES"
        metric_alias = mql.metric.name if mql.metric and mql.metric.name else "value"
        if mql.metric and mql.metric.starrocks_sql:
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()
            metric_field = parsed.bare_field
            metric_alias = mql.metric.name or parsed.alias
        elif mql.metric and mql.metric.field:
            metric_field = mql.metric.field

        # 8. 构建 filters(始终用 FDATE 过滤)
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filters = []

        # 扩展时间范围到对比期(包含去年)
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

        # 9. 构建 SQL(子查询结构:内层按日期聚合,外层 SUM+CASE WHEN 按期间汇总)
        # 避免 StarRocks 嵌套聚合错误:不能 SUM(CASE WHEN ... THEN SUM(...) END)
        # 正确写法:内层先按 FDATE + period 分组,外层再 SUM(period = 'xxx')
        base_filter_sql = " AND ".join([f"{_validate_field_name(f['field'])} {f['op']} '{f['value']}'" for f in filters])

        # CASE WHEN 标记期间(内层子查询用)
        period_case = f"""CASE
    WHEN {self.COL_DATE} >= '{time_start}' AND {self.COL_DATE} <= '{end_dt_adjusted.strftime('%Y-%m-%d')}' THEN 'current'
    WHEN {self.COL_DATE} >= '{mom_start.strftime('%Y-%m-%d')}' AND {self.COL_DATE} <= '{mom_end.strftime('%Y-%m-%d')}' THEN 'mom'
    WHEN {self.COL_DATE} >= '{yoy_start.strftime('%Y-%m-%d')}' AND {self.COL_DATE} <= '{yoy_end.strftime('%Y-%m-%d')}' THEN 'yoy'
END"""

        # 内层:先按 FDATE + period 聚合(消除嵌套聚合)
        # 注意:metric_field 必须用 SUM 聚合,否则 StarRocks 会报 GROUP BY 错误
        inner_select = f"{self.COL_DATE}, {period_case} AS period, SUM({metric_field}) AS daily_val"
        inner_group_by = f"{self.COL_DATE}, {period_case}"

        sql = f"""
SELECT
    SUM(CASE WHEN period = 'current' THEN daily_val ELSE 0 END) AS {metric_alias}_raw,
    SUM(CASE WHEN period = 'mom' THEN daily_val ELSE 0 END) AS mom_val,
    SUM(CASE WHEN period = 'yoy' THEN daily_val ELSE 0 END) AS yoy_val
FROM (
    SELECT
        {inner_select}
    FROM {tables[0]}
    WHERE {base_filter_sql}
    GROUP BY {inner_group_by}
) t
"""
        logger.info(f"[generate_analysis_sql] 同比环比 SQL: {sql[:300]}")
        return sql

    def generate_dimension_attribution_sql(self, mql: MQLSchema, cap: Dict[str, Any], breakdown_dim: str = "FSITE") -> str:
        """
        生成维度归因SQL,按 breakdown_dim 分组计算各维度值的 current/mom/yoy 和贡献率

        关键优化:
        - 用 HAVING contribution_rate >= 1 过滤噪音
        - 按 change_value_abs 降序(谁对整体影响最大谁在前)
        - 贡献率 = ABS(change_value) / ABS(total_change) * 100

        Args:
            mql: MQLSchema 实例
            cap: metric_capability 配置
            breakdown_dim: 维度列名,如 FSITE, GROUP_1, FCHANNEL

        Returns:
            归因分析 SQL 字符串
        """
        self._enrich_from_snapshot(mql)
        # 贡献率阈值：从 cap 获取，默认 1.0
        attribution_min_rate = cap.get("attribution_min_contribution_rate", 1.0)
        import copy
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # 1. 深拷贝并构建时间范围(包含所有对比期)
        mql_copy = copy.deepcopy(mql)

        time_start = mql.time.start if mql.time else None
        time_end = mql.time.end if mql.time else None
        if not time_start or not time_end:
            logger.warning("[generate_dimension_attribution_sql] 缺少时间范围,跳过")
            return ""

        try:
            start_dt = datetime.strptime(time_start, "%Y-%m-%d")
            end_dt = datetime.strptime(time_end, "%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning("[generate_dimension_attribution_sql] 时间解析失败,跳过")
            return ""

        # 2. 结束日期不能超过昨天
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt_adjusted = end_dt
        if end_dt >= today:
            end_dt_adjusted = today - relativedelta(days=1)

        # 3. 计算对比期
        yoy_start = start_dt - relativedelta(years=1)
        yoy_end = end_dt_adjusted - relativedelta(years=1)
        mom_start, mom_end = self.compute_mom_period(start_dt, end_dt_adjusted)

        # 4. 获取表名和指标字段
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]
        metric_field = (mql.metric.field if mql.metric else None) or (mql.metric.name if mql.metric else None) or "ORDERED_PRODUCTSALES"
        metric_alias = mql.metric.name if mql.metric and mql.metric.name else "value"
        if mql.metric and mql.metric.starrocks_sql:
            extractor = FieldExtractor(mql.metric)
            parsed = extractor.parse()
            metric_field = parsed.bare_field
            metric_alias = mql.metric.name or parsed.alias
        elif mql.metric and mql.metric.field:
            metric_field = mql.metric.field

        # 5. 构建 filters
        OP_MAP = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE",
            "in": "IN", "not_in": "NOT IN", "between": "BETWEEN",
        }
        filters = []

        # 扩展时间范围到对比期
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

        base_filter_sql = " AND ".join([f"{_validate_field_name(f['field'])} {f['op']} '{f['value']}'" for f in filters])

        # 6. 验证 breakdown_dim 是合法列名
        try:
            self._validate_field_name(breakdown_dim)
        except ValueError:
            logger.warning(f"[generate_dimension_attribution_sql] 非法维度列名: {breakdown_dim}")
            return ""

        # 7. 构建 CASE WHEN 标记期间
        period_case = f"""CASE
    WHEN {self.COL_DATE} >= '{time_start}' AND {self.COL_DATE} <= '{end_dt_adjusted.strftime('%Y-%m-%d')}' THEN 'current'
    WHEN {self.COL_DATE} >= '{mom_start.strftime('%Y-%m-%d')}' AND {self.COL_DATE} <= '{mom_end.strftime('%Y-%m-%d')}' THEN 'mom'
    WHEN {self.COL_DATE} >= '{yoy_start.strftime('%Y-%m-%d')}' AND {self.COL_DATE} <= '{yoy_end.strftime('%Y-%m-%d')}' THEN 'yoy'
END"""

        # 8. 构建归因 SQL(按 breakdown_dim 分组)
        # 注意:base_data CTE 需要 GROUP BY breakdown_dim 和 period
        # StarRocks 不允许在 WHERE/ORDER BY 中引用 SELECT 别名,需要完整表达式
        # metric_field 需要用 SUM 包裹,否则会报 "must be an aggregate expression" 错误
        sql = f"""
WITH base_data AS (
    SELECT
        {breakdown_dim} AS dim_value,
        {period_case} AS period,
        SUM({metric_field}) AS amount
    FROM {tables[0]}
    WHERE {base_filter_sql}
    GROUP BY {breakdown_dim}, {period_case}
),
overall_metrics AS (
    SELECT
        ABS(SUM(CASE WHEN period = 'current' THEN amount ELSE 0 END) -
            SUM(CASE WHEN period = 'mom' THEN amount ELSE 0 END)) AS total_change_abs
    FROM base_data
),
dimension_metrics AS (
    SELECT
        dim_value,
        SUM(CASE WHEN period = 'current' THEN amount ELSE 0 END) AS current,
        SUM(CASE WHEN period = 'mom' THEN amount ELSE 0 END) AS previous,
        SUM(CASE WHEN period = 'yoy' THEN amount ELSE 0 END) AS yoy_base,
        ABS(SUM(CASE WHEN period = 'current' THEN amount ELSE 0 END) -
            SUM(CASE WHEN period = 'mom' THEN amount ELSE 0 END)) AS change_value_abs,
        SUM(CASE WHEN period = 'current' THEN amount ELSE 0 END) -
        SUM(CASE WHEN period = 'mom' THEN amount ELSE 0 END) AS change_value
    FROM base_data
    GROUP BY dim_value
)
SELECT
    dim_value,
    current,
    ROUND((current / NULLIF(previous, 0) - 1) * 100, 2) AS mom,
    ROUND((current / NULLIF(yoy_base, 0) - 1) * 100, 2) AS yoy,
    change_value,
    ROUND(change_value_abs / NULLIF((SELECT total_change_abs FROM overall_metrics), 0) * 100, 1) AS contribution_rate
FROM dimension_metrics
WHERE ROUND(change_value_abs / NULLIF((SELECT total_change_abs FROM overall_metrics), 0) * 100, 1) >= {attribution_min_rate}
ORDER BY change_value_abs DESC
LIMIT 10;
"""
        logger.info(f"[generate_dimension_attribution_sql] breakdown_dim={breakdown_dim}, SQL: {sql[:400]}")
        return sql

    def _mql_to_semantic_for_analysis(self, mql: MQLSchema, metric_capability: Dict[str, Any], calculation_patterns: List[str]) -> dict:
        """
        构建分析用的 semantic JSON

        与 _mql_to_semantic 的区别:
        1. 时间范围自动扩展到包含同比/环比所需的历史数据
        2. calculation_patterns 根据 metric_capability 决定
        """
        cap = metric_capability or {}

        # 1. 表名
        tables = [mql.metric.table if mql.metric and mql.metric.table else self.DEFAULT_TABLE]

        # 2. Calculated metrics(从 calculation_patterns 生成)
        calculated_metrics: List[dict] = []
        for p in calculation_patterns:
            metric_name = mql.metric.name if mql.metric else ""
            if p == "yoy" and metric_name:
                calculated_metrics.append({"name": "yoy_val", "op": "yoy", "args": [metric_name]})
            elif p == "mom" and metric_name:
                calculated_metrics.append({"name": "mom_val", "op": "mom", "args": [metric_name]})
            elif p == "running_sum" and metric_name:
                calculated_metrics.append({"name": f"{metric_name}_running_sum", "op": "running_sum", "args": [metric_name]})

        # 3. 维度列(分析用,通常不需要时间维度做 GROUP BY)
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

        # 如果没有任何时间维度,根据时间范围跨度决定 dt_column
        # 关键:如果有 yoy/mom/窗口函数,必须用 MONTHS 聚合(不是 FDATE)
        # 这样 LAG(12) 才能正确获取去年同月(12 个月前)
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
                        # 必须将 MONTHS 和 YEARS 加入 dimensions,确保 GROUP BY YEAR, MONTHS
                        # 这样 LAG(12) 可以正确获取去年同月(同一月份,12行前)
                        if self.COL_YEARS not in dimensions:
                            dimensions.append(self.COL_YEARS)
                        if self.COL_MONTHS not in dimensions:
                            dimensions.append(self.COL_MONTHS)
                        logger.info(f"[SQLGenerator] 时间范围 {days} 天 + 窗口函数={has_window_pattern},使用 MONTHS+YEARS 聚合")
                    else:
                        dt_column = self.COL_DATE
                except Exception:
                    pass
        elif has_window_pattern and self.COL_MONTHS not in dimensions:
            # 已有时间维度但有窗口函数,确保 YEARS 和 MONTHS 都在 dimensions 中
            if self.COL_YEARS not in dimensions:
                dimensions.append(self.COL_YEARS)
            if self.COL_MONTHS not in dimensions:
                dimensions.append(self.COL_MONTHS)

        # 4. 时间范围(用 FDATE 过滤,覆盖今年和去年,确保 LAG 窗口函数能正确工作)
        time_start = None
        time_end = None
        if mql.time:
            time_end = mql.time.end
            time_start = mql.time.start

            # 如果需要 yoy,扩展时间范围到去年(但用 FDATE 过滤,不要替换时间范围)
            if cap.get("supports_yoy") and time_start and time_end:
                try:
                    from datetime import datetime
                    start_dt = datetime.strptime(time_start, "%Y-%m-%d")
                    # 扩展到去年1月1日
                    start_dt = start_dt.replace(year=start_dt.year - 1)
                    time_start = start_dt.strftime("%Y-%m-%d")
                    logger.info(f"[SQLGenerator] 扩展时间范围用于同比(FDATE过滤): {time_start} ~ {time_end}")
                except Exception as e:
                    logger.warning(f"[SQLGenerator] 时间范围扩展失败: {e}")

        # 5. 原子指标
        metrics: List[dict] = []
        added_metric_codes: set = set()  # 避免重复指标(如"毛利率"和"销售毛利率"都映射到MKI-02-0094)
        added_metric_names: set = set()  # 避免重复指标名(如"毛利"和"销售毛利"是同一业务指标)

        def _add_metric(m: MQLMetric):
            """将 MQLMetric 添加到 metrics 列表"""
            if not m:
                return
            # 跳过已添加的 metric code(避免重复列)
            if m.code and m.code in added_metric_codes:
                logger.info(f"[_add_metric] 跳过重复code: {m.code} ({m.name})")
                return
            # 跳过已添加的 metric name(业务上同一指标的不同叫法)
            if m.name and m.name in added_metric_names:
                logger.info(f"[_add_metric] 跳过重复name: {m.name} (code={m.code})")
                return
            if m.code:
                added_metric_codes.add(m.code)
            if m.name:
                added_metric_names.add(m.name)
            logger.info(f"[_add_metric] 添加指标: name={m.name}, code={m.code}")

            if m.starrocks_sql:
                extractor = FieldExtractor(m)
                parsed = extractor.parse()
                metrics.append({
                    "name": m.name or parsed.alias,
                    "agg_expression": parsed.expression,
                })
            elif m.name:
                agg = m.aggregation.value if hasattr(m.aggregation, 'value') else str(m.aggregation) if m.aggregation else "SUM"
                field = m.field or m.name or "ORDERED_PRODUCTSALES"
                metrics.append({
                    "name": m.name,
                    "agg_expression": f"{agg}({field})",
                })

        # 主指标
        if mql.metric:
            _add_metric(mql.metric)

        # 附加指标
        logger.info(f"[SQLGenerator] mql.metrics 列表: {[(m.name, m.code) for m in (mql.metrics or [])]}")
        for additional_metric in (mql.metrics or []):
            _add_metric(additional_metric)

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
        # 注意:始终用 FDATE 做日期过滤,即使 dt_column 是 MONTHS(用于聚合)
        # 因为 FDATE 是 YYYY-MM-DD 格式,可以正确做日期范围过滤
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

