"""
Report Generator Node - 多指标下钻分析报告生成器

用于四类下钻（sales/ad/inventory/cost）的多指标 SQL 执行和 LLM 分析报告生成。
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from ai.config.runtime import get_go_api_base
from ai.engine.llm import get_llm_engine
from ai.engine.llm_v2.nodes.sql_executor import SQLExecutor
from ai.engine.prompt_manager import get_prompt_manager
from ai.engine.llm_v2.schema import MQLFilter, OperatorType

logger = logging.getLogger(__name__)


class ReportGeneratorNode:
    """多指标下钻分析报告生成节点"""

    def __init__(self):
        self._prompt_manager = get_prompt_manager()
        self._llm_engine = get_llm_engine()
        self._sql_executor = SQLExecutor()

        # 指标类型后缀规则
        self.metric_type_rules = {
            "mom": "环比上期绝对值",
            "mom_rate": "环比上期变化率(%)",
            "yoy": "同比去年同期绝对值",
            "yoy_rate": "同比去年同期变化率(%)",
            "target": "月度目标值",
            "target_rate": "目标达成率(%)",
            "best": "历史最佳值",
        }

        # 衍生指标集合
        self.derived_metrics = {
            "客单价", "毛利率", "广告产出比", "点击转化率",
            "广告转化率", "库存周转率", "平台边际贡献额率",
        }

    def _generate_metric_description(self, metric_names: List[str]) -> str:
        """
        动态生成指标类型说明，帮助 LLM 理解指标的后缀含义。

        Args:
            metric_names: 指标名列表

        Returns:
            格式化的指标说明字符串
        """
        base, derived, comparison = [], [], []

        for metric in metric_names:
            # 识别对比指标（通过后缀）
            matched = False
            for suffix, desc in self.metric_type_rules.items():
                suffix_with_underscore = f"_{suffix}"
                if metric.endswith(suffix_with_underscore):
                    base_name = metric[: -len(suffix_with_underscore)]
                    comparison.append(f"- {metric}：{base_name}的{desc}")
                    matched = True
                    break
            if matched:
                continue

            # 识别衍生指标
            if metric in self.derived_metrics:
                derived.append(f"- {metric}：衍生业务指标")
                continue

            # 基础指标
            base.append(f"- {metric}：基础业务指标")

        desc = "【数据指标说明】\n"

        if base:
            desc += "1. 基础指标（原始统计数据）：\n" + "\n".join(base) + "\n\n"
        if derived:
            desc += "2. 衍生指标（通过公式计算得出）：\n" + "\n".join(derived) + "\n\n"
        if comparison:
            desc += "3. 对比指标（与其他时间/基准对比）：\n" + "\n".join(comparison) + "\n\n"

        desc += "【重要提示】所有指标均已提前计算完成，请勿自行进行任何数学运算，直接使用给出的数值即可。"

        return desc

    def _validate_llm_response(self, raw_response: str) -> Dict[str, Any]:
        """
        校验 LLM 返回的 JSON 是否合法，失败时返回降级结果。

        Args:
            raw_response: LLM 原始返回字符串

        Returns:
            解析后的字典，失败时返回降级分析
        """
        try:
            # 去掉 markdown fences（如 ```json ... ```）
            text = raw_response.strip()
            if text.startswith("```"):
                # 去掉 ```json 或 ``` 等 fenced code block 开始标记
                text = text.split("\n", 1)[1] if "\n" in text else text
                text = text.strip()
            if text.endswith("```"):
                text = text[:-3].strip()

            data = json.loads(text)

            # 校验必需字段
            if not isinstance(data.get("issues"), list):
                data["issues"] = []
            if not isinstance(data.get("highlights"), list):
                data["highlights"] = []
            if not isinstance(data.get("action_items"), list):
                data["action_items"] = []

            # 重新计算 health_score（基于 issues 和 highlights）
            data["health_score"] = self._calculate_health_score(
                data.get("issues", []),
                data.get("highlights", [])
            )

            return data

        except json.JSONDecodeError as e:
            logger.warning(f"[ReportGenerator] LLM response JSON parse failed: {e}")
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self) -> Dict[str, Any]:
        """LLM 解析失败时的降级分析"""
        return {
            "summary": "数据已返回，请查看各指标详情。",
            "health_score": 50,
            "top_urgent_action": "建议检查各指标数据",
            "issues": [],
            "highlights": [],
            "action_items": [
                {"text": "查看各指标明细数据", "priority": "P1", "type": "normal"}
            ],
        }

    def _calculate_health_score(self, issues: List[Dict], highlights: List[Dict]) -> int:
        """
        根据 issues 和 highlights 量化计算 health_score。

        规则：
        - 基础分：80分
        - 每个P0问题扣20分
        - 每个P1问题扣10分
        - 每个P2问题扣5分
        - 每个亮点加5分（最多加10分）
        - 最低0分，最高100分
        - 最终得分取整数
        """
        # 统计各优先级 issues 数量
        p0_count = sum(1 for i in issues if i.get("priority") == "P0")
        p1_count = sum(1 for i in issues if i.get("priority") == "P1")
        p2_count = sum(1 for i in issues if i.get("priority") == "P2")

        # 计算扣分
        deductions = p0_count * 20 + p1_count * 10 + p2_count * 5

        # 计算加分（亮点最多加10分）
        highlight_bonus = min(len(highlights) * 5, 10)

        # 最终得分
        score = 80 - deductions + highlight_bonus

        # 限制范围
        score = max(0, min(100, score))

        logger.info(
            f"[ReportGenerator] health_score计算: 基础80 - P0({p0_count})*20 - P1({p1_count})*10 - P2({p2_count})*5 "
            f"+ 亮点({len(highlights)})*5 = {score}"
        )

        return score

    async def _load_drilldown_templates(self, category: str) -> List[Dict]:
        """
        从数据库加载 drilldown 模板。

        调用 Go 后端 API 获取 sql_templates 表中：
        - template_type = 'drilldown'
        - drilldown_category = category
        - 按 template_order 排序

        Args:
            category: 下钻类别 (sales/ad/inventory/cost)

        Returns:
            模板列表
        """
        import httpx

        logger.info(f"[ReportGenerator] Loading drilldown templates for category: {category}")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{get_go_api_base()}/api/v1/nlp/sql-templates",
                    params={
                        "type": "drilldown",
                        "drilldown_category": category
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    # 防御性检查：确保 data 和 data["data"] 都是有效列表
                    if data is None:
                        logger.warning(f"[ReportGenerator] API returned None JSON")
                        return []
                    templates = data.get("data")
                    if templates is None:
                        templates = []
                    if not isinstance(templates, list):
                        logger.warning(f"[ReportGenerator] templates is not a list: {type(templates)}")
                        return []
                    logger.info(f"[ReportGenerator] Loaded {len(templates)} templates for category: {category}")
                    return templates
                else:
                    logger.warning(
                        f"[ReportGenerator] Failed to load templates: status={response.status_code}"
                    )
                    return []

        except Exception as e:
            logger.warning(f"[ReportGenerator] Error loading drilldown templates: {e}")
            return []

    async def generate_drilldown_sqls(
        self, category: str, time_range: Dict[str, str], inherited_mql: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        生成下钻 SQL 语句列表。

        Args:
            category: 下钻类别
            time_range: 时间范围 {"start": "2024-01-01", "end": "2024-01-31"}
            inherited_mql: 继承的 MQL（包含 filters 和 dimensions）

        Returns:
            SQL 配置列表 [{"sql": "...", "template_name": "...", "metric_names": [...]}]
        """
        templates = await self._load_drilldown_templates(category)
        if not templates:
            logger.warning(f"[ReportGenerator] No templates found for category: {category}")
            return []

        # 从 inherited_mql 构建维度 filter 字符串
        dim_filter = ""
        if inherited_mql:
            filter_conditions = []
            seen = set()
            # 从 filters 提取
            if hasattr(inherited_mql, 'filters') and inherited_mql.filters:
                for f in inherited_mql.filters:
                    field = getattr(f, 'field', None)
                    value = getattr(f, 'value', None)
                    operator = getattr(f.operator, 'value', 'eq') if hasattr(f, 'operator') else 'eq'
                    if not field or value is None:
                        continue
                    key = f"{field}:{value}"
                    if key in seen:
                        continue
                    seen.add(key)
                    op_str = "=" if operator == "eq" else operator
                    filter_conditions.append(f"{field} {op_str} '{value}'")
            # 从 dimensions 提取
            if hasattr(inherited_mql, 'dimensions') and inherited_mql.dimensions:
                for d in inherited_mql.dimensions:
                    if getattr(d, 'value', None) and getattr(d, 'column', None):
                        key = f"{d.column}:{d.value}"
                        if key in seen:
                            continue
                        seen.add(key)
                        filter_conditions.append(f"{d.column} = '{d.value}'")
            if filter_conditions:
                dim_filter = " AND ".join(filter_conditions)
                logger.info(f"[ReportGenerator] 维度 filter: {dim_filter}")

        results = []
        for tpl in templates:
            sql = tpl.get("sql_template", "")
            start = time_range.get("start", "")
            end = time_range.get("end", "")

            # ✶ 修复日期替换：匹配模板实际格式
            # 数据库模板使用双引号格式: "{start_date}" 和 "{end_date}"
            # 先去掉已有的引号，再添加正确的单引号
            start_clean = start.strip("'\"") if start else ""
            end_clean = end.strip("'\"") if end else ""

            # 替换双引号格式 (模板实际格式)
            sql = sql.replace('"{start_date}"', f"'{start_clean}'")
            sql = sql.replace('"{end_date}"', f"'{end_clean}'")
            # 替换单引号转义格式 (以防万一)
            sql = sql.replace("''{start_date}''", f"'{start_clean}'")
            sql = sql.replace("''{end_date}''", f"'{end_clean}'")
            # 替换无引号格式
            sql = sql.replace("{start_date}", f"'{start_clean}'")
            sql = sql.replace("{end_date}", f"'{end_clean}'")

            # ✶ 修复：替换维度 filter 占位符
            # 模板格式: WHERE FDATE >= "{start_date}" AND FDATE <= "{end_date}" AND\n   {dimension_filter}\n
            # 当 dim_filter 为空时，完整移除 "AND\n   {dimension_filter}" 及后续换行
            if dim_filter:
                sql = sql.replace("{dimension_filter}", dim_filter)
            else:
                # 移除 " AND\n   {dimension_filter}" 及其后面的换行符
                # 使用正则处理各种空白字符组合
                import re
                # 匹配 " AND" 后面跟各种空白字符，然后是 {dimension_filter}，最后是换行
                sql = re.sub(r' AND\s+\{dimension_filter\}\s*\n', '\n', sql)
                sql = re.sub(r' AND\s+\{dimension_filter\}', '', sql)

            raw_metric_names = tpl.get("metric_names")
            metric_names = raw_metric_names if isinstance(raw_metric_names, list) else (raw_metric_names or [])

            results.append(
                {
                    "sql": sql,
                    "template_name": tpl.get("template_name", ""),
                    "metric_names": metric_names,
                }
            )

        logger.info(f"[ReportGenerator] Generated {len(results)} SQLs for category: {category}")
        return results

    def _inject_filters_to_cte_sql(self, sql: str, filters: List[Any]) -> str:
        """将 filters 注入到 CTE SQL 的每个 TABLE WHERE 子句

        对于 CTE 模板（如 base_data, mom, yoy），每个 FROM ... WHERE 后面都需要加 filter。
        """
        if not filters:
            logger.info(f"[_inject_filters_to_cte_sql] 无 filters，直接返回原始 SQL")
            return sql

        # 构建 filter 条件字符串（去重）
        filter_conditions = []
        seen_filters = set()
        for f in filters:
            field = f.field if hasattr(f, 'field') else None
            value = f.value if hasattr(f, 'value') else None
            operator = f.operator.value if hasattr(f, 'operator') and hasattr(f.operator, 'value') else 'eq'
            if not field or value is None:
                continue
            # 去重
            filter_key = f"{field}:{value}"
            if filter_key in seen_filters:
                continue
            seen_filters.add(filter_key)
            op_str = "=" if operator == "eq" else operator
            filter_conditions.append(f"{field} {op_str} '{value}'")

        if not filter_conditions:
            logger.info(f"[_inject_filters_to_cte_sql] 无有效 filter 条件，直接返回原始 SQL")
            return sql

        filter_clause = " AND ".join(filter_conditions)
        logger.info(f"[_inject_filters_to_cte_sql] 原始 SQL:\n{sql}\n{'='*80}")
        logger.info(f"[_inject_filters_to_cte_sql] 注入 filter: {filter_clause}")

        import re

        # 策略：找到每个 CTE 的 ) 括号，在它前面插入 AND filter
        # 匹配 CTE 结束括号前的位置：\n  ) 或 \n)
        result = sql

        # 找所有 CTE 定义块，在其结束 ) 前插入 filter
        # 匹配模式：\n  GROUP BY ...\n) 或 \n  WHERE ...\n)
        # 注意：括号前可能有空格，也可能没有

        def replace_cte_end(match):
            """在 CTE 结束括号前插入 filter"""
            before_paren = match.group(1)  # CTE 块的内容
            paren = match.group(2)  # 括号及前面可能的空格
            # 在结束括号前插入 filter
            return before_paren + " AND " + filter_clause + paren

        # 匹配：WHERE 或 GROUP BY 行，在其结束位置（换行符前）插入 filter
        # 问题：对于 "WHERE FDATE >= ... GROUP BY ASIN" 这种单行 WHERE，
        # 原正则会错误匹配到 GROUP BY 行
        # 解决：分别处理 WHERE 和 GROUP BY，只在 WHERE 行末尾添加

        # 先处理 WHERE 行：在 WHERE ... 换行之前插入 AND filter
        result = re.sub(
            r'(\bWHERE\b[^\n]*)(\n)',
            lambda m: m.group(1) + " AND " + filter_clause + m.group(2),
            result,
            flags=re.IGNORECASE
        )

        # 再处理 GROUP BY 行前面的 WHERE 块结束位置（如果有换行分隔的话）
        # 使用非贪婪匹配在 GROUP BY 前的第一个 ) 之前插入
        # 但要避免重复注入（检查是否已有 filter）
        if filter_clause not in result:
            result = re.sub(
                r'(\n\s*(?:WHERE|GROUP BY).*?)(\n\s*\))',
                replace_cte_end,
                result,
                flags=re.IGNORECASE | re.DOTALL
            )

        logger.info(f"[_inject_filters_to_cte_sql] 注入后 SQL:\n{result}\n{'='*80}")
        return result

    async def execute_all_templates(
        self, category: str, time_range: Dict[str, str], inherited_mql: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        并行执行该 category 下所有模板，返回结构化数据。

        Args:
            category: 下钻类别
            time_range: 时间范围
            inherited_mql: 继承的 MQL（包含 filters 等上下文）

        Returns:
            结构化数据，包含基础指标和维度下钻数据
            {
                "scalar_metrics": {"销售额": 315740886, ...},  # 基础指标（来自 base 模板）
                "by_site": [{"站点": "jd", "销售额": 120M}, ...],       # 站点维度
                "by_category": [{"一级品类": "electronics", "销售额": 200M}, ...],  # 品类维度
                "by_platform": [...],  # 平台维度
                "by_asin": [...]       # ASIN 维度
            }
        """
        sql_configs = await self.generate_drilldown_sqls(category, time_range, inherited_mql)
        if not sql_configs:
            return {}

        async def execute_single(item: Dict[str, Any]) -> Dict[str, Any]:
            """执行单个 SQL 模板，返回全部数据行"""
            try:
                sql = item["sql"]
                # {dimension_filter} 已在 generate_drilldown_sqls 中替换
                logger.info(f"[ReportGenerator] 执行 SQL:\n{sql}\n{'='*80}")
                result = await self._sql_executor.execute(sql)
                if result and result.data:
                    return {
                        "template_name": item["template_name"],
                        "rows": result.data,
                    }
                return {"template_name": item["template_name"], "rows": []}
            except Exception as e:
                logger.warning(
                    f"[ReportGenerator] SQL execution failed: {item['sql'][:500]}... Error: {e}"
                )
                return {"template_name": item["template_name"], "rows": []}

        # asyncio.gather 并行执行所有模板
        results = await asyncio.gather(*[execute_single(item) for item in sql_configs])

        # 分离基础模板和维度模板
        scalar_metrics = {}
        dimensional_data = {
            "by_site": [],
            "by_category": [],
            "by_platform": [],
            "by_asin": [],
        }

        # 维度映射：模板名 → 维度 key
        dimension_mapping = {
            "站点下钻": "by_site",
            "一级品类下钻": "by_category",
            "平台下钻": "by_platform",
            "ASIN下钻": "by_asin",
        }

        for res in results:
            tpl_name = res.get("template_name", "")
            rows = res.get("rows", [])
            if not rows:
                continue

            dim_key = dimension_mapping.get(tpl_name)
            if dim_key:
                # 维度下钻数据：取前10行
                dimensional_data[dim_key] = rows[:10]
            else:
                # 基础模板：取第一行合并到标量指标
                if rows:
                    scalar_metrics.update(rows[0])

        logger.info(
            f"[ReportGenerator] Executed {len(sql_configs)} templates, "
            f"scalar_metrics={len(scalar_metrics)}, scalar_keys={list(scalar_metrics.keys())[:10]}, "
            f"dimensional_data keys={list(dimensional_data.keys())}, "
            f"by_site rows={len(dimensional_data['by_site'])}, "
            f"by_category rows={len(dimensional_data['by_category'])}"
        )
        return {
            "scalar_metrics": scalar_metrics,
            "dimensional_data": dimensional_data,
        }

    async def generate_analysis(
        self,
        multi_metric_data: Dict[str, Any],
        category: str,
        time_range: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        调用 LLM 生成分析报告。

        Args:
            multi_metric_data: 结构化数据，包含 scalar_metrics 和 dimensional_data
            category: 下钻类别
            time_range: 时间范围

        Returns:
            分析报告字典
        """
        prompt_name = f"drilldown_analysis_{category}"

        # 防御性检查：确保 multi_metric_data 是有效字典
        if not isinstance(multi_metric_data, dict) or not multi_metric_data:
            logger.warning(f"[ReportGenerator] multi_metric_data is empty or not a dict: {type(multi_metric_data)}")
            return self._get_fallback_analysis()

        prompt = self._prompt_manager.get_prompt(prompt_name)

        # 构建数据描述文本
        scalar_metrics = multi_metric_data.get("scalar_metrics", {})
        dimensional_data = multi_metric_data.get("dimensional_data", {})
        logger.info(f"[ReportGenerator] scalar_metrics keys={list(scalar_metrics.keys())[:10]}")
        logger.info(f"[ReportGenerator] dim data: by_site={len(dimensional_data.get('by_site',[]))} rows, by_category={len(dimensional_data.get('by_category',[]))} rows")

        if not prompt:
            logger.warning(f"[ReportGenerator] Prompt not found: {prompt_name}")
            return self._get_fallback_analysis()

        # 解析结构化数据
        scalar_metrics = multi_metric_data.get("scalar_metrics", {})
        dimensional_data = multi_metric_data.get("dimensional_data", {})

        # 构建数据描述文本（改进格式，便于LLM横向比较）
        data_parts = []

        # 1. 基础指标（格式化为键值对，便于LLM快速定位）
        if scalar_metrics:
            base_lines = [f"  {k}: {v}" for k, v in scalar_metrics.items()]
            data_parts.append("【基础指标】\n" + "\n".join(base_lines))

        # 2. 维度下钻数据（带列名表头，便于LLM读表格）
        # 硬编码列顺序，与SQL模板的SELECT顺序保持一致
        dim_labels = {
            "by_site": "站点",
            "by_category": "一级品类",
            "by_platform": "平台",
            "by_asin": "ASIN",
        }

        # 每个维度类型的固定列顺序（与SQL模板SELECT顺序一致）
        # 注意：第一个是维度名称列，后面是指标列
        dim_col_order = {
            "by_site": ["站点", "站点编码", "销售额", "销售额占比", "总订单数", "订单量", "B2B订单量", "总销量", "退款量", "国内收入", "跨境收入", "客单价", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"],
            "by_category": ["一级品类", "销售额", "销售额占比", "总订单数", "订单量", "B2B订单量", "国内收入", "跨境收入", "国内收入占比", "跨境收入占比", "客单价", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"],
            "by_platform": ["平台", "销售额", "销售额占比", "总订单数", "订单量", "B2B订单量", "国内收入", "跨境收入", "客单价", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"],
            "by_asin": ["ASIN", "销售额", "销售额占比", "总订单数", "订单量", "退款量", "客单价", "退款率", "销售额_mom_rate", "订单量_mom_rate", "销售额_yoy_rate", "订单量_yoy_rate"],
        }

        for dim_key, dim_label in dim_labels.items():
            rows = dimensional_data.get(dim_key, [])
            if rows:
                # 使用预定义的列顺序
                dim_col_names = dim_col_order.get(dim_key, [])
                # 过滤出实际存在于行数据中的列
                dim_col_names = [c for c in dim_col_names if c in rows[0].keys()]
                # 表头
                header = "  " + " | ".join([dim_label] + dim_col_names)
                sep = "  " + " | ".join(["-" * max(4, len(dim_label))] + ["-" * max(6, len(c)) for c in dim_col_names])
                lines = [f"【{dim_label}排名 TOP{len(rows)}】", header, sep]
                for i, row in enumerate(rows, 1):
                    vals = [str(row.get(c, "-")) for c in dim_col_names]
                    # 取前5个维度展示（避免太长）
                    if i <= 5:
                        lines.append(f"  {row.get(dim_col_names[0], '')} | " + " | ".join(vals))
                if len(rows) > 5:
                    lines.append(f"  ... (共{len(rows)}个，仅展示TOP5)")
                data_parts.append("\n".join(lines))

        data_str = "\n\n".join(data_parts)
        logger.info(f"[ReportGenerator] data_str for LLM:\n{data_str[:2000]}")
        prompt = prompt.replace("{{data}}", data_str)
        prompt = prompt.replace("{{start_date}}", time_range.get("start", ""))
        prompt = prompt.replace("{{end_date}}", time_range.get("end", ""))
        prompt = prompt.replace("{{category}}", category)

        # 动态生成指标说明
        all_metric_names = list(scalar_metrics.keys())
        metric_desc = self._generate_metric_description(all_metric_names)
        prompt = prompt.replace("{{metric_description}}", metric_desc)

        # 调用 LLM
        raw_response = await self._llm_engine.generate(prompt)

        # 校验 LLM 输出
        validated = self._validate_llm_response(raw_response)

        logger.info(
            f"[ReportGenerator] Generated analysis for category {category}: "
            f"{len(validated.get('issues', []))} issues, "
            f"{len(validated.get('highlights', []))} highlights"
        )
        return validated

    def format_multi_metric_data(
        self, merged_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        格式化多指标数据，供前端图表渲染。

        Args:
            merged_data: 结构化数据（来自 execute_all_templates）

        Returns:
            格式化后的数据列表 [{"metricName": "销售额", "data": [...]}]
        """
        # 支持旧格式（扁平字典）兼容
        if isinstance(merged_data, list):
            return merged_data

        scalar_metrics = merged_data.get("scalar_metrics", {})
        result = []
        for metric_name, value in scalar_metrics.items():
            result.append({"metricName": metric_name, "data": [{"value": value}]})
        return result

    def get_dimensional_data(
        self, merged_data: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取维度下钻数据，供前端渲染排名图表。

        Args:
            merged_data: 结构化数据（来自 execute_all_templates）

        Returns:
            维度数据 {"by_site": [...], "by_category": [...], ...}
        """
        if isinstance(merged_data, list):
            return {}
        return merged_data.get("dimensional_data", {})
