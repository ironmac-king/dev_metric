"""
波动分析引擎

职责：
- 计算基础统计指标（CV、环比、同比）
- IQR 异常检测
- 维度贡献度分析
- LLM 根因推理（对标顶流）
"""
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from ai.config.logging_config import get_logger
from ai.engine.llm import get_llm_engine
from ..streaming import StreamEvent, SSSEvent

logger = get_logger("ai.llm_v2.volatility_analyzer")

# LLM 根因分析系统提示词
VOLATILITY_SYSTEM_PROMPT = """你是指标波动分析专家，根据用户查询的指标，自动完成：
1. 波动识别
2. 维度拆解
3. 贡献计算
4. 根因定位（5类：业务活动/流量变化/结构变化/数据口径/系统异常）
5. 结论输出

输出固定结构：概况 → 波动 → 驱动 → 根因 → 建议

语言简洁，专业、可直接用于汇报。不反问、不推诿、不索要额外参数。"""


@dataclass
class VolatilityResult:
    """波动分析结果"""
    metric_name: str
    current_value: float
    mom_change: float      # 环比变化率
    yoy_change: float     # 同比变化率
    volatility_rate: float  # 波动率
    is_anomaly: bool      # 是否异常
    anomaly_level: str     # normal / 波动 / 异常
    top_positive_dims: List[Dict] = field(default_factory=list)  # TOP3 正向驱动
    top_negative_dims: List[Dict] = field(default_factory=list)   # TOP3 负向驱动
    root_cause: str = ""   # 根因归类
    root_cause_confidence: float = 0.0  # 置信度
    suggestion: str = ""    # 建议


class VolatilityAnalyzer:
    """波动分析引擎"""

    def __init__(self):
        self._llm_engine = get_llm_engine()

    async def calculate_basic_stats(
        self,
        data: List[Dict],
        period_days: int = 7,
        yoy_mode: str = "auto",
        starrocks_sql: Optional[str] = None,
        dimension_filters: List[Dict[str, str]] = None,
        time_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """
        计算基础统计指标（自行通过 StarRocks 查询上期数据计算 MoM/YoY）

        Args:
            data: 时间序列数据，按日期排序，每行需包含 'date' 或 'time' 字段
            period_days: 周期天数（默认7天）
            yoy_mode: YoY计算模式
            starrocks_sql: StarRocks SQL（用于自行查询上期数据）
            dimension_filters: 维度过滤 [{"column": "GROUP_2", "value": "智能云存储"}, ...]
            time_range: MQL定义的时间范围 {"start": "2026-01-01", "end": "2026-04-27"}（优先用于MoM/YoY计算）

        Returns:
            {
                current: 当期周期总和,
                prev: 上期周期总和,
                avg: 平均值,
                std: 标准差,
                cv: 变异系数,
                mom: 环比变化率,
                yoy: 同比变化率
            }
        """
        if not data:
            return {"current": 0, "prev": 0, "avg": 0, "std": 0, "cv": 0, "mom": 0, "yoy": 0}

        dimension_filters = dimension_filters or []

        values = [row.get('value', 0) for row in data if 'value' in row]
        if not values:
            return {"current": 0, "prev": 0, "avg": 0, "std": 0, "cv": 0, "mom": 0, "yoy": 0}

        # ========== 1. 解析日期数据 ==========
        dated_values = []
        for row in data:
            if ('date' in row or 'time' in row) and 'value' in row:
                date_val = row.get('date') or row.get('time')
                val = row.get('value', 0)
                try:
                    from datetime import datetime
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                        try:
                            d = datetime.strptime(str(date_val), fmt)
                            dated_values.append((d, val))
                            break
                        except:
                            continue
                except:
                    continue

        if dated_values:
            dated_values.sort(key=lambda x: x[0])

        current_end = dated_values[-1][0] if dated_values else None
        current_start = dated_values[0][0] if dated_values else None
        current_sum = sum(val for d, val in dated_values)

        # 如果提供了 time_range，优先使用 MQL 定义的时间范围（而非数据里的日期）
        if time_range and time_range.get('start') and time_range.get('end'):
            from datetime import datetime
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                try:
                    mql_start = datetime.strptime(time_range['start'], fmt)
                    mql_end = datetime.strptime(time_range['end'], fmt)
                    current_start = mql_start
                    current_end = mql_end
                    break
                except:
                    continue

        mom = 0.0
        prev_period_sum = 0.0
        yoy = 0.0

        if current_start and current_end and dated_values:
            try:
                from datetime import timedelta

                day_count = (current_end - current_start).days + 1

                # MoM：按相同天数往前推
                prev_start = current_start - timedelta(days=day_count)
                prev_end = current_end - timedelta(days=day_count)

                # YoY：去年同期
                prev_year_start = current_start.replace(year=current_start.year - 1)
                prev_year_end = current_end.replace(year=current_end.year - 1)

                # 如果提供了 starrocks_sql，通过 StarRocks 查询上期数据
                if starrocks_sql:
                    # 解析 starrocks_sql 获取表名和字段
                    import re
                    sum_match = re.search(r"SUM\s*\(\s*([A-Z_]+)\s*\)", starrocks_sql, re.IGNORECASE)
                    metric_field = sum_match.group(1) if sum_match else None
                    table_match = re.search(r"FROM\s+([a-zA-Z0-9_\.]+)", starrocks_sql, re.IGNORECASE)
                    table_name = table_match.group(1) if table_match else None

                    if metric_field and table_name:
                        # 构建维度过滤条件（去重）
                        dim_filter_clause = ""
                        if dimension_filters:
                            seen = set()
                            for f in dimension_filters:
                                col = f.get("column", "")
                                val = f.get("value", "")
                                key = f"{col}={val}"
                                if col and val and key not in seen:
                                    seen.add(key)
                                    dim_filter_clause += f" AND {col} = '{val}'"
                            logger.info(f"[calculate_basic_stats] 维度过滤: {dim_filter_clause}")

                        # 查询 MoM 上期
                        mom_sql = (
                            f"SELECT SUM({metric_field}) AS prev_val "
                            f"FROM {table_name} "
                            f"WHERE FDATE >= '{prev_start.strftime('%Y-%m-%d')}' "
                            f"AND FDATE <= '{prev_end.strftime('%Y-%m-%d')}'"
                            f"{dim_filter_clause}"
                        )
                        logger.info(f"[calculate_basic_stats] 查询MoM上期: {mom_sql}")
                        mom_prev = await self._query_starrocks_sum(mom_sql)
                        if mom_prev and mom_prev > 0:
                            mom = (current_sum - mom_prev) / mom_prev
                            prev_period_sum = mom_prev
                            logger.info(f"[calculate_basic_stats] MoM(StarRocks): current={current_sum}, prev={mom_prev}, mom={mom*100:.1f}%")

                        # 查询 YoY 上期
                        yoy_sql = (
                            f"SELECT SUM({metric_field}) AS prev_val "
                            f"FROM {table_name} "
                            f"WHERE FDATE >= '{prev_year_start.strftime('%Y-%m-%d')}' "
                            f"AND FDATE <= '{prev_year_end.strftime('%Y-%m-%d')}'"
                            f"{dim_filter_clause}"
                        )
                        logger.info(f"[calculate_basic_stats] 查询YoY上期: {yoy_sql}")
                        yoy_prev = await self._query_starrocks_sum(yoy_sql)
                        if yoy_prev and yoy_prev > 0:
                            yoy = (current_sum - yoy_prev) / yoy_prev
                            logger.info(f"[calculate_basic_stats] YoY(StarRocks): current={current_sum}, prev={yoy_prev}, yoy={yoy*100:.1f}%")
                    else:
                        logger.warning(f"[calculate_basic_stats] 无法从 starrocks_sql 解析出字段: {starrocks_sql[:80]}")
                else:
                    # 无 starrocks_sql，回退用图表数据估算
                    prev_period_sum = sum(val for d, val in dated_values if prev_start <= d <= prev_end)
                    if prev_period_sum > 0:
                        mom = (current_sum - prev_period_sum) / prev_period_sum
                        logger.info(f"[calculate_basic_stats] MoM(chart): current={current_sum}, prev_period={prev_period_sum}, mom={mom*100:.1f}%")

                    yoy_sum = sum(val for d, val in dated_values if prev_year_start <= d <= prev_year_end)
                    if yoy_sum > 0:
                        yoy = (current_sum - yoy_sum) / yoy_sum
                        logger.info(f"[calculate_basic_stats] YoY(chart): current={current_sum}, prev_year={yoy_sum}, yoy={yoy*100:.1f}%")

            except Exception as e:
                logger.warning(f"[calculate_basic_stats] 计算失败: {e}")
                mom = 0.0
                prev_period_sum = 0.0
                yoy = 0.0

        # ========== 3. 计算其他统计指标 ==========
        avg = sum(values) / len(values) if values else 0
        variance = sum((x - avg) ** 2 for x in values) / len(values) if values else 0
        std = math.sqrt(variance)
        cv = std / avg if avg != 0 else 0

        return {
            "current": current_sum,
            "prev": prev_period_sum,
            "avg": avg,
            "std": std,
            "cv": cv,
            "mom": mom,
            "yoy": yoy,
        }

    async def _query_starrocks_sum(self, sql: str) -> Optional[float]:
        """通过 Go API 查询 StarRocks，返回 SUM 结果"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "http://localhost:8080/api/v1/query/execute",
                    json={"sql": sql, "timeout": 30},
                )
                data = resp.json()
                if data.get("code") == 0 and data.get("data"):
                    inner = data["data"]
                    rows = inner.get("data") if isinstance(inner, dict) else inner
                    if rows and len(rows) > 0:
                        row = rows[0]
                        # 尝试获取 SUM 别名或原始字段
                        val = row.get("prev_val") or row.get(list(row.keys())[0]) if row else None
                        if val is not None:
                            return float(val)
        except Exception as e:
            logger.warning(f"[_query_starrocks_sum] 查询失败: {e}, sql={sql[:100]}")
        return None

    async def _query_sku_dimension_data(
        self,
        starrocks_sql: str,
        dimension_filters: List[Dict[str, str]],
        time_range: Optional[Dict[str, str]],
        period_days: int,
    ) -> tuple:
        """
        按 SKU 分组查询当期和上期的维度数据（用于核心驱动分析）

        Returns:
            (current_dim_data, prev_dim_data): 均为 [{"dimension": "SKU1", "value": xxx}, ...]
        """
        import re
        from datetime import datetime, timedelta

        if not starrocks_sql:
            return [], []

        # 解析 starrocks_sql
        sum_match = re.search(r"SUM\s*\(\s*([A-Z_]+)\s*\)", starrocks_sql, re.IGNORECASE)
        metric_field = sum_match.group(1) if sum_match else None
        table_match = re.search(r"FROM\s+([a-zA-Z0-9_\.]+)", starrocks_sql, re.IGNORECASE)
        table_name = table_match.group(1) if table_match else None

        if not metric_field or not table_name:
            logger.warning(f"[_query_sku_dimension_data] 无法从 starrocks_sql 解析出字段: {starrocks_sql[:80]}")
            return [], []

        # 解析时间范围
        current_start, current_end = None, None
        if time_range and time_range.get('start') and time_range.get('end'):
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                try:
                    current_start = datetime.strptime(time_range['start'], fmt)
                    current_end = datetime.strptime(time_range['end'], fmt)
                    break
                except:
                    continue

        if not current_start or not current_end:
            logger.warning(f"[_query_sku_dimension_data] 无法解析 time_range: {time_range}")
            return [], []

        day_count = (current_end - current_start).days + 1
        prev_start = current_start - timedelta(days=day_count)
        prev_end = current_end - timedelta(days=day_count)

        # 构建维度过滤条件（去重）
        dim_filter_clause = ""
        if dimension_filters:
            seen = set()
            for f in dimension_filters:
                col = f.get("column", "")
                val = f.get("value", "")
                key = f"{col}={val}"
                if col and val and key not in seen:
                    seen.add(key)
                    dim_filter_clause += f" AND {col} = '{val}'"

        async def query_sku(sql: str) -> List[Dict]:
            """执行 SQL 并返回按 SKU 分组的结果"""
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "http://localhost:8080/api/v1/query/execute",
                        json={"sql": sql, "timeout": 30},
                    )
                    data = resp.json()
                    if data.get("code") == 0 and data.get("data"):
                        inner = data["data"]
                        rows = inner.get("data") if isinstance(inner, dict) else inner
                        result = []
                        for row in rows:
                            sku = row.get("SKU") or row.get("sku") or row.get(list(row.keys())[0]) if row else None
                            val = row.get(metric_field) or row.get(list(row.keys())[1]) if row else None
                            if sku is not None and val is not None:
                                result.append({"dimension": str(sku), "value": float(val)})
                        return result
            except Exception as e:
                logger.warning(f"[_query_sku_dimension_data] SKU查询失败: {e}, sql={sql[:100]}")
            return []

        # 查询当期 SKU 数据
        current_sql = (
            f"SELECT SKU, SUM({metric_field}) AS val "
            f"FROM {table_name} "
            f"WHERE FDATE >= '{current_start.strftime('%Y-%m-%d')}' "
            f"AND FDATE <= '{current_end.strftime('%Y-%m-%d')}'"
            f"{dim_filter_clause} "
            f"GROUP BY SKU ORDER BY val DESC LIMIT 20"
        )
        logger.info(f"[_query_sku_dimension_data] 查询当期SKU: {current_sql}")
        current_dim_data = await query_sku(current_sql)

        # 查询上期 SKU 数据
        prev_sql = (
            f"SELECT SKU, SUM({metric_field}) AS val "
            f"FROM {table_name} "
            f"WHERE FDATE >= '{prev_start.strftime('%Y-%m-%d')}' "
            f"AND FDATE <= '{prev_end.strftime('%Y-%m-%d')}'"
            f"{dim_filter_clause} "
            f"GROUP BY SKU ORDER BY val DESC LIMIT 20"
        )
        logger.info(f"[_query_sku_dimension_data] 查询上期SKU: {prev_sql}")
        prev_dim_data = await query_sku(prev_sql)

        return current_dim_data, prev_dim_data

    def detect_anomaly_iqr(
        self,
        values: List[float],
        volatility_threshold_warning: float = 0.15,
        volatility_threshold_critical: float = 0.25
    ) -> Dict[str, Any]:
        """
        IQR 四分位距异常检测（修复版：阈值可配置）

        Args:
            values: 数值列表
            volatility_threshold_warning: 波动阈值（默认15%）
            volatility_threshold_critical: 异常阈值（默认25%）

        Returns:
            {
                is_anomaly: bool,
                anomaly_level: normal / 波动 / 异常,
                anomaly_values: List[float]
            }
        """
        if len(values) < 4:
            return {"is_anomaly": False, "anomaly_level": "normal", "anomaly_values": []}

        # 过滤掉0值（可能是未完成的当天数据）
        non_zero_values = [v for v in values if v > 0]
        if len(non_zero_values) < 4:
            return {"is_anomaly": False, "anomaly_level": "normal", "anomaly_values": []}

        sorted_vals = sorted(non_zero_values)
        n = len(sorted_vals)

        # Q1, Q3
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_vals[q1_idx]
        q3 = sorted_vals[q3_idx]
        iqr = q3 - q1

        # 上下界
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        # 异常值（用过滤后的数据）
        anomaly_values = [v for v in non_zero_values if v < lower or v > upper]

        # 计算波动率（用最后一个非0值）
        current = non_zero_values[-1] if non_zero_values else 0
        avg = sum(non_zero_values) / len(non_zero_values) if non_zero_values else 0
        volatility_rate = abs(current - avg) / avg if avg != 0 else 0

        # ========== 修复 2：阈值可配置 ==========
        anomaly_level = "normal"
        if volatility_rate > volatility_threshold_critical or anomaly_values:
            anomaly_level = "异常"
        elif volatility_rate > volatility_threshold_warning:
            anomaly_level = "波动"
        # =======================================

        is_anomaly = anomaly_level != "normal"

        return {
            "is_anomaly": is_anomaly,
            "anomaly_level": anomaly_level,
            "anomaly_values": anomaly_values,
            "volatility_rate": volatility_rate
        }

    def calc_dimension_contribution(
        self,
        current_data: List[Dict],
        prev_data: Optional[List[Dict]],
        dimension_key: str = "dimension"
    ) -> Dict[str, List[Dict]]:
        """
        计算各维度对波动的贡献度（修复版：使用真实上期数据）

        Args:
            current_data: 当前期数据（按维度分组的）
            prev_data: 上期数据（如果有的话）
            dimension_key: 维度字段名

        Returns:
            {
                "positive": [{"name": xxx, "value": xxx, "contribution": xxx}, ...],
                "negative": [{"name": xxx, "value": xxx, "contribution": xxx}, ...]
            }
        """
        if not current_data:
            return {"positive": [], "negative": []}

        current_total = sum(row.get('value', 0) for row in current_data)

        if not prev_data:
            # 无上期数据，只返回当期占比
            contributions = []
            for row in current_data:
                val = row.get('value', 0)
                contribution = (val / current_total * 100) if current_total != 0 else 0
                contributions.append({
                    "name": row.get(dimension_key, "未知"),
                    "value": val,
                    "change": None,
                    "change_pct": None,
                    "contribution": contribution,
                    "has_prev_data": False
                })
            contributions.sort(key=lambda x: x["contribution"], reverse=True)
            return {
                "positive": [c for c in contributions if c["contribution"] > 0][:3],
                "negative": []
            }

        # ========== 修复 3：使用真实上期数据而非比例估算 ==========
        prev_dict = {row.get(dimension_key): row.get('value', 0) for row in prev_data}
        prev_total = sum(prev_dict.values())
        total_change = current_total - prev_total

        contributions = []
        for row in current_data:
            dim_name = row.get(dimension_key, "未知")
            curr_val = row.get('value', 0)
            prev_val = prev_dict.get(dim_name, 0)

            change = curr_val - prev_val
            contribution = change / total_change * 100 if total_change != 0 else 0
            change_pct = (change / prev_val * 100) if prev_val != 0 else None

            contributions.append({
                "name": dim_name,
                "value": curr_val,
                "prev_value": prev_val,
                "change": change,
                "change_pct": change_pct,
                "contribution": contribution,
                "has_prev_data": True
            })
        # =========================================================

        contributions.sort(key=lambda x: x["contribution"], reverse=True)
        positive = [c for c in contributions if c["contribution"] > 0][:3]
        negative = [c for c in contributions if c["contribution"] < 0][:3]
        negative.sort(key=lambda x: x["contribution"])

        return {
            "positive": positive,
            "negative": negative
        }

    def _calc_category_drivers(
        self,
        data: List[Dict],
        prev_data: Optional[List[Dict]] = None,
        dimension_key: str = "dimension"
    ) -> Dict[str, List[Dict]]:
        """
        对于分类数据，计算品类贡献度（修复版：支持上期数据）

        Args:
            data: 当前期数据
            prev_data: 上期数据（可选）
            dimension_key: 维度字段名
        """
        if not data:
            return {"positive": [], "negative": []}

        current_total = sum(row.get('value', 0) for row in data)
        current_dict = {row.get(dimension_key): row.get('value', 0) for row in data}

        results = []
        for dim_name, curr_val in current_dict.items():
            contribution = (curr_val / current_total * 100) if current_total != 0 else 0

            if prev_data:
                prev_dict = {row.get(dimension_key): row.get('value', 0) for row in prev_data}
                prev_val = prev_dict.get(dim_name, 0)
                change = curr_val - prev_val
                change_pct = (change / prev_val * 100) if prev_val != 0 else None
            else:
                prev_val = 0
                change = None
                change_pct = None

            results.append({
                "name": dim_name,
                "value": curr_val,
                "prev_value": prev_val,
                "change": change,
                "change_pct": change_pct,
                "contribution": contribution,
                "has_prev_data": prev_data is not None
            })

        results.sort(key=lambda x: x["value"], reverse=True)
        return {
            "positive": results[:3],
            "negative": results[-3:] if len(results) > 3 else results
        }

    def _split_current_prev_dim_data(
        self,
        data: List[Dict],
        period_days: int = 7,
        dimension_key: str = "dimension"
    ) -> tuple:
        """
        从时间序列数据中拆分当前期和上期的维度数据

        数据格式约定：
        [
            {"date": "2026-04-27", "dimension": "站点A", "value": 100},
            {"date": "2026-04-27", "dimension": "站点B", "value": 200},
            {"date": "2026-04-20", "dimension": "站点A", "value": 90},
            {"date": "2026-04-20", "dimension": "站点B", "value": 180},
        ]
        """
        if not data:
            return [], []

        # 提取所有唯一日期并排序
        dates = sorted({row.get("date", row.get("time", "")) for row in data})
        if len(dates) < 2:
            return data, []  # 数据不足，返回当前期

        # 拆分当前周期和上期周期的日期
        current_dates = dates[-period_days:] if len(dates) >= period_days else dates
        prev_dates = dates[-period_days*2:-period_days] if len(dates) >= period_days*2 else dates[:-period_days]

        # 提取对应数据
        current_data = [row for row in data if row.get("date", row.get("time", "")) in current_dates]
        prev_data = [row for row in data if row.get("date", row.get("time", "")) in prev_dates]

        # 按维度聚合（同一维度多天数据求和）
        def aggregate_by_dim(data_list: List[Dict]) -> List[Dict]:
            dim_groups = {}
            for row in data_list:
                dim = row.get(dimension_key, "未知")
                val = row.get('value', 0)
                dim_groups[dim] = dim_groups.get(dim, 0) + val
            return [{"dimension": k, "value": v} for k, v in dim_groups.items()]

        return aggregate_by_dim(current_data), aggregate_by_dim(prev_data)

    async def llm_root_cause_analysis(
        self,
        stats: Dict[str, float],
        dims: Dict[str, List[Dict]],
        metric_name: str
    ) -> Dict[str, Any]:
        """
        LLM 根因分析
        """
        # 构建 prompt
        prompt = f"""指标：{metric_name}
当前周期值：{stats.get('current', 0):.2f}
上期周期值：{stats.get('prev', 0):.2f}
平均值：{stats.get('avg', 0):.2f}
环比变化：{stats.get('mom', 0)*100:.1f}%
同比变化：{stats.get('yoy', 0)*100:.1f}%
波动率：{stats.get('cv', 0)*100:.1f}%

正向驱动因素：
{chr(10).join([f"- {d['name']}: 贡献{d['contribution']:.1f}%" for d in dims.get('positive', [])]) if dims.get('positive') else '无'}

负向拖累因素：
{chr(10).join([f"- {d['name']}: 拖累{abs(d['contribution']):.1f}%" for d in dims.get('negative', [])]) if dims.get('negative') else '无'}

请按以下结构输出分析结论：
1. 指标概况（数值、环比、同比）
2. 波动与异常判断
3. 核心驱动维度（TOP3）
4. 可能根因（从以下类别选择：业务活动/流量变化/结构变化/数据口径/系统异常）
5. 结论与建议（简洁专业，可直接用于汇报）

输出格式：
根因：[归类]
置信度：[0-1之间的数值]
建议：[一句话建议]"""

        try:
            response = await self._llm_engine.generate(
                prompt=prompt,
                system_prompt=VOLATILITY_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=500
            )

            # 简单解析 LLM 输出
            result = self._parse_llm_response(response)
            return result

        except Exception as e:
            import traceback
            logger.error(f"LLM 根因分析失败: {type(e).__name__}: {e}")
            logger.error(f"LLM 配置信息: use_case=ask, model={getattr(self._llm_engine, 'model', 'N/A')}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return {
                "root_cause": "分析失败",
                "confidence": 0.0,
                "suggestion": f"LLM服务异常: {type(e).__name__}"
            }

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应（修复版：支持中英文冒号）"""
        lines = response.strip().split('\n')
        root_cause = "待分析"
        confidence = 0.5
        suggestion = "建议持续关注数据变化"

        for line in lines:
            line = line.strip()
            # 支持中文冒号和英文冒号
            if "根因" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    root_cause = parts[1].strip()
            elif "置信度" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    try:
                        confidence = float(parts[1].strip())
                    except:
                        confidence = 0.5
            elif "建议" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    suggestion = parts[1].strip()

        return {
            "root_cause": root_cause,
            "confidence": confidence,
            "suggestion": suggestion
        }

    def _detect_data_type(self, data: List[Dict]) -> str:
        """
        检测数据格式类型

        Returns:
            "time_series": 多天数据，每行是独立时间点
            "category": 单天数据，每行是不同维度/分类
        """
        if not data or len(data) < 2:
            return "category"

        # 提取所有日期
        dates = set()
        for row in data:
            date_val = row.get("date") or row.get("time") or ""
            if date_val:
                dates.add(str(date_val))

        # 多个不同日期 → 时间序列
        if len(dates) > 1:
            return "time_series"

        # 只有一个日期或没有日期 → 分类数据
        return "category"

    async def analyze_stream(
        self,
        metric_name: str,
        data: List[Dict],
        time_range: Optional[Dict[str, str]] = None,
        dimension_key: str = "dimension",
        period_days: int = 7,
        mom_change: Optional[float] = None,
        yoy_change: Optional[float] = None,
        starrocks_sql: Optional[str] = None,
        dimension_filters: List[Dict[str, str]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        流式波动分析（支持自行计算MoM/YoY）

        Args:
            period_days: 周期天数（默认7天）
            mom_change: SQL层计算的环比变化率（如果传了就用这个，不再重复计算）
            yoy_change: SQL层计算的同比变化率（如果传了就用这个，不再重复计算）
            starrocks_sql: StarRocks SQL（用于自行计算MoM/YoY）
            dimension_filters: 维度过滤 [{"column": "GROUP_2", "value": "智能云存储"}, ...]
        """
        if dimension_filters is None:
            dimension_filters = []
        logger.info(f"[VolatilityAnalyzer] 开始分析指标: {metric_name}, 数据量: {len(data)}, mom={mom_change}, yoy={yoy_change}, starrocks_sql={'有' if starrocks_sql else '无'}, dimension_filters={dimension_filters}")

        # 检测数据格式
        data_type = self._detect_data_type(data)
        logger.info(f"[VolatilityAnalyzer] 数据格式检测: {data_type}")

        if data_type == "category":
            # 分类数据分析
            async for event in self._analyze_category_data(metric_name, data, dimension_key):
                yield event
        else:
            # 时间序列数据分析
            async for event in self._analyze_time_series(
                metric_name, data, dimension_key, period_days,
                mom_change=mom_change, yoy_change=yoy_change,
                starrocks_sql=starrocks_sql,
                dimension_filters=dimension_filters,
                time_range=time_range,
            ):
                yield event

        logger.info(f"[VolatilityAnalyzer] 分析完成: {metric_name}")

    async def _analyze_category_data(
        self,
        metric_name: str,
        data: List[Dict],
        dimension_key: str = "dimension"
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        分类数据分析：直接展示品类贡献度
        """
        # 计算总值
        total = sum(row.get('value', 0) for row in data)

        # Step 1: 概况 - 分类数据无法计算环比同比，显示总数和品类数
        overview_data = {
            "metric_name": metric_name,
            "current_value": total,
            "prev_value": 0,
            "avg_value": total / len(data) if data else 0,
            "mom_change": 0,
            "mom_change_pct": "N/A",
            "yoy_change": 0,
            "yoy_change_pct": "N/A",
            "volatility_rate": 0,
            "volatility_rate_pct": "N/A",
            "anomaly_level": "normal",
            "is_anomaly": False,
            "data_type": "category",
            "category_count": len(data)
        }

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_overview",
                **overview_data
            }
        )

        # Step 2: 图表数据 - 分类数据用柱状图
        chart_data = []
        sorted_data = sorted(data, key=lambda x: x.get('value', 0), reverse=True)
        for row in sorted_data:
            chart_data.append({
                "date": row.get(dimension_key, ""),
                "value": row.get('value', 0)
            })

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_chart",
                "chart_data": chart_data,
                "chart_type": "bar"
            }
        )

        # Step 3: 品类驱动
        dims = self._calc_category_drivers(data, None, dimension_key)

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_dims",
                "positive_dims": dims['positive'],
                "negative_dims": dims['negative']
            }
        )

        # Step 4: LLM 分析
        yield StreamEvent(
            event=SSSEvent.THINKING,
            data={
                "type": "volatility_llm_reasoning",
                "stage": "analyzing",
                "content": "正在分析品类贡献度..."
            }
        )

        # 构建分类数据的统计
        stats = {
            "current": total,
            "avg": total / len(data) if data else 0,
            "mom": 0,
            "yoy": 0,
            "cv": 0
        }

        llm_result = await self.llm_root_cause_analysis_category(stats, dims, metric_name, len(data))

        # Step 5: 根因归类
        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_root",
                "root_cause": llm_result['root_cause'],
                "confidence": llm_result['confidence'],
                "suggestion": llm_result['suggestion']
            }
        )

        # Step 6: 完成
        yield StreamEvent(
            event=SSSEvent.DONE,
            data={
                "type": "volatility_done"
            }
        )

    async def _analyze_time_series(
        self,
        metric_name: str,
        data: List[Dict],
        dimension_key: str = "dimension",
        period_days: int = 7,
        mom_change: Optional[float] = None,
        yoy_change: Optional[float] = None,
        starrocks_sql: Optional[str] = None,
        dimension_filters: List[Dict[str, str]] = None,
        time_range: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        时间序列数据分析（支持传入SQL层计算的mom/yoy）
        """
        if dimension_filters is None:
            dimension_filters = []
        # Step 1: 基础统计（使用周期对比）
        # 自行通过 StarRocks 查询上期数据来计算 MoM/YoY（不依赖传入值）
        stats = await self.calculate_basic_stats(data, period_days, starrocks_sql=starrocks_sql, dimension_filters=dimension_filters, time_range=time_range)
        anomaly_result = self.detect_anomaly_iqr([row.get('value', 0) for row in data if 'value' in row])

        stats['volatility_rate'] = anomaly_result.get('volatility_rate', 0)

        # 如果SQL层传了mom/yoy，使用传入值而非重新计算
        final_mom = mom_change if mom_change is not None else stats['mom']
        final_yoy = yoy_change if yoy_change is not None else stats['yoy']

        # 更新stats中的mom/yoy（供LLM分析用）
        stats['mom'] = final_mom
        stats['yoy'] = final_yoy

        overview_data = {
            "metric_name": metric_name,
            "current_value": stats['current'],
            "prev_value": stats['prev'],
            "avg_value": stats['avg'],
            "mom_change": final_mom,
            "mom_change_pct": f"{final_mom*100:.1f}%",
            "yoy_change": final_yoy,
            "yoy_change_pct": f"{final_yoy*100:.1f}%",
            "volatility_rate": stats['volatility_rate'],
            "volatility_rate_pct": f"{stats['volatility_rate']*100:.1f}%",
            "anomaly_level": anomaly_result['anomaly_level'],
            "is_anomaly": anomaly_result['is_anomaly'],
            "data_type": "time_series"
        }

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_overview",
                **overview_data
            }
        )

        # Step 2: 图表数据
        chart_data = []
        for row in data:
            chart_data.append({
                "date": row.get("date", row.get("time", "")),
                "value": row.get('value', 0)
            })

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_chart",
                "chart_data": chart_data,
                "chart_type": "line"
            }
        )

        # ========== 修复 4：按 SKU 分组查询当期/上期数据计算维度贡献 ==========
        # Step 3: 维度贡献度（按 SKU 分组）
        current_dim_data, prev_dim_data = await self._query_sku_dimension_data(
            starrocks_sql, dimension_filters, time_range, period_days
        )
        dims = self.calc_dimension_contribution(
            current_dim_data,
            prev_dim_data,
            "dimension"  # dimension_key 用于兼容，calc_dimension_contribution 内部用 "dimension" 做 key
        )
        # =============================================================

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_dims",
                "positive_dims": dims['positive'],
                "negative_dims": dims['negative']
            }
        )

        # Step 4: LLM 根因分析（流式输出推理过程）
        yield StreamEvent(
            event=SSSEvent.THINKING,
            data={
                "type": "volatility_llm_reasoning",
                "stage": "analyzing",
                "content": "正在分析业务活动因素..."
            }
        )

        llm_result = await self.llm_root_cause_analysis(stats, dims, metric_name)

        # Step 5: 根因归类
        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_root",
                "root_cause": llm_result['root_cause'],
                "confidence": llm_result['confidence'],
                "suggestion": llm_result['suggestion']
            }
        )

        # Step 6: 完成
        yield StreamEvent(
            event=SSSEvent.DONE,
            data={
                "type": "volatility_done"
            }
        )

    async def llm_root_cause_analysis_category(
        self,
        stats: Dict[str, float],
        dims: Dict[str, List[Dict]],
        metric_name: str,
        category_count: int
    ) -> Dict[str, Any]:
        """
        分类数据的 LLM 根因分析
        """
        prompt = f"""指标：{metric_name}
数据类型：品类分布分析（共 {category_count} 个品类）
总销售额：{stats.get('current', 0):.2f}
平均品类销售额：{stats.get('avg', 0):.2f}

TOP3 核心品类（贡献度最高）：
{chr(10).join([f"- {d['name']}: 销售额{d['value']:.2f}，占比{d['contribution']:.1f}%" for d in dims.get('positive', [])]) if dims.get('positive') else '无'}

请按以下结构输出分析结论：
1. 品类概况（总数、最大品类、占比）
2. 核心品类贡献
3. 可能原因（结构变化/品类偏好/季节性等）
4. 结论与建议

输出格式：
根因：[归类]
置信度：[0-1之间的数值]
建议：[一句话建议]"""

        try:
            response = await self._llm_engine.generate(
                prompt=prompt,
                system_prompt=VOLATILITY_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=500
            )

            result = self._parse_llm_response(response)
            return result

        except Exception as e:
            import traceback
            logger.error(f"LLM 品类分析失败: {type(e).__name__}: {e}")
            logger.error(f"LLM 配置信息: use_case=ask, model={getattr(self._llm_engine, 'model', 'N/A')}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return {
                "root_cause": "品类分布分析",
                "confidence": 0.8,
                "suggestion": "品类贡献度分析结果已展示"
            }

    async def analyze(
        self,
        metric_name: str,
        data: List[Dict],
        time_range: Optional[Dict[str, str]] = None,
        dimension_key: str = "dimension",
        period_days: int = 7
    ) -> VolatilityResult:
        """
        同步波动分析（不生成 SSE 流）
        """
        # 基础统计
        stats = await self.calculate_basic_stats(data, period_days)
        anomaly_result = self.detect_anomaly_iqr([row.get('value', 0) for row in data if 'value' in row])

        # 维度贡献度（同步版本先不计算）
        dims = {"positive": [], "negative": []}

        return VolatilityResult(
            metric_name=metric_name,
            current_value=stats['current'],
            mom_change=stats['mom'],
            yoy_change=stats['yoy'],
            volatility_rate=anomaly_result.get('volatility_rate', 0),
            is_anomaly=anomaly_result['is_anomaly'],
            anomaly_level=anomaly_result['anomaly_level'],
            top_positive_dims=dims['positive'],
            top_negative_dims=dims['negative']
        )
