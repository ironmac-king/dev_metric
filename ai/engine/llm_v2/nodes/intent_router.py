"""
步骤 1: 意图路由智能体

职责：
- 识别用户意图（query_value / query_trend / query_comparison 等）
- 判断是否需要追问
- 继承上轮对话上下文
- 本地模型优先匹配，LLM 兜底
"""
import json
from typing import Dict, Any, Optional, List
from ai.config.logging_config import get_logger
from ai.engine.prompt_manager import get_prompt_manager
from ai.engine.llm import get_llm_engine
from ..schema import V2State, MQLSchema, MQLIntent, MQLDimension, TimeRange, TimeType

logger = get_logger("ai.llm_v2.intent_router")

# 本地模型实体类型 → MQLSchema 维度类型 映射
ENTITY_TYPE_TO_DIM_COLUMN = {
    'DIM': 'DIM',           # 通用维度类型
    'DIM_VALUE': 'DIM_VALUE',  # 维度值
    'SKU_VALUE': 'SKU',     # SKU 编码
}

# 时间表达式映射（简单场景用，复杂场景交给 LLM）
TIME_EXPRESSION_MAP = {
    '今日': '本月',
    '昨日': '昨日',
    '本周': '本周',
    '上周': '上周',
    '本月': '本月',
    '上月': '上月',
    '本季度': '本季度',
    '上季度': '上季度',
    '本年': '本年',
    '去年': '去年',
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
                logger.info("[IntentRouter] 本地 Joint BERT 模型加载成功")
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
        self._load_dimension_mappings()
        if self._dimension_type_mappings:
            # 排除时间粒度类型，只保留业务维度
            time_column_names = {"FDATE", "MONTHS", "YEARS", "WEEKS", "QUARTERS", "DAYS"}
            options = []
            seen_values = set()  # 用于去重

            for m in self._dimension_type_mappings:
                # dimension_configs 返回: dimension_name (中文名称), column_name (维度类型代码)
                # dimension_type_mappings 返回: dimension_type (中文), column_name (列名)
                dim_name = m.get("dimension_name", "") or m.get("dimension_type", "") or ""
                column_name = m.get("column_name", "") or ""

                # 跳过时间维度
                if column_name.upper() in time_column_names:
                    continue

                # 跳过没有维度名称的
                if not dim_name:
                    continue

                # column_name 作为维度类型代码（如 "PLATFORM"、"FSITE"）
                # 用于 SQL 生成器的 DIMENSION_COLUMN_MAP 映射
                value = column_name
                if value and value not in seen_values:
                    seen_values.add(value)
                    # dimension_name 本身就是中文名称（如"平台"、"店铺"）
                    label = f"按{dim_name}" if not dim_name.startswith("按") else dim_name
                    options.append({"label": label, "value": value})

            if options:
                logger.info(f"[IntentRouter] 排名维度选项: {options}")
                return options
        # 回退到默认选项
        return self.RANKING_DIMENSION_OPTIONS

    async def route(self, question: str, inherited_mql: Optional[MQLSchema] = None) -> Dict[str, Any]:
        """
        路由用户问题

        Args:
            question: 用户问题
            inherited_mql: 继承的 MQL（用于多轮对话）

        Returns:
            {
                "mql": MQLSchema,
                "needs_clarification": bool,
                "clarification_message": str,
            }
        """
        logger.info(f"[IntentRouter] 路由问题: {question[:50]}...")

        # 1. 寒暄处理
        if self._is_greeting(question):
            return self._handle_greeting()

        # 2. 简短追问处理（仅当有继承上下文时）
        if inherited_mql and self._is_short_followup(question):
            return await self._handle_followup(question, inherited_mql)

        # 3. 本地模型预识别（精准匹配 + LLM 兜底）
        return await self._local_then_llm_intent_recognition(question, inherited_mql)

    def _is_short_followup(self, question: str) -> bool:
        """判断是否为短追问或维度选择"""
        short_keywords = ["呢", "呢？", "？", "啊", "哦", "嗯", "再", "还", "环比呢", "同比呢", "趋势呢"]
        if any(kw in question for kw in short_keywords):
            return True

        # 检测是否是单个维度类型代码（如 FSITECODE、FSITE、PLATFORM 等）
        # 当用户从追问选项中选择维度时，前端发送的是 option.value（如 FSITECODE）
        dimension_codes = {
            "FSITECODE", "FSITE", "PLATFORM", "FCHANNEL", "FBRANDS", "FPRODUCTLINE",
            "FADTYPE", "GROUP_1", "GROUP_2", "GROUP_3", "GROUP_4", "SKU", "ASIN",
            "FCOUNTRY", "REGION", "FDATE", "MONTHS", "WEEKS", "YEARS", "QUARTERS",
            "PRODUCT_STATUS", "PRODUCT_LEVEL", "MODEL", "PEOPLEGROUP", "ADSDIRECTOR",
            "PEOPLEGROUP_CHARGE", "PEOPLEGROUP_DIRECTOR"
        }
        if question.upper() in dimension_codes or question in dimension_codes:
            return True

        # 仅用关键词判断追问，不依赖长度（中文字长但可能是完整问题）
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

        注意：此方法处理所有维度类型，不仅限于泛指类型。
        当 LLM 返回泛指类型（如 PRODUCT_LINE）但实际是具体值（如"智能云存储"）时，
        需要通过此方法纠正。
        """
        generic_types = {"CATEGORY", "品类", "类目", "商品类", "产品类"}

        dim_service = self._get_dimension_service()
        if not dim_service:
            return mql

        # 从问题中提取所有候选维度值
        candidates = self._extract_dimension_candidates(question, "")
        if not candidates:
            return mql

        logger.info(f"[_validate_generic_dimensions] 提取到的候选维度值: {candidates}")

        for candidate in candidates:
            # 查 dim_value_mapping（limit=10 返回多个结果用于判断模糊度）
            search_results = dim_service.search_by_value(candidate, limit=10)
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

    def _extract_dimension_candidates(self, question: str, dim_type: str) -> List[str]:
        """
        从问题中提取候选维度值。
        例如："智能云存储今年业绩" + dim_type="品类"
        → 提取 "智能云存储"（去掉 "品类" 相关词）
        """
        import re
        candidates = []

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
        time_words = ['今天', '昨天', '今年', '去年', '本周', '上周', '本月', '上月']
        for t in time_words:
            if t in question:
                idx = question.find(t)
                before = question[:idx].strip()
                if len(before) >= 2 and before not in candidates:
                    candidates.append(before)

        return candidates

    async def _handle_followup(self, question: str, inherited_mql: Optional[MQLSchema]) -> Dict[str, Any]:
        """处理短追问"""
        if inherited_mql:
            _metric_name = inherited_mql.metric.name if inherited_mql and inherited_mql.metric else None
            _dims = [(d.type, d.value) for d in inherited_mql.dimensions] if inherited_mql and inherited_mql.dimensions else []
            logger.info(f"[IntentRouter] 处理短追问: inherited_mql.metric={_metric_name}, inherited_mql.dimensions={_dims}")
        else:
            logger.info("[IntentRouter] 处理短追问: inherited_mql is None")

        if not inherited_mql:
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": "请问您想查询什么指标？",
                "source": "followup",
            }

        # 检测是否是单个维度类型代码（如 FSITECODE、FSITE、PLATFORM 等）
        dimension_codes = {
            "FSITECODE", "FSITE", "PLATFORM", "FCHANNEL", "FBRANDS", "FPRODUCTLINE",
            "FADTYPE", "GROUP_1", "GROUP_2", "GROUP_3", "GROUP_4", "SKU", "ASIN",
            "FCOUNTRY", "REGION", "FDATE", "MONTHS", "WEEKS", "YEARS", "QUARTERS",
            "PRODUCT_STATUS", "PRODUCT_LEVEL", "MODEL", "PEOPLEGROUP", "ADSDIRECTOR",
            "PEOPLEGROUP_CHARGE", "PEOPLEGROUP_DIRECTOR"
        }
        upper_question = question.upper()
        is_dimension_code = question in dimension_codes or upper_question in dimension_codes

        # 继承上轮 MQL
        mql = MQLSchema()
        mql.session_id = inherited_mql.session_id
        mql.parent_state_id = inherited_mql.session_id  # 关联父状态

        # 如果问题是维度代码，使用它作为维度
        if is_dimension_code:
            dim_code = upper_question if upper_question in dimension_codes else question
            mql.intent = inherited_mql.intent
            mql.metric = inherited_mql.metric
            mql.metrics = inherited_mql.metrics
            mql.time = inherited_mql.time
            mql.dimensions = [MQLDimension(type=dim_code, value=None)]
            mql.order_by = inherited_mql.order_by
            mql.top_n = inherited_mql.top_n
            mql.original_question = inherited_mql.original_question or question
            logger.info(f"[IntentRouter] 检测到维度选择: {dim_code}，替换维度")
            return {
                "mql": mql,
                "needs_clarification": False,
                "source": "followup",
            }

        # 检测是否是"按XX"格式的维度选择（如"按一级品类"、"按站点"等）
        # 前端发送 option.label（如"按一级品类"），后端需要转换为维度代码
        if question.startswith("按") and len(question) >= 3:
            dim_label = question[1:]  # 去掉"按"字，得到如"一级品类"
            # 加载维度类型映射（如果尚未加载）
            if self._dimension_type_mappings is None:
                self._load_dimension_mappings()
            if self._dimension_type_mappings:
                # 建立 中文维度名 -> 维度代码 的映射
                dim_label_to_code = {}
                for m in self._dimension_type_mappings:
                    dim_type = m.get("dimension_type", "") or m.get("dimension_name", "") or ""
                    column_name = m.get("column_name", "") or ""
                    if dim_type and column_name:
                        dim_label_to_code[dim_type] = column_name
                        dim_label_to_code[f"按{dim_type}"] = column_name  # 也包含完整label格式
                if dim_label in dim_label_to_code:
                    dim_code = dim_label_to_code[dim_label]
                    mql.intent = inherited_mql.intent
                    mql.metric = inherited_mql.metric
                    mql.metrics = inherited_mql.metrics
                    mql.time = inherited_mql.time
                    mql.dimensions = [MQLDimension(type=dim_code, value=None)]
                    mql.order_by = inherited_mql.order_by
                    mql.top_n = inherited_mql.top_n
                    mql.original_question = inherited_mql.original_question or question
                    logger.info(f"[IntentRouter] 检测到中文维度选择: {question} -> {dim_code}，替换维度")
                    return {
                        "mql": mql,
                        "needs_clarification": False,
                        "source": "followup",
                    }
                # 模糊匹配：检查 dim_label 是否包含在某维度名中
                for dim_type, dim_code in dim_label_to_code.items():
                    if dim_label in dim_type or dim_type in dim_label:
                        mql.intent = inherited_mql.intent
                        mql.metric = inherited_mql.metric
                        mql.metrics = inherited_mql.metrics
                        mql.time = inherited_mql.time
                        mql.dimensions = [MQLDimension(type=dim_code, value=None)]
                        mql.order_by = inherited_mql.order_by
                        mql.top_n = inherited_mql.top_n
                        mql.original_question = inherited_mql.original_question or question
                        logger.info(f"[IntentRouter] 检测到中文维度选择(模糊): {question} -> {dim_code}，替换维度")
                        return {
                            "mql": mql,
                            "needs_clarification": False,
                            "source": "followup",
                        }

        # 根据追问内容更新意图
        from ..schema import ComparisonSpec
        if "环比" in question:
            mql.intent = MQLIntent.QUERY_COMPARISON
            mql.comparison = inherited_mql.comparison if inherited_mql.comparison else ComparisonSpec()
            mql.comparison.types = ["环比"]
            mql.comparison.enabled = True
        elif "同比" in question:
            mql.intent = MQLIntent.QUERY_COMPARISON
            mql.comparison = inherited_mql.comparison if inherited_mql.comparison else ComparisonSpec()
            mql.comparison.types = ["同比"]
            mql.comparison.enabled = True
        elif "趋势" in question:
            mql.intent = MQLIntent.QUERY_TREND
        else:
            # 继承上轮意图
            mql.intent = inherited_mql.intent

        # 继承指标和时间
        mql.metric = inherited_mql.metric
        mql.metrics = inherited_mql.metrics
        mql.time = inherited_mql.time
        mql.dimensions = inherited_mql.dimensions
        _debug_info = f"[DEBUG: inherited_metric={inherited_mql.metric.name if inherited_mql and inherited_mql.metric else None}, inherited_dims={[(d.type, d.value) for d in inherited_mql.dimensions] if inherited_mql and inherited_mql.dimensions else []}]"
        mql.resolved_question = f"{_debug_info} | question={question}"

        return {
            "mql": mql,
            "needs_clarification": False,
            "source": "followup",
        }

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
        try:
            mql.intent = MQLIntent(local_result['intent'])
        except ValueError:
            mql.intent = MQLIntent.UNKNOWN
        mql.confidence = local_result['confidence']

        # 解析实体
        entities = local_result.get('entities', [])

        # 指标实体（必须）
        metric_entities = [e for e in entities if e['type'] == 'METRIC']
        if metric_entities:
            # 简单场景：取第一个 METRIC 实体作为主指标
            # 复杂场景（如多指标）交给后续 LLM 节点处理
            metric_text = metric_entities[0]['text']
            mql.metric = MQLMetric(
                code="",  # 本地模型不返回 code，让后续节点通过 metric_client 查询
                name=metric_text,
                table="",
                field="",
                unit="",
            )
            logger.info(f"[IntentRouter] 本地模型提取指标: {metric_text}")

        # 时间实体
        time_entities = [e for e in entities if e['type'] == 'TIME']
        if time_entities:
            time_text = time_entities[0]['text']
            time_original = TIME_EXPRESSION_MAP.get(time_text, time_text)
            mql.time = TimeRange(
                type=TimeType.RELATIVE,
                start="",
                end="",
                original=time_original,
            )
            logger.info(f"[IntentRouter] 本地模型提取时间: {time_text} -> {time_original}")

        # 维度实体（类型 + 值）
        dim_entities = [e for e in entities if e['type'] == 'DIM']
        dim_value_entities = [e for e in entities if e['type'] == 'DIM_VALUE']

        # 简单场景：直接组合维度类型和值
        if dim_entities and dim_value_entities:
            for i, dim_entity in enumerate(dim_entities):
                if i < len(dim_value_entities):
                    dim_type = dim_entity['text']
                    dim_value = dim_value_entities[i]['text']
                    # 简单映射，实际维度代码由后续节点解析
                    mql.dimensions.append(MQLDimension(
                        type=dim_type,
                        column="",
                        field="",
                        value=dim_value,
                    ))
                    logger.info(f"[IntentRouter] 本地模型提取维度: {dim_type} = {dim_value}")

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
                    # 泛指类型 → 注入维度（value=None）触发追问
                    mql.dimensions.append(MQLDimension(
                        type=dim_info["dimension_type"],  # 如"品类"
                        column=dim_info.get("column_name", ""),
                        field="",
                        value=None,  # 泛指，没有具体值
                    ))
                    logger.info(f"[IntentRouter] 检测到泛指维度: {dim_info['dimension_type']}")
                else:
                    # 具体值 → 正常处理
                    column_name = dim_info["column_name"]
                    dim_type = column_to_dim_name.get(column_name.upper(), dim_info["dimension_type"])
                    mql.dimensions.append(MQLDimension(
                        type=dim_type,
                        column=column_name,
                        field="",
                        value=dim_value,
                    ))
                    logger.info(f"[IntentRouter] 本地模型提取维度值(DIM_VALUE 反查): {dim_type}({column_name}) = {dim_value}")

        # 检查是否有对比意图（环比/同比关键词）
        if any(kw in question for kw in ['环比', '同比', '增长', '下降', '变化']):
            mql.comparison = ComparisonSpec(
                enabled=True,
                types=["环比"] if "环比" in question else ["同比"],
                compare_period_start="",
                compare_period_end="",
            )

        # 检查是否有排名意图
        if any(kw in question for kw in ['排名', '前几', '最高', '最低', '最好', '最差']):
            mql.intent = MQLIntent.QUERY_RANKING
            # 提取排名数量
            import re
            match = re.search(r'前(\d+)', question)
            if match:
                mql.top_n = int(match.group(1))
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
            if mql.intent == MQLIntent.UNKNOWN or mql.confidence < 0.4:
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
                # LLM 返回 0 或 None 时，从问题文本中提取数字
                import re
                match = re.search(r'前(\d+)', question)
                if match:
                    top_n = int(match.group(1))
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
        """默认意图识别 prompt（精简版）"""
        return """【角色】
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

【维度映射】
店铺=SHOP, 平台=PLATFORM, 品类=CATEGORY, 渠道=CHANNEL, 品牌=BRAND, 产品线=PRODUCT_LINE, 广告类型=AD_TYPE, 站点=SITE, 国家=COUNTRY, 地区=REGION
每天/按天=DAY, 每周/按周=WEEK, 每月/按月=MONTH, 每年/按年=YEAR
一级品类=GROUP_1, 二级品类=GROUP_2, 三级品类=GROUP_3, 四级品类=GROUP_4

【约束】
1. 只输出JSON 2. confidence<0.4用unknown 3. query_ranking必须返回top_n 4. query_comparison必须返回comparison.types

【上下文】
{context}

【用户问题】
{question}

请输出JSON："""
