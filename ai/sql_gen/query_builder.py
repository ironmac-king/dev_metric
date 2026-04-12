"""
QueryBuilder - JSON → SQL 的确定性转换器
用于智能问数的 SQL 生成层重构
"""
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from ai.config.logging_config import get_logger

logger = get_logger("ai.query_builder")


class AggregationType(str, Enum):
    SUM = "SUM"
    AVG = "AVG"
    COUNT = "COUNT"
    MAX = "MAX"
    MIN = "MIN"


class TimeType(str, Enum):
    DATE_RANGE = "date_range"
    RELATIVE = "relative"
    ABSOLUTE_MONTH = "absolute_month"
    QUARTER = "quarter"


class QueryDimension(BaseModel):
    """维度定义"""
    type: str  # GROUP_1, platform, region 等
    column: str  # 中文显示名
    field: str  # 数据库列名
    value: Optional[str] = None  # 过滤值，None=用于GROUP BY


class QueryMetric(BaseModel):
    """指标定义"""
    name: str
    display_name: str
    aggregation: Optional[AggregationType] = None
    field: str
    alias: str


class TimeSpec(BaseModel):
    """时间规格"""
    type: TimeType = TimeType.DATE_RANGE
    start: Optional[str] = None  # YYYY-MM-DD
    end: Optional[str] = None  # YYYY-MM-DD
    original_expr: Optional[str] = None


class ComparisonSpec(BaseModel):
    """对比规格"""
    enabled: bool = False
    types: List[str] = []  # ["同比", "环比"]


class PaginationSpec(BaseModel):
    """分页规格"""
    page: int = 1
    page_size: int = 100


class DrillDownSpec(BaseModel):
    """下钻规格"""
    add_dimensions: List[str] = []
    original_group_by: List[str] = []
    original_sql: Optional[str] = None


class QueryState(BaseModel):
    """完整的查询语义描述"""
    version: str = "1.0"
    session_id: str = ""

    intent: str = ""
    confidence: float = 1.0

    metric: Dict[str, Any] = {}  # {code, name, unit, starrocks_table, starrocks_sql}

    time: TimeSpec = Field(default_factory=TimeSpec)
    dimensions: List[QueryDimension] = []
    metrics: List[QueryMetric] = []
    filters: List[Dict[str, Any]] = []

    comparison: ComparisonSpec = Field(default_factory=ComparisonSpec)
    pagination: PaginationSpec = Field(default_factory=PaginationSpec)
    drill_down: Optional[DrillDownSpec] = None

    created_at: Optional[str] = None


class QueryIntent(BaseModel):
    """
    结构化的查询意图描述

    从 ConversationState.current_intent + entities 转换而来，
    旨在提供比 entities dict 更结构化的语义信息。

    与 QueryState 的区别：
    - QueryState 是执行层参数，QueryBuilder 直接使用
    - QueryIntent 是语义层描述，更接近自然语言理解
    """
    # 核心意图
    intent_type: str = "query_value"  # query_value / query_trend / query_comparison / query_metadata

    # 指标信息
    metric_code: Optional[str] = None
    metric_name: Optional[str] = None
    metric_id: Optional[int] = None

    # 聚合方式
    aggregation: Optional[str] = None  # SUM / AVG / COUNT / MAX / MIN

    # 时间维度
    time_dimension: Optional[str] = None  # day / month / year / 近7天 / 近30天
    time_range: Optional[Dict[str, str]] = None  # {"start": "2026-03-01", "end": "2026-04-10"}
    time_expr: Optional[str] = None  # 原始时间表达式，如"近7天"

    # 分组维度
    group_by_dims: List[str] = []  # ["平台", "品类"]

    # 过滤条件
    filters: List[Dict[str, Any]] = []  # [{field: "GROUP_3", operator: "=", value: "xxx"}]

    # 对比分析
    comparison_enabled: bool = False
    comparison_types: List[str] = []  # ["同比", "环比"]

    # 排序与限制
    top_n: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: str = "DESC"

    # 多指标支持
    multi_metrics: List[Dict[str, Any]] = []  # 多指标查询

    # 原始数据引用（供回退使用）
    raw_starrocks_sql: Optional[str] = None
    raw_starrocks_table: Optional[str] = None

    # 原始 entities（调试用）
    raw_entities: Optional[Dict[str, Any]] = None


class QueryBuilder:
    """
    QueryState JSON → 可执行 SQL 的确定性转换器

    职责：
    1. 解析 starrocks_sql 模板，提取字段映射
    2. 从 QueryState 构建 SELECT / FROM / WHERE / GROUP BY 子句
    3. 处理 drill_down SQL 改写（扩展 GROUP BY + SELECT）
    4. 生成对比计算 SQL（同比/环比）
    """

    def __init__(self, metric_client=None):
        self.metric_client = metric_client

    def build_sql(self, query_state: QueryState) -> Dict[str, Any]:
        """
        主入口：将 QueryState 转换为 SQL

        Returns:
            {
                "sql": "SELECT ...",
                "params": {},
                "comparison_sqls": [{"type": "同比", "sql": "..."}, ...],
                "original_sql": "...",
                "field_mapping": {...},
                "thinking_steps": [...]
            }
        """
        thinking_steps = []

        # Step 1: 解析 starrocks_sql，提取字段映射
        starrocks_sql = query_state.metric.get("starrocks_sql", "")
        field_mapping = self._parse_starrocks_sql(starrocks_sql)
        thinking_steps.append({
            "step": "parse_sql",
            "status": "completed",
            "detail": f"解析 starrocks_sql，提取 {len(field_mapping.get('select_fields', []))} 个字段"
        })

        # Step 2: 渲染 starrocks_sql 模板（替换占位符）
        rendered_sql = self._render_starrocks_sql(starrocks_sql, query_state, field_mapping)
        thinking_steps.append({
            "step": "render_sql",
            "status": "completed",
            "detail": f"渲染SQL: {rendered_sql[:120]}..."
        })

        # Step 2.5: 保留中文别名 - 不要把中文别名替换回字段名！
        # 注意：这段代码原本是把中文别名替换回字段名，但会导致返回结果列名变成英文
        # 正确的做法是保留 starrocks_sql 中的中文别名，让数据库返回中文列名
        # for field_info in field_mapping.get("select_fields", []):
        #     alias = field_info.get("alias", "")
        #     field = field_info.get("field", "")
        #     if alias and field and alias != field:
        #         rendered_sql = re.sub(rf"`{re.escape(alias)}`", f"`{field}`", rendered_sql, flags=re.IGNORECASE)
        #         rendered_sql = re.sub(rf"(?<![a-zA-Z0-9_]){re.escape(alias)}(?![a-zA-Z0-9_`])", field, rendered_sql)
        #         logger.debug(f"[build_sql] 列名标准化: {alias} → {field}")

        # Step 3: 构建基础 SQL
        logger.info(f"[build_sql] rendered_sql (first 150): {rendered_sql[:150] if rendered_sql else 'None/empty'}")
        sql = self._build_base_sql(query_state, field_mapping, rendered_sql)
        logger.info(f"[build_sql] sql after _build_base_sql (first 150): {sql[:150] if sql else 'None/empty'}")
        # Debug: 记录 group_by_dims
        group_by_dims = [d.field for d in query_state.dimensions if d.value is None]
        thinking_steps.append({
            "step": "build_sql",
            "status": "completed",
            "detail": f"构建 SQL: {sql[:120]}... (group_by_dims={group_by_dims})"
        })

        result = {
            "sql": sql,
            "params": {},
            "original_sql": sql,
            "field_mapping": field_mapping,
            "thinking_steps": thinking_steps
        }

        # Step 4: 处理 drill_down（如有）
        if query_state.drill_down and query_state.drill_down.add_dimensions:
            drill_result = self._apply_drill_down(sql, query_state, field_mapping)
            result["sql"] = drill_result["sql"]
            result["original_sql"] = sql  # 保存原始 SQL 用于后续对比计算
            thinking_steps.append({
                "step": "drill_down",
                "status": "completed",
                "detail": f"添加下钻维度: {drill_result.get('added_dims', [])}"
            })

        # Step 5: 构成分页
        result["sql"] = self._apply_pagination(result["sql"], query_state.pagination)
        thinking_steps.append({
            "step": "pagination",
            "status": "completed",
            "detail": f"分页: page={query_state.pagination.page}, page_size={query_state.pagination.page_size}"
        })

        # Step 6: 生成对比 SQL
        if query_state.comparison.enabled and query_state.comparison.types:
            result["comparison_sqls"] = self._build_comparison_sqls(result["original_sql"], query_state)
            thinking_steps.append({
                "step": "comparison",
                "status": "completed",
                "detail": f"生成对比 SQL: {query_state.comparison.types}"
            })

        return result

    def _render_starrocks_sql(self, starrocks_sql: str, query_state: QueryState, field_mapping: Dict) -> str:
        """
        渲染 starrocks_sql 模板，替换时间/维度占位符

        输入: "SELECT ... FROM table WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}'"
        query_state.time = TimeSpec(start="2026-03-21", end="2026-04-05")
        输出: "SELECT ... FROM table WHERE FDATE >= '2026-03-21' AND FDATE <= '2026-04-05'"
        """
        if not starrocks_sql:
            return ""

        rendered = starrocks_sql

        # 1. 替换时间占位符
        if query_state.time.start:
            rendered = rendered.replace("{start_date}", f"'{query_state.time.start}'")
        if query_state.time.end:
            rendered = rendered.replace("{end_date}", f"'{query_state.time.end}'")

        # 2. 如果没有占位符，根据 time spec 自动追加时间条件
        if "{start_date}" not in rendered and "{end_date}" not in rendered:
            if query_state.time.start and query_state.time.end:
                # 从 field_mapping 获取 WHERE 字段
                where_fields = field_mapping.get("where_fields", [])
                # 查找 FDATE 或类似的时间列
                time_col = None
                for wf in where_fields:
                    if "DATE" in wf.upper() or "DAY" in wf.upper():
                        time_col = wf
                        break
                if not time_col:
                    time_col = "FDATE"  # 默认时间列

                # 判断是日期范围还是月份
                if len(query_state.time.start) == 10:  # YYYY-MM-DD
                    time_cond = f"{time_col} >= '{query_state.time.start}' AND {time_col} <= '{query_state.time.end}'"
                else:  # YYYY-MM
                    time_cond = f"{time_col} = '{query_state.time.start}'"

                if "WHERE" in rendered.upper():
                    rendered += f" AND {time_cond}"
                else:
                    rendered += f" WHERE {time_cond}"

        # 3. 替换维度占位符（如 {dimension}）
        for dim in query_state.dimensions:
            if dim.value:
                placeholder = f"{{{dim.type}}}"
                if placeholder in rendered:
                    rendered = rendered.replace(placeholder, f"'{dim.value}'")

        # 3.5 如果维度有具体值但 SQL 里没有占位符，手动追加到 WHERE
        for dim in query_state.dimensions:
            # 跳过 __SYNONYM__ 占位符（表示识别了维度类型但无具体值）
            if dim.value and dim.value != "__SYNONYM__":
                placeholder = f"{{{dim.type}}}"
                if placeholder not in rendered:
                    # 没有占位符，手动追加 WHERE 条件
                    if "WHERE" in rendered.upper():
                        rendered += f" AND {dim.field} = '{dim.value}'"
                    else:
                        rendered += f" WHERE {dim.field} = '{dim.value}'"

        # 4. 移除未替换的占位符
        import re
        rendered = re.sub(r'\{[^}]+\}', '', rendered)

        return rendered

    def _parse_starrocks_sql(self, starrocks_sql: str) -> Dict[str, Any]:
        """
        解析 starrocks_sql，提取字段映射

        输入: "SELECT GROUP_1, sum(ORDERED_PRODUCTSALES) as 总销售额, sum(ORDERED_GMVS) as 总GMVS FROM dws.DWS_IMC_BUSINESSREPORT WHERE FDATE >= '{start_date}' AND FDATE <= '{end_date}' GROUP BY GROUP_1"

        输出: {
            "select_fields": [
                {"field": "GROUP_1", "alias": "GROUP_1", "aggregation": None},
                {"field": "ORDERED_PRODUCTSALES", "alias": "总销售额", "aggregation": "SUM"},
                {"field": "ORDERED_GMVS", "alias": "总GMVS", "aggregation": "SUM"},
            ],
            "table": "dws.DWS_IMC_BUSINESSREPORT",
            "where_fields": ["FDATE"],
            "group_by_fields": ["GROUP_1"]
        }
        """
        import re

        result = {
            "select_fields": [],
            "table": "",
            "where_fields": [],
            "group_by_fields": []
        }

        if not starrocks_sql:
            return result

        # 提取表名
        from_match = re.search(r'FROM\s+([^\s;]+)', starrocks_sql, re.IGNORECASE)
        if from_match:
            result["table"] = from_match.group(1)

        # 提取 SELECT 字段
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', starrocks_sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            fields = self._split_fields(select_clause)

            for field in fields:
                field = field.strip()
                if not field:
                    continue

                # 匹配 sum(xxx) as alias 或 xxx as alias
                # 支持中文别名：\w+ 改为 [\w\u4e00-\u9fa5]+
                agg_match = re.match(r'(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(\w+)\s*\)\s*(?:as\s+`?([\w\u4e00-\u9fa5]+)`?)?', field, re.IGNORECASE)
                alias_match = re.match(r'([\w\u4e00-\u9fa5]+)\s+as\s+`?([\w\u4e00-\u9fa5]+)`?', field, re.IGNORECASE)

                if agg_match:
                    result["select_fields"].append({
                        "field": agg_match.group(2),
                        "alias": agg_match.group(3) or agg_match.group(2),
                        "aggregation": agg_match.group(1).upper()
                    })
                elif alias_match:
                    result["select_fields"].append({
                        "field": alias_match.group(1),
                        "alias": alias_match.group(2),
                        "aggregation": None
                    })
                else:
                    # 普通字段
                    result["select_fields"].append({
                        "field": field,
                        "alias": field,
                        "aggregation": None
                    })

        # 提取 GROUP BY 字段
        group_match = re.search(r'GROUP\s+BY\s+([^\s,]+(?:\s*,\s*[^\s,]+)*)', starrocks_sql, re.IGNORECASE)
        if group_match:
            result["group_by_fields"] = [f.strip() for f in group_match.group(1).split(',')]

        return result

    def _split_fields(self, select_clause: str) -> List[str]:
        """正确分割 SELECT 子句中的字段（忽略括号内的逗号）"""
        fields = []
        depth = 0
        current = ""

        for char in select_clause:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                fields.append(current)
                current = ""
            else:
                current += char

        if current.strip():
            fields.append(current)

        return fields

    def _build_base_sql(self, query_state: QueryState, field_mapping: Dict, rendered_sql: str = "") -> str:
        """
        构建基础 SQL

        如果 rendered_sql 非空（已有渲染后的 starrocks_sql），在其基础上添加 GROUP BY
        否则从零构建
        """

        # 如果有渲染后的 SQL，使用它并只添加 GROUP BY
        if rendered_sql:
            sql = rendered_sql

            # 确定 GROUP BY 维度
            group_by_dims = [d.field for d in query_state.dimensions if d.value is None]
            if not group_by_dims:
                group_by_dims = field_mapping.get("group_by_fields", [])

            logger.info(f"[_build_base_sql] group_by_dims = {group_by_dims}, has GROUP BY in sql: {bool(re.search(r'\\bGROUP\\s+BY\\b', sql, re.IGNORECASE))}")

            # 如果有 GROUP BY 维度
            if group_by_dims:
                logger.info(f"[_build_base_sql] DEBUG: entering group_by_dims block, group_by_dims={group_by_dims}")
                # 检查 SQL 是否已有 GROUP BY
                has_group_by = re.search(r'\bGROUP\s+BY\b', sql, re.IGNORECASE)
                # 查找独立的 FROM 关键字（前面有空格或换行，后面是空格+表名）
                from_pos = re.search(r'\s+FROM\s+', sql, re.IGNORECASE)
                if from_pos:
                    select_start = re.search(r'\bSELECT\b', sql, re.IGNORECASE)
                    if select_start:
                        # 提取 SELECT 和 FROM 之间的内容
                        select_clause_raw = sql[select_start.end():from_pos.start()]
                        logger.info(f"[_build_base_sql] DEBUG: select_start.end()={select_start.end()}, from_pos.start()={from_pos.start()}")
                        # 规范化：替换多余空白为单个空格
                        select_clause = re.sub(r'\s+', ' ', select_clause_raw).strip()
                        # 找出缺失的维度列
                        missing_dims = [d for d in group_by_dims if f"`{d}`".upper() not in select_clause.upper() and d.upper() not in select_clause.upper()]
                        logger.info(f"[_build_base_sql] DEBUG: select_clause='{select_clause}', missing_dims={missing_dims}, has_group_by={bool(has_group_by)}")
                        if missing_dims:
                            # 构建维度列前缀
                            dims_to_add = ", ".join([f"`{d}`" for d in missing_dims]) + ", "
                            logger.info(f"[_build_base_sql] DEBUG: dims_to_add='{dims_to_add}'")
                            if not has_group_by:
                                # 没有 GROUP BY，添加 GROUP BY 列到 SELECT 开头
                                new_select = f"SELECT {dims_to_add}{select_clause_raw.strip()}"
                            else:
                                # GROUP BY 已存在，需要在聚合函数前插入维度列
                                agg_match = re.search(r'\b(SUM|COUNT|AVG|MAX|MIN)\s*\(', select_clause, re.IGNORECASE)
                                logger.info(f"[_build_base_sql] DEBUG: agg_match={agg_match.group() if agg_match else None}")
                                if agg_match:
                                    agg_pos_in_raw = select_clause_raw.find(agg_match.group())
                                    if agg_pos_in_raw == -1:
                                        agg_pos_in_raw = 0
                                    new_select_raw = select_clause_raw[:agg_pos_in_raw] + dims_to_add + select_clause_raw[agg_pos_in_raw:]
                                    new_select = f"SELECT {new_select_raw.strip()}"
                                else:
                                    # Fallback: 在 SELECT 开头添加维度列
                                    new_select = f"SELECT {dims_to_add}{select_clause_raw.strip()}"
                            # 重建完整 SQL: SELECT ... FROM table ...
                            # from_pos.start()+1 跳过换行符，保留 FROM 关键字
                            sql = new_select + sql[from_pos.start():]
                # 添加 GROUP BY（如果还没有）
                if not has_group_by:
                    sql += " GROUP BY " + ", ".join([f"`{d}`" for d in group_by_dims])

            # 返回在 rendered_sql 基础上构建的 SQL（不执行"从零构建"）
            return sql

        # 从零构建 SQL
        parts = ["SELECT"]

        select_parts = []

        # 1. 分组维度列（用于 GROUP BY 的维度）
        for dim in query_state.dimensions:
            if dim.value is None:  # 这是 GROUP BY 维度
                select_parts.append(f"`{dim.field}`")

        # 2. 指标列（带聚合）
        for metric in query_state.metrics:
            if metric.aggregation:
                select_parts.append(f"{metric.aggregation}(`{metric.field}`) as `{metric.alias}`")
            else:
                select_parts.append(f"`{metric.field}` as `{metric.alias}`")

        # 如果 QueryState 没有提供 metrics，使用 starrocks_sql 解析出的字段
        if not select_parts:
            for f in field_mapping.get("select_fields", []):
                if f["aggregation"]:
                    select_parts.append(f"{f['aggregation']}(`{f['field']}`) as `{f['alias']}`")
                else:
                    select_parts.append(f"`{f['field']}` as `{f['alias']}`")

        parts.append(", ".join(select_parts) if select_parts else "*")

        # FROM 子句
        table = query_state.metric.get("starrocks_table") or field_mapping.get("table", "")
        parts.append(f"FROM {table}")

        # WHERE 子句
        where_parts = []

        # 时间条件
        if query_state.time.start:
            where_parts.append(f"FDATE >= '{query_state.time.start}'")
        if query_state.time.end:
            where_parts.append(f"FDATE <= '{query_state.time.end}'")

        # 维度过滤条件
        for dim in query_state.dimensions:
            if dim.value is not None:  # 这是过滤条件
                # 跳过 __SYNONYM__ 占位符（表示识别了维度类型但无具体值，不需要 WHERE 条件）
                if dim.value == '__SYNONYM__':
                    continue
                where_parts.append(f"`{dim.field}` = '{dim.value}'")

        # 其他过滤条件
        for f in query_state.filters:
            # 跳过 __SYNONYM__ 占位符（表示识别了维度类型但无具体值，不需要 WHERE 条件）
            if f.get('value') == '__SYNONYM__':
                continue
            where_parts.append(f"`{f['field']}` {f.get('operator', '=')} '{f['value']}'")

        if where_parts:
            parts.append("WHERE " + " AND ".join(where_parts))

        # GROUP BY 子句
        group_by_dims = [d.field for d in query_state.dimensions if d.value is None]
        if not group_by_dims:
            group_by_dims = field_mapping.get("group_by_fields", [])

        if group_by_dims:
            parts.append("GROUP BY " + ", ".join([f"`{d}`" for d in group_by_dims]))

        return " ".join(parts)

    def _apply_drill_down(self, original_sql: str, query_state: QueryState, field_mapping: Dict) -> Dict[str, Any]:
        """
        处理 drill_down SQL 改写：
        1. 在 SELECT 中添加新维度列
        2. 在 GROUP BY 中添加新维度列

        输入: "SELECT `GROUP_1`, SUM(`ORDERED_PRODUCTSALES`) as sales FROM table GROUP BY `GROUP_1`"
        要添加: GROUP_2
        输出: "SELECT `GROUP_1`, `GROUP_2`, SUM(`ORDERED_PRODUCTSALES`) as sales FROM table GROUP BY `GROUP_1`, `GROUP_2`"
        """
        import re

        new_dims = query_state.drill_down.add_dimensions

        # 1. 从 starrocks_sql 解析获取 group_by_fields（确定性的，因为预置 SQL 格式已知）
        # 不再依赖正则从 current_sql 提取
        group_by_fields = field_mapping.get("group_by_fields", [])

        # 2. 构建新的维度列表
        all_dims = list(group_by_fields)
        for dim in new_dims:
            if dim not in all_dims:
                all_dims.append(dim)

        # 3. 重建 SQL
        # 移除原有的 GROUP BY 部分
        sql_without_group = re.sub(
            r'\s+GROUP\s+BY\s+.*$',
            '',
            original_sql,
            flags=re.IGNORECASE | re.DOTALL
        ).strip()

        # 4. 在 SELECT 的聚合函数之前添加新维度列
        # 找到聚合函数的位置，在它之前插入维度列
        dims_to_add = [d for d in all_dims if d.upper() not in sql_without_group.upper()]
        if dims_to_add:
            dims_str = ", ".join([f"`{d}`" for d in dims_to_add]) + ", "

            # 在第一个 SUM/COUNT/AVG/MAX/MIN 之前插入
            sql_without_group = re.sub(
                r'(\s+)(SUM\s*\(|COUNT\s*\(|AVG\s*\(|MAX\s*\(|MIN\s*\()',
                r'\1' + dims_str + r'\2',
                sql_without_group,
                flags=re.IGNORECASE
            )

        # 5. 添加新的 GROUP BY
        new_sql = sql_without_group + " GROUP BY " + ", ".join([f"`{d}`" for d in all_dims])

        return {
            "sql": new_sql,
            "added_dims": all_dims
        }

    def _apply_pagination(self, sql: str, pagination: PaginationSpec) -> str:
        """添加分页"""
        import re

        offset = (pagination.page - 1) * pagination.page_size
        limit = min(pagination.page_size, 1000)  # 最大1000条

        # 移除原有的 LIMIT/OFFSET
        sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s+OFFSET\s+\d+', '', sql, flags=re.IGNORECASE)

        return f"{sql} LIMIT {limit} OFFSET {offset}"

    def _build_comparison_sqls(self, original_sql: str, query_state: QueryState) -> List[Dict[str, str]]:
        """
        生成对比 SQL（同比/环比）

        同比: 去年同月
        环比: 上月

        T+1 数据逻辑：当前数据是昨天及之前
        """
        from datetime import datetime, timedelta
        import calendar
        import re

        comparison_sqls = []

        # 从 SQL 中提取日期条件
        date_match = re.search(r"FDATE\s*>=\s*'(\d{4})-(\d{2})-(\d{2})'", original_sql)
        if not date_match:
            return comparison_sqls

        year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        # T+1: 当前数据实际是昨天
        current_date = datetime(year, month, day) - timedelta(days=1)

        for comp_type in query_state.comparison.types:
            if comp_type == "环比":
                # 环比上月
                if current_date.month == 1:
                    comp_year, comp_month = current_date.year - 1, 12
                else:
                    comp_year, comp_month = current_date.year, current_date.month - 1
                comp_day = 1
            else:  # 同比
                comp_year, comp_month = current_date.year - 1, current_date.month
                comp_day = 1

            # 计算对比期结束日
            comp_month_days = calendar.monthrange(comp_year, comp_month)[1]
            original_end_day = current_date.day
            comp_end_day = min(original_end_day, comp_month_days)

            comp_start = f"{comp_year}-{comp_month:02d}-{comp_day:02d}"
            comp_end = f"{comp_year}-{comp_month:02d}-{comp_end_day:02d}"

            # 替换 SQL 中的日期条件
            comparison_sql = re.sub(
                r"FDATE\s*>=\s*'\d{4}-\d{2}-\d{2}'",
                f"FDATE >= '{comp_start}'",
                original_sql
            )
            comparison_sql = re.sub(
                r"FDATE\s*<=\s*'\d{4}-\d{2}-\d{2}'",
                f"FDATE <= '{comp_end}'",
                comparison_sql
            )

            # 移除 LIMIT/OFFSET
            comparison_sql = re.sub(r'\s+LIMIT\s+\d+\s*(OFFSET\s+\d+)?', '', comparison_sql, flags=re.IGNORECASE)
            comparison_sql = re.sub(r'\s+OFFSET\s+\d+', '', comparison_sql, flags=re.IGNORECASE)

            comparison_sqls.append({
                "type": comp_type,
                "sql": comparison_sql,
                "period_start": comp_start,
                "period_end": comp_end
            })

        return comparison_sqls

    # ========== QueryIntent 相关方法 ==========

    def build_sql_from_intent(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        新增入口：将 QueryIntent 转换为 SQL

        这是为了后续让 LLM 生成 QueryIntent（结构化意图），
        而不是直接生成 SQL，从而避免 LLM 生成 SQL 的幻觉问题。

        Args:
            intent: 结构化的查询意图

        Returns:
            与 build_sql() 相同的格式
        """
        logger.info(f"[build_sql_from_intent] intent_type={intent.intent_type}, metric_code={intent.metric_code}")
        query_state = self._intent_to_state(intent)
        return self.build_sql(query_state)

    def _intent_to_state(self, intent: QueryIntent) -> QueryState:
        """
        将 QueryIntent 转换为 QueryState

        Args:
            intent: 结构化的查询意图

        Returns:
            QueryState 查询状态
        """
        # 构建 metric dict
        metric = {
            "code": intent.metric_code or "",
            "name": intent.metric_name or "",
            "starrocks_sql": intent.raw_starrocks_sql or "",
            "starrocks_table": intent.raw_starrocks_table or "",
        }

        # 构建 TimeSpec
        time_spec = TimeSpec(
            type=TimeType.DATE_RANGE,
            start=intent.time_range.get("start") if intent.time_range else None,
            end=intent.time_range.get("end") if intent.time_range else None,
            original_expr=intent.time_expr,
        )

        # 构建 dimensions
        query_dimensions = []
        for dim_name in intent.group_by_dims:
            if dim_name:  # 跳过空维度名
                query_dimensions.append(QueryDimension(
                    type=dim_name,
                    column=dim_name,
                    field=dim_name,
                    value=None  # None 表示用于 GROUP BY
                ))

        # 添加 filters 作为 dimensions（带 value 的用于 WHERE 条件）
        for f in intent.filters:
            if isinstance(f, dict) and f.get("field"):
                query_dimensions.append(QueryDimension(
                    type=f["field"],
                    column=f["field"],
                    field=f["field"],
                    value=f.get("value")
                ))

        # 构建 pagination
        pagination = PaginationSpec(
            page=1,
            page_size=min(intent.top_n or 10, 1000)
        )

        # 构建 comparison
        comparison = ComparisonSpec(
            enabled=intent.comparison_enabled,
            types=intent.comparison_types
        )

        return QueryState(
            version="1.0",
            intent=intent.intent_type,
            confidence=0.9,
            metric=metric,
            time=time_spec,
            dimensions=query_dimensions,
            pagination=pagination,
            comparison=comparison,
        )
