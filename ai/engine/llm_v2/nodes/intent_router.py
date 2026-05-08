"""
步骤 1: 意图路由智能体

职责：
- 识别用户意图（query_value / query_trend / query_comparison 等）
- 判断是否需要追问
- 继承上轮对话上下文
- 本地模型优先匹配，LLM 兜底
"""
import json
import re
from enum import Enum
from typing import Dict, Any, Optional, List
from ai.config.logging_config import get_logger
from ai.engine.prompt_manager import get_prompt_manager
from ai.engine.llm import get_llm_engine
from ..schema import V2State, MQLSchema, MQLIntent, MQLDimension, TimeRange, TimeType, AggregationType
from ai.engine.time_parser import TimeParser

logger = get_logger("ai.llm_v2.intent_router")


class FollowupAction(Enum):
    REPLACE_METRIC = "replace_metric"
    ADD_METRIC = "add_metric"
    REMOVE_METRIC = "remove_metric"
    REPLACE_DIM = "replace_dim"
    ADD_DIM = "add_dim"
    REMOVE_DIM = "remove_dim"
    REPLACE_TIME = "replace_time"
    REPLACE_COMP = "replace_comp"
    RESET = "reset"
    CORRECT = "correct"  # 纠错/回退
    INHERIT = "inherit"


FOLLOWUP_ACTION_KEYWORDS: Dict[str, List[str]] = {
    "REPLACE_METRIC": ["换成", "改成", "换为", "改为", "换做", "调整为", "改成用", "换成用", "改算", "算算"],
    "ADD_METRIC": ["加上", "再加", "还有", "加个", "一并", "加一个", "顺便", "增加", "加上去", "添加", "加一下", "再加上", "加进去", "顺带加", "也看看", "也看下", "带上", "一起看"],
    "REMOVE_METRIC": ["去掉", "去除", "移除", "删除", "删掉", "不要", "剔除", "排除", "别要", "去掉这个", "去掉那个", "不要了", "不用了"],
    "REPLACE_DIM": ["换成按", "改成按", "改为按", "换为按", "改成以", "换为以", "改按", "按"],
    "REMOVE_DIM": ["不看", "不按", "别按", "去掉按", "别用", "不用"],
    "REPLACE_COMP": ["环比", "同比", "趋势"],
    "REPLACE_TIME": ["看看上月", "看看上周", "看看去年", "看看本月", "看看今年", "换到本月", "上月呢", "上月吧", "去年呢", "去年吧", "换上月", "换去年", "看上月", "看去年", "本周呢", "上周呢", "上季度"],
    "RESET": ["重新来", "重来", "换一个", "重新", "算了", "换个话题"],
}

# 纠错关键词（最高优先级）
_CORRECTION_KEYWORDS = [
    "不对", "错了", "不是这个", "搞错了",
    "不对不对", "重算",
]

# 时间纠错模式（纠错 + 时间词组合）
_TIME_CORRECTION_PATTERNS = [
    (r"换上月", "上月"),
    (r"换成上月", "上月"),
    (r"改成上月", "上月"),
    (r"换去年", "去年"),
    (r"换成去年", "去年"),
    (r"改成去年", "去年"),
    (r"换本月", "本月"),
    (r"换成本月", "本月"),
    (r"改成本月", "本月"),
]

# "按XX看" 模式需要正则匹配，不在关键词列表中
_REPLACE_DIM_PATTERN = re.compile(r"按.{1,6}看")
_REMOVE_DIM_PATTERN = re.compile(r"不看.{1,6}了")
# "XX呢" 模式中，XX是指标名/时间词
_SHORT_TEXT_METRIC_PATTERN = re.compile(r"^(.+?)呢[？?]?$")

# 本地模型实体类型 → MQLSchema 维度类型 映射
ENTITY_TYPE_TO_DIM_COLUMN = {
    'DIM': 'DIM',           # 通用维度类型
    'DIM_VALUE': 'DIM_VALUE',  # 维度值
    'SKU_VALUE': 'SKU',     # SKU 编码
    'ASIN_VALUE': 'ASIN',   # ASIN 编码
}

# 时间表达式映射（简单场景用，复杂场景交给 LLM）
TIME_EXPRESSION_MAP = {
    # 日期
    '今日': '今日',
    '昨日': '昨日',
    '前日': '前日',
    '前天': '前日',
    '明天': '明日',
    '明日': '明日',
    '后天': '后天',
    # 周
    '本周': '本周',
    '上周': '上周',
    '上上周': '上上周',
    '下周': '下周',
    '下下周': '下下周',
    # 月
    '本月': '本月',
    '上月': '上月',
    '上个月': '上月',
    '上上月': '上上月',
    '上上个月': '上上月',
    '下月': '下月',
    '下下月': '下下月',
    # 季度
    '本季度': '本季度',
    '上季度': '上季度',
    '下季度': '下季度',
    'Q1': 'Q1',
    'Q2': 'Q2',
    'Q3': 'Q3',
    'Q4': 'Q4',
    '一季度': '一季度',
    '二季度': '二季度',
    '三季度': '三季度',
    '四季度': '四季度',
    # 年
    '本年': '本年',
    '今年': '本年',
    '去年': '去年',
    '明年': '明年',
    '前年': '前年',
    '后年': '后年',
    # 滚动窗口（近N天、近N个月等由 TimeParser 处理）
    # 此处仅作快速匹配备用
}

# 下钻类型 → 中文语义标签（用于显示和 LLM 输入）
DRILLDOWN_LABELS = {
    "sales": "销售经营分析",
    "ad": "广告投放分析",
    "inventory": "库存供应链分析",
    "cost": "成本毛利分析",
}


class IntentRouter:
    """
    意图路由智能体

    使用本地 Joint BERT 模型做精准匹配，匹配成功则跳过 LLM，
    匹配失败则使用 LLM 兜底识别。
    """

    # 排名追问的常用维度选项（中文标签 → 英文类型）
    RANKING_DIMENSION_OPTIONS = [
        {"label": "按平台", "value": "PLATFORM"},
        {"label": "按店铺", "value": "SHOP"},
        {"label": "按渠道", "value": "CHANNEL"},
        {"label": "按品类", "value": "GROUP_3"},
        {"label": "按品牌", "value": "BRAND"},
        {"label": "按国家", "value": "COUNTRY"},
        {"label": "按产品线", "value": "PRODUCT_LINE"},
    ]

    def __init__(self):
        self._prompt_manager = get_prompt_manager()
        self._llm_engine = get_llm_engine()
        self._dimension_type_mappings = None
        self._local_model = None  # 本地模型延迟加载
        self._dimension_service = None  # 维度服务延迟加载
        self._semantic_service = None  # 语义快照服务延迟加载

    def _get_semantic_service(self):
        """延迟加载语义快照服务（单例，从内存快照读取，不发 HTTP）"""
        if self._semantic_service is None:
            from ai.services.semantic_snapshot_service import get_semantic_snapshot_service
            self._semantic_service = get_semantic_snapshot_service()
        return self._semantic_service

    def _get_dimension_service(self):
        """延迟加载维度服务"""
        if self._dimension_service is None:
            try:
                from ai.services.dimension_service import DimensionService
                self._dimension_service = DimensionService()
                logger.info("[IntentRouter] DimensionService 加载成功")
            except Exception as e:
                logger.warning(f"[IntentRouter] DimensionService 加载失败: {e}")
                self._dimension_service = None
        return self._dimension_service

    def _get_local_model(self):
        """延迟加载本地模型"""
        if self._local_model is None:
            try:
                from .local_intent_model import get_local_intent_model
                self._local_model = get_local_intent_model()
                logger.warning(f"[IntentRouter] ★★★ 本地模型加载成功, model_path={getattr(self._local_model, 'model_path', 'unknown')}")
            except Exception as e:
                logger.warning(f"[IntentRouter] 本地模型加载失败: {e}")
                self._local_model = None
        return self._local_model

    def _load_dimension_mappings(self):
        """从 API 加载维度类型映射"""
        if self._dimension_type_mappings is None:
            try:
                from ai.client.metric_client import MetricClient
                client = MetricClient()
                # 优先使用 dimension_configs（包含业务维度配置）
                configs = client.get_dimension_configs()
                if configs:
                    self._dimension_type_mappings = configs
                    logger.info(f"[IntentRouter] 从 dimension_configs 加载了 {len(configs)} 个维度配置")
                else:
                    # 回退到 dimension_type_mappings
                    self._dimension_type_mappings = client.get_dimension_type_mappings()
                    logger.info(f"[IntentRouter] 从 dimension_type_mappings 加载了 {len(self._dimension_type_mappings)} 个维度类型映射")
            except Exception as e:
                logger.warning(f"[IntentRouter] 加载维度映射失败: {e}")
                self._dimension_type_mappings = []

    def _get_ranking_dimension_options(self) -> List[Dict[str, str]]:
        """获取排名追问的维度选项（从配置动态加载）"""
        # ========== 使用统一语义层获取维度选项 ==========
        try:
            from ai.services.semantic_layer import get_semantic_layer_service
            from ai.services.semantic_layer.api import EnrichStage, ParseResult

            semantic_layer = get_semantic_layer_service()
            empty_parse_result = ParseResult(intent="unknown", confidence=0.0)
            enrich_result = semantic_layer.enrich(empty_parse_result, stage=EnrichStage.INTENT_ROUTER)

            if enrich_result.ranking_dimension_options:
                logger.info(f"[IntentRouter] 从语义层获取排名维度选项: {enrich_result.ranking_dimension_options}")
                return enrich_result.ranking_dimension_options
        except Exception as e:
            logger.warning(f"[IntentRouter] 语义层获取维度选项失败: {e}")

        # 最终回退到默认选项
        return self.RANKING_DIMENSION_OPTIONS

    async def route(self, question: str, inherited_mql: Optional[MQLSchema] = None,
                    use_semantic_layer: bool = False) -> Dict[str, Any]:
        """
        路由用户问题

        Args:
            question: 用户问题
            inherited_mql: 继承的 MQL（用于多轮对话）
            use_semantic_layer: 是否使用独立语义层（默认 False）

        Returns:
            {
                "mql": MQLSchema,
                "needs_clarification": bool,
                "clarification_message": str,
            }
        """
        logger.info(f"[IntentRouter] 路由问题: {question[:50]}..., use_semantic_layer={use_semantic_layer}")

        # 0. 下钻特殊处理：识别 __DRILLDOWN__:xxx__ 格式
        if question.startswith("__DRILLDOWN__:"):
            return self._handle_drilldown(question, inherited_mql)

        # 1. 寒暄处理
        if self._is_greeting(question):
            return self._handle_greeting()

        # 2. 简短追问处理（仅当有继承上下文时）
        if inherited_mql and self._is_short_followup(question):
            return await self._handle_followup(question, inherited_mql)

        # 3. 独立语义层（如果启用）
        if use_semantic_layer:
            return await self._semantic_layer_intent_recognition(question, inherited_mql)

        # 4. 本地模型预识别（精准匹配 + LLM 兜底）
        return await self._local_then_llm_intent_recognition(question, inherited_mql)

    async def _semantic_layer_intent_recognition(self, question: str,
                                                 inherited_mql: Optional[MQLSchema]) -> Dict[str, Any]:
        """
        独立语义层意图识别

        使用语义层解析问题，然后复用 _build_mql_from_local 的丰富处理逻辑
        构建 MQL（维度解析、过滤器、多指标、指标增强等）。
        """
        try:
            from ai.services.semantic_layer.service import get_semantic_layer_service
            semantic_layer = get_semantic_layer_service()
            parse_result = semantic_layer.parse_query(question)

            # 未知意图 → 追问
            if parse_result.intent == "unknown":
                return {
                    "mql": None,
                    "needs_clarification": True,
                    "clarification_message": parse_result.error or "抱歉，我无法理解您的问题，请换一种问法。",
                    "clarification_options": [],
                    "source": "semantic_layer_failed",
                }

            # 将 ParseResult 转换为 _build_mql_from_local 期望的格式
            entities = []
            for ent in (parse_result.entities or []):
                entities.append({"text": ent.text, "type": ent.type, "start": ent.start, "end": ent.end})

            # 如果语义层没有提取到 METRIC 实体但有 metric_name，手动添加
            if parse_result.metric_name and not any(e['type'] == 'METRIC' for e in entities):
                entities.append({"text": parse_result.metric_name, "type": "METRIC", "start": 0, "end": 0})

            # 如果语义层没有提取到 TIME 实体但有 time_expr，手动添加
            if parse_result.time_expr and not any(e['type'] == 'TIME' for e in entities):
                entities.append({"text": parse_result.time_expr, "type": "TIME", "start": 0, "end": 0})

            # 如果维度列表有值但 entities 中没有 DIM/DIM_VALUE，补充
            for dim in (parse_result.dimensions or []):
                dim_type = dim.get("type", "")
                dim_value = dim.get("value", "")
                if dim_value and not any(e['type'] == 'DIM_VALUE' and e['text'] == dim_value for e in entities):
                    entities.append({"text": dim_value, "type": "DIM_VALUE", "start": 0, "end": 0})
                elif dim_type and not any(e['type'] == 'DIM' and e['text'] == dim_type for e in entities):
                    entities.append({"text": dim_type, "type": "DIM", "start": 0, "end": 0})

            local_result = {
                "intent": parse_result.intent,
                "confidence": parse_result.confidence,
                "entities": entities,
                "match_success": True,
                "local_only": True,
                "metric_code": parse_result.metric_code or "",
            }

            # 意图纠正：含"环比/同比+变化"关键词时应为 comparison 而非 trend
            intent_val = parse_result.intent
            if intent_val == "query_trend":
                if ("环比" in question or "同比" in question) and "变化" in question:
                    local_result["intent"] = "query_comparison"
                    logger.info(f"[IntentRouter] 意图纠正: query_trend → query_comparison (含环比/同比+变化)")

            logger.info(f"[IntentRouter] 语义层→本地MQL构建: intent={parse_result.intent}, "
                       f"entities={[f'{e['type']}:{e['text']}' for e in entities]}, "
                       f"method={parse_result.parse_method}")

            # 复用 _build_mql_from_local 的全部逻辑（维度解析、过滤器、多指标、聚合检测等）
            mql = self._build_mql_from_local(local_result, question)

            # ===== 语义层路径：检测同比/环比关键词（与本地模型路径一致） =====
            # "对比上月/上期" → 环比；"对比去年/同比" → 同比
            comparison_types = []
            if "环比" in question or "对比上月" in question or "对比上期" in question or "环比上月" in question or "环比上期" in question:
                comparison_types.append("环比")
            if "同比" in question or "对比去年" in question or "同比去年" in question or "同比上期" in question:
                comparison_types.append("同比")
            # "对比" 单独出现时默认环比
            if not comparison_types and ("对比" in question or "比较" in question):
                comparison_types.append("环比")
            if comparison_types:
                from ..schema import ComparisonSpec
                mql.comparison = ComparisonSpec(
                    enabled=True,
                    types=comparison_types,
                    compare_period_start="",
                    compare_period_end="",
                )
                if mql.intent.value not in ("query_comparison", "query_trend"):
                    mql.intent = MQLIntent.QUERY_COMPARISON
                logger.info(f"[IntentRouter] 语义层检测到对比关键词: {comparison_types}")

            # 泛指维度校验
            mql = self._validate_generic_dimensions(mql, question)
            clarification = self._check_generic_dimensions(mql, question)
            if clarification.get("is_generic"):
                return {
                    "mql": mql,
                    "needs_clarification": True,
                    "clarification_message": clarification.get("clarification_message", ""),
                    "clarification_options": clarification.get("clarification_options", []),
                    "source": "semantic_layer",
                    "original_question": question,
                }

            return {
                "mql": mql,
                "needs_clarification": False,
                "source": "semantic_layer",
                "drilldown_type": parse_result.drilldown_type,
            }

        except Exception as e:
            logger.error(f"[IntentRouter] 语义层解析异常: {e}，回退到本地模型+LLM")
            import traceback
            traceback.print_exc()
            return await self._local_then_llm_intent_recognition(question, inherited_mql)

    def _detect_followup_action(self, question: str, entities: Optional[Dict[str, Any]] = None) -> FollowupAction:
        """根据文本关键词 + 正则 + 实体类型检测追问动作类型

        优先级：RESET > REPLACE_DIM > REMOVE_DIM > REPLACE_COMP > REPLACE_TIME
                 > REPLACE_METRIC > ADD_METRIC > REMOVE_METRIC > INHERIT
        """
        entities = entities or {}

        # 0. CORRECT — 纠错（最高优先级）
        if any(kw in question for kw in _CORRECTION_KEYWORDS):
            return FollowupAction.CORRECT
        # 纠错+时间组合模式："换上月"、"换成去年"
        for pattern, _ in _TIME_CORRECTION_PATTERNS:
            if re.search(pattern, question):
                return FollowupAction.CORRECT

        # 1. RESET — 重置
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("RESET", []):
            if kw in question:
                return FollowupAction.RESET

        # 2. REPLACE_DIM — "换成按XX"、"改成按XX"、"按XX看"
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("REPLACE_DIM", []):
            if kw in question:
                return FollowupAction.REPLACE_DIM
        if _REPLACE_DIM_PATTERN.search(question):
            return FollowupAction.REPLACE_DIM

        # 3. REMOVE_DIM — "不看XX了"
        if _REMOVE_DIM_PATTERN.search(question):
            return FollowupAction.REMOVE_DIM

        # 4. REPLACE_COMP — 环比/同比（需在 REPLACE_TIME 之前，"环比呢"优先为对比）
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("REPLACE_COMP", []):
            if kw in question:
                return FollowupAction.REPLACE_COMP

        # 5. REPLACE_TIME — "看看上月"、"换到本月"
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("REPLACE_TIME", []):
            if kw in question:
                return FollowupAction.REPLACE_TIME

        # 6. "XX呢" 短文本模式：根据去掉"呢"后的内容判断
        m = _SHORT_TEXT_METRIC_PATTERN.match(question)
        if m:
            core = m.group(1)
            # 检查 core 是否是时间词
            if core in TIME_EXPRESSION_MAP or core in ["上月", "去年", "本月", "去年", "前年"]:
                return FollowupAction.REPLACE_TIME
            # 检查 core 是否是对比词（已在上面 REPLACE_COMP 处理了，这里兜底）
            if core in ["环比", "同比"]:
                return FollowupAction.REPLACE_COMP
            # 检查 core 是否是趋势词
            if core in ["趋势", "变化", "走势"]:
                return FollowupAction.REPLACE_COMP
            # 检查 core 是否能解析为指标名（语义快照 + 同义词）
            if self._resolve_metric_name(core):
                return FollowupAction.REPLACE_METRIC
            # 未知"XX呢"，走 INHERIT
            return FollowupAction.INHERIT

        # 7. ADD_METRIC — "加上XX"、"再加XX"
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("ADD_METRIC", []):
            if kw in question:
                return FollowupAction.ADD_METRIC

        # 8. REMOVE_METRIC — "去掉XX"、"不要XX"
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("REMOVE_METRIC", []):
            if kw in question:
                return FollowupAction.REMOVE_METRIC

        # 9. REPLACE_METRIC — "换成XX"、"改成XX"（排在 ADD/REMOVE 之后避免误判）
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("REPLACE_METRIC", []):
            if kw in question:
                return FollowupAction.REPLACE_METRIC

        # 9.5 短文本指标名：追问选项点击场景（如"访客数"、"销售额"）
        if len(question) <= 10 and self._resolve_metric_name(question):
            return FollowupAction.REPLACE_METRIC

        # 10. 默认 INHERIT
        return FollowupAction.INHERIT

    def _extract_metric_from_text(self, question: str) -> Optional[str]:
        """从文本中提取可能的指标名（用于纠错场景）"""
        # 去掉纠错关键词
        cleaned = question
        for kw in _CORRECTION_KEYWORDS:
            cleaned = cleaned.replace(kw, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        # 尝试语义快照匹配
        try:
            semantic_svc = self._get_semantic_service()
            result = semantic_svc.resolve_metric(cleaned)
            if result:
                return result.get("name") or result.get("display_name") or cleaned
        except Exception:
            pass
        # 如果清理后的文本像是一个指标名（>1 字且不是时间词），返回它
        if len(cleaned) >= 2 and cleaned not in TIME_EXPRESSION_MAP:
            return cleaned
        return None

    def _resolve_metric_name(self, candidate: str) -> Optional[Dict[str, Any]]:
        """解析指标名（语义快照优先 → MetricClient 兜底），纯内存查找"""
        if not candidate:
            return None
        # 1. 语义快照
        try:
            semantic_svc = self._get_semantic_service()
            result = semantic_svc.resolve_metric(candidate)
            if result:
                return result
        except Exception:
            pass
        # 2. 同义词 + MetricClient
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            info = client.get_metric_by_name(candidate)
            if info:
                return info
        except Exception:
            pass
        return None

    def _is_short_followup(self, question: str) -> bool:
        """判断是否为追问：语义快照实体检测 + 动作词 + 兜底关键词"""
        if question.strip() in ("？", "?"):
            return False

        # 1. 语义快照轻量实体检测（内存查找，不调 BERT）
        try:
            semantic_svc = self._get_semantic_service()
            detected_metric = semantic_svc.resolve_metric(question)
            if detected_metric:
                logger.info(f"[_is_short_followup] 语义快照命中指标: {detected_metric.get('name')}")
                return True
            detected_dim = semantic_svc.resolve_dimension(question)
            if detected_dim:
                logger.info(f"[_is_short_followup] 语义快照命中维度: {detected_dim}")
                return True
        except Exception:
            pass

        # 2. 动作词检测（结构化模式，覆盖换/加/去/对比/时间/重置）
        action = self._detect_followup_action(question)
        if action != FollowupAction.INHERIT:
            # REPLACE_COMP/REPLACE_TIME 类追问通常很短（"环比"、"看看环比"等）
            # 超过15字还带这些关键词的，基本是独立新问题
            # 例如 "智能云存储的2026-01-01 ~ 2026-05-05的查看各站点销售额环比变化"
            if len(question) > 15 and action in (FollowupAction.REPLACE_COMP, FollowupAction.REPLACE_TIME):
                logger.info(f"[_is_short_followup] 问题较长({len(question)}字)且含{action.value}动作词，视为新问题")
                return False
            # 含时间表达式 + 可解析指标名的较长文本，视为完整独立查询
            if len(question) > 8:
                has_time = any(t in question for t in ["上月", "本月", "上月", "近7天", "近30天", "去年", "本周", "上周", "本季度", "上季度", "今年", "前年"])
                if has_time and self._resolve_metric_name(question):
                    logger.info(f"[_is_short_followup] 完整查询（含时间+指标），不走追问: {question[:30]}")
                    return False
            return True

        # 3. 维度代码选择（前端追问选项回调）
        dimension_codes = {
            "FSITECODE", "FSITE", "PLATFORM", "FCHANNEL", "FBRANDS", "FPRODUCTLINE",
            "FADTYPE", "GROUP_1", "GROUP_2", "GROUP_3", "GROUP_4", "SKU", "ASIN",
            "FCOUNTRY", "REGION", "FDATE", "MONTHS", "WEEKS", "YEARS", "QUARTERS",
            "PRODUCT_STATUS", "PRODUCT_LEVEL", "MODEL", "PEOPLEGROUP", "ADSDIRECTOR",
            "PEOPLEGROUP_CHARGE", "PEOPLEGROUP_DIRECTOR",
        }
        if question.upper() in dimension_codes or question in dimension_codes:
            return True

        # 4. 兜底：短文本 + 语气助词
        if len(question) <= 5 and question.endswith(("呢", "啊", "哦", "吧")):
            return True

        return False

    def _is_greeting(self, question: str) -> bool:
        """判断是否为寒暄"""
        greeting_keywords = ["你好", "您好", "嗨", "hi", "hello", "早上好", "下午好", "晚上好", "hi", "hey"]
        return any(kw in question.lower() for kw in greeting_keywords)

    def _check_generic_dimensions(self, mql: MQLSchema, question: str = "") -> Dict[str, Any]:
        """检查是否有泛指维度需要追问

        Args:
            mql: MQLSchema
            question: 原始问题（用于检测问题中的泛指关键词）

        Returns:
            {
                "is_generic": bool,
                "generic_types": List[str],  # 泛指类型列表
                "default_dimension": str,     # 默认使用的维度
                "clarification_message": str, # 追问引导
                "clarification_options": List[Dict],  # 选项列表，每项含 replace_key
                "replace_key": str,  # 问题中需要替换的泛指关键词
            }
        """
        generic_types = {"CATEGORY", "品类", "类目", "商品类", "产品类"}
        brand_types = {"BRAND", "品牌"}
        # 品类问法映射：关键词 -> replace_key（问题中实际出现的词）
        category_keyword_map = {
            "品类": "品类", "各品类": "各品类",
            "类目": "类目", "各品类": "各品类",
            "商品类": "商品类", "产品类": "产品类",
        }
        brand_keyword_map = {
            "品牌": "品牌", "各品牌": "各品牌",
            "店铺": "店铺", "各店铺": "各店铺",
            "平台": "平台", "各平台": "各平台",
        }

        # ========== 优先检查问题原文是否包含泛指品类关键词 ==========
        # 即使 MQL 的 dimension type 设错了，只要问题里有泛指词就触发追问
        # 但要排除"一级品类"、"二级品类"等具体级别的情况
        if question:
            # 先检查是否出现了具体级别（一级品类/二级品类/三级品类）
            # 如果出现了具体级别，就不走泛指追问（让 MQL 正常解析）
            specific_levels = ["一级品类", "二级品类", "三级品类", "四级品类", "五级品类"]
            has_specific_level = any(level in question for level in specific_levels)

            if not has_specific_level:
                # 没有具体级别，检查泛指词
                for kw in ["各品类", "品类", "类目", "商品类", "产品类"]:
                    if kw in question:
                        # 发现泛指品类词，直接触发追问
                        return {
                            "is_generic": True,
                            "generic_types": ["品类"],
                            "default_dimension": "三级品类",
                            "clarification_message": "请问您想按哪个品类级别分析？",
                            "clarification_options": [
                                {"label": "一级品类", "value": "一级品类", "replace_key": kw},
                                {"label": "二级品类", "value": "二级品类", "replace_key": kw},
                                {"label": "三级品类", "value": "三级品类", "replace_key": kw},
                            ],
                            "replace_key": kw,
                        }
        # ============================================================

        generic_dims = []
        for dim in mql.dimensions:
            dim_type_upper = dim.type.upper() if dim.type else ""
            if dim_type_upper in generic_types:
                generic_dims.append(dim.type)
            elif dim_type_upper in brand_types and not dim.value:
                # 品牌没有具体值时也视为泛指
                generic_dims.append(dim.type)

        if not generic_dims:
            return {"is_generic": False}

        # 查找第一个泛指维度的配置
        first_generic = generic_dims[0]

        # 检测问题中实际出现的泛指关键词（用于前端替换）
        detected_keyword = ""
        if question:
            if first_generic in generic_types:
                # 优先匹配更长的关键词
                for kw in ["各品类", "品类", "类目", "商品类", "产品类"]:
                    if kw in question:
                        detected_keyword = kw
                        break
            elif first_generic in brand_types:
                for kw in ["各品牌", "品牌", "各店铺", "店铺", "各平台", "平台"]:
                    if kw in question:
                        detected_keyword = kw
                        break

        # 根据泛指类型返回对应的选项
        if first_generic in generic_types:
            return {
                "is_generic": True,
                "generic_types": generic_dims,
                "default_dimension": "三级品类",
                "clarification_message": "请问您想按哪个品类级别分析？",
                "clarification_options": [
                    {"label": "一级品类", "value": "一级品类", "replace_key": detected_keyword or "品类"},
                    {"label": "二级品类", "value": "二级品类", "replace_key": detected_keyword or "品类"},
                    {"label": "三级品类", "value": "三级品类", "replace_key": detected_keyword or "品类"},
                ],
                "replace_key": detected_keyword or "品类",
            }
        elif first_generic in brand_types:
            return {
                "is_generic": True,
                "generic_types": generic_dims,
                "default_dimension": "品牌",
                "clarification_message": "请问您想按什么维度分析？",
                "clarification_options": [
                    {"label": "按品牌", "value": "品牌", "replace_key": detected_keyword or "品牌"},
                    {"label": "按店铺", "value": "店铺", "replace_key": detected_keyword or "店铺"},
                    {"label": "按平台", "value": "平台", "replace_key": detected_keyword or "平台"},
                ],
                "replace_key": detected_keyword or "品牌",
            }
        else:
            return {
                "is_generic": True,
                "generic_types": generic_dims,
                "default_dimension": generic_dims[0],
                "clarification_message": f"请问您想按哪个维度分析？（{', '.join(generic_dims)}）",
                "clarification_options": [{"label": d, "value": d, "replace_key": d} for d in generic_dims],
                "replace_key": generic_dims[0] if generic_dims else "",
            }

    def _validate_generic_dimensions(self, mql: MQLSchema, question: str) -> MQLSchema:
        """
        校验 MQL 中的维度值是否为具体维度值。

        核心逻辑：
        1. 从问题中提取候选维度值（时间词前、品类词前后）
        2. 查 dim_value_mapping 确认候选是否为具体维度值
        3. 精确匹配到唯一结果 → 纠正 dimension type
        4. 候选词模糊（< 3字符）且匹配到多个结果 → 不纠正，让追问处理
        5. 候选词是已知维度类型（如"三级品类"）→ 直接设置 type，不追问

        注意：此方法处理所有维度类型，不仅限于泛指类型。
        当 LLM 返回泛指类型（如 PRODUCT_LINE）但实际是具体值（如"智能云存储"）时，
        需要通过此方法纠正。
        """
        generic_types = {"CATEGORY", "品类", "类目", "商品类", "产品类"}

        dim_service = self._get_dimension_service()
        semantic_svc = self._get_semantic_service()

        # 从问题中提取所有候选维度值（包含维度类型，已在 _extract_dimension_candidates 中从维表动态获取）
        candidates = self._extract_dimension_candidates(question, "", dim_service, semantic_svc)

        logger.info(f"[_validate_generic_dimensions] 提取到的候选维度值: {candidates}")

        # 泛指关键词：这些词应触发追问（一级/二级/三级），不应在这里自动解析
        generic_keywords = {"品类", "类目", "商品类", "产品类", "品牌", "店铺", "平台", "渠道"}
        specific_levels = ["一级品类", "二级品类", "三级品类", "四级品类", "一级类目", "二级类目", "三级类目"]
        has_specific_level = any(level in question for level in specific_levels)

        for candidate in candidates:
            # 跳过泛指关键词（除非问题中包含具体级别）
            if candidate in generic_keywords and not has_specific_level:
                logger.info(f"[_validate_generic_dimensions] 跳过泛指候选 '{candidate}'，交给追问引擎处理")
                continue

            # ========== 优先用语义快照服务解析维度类型 ==========
            # 已知维度类型：一级品类/二级品类/三级品类/四级品类/品牌/平台/店铺等
            if semantic_svc:
                col_from_type = semantic_svc.find_dimension_column_by_type(candidate)
                if col_from_type:
                    logger.info(f"[_validate_generic_dimensions] 快照解析候选 '{candidate}' 是已知维度类型 -> column={col_from_type}，直接设置")
                    for dim in mql.dimensions:
                        if not dim.column or not dim.type:
                            dim.type = candidate
                            dim.column = col_from_type
                    return mql
            # 快照解析失败，继续用 dim_service
            if dim_service:
                col_from_type = dim_service.find_column_by_type(candidate)
                if col_from_type:
                    logger.info(f"[_validate_generic_dimensions] 候选 '{candidate}' 是已知维度类型 -> column={col_from_type}，直接设置")
                    for dim in mql.dimensions:
                        if not dim.column or not dim.type:
                            dim.type = candidate
                            dim.column = col_from_type
                    return mql
            # ============================================================

            # ========== 优先用语义快照服务解析维度值 ==========
            resolved = semantic_svc.resolve_dimension(candidate) if semantic_svc else None
            if resolved:
                correct_type = resolved.get("dimension_type")
                correct_value = resolved.get("dimension_value")
                correct_column = resolved.get("column_name")
                is_generic = resolved.get("is_generic", False)
                if not is_generic and correct_column:
                    logger.info(f"[_validate_generic_dimensions] 快照纠正维度: '{candidate}' -> type={correct_type}, column={correct_column}, value={correct_value}")
                    for dim in mql.dimensions:
                        dim_type_upper = dim.type.upper() if dim.type else ""
                        if dim_type_upper in generic_types or (dim.type and dim.type != correct_type and dim.type != correct_column):
                            dim.type = correct_type
                            dim.column = correct_column
                            dim.value = correct_value
                    return mql
            # ============================================================

            # 查 dim_value_mapping（limit=10 返回多个结果用于判断模糊度）
            search_results = dim_service.search_by_value(candidate, limit=10) if dim_service else []
            if not search_results:
                logger.info(f"[_validate_generic_dimensions] 候选 '{candidate}' 在 dim_value_mapping 中无结果")
                continue

            logger.info(f"[_validate_generic_dimensions] 候选 '{candidate}' 匹配到 {len(search_results)} 个结果: {search_results}")

            # 精确匹配到唯一结果 → 纠正为具体值
            exact_matches = [r for r in search_results
                            if r.get("dimension_value") == candidate]
            if len(exact_matches) == 1:
                dim_info = exact_matches[0]
                correct_type = dim_info.get("dimension_type")  # 如 "二级品类"
                correct_value = dim_info.get("dimension_value")  # 如 "智能云存储"
                correct_column = dim_info.get("column_name")  # 如 "GROUP_2"

                # 更新所有匹配到的维度
                for dim in mql.dimensions:
                    dim_type_upper = dim.type.upper() if dim.type else ""
                    # 如果当前维度类型是泛指类型，或者类型与正确类型不匹配，则纠正
                    if dim_type_upper in generic_types or (dim.type and dim.type != correct_type and dim.type != correct_column):
                        dim.type = correct_type
                        dim.column = correct_column
                        dim.value = correct_value
                        logger.info(f"[_validate_generic_dimensions] 纠正维度: {dim_type_upper} -> {correct_type}({correct_column}), value={correct_value}")
                break

            # 候选词太模糊（< 3字符）且匹配到多个结果 → 不纠正，走追问
            if len(candidate) < 3 and len(search_results) > 1:
                logger.info(f"[_validate_generic_dimensions] 候选词 '{candidate}' 太模糊，匹配到 {len(search_results)} 个结果，跳过纠正")
                continue

            # 匹配到明确的具体值（非模糊）
            if len(search_results) == 1:
                dim_info = search_results[0]
                correct_type = dim_info.get("dimension_type")
                correct_value = dim_info.get("dimension_value")
                correct_column = dim_info.get("column_name")

                for dim in mql.dimensions:
                    dim_type_upper = dim.type.upper() if dim.type else ""
                    # 纠正所有维度，不管当前类型是什么
                    if dim_type_upper in generic_types or dim.value is None:
                        dim.type = correct_type
                        dim.column = correct_column
                        dim.value = correct_value
                        logger.info(f"[_validate_generic_dimensions] 纠正维度(单匹配): {dim_type_upper} -> {correct_type}({correct_column}), value={correct_value}")
                break

        return mql

    def _extract_dimension_candidates(self, question: str, dim_type: str, dim_service, semantic_svc=None) -> List[str]:
        """
        从问题中提取候选维度值。
        例如："智能云存储今年业绩" + dim_type="品类"
        → 提取 "智能云存储"（去掉 "品类" 相关词）

        同时也从维表动态获取所有维度类型，检查问题中是否包含。
        """
        import re
        candidates = []

        # 0. 从维表/语义快照获取所有维度类型，检查问题中是否包含（这是动态的，不是硬编码）
        # 优先用语义快照服务
        all_types = []
        if semantic_svc:
            all_types = semantic_svc.get_all_types()
        if not all_types and dim_service:
            all_types = dim_service.get_all_types()
        # 收集已知维度类型字符串，用于后续过滤
        known_type_strs = set()
        for type_info in all_types:
            dim_type_str = type_info.get("dimension_type", "")
            if dim_type_str:
                known_type_strs.add(dim_type_str)
                if dim_type_str in question and dim_type_str not in candidates:
                    candidates.append(dim_type_str)

        # 1. 检查 "X的品类/Y" 模式：X 是维度值
        category_words = ['品类', '类目', '商品类', '产品类']
        for cat_word in category_words:
            pattern = rf"(.+?)的{re.escape(cat_word)}"
            match = re.search(pattern, question)
            if match:
                val = match.group(1).strip()
                if len(val) >= 2:
                    candidates.append(val)

        # 2. 检查 "智能云存储品类" 模式：X 在品类词前面
        for cat_word in category_words:
            pattern = rf"(.+?){re.escape(cat_word)}"
            for m in re.finditer(pattern, question):
                val = m.group(1).strip()
                if len(val) >= 2 and val not in candidates:
                    candidates.append(val)

        # 3. 检查时间词前面的词作为候选（去掉时间词后）
        # 但只取紧邻时间词的最后一个有意义的词，而不是整个前缀
        time_words = ['今天', '昨天', '今年', '去年', '本周', '上周', '本月', '上月', '近7天', '近30天', '近3个月']
        for t in time_words:
            if t in question:
                idx = question.find(t)
                before = question[:idx].strip()
                # 从 before 中提取最后一个词（而不是整个前缀）
                # 用已知维度类型和维度值来匹配，而不是盲目切词
                # 先检查 before 是否以已知维度类型结尾
                matched = False
                for kt in sorted(known_type_strs, key=len, reverse=True):
                    if before.endswith(kt) and kt not in candidates:
                        candidates.append(kt)
                        matched = True
                        break
                if not matched and len(before) >= 2 and before not in candidates:
                    # 只在 before 是短词（<=4字）且不含功能词时才加入
                    # 功能词（按/看/的/在/从）开头的短词大概率不是维度值
                    if len(before) <= 4 and not re.match(r'^[按看在从的把被]', before):
                        candidates.append(before)

        return candidates

    async def _handle_followup(self, question: str, inherited_mql: Optional[MQLSchema]) -> Dict[str, Any]:
        """处理追问：动作词驱动 + 合并策略"""
        if inherited_mql:
            _metric_name = inherited_mql.metric.name if inherited_mql and inherited_mql.metric else None
            _dims = [(d.type, d.value) for d in inherited_mql.dimensions] if inherited_mql and inherited_mql.dimensions else []
            logger.info(f"[IntentRouter] 处理追问: inherited_mql.metric={_metric_name}, inherited_mql.dimensions={_dims}")
        else:
            logger.info("[IntentRouter] 处理追问: inherited_mql is None")

        if not inherited_mql:
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": "请问您想查询什么指标？",
                "source": "followup",
            }

        # 构建 base MQL（全字段继承）
        mql = self._build_followup_mql(inherited_mql, question)

        # 检测追问动作类型
        action = self._detect_followup_action(question)
        logger.info(f"[IntentRouter] 追问动作: {action.value}, question={question}")

        # === 根据动作类型执行合并策略 ===

        if action == FollowupAction.CORRECT:
            return self._handle_correction_followup(question, mql, inherited_mql)

        if action == FollowupAction.RESET:
            return self._handle_reset_followup(question)

        if action == FollowupAction.REPLACE_DIM:
            dim_result = self._handle_dimension_selection_followup(question, mql)
            if dim_result:
                # 检查泛指维度
                mql = dim_result.get("mql", mql)
                clarification = self._check_generic_dimensions(mql, question)
                if clarification.get("is_generic"):
                    return {
                        "mql": mql,
                        "needs_clarification": True,
                        "clarification_message": clarification.get("clarification_message", ""),
                        "clarification_options": clarification.get("clarification_options", []),
                        "source": "followup",
                        "original_question": question,
                    }
                return dim_result
            # "按XX看" 未匹配到维度代码，回退到 REPLACE_METRIC
            swap_result = self._handle_replace_metric_followup(question, mql)
            if swap_result:
                return swap_result
            # 维度和指标都未匹配 → 尝试从问题中提取维度并走语义层
            logger.info(f"[IntentRouter] REPLACE_DIM 回退失败，尝试从问题中提取维度: {question}")
            extracted_dim = self._try_extract_dim_from_middle(question, mql)
            if extracted_dim:
                return extracted_dim
            # 最终兜底：继承上轮意图
            mql.intent = inherited_mql.intent
            return {"mql": mql, "needs_clarification": False, "source": "followup"}

        if action == FollowupAction.REMOVE_DIM:
            removal_result = self._handle_removal_followup(question, mql, inherited_mql, ["不看"])
            if removal_result:
                return removal_result

        if action == FollowupAction.REPLACE_COMP:
            return self._handle_comparison_followup(question, mql, inherited_mql)

        if action == FollowupAction.REPLACE_TIME:
            return self._handle_time_followup(question, mql)

        if action == FollowupAction.REPLACE_METRIC:
            swap_result = self._handle_replace_metric_followup(question, mql)
            if swap_result:
                return swap_result
            # "换成XX" 中 XX 无法解析为指标 → 可能是新问题
            logger.info(f"[IntentRouter] 换指标追问中指标解析失败，回退到继承")
            mql.intent = inherited_mql.intent
            return {"mql": mql, "needs_clarification": False, "source": "followup"}

        if action == FollowupAction.ADD_METRIC:
            add_keywords = FOLLOWUP_ACTION_KEYWORDS.get("ADD_METRIC", [])
            addition_result = self._handle_addition_followup(question, mql, inherited_mql, add_keywords)
            if addition_result:
                return addition_result

        if action == FollowupAction.REMOVE_METRIC:
            remove_keywords = FOLLOWUP_ACTION_KEYWORDS.get("REMOVE_METRIC", [])
            removal_result = self._handle_removal_followup(question, mql, inherited_mql, remove_keywords)
            if removal_result:
                return removal_result

        # INHERIT：检查是否是独立新问题
        if self._is_new_question(question, inherited_mql):
            logger.info(f"[IntentRouter] 检测到新问题（{question[:20]}...），清除继承指标")
            # 清除继承的追加指标，避免旧指标污染新问题
            mql.metrics = []
            return {"mql": mql, "needs_clarification": False, "source": "llm"}

        # 兜底继承上轮意图
        mql.intent = inherited_mql.intent
        _debug_info = f"[DEBUG: action={action.value}, inherited_metric={inherited_mql.metric.name if inherited_mql and inherited_mql.metric else None}, inherited_dims={[(d.type, d.value) for d in inherited_mql.dimensions] if inherited_mql and inherited_mql.dimensions else []}]"
        mql.resolved_question = f"{_debug_info} | question={question}"
        return {"mql": mql, "needs_clarification": False, "source": "followup"}

    def _handle_replace_metric_followup(self, question: str, mql: MQLSchema) -> Optional[Dict[str, Any]]:
        """换指标：替换 mql.metric，清空 mql.metrics，继承维度/时间/对比"""
        # 从文本中提取新指标名（去掉动作词）
        candidate = question
        for kw in FOLLOWUP_ACTION_KEYWORDS.get("REPLACE_METRIC", []):
            candidate = candidate.replace(kw, " ")
        candidate = candidate.strip()
        # "XX呢" 模式
        m = _SHORT_TEXT_METRIC_PATTERN.match(question)
        if m:
            candidate = m.group(1)

        if not candidate:
            return None

        # 解析新指标（语义快照 → 同义词 → MetricClient）
        metric_info = self._resolve_metric_name(candidate)
        if not metric_info:
            logger.info(f"[_handle_replace_metric_followup] 无法解析指标: {candidate}")
            return None

        from ..schema import MQLMetric
        mql.metric = MQLMetric(
            code=metric_info.get("metric_code") or metric_info.get("code", ""),
            name=metric_info.get("name", candidate),
            table=metric_info.get("starrocks_table") or metric_info.get("table", ""),
            field=metric_info.get("starrocks_field") or metric_info.get("field", ""),
            unit=metric_info.get("unit", ""),
            starrocks_sql=metric_info.get("starrocks_sql", ""),
        )
        mql.metrics = []
        logger.info(f"[_handle_replace_metric_followup] 换指标: {candidate} → {mql.metric.name} ({mql.metric.code})")

        # 追问中可能同时切换维度，从维度配置表动态获取维度关键词
        from ai.services.dimension_service import DimensionService
        dim_service = DimensionService()
        dim_types = dim_service.get_all_types(use_cache=True)  # [{column_name, dimension_type}, ...]
        if dim_types:
            for dim_info in dim_types:
                dim_name = dim_info.get("dimension_type", "")
                dim_col = dim_info.get("column_name", "")
                if dim_name and dim_col and dim_name in question:
                    from ..schema import MQLDimension
                    mql.dimensions = [MQLDimension(type=dim_name, column=dim_col)]
                    logger.info(f"[_handle_replace_metric_followup] 追问检测到维度变更: {dim_name} -> {dim_col}")
                    break

        # 追问中可能同时切换时间，检测时间表达式并解析
        time_detected = None
        for time_kw in sorted(TIME_EXPRESSION_MAP.keys(), key=len, reverse=True):
            if time_kw in question:
                time_detected = time_kw
                break
        if not time_detected:
            # 扩展匹配："上个月"、"近N天" 等不在 MAP 中的常见时间词
            import re
            extended_match = re.search(r'(上个月|前一个月|上上个月|近\d+天|近\d+周|近\d+个月|最近\d+天)', question)
            if extended_match:
                time_detected = extended_match.group(1)
        if time_detected:
            try:
                parsed = TimeParser().parse(time_detected)
                if parsed:
                    from ..schema import TimeRange, TimeType
                    mql.time = TimeRange(
                        type=TimeType(parsed.get("type", "relative")),
                        original=time_detected,
                        start=parsed.get("start", ""),
                        end=parsed.get("end", ""),
                    )
                    mql.comparison = None
                    logger.info(f"[_handle_replace_metric_followup] 追问检测到时间变更: {time_detected} → {mql.time.start} ~ {mql.time.end}")
            except Exception as e:
                logger.warning(f"[_handle_replace_metric_followup] 时间解析失败: {e}")

        return {"mql": mql, "needs_clarification": False, "source": "followup_replace_metric"}

    def _handle_comparison_followup(self, question: str, mql: MQLSchema, inherited_mql: MQLSchema) -> Dict[str, Any]:
        """对比/趋势类追问：环比/同比/趋势"""
        from ..schema import ComparisonSpec
        comp_types = []
        if "环比" in question:
            comp_types.append("环比")
        if "同比" in question:
            comp_types.append("同比")

        # 趋势类
        if "趋势" in question:
            mql.intent = MQLIntent.QUERY_TREND
            logger.info(f"[_handle_comparison_followup] 趋势追问")
            return {"mql": mql, "needs_clarification": False, "source": "followup_comp"}

        mql.intent = MQLIntent.QUERY_COMPARISON
        mql.comparison = ComparisonSpec(
            enabled=True,
            types=comp_types or ["环比"],
        )
        logger.info(f"[_handle_comparison_followup] 对比追问: {comp_types}")
        return {"mql": mql, "needs_clarification": False, "source": "followup_comp"}

    def _handle_time_followup(self, question: str, mql: MQLSchema) -> Dict[str, Any]:
        """时间类追问：上月呢、看看去年"""
        # 提取时间词
        time_word = None
        m = _SHORT_TEXT_METRIC_PATTERN.match(question)
        if m:
            time_word = m.group(1)
        if not time_word:
            for kw in ["看看", "换到", "换成"]:
                if kw in question:
                    time_word = question.replace(kw, "").strip()
                    break
        if not time_word:
            time_word = question.strip()

        # 用 TimeParser 解析
        try:
            parsed = TimeParser().parse(time_word)
            if parsed:
                mql.time = TimeRange(
                    type=TimeType(parsed.get("type", "relative")),
                    original=time_word,
                    start=parsed.get("start", ""),
                    end=parsed.get("end", ""),
                )
                # 换时间清空对比
                mql.comparison = None
                logger.info(f"[_handle_time_followup] 时间追问: {time_word} → {mql.time.start} ~ {mql.time.end}")
        except Exception as e:
            logger.warning(f"[_handle_time_followup] TimeParser 解析失败: {e}")
            mql.time = TimeRange(type=TimeType.RELATIVE, original=time_word)

        return {"mql": mql, "needs_clarification": False, "source": "followup_time"}

    def _handle_reset_followup(self, question: str) -> Dict[str, Any]:
        """重置追问：清空上下文"""
        logger.info(f"[_handle_reset_followup] 重置上下文: {question}")
        return {
            "mql": None,
            "needs_clarification": True,
            "clarification_message": "好的，请问您想查询什么？",
            "source": "followup_reset",
        }

    def _handle_correction_followup(self, question: str, mql: MQLSchema, inherited_mql: MQLSchema) -> Dict[str, Any]:
        """处理纠错追问：分析用户想修正什么，执行回退/修正"""
        logger.info(f"[_handle_correction_followup] 纠错追问: {question}")

        # 1. 时间纠错："不对，换上月" → 替换时间
        time_correction = self._detect_time_correction(question)
        if time_correction:
            try:
                from ai.engine.time_parser import TimeParser
                parser = TimeParser()
                parsed_time = parser.parse(time_correction)
                if parsed_time:
                    from ..schema import TimeRange, TimeType
                    mql.time = TimeRange(
                        type=TimeType(parsed_time.get("type", "relative")),
                        start=parsed_time.get("start", ""),
                        end=parsed_time.get("end", ""),
                        original=time_correction,
                    )
                    mql.comparison = None
                    logger.info(f"[_handle_correction_followup] 时间纠错: {time_correction} → {mql.time.start}~{mql.time.end}")
                    return {"mql": mql, "source": "followup_correction"}
            except Exception as e:
                logger.warning(f"[_handle_correction_followup] 时间解析失败: {e}")

        # 2. 指标纠错："不对，应该是利润" → 替换指标
        metric_correction = self._extract_metric_from_text(question)
        if metric_correction:
            resolved = self._resolve_metric_name(metric_correction)
            if resolved:
                mql.metric = resolved
                mql.metrics = []
                logger.info(f"[_handle_correction_followup] 指标纠错: {metric_correction} → {resolved.name}")
                return {"mql": mql, "source": "followup_correction"}

        # 3. 纯否定（"不对"、"错了"）→ 追问让用户说明要什么
        logger.info(f"[_handle_correction_followup] 纯否定纠错，触发追问")
        return {
            "mql": None,
            "needs_clarification": True,
            "clarification_message": "抱歉理解有误，请问您希望查询什么？可以更具体描述一下。",
            "source": "followup_correction",
        }

    def _detect_time_correction(self, question: str) -> Optional[str]:
        """从纠错文本中提取新的时间表达式"""
        # 检查纠错+时间组合模式
        for pattern, time_expr in _TIME_CORRECTION_PATTERNS:
            if re.search(pattern, question):
                return time_expr
        # 检查文本中是否有已知时间词
        for time_word in ["上月", "去年", "本月", "本周", "上周", "去年", "前年", "上上月"]:
            if time_word in question:
                return time_word
        return None

    def _is_new_question(self, question: str, inherited_mql: Optional["MQLSchema"] = None) -> bool:
        """判断是否为独立新问题（不应继承上轮指标）"""
        # 规则1：包含完整指标名 + 疑问词 → 新问题
        has_question_word = any(q in question for q in ["多少", "是多少", "怎么样", "如何", "为什么", "是什么"])
        if has_question_word:
            metric_info = self._resolve_metric_name(question)
            if metric_info:
                return True

        # 规则2：长文本 + 无动作词 + 有疑问词 → 可能新问题
        if len(question) > 10 and has_question_word:
            action = self._detect_followup_action(question)
            if action == FollowupAction.INHERIT:
                return True

        # 规则3：问题中解析出的指标与继承指标不同 → 新问题
        # 例如继承指标是"毛利"，但问题中明确提到"销售额"
        if inherited_mql and inherited_mql.metric:
            metric_info = self._resolve_metric_name(question)
            if metric_info:
                resolved_name = metric_info.get("name", "")
                inherited_name = inherited_mql.metric.name if inherited_mql.metric else ""
                if resolved_name and inherited_name and resolved_name != inherited_name:
                    logger.info(f"[_is_new_question] 指标不同: resolved={resolved_name}, inherited={inherited_name}")
                    return True

        return False

    def _handle_dimension_selection_followup(self, question: str, mql: MQLSchema) -> Optional[Dict[str, Any]]:
        """Handle dimension replacement follow-ups like `ASIN` or `按站点`."""
        dimension_codes = {
            "FSITECODE", "FSITE", "PLATFORM", "FCHANNEL", "FBRANDS", "FPRODUCTLINE",
            "FADTYPE", "GROUP_1", "GROUP_2", "GROUP_3", "GROUP_4", "SKU", "ASIN",
            "FCOUNTRY", "REGION", "FDATE", "MONTHS", "WEEKS", "YEARS", "QUARTERS",
            "PRODUCT_STATUS", "PRODUCT_LEVEL", "MODEL", "PEOPLEGROUP", "ADSDIRECTOR",
            "PEOPLEGROUP_CHARGE", "PEOPLEGROUP_DIRECTOR",
        }
        upper_question = question.upper()
        is_dimension_code = question in dimension_codes or upper_question in dimension_codes

        if is_dimension_code:
            dim_code = upper_question if upper_question in dimension_codes else question
            mql.dimensions = [MQLDimension(type=dim_code, value=None)]
            logger.info(f"[IntentRouter] 检测到维度选择: {dim_code}，替换维度")
            return {"mql": mql, "needs_clarification": False, "source": "followup"}

        if not (question.startswith("按") and len(question) >= 3):
            return None

        dim_label = question[1:]
        if self._dimension_type_mappings is None:
            self._load_dimension_mappings()
        if not self._dimension_type_mappings:
            return None

        dim_label_to_code = self._build_dimension_label_to_code_map()
        if dim_label in dim_label_to_code:
            dim_code = dim_label_to_code[dim_label]
            mql.dimensions = [MQLDimension(type=dim_code, value=None)]
            logger.info(f"[IntentRouter] 检测到中文维度选择: {question} -> {dim_code}，替换维度")
            return {"mql": mql, "needs_clarification": False, "source": "followup"}

        for dim_type, dim_code in dim_label_to_code.items():
            if dim_label in dim_type or dim_type in dim_label:
                mql.dimensions = [MQLDimension(type=dim_code, value=None)]
                logger.info(f"[IntentRouter] 检测到中文维度选择(模糊): {question} -> {dim_code}，替换维度")
                return {"mql": mql, "needs_clarification": False, "source": "followup"}

        return None

    def _try_extract_dim_from_middle(self, question: str, mql: MQLSchema) -> Optional[Dict[str, Any]]:
        """从问题中间提取'按XX维度'或'按XX'模式（不以'按'开头的场景）。

        例如 '扩展坞的按站点维度对比上月' → 提取 '站点' → FSITECODE
        """
        # 匹配 "按XX看/对比/分析" 或 "按XX维度" 模式
        match = re.search(r'按(.{1,6}?)(?:维度|看|对比|分析)', question)
        if not match:
            match = re.search(r'按(.{1,6}?)(?:\s|$)', question)
        if not match:
            return None

        dim_label = match.group(1).strip()
        if not dim_label or len(dim_label) < 2:
            return None

        if self._dimension_type_mappings is None:
            self._load_dimension_mappings()

        dim_label_to_code = self._build_dimension_label_to_code_map()

        # 精确匹配
        if dim_label in dim_label_to_code:
            dim_code = dim_label_to_code[dim_label]
            mql.dimensions = [MQLDimension(type=dim_code, value=None)]
            logger.info(f"[IntentRouter] 从中间提取维度: '{dim_label}' -> {dim_code}")
            return {"mql": mql, "needs_clarification": False, "source": "followup"}

        # 模糊匹配
        for dim_type, dim_code in dim_label_to_code.items():
            if dim_label in dim_type or dim_type in dim_label:
                mql.dimensions = [MQLDimension(type=dim_code, value=None)]
                logger.info(f"[IntentRouter] 从中间提取维度(模糊): '{dim_label}' -> {dim_code}")
                return {"mql": mql, "needs_clarification": False, "source": "followup"}

        # 语义快照解析
        semantic_svc = self._get_semantic_service()
        if semantic_svc:
            resolved = semantic_svc.resolve_dimension(dim_label)
            if resolved:
                col = resolved.get("column_name", "")
                dtype = resolved.get("dimension_type", dim_label)
                if col:
                    mql.dimensions = [MQLDimension(type=dtype or col, column=col, value=None)]
                    logger.info(f"[IntentRouter] 从中间提取维度(快照): '{dim_label}' -> {dtype}/{col}")
                    return {"mql": mql, "needs_clarification": False, "source": "followup"}

        return None

    def _handle_addition_followup(
        self,
        question: str,
        mql: MQLSchema,
        inherited_mql: MQLSchema,
        add_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        detected_dimensions = self._resolve_additional_dimensions(question, add_keywords)
        detected_metrics = self._resolve_additional_metrics(question, add_keywords)
        if not (detected_metrics or detected_dimensions):
            return None

        self._append_dimensions(mql, detected_dimensions)
        self._append_metrics(mql, detected_metrics)

        mql.original_question = inherited_mql.original_question or question
        logger.info(
            f"[IntentRouter] 处理追加追问: 新增指标={[m.get('name') for m in detected_metrics]}, "
            f"新增维度={[d.get('column_name') for d in detected_dimensions]}, "
            f"继承指标={inherited_mql.metric.name if inherited_mql and inherited_mql.metric else None}"
        )
        return {
            "mql": mql,
            "needs_clarification": False,
            "source": "followup_add_metric" if detected_metrics else "followup_add_dimension",
        }

    def _handle_removal_followup(
        self,
        question: str,
        mql: MQLSchema,
        inherited_mql: MQLSchema,
        remove_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        removed_dimensions = self._resolve_additional_dimensions(question, remove_keywords)
        removed_metrics = self._resolve_additional_metrics(question, remove_keywords)
        if not (removed_metrics or removed_dimensions):
            return None

        self._remove_dimensions(mql, removed_dimensions)
        removal_error = self._remove_metrics(mql, removed_metrics)
        if removal_error:
            return removal_error

        mql.original_question = inherited_mql.original_question or question
        logger.info(
            f"[IntentRouter] 处理去掉追问: 去掉指标={[m.get('name') for m in removed_metrics]}, "
            f"去掉维度={[d.get('column_name') for d in removed_dimensions]}"
        )
        return {
            "mql": mql,
            "needs_clarification": False,
            "source": "followup_remove_metric" if removed_metrics else "followup_remove_dimension",
        }

    def _extract_additional_metric_candidates(self, question: str, add_keywords: List[str]) -> List[str]:
        """从“增加指标”类追问中提取候选指标词。"""
        normalized = question
        for keyword in add_keywords:
            normalized = normalized.replace(keyword, " ")

        for filler in ["指标", "一下", "看看", "也", "再", "再加", "顺便"]:
            normalized = normalized.replace(filler, " ")

        for separator in ["以及", "还有", "和", "、", "，", ",", "/", "及"]:
            normalized = normalized.replace(separator, "|")

        candidates = [normalized.strip()]
        candidates.extend(part.strip() for part in normalized.split("|"))

        deduped = []
        for candidate in candidates:
            if candidate and candidate not in deduped:
                deduped.append(candidate)
        return deduped

    def _build_followup_mql(self, inherited_mql: MQLSchema, question: str) -> MQLSchema:
        """Create a mutable follow-up MQL seeded from the inherited state."""
        mql = MQLSchema()
        mql.session_id = inherited_mql.session_id
        mql.parent_state_id = inherited_mql.session_id
        mql.intent = inherited_mql.intent
        mql.metric = inherited_mql.metric
        mql.metrics = list(inherited_mql.metrics) if inherited_mql.metrics else []
        mql.time = inherited_mql.time
        mql.dimensions = list(inherited_mql.dimensions) if inherited_mql.dimensions else []
        mql.order_by = inherited_mql.order_by
        mql.top_n = inherited_mql.top_n
        mql.comparison = inherited_mql.comparison
        mql.original_question = inherited_mql.original_question or question
        return mql

    def _build_dimension_label_to_code_map(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for item in self._dimension_type_mappings or []:
            dim_type = item.get("dimension_type", "") or item.get("dimension_name", "") or ""
            column_name = item.get("column_name", "") or ""
            if dim_type and column_name:
                mapping[dim_type] = column_name
                mapping[f"按{dim_type}"] = column_name
        return mapping

    def _append_dimensions(self, mql: MQLSchema, detected_dimensions: List[Dict[str, str]]) -> None:
        existing_dimension_types = {d.type for d in mql.dimensions if d and d.type}
        for dimension_info in detected_dimensions:
            dim_code = dimension_info.get("column_name", "")
            if dim_code and dim_code not in existing_dimension_types:
                mql.dimensions.append(MQLDimension(type=dim_code, value=None))
                existing_dimension_types.add(dim_code)
                logger.info(f"[IntentRouter] 检测到追加维度: {dimension_info.get('label', dim_code)} ({dim_code})")

    def _append_metrics(self, mql: MQLSchema, detected_metrics: List[Dict[str, Any]]) -> None:
        from ..schema import MQLMetric

        existing_names = {m.name for m in [mql.metric] + mql.metrics if m and m.name}
        existing_codes = {m.code for m in [mql.metric] + mql.metrics if m and m.code}
        for metric_info in detected_metrics:
            metric_name = metric_info.get("name", "")
            metric_code = metric_info.get("metric_code", "") or metric_info.get("code", "")
            if metric_name in existing_names or metric_code in existing_codes:
                continue

            mql.metrics.append(MQLMetric(
                code=metric_code,
                name=metric_name,
                table=metric_info.get("starrocks_table", "") or metric_info.get("table", ""),
                field=metric_info.get("starrocks_field", "") or metric_info.get("field", ""),
                unit=metric_info.get("unit", ""),
                starrocks_sql=metric_info.get("starrocks_sql", ""),
            ))
            existing_names.add(metric_name)
            if metric_code:
                existing_codes.add(metric_code)
            logger.info(f"[IntentRouter] 检测到追加指标: {metric_name} ({metric_code})")

    def _remove_dimensions(self, mql: MQLSchema, removed_dimensions: List[Dict[str, str]]) -> None:
        removed_dim_codes = {d.get("column_name", "") for d in removed_dimensions if d.get("column_name")}
        if not removed_dim_codes:
            return

        mql.dimensions = [
            dim for dim in mql.dimensions
            if dim.type not in removed_dim_codes and dim.column not in removed_dim_codes
        ]
        logger.info(f"[IntentRouter] 去掉维度: {sorted(removed_dim_codes)}")

    def _remove_metrics(self, mql: MQLSchema, removed_metrics: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        removed_metric_names = {m.get("name", "") for m in removed_metrics if m.get("name")}
        removed_metric_codes = {
            m.get("metric_code", "") or m.get("code", "")
            for m in removed_metrics
            if (m.get("metric_code", "") or m.get("code", ""))
        }
        if not (removed_metric_names or removed_metric_codes):
            return None

        def _should_remove(metric_obj):
            if not metric_obj:
                return False
            return (
                (metric_obj.name and metric_obj.name in removed_metric_names) or
                (metric_obj.code and metric_obj.code in removed_metric_codes)
            )

        current_removed = _should_remove(mql.metric)
        remaining_metrics = [metric for metric in mql.metrics if not _should_remove(metric)]

        if current_removed:
            if remaining_metrics:
                mql.metric = remaining_metrics[0]
                mql.metrics = remaining_metrics[1:]
            else:
                return {
                    "mql": None,
                    "needs_clarification": True,
                    "clarification_message": "至少需要保留一个指标，当前没有可继续查询的指标。",
                    "source": "followup_remove_metric",
                }
        else:
            mql.metrics = remaining_metrics

        logger.info(
            f"[IntentRouter] 去掉指标: names={sorted(removed_metric_names)}, codes={sorted(removed_metric_codes)}"
        )
        return None

    def _resolve_additional_metrics(self, question: str, add_keywords: List[str]) -> List[Dict[str, Any]]:
        """通过指标元数据和同义词表解析追问里追加的指标。"""
        try:
            from ai.client.metric_client import MetricClient

            # 已知维度列名（不应作为指标解析）
            _KNOWN_DIM_NAMES = {
                "sku": "SKU", "SKU": "SKU", "商品": "SKU", "产品": "SKU",
                "asin": "ASIN", "ASIN": "ASIN",
                "店铺": "FSITE", "站点": "FSITE", "平台": "PLATFORM",
                "品牌": "FBRANDS", "品类": "GROUP_3", "类目": "GROUP_3",
                "一级品类": "GROUP_1", "二级品类": "GROUP_2",
                "三级品类": "GROUP_3", "四级品类": "GROUP_4",
            }

            client = MetricClient()
            candidates = self._extract_additional_metric_candidates(question, add_keywords)
            resolved = []
            seen_keys = set()

            for candidate in candidates:
                # 跳过已知维度名
                if candidate.lower() in _KNOWN_DIM_NAMES or candidate in _KNOWN_DIM_NAMES:
                    logger.info(f"[IntentRouter] 追问候选 '{candidate}' 是已知维度名，跳过指标解析")
                    continue

                # 优先用 _resolve_metric_name（语义快照 + 同义词 + MetricClient）
                metric_info = self._resolve_metric_name(candidate)
                if not metric_info:
                    # 兜底：MetricClient 直接查询
                    metric_info = client.get_metric_by_name(candidate)
                if not metric_info:
                    # 兜底：MetricClient 模糊搜索
                    search_results = client.search_metrics(candidate, limit=3)
                    if search_results:
                        first = search_results[0]
                        metric_info = client.get_metric_by_name(first.get("name", "")) or first

                if not metric_info:
                    continue

                metric_name = metric_info.get("name", "")
                metric_code = metric_info.get("metric_code", "") or metric_info.get("code", "")
                dedupe_key = metric_code or metric_name
                if not dedupe_key or dedupe_key in seen_keys:
                    continue

                seen_keys.add(dedupe_key)
                resolved.append(metric_info)

            return resolved
        except Exception as e:
            logger.warning(f"[IntentRouter] 解析追加指标失败: {e}")
            return []

    def _resolve_additional_dimensions(self, question: str, add_keywords: List[str]) -> List[Dict[str, str]]:
        """通过维度映射和维度同义词解析追问里追加的维度。"""
        try:
            dim_service = self._get_dimension_service()
            if self._dimension_type_mappings is None:
                self._load_dimension_mappings()

            candidates = self._extract_additional_metric_candidates(question, add_keywords)
            resolved = []
            seen_codes = set()

            dim_label_to_code = {}
            if self._dimension_type_mappings:
                for mapping in self._dimension_type_mappings:
                    dim_type = mapping.get("dimension_type", "") or mapping.get("dimension_name", "") or ""
                    column_name = mapping.get("column_name", "") or ""
                    if dim_type and column_name:
                        dim_label_to_code[dim_type] = column_name
                        dim_label_to_code[column_name] = column_name

            for candidate in candidates:
                if not candidate:
                    continue

                # 硬编码兜底：已知维度列名直接映射
                _KNOWN_DIM_COLS = {
                    "SKU": "SKU", "sku": "SKU", "商品": "SKU", "产品": "SKU",
                    "ASIN": "ASIN", "asin": "ASIN",
                }
                dim_code = ""
                dim_label = candidate
                upper_candidate = candidate.upper()

                if candidate in _KNOWN_DIM_COLS or candidate.lower() in _KNOWN_DIM_COLS:
                    dim_code = _KNOWN_DIM_COLS.get(candidate) or _KNOWN_DIM_COLS.get(candidate.lower(), "")
                elif upper_candidate in dim_label_to_code:
                    dim_code = dim_label_to_code[upper_candidate]
                elif candidate in dim_label_to_code:
                    dim_code = dim_label_to_code[candidate]
                else:
                    # ========== 优先用语义快照服务解析 ==========
                    semantic_svc = self._get_semantic_service()
                    if semantic_svc:
                        resolved_dim = semantic_svc.resolve_dimension(candidate)
                        if resolved_dim:
                            dim_code = resolved_dim.get("column_name", "") or ""
                            dim_label = resolved_dim.get("dimension_type", candidate)
                            is_generic = resolved_dim.get("is_generic", False)
                            if is_generic and dim_code:
                                # 泛指类型（如"店铺"），label 用 dimension_type
                                pass
                    # ============================================
                    if not dim_code and dim_service:
                        dim_code = dim_service.find_column_by_type(candidate) or ""
                        if not dim_code:
                            dim_info = dim_service.find_dimension_info(candidate)
                            if dim_info and dim_info.get("is_generic"):
                                dim_code = dim_info.get("column_name", "") or ""
                                dim_label = dim_info.get("dimension_type", candidate)

                if not dim_code or dim_code in seen_codes:
                    continue

                seen_codes.add(dim_code)
                resolved.append({
                    "column_name": dim_code,
                    "label": dim_label,
                })

            return resolved
        except Exception as e:
            logger.warning(f"[IntentRouter] 解析追加维度失败: {e}")
            return []

    def _handle_greeting(self) -> Dict[str, Any]:
        """处理寒暄"""
        mql = MQLSchema()
        mql.intent = MQLIntent.GREETING
        mql.confidence = 1.0

        return {
            "mql": mql,
            "needs_clarification": False,
            "source": "followup",
        }

    def _handle_drilldown(self, question: str, inherited_mql: Optional[MQLSchema] = None) -> Dict[str, Any]:
        """处理四类下钻特殊格式 __DRILLDOWN__:xxx__

        解析 __DRILLDOWN__:sales__ 格式，直接设置 drilldown_type，
        让后续 trigger_analyzer 返回对应的分析结果。
        继承 inherited_mql 的 time 和 dimensions 上下文。
        """
        # 解析格式：__DRILLDOWN__:sales__
        try:
            drilldown_type = question.replace("__DRILLDOWN__:", "").replace("__", "").strip()
            logger.info(f"[_handle_drilldown] 解析下钻类型: {drilldown_type}")
        except Exception as e:
            logger.warning(f"[_handle_drilldown] 解析失败: {e}")
            drilldown_type = None

        # 映射为中文语义（用于存储和 LLM 输入）
        chinese_label = DRILLDOWN_LABELS.get(drilldown_type, drilldown_type or question)
        resolved_question = f"请做{chinese_label}"

        mql = MQLSchema()
        mql.intent = MQLIntent.QUERY_VALUE  # 假装是查询值，实际 trigger_analyzer 会处理
        mql.confidence = 1.0
        mql.original_question = resolved_question  # 中文语义，供后续步骤和存储使用
        mql.resolved_question = resolved_question  # 同上

        # 继承 inherited_mql 的上下文（时间、维度、指标等）
        if inherited_mql:
            logger.info(f"[_handle_drilldown] 继承上下文: metric={inherited_mql.metric.name if inherited_mql.metric else None}, time={inherited_mql.time}, dimensions={inherited_mql.dimensions}")
            # 继承指标
            if inherited_mql.metric:
                mql.metric = inherited_mql.metric
            if inherited_mql.time:
                mql.time = inherited_mql.time
            if inherited_mql.dimensions:
                mql.dimensions = inherited_mql.dimensions
            if inherited_mql.filters:
                mql.filters = inherited_mql.filters

        # drilldown_type 会传递给 trigger_analyzer
        return {
            "mql": mql,
            "needs_clarification": False,
            "source": "drilldown",
            "drilldown_type": drilldown_type,  # 关键字段
        }

    async def _local_then_llm_intent_recognition(self, question: str, inherited_mql: Optional[MQLSchema]) -> Dict[str, Any]:
        """
        本地模型预识别 + LLM 兜底

        流程：
        1. 本地 Joint BERT 模型先识别
        2. 匹配成功（置信度 >= 0.85 + 有 METRIC 实体）→ 直接构建 MQLSchema
        3. 匹配失败 → 走 LLM 意图识别（兜底）
        """
        local_model = self._get_local_model()

        if local_model is None:
            # 本地模型加载失败，直接走 LLM
            logger.info("[IntentRouter] 本地模型不可用，走 LLM 兜底")
            return await self._llm_intent_recognition(question, inherited_mql)

        try:
            # 本地模型预测
            local_result = local_model.predict(question)
            logger.info(f"[IntentRouter] 本地模型预测: intent={local_result['intent']}, "
                       f"confidence={local_result['confidence']:.3f}, "
                       f"entities={len(local_result['entities'])}, "
                       f"match_success={local_result['match_success']}")

            # 匹配成功：直接构建 MQLSchema
            if local_result['match_success']:
                mql = self._build_mql_from_local(local_result, question)
                logger.info(f"[IntentRouter] 本地模型精准匹配成功，跳过 LLM: intent={mql.intent.value}")

                # ===== 本地模型匹配成功后：检测同比/环比关键词 =====
                # 注意：这些关键词在实体中被识别为 TIME，需要在这里补充检测并设置 comparison
                # "对比上月/上期" → 环比；"对比去年/同比" → 同比
                comparison_types = []
                if "环比" in question or "对比上月" in question or "对比上期" in question or "环比上月" in question or "环比上期" in question:
                    comparison_types.append("环比")
                if "同比" in question or "对比去年" in question or "同比去年" in question or "同比上期" in question:
                    comparison_types.append("同比")
                # "对比" 单独出现时默认环比（用户说"对比"一般指环比）
                if not comparison_types and ("对比" in question or "比较" in question):
                    comparison_types.append("环比")
                if comparison_types:
                    from ..schema import ComparisonSpec
                    mql.comparison = ComparisonSpec(
                        enabled=True,
                        types=comparison_types,
                        compare_period_start="",
                        compare_period_end="",
                    )
                    # 如果没有设置 intent 为 QUERY_COMPARISON，改为 QUERY_COMPARISON
                    if mql.intent.value not in ("query_comparison", "query_trend"):
                        mql.intent = MQLIntent.QUERY_COMPARISON
                    logger.info(f"[IntentRouter] 本地模型检测到对比关键词: {comparison_types}")

                # 检查是否有泛指维度 → 触发追问
                # ===== 新增：校验泛指维度是否为具体维度值 =====
                mql = self._validate_generic_dimensions(mql, question)
                clarification = self._check_generic_dimensions(mql, question)
                if clarification.get("is_generic"):
                    return {
                        "mql": mql,
                        "needs_clarification": True,
                        "clarification_message": clarification.get("clarification_message", ""),
                        "clarification_options": clarification.get("clarification_options", []),
                        "source": "local_model",
                        "original_question": question,
                    }

                return {
                    "mql": mql,
                    "needs_clarification": False,
                    "source": "local_model",
                    "local_confidence": local_result['confidence'],
                }

            # 匹配失败：LLM 兜底
            logger.info(f"[IntentRouter] 本地模型匹配失败（confidence={local_result['confidence']:.3f} 或缺少 METRIC 实体），"
                       f"走 LLM 兜底")
            return await self._llm_intent_recognition(question, inherited_mql, source_override="fallback")

        except Exception as e:
            logger.error(f"[IntentRouter] 本地模型预测异常: {e}，走 LLM 兜底")
            return await self._llm_intent_recognition(question, inherited_mql, source_override="fallback")

    def _build_mql_from_local(self, local_result: Dict[str, Any], question: str) -> MQLSchema:
        """
        从本地模型预测结果构建 MQLSchema

        本地模型输出：
        {
            'intent': 'query_value',
            'confidence': 0.92,
            'entities': [{'text': '销售额', 'type': 'METRIC'}, ...],
            'match_success': True
        }
        """
        from ..schema import MQLMetric, ComparisonSpec

        mql = MQLSchema()
        mql.original_question = question
        mql.resolved_question = question

        # 意图映射
        intent_str = local_result['intent']
        # drilldown 映射：BERT 识别 query_drilldown，MQLIntent 无此类型
        if intent_str == 'query_drilldown':
            intent_str = 'query_value'
            mql.drilldown_type = True
        try:
            mql.intent = MQLIntent(intent_str)
        except ValueError:
            # 尝试模糊映射
            intent_fallback = {
                'query_drilldown': 'query_value',
                'query_forecast': 'query_trend',
                'query_anomaly': 'query_trend',
                'query_filter': 'query_value',
            }
            mql.intent = MQLIntent(intent_fallback.get(intent_str, 'unknown'))
        mql.confidence = local_result['confidence']

        # 解析实体
        entities = local_result.get('entities', [])

        # 打印完整的 local_result 供调试
        logger.warning(f"[IntentRouter] ═══════════════════════════════════════")
        logger.warning(f"[IntentRouter] ★★★ local_result 完整内容: {local_result}")
        logger.warning(f"[IntentRouter] ★本地模型原始 entities: {entities}")
        logger.warning(f"[IntentRouter] ═══════════════════════════════════════")

        # 指标实体（必须）
        metric_entities = [e for e in entities if e['type'] == 'METRIC']
        if metric_entities:
            # 先检查所有 METRIC 实体是否可能是 business_terms 维度值同义词
            # 例如"美国站"被识别为 METRIC，但实际上是维度值
            dim_service = self._get_dimension_service()
            semantic_svc = self._get_semantic_service()
            real_metric_entities = []
            seen_dims_local = set()  # 去重
            for me in metric_entities:
                metric_text = me['text']
                dim_info = None
                # ========== 优先用语义快照服务解析 ==========
                if semantic_svc:
                    resolved = semantic_svc.resolve_dimension(metric_text)
                    if resolved and not resolved.get('is_generic'):
                        dim_info = resolved
                # 快照解析失败，用 dim_service 兜底
                if not dim_info and dim_service:
                    dim_info = dim_service.find_dimension_info(metric_text)
                # ============================================
                if dim_info and not dim_info.get('is_generic'):
                    # 去重
                    dim_type = dim_info.get('dimension_type', '')
                    dim_val = dim_info.get('dimension_value', metric_text)
                    dim_key = (dim_type, dim_val)
                    if dim_key in seen_dims_local:
                        logger.warning(f"[IntentRouter] 维度同义词重复，跳过: {dim_info}")
                        continue
                    seen_dims_local.add(dim_key)
                    # 这是维度值同义词，添加到 dimensions 而不是 metrics
                    mql.dimensions.append(MQLDimension(
                        type=dim_type,
                        column=dim_info.get('column_name', ''),
                        field="",
                        value=dim_val,
                    ))
                    logger.info(f"[IntentRouter] METRIC实体'{metric_text}'实为维度值同义词，转换: {dim_info}")
                else:
                    # 兜底：已知维度列名硬编码检查（防止本地模型把 sku/商品 等误判为 METRIC）
                    _KNOWN_DIM_NAMES = {
                        "sku": "SKU", "SKU": "SKU", "商品": "SKU", "产品": "SKU", "品名": "SKU",
                        "asin": "ASIN", "ASIN": "ASIN",
                        "店铺": "FSITE", "站点": "FSITE", "平台": "PLATFORM",
                        "渠道": "FCHANNEL", "品牌": "FBRANDS", "国家": "FCOUNTRY",
                        "品类": "GROUP_3", "类目": "GROUP_3",
                        "一级品类": "GROUP_1", "二级品类": "GROUP_2",
                        "三级品类": "GROUP_3", "四级品类": "GROUP_4",
                    }
                    dim_col = _KNOWN_DIM_NAMES.get(metric_text)
                    if dim_col:
                        mql.dimensions.append(MQLDimension(
                            type=dim_col, column=dim_col, field="", value="",
                        ))
                        logger.info(f"[IntentRouter] METRIC实体'{metric_text}'实为已知维度列，转为 dimension: {dim_col}")
                    else:
                        real_metric_entities.append(me)

            # 用过滤后的实体来处理指标
            metric_entities = real_metric_entities

            if metric_entities:
                # 主指标：取第一个 METRIC 实体
                metric_text = metric_entities[0]['text']
                mql.metric = MQLMetric(
                    code=local_result.get("metric_code", ""),  # 语义层可能已解析 metric_code
                    name=metric_text,
                    table="",
                    field="",
                    unit="",
                )
                logger.info(f"[IntentRouter] 本地模型提取主指标: {metric_text}")

                # 聚合关键词检测："平均"→AVG，"最高/最大"→MAX，"最低/最小"→MIN，"总数/总量"→SUM
                agg_keywords = {
                    "平均": AggregationType.AVG,
                    "avg": AggregationType.AVG,
                    "最高": AggregationType.MAX,
                    "最大": AggregationType.MAX,
                    "max": AggregationType.MAX,
                    "最低": AggregationType.MIN,
                    "最小": AggregationType.MIN,
                    "min": AggregationType.MIN,
                    "总数": AggregationType.SUM,
                    "总量": AggregationType.SUM,
                    "合计": AggregationType.SUM,
                }
                for kw, agg_type in agg_keywords.items():
                    if kw in question:
                        mql.metric.aggregation = agg_type
                        logger.info(f"[IntentRouter] 检测到聚合关键词 '{kw}' → {agg_type.value}")
                        break

                # 多指标：其余 METRIC 实体加入 metrics 列表
                if len(metric_entities) > 1:
                    for extra_metric in metric_entities[1:]:
                        extra_name = extra_metric['text']
                        mql.metrics.append(MQLMetric(
                            code="",
                            name=extra_name,
                            table="",
                            field="",
                            unit="",
                        ))
                    logger.info(f"[IntentRouter] 本地模型提取多指标: {[m.name for m in mql.metrics]}")

        # 时间实体
        time_entities = [e for e in entities if e['type'] == 'TIME']
        if time_entities:
            time_text = time_entities[0]['text']
            time_original = TIME_EXPRESSION_MAP.get(time_text, time_text)

            # 修复：当 TIME 实体是 "今年/去年/明年" 时，检查原始问题中是否有紧随其后的 "X月" 或 季度
            # 合并为完整时间表达式（如 "今年3月"、"去年12月"、"今年一季度"、"去年Q3"）
            if time_text in ('今年', '去年', '明年', '本年'):
                import re
                year_month_match = re.search(rf'{time_text}\s*(\d{{1,2}})月', question)
                year_quarter_match = re.search(rf'{time_text}\s*(一季度|二季度|三季度|四季度|[Qq][1-4])', question)
                if year_month_match:
                    time_original = year_month_match.group(0).replace(" ", "")
                    logger.info(f"[IntentRouter] 时间表达式扩展: {time_text} -> {time_original}")
                elif year_quarter_match:
                    time_original = year_quarter_match.group(0).replace(" ", "")
                    logger.info(f"[IntentRouter] 时间表达式扩展: {time_text} -> {time_original}")

            mql.time = TimeRange(
                type=TimeType.RELATIVE,
                start="",
                end="",
                original=time_original,
            )
            # 转换相对时间为绝对日期
            if time_original:
                time_parser = TimeParser()
                parsed = time_parser.parse(time_original)
                if parsed:
                    mql.time.start = parsed.get("start", "")
                    mql.time.end = parsed.get("end", "")
                    if parsed.get("type"):
                        try:
                            mql.time.type = TimeType(parsed["type"])
                        except ValueError:
                            pass
            # 计算时间范围天数
            if mql.time.start and mql.time.end:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(mql.time.start, "%Y-%m-%d")
                    end_dt = datetime.strptime(mql.time.end, "%Y-%m-%d")
                    mql.time.days = (end_dt - start_dt).days
                except ValueError:
                    pass
            logger.info(f"[IntentRouter] 本地模型提取时间: {time_text} -> {time_original}, start={mql.time.start}, end={mql.time.end}, days={mql.time.days}")

        # 维度实体（类型 + 值）
        dim_entities = [e for e in entities if e['type'] == 'DIM']
        dim_value_entities = [e for e in entities if e['type'] == 'DIM_VALUE']

        # 通过 dimension_service 反查 column_name（复用 853-898 行的逻辑）
        if dim_value_entities:
            dim_service = self._get_dimension_service()
            if dim_service and not self._dimension_type_mappings:
                self._load_dimension_mappings()
            column_to_dim_name = {}
            if self._dimension_type_mappings:
                for m in self._dimension_type_mappings:
                    col = m.get("column_name", "") or ""
                    dim_name = m.get("dimension_name", "") or m.get("dimension_type", "") or ""
                    if col and dim_name:
                        column_to_dim_name[col.upper()] = dim_name

            for dv_entity in dim_value_entities:
                dim_value = dv_entity['text']
                if not dim_service:
                    logger.warning(f"[IntentRouter] 无法处理 DIM_VALUE '{dim_value}'：DimensionService 不可用")
                    continue
                dim_info = dim_service.find_dimension_info(dim_value)
                if dim_info is None:
                    logger.warning(f"[IntentRouter] DimensionService 无法找到 '{dim_value}' 对应的维度信息")
                    continue

                if dim_info["is_generic"]:
                    # 去重：检查是否已存在相同的 type+column
                    dim_type = dim_info["dimension_type"]
                    column_name = dim_info.get("column_name", "")
                    if any(d.type == dim_type and d.column == column_name for d in mql.dimensions):
                        logger.info(f"[IntentRouter] 泛指维度已存在，跳过: {dim_type}({column_name})")
                    else:
                        mql.dimensions.append(MQLDimension(
                            type=dim_type,
                            column=column_name,
                            field="",
                            value=None,
                        ))
                        logger.info(f"[IntentRouter] 检测到泛指维度: {dim_info['dimension_type']}")
                else:
                    column_name = dim_info["column_name"]
                    dim_type = column_to_dim_name.get(column_name.upper(), dim_info["dimension_type"])
                    # 使用标准值（同义词映射后的值），如 "NAS" → "智能云存储"
                    canonical_value = dim_info.get("dimension_value") or dim_value
                    # 如果标准值等于维度类型名（如"店铺"=="店铺"），说明是泛指维度，触发追问
                    if canonical_value == dim_type:
                        mql.dimensions.append(MQLDimension(
                            type=dim_type,
                            column=column_name,
                            field="",
                            value=None,  # 泛指，没有具体值
                        ))
                        logger.info(f"[IntentRouter] 泛指维度(值=类型): {dim_type}({column_name})")
                    # 去重：检查是否已存在相同的 type+value
                    elif any(d.type == dim_type and d.value == canonical_value for d in mql.dimensions):
                        logger.info(f"[IntentRouter] 维度值已存在，跳过: {dim_type}={canonical_value}")
                    else:
                        mql.dimensions.append(MQLDimension(
                            type=dim_type,
                            column=column_name,
                            field="",
                            value=canonical_value,
                        ))
                        logger.info(f"[IntentRouter] 本地模型提取维度值: {dim_type}({column_name}) = {canonical_value}")

        # 单独 DIM_VALUE（无对应 DIM 类型）：通过 dimension_service 反查 column_name
        if dim_value_entities and not dim_entities:
            dim_service = self._get_dimension_service()
            # 确保维度映射已加载
            if dim_service and not self._dimension_type_mappings:
                self._load_dimension_mappings()
            # 建立 column_name → dimension_name 的反向映射
            column_to_dim_name = {}
            if self._dimension_type_mappings:
                for m in self._dimension_type_mappings:
                    col = m.get("column_name", "") or ""
                    dim_name = m.get("dimension_name", "") or m.get("dimension_type", "") or ""
                    if col and dim_name:
                        column_to_dim_name[col.upper()] = dim_name

            for dv_entity in dim_value_entities:
                dim_value = dv_entity['text']
                if not dim_service:
                    logger.warning(f"[IntentRouter] 无法处理 DIM_VALUE '{dim_value}'：DimensionService 不可用")
                    continue
                # 调用 Go API 搜索维度值，返回完整信息
                dim_info = dim_service.find_dimension_info(dim_value)
                if dim_info is None:
                    logger.warning(f"[IntentRouter] DimensionService 无法找到 '{dim_value}' 对应的维度信息")
                    continue

                if dim_info["is_generic"]:
                    # 去重：检查是否已存在相同的 type+column
                    dim_type = dim_info["dimension_type"]
                    column_name = dim_info.get("column_name", "")
                    if any(d.type == dim_type and d.column == column_name for d in mql.dimensions):
                        logger.info(f"[IntentRouter] 泛指维度已存在，跳过: {dim_type}({column_name})")
                    else:
                        mql.dimensions.append(MQLDimension(
                            type=dim_type,
                            column=column_name,
                            field="",
                            value=None,
                        ))
                        logger.info(f"[IntentRouter] 检测到泛指维度: {dim_info['dimension_type']}")
                else:
                    # 具体值 → 正常处理
                    column_name = dim_info["column_name"]
                    dim_type = column_to_dim_name.get(column_name.upper(), dim_info["dimension_type"])
                    # 使用标准值（同义词映射后的值），如 "NAS" → "智能云存储"
                    canonical_value = dim_info.get("dimension_value") or dim_value
                    # 如果标准值等于维度类型名（如"店铺"=="店铺"），说明是泛指维度，触发追问
                    if canonical_value == dim_type:
                        mql.dimensions.append(MQLDimension(
                            type=dim_type,
                            column=column_name,
                            field="",
                            value=None,  # 泛指，没有具体值
                        ))
                        logger.info(f"[IntentRouter] 泛指维度(值=类型): {dim_type}({column_name})")
                    # 去重：检查是否已存在相同的 type+value
                    elif any(d.type == dim_type and d.value == canonical_value for d in mql.dimensions):
                        logger.info(f"[IntentRouter] 维度值已存在，跳过(DIM_VALUE反查): {dim_type}={canonical_value}")
                    else:
                        mql.dimensions.append(MQLDimension(
                            type=dim_type,
                            column=column_name,
                            field="",
                            value=canonical_value,
                        ))
                        logger.info(f"[IntentRouter] 本地模型提取维度值(DIM_VALUE 反查): {dim_type}({column_name}) = {canonical_value}")

        # 单独 DIM 实体（无对应 DIM_VALUE）：查找 column_name 并加入 dimensions
        # 例如：用户问"销售额排名前三的站点" → BERT 识别到 DIM='站点' 但没有 DIM_VALUE
        # 此时 '站点' 应该作为分组维度，需要通过 dimension_mappings 反查列名
        if dim_entities:
            dim_service = self._get_dimension_service()
            if dim_service and not self._dimension_type_mappings:
                self._load_dimension_mappings()
            column_to_dim_name = {}
            if self._dimension_type_mappings:
                for m in self._dimension_type_mappings:
                    col = m.get("column_name", "") or ""
                    dim_name = m.get("dimension_name", "") or m.get("dimension_type", "") or ""
                    if col and dim_name:
                        column_to_dim_name[col.upper()] = dim_name

            for dim_entity in dim_entities:
                dim_text = dim_entity['text']
                # 跳过已配对的 DIM（那些有对应 DIM_VALUE 的）
                paired = False
                for dv_entity in dim_value_entities:
                    dv_text = dv_entity['text']
                    if dim_service:
                        dim_info = dim_service.find_dimension_info(dv_text)
                        if dim_info and dim_info.get("dimension_type") == dim_text:
                            paired = True
                            break
                if paired:
                    continue

                # 独立 DIM 实体：通过 dimension_mappings 反查列名
                if not self._dimension_type_mappings:
                    continue
                target_col = None
                for m in self._dimension_type_mappings:
                    d_name = m.get("dimension_name", "") or m.get("dimension_type", "") or ""
                    if d_name == dim_text:
                        col = m.get("column_name", "")
                        if col:
                            target_col = col
                            break
                # 兜底：硬编码已知列名（如 SKU、ASIN 直接是列名，不是维度类型名）
                if not target_col:
                    _KNOWN_DIM_COLS = {
                        "SKU": "SKU", "sku": "SKU", "ASIN": "ASIN", "asin": "ASIN",
                        "商品": "SKU", "产品": "SKU",
                    }
                    target_col = _KNOWN_DIM_COLS.get(dim_text)
                if target_col:
                    dim_type = column_to_dim_name.get(target_col.upper(), dim_text)
                    mql.dimensions.append(MQLDimension(
                        type=dim_type,
                        column=target_col,
                        field="",
                        value=None,
                    ))
                    logger.info(f"[IntentRouter] 本地模型提取分组维度(独立DIM): {dim_text} → {target_col}")
                else:
                    # 查不到列名，说明 dim_text 可能不是维度类型，而是未识别的维度值
                    # 回退到 find_dimension_info 查找它是否是具体维度值（如"德国亚马逊"）
                    if dim_service:
                        dim_info = dim_service.find_dimension_info(dim_text)
                        if dim_info and not dim_info.get("is_generic"):
                            column_name = dim_info["column_name"]
                            dim_type = column_to_dim_name.get(column_name.upper(), dim_info["dimension_type"])
                            mql.dimensions.append(MQLDimension(
                                type=dim_type,
                                column=column_name,
                                field="",
                                value=dim_text,
                            ))
                            logger.info(f"[IntentRouter] DIM回退为VALUE查找: {dim_text} → {dim_type}({column_name})={dim_text}")
                            continue
                    # 真的查不到，当作泛指维度处理
                    mql.dimensions.append(MQLDimension(
                        type=dim_text,
                        column="",
                        field="",
                        value=None,
                    ))
                    logger.info(f"[IntentRouter] 本地模型提取泛指分组维度(独立DIM): {dim_text}")

        # 检查是否有对比意图（环比/同比关键词）
        # 注意：不能仅凭"变化"判断对比，"趋势变化"只是时间序列查询
        if any(kw in question for kw in ['环比', '同比']):
            mql.comparison = ComparisonSpec(
                enabled=True,
                types=["环比"] if "环比" in question else ["同比"],
                compare_period_start="",
                compare_period_end="",
            )

        # 检查是否有排名意图
        if any(kw in question for kw in ['排名', '前几', '最高', '最低', '最好', '最差']):
            mql.intent = MQLIntent.QUERY_RANKING
            # 提取排名数量（支持阿拉伯数字和中文数字）
            import re
            # 中文数字映射
            CN_NUM_MAP = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
            def parse_chinese_num(s):
                if s in CN_NUM_MAP:
                    return CN_NUM_MAP[s]
                try:
                    return int(s)
                except:
                    return None
            # 优先匹配中文数字 "前三"、"前五" 等
            cn_match = re.search(r'前([一二三四五六七八九十]+)', question)
            if cn_match:
                top_n = parse_chinese_num(cn_match.group(1))
                if top_n:
                    mql.top_n = top_n
                else:
                    mql.top_n = 10
            else:
                # 阿拉伯数字 "前10"、"前3"
                digit_match = re.search(r'前(\d+)', question)
                if digit_match:
                    mql.top_n = int(digit_match.group(1))
                else:
                    mql.top_n = 10

        # 纯文本检测：BERT 没有输出 DIM 实体，但问题包含泛指维度关键词
        # 例如"本月各品类销售额" → BERT 没有识别到 DIM/DIM_VALUE，但文本里有"品类"
        if not mql.dimensions:
            generic_type_map = {
                "品类": "品类",
                "类目": "品类",
                "品牌": "品牌",
                "渠道": "渠道",
                "平台": "平台",
                "店铺": "店铺",
                "站点": "站点",
                "区域": "区域",
                "国家": "国家",
            }
            for kw, dim_type in generic_type_map.items():
                if kw in question:
                    mql.dimensions.append(MQLDimension(
                        type=dim_type,
                        column="",
                        field="",
                        value=None,  # 泛指，没有具体值
                    ))
                    logger.info(f"[IntentRouter] 文本检测到泛指维度关键词: {kw} → {dim_type}")
                    break

        # 兜底：扫描纯数字片段（如 SKU "15719"），查 API 确认是否是维度值
        if not mql.dimensions and mql.metric:
            import re
            # 匹配 4 位以上的纯数字（不用 \b，因为中文文本没有 ASCII 单词边界）
            for match in re.finditer(r'(\d{4,})', question):
                num_value = match.group(1)
                dim_service = self._get_dimension_service()
                if dim_service:
                    dim_info = dim_service.find_dimension_info(num_value)
                    if dim_info and not dim_info.get("is_generic"):
                        column_name = dim_info.get("column_name", "")
                        dim_type = dim_info.get("dimension_type", "")
                        # 建立 column_name → dimension_name 映射
                        if not self._dimension_type_mappings:
                            self._load_dimension_mappings()
                        column_to_dim_name = {}
                        if self._dimension_type_mappings:
                            for m in self._dimension_type_mappings:
                                col = m.get("column_name", "") or ""
                                dn = m.get("dimension_name", "") or m.get("dimension_type", "") or ""
                                if col and dn:
                                    column_to_dim_name[col.upper()] = dn
                        mql.dimensions.append(MQLDimension(
                            type=column_to_dim_name.get(column_name.upper(), dim_type),
                            column=column_name,
                            field="",
                            value=num_value,
                        ))
                        logger.info(f"[IntentRouter] 数字兜底查到维度: {num_value} -> {dim_type}({column_name})")
                        break  # 只取第一个匹配

        # ========== 占比模式检测（本地模型匹配成功后补充检测）==========
        # 本地模型可能把 "XX在YY中的占比" 识别为 query_value，
        # 需要在此补充检测并修正为 QUERY_RATIO
        if mql.metric and ('占比' in question or '比重' in question or '比例' in question):
            import re
            # 模式1: "XX在YY中的占比" 或 "XX在YY中的比重"
            match1 = re.search(r'([^\s，。,.！!？?在]+?)在([^\s，。,.！!？?中的]+?)中的[比]?占比', question)
            # 模式2: "XX占YY的占比" 或 "XX占YY比重"
            match2 = re.search(r'([^\s，。,.！!？?在]+?)占([^\s，。,.！!？?的]+?)[比]?占比', question)
            # 模式3: "XX在YY中的比例"
            match3 = re.search(r'([^\s，。,.！!？?在]+?)在([^\s，。,.！!？?中的]+?)中的比例', question)

            ratio_match = match1 or match2 or match3
            if ratio_match:
                molecule_text = ratio_match.group(1).strip()
                denominator_text = ratio_match.group(2).strip()

                # 排除明显不是指标的词（如"亚马逊"、"各站点"）
                skip_words = ['亚马逊', '各站点', '各平台', '各渠道', '各品类', '各品牌', '美国站', '中国站']
                if molecule_text not in skip_words and denominator_text not in skip_words:
                    from ..schema import CalculationPattern
                    mql.intent = MQLIntent.QUERY_RATIO
                    mql.calculation_patterns = [CalculationPattern.PERCENTAGE]
                    mql.molecule_metric = MQLMetric(
                        name=molecule_text,
                        code="",
                        table="",
                        field="",
                        unit="",
                    )
                    mql.denominator_metric = MQLMetric(
                        name=denominator_text,
                        code="",
                        table="",
                        field="",
                        unit="",
                    )
                    logger.info(f"[IntentRouter] 占比模式检测成功: 分子={molecule_text}, 分母={denominator_text}")

        return mql

    async def _llm_intent_recognition(self, question: str, inherited_mql: Optional[MQLSchema],
                                       source_override: str = None) -> Dict[str, Any]:
        """
        LLM 意图识别

        使用 DeepSeek 识别用户意图。

        Args:
            source_override: 强制指定 source（fallback 时传 "fallback"）
        """
        try:
            # 使用 V2 专用的 intent prompt
            prompt_template = self._prompt_manager.get_prompt(
                "nl2mql_intent",
                default=self._get_default_intent_prompt()
            )

            # 构建上下文
            context = ""
            if inherited_mql:
                context = f"""
【上轮上下文】
- 指标: {inherited_mql.metric.name if inherited_mql.metric else '无'}
- 时间: {inherited_mql.time.original if inherited_mql.time else '无'}
- 维度: {[d.type for d in inherited_mql.dimensions]}
"""

            # 填充 prompt（避免JSON中的{}被.format()解释）
            prompt = prompt_template.replace("{question}", question).replace("{context}", context)

            # 调用 LLM
            response = self._llm_engine.call(prompt, temperature=0.1, max_tokens=500)
            logger.info(f"[IntentRouter] LLM原始返回: {response[:500]}")

            # 解析 JSON - 尝试多种格式
            json_str = response.strip()
            # 去掉 markdown 代码块
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            logger.info(f"[IntentRouter] 解析JSON: {json_str[:200]}")
            result = json.loads(json_str.strip())

            # 构建 MQL
            mql = self._parse_mql_from_result(result, question)

            # 判断是否需要追问
            needs_clarification = False
            clarification_message = ""

            # 1. 检查意图是否未知
            # ✶ 修复：当 metric 已识别但 intent=unknown 时，默认设置为 query_value 而非追问
            # 因为 LLM 可能正确识别了 metric 但 intent 解析失败
            if mql.intent == MQLIntent.UNKNOWN or mql.confidence < 0.4:
                if mql.metric and mql.metric.name:
                    # metric 已识别，默认意图为 query_value，继续流程
                    mql.intent = MQLIntent.QUERY_VALUE
                    mql.confidence = 0.7
                    logger.info(f"[IntentRouter] LLM intent=unknown 但 metric={mql.metric.name} 已识别，默认设置 intent=query_value")
                else:
                    # metric 也未识别，才追问
                    needs_clarification = True
                    clarification_message = "抱歉，我没有理解您的问题，请换一种方式描述？"

            # 2. 检查是否有泛指维度需要追问（返回兜底数据 + 引导细化）
            # ===== 新增：校验泛指维度是否为具体维度值 =====
            mql = self._validate_generic_dimensions(mql, question)
            generic_check = self._check_generic_dimensions(mql, question)
            if generic_check.get("is_generic"):
                # 泛指维度：设置追问引导，但仍然继续执行返回数据
                needs_clarification = True
                clarification_message = generic_check.get("clarification_message", "")

            # 3. 排名查询没有维度时追问（类似品类追问）
            if not needs_clarification and mql.intent == MQLIntent.QUERY_RANKING and not mql.dimensions:
                needs_clarification = True
                clarification_message = "请问您想按哪个维度排名？"
                clarification_options = self._get_ranking_dimension_options()
                return {
                    "mql": mql,
                    "needs_clarification": needs_clarification,
                    "clarification_message": clarification_message,
                    "clarification_options": clarification_options,
                    "is_generic": True,
                    "default_dimension": "PLATFORM",
                    "source": source_override or "llm",
                    "original_question": question,
                }

            return {
                "mql": mql,
                "needs_clarification": needs_clarification,
                "clarification_message": clarification_message,
                "is_generic": generic_check.get("is_generic", False),
                "clarification_options": generic_check.get("clarification_options", []),
                "default_dimension": generic_check.get("default_dimension", ""),
                "source": source_override or "llm",
                "original_question": question,
            }

        except json.JSONDecodeError as e:
            logger.error(f"[IntentRouter] JSON 解析失败: {e}, json_str={json_str[:200] if 'json_str' in dir() else 'N/A'}")
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": "抱歉，我没有理解您的问题，请换一种方式描述？",
                "source": source_override or "llm",
            }
        except Exception as e:
            logger.error(f"[IntentRouter] 错误: {e}")
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": f"处理出错: {str(e)}",
                "source": source_override or "llm",
            }

    def _parse_mql_from_result(self, result: Dict[str, Any], question: str) -> MQLSchema:
        """从 LLM 结果解析 MQL（适配 nl2structure 格式）"""
        mql = MQLSchema()
        mql.original_question = question
        mql.resolved_question = question

        # 解析意图
        intent_str = result.get("intent", "unknown")
        try:
            mql.intent = MQLIntent(intent_str)
        except ValueError:
            mql.intent = MQLIntent.UNKNOWN

        mql.confidence = result.get("confidence", 0.7)

        # 解析指标（nl2structure 使用 metric_name）
        metric_data = result.get("metric") or {}
        metric_name = result.get("metric_name") or metric_data.get("name", "") if isinstance(metric_data, dict) else ""
        if metric_name:
            from ..schema import MQLMetric
            mql.metric = MQLMetric(
                code="",  # LLM不返回code，留空让后续节点补充
                name=metric_name,
                table="",
                field="",
                unit="",
            )

        # 解析时间（nl2structure 使用 time_range）
        time_data = result.get("time_range") or result.get("time", {})
        if time_data:
            from ..schema import TimeRange, TimeType
            original = time_data.get("original", "")
            if not original:
                original = time_data.get("start", "") or time_data.get("end", "") or "本月"
            try:
                time_type = TimeType(time_data.get("type", "relative"))
            except ValueError:
                time_type = TimeType.RELATIVE
            mql.time = TimeRange(
                type=time_type,
                start=time_data.get("start", ""),
                end=time_data.get("end", ""),
                original=original,
            )
            # 如果 start/end 为空，调用 TimeParser 将 original 转换为绝对日期
            if not mql.time.start or not mql.time.end:
                time_parser = TimeParser()
                parsed = time_parser.parse(original)
                if parsed:
                    if not mql.time.start:
                        mql.time.start = parsed.get("start", "")
                    if not mql.time.end:
                        mql.time.end = parsed.get("end", "")
                    if parsed.get("type"):
                        try:
                            mql.time.type = TimeType(parsed["type"])
                        except ValueError:
                            pass
            # 计算时间范围天数
            if mql.time.start and mql.time.end:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(mql.time.start, "%Y-%m-%d")
                    end_dt = datetime.strptime(mql.time.end, "%Y-%m-%d")
                    mql.time.days = (end_dt - start_dt).days
                except ValueError:
                    pass
            logger.info(f"[IntentRouter] LLM nl2structure 时间解析: original={original}, start={mql.time.start}, end={mql.time.end}, days={mql.time.days}")

        # 解析维度（支持 dimensions 数组 和 dimension 单个值两种格式）
        dim_type_map = {
            "店铺": "SHOP",
            "站点": "SITE",
            "平台": "PLATFORM",
            "渠道": "CHANNEL",
            "品类": "CATEGORY",
            "商品": "PRODUCT",
            "产品": "PRODUCT",
            "SKU": "SKU",
            "ASIN": "ASIN",
            "国家": "COUNTRY",
            "地区": "REGION",
            "区域": "REGION",
            "部门": "DEPARTMENT",
            "产品线": "PRODUCT_LINE",
            "广告类型": "AD_TYPE",
            "广告": "AD_TYPE",
            "日": "DAY",
            "月": "MONTH",
            "年": "YEAR",
            "周": "WEEK",
        }

        # 优先解析 dimensions 数组格式
        dimensions_list = result.get("dimensions", [])
        seen_dims = set()  # 去重：(type, value) 组合
        if dimensions_list:
            for dim_obj in dimensions_list:
                if isinstance(dim_obj, dict):
                    dim_type = dim_obj.get("type", "")
                    dim_value = dim_obj.get("value")
                else:
                    dim_type = str(dim_obj)
                    dim_value = None
                if dim_type:
                    mapped_type = dim_type_map.get(dim_type, dim_type.upper())
                    # 去重
                    dim_key = (mapped_type, dim_value)
                    if dim_key in seen_dims:
                        logger.warning(f"[IntentRouter] 维度重复，跳过: type={mapped_type}, value={dim_value}")
                        continue
                    seen_dims.add(dim_key)
                    mql.dimensions.append(MQLDimension(
                        type=mapped_type,
                        column="",
                        field="",
                        value=dim_value,
                    ))
        # 回退到 dimension 单个值格式（兼容旧格式）
        elif result.get("dimension"):
            dimension = result.get("dimension", "")
            dim_type = dim_type_map.get(dimension, dimension.upper())
            mql.dimensions.append(MQLDimension(
                type=dim_type,
                column="",
                field="",
                value=result.get("dimension_values"),
            ))

        # 解析对比周期
        # 支持两种格式：1) comparison_period 字符串（旧格式），2) comparison 对象（新格式）
        comparison_data = result.get("comparison", {})
        # 安全获取 types：key 存在但值为空列表时也要处理
        types = comparison_data.get("types") or [""]
        comparison_period = result.get("comparison_period", "") or types[0] if comparison_data else ""

        if comparison_period or (comparison_data and comparison_data.get("enabled")):
            from ..schema import ComparisonSpec
            mql.comparison = ComparisonSpec(
                enabled=True,
                types=[comparison_period] if comparison_period else comparison_data.get("types", []),
                compare_period_start=comparison_data.get("period_start", "") if isinstance(comparison_data, dict) else "",
                compare_period_end=comparison_data.get("period_end", "") if isinstance(comparison_data, dict) else "",
            )

        # 解析 Top N（从 intent 或 dimension 推断）
        if mql.intent == MQLIntent.QUERY_RANKING:
            top_n = result.get("top_n")
            if top_n is None or top_n == 0:
                # LLM 返回 0 或 None 时，从问题文本中提取数字（支持中文数字和阿拉伯数字）
                import re
                CN_NUM_MAP = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                def parse_cn_num(s):
                    if s in CN_NUM_MAP:
                        return CN_NUM_MAP[s]
                    try:
                        return int(s)
                    except:
                        return None
                cn_match = re.search(r'前([一二三四五六七八九十]+)', question)
                if cn_match:
                    parsed = parse_cn_num(cn_match.group(1))
                    top_n = parsed if parsed else 10
                else:
                    digit_match = re.search(r'前(\d+)', question)
                    if digit_match:
                        top_n = int(digit_match.group(1))
                    else:
                        top_n = 10  # 默认 Top 10
            mql.top_n = top_n

        # 解析排序方向（最少/最小 → ASC；最多/最大 → DESC）
        order_by_direction = result.get("order_by", {}).get("direction", "") if isinstance(result.get("order_by"), dict) else ""
        if not order_by_direction:
            order_by_direction = result.get("order_by_direction", "")
        if not order_by_direction:
            # 根据问题关键词推断排序方向
            question_lower = question.lower()
            if any(kw in question_lower for kw in ['最少', '最小', '最低', '最差', '最弱', '最慢']):
                order_by_direction = "ASC"
            elif any(kw in question_lower for kw in ['最多', '最大', '最高', '最好', '最强', '最快']):
                order_by_direction = "DESC"
        if order_by_direction:
            from ..schema import OrderBySpec
            mql.order_by = OrderBySpec(
                field="",
                direction=order_by_direction.upper()
            )

        return mql

    def _get_default_intent_prompt(self) -> str:
        """默认意图识别 prompt（精简版）- 动态注入实际指标和维度"""
        from ai.engine.prompt_metadata_loader import get_prompt_metadata_loader
        loader = get_prompt_metadata_loader()

        metric_names_str = loader.build_metric_names_section(max_count=80)
        dim_mappings_str = loader.build_dimension_mappings_section()

        prompt = """【角色】
你是一个业务指标查询助手，擅长从用户问题中识别查询意图。

【任务】
分析用户问题，提取：意图类型、指标名称、时间、维度、对比类型、排名N。

【输出格式】
只输出JSON，不要有其他内容：
{{"intent": "意图", "confidence": 0.0-1.0, "metric": {{"code": "", "name": "指标名称"}}, "time": {{"type": "relative", "original": "时间"}}, "dimensions": [{{"type": "维度"}}], "comparison": {{"enabled": false, "types": [], "period_start": "", "period_end": ""}}, "top_n": 0, "order_by_direction": "ASC或DESC"}}

【对比时间】
当用户询问同比/环比时（如"3月比2月"、"环比2月"），必须提取对比时间：
- comparison.enabled = true
- comparison.types = ["环比"] 或 ["同比"]
- comparison.period_start = 对比开始日期 (YYYY-MM-DD)
- comparison.period_end = 对比结束日期 (YYYY-MM-DD)

示例：
- 用户问"2026年3月环比2月" → period_start="2026-02-01", period_end="2026-02-28"
- 用户问"2026年Q1同比去年" → period_start="2025-01-01", period_end="2025-03-31"

【排序方向规则】
- 最多/最大/最高/最好 → DESC
- 最少/最小/最低/最差 → ASC
- 默认 DESC

【意图类型】
- query_value: 查指标数值（多少、总额）
- query_trend: 查趋势变化（趋势、走势、增长）
- query_comparison: 对比分析（对比、同比、环比）
- query_ranking: 排名（排名、前N、最好、最差、最大、最小）
- query_ratio: 占比（占比、比例、占多少）
- query_metadata: 查口径（业务口径、技术口径）
- greeting/thanks/bye: 寒暄

【系统实际指标名称（按此识别）】
{METRIC_NAMES}

【系统实际维度类型映射（按此映射）】
{DIMENSION_MAPPINGS}
每天/按天=DAY, 每周/按周=WEEK, 每月/按月=MONTH, 每年/按年=YEAR

【约束】
1. 只输出JSON 2. confidence<0.4用unknown 3. query_ranking必须返回top_n 4. query_comparison必须返回comparison.types

【上下文】
{context}

【用户问题】
{question}

请输出JSON："""

        prompt = prompt.replace("{METRIC_NAMES}", metric_names_str)
        prompt = prompt.replace("{DIMENSION_MAPPINGS}", dim_mappings_str)
        return prompt
