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
from ai.config.runtime import get_go_api_base
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
        self._go_api_base = get_go_api_base()

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
                    f"{self._go_api_base}/api/v1/query/execute",
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

        # 构建维度过滤条件（去重）- SKU 粒度查询不加维度过滤，看整体 top/bottom SKU
        # （dimension_filters 来自 metric 定义，对 SKU 粒度查询会过度约束导致 0 行）
        dim_filter_clause = ""

        async def query_sku(sql: str) -> List[Dict]:
            """执行 SQL 并返回按 SKU 分组的结果"""
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{self._go_api_base}/api/v1/query/execute",
                        json={"sql": sql, "timeout": 30},
                    )
                    data = resp.json()
                    logger.info(f"[_query_sku_dimension_data] API响应: code={data.get('code')}, keys={list(data.keys())}, count={data.get('count')}")
                    # Go API 返回格式: {code: 0, data: {data: [...], columns: [...]}} 或 {cached: True, columns: [...], count: 0, data: null}
                    rows = None
                    if data.get("code") == 0 and data.get("data"):
                        inner = data["data"]
                        rows = inner.get("data") if isinstance(inner, dict) else inner
                    elif "columns" in data:
                        # 无 code 字段的响应格式
                        rows = data.get("data")
                    if rows is None or not isinstance(rows, list):
                        logger.warning(f"[_query_sku_dimension_data] rows无效, rows={rows}, sql={sql[:100]}")
                        return []
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

    async def _query_related_indicators(
        self,
        starrocks_sql: Optional[str],
        dimension_filters: List[Dict[str, str]],
        time_range: Optional[Dict[str, str]],
        period_days: int,
    ) -> Dict[str, Any]:
        """
        查询关联辅助指标（广告产出比/曝光量/销售单价等），用于增强 LLM 根因判断

        Returns:
            {
                "current": [月度数],  # 当前期每月数据
                "prev": [月度数],     # 上期每月数据
            }
        """
        import re
        from datetime import datetime, timedelta

        if not starrocks_sql:
            return {"current": [], "prev": []}

        # 解析 starrocks_sql 获取表名
        table_match = re.search(r"FROM\s+([a-zA-Z0-9_\.]+)", starrocks_sql, re.IGNORECASE)
        table_name = table_match.group(1) if table_match else "ids.IDS_AMZ_COMPREHENSIVE_DI"

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
            logger.warning(f"[_query_related_indicators] 无法解析 time_range: {time_range}")
            return {"current": [], "prev": []}

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

        related_sql = f"""
SELECT
    LEFT(FDATE, 7) AS 月份,
    SKU,
    SUM(INCOME_NBCSS) AS 销售额,
    SUM(TOTALSALES)/NULLIF(SUM(SPEND),0) AS 广告产出比,
    SUM(IMPRESSIONS) AS 曝光量,
    SUM(ORDERED_PRODUCTSALES)/NULLIF(SUM(UNITS_ORDERED),0) AS 销售单价
FROM {table_name}
WHERE FDATE >= '{{}}' AND FDATE <= '{{}}'
{dim_filter_clause}
GROUP BY LEFT(FDATE, 7), SKU
ORDER BY 月份, SKU
""".strip()

        async def query_indicators(sql: str) -> List[Dict]:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{self._go_api_base}/api/v1/query/execute",
                        json={"sql": sql, "timeout": 30},
                    )
                    data = resp.json()
                    if data.get("code") == 0 and data.get("data"):
                        inner = data["data"]
                        rows = inner.get("data") if isinstance(inner, dict) else inner
                        return rows if rows else []
            except Exception as e:
                logger.warning(f"[_query_related_indicators] 查询失败: {e}")
            return []

        # 查询当期和上期
        current_sql = related_sql.format(
            current_start.strftime('%Y-%m-%d'),
            current_end.strftime('%Y-%m-%d')
        )
        prev_sql = related_sql.format(
            prev_start.strftime('%Y-%m-%d'),
            prev_end.strftime('%Y-%m-%d')
        )

        logger.info(f"[_query_related_indicators] 查询当期: {current_sql[:200]}")
        logger.info(f"[_query_related_indicators] 查询上期: {prev_sql[:200]}")

        current_data = await query_indicators(current_sql)
        prev_data = await query_indicators(prev_sql)

        return {"current": current_data, "prev": prev_data}

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
        metric_name: str,
        data: List[Dict] = None,
        related_indicators: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        LLM 根因分析（增强版：含每月趋势 + 更多驱动因素 + 关联指标）
        """
        if data is None:
            data = []
        if related_indicators is None:
            related_indicators = {"current": [], "prev": []}

        # ========== 构建每月趋势数据 ==========

        # ========== 构建每月趋势数据 ==========
        monthly_lines = []
        for row in data:
            date_val = row.get("date") or row.get("time") or ""
            val = row.get("value", 0)
            if date_val and val:
                monthly_lines.append(f"- {date_val}: {val:,.0f}")

        monthly_block = "\n".join(monthly_lines) if monthly_lines else "无月度数据"

        # ========== 构建驱动因素（含绝对值）==========
        def format_driver(d: Dict, sign: str) -> str:
            name = d.get("name", "未知")
            val = d.get("value", 0)
            prev = d.get("prev_value", 0)
            change = d.get("change", 0)
            pct = d.get("change_pct")
            contrib = d.get("contribution", 0)
            pct_str = f"{pct:+.1f}%" if pct else "N/A"
            prev_str = f"{prev:,.0f}" if prev else "0"
            return f"- {name}: 当期{val:,.0f} | 上期{prev_str} | 变化{pct_str} | 贡献{sign}{abs(contrib):.1f}%"

        pos_lines = [format_driver(d, "+") for d in dims.get("positive", [])]
        neg_lines = [format_driver(d, "-") for d in dims.get("negative", [])]

        # ========== 构建关联指标区块（每一行明细都传给 LLM）==========
        related_block = "无关联数据"
        current_ind = related_indicators.get("current", [])
        prev_ind = related_indicators.get("prev", [])
        if current_ind and len(current_ind) > 0:
            def to_float(val):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None

            # 按 (月份, SKU) 建立索引
            prev_index = {}
            for row in prev_ind:
                key = (str(row.get("月份", "")), str(row.get("SKU", "")))
                prev_index[key] = row

            # 按周期内月份排序（2026-01, 2026-02... 对应 2025-09, 2025-10...）
            # 注意：当期 2026-01 对应上期 2025-09（同一周期的第1个月）
            curr_months_sorted = sorted(set(str(r.get("月份", "")) for r in current_ind))
            prev_months_sorted = sorted(set(str(r.get("月份", "")) for r in prev_ind))

            # 月份位置映射：当期第N个月 → 上期第N个月
            month_pos_map = {}
            for i, curr_m in enumerate(curr_months_sorted):
                prev_m = prev_months_sorted[i] if i < len(prev_months_sorted) else None
                month_pos_map[curr_m] = prev_m

            # 生成对比文本：top 5（正向驱动）+ bottom 5（负向拖累），避免超出 context limit
            sorted_rows = sorted(current_ind, key=lambda r: abs(to_float(r.get("销售额")) or 0), reverse=True)
            top_rows = sorted_rows[:5]
            bottom_rows = sorted_rows[-5:] if len(sorted_rows) >= 5 else sorted_rows
            all_selected = top_rows + bottom_rows

            related_lines = []
            for row in all_selected:
                month = str(row.get("月份", ""))
                sku = str(row.get("SKU", ""))
                c_sales = to_float(row.get("销售额"))
                c_roas = to_float(row.get("广告产出比"))
                c_imp = to_float(row.get("曝光量"))
                c_price = to_float(row.get("销售单价"))

                # 用位置映射找上期月份
                prev_month = month_pos_map.get(month)
                p_row = prev_index.get((prev_month, sku), {}) if prev_month else {}
                p_sales = to_float(p_row.get("销售额")) if p_row else None
                p_roas = to_float(p_row.get("广告产出比")) if p_row else None
                p_imp = to_float(p_row.get("曝光量")) if p_row else None
                p_price = to_float(p_row.get("销售单价")) if p_row else None

                def fmt_val(val, fmt=".0f"):
                    if val is None:
                        return "N/A"
                    try:
                        v = float(val)
                        if abs(v) > 100:
                            return f"{v:,.0f}"
                        return f"{v:{fmt}}"
                    except (TypeError, ValueError):
                        return "N/A"

                def fmt_chg_cur(c, p):
                    if c is None or p is None or p == 0:
                        return "N/A"
                    return f"{(c-p)/p*100:+.1f}%"

                # 用上期月份显示，没有则标 N/A
                period_label = f"{month}"
                if prev_month and prev_month != month:
                    period_label = f"{month}(vs {prev_month})"

                line = (
                    f"- {period_label} {sku}: "
                    f"销售额={fmt_val(c_sales)}"
                    f"(上期{fmt_val(p_sales)} {fmt_chg_cur(c_sales, p_sales)}) | "
                    f"广告产出比={fmt_val(c_roas, '.2f')}"
                    f"(上期{fmt_val(p_roas, '.2f')} {fmt_chg_cur(c_roas, p_roas)}) | "
                    f"曝光量={fmt_val(c_imp)}"
                    f"(上期{fmt_val(p_imp)} {fmt_chg_cur(c_imp, p_imp)}) | "
                    f"销售单价={fmt_val(c_price, '.1f')}"
                    f"(上期{fmt_val(p_price, '.1f')} {fmt_chg_cur(c_price, p_price)})"
                )
                related_lines.append(line)

            related_block = "\n".join(related_lines) if related_lines else "无关联数据"

        # ========== 构建 prompt ==========
        prompt = f"""你是指标波动分析专家，请根据以下真实数据给出深入分析。

## 指标概况
- 指标名称：{metric_name}
- 当期合计：{stats.get('current', 0):,.0f}
- 上期合计：{stats.get('prev', 0):,.0f}
- 平均值：{stats.get('avg', 0):,.0f}
- 环比（MoM）：{stats.get('mom', 0)*100:+.1f}%
- 同比（YoY）：{stats.get('yoy', 0)*100:+.1f}%
- 波动率（CV）：{stats.get('cv', 0)*100:.1f}%

## 每月趋势（当期）
{monthly_block}

## 核心驱动因素（按贡献排序）
正向驱动（贡献最大）:
{chr(10).join(pos_lines) if pos_lines else '无'}

负向拖累（拖累最大）:
{chr(10).join(neg_lines) if neg_lines else '无'}

## 关联指标（同期对比）
{related_block}

## 分析要求
请深度分析：
1. 结合每月趋势和驱动因素，找出波动的关键原因
2. 判断是业务活动、流量变化、结构变化、数据口径还是系统异常
3. 给出一句最有价值的洞察

## 输出格式（必须严格JSON）
{{
  "confidence": 0.0-1.0之间的置信度数值,
  "suggestion": "给出2-3条具体可执行的建议，每条格式为：1.【标题】具体描述，标题要简洁概括问题类型（如：核心SKU断崖复盘/新SKU效率优化/数据异常监控），描述要指明具体问题来源（具体SKU或具体指标）",
  "summary": "3-5句话的深度分析摘要，结合具体数字说明问题根源",
  "key_insight": "一句话核心洞察"
}}"""

        logger.info(f"[llm_root_cause_analysis] prompt内容:\n{prompt[:3000]}")

        try:
            response = await self._llm_engine.generate(
                prompt=prompt,
                system_prompt=VOLATILITY_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1200
            )

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
                "suggestion": f"LLM服务异常: {type(e).__name__}",
                "summary": "",
                "key_insight": ""
            }

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应：优先 JSON 解析，fallback 到行解析，同时清洗 markdown 标记"""
        # 清洗 markdown 标记
        cleaned = response.replace("**", "").replace("*", "").strip()

        # 优先尝试 JSON 解析
        try:
            import json, re
            # 提取第一个 {...} 块
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "root_cause": str(parsed.get("root_cause", "待分析")).strip(),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "suggestion": str(parsed.get("suggestion", "建议持续关注数据变化")).strip(),
                    "summary": str(parsed.get("summary", "")).strip(),
                    "key_insight": str(parsed.get("key_insight", "")).strip(),
                }
        except Exception:
            pass

        # Fallback：按行解析
        lines = cleaned.split('\n')
        root_cause = "待分析"
        confidence = 0.5
        suggestion = "建议持续关注数据变化"
        summary = ""
        key_insight = ""

        for line in lines:
            line = line.strip()
            if "root_cause" in line.lower() or "根因" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    root_cause = parts[1].strip().replace("**", "")
            elif "confidence" in line.lower() or "置信度" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    try:
                        confidence = float(parts[1].strip())
                    except:
                        confidence = 0.5
            elif "suggestion" in line.lower() or "建议" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    suggestion = parts[1].strip().replace("**", "")
            elif "summary" in line.lower() or "摘要" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    summary = parts[1].strip().replace("**", "")
            elif "key_insight" in line.lower() or "洞察" in line:
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1:
                    key_insight = parts[1].strip().replace("**", "")

        return {
            "root_cause": root_cause,
            "confidence": confidence,
            "suggestion": suggestion,
            "summary": summary,
            "key_insight": key_insight
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

        # Step 5: 根因归类（不再展示 root_cause，只展示置信度和详细建议）
        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_root",
                "confidence": llm_result.get('confidence', 0),
                "suggestion": llm_result.get('suggestion', ''),
                "summary": llm_result.get('summary', ''),
                "key_insight": llm_result.get('key_insight', '')
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

        # 查询关联指标（广告产出比/曝光量/销售单价等）
        related_indicators = await self._query_related_indicators(
            starrocks_sql, dimension_filters, time_range, period_days
        )

        llm_result = await self.llm_root_cause_analysis(
            stats, dims, metric_name, data=data, related_indicators=related_indicators
        )

        # Step 5: 根因归类（不再展示 root_cause，只展示置信度和详细建议）
        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_root",
                "confidence": llm_result.get('confidence', 0),
                "suggestion": llm_result.get('suggestion', ''),
                "summary": llm_result.get('summary', ''),
                "key_insight": llm_result.get('key_insight', '')
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
        分类数据的 LLM 根因分析（增强版）
        """
        # 构建驱动因素详情
        def format_driver(d: Dict) -> str:
            name = d.get("name", "未知")
            val = d.get("value", 0)
            prev = d.get("prev_value", 0)
            pct = d.get("change_pct")
            contrib = d.get("contribution", 0)
            pct_str = f"{pct:+.1f}%" if pct else "N/A"
            prev_str = f"{prev:,.0f}" if prev else "0"
            return f"- {name}: 当期{val:,.0f} | 上期{prev_str} | 变化{pct_str} | 贡献{abs(contrib):.1f}%"

        pos_lines = [format_driver(d) for d in dims.get("positive", [])]
        neg_lines = [format_driver(d) for d in dims.get("negative", [])]

        prompt = f"""你是指标波动分析专家，请根据以下真实数据给出深入分析。

## 指标概况
- 指标名称：{metric_name}
- 数据类型：品类分布分析（共 {category_count} 个品类）
- 总计：{stats.get('current', 0):,.0f}
- 平均值：{stats.get('avg', 0):,.0f}

## 核心品类（按贡献排序）
正向驱动（贡献最大）:
{chr(10).join(pos_lines) if pos_lines else '无'}

负向拖累（拖累最大）:
{chr(10).join(neg_lines) if neg_lines else '无'}

## 分析要求
请深度分析：
1. 结合品类结构和贡献因素，找出关键原因
2. 判断是业务活动、流量变化、结构变化、数据口径还是系统异常
3. 给出一句最有价值的洞察

## 输出格式（必须严格JSON）
{{
  "confidence": 0.0-1.0之间的置信度数值,
  "suggestion": "给出2-3条具体可执行的建议，每条格式为：1.【标题】具体描述，标题要简洁概括问题类型（如：核心SKU断崖复盘/新SKU效率优化/数据异常监控），描述要指明具体问题来源（具体SKU或具体指标）",
  "summary": "3-5句话的深度分析摘要，结合具体数字说明问题根源",
  "key_insight": "一句话核心洞察"
}}"""

        try:
            response = await self._llm_engine.generate(
                prompt=prompt,
                system_prompt=VOLATILITY_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1200
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
