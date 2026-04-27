"""
Report Generator Node - 多指标下钻分析报告生成器

用于四类下钻（sales/ad/inventory/cost）的多指标 SQL 执行和 LLM 分析报告生成。
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from ai.engine.llm import get_llm_engine
from ai.engine.llm_v2.nodes.sql_executor import SQLExecutor
from ai.engine.prompt_manager import get_prompt_manager

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

            # 确保 health_score 存在
            if "health_score" not in data:
                data["health_score"] = 50  # 默认值

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
                    "http://localhost:8080/api/v1/nlp/sql-templates",
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
        self, category: str, time_range: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        生成下钻 SQL 语句列表。

        Args:
            category: 下钻类别
            time_range: 时间范围 {"start": "2024-01-01", "end": "2024-01-31"}

        Returns:
            SQL 配置列表 [{"sql": "...", "template_name": "...", "metric_names": [...]}]
        """
        templates = await self._load_drilldown_templates(category)
        if not templates:
            logger.warning(f"[ReportGenerator] No templates found for category: {category}")
            return []

        results = []
        for tpl in templates:
            sql = tpl.get("sql_template", "")
            start = time_range.get("start", "")
            end = time_range.get("end", "")
            # 处理 ''{start_date}'' 格式（数据库模板中使用了双单引号）
            sql = sql.replace("''{start_date}''", f"'{start}'")
            sql = sql.replace("''{end_date}''", f"'{end}'")
            # 同时处理普通格式 {start_date}
            sql = sql.replace("{start_date}", start)
            sql = sql.replace("{end_date}", end)

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

    async def execute_all_templates(
        self, category: str, time_range: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        并行执行该 category 下所有模板，返回结构化数据。

        Args:
            category: 下钻类别
            time_range: 时间范围

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
        sql_configs = await self.generate_drilldown_sqls(category, time_range)
        if not sql_configs:
            return {}

        async def execute_single(item: Dict[str, Any]) -> Dict[str, Any]:
            """执行单个 SQL 模板，返回全部数据行"""
            try:
                result = await self._sql_executor.execute(item["sql"])
                if result and result.data:
                    return {
                        "template_name": item["template_name"],
                        "rows": result.data,
                    }
                return {"template_name": item["template_name"], "rows": []}
            except Exception as e:
                logger.warning(
                    f"[ReportGenerator] SQL execution failed: {item['sql'][:100]}... Error: {e}"
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
        dim_labels = {
            "by_site": "站点",
            "by_category": "一级品类",
            "by_platform": "平台",
            "by_asin": "ASIN",
        }

        for dim_key, dim_label in dim_labels.items():
            rows = dimensional_data.get(dim_key, [])
            if rows:
                # 提取所有列名（排除维度名称列本身）
                dim_col_names = [k for k in rows[0].keys() if k not in (
                    "FSITE", "FSITECODE", "站点", "站点编码",
                    "GROUP_1", "一级品类",
                    "PLATFORM", "平台",
                    "ASIN", "SKU"
                )]
                # 表头
                header = "  " + " | ".join([dim_label] + dim_col_names)
                sep = "  " + " | ".join(["-" * max(4, len(dim_label))] + ["-" * max(6, len(c)) for c in dim_col_names])
                lines = [f"【{dim_label}排名 TOP{len(rows)}】", header, sep]
                for i, row in enumerate(rows, 1):
                    vals = [str(row.get(c, "-")) for c in dim_col_names]
                    # 取前5个维度展示（避免太长）
                    if i <= 5:
                        lines.append(f"  {row.get(list(rows[0].keys())[0], '')} | " + " | ".join(vals))
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
