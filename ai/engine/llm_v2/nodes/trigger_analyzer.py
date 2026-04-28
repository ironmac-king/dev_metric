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
from ai.engine.llm_v2.nodes.volatility_analyzer import VolatilityAnalyzer

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
                    database="dev_metric"
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

        # 提取波动数据
        mom = result.get("mom_change", 0)
        yoy = result.get("yoy_change", 0)
        current = result.get("current_value", result.get("value", 0))

        # 如果没有mom/yoy，尝试从数据计算
        if mom == 0 and "data" in result:
            mom = self._calc_mom_from_data(result.get("data", []))

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
        values = [row.get('value', 0) for row in data if 'value' in row]
        if len(values) < 2:
            return 0
        current = values[-1]
        prev = values[-2]
        if prev == 0:
            return 0
        return (current - prev) / prev * 100

    async def _calc_affected_dimensions(self, result: Dict, metric_code: str) -> List[Dict]:
        """计算各维度对整体的影响，使用 IQR 异常检测"""
        # 复用 volatility_analyzer 的 IQR 逻辑
        data = result.get("data", [])
        if not data:
            return []

        # 尝试使用 VolatilityAnalyzer
        try:
            analyzer = VolatilityAnalyzer()
            # 尝试检测维度列
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
            options = [
                self._build_drilldown("🏪 站点健康度", {"check": "site_health"}),
                self._build_drilldown("📢 广告效果", {"check": "ad_effect"}),
            ]
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

        # 检测四类分析词（文字匹配）
        if not drilldown_type:
            for check_type, patterns in self.DRILLDOWN_CATEGORY_PATTERNS.items():
                if any(p in question for p in patterns):
                    drilldown_type = check_type
                    break

        if drilldown_type:
            # 四类分析词触发对应的分析
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
                trigger_reason=f"触发{category_labels.get(drilldown_type, drilldown_type)}",
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
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.AD_EFFECT,
                trigger_reason="广告效果分析",
                priority=Priority.P1,
                affected_dimensions=[],
                drilldown_options=[
                    self._build_drilldown("📢 按渠道对比", {"dimension": "ad_channel"}),
                    self._build_drilldown("📉 低效站点", {"dimension": "low_roas_site"}),
                    self._build_drilldown("💰 花费明细", {"metric": "ad_spend"}),
                    self._build_drilldown("📊 ROI趋势", {"metric": "roi_trend"}),
                ]
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

            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.INVENTORY_RISK,
                trigger_reason=f"库存可售天数{inventory_days}天",
                priority=priority,
                affected_dimensions=[],
                drilldown_options=[
                    self._build_drilldown("📦 库存明细", {"check": "inventory_detail"}),
                    self._build_drilldown("⚠️ 断货预警", {"check": "stockout_risk"}),
                ]
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
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.CONTEXT_FOLLOWUP,
                trigger_reason="连续追问，进入深度归因",
                priority=Priority.P1,
                affected_dimensions=[],
                drilldown_options=[
                    self._build_drilldown("🏪 按站点归因", {"drilldown": "site"}),
                    self._build_drilldown("📊 按因素归因", {"drilldown": "factor"}),
                    self._build_drilldown("⏰ 时间维度", {"drilldown": "time"}),
                ]
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

        if is_comparison and has_multi_dims:
            return TriggerResult(
                should_analyze=True,
                trigger_type=TriggerType.COMPARISON,
                trigger_reason="多维度对比分析",
                priority=Priority.P2,
                affected_dimensions=[],
                drilldown_options=[
                    self._build_drilldown("📊 各维度排序", {"check": "dimension_rank"}),
                    self._build_drilldown("🔍 Top/Bottom", {"check": "top_bottom"}),
                ]
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

        # 2. 获取已启用的触发器
        enabled_triggers = []
        for t in self.triggers:
            try:
                trigger_type = t.trigger_type.value if hasattr(t, 'trigger_type') else type(t).__name__
                status = await self.switch_checker.get_switch_status(trigger_type)
                if status == 'disabled':
                    continue
                if status == 'gray':
                    gray_ratio = await self.switch_checker.get_gray_ratio(trigger_type)
                    if not self._in_gray_group(gray_ratio):
                        continue
                enabled_triggers.append(t)
            except Exception as e:
                logger.warning(f"[TriggerAnalyzer] 检查触发器{t}开关失败: {e}")
                enabled_triggers.append(t)  # 出错时默认启用

        # 3. 并行执行启用的触发器
        if not enabled_triggers:
            return TriggerResult(should_analyze=False)

        tasks = [t.check(mql, result, state) for t in enabled_triggers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, TriggerResult) and r.should_analyze:
                logger.info(f"[TriggerAnalyzer] 触发器命中: {r.trigger_type}")
                return r

        return TriggerResult(should_analyze=False)

    def _in_gray_group(self, gray_ratio: int) -> bool:
        """灰度逻辑：基于时间戳哈希"""
        import hashlib
        ts = str(time.time())
        session_hash = hashlib.md5(ts.encode()).hexdigest()
        return int(session_hash[:8], 16) % 100 < gray_ratio

    async def generate_output(self, trigger_result: TriggerResult, mql, result: Dict) -> AnalysisOutput:
        """根据触发结果生成 AnalysisOutput"""
        # 防御性检查：确保 trigger_result 是 TriggerResult 类型
        if not isinstance(trigger_result, TriggerResult):
            logger.error(f"[generate_output] trigger_result is not a TriggerResult! type={type(trigger_result)}")
            raise TypeError(f"trigger_result must be TriggerResult, got {type(trigger_result).__name__}")

        logger.info(f"[generate_output] ENTRY, trigger_type={trigger_result.trigger_type}")

        # 1. 获取输出模板
        template = await self.template_loader.get_template(
            trigger_result.trigger_type.value if trigger_result.trigger_type else 'generic'
        )
        logger.info(f"[generate_output] template type={type(template)}, keys={list(template.keys()) if isinstance(template, dict) else 'N/A'}")

        # 2. 构建 breakdown
        breakdown = await self._build_breakdown(trigger_result, result)
        logger.info(f"[generate_output] breakdown type={type(breakdown)}, len={len(breakdown) if isinstance(breakdown, (list, tuple)) else 'N/A'}")

        # 3. 翻译维度标签
        breakdown = await self._translate_dimensions(breakdown)
        logger.info(f"[generate_output] after translate breakdown type={type(breakdown)}")

        # 4. 构建 summary
        summary = self._build_summary(trigger_result, breakdown, template)
        logger.info(f"[generate_output] summary={summary[:50] if summary else 'N/A'}")

        # 5. 构建 action_items
        action_items = self._build_action_items(trigger_result, breakdown, template)
        logger.info(f"[generate_output] action_items type={type(action_items)}, len={len(action_items) if isinstance(action_items, (list, tuple)) else 'N/A'}")

        # 6. 提取 KPI
        kpi = self._extract_kpi(result)
        logger.info(f"[generate_output] kpi type={type(kpi)}, keys={list(kpi.keys()) if isinstance(kpi, dict) else 'N/A'}")

        logger.info(f"[generate_output] drilldown_options type={type(trigger_result.drilldown_options)}")

        try:
            output = AnalysisOutput(
                trigger=trigger_result.trigger_type.value if trigger_result.trigger_type else 'unknown',
                summary=summary,
                kpi=kpi,
                breakdown=breakdown,
                action_items=action_items,
                drilldown_options=trigger_result.drilldown_options
            )
            logger.info(f"[generate_output] SUCCESS, created AnalysisOutput")
            return output
        except Exception as e:
            logger.error(f"[generate_output] FAILED to create AnalysisOutput: {e}")
            logger.error(f"[generate_output] breakdown value: {breakdown}")
            raise

    async def _build_breakdown(self, trigger_result: TriggerResult, result: Dict) -> List[Dict]:
        """构建 breakdown"""
        # 防御性检查：确保 affected_dimensions 是列表
        affected = trigger_result.affected_dimensions
        if not isinstance(affected, list):
            logger.warning(f"[_build_breakdown] affected_dimensions is not a list! type={type(affected)}, converting to empty list")
            affected = []
        if affected:
            return affected

        # 从result数据构建
        breakdown = []
        data = result.get("data", [])
        if data and len(data) > 1:
            first_row = data[0]
            dimension_key = None
            # 扩展维度列检测：支持 FSITE（站点）、country、platform 等
            for key in ['FSITE', '站点', 'dimension', 'country', 'platform', 'site', 'SITE']:
                if key in first_row:
                    dimension_key = key
                    break

            # 检测指标列（用于排序和取值）
            metric_key = None
            for mk in ['ORDERED_PRODUCTSALES', 'GMV', 'SALES', 'REVENUE', 'value', 'VALUE', 'TOTAL']:
                if mk in first_row:
                    metric_key = mk
                    break

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
                    metric_val = float(row.get(metric_key, 0) or 0) if metric_key else 0
                    breakdown.append({
                        "dimension": raw_val,
                        "raw_value": raw_val,
                        "value": str(round(metric_val, 2)),
                        "change": "",
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
            raw_val = item.get('raw_value', '')
            label = await self.template_loader.get_dimension_label(dim_type, raw_val)
            emoji = label.get('emoji', '')
            display_name = label.get('display_name', raw_val)
            item['dimension'] = f"{emoji} {display_name}" if emoji else display_name
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
        summary = summary.replace('{{emoji}}', top.get('emoji', ''))
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
                database="dev_metric"
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
                database="dev_metric"
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
                database="dev_metric"
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
                database="dev_metric"
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
