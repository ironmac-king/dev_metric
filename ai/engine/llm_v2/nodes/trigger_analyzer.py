"""
触发分析器

职责：
- 接收 sql_executor 返回的原始数据
- 执行6个触发器检查（并行）
- 符合规则 → 生成 AnalysisOutput
- 不符合规则 → analysis=null
"""
import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Dict as TypeDict
from enum import Enum

from ai.config.logging_config import get_logger
from ai.engine.llm import get_llm_engine_for_analysis
from ai.engine.llm_v2.nodes.volatility_analyzer import VolatilityAnalyzer
from ai.engine.prompt_manager import get_prompt_manager

logger = get_logger("ai.llm_v2.trigger_analyzer")


class TriggerType(Enum):
    VOLATILITY = "volatility"
    COMPARISON = "comparison"
    AD_EFFECT = "ad_effect"
    INVENTORY_RISK = "inventory_risk"
    GENERIC_QUERY = "generic_query"
    CONTEXT_FOLLOWUP = "context_followup"


class Priority(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


@dataclass
class TriggerResult:
    should_analyze: bool
    trigger_type: Optional[TriggerType] = None
    trigger_reason: str = ""
    priority: Priority = Priority.P2
    affected_dimensions: List[Dict[str, Any]] = field(default_factory=list)
    drilldown_options: List[Dict[str, Any]] = field(default_factory=list)
    # 分析数据（从分析 SQL 执行结果，用于 generate_output）
    analysis_data: Optional[Dict[str, Any]] = None


@dataclass
class AnalysisOutput:
    trigger: str
    summary: str
    kpi: Dict[str, Any]
    breakdown: List[Dict[str, Any]]
    action_items: List[Dict[str, str]]
    drilldown_options: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trigger": self.trigger,
            "summary": self.summary,
            "kpi": self.kpi,
            "breakdown": self.breakdown,
            "action_items": self.action_items,
            "drilldown_options": self.drilldown_options,
        }


class BaseTrigger(ABC):
    """触发器基类"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self._semantic_service = None  # 语义快照服务（可被外部设置或在 TriggerAnalyzer 中设置）

    @abstractmethod
    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        pass

    def _build_drilldown(self, label: str, params: Dict) -> Dict:
        return {"label": label, "action": "drilldown", "params": params}


class VolatilityTrigger(BaseTrigger):
    """指标波动触发器（业务化阈值）"""

    DEFAULT_RULES = {
        # key 为指标中文名，与 MQL.metric.name 对应
        # threshold_type: "normal"=宽松(-10%/-15%), "strict"=严格(-5%/-8%)
        # mom/yoy: 环比/同比波动阈值（负值表示下跌预警，正值表示上涨预警）
        # None 表示不监控该周期
        "销售额": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "GMV": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "订单量": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "转化率": {"mom": -5, "yoy": -8, "threshold_type": "strict"},
        "点击转化率": {"mom": -5, "yoy": -8, "threshold_type": "strict"},
        "签收率": {"mom": -3, "yoy": -5, "threshold_type": "strict"},
        "ROAS": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "广告产出比": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "广告花费": {"mom": 20, "yoy": None, "threshold_type": "normal"},
        "毛利率": {"mom": -3, "yoy": -5, "threshold_type": "strict"},
        "净利率": {"mom": -3, "yoy": -5, "threshold_type": "strict"},
        "客单价": {"mom": -5, "yoy": -8, "threshold_type": "normal"},
        "曝光量": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "点击量": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "会话量": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "ACOS": {"mom": 20, "yoy": None, "threshold_type": "normal"},
        "CPC": {"mom": 15, "yoy": None, "threshold_type": "normal"},
        "CTR": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "业绩": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "利润": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "利润额": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "成本": {"mom": 15, "yoy": None, "threshold_type": "normal"},
        "广告点击": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "广告曝光": {"mom": -15, "yoy": -20, "threshold_type": "normal"},
        "智能云存储销售额": {"mom": -10, "yoy": -15, "threshold_type": "normal"},
        "智能云存储毛利": {"mom": -3, "yoy": -5, "threshold_type": "strict"},
        "智能云存储毛利率": {"mom": -3, "yoy": -5, "threshold_type": "strict"},
    }

    CAMPAIGN_BUFFERS = {
        "双11": 1.5, "黑五": 1.3, "圣诞": 1.2, "618": 1.4,
    }

    def _get_threshold(self, metric_code: str) -> Dict:
        """获取指标阈值配置（先查库，无则用默认）"""
        # 先尝试从数据库加载
        if self.db_pool:
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host="192.168.1.225",
                    port=5432,
                    user="postgres",
                    password="admin123",
                    database="dev_metric",
                    connect_timeout=5
                )
                cur = conn.cursor()
                cur.execute("""
                    SELECT condition FROM analysis_trigger_configs
                    WHERE trigger_type = 'volatility'
                    AND (metric_code = %s OR metric_code IS NULL OR metric_code = '')
                    AND enabled = true
                    ORDER BY priority DESC
                    LIMIT 1
                """, (metric_code,))
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    return json.loads(row[0])
            except Exception as e:
                logger.warning(f"[VolatilityTrigger] 加载阈值配置失败: {e}")

        return self.DEFAULT_RULES.get(metric_code, {"mom": -10, "yoy": -15})

    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        metric_code = self._get_metric_code(mql)
        if not metric_code:
            return TriggerResult(should_analyze=False)

        # 获取阈值配置
        threshold = self._get_threshold(metric_code)
        buffer = self._get_campaign_buffer()

        # 提取波动数据（优先从 kpi 取，其次从 result 直接取）
        kpi = result.get("kpi", {}) or {}
        mom = kpi.get("mom", result.get("mom_change", 0))
        yoy = kpi.get("yoy", result.get("yoy_change", 0))
        current = kpi.get("current", result.get("current_value", result.get("value", 0)))

        # 如果mom/yoy为None或0，尝试从数据计算
        if (mom is None or mom == 0) and "data" in result:
            mom = self._calc_mom_from_data(result.get("data", []))
        if (yoy is None or yoy == 0) and "data" in result:
            yoy = self._calc_yoy_from_data(result.get("data", []))

        # 应用缓冲后的阈值
        mom_threshold = threshold["mom"] * buffer
        yoy_threshold = (threshold.get("yoy", -999) or -999) * buffer

        # 检查是否触发
        triggered = mom <= mom_threshold or yoy <= yoy_threshold

        # 特殊检查：广告花费涨 + 销售额跌（效果变差）
        if metric_code == "广告花费" and result.get("gmv_change", 0) < 0:
            triggered = True

        if triggered:
            # 计算受影响维度
            affected = await self._calc_affected_dimensions(result, metric_code)
            priority = self._calc_priority(mom, yoy)

            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.VOLATILITY,
                trigger_reason=f"{metric_code}环比下降{abs(mom) if mom < 0 else mom}%",
                priority=priority,
                affected_dimensions=affected,
                drilldown_options=self._build_drilldowns(affected)
            )

        return TriggerResult(should_analyze=False)

    def _get_metric_code(self, mql) -> str:
        """从 MQL 对象获取指标名称（优先中文名，其次系统Code）"""
        if hasattr(mql, 'metric') and mql.metric:
            # 优先使用指标中文名（用户配置的直观名称）
            if hasattr(mql.metric, 'name') and mql.metric.name:
                return mql.metric.name
            # 其次使用系统指标Code（如 MKI-02-0009）
            if hasattr(mql.metric, 'code') and mql.metric.code:
                return mql.metric.code
            if hasattr(mql.metric, 'metric_code') and mql.metric.metric_code:
                return mql.metric.metric_code
        if hasattr(mql, 'name') and mql.name:
            return mql.name
        if hasattr(mql, 'code'):
            return mql.code
        if hasattr(mql, 'metric_code'):
            return mql.metric_code
        return ""

    def _get_campaign_buffer(self) -> float:
        """检查是否大促期间，返回缓冲倍数"""
        # TODO: 实现大促期间检测
        return 1.0

    def _calc_mom_from_data(self, data: List[Dict]) -> float:
        """从数据计算环比"""
        if len(data) < 2:
            return 0
        # 优先使用 mom_val 列（SQL 窗口函数计算好的）
        if data and "mom_val" in data[0]:
            vals_with_mom = [(row.get('MONTHS', ''), row.get('mom_val')) for row in data]
            vals_with_mom = [(m, v) for m, v in vals_with_mom if v is not None and v != 0]
            if vals_with_mom:
                return vals_with_mom[-1][1]
        # 找不到则尝试用原始值列
        first_row = data[0] if data else {}
        value_key = None
        for key in first_row.keys():
            if 'raw' in key.lower() or key in ['销售额', 'ORDERED_PRODUCTSALES']:
                value_key = key
                break
        if not value_key:
            return 0
        values = [(row.get('MONTHS', ''), row.get(value_key, 0)) for row in data]
        values.sort(key=lambda x: x[0] if x[0] else '')
        if len(values) < 2:
            return 0
        current = values[-1][1] if values else 0
        prev = values[-2][1] if len(values) > 1 else 0
        if prev == 0:
            return 0
        return (current - prev) / prev * 100

    def _calc_yoy_from_data(self, data: List[Dict]) -> float:
        """从数据计算同比（需要12个月前的数据）"""
        if len(data) < 2:
            return 0
        # 尝试找 mom_val 或 yoy_val 列（SQL 窗口函数计算的）
        for row in data:
            mom_val = row.get("mom_val")
            yoy_val = row.get("yoy_val")
            if yoy_val is not None and yoy_val != 0:
                return yoy_val
            if mom_val is not None and mom_val != 0:
                return mom_val
        # 如果窗口函数没算出值，尝试用原始值计算
        # 找销售额_raw 或类似列
        first_row = data[0] if data else {}
        value_key = None
        for key in first_row.keys():
            if 'raw' in key.lower() or key in ['销售额', 'ORDERED_PRODUCTSALES', 'value']:
                value_key = key
                break
        if not value_key:
            return 0
        values = [(row.get('MONTHS', ''), row.get(value_key, 0)) for row in data]
        # 按月份排序
        values.sort(key=lambda x: x[0] if x[0] else '')
        if len(values) < 2:
            return 0
        # 尝试找当前期间和上一个同比期间
        current_val = values[-1][1] if values else 0
        # 找去年同月
        for row in values:
            month_str = row[0]
            if month_str and len(month_str) >= 7:
                # 检查是否是12个月前
                try:
                    from datetime import datetime
                    dt = datetime.strptime(month_str, '%Y-%m')
                    # 找12个月前的数据
                    prev_dt = dt.replace(year=dt.year - 1)
                    prev_str = prev_dt.strftime('%Y-%m')
                    for prev_row in values:
                        if prev_row[0] == prev_str and prev_row[1] != 0:
                            return (current_val - prev_row[1]) / prev_row[1] * 100
                except Exception:
                    pass
        return 0

    async def _calc_affected_dimensions(self, result: Dict, metric_code: str) -> List[Dict]:
        """计算各维度对整体的影响

        优先使用归因数据（attribution_data），回退到 IQR 异常检测
        """
        # 1. 优先使用归因数据
        attribution_data = result.get("attribution_data", [])
        if attribution_data:
            logger.info(f"[VolatilityTrigger] 使用归因数据构建 affected_dimensions，共 {len(attribution_data)} 项")
            return attribution_data

        # 2. 回退到 IQR 异常检测
        data = result.get("data", [])
        if not data:
            return []

        try:
            analyzer = VolatilityAnalyzer()
            first_row = data[0] if data else {}
            dimension_key = None
            for key in ['dimension', 'country', 'platform', 'site', 'ad_channel']:
                if key in first_row:
                    dimension_key = key
                    break

            if dimension_key:
                dims = analyzer.calc_dimension_contribution(data, 0, 0, dimension_key)
                affected = []
                for dim in dims.get('negative', [])[:3]:
                    affected.append({
                        "dimension": dim.get('name', ''),
                        "raw_value": dim.get('name', ''),
                        "value": f"{dim.get('change', 0):.1f}",
                        "impact": f"拖累{abs(dim.get('contribution', 0)):.1f}%",
                        "priority": "P0",
                        "reason": "需关注",
                        "dimension_type": dimension_key
                    })
                return affected
        except Exception as e:
            logger.warning(f"[VolatilityTrigger] IQR计算失败: {e}")

        return []

    def _calc_priority(self, mom: float, yoy: float) -> Priority:
        """确定优先级"""
        if abs(mom) >= 20 or abs(yoy) >= 30:
            return Priority.P0
        elif abs(mom) >= 10 or abs(yoy) >= 15:
            return Priority.P1
        return Priority.P2

    def _build_drilldowns(self, affected: List[Dict]) -> List[Dict]:
        options = []
        for dim in affected[:2]:
            raw_val = dim.get('raw_value', '')
            options.append(self._build_drilldown(
                f"🏪 {dim.get('dimension', '')}流量分析",
                {"dimension": "traffic", "site": raw_val}
            ))
            options.append(self._build_drilldown(
                f"📢 {dim.get('dimension', '')}广告效果",
                {"metric": "ad_roas", "site": raw_val}
            ))
        if not options:
            # ========== 优先用语义快照的 recommend_actions ==========
            if self._semantic_service:
                semantic_actions = self._semantic_service.recommend_actions("volatility", limit=4) or []
                if semantic_actions:
                    logger.info(f"[_build_drilldowns] 从语义快照获取 actions: {semantic_actions}")
                    return semantic_actions
            # ======================================================
            options = [
                self._build_drilldown("🏪 站点健康度", {"check": "site_health"}),
                self._build_drilldown("📢 广告效果", {"check": "ad_effect"}),
            ]
        else:
            # 有动态 drilldowns 时，追加语义快照的 actions
            if self._semantic_service:
                semantic_actions = self._semantic_service.recommend_actions("volatility", limit=4) or []
                if semantic_actions:
                    logger.info(f"[_build_drilldowns] 追加语义快照 actions: {semantic_actions}")
                    options.extend(semantic_actions)
        return options[:4]


class GenericQueryTrigger(BaseTrigger):
    """模糊泛问触发器"""

    GENERIC_PATTERNS = ["怎么样", "怎么", "如何", "今天", "最近", "情况", "生意"]
    CORE_METRICS = ["gmv", "orders"]

    # 四类分析词映射
    DRILLDOWN_CATEGORY_PATTERNS = {
        "sales": ["销售经营", "销售分析", "销售概览"],
        "ad": ["广告投放", "广告效果", "广告分析", "投放分析"],
        "inventory": ["库存供应", "库存分析", "供应链", "补货分析"],
        "cost": ["成本毛利", "成本分析", "毛利分析", "利润分析"],
    }

    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        question = mql.original_question if hasattr(mql, 'original_question') and mql.original_question else (mql.resolved_question or '' if hasattr(mql, 'resolved_question') else '')

        metric_code = ""
        if hasattr(mql, 'metric') and mql.metric:
            metric_code = getattr(mql.metric, 'code', '') or getattr(mql.metric, 'metric_code', '')

        # 匹配泛问模式
        is_generic = any(p in question for p in self.GENERIC_PATTERNS)
        is_core = metric_code.lower() in self.CORE_METRICS if metric_code else False

        # 检测四类分析词
        drilldown_type = None

        # 优先从 state（graph.py 传递的 context_cache）获取 drilldown_type
        if state and isinstance(state, dict):
            drilldown_type = state.get("drilldown_type")
            if drilldown_type:
                logger.info(f"[GenericQueryTrigger] 从 state 获取 drilldown_type: {drilldown_type}")

        # 其次检测 __DRILLDOWN__:xxx__ 格式
        if not drilldown_type and "__DRILLDOWN__:" in question:
            try:
                # 解析格式：__DRILLDOWN__:sales__
                parts = question.replace("__DRILLDOWN__:", "").replace("__", "").strip()
                drilldown_type = parts
                logger.info(f"[GenericQueryTrigger] 识别到下钻格式: {drilldown_type}")
            except Exception as e:
                logger.warning(f"[GenericQueryTrigger] 解析下钻格式失败: {e}")

        # ========== 使用语义快照服务检测四类分析词 ==========
        if not drilldown_type and self._semantic_service:
            try:
                # 从 semantic service 获取 drilldown categories
                scene_categories = self._semantic_service.get_scene_drilldown_categories("generic_query") or {}
                # 直接匹配 question 与 category sub-items（如 "sales-deep-dive" ∈ ["sales-deep-dive"]）
                for cat, sub_cats in scene_categories.items():
                    if any(str(sc) in question or question in str(sc) for sc in sub_cats):
                        drilldown_type = cat
                        logger.info(f"[GenericQueryTrigger] 快照 category '{cat}' sub-item 匹配 question '{question}'")
                        break
                # 如果没匹配上，尝试通过 keywords 匹配
                if not drilldown_type:
                    scene_keywords = self._semantic_service.get_scene_keywords("generic_query") or []
                    for kw in scene_keywords:
                        if kw and kw in question:
                            # 匹配到关键词，查找对应的 drilldown_type
                            for cat, sub_cats in scene_categories.items():
                                if any(kw in str(sc) or str(sc) in kw for sc in sub_cats):
                                    drilldown_type = cat
                                    logger.info(f"[GenericQueryTrigger] 快照关键词 '{kw}' 匹配到 drilldown_type={drilldown_type}")
                                    break
                            if drilldown_type:
                                break
            except Exception as e:
                logger.warning(f"[GenericQueryTrigger] 语义快照服务关键词匹配失败: {e}")
        # =====================================================

        # Fallback：检测四类分析词（文字匹配）
        if not drilldown_type:
            for check_type, patterns in self.DRILLDOWN_CATEGORY_PATTERNS.items():
                if any(p in question for p in patterns):
                    drilldown_type = check_type
                    break

        if drilldown_type:
            # ========== 优先用 semantic service 的 resolve_action ==========
            drilldown_opts = []
            if self._semantic_service:
                try:
                    resolved = self._semantic_service.resolve_action(
                        check=drilldown_type,
                        question=question,
                        scene_type="generic_query",
                        target_scene_type="drilldown"
                    )
                    if resolved:
                        drilldown_opts = [self._build_drilldown(
                            resolved.get("label", ""),
                            resolved.get("params", {})
                        )]
                except Exception as e:
                    logger.warning(f"[GenericQueryTrigger] 语义快照 resolve_action 失败: {e}")
            # ============================================================

            # Fallback：使用硬编码的 category_labels
            if not drilldown_opts:
                category_labels = {
                    "sales": "📊 销售经营分析",
                    "ad": "📢 广告投放分析",
                    "inventory": "📦 库存供应链分析",
                    "cost": "💰 成本毛利分析",
                }
                # 如果是 __DRILLDOWN__ 格式，不返回 drilldown_options（避免循环）
                is_drilldown_signal = "__DRILLDOWN__:" in question
                drilldown_opts = [] if is_drilldown_signal else [
                    self._build_drilldown(category_labels.get(drilldown_type, drilldown_type), {"check": drilldown_type}),
                ]
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.GENERIC_QUERY,
                trigger_reason=f"触发{category_labels.get(drilldown_type, drilldown_type) if not drilldown_opts else drilldown_opts[0]['label']}",
                priority=Priority.P1,
                affected_dimensions=[],
                drilldown_options=drilldown_opts
            )

        if is_generic or is_core:
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.GENERIC_QUERY,
                trigger_reason="模糊泛问，触发整体健康度分析",
                priority=Priority.P2,
                affected_dimensions=[],
                drilldown_options=[
                    self._build_drilldown("📊 看销售", {"check": "sales"}),
                    self._build_drilldown("📢 看广告", {"check": "ad"}),
                    self._build_drilldown("📦 看库存", {"check": "inventory"}),
                    self._build_drilldown("💰 看利润", {"check": "profit"}),
                ]
            )

        return TriggerResult(should_analyze=False)


class AdEffectTrigger(BaseTrigger):
    """广告效果触发器"""

    AD_PATTERNS = ["广告", "ROAS", "ROI", "花费", "投产", "效果", "推广"]

    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        question = mql.original_question if hasattr(mql, 'original_question') and mql.original_question else (mql.resolved_question or '' if hasattr(mql, 'resolved_question') else '')

        if any(p in question for p in self.AD_PATTERNS):
            # 优先用 semantic service 的 recommend_actions
            drilldown_opts = []
            if self._semantic_service:
                try:
                    semantic_actions = self._semantic_service.recommend_actions("ad_effect", limit=4) or []
                    if semantic_actions:
                        drilldown_opts = semantic_actions
                except Exception as e:
                    logger.warning(f"[AdEffectTrigger] 语义快照 recommend_actions 失败: {e}")
            if not drilldown_opts:
                drilldown_opts = [
                    self._build_drilldown("📢 按渠道对比", {"dimension": "ad_channel"}),
                    self._build_drilldown("📉 低效站点", {"dimension": "low_roas_site"}),
                    self._build_drilldown("💰 花费明细", {"metric": "ad_spend"}),
                    self._build_drilldown("📊 ROI趋势", {"metric": "roi_trend"}),
                ]
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.AD_EFFECT,
                trigger_reason="广告效果分析",
                priority=Priority.P1,
                affected_dimensions=[],
                drilldown_options=drilldown_opts
            )

        return TriggerResult(should_analyze=False)


class InventoryRiskTrigger(BaseTrigger):
    """库存风险触发器"""

    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        # 检查是否有库存相关数据
        data = result.get("data", [])
        if not data:
            return TriggerResult(should_analyze=False)

        # 检查是否有可售天数字段
        inventory_days = None
        for row in data:
            if 'inventory_days' in row:
                inventory_days = row.get('inventory_days')
                break
            if 'days' in row:
                inventory_days = row.get('days')
                break

        if inventory_days is not None:
            if inventory_days < 3:
                priority = Priority.P0
            elif inventory_days < 7:
                priority = Priority.P1
            else:
                priority = Priority.P2

            # 优先用 semantic service 的 recommend_actions
            drilldown_opts = []
            if self._semantic_service:
                try:
                    semantic_actions = self._semantic_service.recommend_actions("inventory_risk", limit=4) or []
                    if semantic_actions:
                        drilldown_opts = semantic_actions
                except Exception as e:
                    logger.warning(f"[InventoryRiskTrigger] 语义快照 recommend_actions 失败: {e}")
            if not drilldown_opts:
                drilldown_opts = [
                    self._build_drilldown("📦 库存明细", {"check": "inventory_detail"}),
                    self._build_drilldown("⚠️ 断货预警", {"check": "stockout_risk"}),
                ]
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.INVENTORY_RISK,
                trigger_reason=f"库存可售天数{inventory_days}天",
                priority=priority,
                affected_dimensions=[],
                drilldown_options=drilldown_opts
            )

        return TriggerResult(should_analyze=False)


class ContextTrigger(BaseTrigger):
    """连续追问触发器"""

    FOLLOWUP_PATTERNS = ["为什么", "原因", "为啥", "哪个", "什么导致"]

    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        if not state:
            return TriggerResult(should_analyze=False)

        question = mql.original_question if hasattr(mql, 'original_question') and mql.original_question else (mql.resolved_question or '' if hasattr(mql, 'resolved_question') else '')

        last_query_type = state.get("last_query_type", "")

        is_followup = any(p in question for p in self.FOLLOWUP_PATTERNS)
        was_metric = last_query_type == "metric"

        if is_followup and was_metric:
            # 优先用 semantic service 的 recommend_actions
            drilldown_opts = []
            if self._semantic_service:
                try:
                    semantic_actions = self._semantic_service.recommend_actions("context_followup", limit=4) or []
                    if semantic_actions:
                        drilldown_opts = semantic_actions
                except Exception as e:
                    logger.warning(f"[ContextTrigger] 语义快照 recommend_actions 失败: {e}")
            if not drilldown_opts:
                drilldown_opts = [
                    self._build_drilldown("🏪 按站点归因", {"drilldown": "site"}),
                    self._build_drilldown("📊 按因素归因", {"drilldown": "factor"}),
                    self._build_drilldown("⏰ 时间维度", {"drilldown": "time"}),
                ]
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.CONTEXT_FOLLOWUP,
                trigger_reason="连续追问，进入深度归因",
                priority=Priority.P1,
                affected_dimensions=[],
                drilldown_options=drilldown_opts
            )

        return TriggerResult(should_analyze=False)


class ComparisonTrigger(BaseTrigger):
    """多维度对比触发器"""

    COMPARISON_PATTERNS = ["哪个", "对比", "比较", "平台表现", "站点", "国家"]

    async def check(self, mql, result: Dict, state=None) -> TriggerResult:
        question = mql.original_question if hasattr(mql, 'original_question') and mql.original_question else (mql.resolved_question or '' if hasattr(mql, 'resolved_question') else '')

        # 检查是否有多维度数据
        data = result.get("data", [])
        has_multi_dims = False
        if len(data) > 1:
            first_row = data[0] if data else {}
            for key in ['country', 'platform', 'site', 'dimension']:
                if key in first_row:
                    has_multi_dims = True
                    break

        is_comparison = any(p in question for p in self.COMPARISON_PATTERNS)

        # ========== 优先用 semantic service 的 keywords 判断 ==========
        should_trigger = is_comparison
        if self._semantic_service and not should_trigger:
            try:
                scene_keywords = self._semantic_service.get_scene_keywords("comparison") or []
                if any(kw and kw in question for kw in scene_keywords):
                    should_trigger = True
                    logger.info(f"[ComparisonTrigger] 语义快照 keywords 触发: {scene_keywords}")
            except Exception as e:
                logger.warning(f"[ComparisonTrigger] 语义快照 keywords 查询失败: {e}")
        # ============================================================

        if should_trigger:
            # 优先用 semantic service 的 recommend_actions
            drilldown_opts = []
            if self._semantic_service:
                try:
                    semantic_actions = self._semantic_service.recommend_actions("comparison", limit=4) or []
                    if semantic_actions:
                        drilldown_opts = semantic_actions
                        logger.info(f"[ComparisonTrigger] 使用语义快照 actions: {drilldown_opts}")
                except Exception as e:
                    logger.warning(f"[ComparisonTrigger] 语义快照 recommend_actions 失败: {e}")
            # Fallback 到硬编码
            if not drilldown_opts:
                drilldown_opts = [
                    self._build_drilldown("📊 各维度排序", {"check": "dimension_rank"}),
                    self._build_drilldown("🔍 Top/Bottom", {"check": "top_bottom"}),
                ]
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.COMPARISON,
                trigger_reason="多维度对比分析",
                priority=Priority.P2,
                affected_dimensions=[],
                drilldown_options=drilldown_opts
            )

        return TriggerResult(should_analyze=False)


class TriggerAnalyzer:
    """触发分析器 - 并行执行所有触发器，支持灰度/开关"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.triggers = [
            VolatilityTrigger(db_pool),
            ComparisonTrigger(db_pool),
            AdEffectTrigger(db_pool),
            InventoryRiskTrigger(db_pool),
            GenericQueryTrigger(db_pool),
            ContextTrigger(db_pool),
        ]
        self.template_loader = TemplateLoader(db_pool)
        self.switch_checker = TriggerSwitchChecker(db_pool)
        self._semantic_service = None
        self._sql_generator = None  # 延迟初始化

    def _get_sql_generator(self):
        """延迟加载 SQLGenerator"""
        if self._sql_generator is None:
            from .sql_generator import SQLGeneratorNode
            self._sql_generator = SQLGeneratorNode()
        return self._sql_generator

    def _get_semantic_service(self):
        """延迟加载语义快照服务（单例，从内存快照读取，不发 HTTP）"""
        if self._semantic_service is None:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            self._semantic_service = get_semantic_snapshot_service()
        return self._semantic_service

    def _merge_drilldown_options(self, primary: List[Dict], semantic: List[Dict]) -> List[Dict]:
        """合并主要 drilldown_options 和语义快照返回的 options，去重"""
        seen = set()
        result = []
        for opt in primary:
            key = (opt.get("label", ""), opt.get("action", ""), str(opt.get("params", "")))
            if key not in seen:
                seen.add(key)
                result.append(opt)
        for opt in semantic:
            key = (opt.get("label", ""), opt.get("action", ""), str(opt.get("params", "")))
            if key not in seen:
                seen.add(key)
                result.append(opt)
        return result

    async def check_triggers(self, mql, result: Dict, state=None) -> TriggerResult:
        """并行检查所有触发器，返回第一个命中的结果"""
        # 1. 检查全局开关
        try:
            global_status = await self.switch_checker.get_switch_status('all')
            if global_status == 'disabled':
                logger.info("[TriggerAnalyzer] 全局开关已关闭")
                return TriggerResult(should_analyze=False)
        except Exception as e:
            logger.warning(f"[TriggerAnalyzer] 检查全局开关失败: {e}")

        # 2. 获取已启用的触发器（从数据库开关）- 并发执行避免串行等待
        async def get_trigger_status(t) -> tuple:
            try:
                trigger_type = t.trigger_type.value if hasattr(t, 'trigger_type') else type(t).__name__
                status = await self.switch_checker.get_switch_status(trigger_type)
                gray_ratio = None
                if status == 'gray':
                    gray_ratio = await self.switch_checker.get_gray_ratio(trigger_type)
                return (t, trigger_type, status, gray_ratio)
            except Exception as e:
                logger.warning(f"[TriggerAnalyzer] 检查触发器{t}开关失败: {e}")
                return (t, type(t).__name__, 'enabled', None)

        results = await asyncio.gather(*[get_trigger_status(t) for t in self.triggers], return_exceptions=True)
        enabled_triggers = []
        for r in results:
            if isinstance(r, Exception):
                continue
            t, trigger_type, status, gray_ratio = r
            if status == 'disabled':
                continue
            if status == 'gray' and gray_ratio is not None:
                if not self._in_gray_group(gray_ratio):
                    continue
            enabled_triggers.append(t)

        # 全局开关检查（也已并发，上面6个足够代表）
        # (如果'all'的全局开关为disabled，会在第一个trigger检查时提前返回)

        # 3. 根据 metric_capability 生成并执行分析 SQL（语义快照驱动）
        cap = {}
        mql_slots = {}
        logger.info(f"[TriggerAnalyzer] check_triggers 收到 state 类型: {type(state)}, state={state}")
        if isinstance(state, dict):
            cap = state.get("metric_capability", {}) or {}
            mql_slots = state.get("mql_slots", {}) or {}
            logger.info(f"[TriggerAnalyzer] 从 state 获取 metric_capability: {cap}")

        analysis_result = await self._generate_and_execute_analysis_sql(mql, cap, mql_slots, result)

        # 4. 根据 metric_capability 过滤触发器
        enabled_triggers = self._filter_triggers_by_capability(enabled_triggers, cap)

        # 5. 数据不足时按配置生成精准提示
        # 注意：分析 SQL 永远返回 1 行汇总数据（current/mom/yoy），不能按行数判断
        # 应该检查 KPI 是否有有效值
        kpi = analysis_result.get("kpi", {})
        has_kpi_data = kpi.get("current") is not None or kpi.get("mom") is not None or kpi.get("yoy") is not None
        # 维度探索：多行数据 + group by 维度，即使 KPI 为空也不 early return，继续走触发器流程
        rows = analysis_result.get("data", [])
        is_dim_exploration = bool(rows and len(rows) > 1 and mql and mql.dimensions and any(dim.value is None and dim.column for dim in mql.dimensions))
        if not has_kpi_data and not is_dim_exploration:
            insufficient_msg = self._generate_data_insufficient_msg(cap)
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.GENERIC_QUERY,
                trigger_reason=insufficient_msg,
                priority=Priority.P2,
                affected_dimensions=[],
                drilldown_options=[],
                analysis_data=analysis_result
            )

        # 5. 如果所有触发器都被 capability 禁用，默认保留 GenericQueryTrigger
        if not enabled_triggers:
            for t in self.triggers:
                if isinstance(t, GenericQueryTrigger):
                    enabled_triggers = [t]
                    break

        # 6. 并行执行启用的触发器（使用分析 SQL 结果）
        if not enabled_triggers:
            return TriggerResult(should_analyze=False, analysis_data=analysis_result)

        # 优先用分析 SQL 结果，其次用渲染 SQL 结果
        trigger_result_data = analysis_result if analysis_result.get("data") else result
        tasks = [t.check(mql, trigger_result_data, state) for t in enabled_triggers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, TriggerResult) and r.should_analyze:
                logger.info(f"[TriggerAnalyzer] 触发器命中: {r.trigger_type}")
                r.analysis_data = analysis_result  # 携带分析数据
                return r

        return TriggerResult(should_analyze=False, analysis_data=analysis_result)

    def _in_gray_group(self, gray_ratio: int) -> bool:
        """灰度逻辑：基于时间戳哈希"""
        import hashlib
        ts = str(time.time())
        session_hash = hashlib.md5(ts.encode()).hexdigest()
        return int(session_hash[:8], 16) % 100 < gray_ratio

    def _filter_triggers_by_capability(self, triggers: List, cap: Dict) -> List:
        """根据语义快照 metric_capability 过滤触发器"""
        if not cap:
            return triggers  # 无 capability 时不过滤

        filtered = []
        for t in triggers:
            t_name = type(t).__name__
            if t_name == "VolatilityTrigger" and (cap.get("supports_trend") or cap.get("supports_mom") or cap.get("supports_comparison")):
                filtered.append(t)
            elif t_name == "ComparisonTrigger" and (cap.get("supports_comparison") or cap.get("supports_yoy") or cap.get("supports_mom")):
                filtered.append(t)
            elif t_name == "AdEffectTrigger" and cap.get("supports_ad_effect"):
                filtered.append(t)
            elif t_name == "InventoryRiskTrigger" and cap.get("supports_inventory_risk"):
                filtered.append(t)
            elif t_name == "GenericQueryTrigger":
                filtered.append(t)  # GenericQueryTrigger 始终保留（兜底）
            elif t_name == "ContextTrigger" and cap.get("supports_context_followup"):
                filtered.append(t)
        logger.info(f"[_filter_triggers_by_capability] cap={cap.get('supports_trend')}/{cap.get('supports_mom')}/{cap.get('supports_comparison')}, enabled_triggers={[type(t).__name__ for t in filtered]}")
        return filtered

    def _generate_data_insufficient_msg(self, cap: Dict) -> str:
        """按能力配置生成数据不足的精准提示"""
        tips = []
        if cap.get("supports_trend"):
            tips.append("趋势分析")
        if cap.get("supports_mom"):
            tips.append("环比分析")
        if cap.get("supports_yoy"):
            tips.append("同比分析")
        if not tips:
            return "当前数据量不足，无法生成分析"
        return f"数据点不足，无法进行{'、'.join(tips)}，请扩大时间范围或检查数据筛选条件"

    async def _generate_and_execute_analysis_sql(self, mql, metric_capability: Dict, mql_slots: Dict, result: Dict = None) -> Dict[str, Any]:
        """
        根据 metric_capability 生成并执行分析 SQL

        分析路 SQL：根据 metric_capability 计算 mom/yoy/trend 等
        MQL 槽位：date/dim/filters

        当 supports_attribution=1 时，额外执行维度归因 SQL

        如果 result 参数已经包含多行维度数据（如渲染SQL返回的13行FSITE数据），
        则直接使用该数据计算KPI，而不是生成新的分析SQL

        Returns:
            {"data": [...], "total": int, "kpi": {...}, "attribution_data": [...]}
        """
        logger.info(f"[_generate_and_execute_analysis_sql] START, mql.time={mql.time if mql else None}")
        cap = metric_capability or {}

        # 检查是否有需要分析能力
        if not any([cap.get("supports_yoy"), cap.get("supports_mom"),
                    cap.get("supports_trend"), cap.get("supports_ranking")]):
            logger.info("[TriggerAnalyzer] 无分析能力，不生成分析 SQL")
            return {"data": [], "total": 0, "kpi": {}}

        logger.info(f"[_generate_and_execute_analysis_sql] supports_attribution={cap.get('supports_attribution')}, drilldown_targets={cap.get('drilldown_targets')}")

        try:
            # ========== 检查 result 是否已经包含多行维度数据 ==========
            # 如果 result 已经有足够的多行数据（如渲染SQL返回的13行FSITE数据），
            # 直接使用该数据计算KPI，避免重复查询
            if result and isinstance(result, dict):
                existing_data = result.get("data", [])
                # 使用 mql.dimensions 判断是否是维度探索，而不是 hardcoded 列表
                if self._is_dimension_exploration(mql, existing_data):
                    logger.info(f"[_generate_and_execute_analysis_sql] 维度探索，直接返回原始 {len(existing_data)} 行数据，不累加")
                    # 维度探索：始终执行 attribution SQL 获取 mom/yoy
                    attribution_result = None
                    try:
                        attribution_result = await self._execute_dimension_attribution(mql, cap, {})
                    except Exception as e:
                        logger.warning(f"[_generate_and_execute_analysis_sql] 维度探索 attribution 执行失败: {e}")

                    return {
                        "data": existing_data,
                        "total": len(existing_data),
                        "kpi": {},  # 维度探索不需要汇总 KPI
                        "is_dimension_exploration": True,  # 标记为维度探索
                        "attribution_data": attribution_result
                    }
            # =========================================================

            # 生成分析 SQL
            sql_gen = self._get_sql_generator()
            analysis_sql = sql_gen.generate_analysis_sql(mql, cap)
            logger.info(f"[TriggerAnalyzer] 生成分析 SQL: {analysis_sql[:200]}...")

            # 执行 SQL
            result_data = await self._execute_analysis_sql(analysis_sql)
            logger.info(f"[TriggerAnalyzer] 分析 SQL 执行成功，返回 {len(result_data.get('data', []))} 条数据")

            # 提取 KPI
            kpi = self._extract_analysis_kpi(result_data.get("data", []), mql)
            result_data["kpi"] = kpi

            # 如果 supports_attribution=1，执行维度归因 SQL
            if cap.get("supports_attribution") == 1:
                attribution_result = await self._execute_dimension_attribution(mql, cap, kpi)
                if attribution_result:
                    result_data["attribution_data"] = attribution_result
                    logger.info(f"[TriggerAnalyzer] 维度归因 SQL 执行成功，返回 {len(attribution_result)} 条数据")

            return result_data
        except Exception as e:
            logger.warning(f"[TriggerAnalyzer] 生成/执行分析 SQL 失败: {e}")
            import traceback
            logger.warning(f"[TriggerAnalyzer] 堆栈: {traceback.format_exc()}")
            return {"data": [], "total": 0, "kpi": {}}

    async def _execute_dimension_attribution(self, mql, cap: Dict, kpi: Dict) -> Optional[List[Dict]]:
        """
        执行维度归因 SQL

        1. 选择优先级最高的有效维度
        2. 检查基数（≤1000）
        3. 生成并执行归因 SQL
        4. 构建 breakdown

        Returns:
            breakdown 列表，如果失败返回 None
        """
        logger.info(f"[_execute_dimension_attribution] START, drilldown_targets={cap.get('drilldown_targets')}")
        try:
            # 1. 选择维度
            drilldown_targets = cap.get("drilldown_targets", "")
            breakdown_dim = await self._select_top_dimension(drilldown_targets, mql)

            # 如果 drilldown_targets 为空但 mql.dimensions 有 group by 维度，直接使用
            if not breakdown_dim and mql and mql.dimensions:
                for dim in mql.dimensions:
                    if dim.value is None and dim.column:
                        breakdown_dim = dim.column
                        logger.info(f"[_execute_dimension_attribution] 使用 mql.dimensions 中的维度: {breakdown_dim}")
                        break

            if not breakdown_dim:
                logger.info("[_execute_dimension_attribution] 无有效维度或所有维度基数>1000")
                return None

            # 2. 检查基数
            if not await self._check_dimension_cardinality(breakdown_dim, mql):
                logger.info(f"[_execute_dimension_attribution] 维度 {breakdown_dim} 基数超限，跳过")
                return None

            # 3. 生成归因 SQL
            logger.info(f"[_execute_dimension_attribution] 生成归因SQL，breakdown_dim={breakdown_dim}")
            sql_gen = self._get_sql_generator()
            attribution_sql = sql_gen.generate_dimension_attribution_sql(mql, cap, breakdown_dim)
            if not attribution_sql:
                logger.warning("[_execute_dimension_attribution] 生成归因 SQL 失败")
                return None

            # 4. 执行 SQL
            logger.info(f"[_execute_dimension_attribution] 执行归因 SQL: {attribution_sql[:500]}")
            attribution_data = await self._execute_analysis_sql(attribution_sql)
            rows = attribution_data.get("data", [])
            logger.info(f"[_execute_dimension_attribution] 归因 SQL 返回: {len(rows)} 行, data={rows[:3] if rows else 'empty'}")
            if not rows:
                return None

            # 5. 构建 breakdown
            breakdown = self._build_breakdown_from_attribution(rows, kpi, breakdown_dim)
            return breakdown

        except Exception as e:
            logger.warning(f"[_execute_dimension_attribution] 维度归因失败: {e}")
            import traceback
            logger.warning(f"[_execute_dimension_attribution] 堆栈: {traceback.format_exc()}")
            return None

    # 维度归因辅助方法
    DIMENSION_LABELS = {
        "FSITE": "站点",
        "GROUP_1": "品类",
        "GROUP_2": "二级品类",
        "GROUP_3": "三级品类",
        "GROUP_4": "四级品类",
        "FCHANNEL": "渠道",
        "FCOUNTRY": "国家",
        "FREGION": "区域",
        "FBRANDS": "品牌",
        "FPRODUCTLINE": "产品线",
        "FADTYPE": "广告类型",
        "PLATFORM": "平台",
        "SKU": "商品",
        "ASIN": "ASIN",
    }

    async def _select_top_dimension(self, drilldown_targets: str, mql) -> Optional[str]:
        """
        从 drilldown_targets 中选择优先级最高且基数≤1000的维度

        优先级规则：
        1. 优先按 drilldown_targets 传入的顺序
        2. 如果没有顺序，优先使用 mql.dimensions 中的维度
        3. 如果 mql.dimensions 没有有效维度，按默认优先级：FSITE > GROUP_1/2/3/4 > FCHANNEL > 其他
        """
        if not drilldown_targets:
            # 优先使用 mql.dimensions 中的 group by 维度
            if mql and mql.dimensions:
                for dim in mql.dimensions:
                    if dim.value is None and dim.column:
                        if await self._check_dimension_cardinality(dim.column, mql):
                            logger.info(f"[_select_top_dimension] 使用 mql.dimensions 中的维度: {dim.column}")
                            return dim.column
            # 无 drilldown_targets，按默认优先级遍历
            default_priority = ["FSITE", "GROUP_1", "GROUP_2", "GROUP_3", "GROUP_4", "FCHANNEL"]
            for dim in default_priority:
                if await self._check_dimension_cardinality(dim, mql):
                    return dim
            return None

        # 1. 解析 drilldown_targets 为列表
        target_dims = [dim.strip() for dim in drilldown_targets.split(',') if dim.strip()]

        # 2. 默认优先级兜底
        default_priority = ["FSITE", "GROUP_1", "GROUP_2", "GROUP_3", "GROUP_4", "FCHANNEL", "FCOUNTRY", "FREGION"]

        # 3. 合并优先级：先按 drilldown_targets 顺序，再补默认优先级里的其他维度
        sorted_dims = []
        for dim in target_dims:
            if dim not in sorted_dims:
                sorted_dims.append(dim)
        for dim in default_priority:
            if dim not in sorted_dims:
                sorted_dims.append(dim)

        # 4. 遍历选择第一个基数≤1000的维度
        for dim in sorted_dims:
            if await self._check_dimension_cardinality(dim, mql):
                logger.info(f"[_select_top_dimension] 选择维度: {dim}")
                return dim

        logger.warning(f"[_select_top_dimension] 所有可下钻维度基数均>1000，跳过维度归因: {sorted_dims}")
        return None

    async def _check_dimension_cardinality(self, breakdown_dim: str, mql) -> bool:
        """
        检查维度基数是否≤1000，防止慢查询

        通过 StarRocks 查询 COUNT(DISTINCT breakdown_dim)
        """
        try:
            # 构建基础 SQL 检查基数
            from datetime import datetime
            from dateutil.relativedelta import relativedelta

            time_start = mql.time.start if mql.time else None
            time_end = mql.time.end if mql.time else None
            if not time_start or not time_end:
                return False

            start_dt = datetime.strptime(time_start, "%Y-%m-%d")
            end_dt = datetime.strptime(time_end, "%Y-%m-%d")

            # 结束日期不能超过昨天
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if end_dt >= today:
                end_dt = today - relativedelta(days=1)

            # 构建过滤条件
            tables = [mql.metric.table if mql.metric and mql.metric.table else "ids.IDS_AMZ_COMPREHENSIVE_DI"]
            filter_sql = f"FDATE >= '{time_start}' AND FDATE <= '{end_dt.strftime('%Y-%m-%d')}'"

            check_sql = f"SELECT COUNT(DISTINCT {breakdown_dim}) FROM {tables[0]} WHERE {filter_sql}"

            import httpx
            from ai.engine.llm_v2.graph import get_go_api_base

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{get_go_api_base()}/api/v1/query/execute",
                    json={"sql": check_sql, "timeout": 30},
                )
                data = resp.json()
                if data.get("code") == 0 and data.get("data"):
                    inner_data = data["data"]
                    rows = inner_data.get("data") if isinstance(inner_data, dict) else inner_data
                    logger.info(f"[_check_dimension_cardinality] {breakdown_dim} rows type={type(rows)}, first_row={rows[0] if rows else 'empty'}")
                    if rows and rows[0]:
                        first = rows[0]
                        if isinstance(first, (list, tuple)):
                            cardinality = first[0]
                        elif isinstance(first, dict):
                            # 尝试从字典中获取计数值
                            cardinality = first.get('count') or first.get('cnt') or first.get('cardinality') or list(first.values())[0]
                        else:
                            cardinality = first
                        try:
                            result = int(cardinality) <= 1000
                            logger.info(f"[_check_dimension_cardinality] {breakdown_dim} 基数={cardinality}, 通过={result}")
                            return result
                        except (ValueError, TypeError) as e:
                            logger.warning(f"[_check_dimension_cardinality] {breakdown_dim} 解析基数失败: {e}, value={cardinality}")
                return False

        except Exception as e:
            logger.warning(f"[_check_dimension_cardinality] 基数检查失败，跳过该维度: {breakdown_dim}, error: {e}")
            return False

    def _get_dimension_label(self, dim_code: str) -> str:
        """获取维度的中文标签"""
        return self.DIMENSION_LABELS.get(dim_code, dim_code)

    def _build_breakdown_from_attribution(self, attribution_data: List[Dict], kpi: Dict, breakdown_dim: str) -> Optional[List[Dict]]:
        """
        从归因数据构建 breakdown

        规则：
        - 按 contribution_rate 降序排序
        - 分离「拖累项」（change_value < 0）和「贡献项」（change_value > 0）
        - 主要拖累：Top 2（贡献率最大的负向变化）
        - 正向贡献：Top 1（贡献率最大的正向变化）
        """
        if not attribution_data:
            return None

        items = []
        for row in attribution_data:
            dim_value = row.get("dim_value") or row.get("name") or str(row.get(breakdown_dim, ""))
            # 确保数值类型正确
            try:
                current = float(row.get("current")) if row.get("current") is not None else None
                mom = float(row.get("mom")) if row.get("mom") is not None else 0
                yoy = float(row.get("yoy")) if row.get("yoy") is not None else 0
                change_value = float(row.get("change_value")) if row.get("change_value") is not None else 0
                contribution_rate = float(row.get("contribution_rate")) if row.get("contribution_rate") is not None else 0
            except (ValueError, TypeError):
                current = row.get("current")
                mom = yoy = change_value = contribution_rate = 0

            items.append({
                "dim_value": dim_value,
                "current": current,
                "mom": mom,
                "yoy": yoy,
                "change_value": change_value,
                "contribution_rate": contribution_rate,
                "role": "neutral",
                "conclusion": ""
            })

        if not items:
            return None

        # 分离拖累项和贡献项
        drag_items = [item for item in items if item["change_value"] < 0]
        positive_items = [item for item in items if item["change_value"] > 0]

        # 按 contribution_rate 降序排序
        drag_items_sorted = sorted(drag_items, key=lambda x: x["contribution_rate"], reverse=True)
        positive_items_sorted = sorted(positive_items, key=lambda x: x["contribution_rate"], reverse=True)

        # 标记 role
        final_items = []
        for item in drag_items_sorted[:2]:
            item["role"] = "main_drag"
            item["conclusion"] = f"拖累{item['contribution_rate']}%"
            final_items.append(item)
        for item in positive_items_sorted[:1]:
            item["role"] = "positive_contributor"
            item["conclusion"] = f"贡献{item['contribution_rate']}%"
            final_items.append(item)

        if not final_items:
            return None

        # 包装成 breakdown 格式
        dimension_label = self._get_dimension_label(breakdown_dim)
        breakdown = []
        for item in final_items:
            breakdown.append({
                "dimension": f"{item['dim_value']}",
                "raw_value": item["current"],  # 实际销售额
                "value": f"{item['mom']:.1f}%" if item['mom'] else "",
                "change": f"{item['mom']:.1f}%" if item['mom'] else "",
                "impact": item["conclusion"],
                "priority": "P0" if item["role"] == "main_drag" else "P1",
                "reason": item["conclusion"],
                "dimension_type": breakdown_dim,
                "dimension_label": dimension_label,
                "contribution_rate": item["contribution_rate"],
                "role": item["role"],
            })

        logger.info(f"[_build_breakdown_from_attribution] breakdown_dim={breakdown_dim}, 最终 {len(breakdown)} 项")
        return breakdown

    async def _execute_analysis_sql(self, sql: str) -> Dict[str, Any]:
        """执行分析 SQL，返回 {data, total}"""
        try:
            # 通过 Go API 执行 SQL
            import httpx
            from ai.engine.llm_v2.graph import get_go_api_base
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{get_go_api_base()}/api/v1/query/execute",
                    json={"sql": sql, "timeout": 60},
                )
                data = resp.json()
                if data.get("code") == 0 and data.get("data"):
                    inner_data = data["data"]
                    rows = inner_data.get("data") if isinstance(inner_data, dict) else inner_data
                    return {"data": rows or [], "total": len(rows) if rows else 0}
                else:
                    logger.warning(f"[TriggerAnalyzer] 执行分析 SQL 失败: {data.get('message')}")
                    return {"data": [], "total": 0}
        except Exception as e:
            logger.warning(f"[TriggerAnalyzer] 执行分析 SQL 异常: {e}")
            return {"data": [], "total": 0}

    def _extract_analysis_kpi(self, data: List[Dict], mql) -> Dict[str, Any]:
        """从分析结果提取 KPI（mom/yoy/current 等）

        新的 generate_analysis_sql 返回格式：
        - {metric_alias}_raw: 当前期值
        - mom_val: 上月值
        - yoy_val: 去年同期值

        计算百分比：mom = (current - mom_val) / mom_val
        """
        kpi = {}
        if not data:
            return kpi

        # 找最新一条记录，提取 mom/yoy/current 值
        latest = data[0]  # 单行结果
        metric_name = mql.metric.name if mql and mql.metric else ""

        # ========== 检测并处理多行维度数据 ==========
        if len(data) > 1:
            # 使用 mql.dimensions 判断是否是维度探索，而不是 hardcoded 列表
            has_dimension = self._is_dimension_exploration(mql, data)

            if has_dimension:
                # metric_alias 与 metric_name 相同（都来自 mql.metric.name）
                metric_alias = metric_name
                # 正确累加基期值（而非直接累加环比/同比百分比）
                total_current = 0.0
                total_mom_base = 0.0  # 上期值（环比基期）
                total_yoy_base = 0.0  # 去年同期值（同比基期）

                for row in data:
                    # 1. 累加当前值 - 优先使用 SQL alias 名称（{metric_alias}_raw）
                    current_val_row = row.get(f'{metric_alias}_raw') or row.get('销售额当前值') or row.get(f"{metric_name}当前值") or row.get('current')
                    if current_val_row is not None:
                        try:
                            total_current += float(current_val_row)
                        except (ValueError, TypeError):
                            pass

                    # 2. 累加环比基期值（mom_val通常指上期值，而非百分比）
                    mom_base_val = row.get('mom_val') or row.get('上期值') or row.get('mom_base') or row.get('环比')
                    if mom_base_val is not None:
                        try:
                            total_mom_base += float(mom_base_val)
                        except (ValueError, TypeError):
                            pass

                    # 3. 累加同比基期值
                    yoy_base_val = row.get('yoy_val') or row.get('去年同期值') or row.get('yoy_base') or row.get('同比')
                    if yoy_base_val is not None:
                        try:
                            total_yoy_base += float(yoy_base_val)
                        except (ValueError, TypeError):
                            pass

                # 正确计算环比/同比百分比
                kpi["current"] = total_current if total_current != 0 else None
                if total_mom_base != 0 and total_current != 0:
                    kpi["mom"] = ((total_current - total_mom_base) / total_mom_base) * 100
                if total_yoy_base != 0 and total_current != 0:
                    kpi["yoy"] = ((total_current - total_yoy_base) / total_yoy_base) * 100

                logger.info(f"[_extract_analysis_kpi] 多行维度数据处理完成: current={total_current}, mom={kpi.get('mom')}, yoy={kpi.get('yoy')}")
                return kpi

        # ========== 单行KPI处理逻辑 ==========
        # 获取当前期值
        current_val = None
        # 优先使用常见的 SQL alias 名称
        if "销售额_raw" in latest:
            current_val = latest.get("销售额_raw")
        elif "销售额当前值" in latest:
            current_val = latest.get("销售额当前值")
        elif metric_name and f"{metric_name}_raw" in latest:
            current_val = latest.get(f"{metric_name}_raw")
        elif metric_name and f"{metric_name}当前值" in latest:
            current_val = latest.get(f"{metric_name}当前值")
        elif "current_val" in latest:
            current_val = latest.get("current_val")
        elif "当前值" in latest:
            current_val = latest.get("当前值")
        elif "value" in latest:
            current_val = latest.get("value")

        # 获取对比期值
        mom_base = latest.get("mom_val") or latest.get("环比") or latest.get("上期值")
        yoy_base = latest.get("yoy_val") or latest.get("同比") or latest.get("去年同期值")

        # 计算 mom/yoy 百分比（乘100转为百分数形式，与 DEFAULT_RULES 阈值单位一致）
        if mom_base and mom_base != 0 and current_val is not None:
            kpi["mom"] = ((float(current_val) - float(mom_base)) / float(mom_base)) * 100
        # 计算 yoy 百分比
        if yoy_base and yoy_base != 0 and current_val is not None:
            kpi["yoy"] = ((float(current_val) - float(yoy_base)) / float(yoy_base)) * 100

        # 保留原始值
        if current_val is not None:
            kpi["current"] = float(current_val)

        logger.info(f"[_extract_analysis_kpi] current={current_val}, mom_base={mom_base}, yoy_base={yoy_base}, kpi={kpi}")
        return kpi

    def _is_dimension_exploration(self, mql, data: List[Dict]) -> bool:
        """判断是否是维度探索（group by 维度 + 多行数据）

        MQLDimension 字段：type(中文), column(DB列名), field(DB列名), value(过滤值)
        当 value=None 且 column 有值时，表示 group by 维度
        """
        if not mql or not mql.dimensions or not data:
            return False

        # 检查 mql.dimensions 是否有维度且 value=None（group by）
        for dim in mql.dimensions:
            # dim.value is None 表示是 group by，不是过滤
            # dim.column 有值才说明是有效维度
            if dim.value is None and dim.column:
                return True

        return False

    def _merge_dimension_data(self, result_data: List[Dict], attribution_data: List[Dict], dim_col: str) -> List[Dict]:
        """合并 result_data（品类名）和 attribution_data（mom/yoy）

        result_data 格式: {"GROUP_1": "充电创意", "销售额当前值": "57674769.94"}
        attribution_data 格式: {"dim_value": "充电创意", "current": 57674769.94, "mom": -63.5, ...}

        返回格式: {"GROUP_1": "充电创意", "销售额当前值": 57674769.94, "mom": -63.5}
        """
        if not result_data:
            return attribution_data or []
        if not attribution_data:
            return result_data

        # 建立 dim_value -> mom/yoy 的映射
        attr_map = {}
        for row in attribution_data:
            key = row.get("dim_value") or row.get("name")
            if key:
                attr_map[key] = {
                    "mom": row.get("mom"),
                    "yoy": row.get("yoy"),
                    "current": row.get("current"),
                    "contribution_rate": row.get("contribution_rate"),
                }

        # 合并：遍历 result_data，用品类名匹配 mom/yoy
        merged = []
        for row in result_data:
            # 找出品类名（遍历 values 找非数值的）
            dim_name = None
            metric_val = None
            for k, v in row.items():
                if isinstance(v, str) and not v.replace(".", "").replace("-", "").isdigit():
                    dim_name = v
                elif isinstance(v, (int, float)):
                    metric_val = v
            if dim_name and dim_name in attr_map:
                merged_row = dict(row)
                merged_row["mom"] = attr_map[dim_name].get("mom")
                merged_row["yoy"] = attr_map[dim_name].get("yoy")
                merged.append(merged_row)
            elif dim_name:
                merged_row = dict(row)
                merged_row["mom"] = None
                merged_row["yoy"] = None
                merged.append(merged_row)

        return merged if merged else result_data

    async def _generate_dimension_insight(self, mql, data: List[Dict]) -> str:
        """为维度探索查询生成 LLM 洞察"""
        if not data or not mql:
            return ""

        # 1. 获取维度信息（从 mql.dimensions[0]）
        # MQLDimension: type(中文显示名), column(数据库列名), value(过滤值)
        dim_col = None
        dim_type = None
        for dim in (mql.dimensions or []):
            if dim.value is None and dim.column:  # value=None 表示 group by
                dim_col = dim.column
                dim_type = dim.type
                break
        if not dim_col and data:
            dim_col = list(data[0].keys())[0]

        # 验证 dim_col 是否真的在 data 中存在，不存在则从数据中检测
        if dim_col and data and dim_col not in data[0]:
            # mql.dimensions 中的 column 是 DB 列名，可能不在结果集的 keys 中
            # 从数据中找包含字符串值的列（通常是维度名称列）
            for key in data[0].keys():
                val = data[0].get(key)
                if isinstance(val, str) and not val.replace(".", "").replace("-", "").replace("e", "").replace("E", "").replace("+", "").isdigit():
                    dim_col = key
                    break

        # 2. 获取指标信息
        metric_name = mql.metric.name if mql and mql.metric else "销售额"

        # 3. 动态检测指标列和维度列
        # attribution_data 格式: dim_value, current, mom, yoy, contribution_rate
        # breakdown 格式: dimension, raw_value, value (变化率), change, impact
        # data 格式: GROUP_1, 销售额当前值 (merged format from _merge_dimension_data)
        first_row = data[0] if data else {}
        has_attribution_keys = all(k in first_row.keys() for k in ["dim_value", "current"])
        is_attribution = has_attribution_keys
        is_breakdown = "dimension" in first_row.keys() and "value" in first_row.keys()

        if is_attribution:
            # attribution_data 格式
            dim_col = "dim_value"
            metric_col = "current"
        elif is_breakdown:
            # breakdown 格式 (from _build_breakdown_from_attribution)
            dim_col = "dimension"
            metric_col = "raw_value"
        else:
            # 普通格式：检测所有指标列（当前值或 _raw 后缀）
            metric_cols = []
            if data:
                first_row = data[0]
                for key in first_row.keys():
                    if key == dim_col:
                        continue  # 跳过维度列
                    if "当前值" in key or "当前" in key or key.endswith("_raw"):
                        metric_cols.append(key)
                # 如果没找到，收集所有指标名（包括主指标 + mql.metrics 中的附加指标）
                if not metric_cols:
                    all_metric_names = [metric_name]
                    if mql and mql.metrics:
                        for m in mql.metrics:
                            if m.name and m.name not in all_metric_names:
                                all_metric_names.append(m.name)
                    for key in first_row.keys():
                        for mn in all_metric_names:
                            if mn in key:
                                metric_cols.append(key)
                                break
            if not metric_cols:
                metric_cols = ["销售额当前值"]
            # 第一个指标作为主指标（用于占比计算）
            metric_col = metric_cols[0]

        # 4. 计算总和（用于占比）
        total = 0.0
        for row in data:
            val = float(row.get(metric_col) or 0)
            total += val

        # 5. 构建维度描述（前10行 + 占比）
        lines = []
        for row in data[:10]:
            dim_name = row.get(dim_col, "其他")

            # 构建主指标描述
            current_val = float(row.get(metric_col) or 0)
            pct = (current_val / total * 100) if total > 0 else 0
            parts = [f"{current_val/10000:.2f}万（占比{pct:.1f}%）"]

            # 附加其他指标值
            for mcol in metric_cols[1:]:
                val = row.get(mcol)
                if val is not None:
                    try:
                        fval = float(val)
                        # 毛利率通常是小数形式，转成百分比
                        if "率" in mcol and abs(fval) < 1:
                            parts.append(f"{mcol.replace('当前值', '')} {fval*100:.1f}%")
                        else:
                            parts.append(f"{mcol.replace('当前值', '')} {fval/10000:.2f}万")
                    except Exception:
                        parts.append(f"{mcol.replace('当前值', '')} {val}")

            # 提取 mom/yoy（breakdown 格式在 value/change 字段，attribution 格式在 mom/yoy 字段）
            mom_val = row.get("mom")
            yoy_val = row.get("yoy")
            if mom_val is None:
                # breakdown 格式：value 是 mom 字符串如 "-63.5%"
                mom_str = row.get("value") or row.get("change")
                if mom_str and isinstance(mom_str, str) and mom_str.endswith("%"):
                    try:
                        mom_val = float(mom_str.replace("%", ""))
                    except Exception:
                        mom_val = None
            if yoy_val is None:
                yoy_val = None

            line = f"- {dim_name}: " + "，".join(parts)
            if mom_val is not None:
                line += f", 环比{mom_val:+.1f}%"
            if yoy_val is not None:
                line += f", 同比{yoy_val:+.1f}%"
            lines.append(line)

        # 6. 从 prompt 配置表加载 prompt
        pm = get_prompt_manager()
        prompt_config = pm.get_prompt_config("dimension_insight_llm")

        if prompt_config and prompt_config.get("prompt_text"):
            # 使用配置的 prompt 模板
            system_prompt = prompt_config["prompt_text"]
        else:
            # fallback 默认 prompt
            system_prompt = """【角色】
你是一个专业的业务数据分析师，擅长从维度细分数据中提取关键洞察。

【分析要求】
1. 找出占比最高（表现最好）的维度
2. 分析该维度的趋势（环比/同比）
3. 如果有多个维度对比，指出差异
4. 语气专业、简洁，不超过50字

【输出格式】
直接返回洞察文字，不需要解释。"""

        # 7. 构造用户 prompt
        user_prompt = f"""用户问题：{mql.original_question}
维度类型：{dim_type or '未知'}
指标：{metric_name}

各维度数据：
{chr(10).join(lines)}

请生成一句简短洞察（50字以内），重点描述：
1. 哪个维度表现最好（占比最高）
2. 该维度自身的同比/环比趋势

只返回洞察文字，不要解释。"""

        try:
            llm_engine = get_llm_engine_for_analysis()
            result = await llm_engine.generate(
                prompt=user_prompt,
                temperature=0.5,
                max_tokens=100,
                system_prompt=system_prompt
            )
            return result.strip()
        except Exception as e:
            logger.warning(f"[_generate_dimension_insight] LLM 调用失败: {e}")
            return "各维度数据如下：\n" + chr(10).join(lines[:3])

    async def generate_output(self, trigger_result: TriggerResult, mql, result: Dict) -> AnalysisOutput:
        """根据触发结果生成 AnalysisOutput"""
        # 防御性检查：确保 trigger_result 是 TriggerResult 类型
        if not isinstance(trigger_result, TriggerResult):
            logger.error(f"[generate_output] trigger_result is not a TriggerResult! type={type(trigger_result)}")
            raise TypeError(f"trigger_result must be TriggerResult, got {type(trigger_result).__name__}")

        logger.info(f"[generate_output] ENTRY, trigger_type={trigger_result.trigger_type}")

        # 优先使用分析 SQL 的结果（trigger_result.analysis_data），其次使用渲染 SQL 的结果
        # 注意：analysis_data 可能没有 data 但有 attribution_data，两者都需要检查
        analysis_data = getattr(trigger_result, 'analysis_data', None) or {}
        effective_result = analysis_data if (analysis_data.get("data") or analysis_data.get("attribution_data")) else result
        logger.info(f"[generate_output] analysis_data has data={bool(analysis_data.get('data'))}, has_attr={bool(analysis_data.get('attribution_data'))}, eff_result keys={list(effective_result.keys()) if isinstance(effective_result, dict) else type(effective_result)}")
        logger.info(f"[generate_output] is_dim_exploration flag in eff_result={effective_result.get('is_dimension_exploration')}, data len={len(effective_result.get('data', []))}")
        logger.info(f"[generate_output] analysis_data keys={list(analysis_data.keys()) if analysis_data else 'empty'}, has_attr_data={bool(analysis_data.get('attribution_data'))}, attr_data_len={len(analysis_data.get('attribution_data', []) if analysis_data else 0)}")

        # 1. 获取输出模板
        template = await self.template_loader.get_template(
            trigger_result.trigger_type.value if trigger_result.trigger_type else 'generic'
        )
        logger.info(f"[generate_output] template type={type(template)}, keys={list(template.keys()) if isinstance(template, dict) else 'N/A'}")

        # 2. 构建 breakdown
        breakdown = await self._build_breakdown(trigger_result, effective_result)
        logger.info(f"[generate_output] breakdown type={type(breakdown)}, len={len(breakdown) if isinstance(breakdown, (list, tuple)) else 'N/A'}")

        # 3. 翻译维度标签
        breakdown = await self._translate_dimensions(breakdown)
        logger.info(f"[generate_output] after translate breakdown type={type(breakdown)}")

        # 4. 提取 KPI（优先从分析 SQL 的 kpi，其次从 effective_result）
        kpi = analysis_data.get("kpi") if analysis_data else None
        if not kpi:
            kpi = self._extract_kpi(effective_result)
        logger.info(f"[generate_output] kpi type={type(kpi)}, keys={list(kpi.keys()) if isinstance(kpi, dict) else 'N/A'}")

        # 4b. 数据不足场景：直接用 trigger_reason 作为 summary，不走 LLM
        if (trigger_result.trigger_type == TriggerType.GENERIC_QUERY
                and "数据点不足" in trigger_result.trigger_reason):
            summary = trigger_result.trigger_reason
            action_items = [{"text": "请扩大时间范围或检查筛选条件", "type": "normal"}]
            drilldown_options = trigger_result.drilldown_options or []
            return AnalysisOutput(
                trigger=trigger_result.trigger_type.value,
                summary=summary,
                kpi=kpi,
                breakdown=breakdown,
                action_items=action_items,
                drilldown_options=drilldown_options
            )

        # 4c. 维度探索：直接生成维度洞察
        is_dim_exploration = effective_result.get("is_dimension_exploration") or self._is_dimension_exploration(mql, effective_result.get("data", []))
        if is_dim_exploration and effective_result.get("data"):
            try:
                # 合并 result_data（品类名）和 attribution_data（mom/yoy）
                result_data = effective_result.get("data", [])
                attr_data = effective_result.get("attribution_data") or []
                # 获取维度列名
                dim_col = None
                for dim in (mql.dimensions or []):
                    if dim.value is None and dim.column:
                        dim_col = dim.column
                        break
                insight_data = self._merge_dimension_data(result_data, attr_data, dim_col)
                insight = await self._generate_dimension_insight(mql, insight_data)
                summary = insight
                # 确保 breakdown 是原始多行数据
                breakdown = effective_result.get("data", [])
                action_items = [{"text": "查看各维度明细趋势", "type": "normal"}]
                logger.info(f"[generate_output] 维度探索洞察生成成功: {summary[:50] if summary else 'N/A'}")
                return AnalysisOutput(
                    trigger="dimension_exploration",
                    summary=summary,
                    kpi={},
                    breakdown=breakdown,
                    action_items=action_items,
                    drilldown_options=trigger_result.drilldown_options or []
                )
            except Exception as e:
                logger.warning(f"[generate_output] 维度探索洞察生成失败: {e}")

        # 5. VolatilityTrigger + 有意义 KPI → 尝试 LLM 生成自然语言
        summary = None
        action_items = None
        if trigger_result.trigger_type == TriggerType.VOLATILITY and (kpi.get('mom') is not None or kpi.get('yoy') is not None):
            # 检查是否是维度探索
            if self._is_dimension_exploration(mql, effective_result.get("data", [])):
                # 维度探索：LLM 生成洞察 + 展示明细
                try:
                    insight_data = effective_result.get("attribution_data") or effective_result.get("data", [])
                    insight = await self._generate_dimension_insight(mql, insight_data)
                    summary = insight
                    # 确保 breakdown 是原始多行数据
                    breakdown = effective_result.get("data", [])
                    logger.info(f"[generate_output] 维度探索洞察生成成功: {summary[:50] if summary else 'N/A'}")
                except Exception as e:
                    logger.warning(f"[generate_output] 维度探索洞察生成失败: {e}")
                    summary = None
            else:
                # 现有波动触发器逻辑
                try:
                    # 获取指标名称
                    metric_name = ""
                    if hasattr(mql, 'metric') and mql.metric:
                        metric_name = getattr(mql.metric, 'name', '') or getattr(mql.metric, 'code', '') or ''
                    elif hasattr(mql, 'name'):
                        metric_name = mql.name

                    # 获取 business_summary（如果有）
                    business_summary = ""
                    if hasattr(mql, 'metric') and mql.metric:
                        business_summary = getattr(mql.metric, 'business_summary', '') or ''

                    # 尝试从 prompt_configs 加载 LLM prompt
                    pm = get_prompt_manager()
                    prompt_config = pm.get_prompt_config("volatility_summary_llm")

                    if prompt_config and prompt_config.get("prompt_text"):
                        logger.info(f"[generate_output] 使用 LLM 生成自然语言 summary，prompt_config={prompt_config.get('name')}")
                        # 构建 breakdown 描述
                        breakdown_desc = ""
                        if breakdown:
                            dim_parts = []
                            for dim in breakdown[:3]:
                                dim_parts.append(
                                    f"{dim.get('dimension', '')}({dim.get('change', dim.get('value', ''))})"
                                )
                            breakdown_desc = "，".join(dim_parts)

                        # 构造用户 prompt
                        # 获取时间范围
                        time_desc = ""
                        if hasattr(mql, 'time') and mql.time:
                            time_obj = mql.time
                            time_desc = f"{getattr(time_obj, 'original', '') or ''}（{getattr(time_obj, 'start', '')} ~ {getattr(time_obj, 'end', '')}）"

                        user_prompt = f"""指标：{metric_name}，时间：{time_desc if time_desc else '未指定'}，环比：{kpi.get('mom')}% ，同比：{kpi.get('yoy')}%
主要拖累：{breakdown_desc if breakdown_desc else '无明显维度波动'}
业务口径：{business_summary if business_summary else '无'}"""

                        system_prompt = prompt_config["prompt_text"]
                        llm_engine = get_llm_engine_for_analysis()
                        llm_result = await llm_engine.generate(
                            prompt=user_prompt,
                            temperature=0.7,
                            max_tokens=800,
                            system_prompt=system_prompt
                        )
                        logger.info(f"[generate_output] LLM result={llm_result[:200] if llm_result else 'N/A'}")

                        # 解析 LLM 响应：优先 JSON，次选纯文本
                        # 先去除 markdown fences（处理 LLM 返回 ```json {...} ``` 的情况）
                        cleaned = llm_result.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        if cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()

                        try:
                            parsed = json.loads(cleaned)
                            summary = parsed.get("summary", "")
                            raw_items = parsed.get("action_items", [])
                            if isinstance(raw_items, list):
                                action_items = []
                                for item in raw_items:
                                    if isinstance(item, dict):
                                        action_items.append({
                                            "text": item.get("text", item.get("suggestion", "")),
                                            "type": item.get("type", "normal")
                                        })
                                    else:
                                        action_items.append({"text": str(item), "type": "normal"})
                            else:
                                action_items = [{"text": summary, "type": "normal"}]
                        except (json.JSONDecodeError, ValueError):
                            # 非 JSON 格式，整段作为 summary
                            summary = cleaned
                            action_items = [{"text": "建议关注该指标变化", "type": "normal"}]

                        logger.info(f"[generate_output] LLM 生成成功，summary={summary[:80] if summary else 'N/A'}")
                    else:
                        logger.info(f"[generate_output] 未配置 volatility_summary_llm prompt，使用模板")
                except Exception as e:
                    logger.warning(f"[generate_output] LLM 生成失败: {e}，回退到模板")
                    summary = None
                    action_items = None

        # 6. 模板 fallback
        if summary is None:
            summary = self._build_summary(trigger_result, breakdown, template)
            logger.info(f"[generate_output] summary={summary[:50] if summary else 'N/A'}")

        # 7. 优先从语义快照获取 action_items（scene_type 映射到 trigger_type）
        if action_items is None:
            scene_type_map = {
                TriggerType.VOLATILITY: "volatility",
                TriggerType.COMPARISON: "comparison",
                TriggerType.AD_EFFECT: "ad_effect",
                TriggerType.INVENTORY_RISK: "inventory_risk",
                TriggerType.GENERIC_QUERY: "generic_query",
                TriggerType.CONTEXT_FOLLOWUP: "context_followup",
            }
            scene_type = scene_type_map.get(trigger_result.trigger_type, "generic_query")
            # ========== 优先使用语义层 recommend() 获取 ==========
            try:
                from ai.services.semantic_layer import get_semantic_layer_service
                from ai.services.semantic_layer.api import RecommendContext

                semantic_layer = get_semantic_layer_service()
                recommend_context = RecommendContext(stage="trigger_analysis", trigger_type=scene_type)
                recommend_result = semantic_layer.recommend(recommend_context)
                if recommend_result.actions:
                    action_items = [{"text": a.get("label", ""), "type": "normal"} for a in recommend_result.actions if a.get("label")]
                    logger.info(f"[generate_output] 从语义层 recommend() 获取 action_items")
            except Exception as e:
                logger.warning(f"[generate_output] 语义层 recommend 失败: {e}")
                action_items = None
            # ====================================================
            if action_items is None:
                # 回退到直接调用语义快照
                semantic_svc = self._get_semantic_service()
                if semantic_svc:
                    snapshot_actions = semantic_svc.recommend_actions(scene_type, limit=4)
                    if snapshot_actions:
                        logger.info(f"[generate_output] 从语义快照获取 action_items: {snapshot_actions}")
                        action_items = [{"text": a.get("label", ""), "type": "normal"} for a in snapshot_actions if a.get("label")]
            if action_items is None:
                action_items = self._build_action_items(trigger_result, breakdown, template)
                logger.info(f"[generate_output] action_items type={type(action_items)}, len={len(action_items) if isinstance(action_items, (list, tuple)) else 'N/A'}")

        # 8. 优先从语义快照获取 drilldown_options（与 trigger 的 primary options 合并）
        scene_type_map = {
            TriggerType.VOLATILITY: "volatility",
            TriggerType.COMPARISON: "comparison",
            TriggerType.AD_EFFECT: "ad_effect",
            TriggerType.INVENTORY_RISK: "inventory_risk",
            TriggerType.GENERIC_QUERY: "generic_query",
            TriggerType.CONTEXT_FOLLOWUP: "context_followup",
        }
        scene_type = scene_type_map.get(trigger_result.trigger_type, "generic_query")
        primary_drilldowns = trigger_result.drilldown_options or []
        semantic_drilldowns = []

        # ========== 优先使用语义层 recommend() 和 enrich() 获取 ==========
        try:
            from ai.services.semantic_layer import get_semantic_layer_service
            from ai.services.semantic_layer.api import RecommendContext, EnrichStage

            semantic_layer = get_semantic_layer_service()

            # 使用 recommend() 获取 actions
            recommend_context = RecommendContext(stage="trigger_analysis", trigger_type=scene_type)
            recommend_result = semantic_layer.recommend(recommend_context)
            if recommend_result.actions:
                semantic_drilldowns = recommend_result.actions
                logger.info(f"[generate_output] 从语义层 recommend() 获取 drilldown_options: {semantic_drilldowns}")
            else:
                # 使用 enrich() 获取 scene_drilldown_categories
                from ai.services.semantic_layer.api import ParseResult
                enrich_result = semantic_layer.enrich(ParseResult(intent="", confidence=0.0),
                                                     stage=EnrichStage.TRIGGER_ANALYSIS,
                                                     trigger_type=scene_type)
                if enrich_result.scene_drilldown_categories:
                    for cat, sub_cats in enrich_result.scene_drilldown_categories.items():
                        for sub_cat in sub_cats[:5]:
                            semantic_drilldowns.append({
                                "label": f"按{cat}/{sub_cat}",
                                "action": "drilldown",
                                "params": {"category": cat, "sub_category": sub_cat},
                            })
                    logger.info(f"[generate_output] 从语义层 enrich() 获取 drilldown_options: {semantic_drilldowns}")
        except Exception as e:
            logger.warning(f"[generate_output] 语义层获取 drilldown_options 失败: {e}")
        # ====================================================

        # 回退到直接调用语义快照
        if not semantic_drilldowns:
            semantic_svc = self._get_semantic_service()
            if semantic_svc:
                # 优先用 recommend_actions 获取 drilldown_options
                snapshot_actions = semantic_svc.recommend_actions(scene_type, limit=4) or []
                if snapshot_actions:
                    semantic_drilldowns = snapshot_actions
                    logger.info(f"[generate_output] 从语义快照 recommend_actions 获取 drilldown_options: {semantic_drilldowns}")
                else:
                    # 次选 get_scene_drilldown_categories
                    snapshot_drilldowns = semantic_svc.get_scene_drilldown_categories(scene_type)
                    if snapshot_drilldowns:
                        for cat, sub_cats in snapshot_drilldowns.items():
                            for sub_cat in sub_cats[:5]:
                                semantic_drilldowns.append({
                                    "label": f"按{cat}/{sub_cat}",
                                    "action": "drilldown",
                                    "params": {"category": cat, "sub_category": sub_cat},
                                })
                        logger.info(f"[generate_output] 从语义快照 get_scene_drilldown_categories 获取 drilldown_options: {semantic_drilldowns}")
        # 合并 primary 和 semantic（去重）
        drilldown_options = self._merge_drilldown_options(primary_drilldowns, semantic_drilldowns)

        logger.info(f"[generate_output] drilldown_options type={type(drilldown_options)}")

        try:
            output = AnalysisOutput(
                trigger=trigger_result.trigger_type.value if trigger_result.trigger_type else 'unknown',
                summary=summary,
                kpi=kpi,
                breakdown=breakdown,
                action_items=action_items,
                drilldown_options=drilldown_options
            )
            logger.info(f"[generate_output] SUCCESS, created AnalysisOutput")
            return output
        except Exception as e:
            logger.error(f"[generate_output] FAILED to create AnalysisOutput: {e}")
            logger.error(f"[generate_output] breakdown value: {breakdown}")
            raise

    async def _build_breakdown(self, trigger_result: TriggerResult, result: Dict) -> List[Dict]:
        """构建 breakdown

        优先顺序：
        1. trigger_result.affected_dimensions（trigger check 中已计算）
        2. result.attribution_data（归因 SQL 结果）
        3. 从 result.data 构建
        """
        # 防御性检查：确保 affected_dimensions 是列表
        affected = trigger_result.affected_dimensions
        if not isinstance(affected, list):
            logger.warning(f"[_build_breakdown] affected_dimensions is not a list! type={type(affected)}, converting to empty list")
            affected = []
        if affected:
            return affected

        # 2. 优先使用归因数据（attribution_data 已在 _execute_dimension_attribution 中构建好 breakdown 格式）
        attribution_data = result.get("attribution_data", [])
        if attribution_data:
            logger.info(f"[_build_breakdown] 使用 attribution_data，共 {len(attribution_data)} 项")
            return attribution_data

        # 从result数据构建
        breakdown = []
        data = result.get("data", [])
        if data and len(data) > 1:
            first_row = data[0]
            dimension_key = None
            # 扩展维度列检测：支持 FSITE（站点）、country、platform、店铺等
            for key in ['FSITE', '站点', 'dimension', 'country', 'platform', 'site', 'SITE', '店铺']:
                if key in first_row:
                    dimension_key = key
                    break

            # 检测指标列（用于排序和取值）
            # 扩展：支持中文列名（销售额当前值、销售额_raw）和常见的 metric_val/mom_val/yoy_val
            metric_key = None
            for mk in ['销售额当前值', '销售额_raw', 'ORDERED_PRODUCTSALES', 'GMV', 'SALES', 'REVENUE', 'value', 'VALUE', 'TOTAL']:
                if mk in first_row:
                    metric_key = mk
                    break

            # 如果没有找到主指标列，尝试使用 mom_val/yoy_val 作为排序依据
            if not metric_key:
                if 'mom_val' in first_row:
                    metric_key = 'mom_val'
                elif 'yoy_val' in first_row:
                    metric_key = 'yoy_val'
                elif '环比' in first_row:
                    metric_key = '环比'

            if dimension_key:
                # 按指标值排序，取 top 10
                try:
                    sorted_data = sorted(
                        [r for r in data if r.get(dimension_key)],
                        key=lambda r: float(r.get(metric_key, 0) or 0) if metric_key else 0,
                        reverse=True
                    )
                except (ValueError, TypeError):
                    sorted_data = data[:10]

                for row in sorted_data[:10]:
                    raw_val = row.get(dimension_key, '')
                    # 优先使用 销售额当前值/销售额_raw 作为当前值
                    value_key = '销售额当前值' if '销售额当前值' in row else ('销售额_raw' if '销售额_raw' in row else metric_key)
                    metric_val = float(row.get(value_key, 0) or 0) if value_key else 0
                    # 环比/同比变化
                    # 优先使用 mom_change（SQL 已格式化的百分比字符串，如 '+2627.168%'）
                    # 次选 mom_val/yoy_val（需要判断是比例还是百分比）
                    change_val = row.get('mom_change') or row.get('mom_val') or row.get('环比') or row.get('yoy_val') or row.get('同比')
                    change_str = ""
                    if change_val is not None:
                        try:
                            # 统一格式化百分比，保留2位小数
                            change_float = float(str(change_val).replace("%", "").replace(",", ""))
                            if -2 < change_float < 2:
                                # 比例形式（-1到1的小数），乘100转百分比
                                change_str = f"{change_float * 100:+.2f}%"
                            else:
                                # 已经是百分比形式，直接格式化
                                change_str = f"{change_float:+.2f}%"
                        except (ValueError, TypeError):
                            change_str = str(change_val)
                    breakdown.append({
                        "dimension": raw_val,
                        "raw_value": raw_val,
                        "value": str(round(metric_val, 2)),
                        "change": change_str,
                        "impact": "",
                        "priority": "P2",
                        "reason": "",
                        "dimension_type": dimension_key.upper()
                    })

        return breakdown

    async def _translate_dimensions(self, breakdown: List[Dict]) -> List[Dict]:
        """翻译维度值为业务标签"""
        translated = []
        for item in breakdown:
            dim_type = item.get('dimension_type', '')
            dim_val = item.get('dimension', '')
            label = await self.template_loader.get_dimension_label(dim_type, str(dim_val))
            emoji = label.get('emoji', '')
            display_name = label.get('display_name', dim_val)
            item['dimension'] = display_name
            item['emoji'] = emoji
            translated.append(item)
        return translated

    def _build_summary(self, trigger_result: TriggerResult, breakdown: List[Dict], template: Dict) -> str:
        """使用模板构建 summary"""
        if not breakdown:
            return trigger_result.trigger_reason

        # 获取对应 trigger_type 的 summary 模板
        trigger_type = trigger_result.trigger_type.value if trigger_result.trigger_type else 'generic'
        tmpl_key = f"{trigger_type}_summary"
        tmpl = template.get(tmpl_key) or template.get('summary_template') or '{{dimension}}{{change}}，{{impact}}'

        top = breakdown[0]
        summary = tmpl
        summary = summary.replace('{{dimension}}', top.get('dimension', ''))
        summary = summary.replace('{{emoji}}', '')
        summary = summary.replace('{{change}}', top.get('change', top.get('value', '')))
        summary = summary.replace('{{value}}', top.get('value', ''))
        summary = summary.replace('{{impact}}', top.get('impact', ''))
        summary = summary.replace('{{reason}}', top.get('reason', ''))
        return summary

    def _build_action_items(self, trigger_result: TriggerResult, breakdown: List[Dict], template: Dict) -> List[Dict]:
        """使用模板构建 action_items"""
        trigger_type = trigger_result.trigger_type.value if trigger_result.trigger_type else 'generic'
        # 优先用 reason 模板，次选用 action 模板
        reason_key = f"{trigger_type}_reason"
        action_key = f"{trigger_type}_action"
        reason_tmpl = template.get(reason_key)
        action_tmpl = template.get(action_key)

        items = []
        for dim in breakdown[:3]:
            priority = dim.get('priority', 'P2')
            # 用 reason 模板渲染
            text = ""
            if reason_tmpl:
                text = reason_tmpl
                text = text.replace('{{dimension}}', dim.get('dimension', ''))
                text = text.replace('{{value}}', dim.get('value', ''))
                text = text.replace('{{days}}', str(dim.get('days', '')))
            elif action_tmpl:
                text = action_tmpl
            else:
                text = f"关注 {dim.get('dimension', '')} 变化" if dim.get('dimension') else "建议关注该指标变化"

            item_type = "normal"
            if priority == "P0":
                item_type = "urgent"
            elif priority == "P1":
                item_type = "warning"
            items.append({"text": text, "type": item_type})

        if not items:
            items.append({"text": "建议持续关注数据变化", "type": "normal"})
        return items

    def _extract_kpi(self, result: Dict) -> Dict:
        """提取 KPI 数据，支持多种字段名"""
        # current_value：优先标准别名，其次 raw column（ORDERED_PRODUCTSALES 等）
        current = result.get('current_value')
        if current is None or current == 0:
            current = result.get('value', 0)
        if (current is None or current == 0) and 'data' in result:
            # generic query 场景：SQL 返回 raw column（如 ORDERED_PRODUCTSALES），尝试提取
            data_rows = result.get('data', [])
            if data_rows:
                # 尝试常见的 metric 列名
                metric_keys = ['ORDERED_PRODUCTSALES', 'GMV', 'SALES', 'REVENUE', 'VALUE']
                for key in metric_keys:
                    total = 0
                    has_key = False
                    for row in data_rows:
                        if key in row:
                            has_key = True
                            try:
                                val = float(row[key] or 0)
                                if val > 0:
                                    total += val
                            except (ValueError, TypeError):
                                pass
                    if has_key and total > 0:
                        current = total
                        break
        return {
            "current": current or 0,
            "mom": result.get('mom_change'),
            "yoy": result.get('yoy_change'),
            "unit": result.get('unit', '')
        }


class TemplateLoader:
    """输出模板加载器，支持热修改"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
        self.CACHE_TTL = 60  # 缓存60秒，支持热修改

    async def get_template(self, trigger_type: str) -> Dict:
        """获取触发类型的输出模板，按 trigger_type 过滤"""
        cache_key = f"tmpl_{trigger_type}"
        if cache_key in self._cache:
            if time.time() - self._cache_time.get(cache_key, 0) < self.CACHE_TTL:
                return self._cache[cache_key]

        try:
            import psycopg2
            conn = psycopg2.connect(
                host="192.168.1.225",
                port=5432,
                user="postgres",
                password="admin123",
                database="dev_metric",
                connect_timeout=5
            )
            cur = conn.cursor()
            # 按 trigger_type 映射到 template_key 前缀
            cur.execute("""
                SELECT template_key, content_template
                FROM output_templates
                WHERE enabled = true
                AND (
                    (template_key = %s AND template_type = 'summary')
                    OR (template_key LIKE %s AND template_type = 'reason')
                    OR (template_key LIKE %s AND template_type = 'action')
                )
            """, (f"{trigger_type}_summary", f"{trigger_type}_%", f"{trigger_type}_%"))
            rows = cur.fetchall()
            conn.close()

            template = {}
            for row in rows:
                template[row[0]] = row[1]
            self._cache[cache_key] = template
            self._cache_time[cache_key] = time.time()
            return template
        except Exception as e:
            logger.warning(f"[TemplateLoader] 加载模板失败: {e}")
            # 硬编码 fallback
            return {
                "summary_template": "{{dimension}}{{change}}，{{impact}}",
                "reason_template": "{{dimension}}下降{{value}}",
                "action_template": "建议关注该指标变化"
            }

    async def get_dimension_label(self, dimension_type: str, raw_value: str) -> Dict:
        """获取维度标签翻译"""
        cache_key = f"{dimension_type}:{raw_value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import psycopg2
            conn = psycopg2.connect(
                host="192.168.1.225",
                port=5432,
                user="postgres",
                password="admin123",
                database="dev_metric",
                connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT display_name, emoji
                FROM business_dimension_labels
                WHERE dimension_type = %s AND raw_value = %s
            """, (dimension_type, raw_value))
            row = cur.fetchone()
            conn.close()

            result = {
                'display_name': row[0] if row else raw_value,
                'emoji': row[1] if row else ''
            }
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning(f"[TemplateLoader] 获取维度标签失败: {e}")
            return {'display_name': raw_value, 'emoji': ''}


class TriggerSwitchChecker:
    """触发器开关检查，支持灰度"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self._cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, float] = {}
        self.CACHE_TTL = 10  # 开关缓存10秒，快速响应

    async def get_switch_status(self, trigger_type: str) -> str:
        """获取触发器状态: enabled/disabled/gray"""
        # 检查缓存
        if trigger_type in self._cache:
            if time.time() - self._cache_time.get(trigger_type, 0) < self.CACHE_TTL:
                return self._cache[trigger_type]['status']

        try:
            import psycopg2
            conn = psycopg2.connect(
                host="192.168.1.225",
                port=5432,
                user="postgres",
                password="admin123",
                database="dev_metric",
                connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT switch_status, gray_ratio
                FROM trigger_switches
                WHERE trigger_type = %s
            """, (trigger_type,))
            row = cur.fetchone()
            conn.close()

            status = row[0] if row else 'enabled'
            gray_ratio = row[1] if row else 100
            self._cache[trigger_type] = {'status': status, 'gray_ratio': gray_ratio}
            self._cache_time[trigger_type] = time.time()
            return status
        except Exception as e:
            logger.warning(f"[TriggerSwitchChecker] 获取开关状态失败: {e}")
            return 'enabled'

    async def get_gray_ratio(self, trigger_type: str) -> int:
        """获取灰度比例"""
        info = self._cache.get(trigger_type, {})
        return info.get('gray_ratio', 100)

    async def set_switch(self, trigger_type: str, status: str, gray_ratio: int = 100):
        """设置触发器开关（运维接口）"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="192.168.1.225",
                port=5432,
                user="postgres",
                password="admin123",
                database="dev_metric",
                connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO trigger_switches (trigger_type, switch_status, gray_ratio, switched_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (trigger_type) DO UPDATE
                SET switch_status = %s, gray_ratio = %s, switched_at = NOW()
            """, (trigger_type, status, gray_ratio, status, gray_ratio))
            conn.commit()
            conn.close()
            # 清除缓存
            self._cache.pop(trigger_type, None)
        except Exception as e:
            logger.error(f"[TriggerSwitchChecker] 设置开关失败: {e}")
