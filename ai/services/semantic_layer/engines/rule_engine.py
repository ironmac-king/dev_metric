"""
规则引擎

基于规则的语义解析，处理边缘场景
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

import re
from typing import Optional, List, Dict, Any

from ai.config.logging_config import get_logger
from .base import BaseEngine
from ..api import ParseResult

logger = get_logger("semantic_layer.rule_engine")


class RuleEngine(BaseEngine):
    """
    规则引擎

    处理：
    - 时间表达式解析
    - 对比类型检测
    - 模糊表述理解
    - 口语化表达
    """

    def __init__(self):
        super().__init__("rule_engine")

        # 意图关键词
        self._intent_keywords = {
            "query_trend": ["趋势", "变化", "走势", "看下", "查看", "看看"],
            "query_comparison": ["对比", "比较", "同比", "环比", "和", "比"],
            "query_ranking": ["排名", "前几", "top", "最少", "最多", "最大", "最小"],
            "drilldown": ["各", "按", "每", "各个", "品类", "渠道", "站点"],
        }

        # 时间表达式
        self._time_patterns = [
            (r"近[7七]天", "近7天"),
            (r"近[3三]个月", "近3个月"),
            (r"近30天", "近30天"),
            (r"最近一周", "最近一周"),
            (r"最近一个月", "最近一个月"),
            (r"本月", "本月"),
            (r"上月", "上月"),
            (r"本月", "本月"),
            (r"今年", "今年"),
            (r"去年", "去年"),
            (r"今日|今天", "今天"),
            (r"昨日|昨天", "昨天"),
            (r"本周", "本周"),
            (r"上周", "上周"),
            (r"一季度|1季度|Q1", "一季度"),
            (r"二季度|2季度|Q2", "二季度"),
            (r"三季度|3季度|Q3", "三季度"),
            (r"四季度|4季度|Q4", "四季度"),
            (r"(\d{4})年", None),  # 2026年
            (r"(\d{1,2})月", None),  # 3月
        ]

        # 指标关键词
        self._metric_keywords = [
            "销售额", "销售", "营收", "收入", "毛利", "毛利率",
            "访客", "访问", "点击", "转化", "转化率",
            "订单", "订单量", "销量", "销售量",
            "成本", "利润", "广告", "花费", "投放",
            "GMV", "客流", "客单价",
        ]

        # 对比类型检测
        self._comparison_keywords = {
            "同比": ["同比", "去年同期", "去年"],
            "环比": ["环比", "上周", "上月", "上个月"],
        }

    def parse(self, query: str, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        用规则解析查询

        适用于：本地模型和语义快照都无法处理的边缘场景
        """
        try:
            # 0. 短文本专用规则（<= 6 字）
            short_result = self._parse_short_text(query)
            if short_result:
                return short_result

            # 1. 检测意图
            intent = self._detect_intent(query)

            # 2. 提取时间表达式
            time_expr = self._extract_time(query)

            # 3. 检测对比类型
            comparison_types = self._detect_comparison(query)

            # 4. 提取指标
            metric_name = self._extract_metric(query)

            # 5. 提取维度
            dimensions = self._extract_dimensions(query)

            # 6. 计算置信度
            confidence = self._calculate_confidence(
                intent=intent,
                has_metric=metric_name is not None,
                has_time=time_expr is not None,
                has_comparison=len(comparison_types) > 0,
                has_dimensions=len(dimensions) > 0,
            )

            return ParseResult(
                intent=intent,
                confidence=confidence,
                entities=[],
                metric_name=metric_name,
                dimensions=dimensions,
                time_expr=time_expr,
                comparison_types=comparison_types,
                parse_method="rule",
            )

        except Exception as e:
            logger.error(f"[RuleEngine] parse error: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="rule_error",
                error=str(e)
            )

    def _parse_short_text(self, query: str) -> Optional[ParseResult]:
        """短文本专用规则（<= 6 字），处理追问类短输入"""
        if len(query) > 6:
            return None

        stripped = query.rstrip("？?")

        # "XX呢" 模式
        if stripped.endswith("呢"):
            core = stripped[:-1]
            if not core:
                return None

            # 对比词
            if core in ("环比", "同比"):
                return ParseResult(
                    intent="query_comparison",
                    comparison_types=[core],
                    confidence=0.6,
                    parse_method="short_text",
                )

            # 趋势词
            if core in ("趋势", "变化", "走势"):
                return ParseResult(
                    intent="query_trend",
                    confidence=0.6,
                    parse_method="short_text",
                )

            # 指标词
            for metric in self._metric_keywords:
                if core == metric or core in metric or metric in core:
                    return ParseResult(
                        intent="query_value",
                        metric_name=metric,
                        confidence=0.6,
                        parse_method="short_text",
                    )

            # 时间词
            for pattern, replacement in self._time_patterns:
                import re as _re
                if replacement and _re.search(pattern, core):
                    return ParseResult(
                        intent="query_value",
                        time_expr=replacement,
                        confidence=0.6,
                        parse_method="short_text",
                    )

            # 未识别的"XX呢"，返回 metric_name=core 让上层尝试解析
            return ParseResult(
                intent="query_value",
                metric_name=core,
                confidence=0.4,
                parse_method="short_text_unknown",
            )

        return None

    def _detect_intent(self, query: str) -> str:
        """检测意图"""
        query_lower = query.lower()

        # 按优先级检测
        # 1. 排名
        for kw in self._intent_keywords.get("query_ranking", []):
            if kw in query:
                return "query_ranking"

        # 2. 对比
        for kw in self._intent_keywords.get("query_comparison", []):
            if kw in query:
                return "query_comparison"

        # 3. 趋势
        for kw in self._intent_keywords.get("query_trend", []):
            if kw in query:
                return "query_trend"

        # 4. 下钻
        for kw in self._intent_keywords.get("drilldown", []):
            if kw in query:
                return "drilldown"

        # 5. 默认 query_value
        return "query_value"

    def _extract_time(self, query: str) -> Optional[str]:
        """提取时间表达式"""
        for pattern, replacement in self._time_patterns:
            if replacement:
                if re.search(pattern, query):
                    return replacement
            else:
                match = re.search(pattern, query)
                if match:
                    return match.group(0)

        # 特殊处理年月
        month_match = re.search(r"(\d{1,2})月", query)
        if month_match:
            return month_match.group(0)

        year_match = re.search(r"(\d{4})年", query)
        if year_match:
            return year_match.group(0)

        return None

    def _detect_comparison(self, query: str) -> List[str]:
        """检测对比类型"""
        comparison_types = []

        for comp_type, keywords in self._comparison_keywords.items():
            for kw in keywords:
                if kw in query:
                    if comp_type not in comparison_types:
                        comparison_types.append(comp_type)

        return comparison_types

    def _extract_metric(self, query: str) -> Optional[str]:
        """提取指标"""
        for metric in self._metric_keywords:
            if metric in query:
                return metric
        return None

    def _extract_dimensions(self, query: str) -> List[Dict[str, Any]]:
        """提取维度"""
        dimensions = []

        # 品类
        if "品类" in query or "类目" in query:
            dimensions.append({"type": "品类", "value": None})

        # 渠道
        if "渠道" in query:
            dimensions.append({"type": "渠道", "value": None})

        # 站点
        if "站点" in query or "站" in query:
            dimensions.append({"type": "站点", "value": None})

        # 店铺
        if "店铺" in query or "店" in query:
            dimensions.append({"type": "店铺", "value": None})

        # 平台
        if "平台" in query:
            dimensions.append({"type": "平台", "value": None})

        return dimensions

    def _calculate_confidence(
        self,
        intent: str,
        has_metric: bool,
        has_time: bool,
        has_comparison: bool,
        has_dimensions: bool
    ) -> float:
        """计算置信度"""
        if intent == "unknown":
            return 0.0

        confidence = 0.4  # 基础分

        if has_metric:
            confidence += 0.2

        if has_time:
            confidence += 0.1

        if has_comparison:
            confidence += 0.15

        if has_dimensions:
            confidence += 0.15

        return min(confidence, 0.7)  # 规则引擎最高0.7
