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

    def calculate_basic_stats(self, data: List[Dict]) -> Dict[str, float]:
        """
        计算基础统计指标

        Returns:
            {
                current: 当期值,
                prev: 上期值,
                avg: 平均值,
                std: 标准差,
                cv: 变异系数,
                mom: 环比变化率,
                yoy: 同比变化率
            }
        """
        if not data:
            return {"current": 0, "prev": 0, "avg": 0, "std": 0, "cv": 0, "mom": 0, "yoy": 0}

        values = [row.get('value', 0) for row in data if 'value' in row]
        if not values:
            return {"current": 0, "prev": 0, "avg": 0, "std": 0, "cv": 0, "mom": 0, "yoy": 0}

        current = values[-1] if values else 0
        prev = values[-2] if len(values) > 1 else 0
        avg = sum(values) / len(values) if values else 0

        # 标准差
        variance = sum((x - avg) ** 2 for x in values) / len(values) if values else 0
        std = math.sqrt(variance)

        # 变异系数
        cv = std / avg if avg != 0 else 0

        # 环比变化率
        mom = (current - prev) / prev if prev != 0 else 0

        # 同比变化率（假设数据按天排列，取同周期数据）
        yoy = 0
        if len(values) >= 7:  # 至少有一周数据
            yoy = (current - values[-8]) / values[-8] if values[-8] != 0 else 0

        return {
            "current": current,
            "prev": prev,
            "avg": avg,
            "std": std,
            "cv": cv,
            "mom": mom,
            "yoy": yoy
        }

    def detect_anomaly_iqr(self, values: List[float]) -> Dict[str, Any]:
        """
        IQR 四分位距异常检测

        Returns:
            {
                is_anomaly: bool,
                anomaly_level: normal / 波动 / 异常,
                anomaly_values: List[float]  # 异常值列表
            }
        """
        if len(values) < 4:
            return {"is_anomaly": False, "anomaly_level": "normal", "anomaly_values": []}

        sorted_vals = sorted(values)
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

        # 异常值
        anomaly_values = [v for v in values if v < lower or v > upper]

        # 计算波动率（用于判断）
        current = values[-1] if values else 0
        avg = sum(values) / len(values) if values else 0
        volatility_rate = abs(current - avg) / avg if avg != 0 else 0

        # 判断等级
        anomaly_level = "normal"
        if volatility_rate > 0.25 or anomaly_values:
            anomaly_level = "异常"
        elif volatility_rate > 0.15:
            anomaly_level = "波动"

        is_anomaly = anomaly_level != "normal"

        return {
            "is_anomaly": is_anomaly,
            "anomaly_level": anomaly_level,
            "anomaly_values": anomaly_values,
            "volatility_rate": volatility_rate
        }

    def calc_dimension_contribution(
        self,
        data: List[Dict],
        current_total: float,
        prev_total: float,
        dimension_key: str = "dimension"
    ) -> Dict[str, List[Dict]]:
        """
        计算各维度对波动的贡献度

        Args:
            data: 当前期数据
            current_total: 当前期总值
            prev_total: 上期总值
            dimension_key: 维度字段名

        Returns:
            {
                "positive": [{"name": xxx, "value": xxx, "contribution": xxx}, ...],
                "negative": [{"name": xxx, "value": xxx, "contribution": xxx}, ...]
            }
        """
        if not data or current_total == prev_total:
            return {"positive": [], "negative": []}

        # 按维度分组
        dim_groups: Dict[str, List[float]] = {}
        for row in data:
            dim_value = row.get(dimension_key, "未知")
            val = row.get('value', 0)
            if dim_value not in dim_groups:
                dim_groups[dim_value] = []
            dim_groups[dim_value].append(val)

        # 计算各维度贡献度
        total_change = current_total - prev_total
        contributions = []

        for dim_name, values in dim_groups.items():
            curr_sum = sum(values)
            # 估算上期值（按比例估算）
            if current_total > 0:
                prev_estimate = curr_sum * (prev_total / current_total) if current_total != 0 else 0
            else:
                prev_estimate = 0

            change = curr_sum - prev_estimate
            contribution = change / total_change if total_change != 0 else 0

            contributions.append({
                "name": dim_name,
                "value": curr_sum,
                "change": change,
                "contribution": contribution * 100  # 转为百分比
            })

        # 按贡献度排序
        contributions.sort(key=lambda x: x["contribution"], reverse=True)

        positive = [c for c in contributions if c["contribution"] > 0][:3]
        negative = [c for c in contributions if c["contribution"] < 0][:3]
        negative.sort(key=lambda x: x["contribution"])  # 负向按最小排

        return {
            "positive": positive,
            "negative": negative
        }

    async def llm_root_cause_analysis(
        self,
        stats: Dict[str, float],
        dims: Dict[str, List[Dict]],
        metric_name: str
    ) -> Dict[str, Any]:
        """
        LLM 根因分析

        Returns:
            {
                "root_cause": str,
                "confidence": float,
                "suggestion": str
            }
        """
        # 构建 prompt
        prompt = f"""指标：{metric_name}
当前值：{stats.get('current', 0):.2f}
平均值：{stats.get('avg', 0):.2f}
环比变化：{stats.get('mom', 0)*100:.1f}%
同比变化：{stats.get('yoy', 0)*100:.1f}%
波动率：{stats.get('cv', 0)*100:.1f}%

正向驱动因素：
{chr(10).join([f"- {d['name']}: 贡献{d['contribution']:.1f}%" for d in dims.get('positive', [])]) if dims.get('positive') else '无'}

负向拖累因素：
{chr(10).join([f"- {d['name']}: 拖累{d['contribution']:.1f}%" for d in dims.get('negative', [])]) if dims.get('negative') else '无'}

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
            logger.error(f"LLM 根因分析失败: {e}")
            return {
                "root_cause": "分析失败",
                "confidence": 0.0,
                "suggestion": "请稍后重试"
            }

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        lines = response.strip().split('\n')
        root_cause = "待分析"
        confidence = 0.5
        suggestion = "建议持续关注数据变化"

        for line in lines:
            line = line.strip()
            if line.startswith("根因："):
                root_cause = line.replace("根因：", "").strip()
            elif line.startswith("置信度："):
                try:
                    confidence = float(line.replace("置信度：", "").strip())
                except:
                    confidence = 0.5
            elif line.startswith("建议："):
                suggestion = line.replace("建议：", "").strip()

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

    def _calc_category_drivers(
        self,
        data: List[Dict],
        dimension_key: str = "dimension"
    ) -> Dict[str, List[Dict]]:
        """
        对于分类数据，计算品类贡献度
        直接用数值排序，TOP3正向=最大值，TOP3负向=最小值
        """
        if not data:
            return {"positive": [], "negative": []}

        # 按value排序
        sorted_data = sorted(data, key=lambda x: x.get('value', 0), reverse=True)

        # 计算总值
        total = sum(row.get('value', 0) for row in data)

        # TOP3 正向（最大）
        positive = []
        for i, row in enumerate(sorted_data[:3]):
            val = row.get('value', 0)
            contribution = (val / total * 100) if total != 0 else 0
            positive.append({
                "name": row.get(dimension_key, f"品类{i+1}"),
                "value": val,
                "change": val,
                "contribution": contribution
            })

        # TOP3 负向（最小）
        negative = []
        for row in sorted_data[-3:]:
            val = row.get('value', 0)
            contribution = (val / total * 100) if total != 0 else 0
            negative.append({
                "name": row.get(dimension_key, "其他"),
                "value": val,
                "change": -val,
                "contribution": -contribution
            })
        negative.reverse()  # 按贡献度从小到大排列

        return {"positive": positive, "negative": negative}

    async def analyze_stream(
        self,
        metric_name: str,
        data: List[Dict],
        time_range: Optional[Dict[str, str]] = None,
        dimension_key: str = "dimension"
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        流式波动分析

        生成 SSE 事件流：
        1. volatility_overview - 基础统计
        2. volatility_chart - 图表数据
        3. volatility_dims - 维度贡献
        4. volatility_llm_reasoning - LLM 推理过程
        5. volatility_root - 根因归类
        6. volatility_done - 完成

        支持两种数据格式：
        - 时间序列：多天数据，计算完整波动分析
        - 分类数据：单天多品类，直接展示TOP驱动
        """
        logger.info(f"[VolatilityAnalyzer] 开始分析指标: {metric_name}, 数据量: {len(data)}")

        # 检测数据格式
        data_type = self._detect_data_type(data)
        logger.info(f"[VolatilityAnalyzer] 数据格式检测: {data_type}")

        if data_type == "category":
            # 分类数据分析
            async for event in self._analyze_category_data(metric_name, data, dimension_key):
                yield event
        else:
            # 时间序列数据分析
            async for event in self._analyze_time_series(metric_name, data, dimension_key):
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
        dims = self._calc_category_drivers(data, dimension_key)

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
        dimension_key: str = "dimension"
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        时间序列数据分析：完整波动分析
        """
        # Step 1: 基础统计
        stats = self.calculate_basic_stats(data)
        anomaly_result = self.detect_anomaly_iqr([row.get('value', 0) for row in data if 'value' in row])

        stats['volatility_rate'] = anomaly_result.get('volatility_rate', 0)

        overview_data = {
            "metric_name": metric_name,
            "current_value": stats['current'],
            "prev_value": stats['prev'],
            "avg_value": stats['avg'],
            "mom_change": stats['mom'],
            "mom_change_pct": f"{stats['mom']*100:.1f}%",
            "yoy_change": stats['yoy'],
            "yoy_change_pct": f"{stats['yoy']*100:.1f}%",
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
                "value": row.get("value", 0)
            })

        yield StreamEvent(
            event=SSSEvent.STEP_COMPLETE,
            data={
                "type": "volatility_chart",
                "chart_data": chart_data,
                "chart_type": "line"
            }
        )

        # Step 3: 维度贡献度
        dims = self.calc_dimension_contribution(
            data,
            stats['current'],
            stats['prev'],
            dimension_key
        )

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
            logger.error(f"LLM 品类分析失败: {e}")
            return {
                "root_cause": "品类分布分析",
                "confidence": 0.8,
                "suggestion": "品类贡献度分析结果已展示"
            }

    def analyze(
        self,
        metric_name: str,
        data: List[Dict],
        time_range: Optional[Dict[str, str]] = None,
        dimension_key: str = "dimension"
    ) -> VolatilityResult:
        """
        同步波动分析（不生成 SSE 流）
        """
        # 基础统计
        stats = self.calculate_basic_stats(data)
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
