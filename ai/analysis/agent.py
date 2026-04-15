"""
决策分析 Agent - 核心分析逻辑
"""
from typing import Dict, List, Any, Optional, AsyncIterator
import asyncio
import json
import re
import httpx
from dataclasses import dataclass
from datetime import datetime

from .sse_utils import SSEEvent, create_sse_event
from .template_loader import template_loader
from .template_matcher import template_matcher, MatchResult
from .insights import get_insight_function, INDUSTRY_BENCHMARKS
from ..engine.time_parser import TimeParser
from ..engine.llm import get_llm_engine, get_llm_engine_for_analysis
from ..client.metric_client import MetricClient


# 内置演示模板（当无模板匹配时使用）
DEMO_TEMPLATE = {
    "id": 999,
    "name": "通用决策分析",
    "prompt_text": """
# {metric_name} 决策分析报告

## 概述
{message}

## 关键指标
- **ROAS**: {metric_roas}（广告支出回报率）
- **ACOS**: {metric_acos}%（广告成本销售比）
- **CPC**: {metric_cpc}元（单次点击成本）
- **CTR**: {metric_ctr}%（点击率）

## 趋势分析
{insights: ["trend"]}

## 异常检测
{insights: ["anomaly"]}

## 建议
基于当前数据分析，建议：
1. 优化广告投放策略，提高 ROAS
2. 关注 ACOS 变化，控制广告成本
3. 定期监控关键指标异常波动
""",
    "category": "decision_analysis",
    "keywords": "分析,效果,广告",
    "description": "通用决策分析模板"
}


# LLM 分析 Prompt 模板
# 注意：使用 str.replace() 代替 .format()，避免 JSON 示例中的 {} 被误解析
LLM_ANALYSIS_PROMPT = """你是一个专业的亚马逊广告数据分析助手。

## 模板结构（必须严格按照此结构生成分析）
{template_structure}

## 指标数据
{metric_data}

## 行业基准
{benchmark_data}

## 输出要求

### 分析内容
- 每个分析维度都要有具体的文字分析内容
- 结合指标数据和行业基准进行具体分析
- 使用Markdown格式输出
- 分析要有深度，不能只是泛泛而谈
- 模板中的 {CHART_DATA:...} 标记已经包含了图表数据，请在其后撰写分析文字
- **尽量减少加粗标记的使用**，只在真正关键的数据处使用

请生成完整的分析报告：
"""


@dataclass
class AnalysisRequest:
    """分析请求"""
    session_id: str
    query: str = ""
    metric_codes: List[str] = None  # 如 ["roas", "acos"]
    time_range: str = "近30天"

    def __post_init__(self):
        if self.metric_codes is None:
            self.metric_codes = []


class AnalysisAgent:
    """决策分析 Agent"""

    def __init__(self, request: AnalysisRequest):
        self.request = request
        self.template_loader = template_loader
        self.template_matcher = template_matcher
        self.http_client = httpx.AsyncClient(timeout=60)
        self.metric_client = MetricClient(base_url="http://localhost:8080")
        self._table_dimensions_cache: Dict[str, Dict[str, Dict]] = {}

    async def get_last_query_result(self) -> Dict[str, Any]:
        """从 Go 后端获取最近一次问数结果"""
        try:
            response = await self.http_client.get(
                "http://localhost:8080/api/v1/ask/last-result",
                params={"session_id": self.request.session_id}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    return data.get("data", {})
        except Exception as e:
            print(f"[AnalysisAgent] 获取问数结果失败: {e}")
        return {}

    async def query_metric_timeseries(
        self,
        metric_code: str,
        days: int = 30,
        dimension: str = None
    ) -> List[Dict[str, Any]]:
        """
        查询 StarRocks 时序数据

        Args:
            metric_code: 指标编号（如 MKI-02-0001）
            days: 查询天数，默认30天
            dimension: 维度分组（如 "日"、"三级品类"）

        Returns:
            时序数据列表，如 [{"date": "2026-04-01", "value": 3.2}, ...]
        """
        try:
            # 1. 获取指标元数据（包含 starrocks_sql 模板）
            metric_info = await self._get_metric_info(metric_code)
            if not metric_info:
                print(f"[AnalysisAgent] 未找到指标 {metric_code}")
                return []

            starrocks_sql = metric_info.get("starrocks_sql", "")
            if not starrocks_sql:
                print(f"[AnalysisAgent] 指标 {metric_code} 未配置 starrocks_sql")
                return []

            # 2. 解析时间范围，计算 start_date 和 end_date
            time_parser = TimeParser()
            time_info = time_parser.parse(f"近{days}天")

            if not time_info or not time_info.get("start") or not time_info.get("end"):
                print(f"[AnalysisAgent] 无法解析时间范围: 近{days}天")
                return []

            start_date = time_info["start"]
            end_date = time_info["end"]

            # 3. 组装 SQL 查询（注入时间和维度条件）
            sql = self._build_timeseries_sql(starrocks_sql, start_date, end_date, dimension)

            if not sql:
                print(f"[AnalysisAgent] 无法构建时序查询 SQL")
                return []

            print(f"[AnalysisAgent] SQL: {sql}")

            # 4. 执行 SQL 查询
            result = await self._execute_starrocks_query(sql)

            if result is None:
                print(f"[AnalysisAgent] StarRocks 查询失败或返回空")
                return []

            # 5. 解析结果，转换为 [{date, value}] 格式
            timeseries_data = self._parse_query_result(result, metric_code)

            print(f"[AnalysisAgent] 查询指标 {metric_code} 获取 {len(timeseries_data)} 条时序数据")
            return timeseries_data

        except Exception as e:
            print(f"[AnalysisAgent] 查询时序数据异常: {e}")
            return []

    async def _get_metric_info(self, metric_code: str) -> Optional[Dict[str, Any]]:
        """从 Go 后端获取指标元数据，支持按 metric_code、name 或 name_en 查询"""
        try:
            response = await self.http_client.get(
                "http://localhost:8080/api/v1/metadata/metrics",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                metrics = data.get("data", []) if isinstance(data, dict) else []
                for m in metrics:
                    # 优先匹配 metric_code（如 MKI-02-0001）
                    if m.get("metric_code") == metric_code:
                        return m
                    # 如果 metric_code 没匹配上，尝试匹配 name（指标中文名，如"曝光量"）
                    if m.get("name") == metric_code:
                        return m
                    # 再尝试匹配 name_en（指标英文名）
                    if m.get("name_en") and m.get("name_en").lower() == metric_code.lower():
                        return m
        except Exception as e:
            print(f"[AnalysisAgent] 获取指标信息失败: {e}")
        return None

    def _get_table_dimensions_cached(self, table_name: str) -> Dict[str, Dict]:
        """获取表的维度配置，带缓存（参考 nodes.py 的实现）"""
        if table_name in self._table_dimensions_cache:
            return self._table_dimensions_cache[table_name]
        try:
            configs = self.metric_client.get_dimension_configs(table_name)
            result = {}
            for cfg in configs:
                if cfg.get("status") == 1:
                    result[cfg["dimension_name"]] = {
                        "column_name": cfg["column_name"],
                        "values": json.loads(cfg["dimension_values"]) if cfg.get("dimension_values") else []
                    }
            self._table_dimensions_cache[table_name] = result
        except Exception as e:
            print(f"[AnalysisAgent] 获取维度配置失败: {e}")
            self._table_dimensions_cache[table_name] = {}
        return self._table_dimensions_cache[table_name]

    def _extract_table_name(self, sql: str) -> str:
        """从 SQL 中提取表名（FROM 后第一个表名，参考 nodes.py）"""
        sql_upper = sql.upper()
        from_pos = sql_upper.find(" FROM ")
        if from_pos == -1:
            return ""
        after_from = sql[from_pos + 6:].strip()
        # 获取表名（到第一个空白、换行、逗号或括号为止）
        table_name = ""
        for ch in after_from:
            if ch == ' ' or ch == '\n' or ch == '\r' or ch == '\t' or ch == ',' or ch == '(':
                break
            table_name += ch
        return table_name.strip()

    async def _execute_starrocks_query(self, sql: str) -> Optional[Any]:
        """通过 Go 后端执行 StarRocks 查询"""
        try:
            response = await self.http_client.post(
                "http://localhost:8080/api/v1/query/execute",
                json={"sql": sql, "params": {}},
                timeout=30.0
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return result.get("data")
                else:
                    print(f"[AnalysisAgent] 查询执行失败: {result.get('message')}")
            else:
                print(f"[AnalysisAgent] 查询请求失败: {response.status_code}")
        except Exception as e:
            print(f"[AnalysisAgent] 执行 StarRocks 查询异常: {e}")
        return None

    def _build_timeseries_sql(
        self,
        starrocks_sql: str,
        start_date: str,
        end_date: str,
        dimension: str = None
    ) -> Optional[str]:
        """
        构建时序查询 SQL（使用智能问数的维度配置逻辑）

        支持：
        1. 时间范围注入（{start_date}/{end_date} 占位符或自动追加）
        2. 维度分组（GROUP BY），如 "日"、"三级品类" 等
        """
        sql = starrocks_sql

        # 1. 尝试直接替换占位符
        replacements = [
            ("{start_date}", f"'{start_date}'"),
            ("{end_date}", f"'{end_date}'"),
            ("{date_from}", f"'{start_date}'"),
            ("{date_to}", f"'{end_date}'"),
        ]
        for placeholder, value in replacements:
            if placeholder in sql:
                sql = sql.replace(placeholder, value)

        # 2. 如果没有时间占位符，追加时间条件
        if "{start_date}" not in sql and "{end_date}" not in sql:
            # 已知的时间列名映射
            time_col_map = {
                "日": "FDATE", "day": "FDATE",
                "月": "MONTHS", "month": "MONTHS",
                "年": "YEARS", "year": "YEARS",
            }
            date_col = "FDATE"  # 默认值

            # 检查是否已有时间条件
            sql_lower = sql.lower()
            has_time_cond = False
            for col in ["fdate", "dt", "date", "months"]:
                pattern = rf"{col}\s*>=\s*['\"]?(\d{8}|\d{4}-\d{2}-\d{2})"
                if re.search(pattern, sql_lower):
                    has_time_cond = True
                    break

            if not has_time_cond:
                time_cond = f"FDATE >= '{start_date}' AND FDATE <= '{end_date}'"
                if "WHERE" in sql.upper():
                    sql = sql + f" AND {time_cond}"
                else:
                    from_pos = sql_lower.find(" from ")
                    if from_pos != -1:
                        pos = from_pos + 6
                        while pos < len(sql) and sql[pos] == ' ':
                            pos += 1
                        keywords = ["WHERE", "GROUP", "ORDER", "LIMIT", "HAVING"]
                        insert_pos = len(sql)
                        for kw in keywords:
                            kw_pos = sql.upper().find(kw, pos)
                            if kw_pos != -1 and kw_pos < insert_pos:
                                insert_pos = kw_pos
                        sql = sql[:insert_pos] + f" WHERE {time_cond}" + sql[insert_pos:]
                    else:
                        sql = sql + f" WHERE {time_cond}"

        # 3. 处理维度分组（GROUP BY）
        if dimension:
            # 统一维度键到列名的映射（基于已知配置）
            dim_col_map = {
                "日": "FDATE", "day": "FDATE",
                "月": "MONTHS", "month": "MONTHS",
                "年": "YEARS", "year": "YEARS",
                "三级品类": "GROUP_3",
                "二级品类": "GROUP_2",
                "一级品类": "GROUP_1",
                "SKU": "SKU",
            }
            col = dim_col_map.get(dimension, dimension)

            # 添加 GROUP BY
            if "GROUP BY" not in sql.upper():
                sql = sql.rstrip() + f" GROUP BY {col}"

            # 如果 SELECT 中没有 GROUP BY 列，需要添加到 SELECT
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1).upper()
                if col.upper() not in select_clause:
                    sql = re.sub(
                        r'(SELECT\s+)(.*?)(\s+FROM)',
                        r'\1' + col + r', \2\3',
                        sql,
                        flags=re.IGNORECASE | re.DOTALL
                    )

        # 4. 清理未替换的占位符
        sql = re.sub(r'\{[^}]+\}', '', sql)

        return sql

    def _parse_query_result(
        self,
        result: Any,
        metric_code: str
    ) -> List[Dict[str, Any]]:
        """
        解析查询结果，提取时序数据

        结果格式可能是：
        1. {"columns": [...], "rows": [[...], [...]]}
        2. [[...], [...]] (直接行数据)
        3. [{"date": ..., "value": ...}, ...] (已经是字典格式)
        """
        timeseries = []

        try:
            # 处理可能的嵌套结果
            if isinstance(result, dict):
                # 格式1: {"columns": [...], "rows": [[...], [...]]}
                if "data" in result:
                    result = result["data"]
                    # 递归调用会返回填充后的 timeseries，直接返回
                    return self._parse_query_result(result, metric_code)

                columns = result.get("columns", [])
                rows = result.get("rows", [])

                if not columns or not rows:
                    # 可能是直接的行数据列表
                    if isinstance(result.get("rows"), list):
                        return self._parse_query_result(result["rows"], metric_code)
                    # 处理 Go 后端返回格式 {"count": N, "data": [{...}]}
                    if "data" in result and isinstance(result.get("data"), list):
                        # 递归调用会返回填充后的 timeseries，直接返回
                        return self._parse_query_result(result["data"], metric_code)
                    return []

                # 查找日期列和值列
                date_col_idx = None
                value_col_idx = None

                for i, col in enumerate(columns):
                    col_lower = col.lower()
                    # 扩展日期列的识别范围，包含 FDATE
                    if col_lower in ["dt", "date", "stat_date", "report_date", "day", "fdate"]:
                        date_col_idx = i
                    elif col_lower in ["value", "metric_value", "cnt", "num"]:
                        value_col_idx = i

                # 如果没找到，尝试用第一列作为日期，第二列作为值
                if date_col_idx is None:
                    date_col_idx = 0
                if value_col_idx is None:
                    value_col_idx = 1

                for row in rows:
                    if isinstance(row, (list, tuple)):
                        if len(row) == 1:
                            # 单列结果：这是聚合查询（如 SUM/GROUP BY），直接用固定日期和该值
                            value_val = row[0]
                            timeseries.append({
                                "date": "聚合",
                                "value": float(value_val) if value_val is not None else 0.0
                            })
                        elif len(row) > max(date_col_idx, value_col_idx):
                            date_val = row[date_col_idx]
                            value_val = row[value_col_idx]
                            timeseries.append({
                                "date": str(date_val),
                                "value": float(value_val) if value_val is not None else 0.0
                            })
                    elif isinstance(row, dict):
                        # 已经是字典格式
                        # 检查是否是单列聚合结果（如 {"sum(ORDERED_PRODUCTSALES)": "786369189.69"}）
                        if len(row) == 1:
                            # 单列dict：key是列名（如sum函数），value是实际值
                            value_val = list(row.values())[0]
                            timeseries.append({
                                "date": "聚合",
                                "value": float(value_val) if value_val is not None else 0.0
                            })
                        else:
                            # 扩展日期列的识别范围，包含 FDATE
                            date_val = row.get("dt") or row.get("date") or row.get("stat_date") or row.get("fdate") or list(row.values())[0]
                            value_val = row.get("value") or row.get("metric_value") or (list(row.values())[1] if len(row) > 1 else 0)
                            # 如果 value_val 是日期字符串（解析错误），尝试用第二列作为值
                            try:
                                float(value_val)
                            except (ValueError, TypeError):
                                # value_val 不是有效数字，使用第二列
                                values = list(row.values())
                                if len(values) > 1:
                                    value_val = values[1]
                            timeseries.append({
                                "date": str(date_val),
                                "value": float(value_val) if value_val is not None else 0.0
                            })

            elif isinstance(result, list):
                # 格式2: [[...], [...]] 或 [{"date": ..., "value": ...}, ...]
                for item in result:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        timeseries.append({
                            "date": str(item[0]),
                            "value": float(item[1]) if item[1] is not None else 0.0
                        })
                    elif isinstance(item, dict):
                        # 检查是否是单列聚合结果（如 {"page_views": "26280027.0000000"}）
                        if len(item) == 1:
                            value_val = list(item.values())[0]
                            timeseries.append({
                                "date": "聚合",
                                "value": float(value_val) if value_val is not None else 0.0
                            })
                        else:
                            # 已知日期列
                            date_keys = {"dt", "date", "stat_date", "fdate", "FDATE", "report_date", "day"}
                            date_val = None
                            value_val = None
                            # 遍历所有 key-value，找出日期列和数值列
                            for k, v in item.items():
                                k_lower = str(k).lower()
                                if k_lower in date_keys:
                                    date_val = v
                                else:
                                    # 尝试作为数值
                                    try:
                                        float(v)
                                        value_val = v
                                    except (ValueError, TypeError):
                                        pass
                            # 如果没有找到日期列，用第一个值作为日期
                            if date_val is None and value_val is not None:
                                # 交换：value_val 变成日期
                                date_val = str(value_val)
                                value_val = None
                            timeseries.append({
                                "date": str(date_val) if date_val else "未知",
                                "value": float(value_val) if value_val is not None else 0.0
                            })

        except Exception as e:
            print(f"[AnalysisAgent] 解析查询结果异常: {e}")

        # 按日期排序
        timeseries.sort(key=lambda x: x.get("date", ""))

        return timeseries

    async def query_metric_data(
        self,
        metric_code: str,
        time_range: str,
        dimension: str = None
    ) -> List[float]:
        """
        查询指标时序数据（Python 直连 StarRocks）

        Returns:
            时序数据列表，如 [3.2, 3.1, 3.5, 3.8, 3.5]
        """
        try:
            # 解析 time_range 获取天数
            time_parser = TimeParser()
            time_info = time_parser.parse(time_range)

            if not time_info or not time_info.get("start"):
                print(f"[AnalysisAgent] 无法解析时间范围: {time_range}，使用默认值30天")
                days = 30
            else:
                # 计算天数
                from datetime import datetime
                start = datetime.strptime(time_info["start"], "%Y-%m-%d")
                end = datetime.strptime(time_info["end"], "%Y-%m-%d")
                days = (end - start).days
                if days <= 0:
                    days = 30

            # 查询时序数据
            timeseries = await self.query_metric_timeseries(metric_code, days, dimension)

            # 转换为简单的浮点数列表
            return [item["value"] for item in timeseries]

        except Exception as e:
            print(f"[AnalysisAgent] 查询指标数据异常: {e}")
            return []

    async def query_metric_timeseries_for_chart(
        self,
        metric_code: str,
        time_range: str
    ) -> Dict[str, Any]:
        """
        查询指标时序数据用于图表（强制按"日"分组）

        Returns:
            {
                "dates": ["4/1", "4/2", ...],
                "values": [1000, 1200, ...],
                "metric_name": "销售额"
            }
        """
        try:
            # 解析 time_range 获取天数
            time_parser = TimeParser()
            time_info = time_parser.parse(time_range)

            if not time_info or not time_info.get("start"):
                days = 30
            else:
                from datetime import datetime
                start = datetime.strptime(time_info["start"], "%Y-%m-%d")
                end = datetime.strptime(time_info["end"], "%Y-%m-%d")
                days = (end - start).days
                if days <= 0:
                    days = 30

            # 查询时序数据，强制使用"日"维度
            timeseries = await self.query_metric_timeseries(metric_code, days, "日")

            # 获取指标名称
            metric_info = await self._get_metric_info(metric_code)
            metric_name = metric_info.get("name", metric_code) if metric_info else metric_code

            # 转换为日期和值的列表
            dates = []
            values = []
            for item in timeseries:
                date_str = item.get("date", "")
                # 转换日期格式 2026-04-07 -> 4/7
                if date_str and date_str != "聚合":
                    try:
                        from datetime import datetime
                        d = datetime.strptime(date_str, "%Y-%m-%d")
                        dates.append(f"{d.month}/{d.day}")
                    except:
                        dates.append(date_str)
                values.append(item.get("value", 0))

            return {
                "dates": dates,
                "values": values,
                "metric_name": metric_name
            }

        except Exception as e:
            print(f"[AnalysisAgent] 查询图表时序数据异常: {e}")
            return {"dates": [], "values": [], "metric_name": metric_code}

    async def compute_insights(
        self,
        metric_code: str,
        data: List[float],
        insights_needed: List[str]
    ) -> Dict[str, Any]:
        """计算洞察"""
        results = {}

        for insight_type in insights_needed:
            func = get_insight_function(insight_type)
            if func:
                try:
                    # 趋势分析需要知道指标类型
                    kwargs = {"data": data}
                    if insight_type in ["trend", "detect_anomaly"]:
                        # 从指标 code 推断类型
                        metric_type = self._infer_metric_type(metric_code)
                        kwargs["metric_type"] = metric_type

                    results[insight_type] = func(**kwargs)
                except Exception as e:
                    print(f"[AnalysisAgent] 洞察 {insight_type} 计算失败: {e}")
                    results[insight_type] = {"error": str(e)}

        return results

    def _infer_metric_type(self, metric_code: str) -> str:
        """从指标 code 推断指标类型"""
        code_lower = metric_code.lower()
        if "roas" in code_lower:
            return "roas"
        elif "acos" in code_lower:
            return "acos"
        elif "cpc" in code_lower:
            return "cpc"
        elif "ctr" in code_lower:
            return "ctr"
        return "roas"  # 默认

    def _get_demo_value(self, metric_code: str) -> float:
        """获取演示用的模拟指标值"""
        demo_values = {
            "roas": 3.5,
            "acos": 25.0,
            "cpc": 1.8,
            "ctr": 2.3,
            "cvr": 4.5,
            "gmv": 125000,
            "orders": 850,
        }
        code_lower = metric_code.lower()
        for key, value in demo_values.items():
            if key in code_lower:
                return value
        return 3.5  # 默认值

    def _fill_template(
        self,
        template: Dict[str, Any],
        metric_values: Dict[str, float],
        insight_results: Dict[str, Any]
    ) -> str:
        """填充模板占位符"""
        prompt_text = template.get("prompt_text", "")

        # 填充指标值
        for metric_code, value in metric_values.items():
            placeholder = f"{{metric_{metric_code}}}"
            prompt_text = prompt_text.replace(placeholder, str(value))

        # 填充洞察结果
        for insight_type, result in insight_results.items():
            if isinstance(result, dict):
                # trend_xxx -> insight_trend
                for key, value in result.items():
                    placeholder = f"{{insight_{insight_type}_{key}}}"
                    prompt_text = prompt_text.replace(placeholder, str(value))

                # 生成摘要描述
                if insight_type == "trend":
                    direction_desc = {"up": "上升", "down": "下降", "stable": "稳定"}
                    desc = f"{direction_desc.get(result.get('direction', 'stable'), '稳定')}"
                    desc += f"，当前值 {result.get('current_value', 0)}"
                    desc += f"，{result.get('assessment', '')}"
                    prompt_text = prompt_text.replace(
                        "{insight_trend_xxx}",
                        desc
                    )
                elif insight_type == "anomaly":
                    if result.get("detected"):
                        anomalies = result.get("anomalies", [])
                        desc = f"检测到 {len(anomalies)} 个异常点"
                        prompt_text = prompt_text.replace("{insight_anomaly_xxx}", desc)
                    else:
                        prompt_text = prompt_text.replace("{insight_anomaly_xxx}", "未检测到异常")

        # 清理未填充的占位符
        prompt_text = re.sub(r'\{[^}]+\}', '', prompt_text)

        return prompt_text

    async def run_streaming(self) -> AsyncIterator[SSEEvent]:
        """流式执行分析 - 新流程"""
        import time
        total_start = time.time()
        step_start = total_start

        def get_delta() -> tuple:
            """计算当前步骤耗时和总耗时，返回 (delta_ms, total_ms)"""
            now = time.time()
            delta = (now - step_start) * 1000
            total = (now - total_start) * 1000
            return delta, total

        def log_step(step_num: int, label: str):
            """打印步骤耗时到控制台"""
            nonlocal step_start
            delta, total = get_delta()
            print(f"[耗时] 步骤{step_num}: {label}: {delta:.0f}ms (累计: {total:.0f}ms)")
            step_start = time.time()

        def make_thinking_event(step_num: int, label: str) -> str:
            """生成带耗时的 thinking 事件数据"""
            delta, total = get_delta()
            return f"[耗时] 步骤{step_num}: {label}: {delta:.0f}ms (累计: {total:.0f}ms)"

        print(f"\n{'='*60}")
        print(f"[分析开始] session_id={self.request.session_id}, query={self.request.query}")
        print(f"{'='*60}")

        # 1. 获取最近问数结果
        last_result = await self.get_last_query_result()
        metric_code = last_result.get("metric_code", "")
        log_step(1, "获取问数上下文")
        yield create_sse_event("thinking", make_thinking_event(1, "获取问数上下文"))

        # 2. 加载模板
        templates = self.template_loader.get_templates()
        log_step(2, "加载模板")
        yield create_sse_event("thinking", make_thinking_event(2, "加载模板"))

        if not templates:
            template = DEMO_TEMPLATE
            print(f"[模板] 使用演示模板 (id={template.get('id')})")
        else:
            # 3. 匹配模板
            context = {
                "metric_name": last_result.get("metric_name", ""),
                "metric_code": metric_code
            }
            match_start = time.time()
            match_result = await self.template_matcher.match(
                self.request.query or metric_code,
                context,
                templates
            )
            print(f"[模板匹配] 耗时: {(time.time()-match_start)*1000:.0f}ms, 匹配结果: {match_result.template.get('name') if match_result.template else 'None'}")
            log_step(3, "匹配分析模板")
            yield create_sse_event("thinking", make_thinking_event(3, "匹配分析模板"))

            if match_result.needs_confirmation and not match_result.template:
                if match_result.candidates:
                    first_candidate_id = match_result.candidates[0].get("id")
                    template = self.template_loader.get_template_by_id(first_candidate_id)
                    if not template:
                        template = DEMO_TEMPLATE
                else:
                    template = DEMO_TEMPLATE
            else:
                template = match_result.template or DEMO_TEMPLATE

        # 4. 获取模板配置
        indicators = self.template_loader.get_indicators(template)
        max_data_items = self.template_loader.get_max_data_items(template)
        benchmark = self.template_loader.get_benchmark(template)

        if not indicators:
            # 如果没有indicators配置，回退到演示数据
            indicators = [
                {"code": "roas", "time_range": "近30天", "dimensions": None},
                {"code": "acos", "time_range": "近30天", "dimensions": None},
                {"code": "cpc", "time_range": "近30天", "dimensions": None},
                {"code": "ctr", "time_range": "近30天", "dimensions": None},
                {"code": "cvr", "time_range": "近30天", "dimensions": None},
            ]

        # 5. 并发查询所有指标数据（汇总值，用于数据概览）
        query_start = time.time()

        metric_summaries = {}
        is_demo = template.get("id") == 999

        async def query_one(indicator: Dict) -> tuple:
            code = indicator.get("code", "")
            time_range = indicator.get("time_range", self.request.time_range)
            dimension = indicator.get("dimensions")  # 获取维度
            q_start = time.time()
            data = await self.query_metric_data(code, time_range, dimension)
            print(f"  [指标查询] {code}: {(time.time()-q_start)*1000:.0f}ms, 数据点: {len(data)}")
            summary = self._calculate_summary(data, code, is_demo)
            return code, summary

        # 并发查询汇总数据
        results = await asyncio.gather(*[query_one(ind) for ind in indicators])
        for code, summary in results:
            metric_summaries[code] = summary
        print(f"[汇总查询] 总耗时: {(time.time()-query_start)*1000:.0f}ms")
        log_step(5, "查询指标汇总数据")
        yield create_sse_event("thinking", make_thinking_event(5, f"查询 {len(indicators)} 个指标汇总数据"))

        # 5b. 查询时序数据用于图表（强制按"日"分组）
        ts_start = time.time()

        timeseries_for_chart = {}
        async def query_timeseries(indicator: Dict) -> tuple:
            code = indicator.get("code", "")
            time_range = indicator.get("time_range", self.request.time_range)
            t_start = time.time()
            ts_data = await self.query_metric_timeseries_for_chart(code, time_range)
            print(f"  [时序查询] {code}: {(time.time()-t_start)*1000:.0f}ms, 数据点: {len(ts_data.get('dates', []))}")
            return code, ts_data

        ts_results = await asyncio.gather(*[query_timeseries(ind) for ind in indicators])
        for code, ts_data in ts_results:
            timeseries_for_chart[code] = ts_data
        print(f"[时序查询] 总耗时: {(time.time()-ts_start)*1000:.0f}ms")
        log_step(5, "查询时序图表数据")
        yield create_sse_event("thinking", make_thinking_event(5, "查询时序图表数据"))

        # 6. 调用 LLM 分析
        # 构建 LLM prompt（传入完整模板结构 + 时序数据）
        llm_prompt = self._build_llm_prompt(template, metric_summaries, benchmark, timeseries_for_chart)

        # 获取实际的图表数据（在 prompt 构建后，因为 _build_llm_prompt 内部已经计算了）
        chart_data_json = self._build_chart_data_json(timeseries_for_chart or {})

        # 调用 LLM（异步流式方式，逐块返回）
        llm_engine = get_llm_engine_for_analysis()
        llm_start = time.time()
        log_step(6, "LLM生成分析")
        yield create_sse_event("thinking", make_thinking_event(6, "生成分析"))

        # 流式输出：逐块 yield chunk 事件
        full_result = ""
        async for chunk_text in llm_engine.stream(llm_prompt, temperature=llm_engine.temperature, max_tokens=4000):
            full_result += chunk_text
            yield create_sse_event("chunk", chunk_text)
        print(f"[LLM调用] 耗时: {(time.time()-llm_start)*1000:.0f}ms, 总长度: {len(full_result)}")

        # 6b. 后处理：清理 LLM 输出的格式问题
        full_result = self._clean_llm_output(full_result)

        # 6c. 发送图表数据（作为单独的事件，让前端直接使用而不需要从文本解析）
        try:
            # chart_data_json 格式是 {CHART_DATA:{"charts":[...]}}，需要解析内部 JSON
            import json
            # 去掉前缀 {CHART_DATA: 和末尾的 }
            inner_json = chart_data_json[len('{CHART_DATA:'):-1]
            chart_obj = json.loads(inner_json)
            if chart_obj.get('charts'):
                yield create_sse_event("chart", json.dumps(chart_obj, ensure_ascii=False))
                print(f"[图表] 已发送图表数据，charts 数量: {len(chart_obj['charts'])}")
        except Exception as e:
            print(f"[图表] 发送图表数据失败: {e}")

        # 7. 完成
        yield create_sse_event("done", "")
        total_time = time.time() - total_start
        print(f"\n{'='*60}")
        print(f"[分析完成] 总耗时: {total_time*1000:.0f}ms ({total_time:.1f}s)")
        print(f"{'='*60}\n")

    async def run(self) -> Dict[str, Any]:
        """非流式执行分析 - 返回完整结果"""
        import time
        import json
        import traceback
        import sys
        total_start = time.time()

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[分析开始] session_id={self.request.session_id}, query={self.request.query}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        try:
            # 1. 获取最近问数结果
            last_result = await self.get_last_query_result()
            metric_code = last_result.get("metric_code", "")

            # 2. 加载模板
            templates = self.template_loader.get_templates()

            if not templates:
                template = DEMO_TEMPLATE
                print(f"[模板] 使用演示模板 (id={template.get('id')})")
            else:
                # 3. 匹配模板
                context = {
                    "metric_name": last_result.get("metric_name", ""),
                    "metric_code": metric_code
                }
                match_result = await self.template_matcher.match(
                    self.request.query or metric_code,
                    context,
                    templates
                )
                print(f"[模板匹配] 匹配结果: {match_result.template.get('name') if match_result.template else 'None'}")

                if match_result.needs_confirmation and not match_result.template:
                    if match_result.candidates:
                        first_candidate_id = match_result.candidates[0].get("id")
                        template = self.template_loader.get_template_by_id(first_candidate_id)
                        if not template:
                            template = DEMO_TEMPLATE
                    else:
                        template = DEMO_TEMPLATE
                else:
                    template = match_result.template or DEMO_TEMPLATE

            # 4. 获取模板配置
            indicators = self.template_loader.get_indicators(template)
            max_data_items = self.template_loader.get_max_data_items(template)
            benchmark = self.template_loader.get_benchmark(template)

            if not indicators:
                indicators = [
                    {"code": "roas", "time_range": "近30天", "dimensions": None},
                    {"code": "acos", "time_range": "近30天", "dimensions": None},
                    {"code": "cpc", "time_range": "近30天", "dimensions": None},
                    {"code": "ctr", "time_range": "近30天", "dimensions": None},
                    {"code": "cvr", "time_range": "近30天", "dimensions": None},
                ]

            # 5. 并发查询所有指标数据
            metric_summaries = {}
            is_demo = template.get("id") == 999

            async def query_one(indicator: Dict) -> tuple:
                code = indicator.get("code", "")
                time_range = indicator.get("time_range", self.request.time_range)
                dimension = indicator.get("dimensions")
                data = await self.query_metric_data(code, time_range, dimension)
                summary = self._calculate_summary(data, code, is_demo)
                return code, summary

            results = await asyncio.gather(*[query_one(ind) for ind in indicators])
            for code, summary in results:
                metric_summaries[code] = summary
            print(f"[汇总查询] 完成，共 {len(indicators)} 个指标")

            # 5b. 查询时序数据用于图表
            timeseries_for_chart = {}

            async def query_timeseries(indicator: Dict) -> tuple:
                code = indicator.get("code", "")
                time_range = indicator.get("time_range", self.request.time_range)
                ts_data = await self.query_metric_timeseries_for_chart(code, time_range)
                return code, ts_data

            ts_results = await asyncio.gather(*[query_timeseries(ind) for ind in indicators])
            for code, ts_data in ts_results:
                timeseries_for_chart[code] = ts_data
            print(f"[时序查询] 完成，共 {len(timeseries_for_chart)} 个指标")

            # 6. 调用 LLM 分析
            llm_prompt = self._build_llm_prompt(template, metric_summaries, benchmark, timeseries_for_chart)
            chart_data_json = self._build_chart_data_json(timeseries_for_chart or {})

            llm_engine = get_llm_engine_for_analysis()

            # 非流式调用：一次性获取完整结果
            full_result = await llm_engine.generate(llm_prompt, temperature=llm_engine.temperature, max_tokens=4000)
            print(f"[LLM调用] 完成，总长度: {len(full_result)}")

            # 6b. 后处理：清理 LLM 输出的格式问题
            full_result = self._clean_llm_output(full_result)

            # 6c. 解析图表数据（charts 数组会单独返回，不需要在 answer 中保留 CHART_DATA）
            charts = []
            try:
                inner_json = chart_data_json[len('{CHART_DATA:'):-1]
                chart_obj = json.loads(inner_json)
                charts = chart_obj.get('charts', [])
                print(f"[图表] 解析完成，charts 数量: {len(charts)}")
            except Exception as e:
                print(f"[图表] 解析失败: {e}")

            total_time = time.time() - total_start
            print(f"\n{'='*60}")
            print(f"[分析完成] 总耗时: {total_time*1000:.0f}ms ({total_time:.1f}s)")
            print(f"{'='*60}\n")

            return {
                "answer": full_result,
                "charts": charts
            }
        except Exception as e:
            tb_str = traceback.format_exc()
            try:
                print(f"[Agent.run] 异常: {type(e).__name__}: {str(e)}", file=sys.stderr)
                print(f"[Agent.run] Traceback: {tb_str}", file=sys.stderr)
            except:
                pass
            return {
                "answer": f"Request Error: {type(e).__name__}: {str(e)}\n\nTraceback:\n{tb_str}",
                "charts": []
            }

    def _calculate_summary(self, data: List[float], metric_code: str, is_demo: bool) -> Dict[str, Any]:
        """计算指标汇总数据"""
        if not data or len(data) == 0:
            return {
                "current": self._get_demo_value(metric_code) if is_demo else 0,
                "max": 0,
                "min": 0,
                "avg": 0
            }

        values = [float(v) for v in data if v is not None]
        if not values:
            return {"current": 0, "max": 0, "min": 0, "avg": 0}

        return {
            "current": values[-1] if values else 0,
            "max": max(values) if values else 0,
            "min": min(values) if values else 0,
            "avg": sum(values) / len(values) if values else 0
        }

    def _build_llm_prompt(
        self,
        template: Dict,
        metric_summaries: Dict,
        benchmark: Dict,
        timeseries_for_chart: Dict[str, Any] = None
    ) -> str:
        """构建 LLM 分析 prompt"""
        # 获取模板结构
        template_structure = template.get("prompt_text", "")

        # 生成实际的 CHART_DATA（基于查询到的时序数据）
        chart_data_json = self._build_chart_data_json(timeseries_for_chart or {})

        # 清除预置的示例 CHART_DATA 并替换为占位符
        # 注意：不要发送实际的图表 JSON 给 LLM，否则 LLM 会模仿生成错误格式
        import re
        import sys
        # 匹配 CHART_DATA 块
        # re.DOTALL 使 . 能匹配换行符
        if '{CHART_DATA:' in template_structure:
            print(f"[DEBUG] 模板中发现 CHART_DATA，正则替换前长度: {len(template_structure)}", flush=True)
            # 打印 CHART_DATA 前的 50 个字符
            idx = template_structure.find('{CHART_DATA:')
            print(f"[DEBUG] CHART_DATA 位置 {idx}，前50字符: {repr(template_structure[max(0,idx-50):idx+50])}", flush=True)
            # 先尝试匹配标准 JSON 格式 {CHART_DATA:{...}}
            new_template, count = re.subn(
                r'\{CHART_DATA:\s*\{[\s\S]*?\}\s*\}',
                '[[CHART_BLOCK]]',
                template_structure,
                flags=re.DOTALL
            )
            print(f"[DEBUG] 正则1匹配次数: {count}", flush=True)
            if count > 0:
                template_structure = new_template
            else:
                # 尝试更宽松的模式
                new_template2, count2 = re.subn(
                    r'\{CHART_DATA:[\s\S]*?\}\s*\}',
                    '[[CHART_BLOCK]]',
                    template_structure,
                    flags=re.DOTALL
                )
                print(f"[DEBUG] 正则2匹配次数: {count2}", flush=True)
                if count2 > 0:
                    template_structure = new_template2
                else:
                    print(f"[ERROR] 所有正则模式都无法匹配 CHART_DATA", flush=True)
                    print(f"[ERROR] 模板片段: {repr(template_structure[idx:idx+200])}", flush=True)

        # 填充模板中的指标占位符
        for code, summary in metric_summaries.items():
            placeholder = f"{{metric_{code}}}"
            value_str = f"¥{summary['current']:.2f}"
            template_structure = template_structure.replace(placeholder, value_str)

        # 填充模板中的基准占位符
        for code, bench in benchmark.items():
            placeholder = f"{{benchmark_{code}}}"
            excellent = bench.get("excellent", "")
            good = bench.get("good", "")
            value_str = f"优秀={excellent}, 良好={good}"
            template_structure = template_structure.replace(placeholder, value_str)

        # 清理未填充的洞察占位符（让 LLM 自然生成）
        template_structure = template_structure.replace("{insight_findings}", "（根据数据分析自动生成）")
        template_structure = template_structure.replace("{insight_suggestion}", "（根据数据分析自动生成）")

        # 构建指标数据字符串
        metric_lines = []
        for code, summary in metric_summaries.items():
            metric_lines.append(
                f"- {code}: 当前值={summary['current']:.2f}, "
                f"最大值={summary['max']:.2f}, 最小值={summary['min']:.2f}, 平均值={summary['avg']:.2f}"
            )
        metric_data_str = "\n".join(metric_lines)

        # 构建基准数据字符串
        benchmark_lines = []
        for code, bench in benchmark.items():
            excellent = bench.get("excellent", "")
            good = bench.get("good", "")
            benchmark_lines.append(f"- {code}: 优秀={excellent}, 良好={good}")
        benchmark_str = "\n".join(benchmark_lines) if benchmark_lines else "无行业基准数据"

        # 使用 str.replace 代替 .format()，避免 JSON 示例中的 {} 被误解析
        prompt = LLM_ANALYSIS_PROMPT
        prompt = prompt.replace("{template_structure}", template_structure)
        prompt = prompt.replace("{metric_data}", metric_data_str)
        prompt = prompt.replace("{benchmark_data}", benchmark_str)
        return prompt

    def _clean_llm_output(self, text: str) -> str:
        """清理 LLM 输出的格式问题"""
        import re
        # 修复被空格断开的代码/ID（如 M KI-02 -000 9 -> MKI-02-0009）
        text = re.sub(r'\b([A-Z])\s+([A-Z])\s*-\s*(\d+)\s*-\s*(\d+)\b', r'\1\2-\3-\4', text)
        # 修复 MKI-02-0009 等代码中的多余空格
        text = re.sub(r'\b(MKI-\d+-\d+)\b', lambda m: m.group(1).replace(' ', ''), text)
        # 修复数字中的多余空格（如 754, 807, 145.12 -> 754807145.12）
        text = re.sub(r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', r'\1\2\3', text)
        # 修复千分位分隔的数字（如 27, 258, 455 -> 27258455）
        text = re.sub(r'(\d+)\s*,\s*(\d{3})\s*,\s*(\d{3})', r'\1\2\3', text)
        # 修复加粗标记周围的空格（如 ** text ** -> **text**）
        text = re.sub(r'\*\*\s+(.+?)\s+\*\*', r'**\1**', text)
        # 修复中文词语间的空格（如 页面访问 量 -> 页面访问量）
        text = re.sub(r'([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])', r'\1\2', text)
        # 修复英文单词间的多余空格
        text = re.sub(r'([a-zA-Z])\s{2,}([a-zA-Z])', r'\1 \2', text)
        return text

    def _build_chart_data_json(self, timeseries_for_chart: Dict[str, Any]) -> str:
        """
        根据查询到的时序数据构建 CHART_DATA JSON

        Args:
            timeseries_for_chart: {
                "MKI-02-0009": {"dates": ["4/1", "4/2", ...], "values": [1000, 1200, ...], "metric_name": "销售额"},
                "MKI-02-0004": {"dates": [...], "values": [...], "metric_name": "页面访问量"},
                ...
            }

        Returns:
            CHART_DATA JSON 字符串
        """
        if not timeseries_for_chart:
            return "{CHART_DATA:{\"charts\":[]}}"

        charts = []

        for code, ts_data in timeseries_for_chart.items():
            dates = ts_data.get("dates", [])
            values = ts_data.get("values", [])
            metric_name = ts_data.get("metric_name", code)

            if not dates or not values:
                continue

            # 限制数据点数量（最多30个）
            max_items = 30
            dates = dates[:max_items]
            values = values[:max_items]

            # 格式化为字符串
            x_data = json.dumps(dates, ensure_ascii=False)
            # 将数值列表格式化为带千分位的价格格式
            data_values = []
            for v in values:
                if v >= 10000:
                    data_values.append(f"{v:,.0f}")
                else:
                    data_values.append(str(round(v, 2)))

            series_data = json.dumps(data_values, ensure_ascii=False)

            chart = {
                "title": f"{metric_name}趋势",
                "type": "line",
                "xData": dates,
                "series": [
                    {"name": metric_name, "data": values}
                ]
            }
            charts.append(chart)

        if not charts:
            return "{CHART_DATA:{\"charts\":[]}}"

        result = {
            "charts": charts
        }
        return "{CHART_DATA:" + json.dumps(result, ensure_ascii=False) + "}"

    def _parse_llm_insights(self, llm_output: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON 洞察"""
        try:
            # 尝试提取 JSON
            import re
            json_match = re.search(r'\{[^{}]*"findings"[^{}]*"trend"[^{}]*"anomaly"[^{}]*"suggestion"[^{}]*\}', llm_output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            print(f"[AnalysisAgent] 解析 LLM 洞察失败: {e}")

        # 解析失败，返回默认
        return {
            "findings": "数据分析完成",
            "trend": "趋势分析生成中",
            "anomaly": None,
            "suggestion": "建议持续监控关键指标"
        }

    def _build_report(self, template: Dict, metric_summaries: Dict, insights: Dict) -> str:
        """构建完整报告"""
        prompt_text = template.get("prompt_text", "")
        prompt_text = prompt_text.replace("{time_range}", self.request.time_range or "近30天")

        # 填充指标值
        for code, summary in metric_summaries.items():
            placeholder = f"{{metric_{code}}}"
            current_value = summary.get('current', 0) or 0
            prompt_text = prompt_text.replace(placeholder, f"{current_value:.2f}")

        # 填充基准值
        benchmark = self.template_loader.get_benchmark(template)
        for code, bench in benchmark.items():
            placeholder = f"{{benchmark_{code}}}"
            excellent = bench.get("excellent", "") or ""
            good = bench.get("good", "") or ""
            prompt_text = prompt_text.replace(placeholder, f"{excellent} (良好{good})")

        # 填充洞察 - 确保值为字符串
        def safe_str(val):
            if val is None:
                return ""
            if isinstance(val, (list, dict)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)

        prompt_text = prompt_text.replace("{insight_findings}", safe_str(insights.get("findings", "")))
        prompt_text = prompt_text.replace("{insight_trend}", safe_str(insights.get("trend", "")))
        prompt_text = prompt_text.replace("{insight_anomaly}", safe_str(insights.get("anomaly", "无异常")))
        prompt_text = prompt_text.replace("{insight_suggestion}", safe_str(insights.get("suggestion", "")))

        # 清理未填充的占位符
        prompt_text = re.sub(r'\{[^}]+\}', '', prompt_text)

        return prompt_text

    async def close(self):
        """关闭资源"""
        await self.http_client.aclose()


# 辅助函数
async def run_analysis(request: AnalysisRequest) -> AsyncIterator[SSEEvent]:
    """运行分析的便捷函数"""
    agent = AnalysisAgent(request)
    try:
        async for event in agent.run_streaming():
            yield event
    finally:
        await agent.close()
