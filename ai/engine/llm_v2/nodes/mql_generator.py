"""
步骤 3: MQL 生成智能体

职责：
- 将自然语言转换为 MQL（Metric Query Language）
- 处理多轮对话上下文
- 应用 RAG 上下文
"""
import json
from typing import Dict, Any, List, Optional
from ai.config.logging_config import get_logger
from ai.engine.prompt_manager import get_prompt_manager
from ai.engine.llm import get_llm_engine
from ..schema import MQLSchema, MQLIntent, MQLMetric, MQLDimension, TimeRange, TimeType

logger = get_logger("ai.llm_v2.mql_generator")


class MQLGenerator:
    """
    MQL 生成智能体

    使用 LLM 将自然语言转换为 MQL 结构化查询。
    """

    def __init__(self):
        self._prompt_manager = get_prompt_manager()
        self._llm_engine = get_llm_engine()

    async def generate(
        self,
        question: str,
        rag_context: List[Dict[str, Any]] = None,
        inherited_mql: Optional[MQLSchema] = None,
    ) -> Optional[MQLSchema]:
        """
        生成 MQL

        Args:
            question: 用户问题
            rag_context: RAG 检索到的相似案例
            inherited_mql: 继承的 MQL（多轮对话）

        Returns:
            MQLSchema 或 None
        """
        logger.info(f"[MQLGenerator] 生成 MQL: {question[:50]}...")

        try:
            # 1. 构建 prompt
            prompt = self._build_prompt(question, rag_context, inherited_mql)

            # 调试：打印完整 prompt
            logger.info(f"[MQLGenerator] 完整 prompt:\n{prompt}\n{'='*80}")

            # 2. 调用 LLM
            response = self._llm_engine.call(prompt, temperature=0.1, max_tokens=1000)

            # 3. 解析 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            result = json.loads(response.strip())

            # 4. 构建 MQL
            mql = self._parse_mql(result, question)

            # 5. 填充默认值
            self._fill_defaults(mql, inherited_mql)

            logger.info(f"[MQLGenerator] MQL 生成成功: intent={mql.intent.value}")
            return mql

        except json.JSONDecodeError as e:
            logger.error(f"[MQLGenerator] JSON 解析失败: {e}")
            return None
        except Exception as e:
            import traceback
            logger.error(f"[MQLGenerator] 错误: {e}\n{traceback.format_exc()}")
            return None

    def _build_prompt(
        self,
        question: str,
        rag_context: List[Dict[str, Any]] = None,
        inherited_mql: Optional[MQLSchema] = None,
    ) -> str:
        """构建 MQL 生成 prompt"""
        # 从 PromptManager 获取 prompt
        prompt_template = self._prompt_manager.get_prompt(
            "nl2mql",
            default=self._get_default_nl2mql_prompt()
        )

        # 构建上下文
        context_parts = []

        # RAG 上下文
        if rag_context:
            context_parts.append("【相似案例】")
            for i, case in enumerate(rag_context[:3], 1):
                context_parts.append(f"\n案例 {i}:")
                context_parts.append(f"  问题: {case.get('question', '')}")
                if case.get('mql'):
                    mql_dict = case['mql'] if isinstance(case['mql'], dict) else case['mql'].to_dict()
                    context_parts.append(f"  指标: {mql_dict.get('metric', {}).get('name', '')}")
                    context_parts.append(f"  时间: {mql_dict.get('time', {}).get('original', '')}")

        # 继承上下文
        if inherited_mql:
            context_parts.append("\n【上轮上下文】")
            context_parts.append(f"  指标: {inherited_mql.metric.name if inherited_mql.metric else '无'}")
            context_parts.append(f"  时间: {inherited_mql.time.original if inherited_mql.time else '无'}")
            dims = [d.type for d in inherited_mql.dimensions] if inherited_mql.dimensions else []
            context_parts.append(f"  维度: {', '.join(dims) if dims else '无'}")

        # 维度值上下文（从 dim_value_mapping 查询）
        dim_values_context = self._get_dimension_values_context()
        if dim_values_context:
            context_parts.append("\n【维度值参考】")
            context_parts.append(dim_values_context)

        context_str = "\n".join(context_parts) if context_parts else "（无历史上下文）"

        # 填充 prompt
        return prompt_template.format(
            question=question,
            context=context_str,
        )

    def _get_dimension_values_context(self) -> str:
        """从 dim_value_mapping 获取维度值上下文"""
        try:
            from ai.client.dim_value_client import DimValueClient
            client = DimValueClient()

            # 查询关键维度字段的值
            dimension_fields = ["PLATFORM", "FCHANNEL", "FADTYPE", "FSITE"]
            context_lines = []

            for field in dimension_fields:
                values = client.search_dimension_values(query="", dimension_field=field, limit=20)
                if values:
                    value_list = [v.get("dimension_value", "") for v in values]
                    context_lines.append(f"  {field}: {', '.join(value_list)}")

            return "\n".join(context_lines) if context_lines else ""
        except Exception as e:
            logger.warning(f"[_get_dimension_values_context] 获取维度值失败: {e}")
            return ""

    def _correct_category_level(self, dim_type: str, question: str) -> str:
        """纠正 LLM 品类级别幻觉

        如果用户提到"X级品类"，但 LLM 返回了错误的级别，需要纠正。
        例如用户说"三级品类"但 LLM 返回 GROUP_1，需要纠正为 GROUP_3。
        """
        if not question or not dim_type:
            return dim_type

        # 检查用户是否提到了具体级别
        level_keywords = {
            "一级品类": "GROUP_1",
            "二级品类": "GROUP_2",
            "三级品类": "GROUP_3",
            "四级品类": "GROUP_4",
        }

        for keyword, correct_type in level_keywords.items():
            if keyword in question:
                # 用户明确提到了这个级别
                if dim_type != correct_type:
                    logger.warning(f"[_correct_category_level] 检测到 LLM 品类级别幻觉: 用户说'{keyword}'但 LLM 返回'{dim_type}'，纠正为'{correct_type}'")
                    return correct_type
                return dim_type

        # 用户没提具体级别，检查是否提到"品类"（泛指）
        if "品类" in question or "类目" in question:
            # 如果 LLM 返回的是品类相关但不是具体级别，保持不变
            # 让后续的泛指维度追问机制处理
            pass

        return dim_type

    def _parse_mql(self, result: Dict[str, Any], question: str) -> MQLSchema:
        """从 LLM 结果解析 MQL"""
        logger.info(f"[_parse_mql] 原始 LLM 返回: {result}")
        mql = MQLSchema()
        mql.original_question = question

        # 基本字段
        mql.resolved_question = result.get("resolved_question", question)

        intent_str = result.get("intent", "query_value")
        try:
            mql.intent = MQLIntent(intent_str)
        except ValueError:
            mql.intent = MQLIntent.UNKNOWN

        mql.confidence = result.get("confidence", 0.7)

        # 指标 - 只提取 name 和 code，不从 LLM 获取 table/starrocks_sql
        # table 和 starrocks_sql 必须从指标库配置获取，不能信任 LLM 的幻觉
        metric_data = result.get("metric", {})
        if metric_data:
            # 提取 name，忽略 code（避免 LLM 幻觉）
            metric_name = metric_data.get("name", "")
            # 忽略 LLM 返回的 code，避免幻觉
            code = metric_data.get("code", "")
            if code and ("留空" in code or "不填" in code or len(code) > 20):
                code = ""  # 强制置空，让 mql_validator 通过 name 查找
            mql.metric = MQLMetric(
                code=code,
                name=metric_name,
                table="",  # 不从 LLM 提取，避免幻觉
                field="",
                unit=metric_data.get("unit", ""),
                starrocks_sql="",  # 不从 LLM 提取，避免幻觉
            )

        # 占比分子/分母指标
        from ..schema import AggregationType
        molecule_data = result.get("molecule_metric", {})
        if molecule_data:
            agg_str = molecule_data.get("aggregation", "SUM").upper()
            try:
                agg = AggregationType(agg_str)
            except ValueError:
                agg = AggregationType.SUM
            mql.molecule_metric = MQLMetric(
                name=molecule_data.get("name", ""),
                field=molecule_data.get("field", ""),
                aggregation=agg,
            )
        denominator_data = result.get("denominator_metric", {})
        if denominator_data:
            agg_str = denominator_data.get("aggregation", "SUM").upper()
            try:
                agg = AggregationType(agg_str)
            except ValueError:
                agg = AggregationType.SUM
            mql.denominator_metric = MQLMetric(
                name=denominator_data.get("name", ""),
                field=denominator_data.get("field", ""),
                aggregation=agg,
            )

        # 时间
        time_data = result.get("time", {})
        if time_data:
            try:
                mql.time = TimeRange(
                    type=TimeType(time_data.get("type", "relative")),
                    start=time_data.get("start", ""),
                    end=time_data.get("end", ""),
                    original=time_data.get("original", "本月"),
                )
            except ValueError:
                mql.time = TimeRange(original=time_data.get("original", "本月"))

        # 维度 - 中文到英文的映射
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
            "一级品类": "GROUP_1",
            "二级品类": "GROUP_2",
            "三级品类": "GROUP_3",
            "四级品类": "GROUP_4",
        }

        # 维度 - 不从 LLM 提取 column，避免幻觉，使用 sql_generator 的映射
        for dim_data in result.get("dimensions", []):
            dim_type = dim_data.get("type", "")
            # 转换为英文
            mapped_type = dim_type_map.get(dim_type, dim_type.upper() if dim_type else "")

            # 纠正 LLM 品类级别幻觉：如果用户提到"X级品类"，但 LLM 返回了错误的级别
            # 例如用户说"三级品类"但 LLM 返回 GROUP_1，需要纠正
            mapped_type = self._correct_category_level(mapped_type, question)

            mql.dimensions.append(MQLDimension(
                type=mapped_type,
                column="",  # 不从 LLM 提取，使用 sql_generator 的维度类型映射
                field=dim_data.get("field", ""),
                value=dim_data.get("value"),
            ))

        # 筛选
        for filter_data in result.get("filters", []):
            from ..schema import MQLFilter, OperatorType
            try:
                mql.filters.append(MQLFilter(
                    field=filter_data.get("field", ""),
                    operator=OperatorType(filter_data.get("operator", "eq")),
                    value=filter_data.get("value"),
                ))
            except ValueError:
                pass

        # 对比
        comparison_data = result.get("comparison", {})
        if comparison_data:
            from ..schema import ComparisonSpec
            mql.comparison = ComparisonSpec(
                enabled=comparison_data.get("enabled", False),
                types=comparison_data.get("types", []),
            )

        # Top N
        mql.top_n = int(result.get("top_n") or 0)
        mql.bottom_n = int(result.get("bottom_n") or 0)

        # 计算模式
        for pattern in result.get("calculation_patterns", []):
            from ..schema import CalculationPattern
            try:
                mql.calculation_patterns.append(CalculationPattern(pattern))
            except ValueError:
                pass

        return mql

    def _fill_defaults(self, mql: MQLSchema, inherited_mql: Optional[MQLSchema]):
        """填充默认值"""
        logger.info(f"[_fill_defaults] 进入方法，dimensions={mql.dimensions}, original_question={mql.original_question}")
        # 时间默认本月
        if not mql.time and inherited_mql and inherited_mql.time:
            mql.time = inherited_mql.time
        elif not mql.time:
            mql.time = TimeRange(type=TimeType.RELATIVE, original="本月")

        # 指标继承
        if not mql.metric and inherited_mql and inherited_mql.metric:
            mql.metric = inherited_mql.metric

        # 自动注入时序维度（每天/每周/每月/每年）
        if not mql.dimensions:
            question = mql.original_question or ""
            dim_type = self._detect_time_granularity(question)
            if dim_type:
                logger.info(f"[MQLGenerator] 检测到时序粒度: {dim_type}，注入维度")
                mql.dimensions.append(MQLDimension(type=dim_type))
            else:
                logger.info(f"[MQLGenerator] 未检测到时序粒度，原始问题: {question}")

    def _detect_time_granularity(self, question: str) -> Optional[str]:
        """检测问题中的时序粒度关键词

        只有明确说"每天/每周/每月/每年"才触发分组
        """
        if not question:
            return None

        logger.info(f"[_detect_time_granularity] 检查: '{question}'")

        # 精确匹配完整词
        if "每天" in question:
            return "日"
        if "每周" in question:
            return "周"
        if "每月" in question and "月销售额" not in question:
            return "月"
        if "每年" in question and "年销售额" not in question:
            return "年"

        return None

    def _get_default_nl2mql_prompt(self) -> str:
        """默认 NL2MQL prompt"""
        return """【角色】
你是一个专业的业务指标查询助手，擅长将用户的自然语言问题转换为结构化的 MQL (Metric Query Language) JSON。

【MQL JSON Schema】
{{
  "version": "1.0",
  "intent": "query_value|query_trend|query_comparison|query_ranking|query_ratio|query_metadata|greeting|thanks|bye|unknown",
  "confidence": 0.0-1.0,
  "metric": {{
    "code": "留空，不填！由后续系统根据 name 自动查找",
    "name": "指标名称，如 总销售额、客单价、订单量",
    "table": "留空，不填！由后续系统根据 name 自动查找",
    "field": "留空，不填！由后续系统根据 name 自动查找"
  }},
  "time": {{
    "type": "date_range|relative|absolute_month",
    "start": "开始日期(YYYY-MM-DD)",
    "end": "结束日期(YYYY-MM-DD)",
    "original": "原始表达，如 近30天、本月"
  }},
  "dimensions": [
    {{"type": "维度英文名，如 PRODUCT_LINE, PLATFORM, GROUP_3", "column": "留空，由系统映射", "field": "留空", "value": "过滤值"}}
  ],
  "filters": [
    {{"field": "字段名", "operator": "eq|gt|lt|in|between", "value": "值"}}
  ],
  "comparison": {{
    "enabled": true/false,
    "types": ["同比", "环比"]
  }},
  "top_n": 数字,
  "bottom_n": 数字,
  "calculation_patterns": ["yoy", "mom", "percentage", "ranking", "trend", "concentration", "mean", "multiplier", "delta"],
  "molecule_metric": {{"name": "分子指标名称，如 退款数量、亏损金额", "field": "字段名，如 REFUND_QTY", "aggregation": "SUM|AVG|COUNT"}},
  "denominator_metric": {{"name": "分母指标名称，如 销量、销售额", "field": "字段名，如 ORDERED_PRODUCTSALES", "aggregation": "SUM|AVG|COUNT"}}
}}

【意图类型说明】
- query_value: 查询指标数值
- query_trend: 查询趋势变化
- query_comparison: 对比分析（同比/环比）
- query_ranking: 排名分析
- query_ratio: 占比分析
- query_metadata: 查询元数据

【时间类型说明】
- date_range: 日期范围，如 2026-03-01 到 2026-03-15
- relative: 相对表达，如 近30天、本月、上月
- absolute_month: 绝对月份，如 2026-03

【计算模式】
- yoy: 同比
- mom: 环比
- percentage: 占比（必须同时填写 molecule_metric 和 denominator_metric！）
- ranking: 排名
- top_n: Top N
- trend: 趋势
- concentration: 集中度
- mean: 均值
- multiplier: 倍数
- delta: 增量

【占比计算（percentage）填写说明】
当用户询问"XX占YY的比重/比例/占比"时：
1. 设置 calculation_patterns: ["percentage"]
2. molecule_metric: 分子，如 {{"name": "退款数量", "field": "REFUND_QTY", "aggregation": "SUM"}}
3. denominator_metric: 分母，如 {{"name": "销量", "field": "ORDERED_PRODUCTSALES", "aggregation": "SUM"}}
注意：field 字段名必须是 StarRocks 表中实际存在的列名！

【维度类型参考】
- GROUP_1: 一级品类
- GROUP_2: 二级品类
- GROUP_3: 三级品类
- GROUP_4: 四级品类
- SKU: 商品SKU
- FDATE: 日期
- MONTHS: 月份
- WEEKS: 周
- YEARS: 年
- REGION: 地区/区域
- FCOUNTRY: 国家
- PLATFORM: 平台
- FSITE: 站点/店铺
- FCHANNEL: 渠道
- FBRANDS: 品牌
- FPRODUCTLINE: 产品线
- FADTYPE: 广告类型
- AD_TYPE: 广告类型

【时间粒度分组规则】
当用户提到以下时间粒度关键词时，在 dimensions 中返回对应的语义类型（由系统代码映射到数据库列名）：
- "每天"、"按天" → {{"type": "天"}}
- "每周"、"按周" → {{"type": "周"}}
- "每月"、"按月" → {{"type": "月"}}
- "每年"、"按年" → {{"type": "年"}}

示例：
- 用户说"本月每天销售额" → dimensions 应包含 [{{"type": "天"}}]
- 用户说"每周订单量趋势" → dimensions 应包含 [{{"type": "周"}}]

【约束条件】
1. 必须输出合法 JSON
2. 只输出 JSON，不要有其他内容
3. confidence 低于 0.4 时，intent 使用 "unknown"
4. 指标 code/name 从指标库选择，不要瞎编

【上下文】
{context}

【用户问题】
{question}

请输出 JSON："""
