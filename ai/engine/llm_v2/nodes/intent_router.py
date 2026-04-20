"""
步骤 1: 意图路由智能体

职责：
- 识别用户意图（query_value / query_trend / query_comparison 等）
- 判断是否需要追问
- 继承上轮对话上下文
"""
import json
from typing import Dict, Any, Optional, List
from ai.config.logging_config import get_logger
from ai.engine.prompt_manager import get_prompt_manager
from ai.engine.llm import get_llm_engine
from ..schema import V2State, MQLSchema, MQLIntent, MQLDimension

logger = get_logger("ai.llm_v2.intent_router")


class IntentRouter:
    """
    意图路由智能体

    使用 LLM 识别用户意图，并判断是否需要追问。
    """

    def __init__(self):
        self._prompt_manager = get_prompt_manager()
        self._llm_engine = get_llm_engine()

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

        # 3. LLM 意图识别
        return await self._llm_intent_recognition(question, inherited_mql)

    def _is_short_followup(self, question: str) -> bool:
        """判断是否为短追问"""
        short_keywords = ["呢", "呢？", "？", "啊", "哦", "嗯", "再", "还", "环比呢", "同比呢", "趋势呢"]
        return len(question) < 10 or any(kw in question for kw in short_keywords)

    def _is_greeting(self, question: str) -> bool:
        """判断是否为寒暄"""
        greeting_keywords = ["你好", "您好", "嗨", "hi", "hello", "早上好", "下午好", "晚上好", "hi", "hey"]
        return any(kw in question.lower() for kw in greeting_keywords)

    def _check_generic_dimensions(self, mql: MQLSchema) -> Dict[str, Any]:
        """检查是否有泛指维度需要追问

        Returns:
            {
                "is_generic": bool,
                "generic_types": List[str],  # 泛指类型列表
                "default_dimension": str,     # 默认使用的维度
                "clarification_message": str, # 追问引导
                "clarification_options": List[Dict]  # 选项列表
            }
        """
        generic_types = {"CATEGORY", "品类", "类目", "商品类", "产品类"}
        brand_types = {"BRAND", "品牌"}

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

        # 根据泛指类型返回对应的选项
        if first_generic in generic_types:
            return {
                "is_generic": True,
                "generic_types": generic_dims,
                "default_dimension": "三级品类",
                "clarification_message": "您选择的是三级品类，要切换吗？",
                "clarification_options": [
                    {"label": "一级品类", "value": "一级品类"},
                    {"label": "二级品类", "value": "二级品类"},
                    {"label": "三级品类", "value": "三级品类"},
                ]
            }
        elif first_generic in brand_types:
            return {
                "is_generic": True,
                "generic_types": generic_dims,
                "default_dimension": "品牌",
                "clarification_message": "您选择的是品牌维度，要切换吗？",
                "clarification_options": [
                    {"label": "按品牌", "value": "品牌"},
                    {"label": "按店铺", "value": "店铺"},
                    {"label": "按平台", "value": "平台"},
                ]
            }
        else:
            return {
                "is_generic": True,
                "generic_types": generic_dims,
                "default_dimension": generic_dims[0],
                "clarification_message": f"请问您想按哪个维度分析？（{', '.join(generic_dims)}）",
                "clarification_options": [{"label": d, "value": d} for d in generic_dims]
            }

    def _handle_greeting(self) -> Dict[str, Any]:
        """处理寒暄"""
        return {
            "mql": None,
            "needs_clarification": False,
            "clarification_message": "",
            "answer": "您好！我是智能问数助手，可以帮您查询业务数据。请问您想查询什么指标？",
        }

    async def _handle_followup(self, question: str, inherited_mql: Optional[MQLSchema]) -> Dict[str, Any]:
        """处理短追问"""
        logger.info("[IntentRouter] 处理短追问")

        if not inherited_mql:
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": "请问您想查询什么指标？",
            }

        # 继承上轮 MQL
        mql = MQLSchema()
        mql.session_id = inherited_mql.session_id
        mql.parent_state_id = inherited_mql.session_id  # 关联父状态

        # 根据追问内容更新意图
        if "环比" in question:
            mql.intent = MQLIntent.QUERY_COMPARISON
            mql.comparison = inherited_mql.comparison or type(inherited_mql.comparison).__call__()
            mql.comparison.types = ["环比"]
            mql.comparison.enabled = True
        elif "同比" in question:
            mql.intent = MQLIntent.QUERY_COMPARISON
            mql.comparison = inherited_mql.comparison or type(inherited_mql.comparison).__call__()
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
        mql.original_question = question

        return {
            "mql": mql,
            "needs_clarification": False,
        }

    def _handle_greeting(self) -> Dict[str, Any]:
        """处理寒暄"""
        mql = MQLSchema()
        mql.intent = MQLIntent.GREETING
        mql.confidence = 1.0

        return {
            "mql": mql,
            "needs_clarification": False,
        }

    async def _llm_intent_recognition(self, question: str, inherited_mql: Optional[MQLSchema]) -> Dict[str, Any]:
        """
        LLM 意图识别

        使用 DeepSeek 识别用户意图。
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
            generic_check = self._check_generic_dimensions(mql)
            if generic_check.get("is_generic"):
                # 泛指维度：设置追问引导，但仍然继续执行返回数据
                needs_clarification = True
                clarification_message = generic_check.get("clarification_message", "")

            return {
                "mql": mql,
                "needs_clarification": needs_clarification,
                "clarification_message": clarification_message,
                "is_generic": generic_check.get("is_generic", False),
                "clarification_options": generic_check.get("clarification_options", []),
                "default_dimension": generic_check.get("default_dimension", ""),
            }

        except json.JSONDecodeError as e:
            logger.error(f"[IntentRouter] JSON 解析失败: {e}, json_str={json_str[:200] if 'json_str' in dir() else 'N/A'}")
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": "抱歉，我没有理解您的问题，请换一种方式描述？",
            }
        except Exception as e:
            logger.error(f"[IntentRouter] 错误: {e}")
            return {
                "mql": None,
                "needs_clarification": True,
                "clarification_message": f"处理出错: {str(e)}",
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
        comparison_period = result.get("comparison_period", "")
        if comparison_period:
            from ..schema import ComparisonSpec
            mql.comparison = ComparisonSpec(
                enabled=True,
                types=[comparison_period],
            )

        # 解析 Top N（从 intent 或 dimension 推断）
        if mql.intent == MQLIntent.QUERY_RANKING:
            mql.top_n = result.get("top_n", 10)

        return mql

    def _get_default_intent_prompt(self) -> str:
        """默认意图识别 prompt（精简版）"""
        return """【角色】
你是一个业务指标查询助手，擅长从用户问题中识别查询意图。

【任务】
分析用户问题，提取：意图类型、指标名称、时间、维度、对比类型、排名N。

【输出格式】
只输出JSON，不要有其他内容：
{{"intent": "意图", "confidence": 0.0-1.0, "metric": {{"code": "", "name": "指标名称"}}, "time": {{"type": "relative", "original": "时间"}}, "dimensions": [{{"type": "维度"}}], "comparison": {{"enabled": false}}, "top_n": 0}}

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
