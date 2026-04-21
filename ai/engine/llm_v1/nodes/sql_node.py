"""
SQLNode - SQL 生成节点（Node3）
输入：SF 输出的完整槽位
输出：{ sql, sql_type, params, has_comparison, has_percentage }
策略：
- 简单指标：QueryBuilder 模板
- 复杂指标：LLM 生成
"""
import logging
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..config_loader import get_config_loader
from ..rag.sql_example_retriever import get_sql_example_retriever, SQLExample
from ..prompts.sql_prompt import SQL_PROMPT

logger = logging.getLogger("ai.llm_v1.sql_node")


@dataclass
class SQLOutput:
    """SQL 节点输出"""
    sql: str
    sql_type: str
    params: Dict[str, Any]
    has_comparison: bool
    has_percentage: bool
    table: str = "ids.IDS_AMZ_COMPREHENSIVE_DI"


class SQLNode:
    """
    SQL 生成节点

    职责：
    1. 根据槽位信息生成最终可执行的 SQL
    2. 策略选择：
       - 简单指标 → QueryBuilder 模板
       - 复杂指标 → LLM 生成
    3. 注入 SQL 示例（RAG）
    """

    def __init__(self):
        self._config_loader = get_config_loader()
        self._sql_retriever = get_sql_example_retriever()
        self._llm_engine = None  # TODO: 后续初始化

    async def process(self, sf_output) -> SQLOutput:
        """
        处理 SF 节点输出，生成 SQL

        Args:
            sf_output: SF 节点输出

        Returns:
            SQLOutput: 生成的 SQL
        """
        logger.info(
            f"[SQLNode] 处理: metric={sf_output.metric_name}, "
            f"dimensions={list(sf_output.dimensions.values())}"
        )

        # 特殊处理：当意图是趋势查询且时间范围<=7天时，应该按日分组
        # 如果当前维度是 MONTHS 但时间范围很短，需要改为 FDATE
        time_start = sf_output.time_range.get("start", "")
        time_end = sf_output.time_range.get("end", "")
        if time_start and time_end and sf_output.dimensions:
            from datetime import datetime
            try:
                start_dt = datetime.strptime(time_start[:10], "%Y-%m-%d")
                end_dt = datetime.strptime(time_end[:10], "%Y-%m-%d")
                days_diff = (end_dt - start_dt).days + 1

                # 如果时间范围 <= 10天 且 当前维度是 MONTHS，改为 FDATE
                if days_diff <= 10 and "MONTHS" in str(list(sf_output.dimensions.values())):
                    logger.info(f"[SQLNode] 时间范围 {days_diff} 天 <= 10天，将 MONTHS 替换为 FDATE")
                    # 替换维度中的 MONTHS 为 FDATE
                    new_dimensions = {}
                    for k, v in sf_output.dimensions.items():
                        if v == "MONTHS":
                            new_dimensions["日期"] = "FDATE"
                        else:
                            new_dimensions[k] = v
                    sf_output.dimensions = new_dimensions
            except Exception as e:
                logger.warning(f"[SQLNode] 时间范围计算失败: {e}")

        # 特殊处理：率指标 + 有维度 + 无比较操作 → 直接构建 SQL（不走 LLM）
        # 如果有比较操作（同比/环比），需要走 LLM 路径来扩展时间范围
        if sf_output.is_rate_metric and sf_output.dimensions:
            operations = sf_output.operations or []
            has_compare = any(
                isinstance(op, dict) and op.get("type") == "compare"
                for op in operations
            )
            if not has_compare:
                logger.info(f"[SQLNode] 率指标 + 维度（无比较），直接构建 SQL")
                return self._build_rate_metric_sql(sf_output)
            else:
                logger.info(f"[SQLNode] 率指标 + 维度 + 有比较操作，走 LLM 路径")

        # 特殊处理：动态占比计算（percentage 操作但没有预定义指标）
        operations = sf_output.operations or []
        has_percentage = any(
            isinstance(op, dict) and op.get("type") == "percentage"
            for op in operations
        )
        if has_percentage and not sf_output.starrocks_sql:
            # 尝试构建动态占比 SQL
            logger.info(f"[SQLNode] 检测到动态占比计算")
            ratio_sql = await self._try_build_dynamic_ratio_sql(sf_output)
            if ratio_sql:
                return ratio_sql

        # Step 1: 检索 SQL 示例
        sql_examples = self._sql_retriever.retrieve(
            question="",  # TODO: 传入原始问题
            metric_code=sf_output.metric_code,
            dimension=list(sf_output.dimensions.values())[0] if sf_output.dimensions else None,
            intent_type=None,
            top_k=5,
        )
        logger.info(f"[SQLNode] 检索到 {len(sql_examples)} 个 SQL 示例")

        # Step 2: 判断策略
        use_llm = self._should_use_llm(sf_output)
        logger.info(f"[SQLNode] 判断结果: use_llm={use_llm}, dimensions={sf_output.dimensions}, operations={sf_output.operations}")

        if use_llm:
            # Step 3a: LLM 生成
            sql_output = await self._generate_sql_with_llm(sf_output, sql_examples)
        else:
            # Step 3b: QueryBuilder 模板生成
            sql_output = self._generate_sql_with_template(sf_output)

        logger.info(f"[SQLNode] 生成 SQL: {sql_output.sql[:100]}...")
        return sql_output

    def _should_use_llm(self, sf_output) -> bool:
        """
        判断是否使用 LLM 生成
        简单场景用模板，复杂场景用 LLM

        触发 LLM 的条件：
        1. 有衍生指标计算（同比/环比/占比）
        2. 有排序/限制操作（order_by/limit）
        3. 有维度分组（GROUP BY）
        4. 多维度组合（>2个维度）
        5. 有复杂筛选条件（>2个筛选）
        """
        # 有衍生指标计算（同比/环比/占比）→ 用 LLM
        if sf_output.operations:
            for op in sf_output.operations:
                # op 可能是字符串或字典
                if isinstance(op, str) and op in ["compare", "percentage", "order_by", "limit"]:
                    return True
                elif isinstance(op, dict) and op.get("type") in ["compare", "percentage", "order_by", "limit"]:
                    return True

        # 有维度分组 → 用 LLM（需要正确处理 GROUP BY）
        if sf_output.dimensions and len(sf_output.dimensions) > 0:
            return True

        # 多维度组合 → 用 LLM
        if len(sf_output.dimensions) > 2:
            return True

        # 有复杂筛选条件 → 用 LLM
        if len(sf_output.filters) > 2:
            return True

        # 其他情况用模板
        return False

    def _expand_time_range_for_compare(self, sf_output):
        """
        当操作类型包含同比/环比时，扩展时间范围以包含比较周期

        支持：
        - 同比 (YoY): 本月 (2026-04-01 ~ 2026-04-17) + 去年同期 (2025-04-01 ~ 2025-04-17)
        - 环比 (MoM/QoQ): 本月 (2026-04-01 ~ 2026-04-17) + 上月 (2026-03-01 ~ 2026-03-31)

        注意：同时支持同比和环比时，设置多组时间范围
        """
        operations = sf_output.operations or []

        # 查找所有 compare 操作
        compare_ops = []
        for op in operations:
            if isinstance(op, dict) and op.get("type") == "compare":
                compare_ops.append(op)
            elif op == "compare":
                compare_ops.append({"type": "compare", "compare_type": "同比"})

        if not compare_ops:
            logger.info(f"[SQLNode] 没有 compare_ops，不需要扩展时间范围, operations={operations}")
            return  # 不需要扩展

        time_start = sf_output.time_range.get("start", "")
        time_end = sf_output.time_range.get("end", "")

        # 如果没有时间范围，使用当前时间自动计算"本月"
        if not time_start or not time_end:
            from datetime import datetime, timedelta
            today = datetime.now()
            # 计算本月第一天
            first_day_this_month = today.replace(day=1)
            # 计算本月最后一天
            if today.month == 12:
                last_day_this_month = today.replace(day=31, month=12)
            else:
                last_day_this_month = today.replace(day=1, month=today.month + 1) - timedelta(days=1)
            time_start = first_day_this_month.strftime("%Y-%m-%d")
            time_end = last_day_this_month.strftime("%Y-%m-%d")
            sf_output.time_range["start"] = time_start
            sf_output.time_range["end"] = time_end
            logger.info(f"[SQLNode] 自动计算本月时间范围: {time_start} ~ {time_end}")

        # 尝试解析时间范围
        try:
            from datetime import datetime, timedelta
            import calendar

            # 解析当前时间范围的年份
            start_dt = datetime.strptime(time_start[:10], "%Y-%m-%d")
            end_dt = datetime.strptime(time_end[:10], "%Y-%m-%d")

            for compare_op in compare_ops:
                compare_type = compare_op.get("compare_type", "同比")

                if "环比" in compare_type or "上月" in compare_type or "QoQ" in compare_type:
                    # 环比：计算上月
                    first_day_this_month = start_dt.replace(day=1)
                    last_day_last_month = first_day_this_month - timedelta(days=1)
                    first_day_last_month = last_day_last_month.replace(day=1)

                    mom_start = first_day_last_month.strftime("%Y-%m-%d")
                    mom_end = last_day_last_month.strftime("%Y-%m-%d")

                    logger.info(
                        f"[SQLNode] 扩展时间范围(环比): 当前 {time_start} ~ {time_end}, "
                        f"上月 {mom_start} ~ {mom_end}"
                    )

                    sf_output.time_range["mom_start"] = mom_start
                    sf_output.time_range["mom_end"] = mom_end
                    logger.info(f"[SQLNode] 设置 mom_start={mom_start}, mom_end={mom_end}")
                else:
                    # 同比：计算去年同期（默认）
                    last_year_start = start_dt.replace(year=start_dt.year - 1)
                    last_year_end = end_dt.replace(year=end_dt.year - 1)

                    yoy_start = last_year_start.strftime("%Y-%m-%d")
                    yoy_end = last_year_end.strftime("%Y-%m-%d")

                    logger.info(
                        f"[SQLNode] 扩展时间范围(同比): 当前 {time_start} ~ {time_end}, "
                        f"去年同期 {yoy_start} ~ {yoy_end}"
                    )

                    sf_output.time_range["yoy_start"] = yoy_start
                    sf_output.time_range["yoy_end"] = yoy_end
                    logger.info(f"[SQLNode] 设置 yoy_start={yoy_start}, yoy_end={yoy_end}")

        except Exception as e:
            logger.warning(f"[SQLNode] 扩展时间范围失败: {e}")

    async def _generate_sql_with_llm(
        self,
        sf_output,
        sql_examples: list,
    ) -> SQLOutput:
        """使用 LLM 生成 SQL"""
        # 当有比较操作时，扩展时间范围
        self._expand_time_range_for_compare(sf_output)

        # 构建 Prompt
        prompt = self._build_sql_prompt(sf_output, sql_examples)

        # 调用 LLM
        logger.info(f"[SQLNode] 发送 Prompt: {prompt[:500]}...")
        response_text = await self._call_llm(prompt)
        logger.info(f"[SQLNode] LLM 响应: {response_text[:200]}...")

        # 解析响应
        sql_output = self._parse_llm_response(response_text, sf_output)
        
        # 检查并补充 GROUP BY（如果 LLM 未正确生成）
        if sf_output.dimensions and "GROUP BY" not in sql_output.sql.upper():
            logger.warning(f"[SQLNode] LLM 未生成 GROUP BY，尝试补充")
            sql_output = self._add_group_by(sql_output, sf_output)
        
        return sql_output


    def _add_group_by(self, sql_output: 'SQLOutput', sf_output) -> 'SQLOutput':
        """为 SQL 输出补充 GROUP BY 子句"""
        if not sf_output.dimensions:
            return sql_output
        
        # 获取维度列
        if isinstance(sf_output.dimensions, dict):
            group_by_cols = list(sf_output.dimensions.values())
        elif isinstance(sf_output.dimensions, list):
            dimension_map = self._config_loader.get_dimension_map()
            group_by_cols = []
            for dim in sf_output.dimensions:
                if dim in dimension_map:
                    group_by_cols.append(dimension_map[dim])
                else:
                    group_by_cols.append(dim)
        else:
            return sql_output
        
        if not group_by_cols:
            return sql_output
        
        group_by_str = ", ".join(group_by_cols)
        sql = sql_output.sql
        
        # 如果 SQL 中已有 GROUP BY，不处理
        if "GROUP BY" in sql.upper():
            return sql_output
        
        # 在 WHERE 或 FROM 后添加 GROUP BY
        sql = sql.rstrip().rstrip(';')
        if " WHERE " in sql.upper():
            # 在 WHERE 条件之后添加 GROUP BY
            # SQL 正确顺序: SELECT ... FROM ... WHERE ... GROUP BY ...
            # 我们需要在 " WHERE " 之后插入 " GROUP BY {cols}"
            where_pos = sql.upper().find(" WHERE ")
            before_where = sql[:where_pos]  # SELECT ... FROM ... (不包含 WHERE)
            where_and_conditions = sql[where_pos + 7:]  # FDATE >= ... AND FDATE <= ... (跳过 " WHERE ")
            sql = f"{before_where} WHERE {where_and_conditions} GROUP BY {group_by_str}"
        else:
            # 没有 WHERE，在末尾添加 GROUP BY
            sql = f"{sql} GROUP BY {group_by_str}"
        
        logger.info(f"[SQLNode] 补充 GROUP BY 后 SQL: {sql[:100]}...")
        return SQLOutput(
            sql=sql,
            sql_type=sql_output.sql_type,
            params=sql_output.params,
            has_comparison=sql_output.has_comparison,
            has_percentage=sql_output.has_percentage,
            table=sql_output.table,
        )

    def _generate_sql_with_template(self, sf_output) -> SQLOutput:
        """使用 QueryBuilder 模板生成 SQL"""
        # 直接使用 starrocks_sql 作为基础
        starrocks_sql = sf_output.starrocks_sql

        if not starrocks_sql:
            # 如果没有 starrocks_sql，生成简单的聚合 SQL
            metric_alias = sf_output.metric_name or "value"
            sql = f"SELECT SUM(ORDERED_PRODUCTSALES) AS `{metric_alias}` FROM {sf_output.table} WHERE 1=1"
            return SQLOutput(
                sql=sql,
                sql_type="query_value",
                params={},
                has_comparison=False,
                has_percentage=False,
                table=sf_output.table,
            )

        # 替换 1=1 为实际的条件
        time_start = sf_output.time_range.get("start", "")
        time_end = sf_output.time_range.get("end", "")

        # 构建 WHERE 条件列表
        where_conditions = []

        # 添加时间条件
        if time_start and time_end:
            where_conditions.append(f"FDATE >= '{time_start}' AND FDATE <= '{time_end}'")

        # 处理 filters（筛选条件）
        filters = sf_output.filters or []
        if isinstance(filters, dict):
            # filters 可能是 {'平台': 'B2B APP'} 格式，需要转换为 WHERE 条件
            for field_name, field_value in filters.items():
                # 将中文维度名转换为列名
                column_name = self._config_loader.get_column_name(field_name)
                if column_name:
                    # 如果值是列表，使用 IN；否则使用 =
                    if isinstance(field_value, list):
                        values_str = ", ".join(f"'{v}'" for v in field_value)
                        where_conditions.append(f"{column_name} IN ({values_str})")
                    else:
                        where_conditions.append(f"{column_name} = '{field_value}'")
                else:
                    logger.warning(f"[SQLNode] 未找到筛选字段映射: {field_name}")
        elif isinstance(filters, list):
            # filters 可能是 [{'field': 'PLATFORM', 'op': '=', 'value': 'B2B APP'}] 格式
            for f in filters:
                if isinstance(f, dict):
                    field = f.get("field", "")
                    op = f.get("op", "=")
                    value = f.get("value", "")
                    if field and value:
                        where_conditions.append(f"{field} {op} '{value}'")

        # 替换或添加 WHERE 条件
        if where_conditions:
            if "WHERE 1=1" in starrocks_sql.upper():
                sql = starrocks_sql.replace("WHERE 1=1", f"WHERE {' AND '.join(where_conditions)}")
            elif "WHERE" in starrocks_sql.upper():
                # 在 WHERE 后追加条件
                sql = starrocks_sql + f" AND {' AND '.join(where_conditions)}"
            else:
                # 没有 WHERE，添加 WHERE 子句
                sql = starrocks_sql + f" WHERE {' AND '.join(where_conditions)}"
        else:
            sql = starrocks_sql

        # 添加 GROUP BY（如果有维度）
        group_by_cols = []
        if sf_output.dimensions:
            # dimensions 可能是 dict 或 list
            if isinstance(sf_output.dimensions, dict):
                group_by_cols = list(sf_output.dimensions.values())
            elif isinstance(sf_output.dimensions, list):
                # 如果是 list，需要将中文维度名转换为列名
                dimension_map = self._config_loader.get_dimension_map()
                for dim in sf_output.dimensions:
                    if dim in dimension_map:
                        group_by_cols.append(dimension_map[dim])
                    else:
                        logger.warning(f"[SQLNode] 未找到维度映射: {dim}")

            if group_by_cols:
                # 检查 starrocks_sql 是否已有 GROUP BY
                if "GROUP BY" not in sql.upper():
                    # 需要在 SELECT 中添加维度列
                    # starrocks_sql 格式: SELECT SUM(metric) AS `alias` FROM ...
                    # 需要修改为: SELECT dim_col, SUM(metric) AS `alias` FROM ...
                    import re
                    # 匹配 SELECT ... SUM(...) AS `alias` 部分
                    select_pattern = r'(SELECT\s+)(SUM\([^)]+\)\s+AS\s+[`"\']?\w+[`"\']?)(.+)'
                    match = re.match(select_pattern, sql, re.IGNORECASE | re.DOTALL)
                    if match:
                        # 在 SUM() 前面添加维度列
                        sql = f"{match.group(1)}{', '.join(group_by_cols)}, {match.group(2)}{match.group(3)}"

                    sql = sql.rstrip().rstrip(';') + f" GROUP BY {', '.join(group_by_cols)}"

        # 处理 operations（排序、限制）
        order_by_added = False
        for op in sf_output.operations:
            if isinstance(op, dict) and op.get("type") == "order_by":
                # 尝试从 starrocks_sql 提取指标列用于排序
                order_field = "SUM(ORDERED_PRODUCTSALES)"
                # 尝试从 SQL 中提取聚合表达式
                import re
                sum_match = re.search(r'SUM\([^)]+\)\s+AS\s+[`"\']?(\w+)[`"\']?', starrocks_sql, re.IGNORECASE)
                if sum_match:
                    order_field = f"SUM({sum_match.group(1)})"
                order_dir = op.get("direction", "DESC")
                if "ORDER BY" not in sql.upper():
                    sql = sql + f" ORDER BY {order_field} {order_dir}"
                order_by_added = True
            if isinstance(op, dict) and op.get("type") == "limit":
                limit_val = op.get("value")
                # 只有当 limit_val 是有效数字时才添加 LIMIT 子句
                if limit_val is not None and isinstance(limit_val, (int, str)) and str(limit_val) != "None":
                    limit_num = int(limit_val) if str(limit_val).isdigit() else 10
                    if "LIMIT" not in sql.upper():
                        sql = sql + f" LIMIT {limit_num}"

        # 清理末尾的分号和空白
        sql = sql.rstrip().rstrip(';')

        return SQLOutput(
            sql=sql,
            sql_type="query_value",
            params={},
            has_comparison=False,
            has_percentage=False,
            table=sf_output.table,
        )

    def _build_rate_metric_sql(self, sf_output) -> SQLOutput:
        """
        构建率指标 SQL（支持 GROUP BY）

        例如: base_sql = "SUM(TRANSPORTATION)/SUM(INCOME_BCSS)"

        Args:
            sf_output: SF 节点输出

        Returns:
            SQLOutput: 构建好的 SQL
        """
        # 从 starrocks_sql 提取核心公式
        # starrocks_sql 格式: SELECT SUM(x)/SUM(y) AS `xxx` FROM ... WHERE 1=1
        # 需要提取出纯公式: SUM(x)/SUM(y)
        import re
        starrocks_sql = sf_output.starrocks_sql or ""

        # 用正则提取 SUM(x)/SUM(y) 公式
        formula_match = re.search(r'SUM\s*\(\s*\w+\s*\)\s*/\s*SUM\s*\(\s*\w+\s*\)', starrocks_sql, re.IGNORECASE)
        if formula_match:
            base_sql = formula_match.group()
            logger.info(f"[SQLNode] 提取率指标公式: {base_sql}")
        else:
            # 兜底：尝试清理完整 SQL
            base_sql = starrocks_sql
            if "WHERE" in base_sql:
                base_sql = base_sql.split("WHERE")[0].strip()
            if "GROUP BY" in base_sql:
                base_sql = base_sql.split("GROUP BY")[0].strip()
            if "ORDER BY" in base_sql:
                base_sql = base_sql.split("ORDER BY")[0].strip()
            # 移除 SELECT 和 FROM 之间的部分
            if "SELECT" in base_sql:
                parts = base_sql.split("SELECT")
                base_sql = parts[-1] if parts[-1].strip() else base_sql
            if "FROM" in base_sql:
                base_sql = base_sql.split("FROM")[0].strip()
            logger.warning(f"[SQLNode] 无法提取公式，使用清理后SQL: {base_sql}")

        dimensions = sf_output.dimensions or {}

        # 构建 SELECT 子句
        if dimensions:
            dim_cols = list(dimensions.values())
            select_clause = f"{', '.join(dim_cols)}, {base_sql} AS `比率`"
            group_by_clause = f"GROUP BY {', '.join(dim_cols)}"
        else:
            select_clause = base_sql
            group_by_clause = ""

        # 构建 WHERE 子句
        where_parts = []
        if sf_output.time_range.get("start"):
            where_parts.append(f"FDATE >= '{sf_output.time_range['start']}'")
        if sf_output.time_range.get("end"):
            where_parts.append(f"FDATE <= '{sf_output.time_range['end']}'")

        # 组合 SQL
        sql = f"SELECT {select_clause} FROM {sf_output.table}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        else:
            sql += " WHERE 1=1"
        if group_by_clause:
            sql += " " + group_by_clause

        logger.info(f"[SQLNode] 构建率指标 SQL: {sql[:200]}...")

        return SQLOutput(
            sql=sql,
            sql_type="query_value",
            params={},
            has_comparison=False,
            has_percentage=True,
            table=sf_output.table,
        )

    async def _try_build_dynamic_ratio_sql(self, sf_output) -> Optional[SQLOutput]:
        """
        尝试构建动态占比 SQL

        当用户问"X占Y的比例"但没有匹配到预定义指标时，
        通过指标字段映射表查找字段并构建 SQL

        Args:
            sf_output: SF 节点输出

        Returns:
            SQLOutput 或 None（无法构建时）
        """
        from ..metric_client import get_metric_client

        operations = sf_output.operations or []

        # 提取 base_metric 和 compare_metric
        base_metric = None
        compare_metric = None
        for op in operations:
            if isinstance(op, dict) and op.get("type") == "percentage":
                base_metric = op.get("base_metric")
                compare_metric = op.get("compare_metric")
                break

        # 如果缺失，尝试从问题文本解析
        if not base_metric or not compare_metric:
            resolved_question = sf_output.resolved_question or sf_output.original_question or ""
            ratio_match = re.search(r'在(.+?)中的占比', resolved_question)
            if ratio_match:
                compare_metric = ratio_match.group(1).strip()
                before_part = resolved_question[:ratio_match.start()]
                # 提取 base_metric
                metric_patterns = [
                    r'退款金额数量', r'退款金额', r'退款数量', r'退款额',
                    r'销量', r'销售额', r'销售量', r'收入', r'总收入', r'总营收',
                ]
                for pattern in metric_patterns:
                    if pattern in before_part:
                        base_metric = pattern
                        break

        if not base_metric or not compare_metric:
            logger.warning(f"[SQLNode] 无法提取 base/compare metric")
            return None

        # 查找字段映射
        metric_client = get_metric_client()
        mapping = metric_client.get_metric_field_mapping()

        base_field = mapping.get(base_metric, "")
        compare_field = mapping.get(compare_metric, "")

        if not base_field or not compare_field:
            logger.warning(f"[SQLNode] 未找到字段映射: {base_metric}→?, {compare_metric}→?")
            return None

        # 构建核心除法 SQL
        base_sql = f"SUM({base_field})/SUM({compare_field})"

        # 使用率指标 SQL 构建逻辑
        return self._build_rate_metric_sql_with_base(sf_output, base_sql)

    def _build_rate_metric_sql_with_base(self, sf_output, base_sql: str) -> SQLOutput:
        """
        使用指定的基础 SQL 构建率指标 SQL

        Args:
            sf_output: SF 节点输出
            base_sql: 基础 SQL，如 "SUM(a)/SUM(b)"

        Returns:
            SQLOutput
        """
        dimensions = sf_output.dimensions or {}

        # 构建 SELECT 子句
        if dimensions:
            dim_cols = list(dimensions.values())
            select_clause = f"{', '.join(dim_cols)}, {base_sql} AS `比率`"
            group_by_clause = f"GROUP BY {', '.join(dim_cols)}"
        else:
            select_clause = base_sql
            group_by_clause = ""

        # 构建 WHERE 子句
        where_parts = []
        if sf_output.time_range.get("start"):
            where_parts.append(f"FDATE >= '{sf_output.time_range['start']}'")
        if sf_output.time_range.get("end"):
            where_parts.append(f"FDATE <= '{sf_output.time_range['end']}'")

        # 组合 SQL
        sql = f"SELECT {select_clause} FROM {sf_output.table}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        else:
            sql += " WHERE 1=1"
        if group_by_clause:
            sql += " " + group_by_clause

        logger.info(f"[SQLNode] 构建动态占比 SQL: {sql[:200]}...")

        return SQLOutput(
            sql=sql,
            sql_type="query_value",
            params={},
            has_comparison=False,
            has_percentage=True,
            table=sf_output.table,
        )

    def _safe_format_template(self, template: str, vars: dict) -> str:
        """
        安全格式化模板，处理以下情况：
        1. 已知占位符 {var} → 替换为变量值
        2. 转义花括号 {{ }} → 替换为字面 { }
        3. 未知占位符（如 SQL 中的 {dimension}）→ 保持原样
        """
        # 第一步：将转义的花括号 {{ }} 替换为临时占位符
        ESCAPE_PLACEHOLDER = "\x00ESCAPE\x00"
        result = template.replace("{{", ESCAPE_PLACEHOLDER).replace("}}", ESCAPE_PLACEHOLDER)

        # 第二步：替换已知的占位符
        for key, value in vars.items():
            result = result.replace(f"{{{key}}}", str(value))

        # 第三步：将转义占位符替换回花括号
        result = result.replace(ESCAPE_PLACEHOLDER, "}")

        return result

    def _build_sql_prompt(self, sf_output, sql_examples: list) -> str:
        """构建 SQL 生成 Prompt"""
        # 获取维度映射
        dimension_map = self._config_loader.get_dimension_map()
        dimension_table = "\n".join(
            f"| {k} | {v} |" for k, v in dimension_map.items()
        )

        # 格式化 SQL 示例
        examples_text = self._sql_retriever.format_examples_for_prompt(sql_examples)

        # 解析 operations
        operations = sf_output.operations or []
        has_compare = any(
            isinstance(op, dict) and op.get("type") == "compare"
            for op in operations
        )
        has_percentage = any(
            isinstance(op, dict) and op.get("type") == "percentage"
            for op in operations
        )

        # 提取占比操作的分子分母
        base_metric = None
        compare_metric = None
        for op in operations:
            if isinstance(op, dict) and op.get("type") == "percentage":
                base_metric = op.get("base_metric")
                compare_metric = op.get("compare_metric")
                logger.info(f"[SQLNode] 提取到占比操作: base_metric={base_metric}, compare_metric={compare_metric}")
                break

        # 优先使用 operations 中的占比信息
        # 如果缺失，尝试从 resolved_question 或 original_question 中解析（关键词触发解析）
        resolved_question = sf_output.resolved_question or ""
        original_question = sf_output.original_question or ""

        # 关键：即使 has_percentage=False，如果问题包含"占比"关键词，也尝试解析
        # 优先使用 resolved_question（经过同义词替换的版本），如果为空则使用 original_question
        ratio_text = resolved_question if resolved_question else original_question
        should_parse_ratio = has_percentage or ("占比" in ratio_text or "比例" in ratio_text)

        if should_parse_ratio and (not base_metric or not compare_metric) and ratio_text:
            import re
            # 匹配占比模式
            # 格式1: "A在B中的占比" - 例如 "退款金额数量在销量中的占比"
            # 格式2: "A占B的比例" - 例如 "销售额占总收入的比例"
            # 格式3: "A在B中的比例" - 例如 "退款金额数量在销量中的比例"

            # 常见指标词模式（从右向左）
            metric_patterns = [
                r'退款金额数量', r'退款金额', r'退款数量', r'退款额',
                r'销量', r'销售额', r'销售量', r'收入', r'总收入', r'总营收',
                r'订单量', r'订单额', r'订单金额',
                r'访客量', r'访客数', r'浏览量', r'浏览数',
                r'转化率', r'点击率', r'利用率',
            ]

            def extract_base_compare(ratio_text: str):
                """从问题文本中提取分子和分母"""
                # 尝试格式1: "A在B中的占比"
                ratio_match = re.search(r'在(.+?)中的占比', ratio_text)
                if ratio_match:
                    compare_part = ratio_match.group(1).strip()
                    before_part = ratio_text[:ratio_match.start()]
                    # 从 before_part 提取指标词
                    for pattern in metric_patterns:
                        if pattern in before_part:
                            return pattern, compare_part
                    # 尝试后缀匹配
                    suffix_match = re.search(r'([\w\u4e00-\u9fa5]*?(?:数量|金额|额|率|比))$', before_part)
                    if suffix_match:
                        return suffix_match.group(1), compare_part
                    return None, compare_part

                # 尝试格式2: "A占B的比例"
                ratio_match = re.search(r'占(.+?)的比例', ratio_text)
                if ratio_match:
                    compare_part = ratio_match.group(1).strip()
                    before_part = ratio_text[:ratio_match.start()]
                    for pattern in metric_patterns:
                        if pattern in before_part:
                            return pattern, compare_part
                    suffix_match = re.search(r'([\w\u4e00-\u9fa5]*?(?:数量|金额|额|率|比))$', before_part)
                    if suffix_match:
                        return suffix_match.group(1), compare_part
                    return None, compare_part

                # 尝试格式3: "A在B中的比例"
                ratio_match = re.search(r'在(.+?)中的比例', ratio_text)
                if ratio_match:
                    compare_part = ratio_match.group(1).strip()
                    before_part = ratio_text[:ratio_match.start()]
                    for pattern in metric_patterns:
                        if pattern in before_part:
                            return pattern, compare_part
                    suffix_match = re.search(r'([\w\u4e00-\u9fa5]*?(?:数量|金额|额|率|比))$', before_part)
                    if suffix_match:
                        return suffix_match.group(1), compare_part
                    return None, compare_part

                return None, None

            extracted_base, extracted_compare = extract_base_compare(ratio_text)
            logger.info(f"[SQLNode] 从问题文本解析占比: base={extracted_base}, compare={extracted_compare}")
            if not base_metric and extracted_base:
                base_metric = extracted_base
            if not compare_metric and extracted_compare:
                compare_metric = extracted_compare

        # 关键：如果解析到了 base_metric 和 compare_metric，更新 has_percentage 标志
        if not has_percentage and base_metric and compare_metric:
            has_percentage = True
            logger.info(f"[SQLNode] 通过解析更新 has_percentage=True")

        # 构建衍生指标要求
        compare_requirement = "无对比计算"
        if has_percentage and base_metric and compare_metric:
            percentage_requirement = f"""需要生成占比计算：
- 分子：{base_metric}（需要 SUM 聚合）
- 分母：{compare_metric}（需要 SUM 聚合）
- 格式：SUM({base_metric}) / SUM({compare_metric})
- 必须添加 ROUND(..., 2) 保留两位小数
- 分子分母都必须是 SUM 聚合"""
        elif has_percentage:
            percentage_requirement = """需要生成占比计算（两个指标相除）：
- 格式：SUM(分子指标) / SUM(分母指标)
- 示例：退款率 = SUM(fqty_tk) / SUM(ORDER_QTY)
- 必须添加 ROUND(..., 2) 保留两位小数
- 分子分母都必须是 SUM 聚合，不能遗漏任何一个"""
        else:
            percentage_requirement = "无占比计算"


        # 如果有比较操作，在要求中说明时间范围扩展
        # 支持同时处理同比和环比
        if has_compare:
            logger.info(f"[SQLNode] 检测到 has_compare=True, operations={operations}")
            yoy_start = sf_output.time_range.get('yoy_start', '')
            yoy_end = sf_output.time_range.get('yoy_end', '')
            mom_start = sf_output.time_range.get('mom_start', '')
            mom_end = sf_output.time_range.get('mom_end', '')

            current_start = sf_output.time_range.get('start', '')
            current_end = sf_output.time_range.get('end', '')

            # 检查有哪些比较类型
            compare_types = set()
            for op in operations:
                if isinstance(op, dict) and op.get("type") == "compare":
                    ct = op.get("compare_type", "同比")
                    if "环比" in ct or "上月" in ct or "QoQ" in ct:
                        compare_types.add("环比")
                    else:
                        compare_types.add("同比")
                elif op == "compare":
                    compare_types.add("同比")

            logger.info(f"[SQLNode] compare_types: {compare_types}")

            compare_requirement_parts = []

            # 调试日志
            logger.info(f"[SQLNode] compare_types: {compare_types}, yoy_start={yoy_start}, yoy_end={yoy_end}, mom_start={mom_start}, mom_end={mom_end}")

            # 构建同比要求
            if "同比" in compare_types and yoy_start and yoy_end:
                compare_requirement_parts.append(
                    f"【同比计算】需要生成同比计算（对比去年同期）。"
                    f"当前周期（{current_start} ~ {current_end}），去年同期（{yoy_start} ~ {yoy_end}）。"
                    f"使用 JOIN 方式，ON 条件为 t1.MONTHS = t2.MONTHS（月份匹配）。"
                )

            # 构建环比要求
            if "环比" in compare_types and mom_start and mom_end:
                compare_requirement_parts.append(
                    f"【环比计算】需要生成环比计算（对比上一周期）。"
                    f"当前周期（{current_start} ~ {current_end}），上一周期（{mom_start} ~ {mom_end}）。"
                    f"使用 JOIN 方式，ON 条件为 t1.MONTHS = t2.MONTHS（月份匹配）。"
                )

            if compare_requirement_parts:
                compare_requirement = "\n".join(compare_requirement_parts)
                logger.info(f"[SQLNode] compare_requirement_parts: {compare_requirement_parts}")
            else:
                compare_requirement = "需要生成同比和/或环比计算，使用 JOIN 方式连接两个时间周期的聚合结果。"
                logger.warning(f"[SQLNode] compare_requirement_parts 为空，使用默认描述")

        # 准备模板变量
        # dimensions 字典的 values 是数据库列名（如 "FDATE"），keys 是中文维度名（如"日期"）
        # 但 prompt 中需要使用列名用于 SQL 生成
        dimension_cols = list(sf_output.dimensions.values()) if sf_output.dimensions else []
        dimension_keys = list(sf_output.dimensions.keys()) if sf_output.dimensions else []
        template_vars = {
            "metric_name": sf_output.metric_name or "",
            "metric_code": sf_output.metric_code or "",
            "dimensions": ", ".join(dimension_cols),  # 使用列名而非中文名
            "dimension_keys": ", ".join(dimension_keys),  # 中文维度名
            "dimension_column": dimension_cols[0] if dimension_cols else "",  # 第一个维度列名
            "time_range_original": sf_output.time_range.get('original', ''),
            "time_range_start": sf_output.time_range.get('start', ''),
            "time_range_end": sf_output.time_range.get('end', ''),
            "aggregations": str(sf_output.aggregations),
            "operations": str([{"type": op.get('type'), "value": op.get('value')} if isinstance(op, dict) else op for op in operations]),
            "starrocks_sql": sf_output.starrocks_sql or 'SELECT SUM(...) FROM table WHERE 1=1',
            "dimension_table": dimension_table,
            "sql_examples": examples_text,
            "compare_requirement": compare_requirement,
            "percentage_requirement": percentage_requirement,
            "has_compare": "true" if has_compare else "false",
            "has_percentage": "true" if has_percentage else "false",
        }

        # 尝试从数据库加载 prompt
        prompt_template = self._config_loader.get_prompt_template("llm_v1_sql")
        if prompt_template and prompt_template.content:
            try:
                prompt = self._safe_format_template(prompt_template.content, template_vars)
                return prompt
            except Exception as e:
                logger.warning(f"[SQLNode] 格式化 prompt 失败: {e}，使用默认 prompt")

        # 降级到硬编码的默认 prompt
        # 使用 _safe_format_template 替换所有占位符（包括 {dimension_column}）
        default_prompt = """你是一个 SQL 生成专家。根据槽位信息生成 StarRocks SQL。

## 槽位信息

- 指标名称：{metric_name}
- 指标代码：{metric_code}
- 维度：{dimension_keys}
- 时间范围：{time_range_original}（{time_range_start} ~ {time_range_end}）
- 聚合方式：{aggregations}
- 操作类型：{operations}

## 基础 SQL 模板

{starrocks_sql}

## 维度映射表

| 中文维度名 | 数据库列名 |
|-----------|-----------|
{dimension_table}

## SQL 示例

{sql_examples}

## 生成要求

1. **维度处理**：
   - 所有中文维度名必须转换为数据库列名
   - **重要：当有维度时，SQL 必须包含 GROUP BY {dimension_column}**
   - 例如：维度为"日期"时 → GROUP BY FDATE
2. **时间条件**：使用 FDATE 字段，格式 YYYY-MM-DD
3. **衍生指标**：
   - {compare_requirement}
   - {percentage_requirement}
4. **输出格式**：直接返回 JSON

## 输出格式

{{
  "sql": "SELECT ... FROM ...",
  "params": {{}},
  "sql_type": "query_value|query_ranking|query_trend",
  "has_comparison": {has_compare},
  "has_percentage": {has_percentage}
}}

现在请生成 SQL：
"""
        prompt = self._safe_format_template(default_prompt, template_vars)
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        from ..llm_client import get_llm_client

        llm_client = get_llm_client()
        return await llm_client.call(prompt, temperature=0.7, max_tokens=4000)

    def _parse_llm_response(self, response_text: str, sf_output) -> SQLOutput:
        """解析 LLM 输出"""
        import json

        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return SQLOutput(
                    sql=data.get("sql", ""),
                    sql_type=data.get("sql_type", "query_value"),
                    params=data.get("params", {}),
                    has_comparison=data.get("has_comparison", False),
                    has_percentage=data.get("has_percentage", False),
                    table=sf_output.table,
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[SQLNode] 解析 LLM 响应失败: {e}")

        # 解析失败，使用模板兜底
        logger.warning("[SQLNode] LLM 解析失败，使用模板兜底")
        return self._generate_sql_with_template(sf_output)


# 全局实例
_sql_node: Optional[SQLNode] = None


def get_sql_node() -> SQLNode:
    """获取 SQL 节点单例"""
    global _sql_node
    if _sql_node is None:
        _sql_node = SQLNode()
    return _sql_node
