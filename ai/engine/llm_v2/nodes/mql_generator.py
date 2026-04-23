"""
步骤 3: MQL 生成智能体

职责：
- 将自然语言转换为 MQL（Metric Query Language）
- 处理多轮对话上下文
- 应用 RAG 上下文
"""
import json
from string import Template
from typing import Dict, Any, List, Optional
from ai.config.logging_config import get_logger
from ai.engine.prompt_manager import get_prompt_manager
from ai.engine.llm import get_llm_engine
from ..schema import MQLSchema, MQLIntent, MQLMetric, MQLDimension, MQLFilter, TimeRange, TimeType, OperatorType
from ..cache import get_history_reuse_cache

logger = get_logger("ai.llm_v2.mql_generator")


class MQLGenerator:
    """
    MQL 生成智能体

    使用 LLM 将自然语言转换为 MQL 结构化查询。
    """

    def __init__(self):
        self._prompt_manager = get_prompt_manager()
        self._llm_engine = get_llm_engine()
        self._dimension_name_to_column = None  # 动态维度映射

    def _load_dimension_configs(self):
        """从 API 加载维度配置，构建 dimension_name → column_name 映射"""
        if self._dimension_name_to_column is not None:
            return
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            configs = client.get_dimension_configs()
            if configs:
                self._dimension_name_to_column = {}
                for cfg in configs:
                    dimName = cfg.get("dimension_name", "")
                    colName = cfg.get("column_name", "")
                    if dimName and colName:
                        self._dimension_name_to_column[dimName] = colName
                logger.info(f"[MQLGenerator] 从 dimension_configs 加载了 {len(self._dimension_name_to_column)} 个维度映射")
        except Exception as e:
            logger.warning(f"[MQLGenerator] 加载 dimension_configs 失败: {e}")
            self._dimension_name_to_column = None

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
            # 0. 查历史缓存（优化：相似问题直接复用，跳过 LLM 调用）
            # 注意：对于追问（source=followup），跳过缓存以保留从 intent_router 继承的 comparison 和 dimensions
            history_cache = get_history_reuse_cache()
            # 检查是否是追问场景（通过 inherited_mql 判断）
            is_followup = inherited_mql is not None
            if not is_followup:
                # 非追问场景才查缓存
                cached = history_cache.find_similar(question, threshold=0.75)
            else:
                # 追问场景跳过缓存
                cached = None
            if cached:
                cached_mql_dict = cached.get("mql")
                if cached_mql_dict:
                    try:
                        cached_mql = MQLSchema.from_dict(cached_mql_dict)

                        # ========== 修复：检查维度兼容性 ==========
                        # 动态获取维度关键词（从数据库加载）
                        dim_keywords = self._get_dimension_keywords_list()
                        current_has_dim = any(kw in question for kw in dim_keywords)
                        cached_has_dim = cached_mql.dimensions and len(cached_mql.dimensions) > 0

                        # 如果缓存有维度但当前问题没有维度，清除维度继承
                        if cached_has_dim and not current_has_dim:
                            logger.warning("[MQLGenerator] 缓存MQL有维度但当前问题无维度，清除维度继承")
                            cached_mql.dimensions = []
                        # ===========================================

                        logger.info(f"[MQLGenerator] 历史缓存命中，跳过 LLM 调用: {question[:30]}...")
                        # 继承上下文
                        if inherited_mql:
                            cached_mql.session_id = inherited_mql.session_id
                            cached_mql.parent_state_id = inherited_mql.session_id
                            # 继承 starrocks_sql（缓存的 MQL 没有经过 validator，starrocks_sql 为空）
                            if inherited_mql.metric and inherited_mql.metric.starrocks_sql:
                                cached_mql.metric.starrocks_sql = inherited_mql.metric.starrocks_sql
                            if inherited_mql.metric and inherited_mql.metric.table:
                                cached_mql.metric.table = inherited_mql.metric.table
                        # 即使命中缓存也要尝试校正指标名中的维度值（如"智能云存储销售额"→"销售额"）
                        self._correct_dimension_value_in_metric_name(cached_mql)
                        return cached_mql
                    except Exception as e:
                        logger.warning(f"[MQLGenerator] 缓存 MQL 解析失败: {e}，继续 LLM 生成")

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

            # 6. 写入历史缓存
            try:
                history_cache.add(question, mql.to_dict())
            except Exception as e:
                logger.warning(f"[MQLGenerator] 历史缓存写入失败: {e}")

            return mql

        except json.JSONDecodeError as e:
            logger.error(f"[MQLGenerator] JSON 解析失败: {e}")
            return None
        except Exception as e:
            import traceback
            logger.error(f"[MQLGenerator] 错误: {e}\n{traceback.format_exc()}")
            return None

    def _get_dimension_keywords_list(self) -> list:
        """从 dimension-type-mappings API 获取维度关键词列表（含同义词扩展）"""
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            mappings = client.get_dimension_type_mappings()
            keywords = set()
            for m in mappings:
                dim_type = m.get("dimension_type", "")
                if dim_type and len(dim_type) < 20:
                    keywords.add(dim_type)
            # 添加同义词扩展（从 business_terms）
            synonym_map, _ = self._load_business_terms()
            for syn, canonical in synonym_map.items():
                if syn and canonical and len(syn) < 10:
                    keywords.add(syn)
            return list(keywords) if keywords else ["渠道", "店铺", "品牌", "平台", "国家", "地区", "品类", "商品"]
        except Exception as e:
            logger.warning(f"[_get_dimension_keywords_list] 获取维度关键词失败: {e}")
            return ["渠道", "店铺", "品牌", "平台", "国家", "地区", "品类", "商品"]

    def _get_dimension_keywords_str(self) -> str:
        """获取维度关键词字符串（供 prompt 使用）"""
        return "、".join(self._get_dimension_keywords_list())

    def _load_business_terms(self) -> tuple:
        """
        从 business_terms 表加载同义词映射和有效值集合
        返回: (synonym_map, valid_values_set)
        synonym_map: Dict[str, str] = {用户词: 标准值}
        valid_values: set = 所有有效的维度值集合
        """
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            terms = client.get_business_terms()
            synonym_map = {}   # 用户词 -> 标准值
            valid_values = set()  # 所有有效的维度值
            for t in terms:
                canonical = t.get("dimension_value", "")
                synonyms = t.get("synonyms") or []
                # 处理 PostgreSQL 数组格式字符串
                if isinstance(synonyms, str):
                    synonyms = [s.strip().strip('"') for s in synonyms.strip("{}").split(",") if s.strip()]
                if canonical:
                    valid_values.add(canonical)
                    synonym_map[canonical] = canonical
                for syn in synonyms:
                    valid_values.add(syn)
                    synonym_map[syn] = canonical
            return synonym_map, valid_values
        except Exception as e:
            logger.warning(f"[_load_business_terms] 加载业务术语失败: {e}")
            return {}, set()

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
            # ========== 修复：增加维度清除指令 ==========
            context_parts.append("  注意: 如果当前问题没有提到任何维度（如'品类'、'渠道'等），请将维度设为空，不要继承上轮维度！")
            # ===========================================

        # 维度值上下文（从 dim_value_mapping 查询）
        dim_values_context = self._get_dimension_values_context()
        if dim_values_context:
            context_parts.append("\n【维度值参考】")
            context_parts.append(dim_values_context)

        context_str = "\n".join(context_parts) if context_parts else "（无历史上下文）"

        # 动态获取中文维度关键词
        dim_keywords_str = self._get_dimension_keywords_str()

        # 填充 prompt - 使用自定义安全格式化，只替换指定的占位符
        # 注意：不能用 str.format() 因为 prompt 中有 JSON 示例如 {"field": ...}
        # Python 会把 {field} 当作占位符导致 KeyError
        return self._safe_format(
            prompt_template,
            question=question,
            context=context_str,
            dimension_keywords=dim_keywords_str,
        )

    def _safe_format(self, template: str, **kwargs) -> str:
        """安全的字符串格式化，只替换指定的占位符

        Args:
            template: 包含 {question}, {context}, {dimension_keywords} 的模板
            **kwargs: 要替换的值

        Returns:
            格式化后的字符串
        """
        # 只替换我们知道的占位符，不处理其他 {xxx}
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            if placeholder in template:
                template = template.replace(placeholder, str(value))
        return template

    def _get_dimension_values_context(self) -> str:
        """从 dim_value_mapping 获取维度值上下文（使用 DimensionService 消除硬编码）"""
        try:
            from ai.services.dimension_service import DimensionService
            svc = DimensionService()
            return svc.get_dimension_values_context()
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

        # 检查用户是否提到了具体级别（使用 DimensionService 消除硬编码）
        try:
            from ai.services.dimension_service import DimensionService
            level_keywords = DimensionService().get_level_keywords()
        except Exception:
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

        # 多指标支持（如"销售额及销量"）
        metrics_data = result.get("metrics", [])
        if metrics_data:
            for metric_item in metrics_data:
                metric_name = metric_item.get("name", "")
                if metric_name and (not mql.metric or mql.metric.name != metric_name):
                    # 跳过与主指标相同的项，避免重复
                    mql.metrics.append(MQLMetric(
                        code="",
                        name=metric_name,
                        table="",
                        field="",
                        unit=metric_item.get("unit", ""),
                        starrocks_sql="",
                    ))
            logger.info(f"[_parse_mql] 解析到多指标: {[m.name for m in mql.metrics]}")

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

        # 加载 dimension_configs 动态映射
        self._load_dimension_configs()

        # 维度 - 中文到英文的映射（动态加载优先，硬编码作为回退）
        # dimension_configs 返回 dimension_name → column_name 的映射
        dim_type_map = {}
        if self._dimension_name_to_column:
            dim_type_map.update(self._dimension_name_to_column)

        # 硬编码映射作为回退（处理 dimension_configs 中没有的情况，使用 DimensionService 动态获取）
        try:
            from ai.services.dimension_service import DimensionService
            fallback_map = DimensionService().get_fallback_map()
        except Exception:
            fallback_map = {
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
        for k, v in fallback_map.items():
            if k not in dim_type_map:
                dim_type_map[k] = v

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

        # 筛选 - 只有用户明确指定时才添加
        # 验证规则：filter 值必须紧跟维度关键词（动态从 API 获取）
        # 允许两种顺序：关键词+值（如"渠道自然"）或 值+关键词（如"自然渠道"）
        dimension_keywords = self._get_dimension_keywords_list()
        synonym_map, valid_values = self._load_business_terms()
        metric_name = mql.metric.name if mql.metric else ""

        for filter_data in result.get("filters", []):
            from ..schema import MQLFilter, OperatorType
            try:
                filter_value = filter_data.get("value")
                field = filter_data.get("field", "")

                # 验证 filter 值是否在原始问题中紧跟维度关键词出现
                is_valid_filter = False
                if filter_value:
                    value_str = str(filter_value).strip()
                    # 1. 标准化：同义词映射到标准值
                    normalized_value = synonym_map.get(value_str, value_str)

                    for kw in dimension_keywords:
                        # 检查两种顺序：kw+value 或 value+kw（使用原值和标准化值）
                        patterns = [
                            kw + value_str, value_str + kw,
                            kw + normalized_value, normalized_value + kw
                        ]
                        if any(p in question for p in patterns):
                            is_valid_filter = True
                            logger.info(f"[_parse_mql] 验证通过: filter field={field}, value={filter_value} 紧跟维度关键词'{kw}'")
                            break

                    # 2. 值验证：确保是有效的业务术语
                    if is_valid_filter and value_str:
                        if value_str not in valid_values and normalized_value not in valid_values:
                            logger.warning(f"[_parse_mql] filter值无效（不在business_terms中）: field={field}, value={value_str}")
                            is_valid_filter = False
                        # 3. 排除指标名一部分的情况
                        elif value_str in metric_name or normalized_value in metric_name:
                            logger.warning(f"[_parse_mql] filter值是指标名一部分: field={field}, value={value_str}, metric_name={metric_name}")
                            is_valid_filter = False

                if is_valid_filter:
                    mql.filters.append(MQLFilter(
                        field=field,
                        operator=OperatorType(filter_data.get("operator", "eq")),
                        value=filter_value,
                    ))
                else:
                    logger.warning(f"[_parse_mql] 丢弃无效 filter: field={field}, value={filter_value}, question={question[:50]}...")
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
        # 如果新 MQL 的 metric 存在但 starrocks_sql 为空，从 inherited_mql 继承
        elif mql.metric and inherited_mql and inherited_mql.metric and inherited_mql.metric.starrocks_sql:
            if not mql.metric.starrocks_sql:
                mql.metric.starrocks_sql = inherited_mql.metric.starrocks_sql
                logger.info(f"[_fill_defaults] 从 inherited_mql 继承 starrocks_sql")

        # Top N 继承（用于排名查询的追问回复）
        if inherited_mql and inherited_mql.top_n and inherited_mql.top_n > 0:
            mql.top_n = inherited_mql.top_n

        # Order By 继承
        if not mql.order_by and inherited_mql and inherited_mql.order_by:
            mql.order_by = inherited_mql.order_by

        # 自动注入时序维度（每天/每周/每月/每年）
        if not mql.dimensions:
            question = mql.original_question or ""
            dim_type = self._detect_time_granularity(question)
            if dim_type:
                logger.info(f"[MQLGenerator] 检测到时序粒度: {dim_type}，注入维度")
                mql.dimensions.append(MQLDimension(type=dim_type))
            else:
                logger.info(f"[MQLGenerator] 未检测到时序粒度，原始问题: {question}")

        # ========== 后处理：修正指标名中的维度值 ==========
        # 如果指标名包含"XXX销售额"且XXX是维度值（如"智能云存储"），
        # 从指标名中剔除XXX，生成对应 filter
        self._correct_dimension_value_in_metric_name(mql)

    def _correct_dimension_value_in_metric_name(self, mql: MQLSchema):
        """从问题文本中识别维度值并生成 filter

        策略：解析维度值上下文，建立 (dimension_value → column) 映射。
        然后在原始问题中搜索这些维度值。
        如果某维度值紧贴在指标名左侧（如"智能云存储销售额"），
        则认为它是维度值而非指标名的一部分，剥离并生成 filter。
        """
        if not mql or not mql.metric or not mql.metric.name:
            return

        metric_name = mql.metric.name
        question = mql.original_question or ""

        # 如果 original_question 为空，说明该 MQL 来自缓存且已被校正过，跳过
        if not question:
            logger.warning(f"[_correct_dimension_value_in_metric_name] original_question 为空（来自缓存），跳过校正")
            return

        # 指标名后缀（用于判断维度值和指标的边界）
        metric_suffixes = ["销售额", "订单量", "转化率", "用户数", "访问量", "成交量", "点击量", "展示量"]

        # 获取维度值上下文
        dim_values_context = self._get_dimension_values_context()
        if not dim_values_context:
            logger.warning(f"[_correct_dimension_value_in_metric_name] 维度上下文为空，跳过")
            return

        logger.warning(f"[_correct_dimension_value_in_metric_name] 检查: metric_name='{metric_name}', question='{question}', 上下文长度={len(dim_values_context)}")

        import re
        # 解析维度值上下文，建立 (dimension_value → column_name) 映射
        # 格式: "GROUP_1(一级品类): 充电创意, 智能影音..."
        dim_value_to_column = {}
        for line in dim_values_context.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            m = re.match(r"^(\w+)(?:\([^)]+\))?:(.+)$", line)
            if m:
                col = m.group(1)
                values_part = m.group(2)
                for val in values_part.split(","):
                    val = val.strip().strip("'\"")
                    if val and len(val) >= 2:
                        dim_value_to_column[val] = col

        if not dim_value_to_column:
            logger.warning(f"[_correct_dimension_value_in_metric_name] 无法解析维度值上下文，跳过")
            return

        # 从问题中搜索维度值（优先匹配长词）
        found_dim_values = []  # [(dim_value, column), ...]
        for dim_val, col in dim_value_to_column.items():
            if dim_val in question:
                # 检查是否紧贴在指标名左侧（维度值 + 指标后缀 的模式）
                for suffix in metric_suffixes:
                    combined = dim_val + suffix
                    if combined in question:
                        found_dim_values.append((dim_val, col))
                        break
                    # 也检查 "X的Y销售额" 模式
                    pattern = rf"{re.escape(dim_val)}的{suffix}"
                    if re.search(pattern, question):
                        found_dim_values.append((dim_val, col))
                        break

        logger.warning(f"[_correct_dimension_value_in_metric_name] 从问题中找到维度值: {found_dim_values}")

        for dim_val, dim_field in found_dim_values:
            # 如果已有 user filter 的同字段，说明 intent_router 已处理，不再加 corrected filter
            has_user_filter = any(
                (hasattr(f, 'field') and f.field == dim_field and hasattr(f, 'source') and f.source == "user")
                for f in mql.filters
            )
            if has_user_filter:
                logger.info(f"[_correct_dimension_value_in_metric_name] field={dim_field} 已有 user filter，跳过添加 corrected filter")
                continue

            # 检查是否已经在 filters 或 dimensions 中（field OR value 任一匹配即跳过）
            already_filtered = any(
                (hasattr(f, 'field') and f.field == dim_field) or
                (hasattr(f, 'value') and f.value == dim_val)
                for f in mql.filters
            )
            if already_filtered:
                continue

            already_dim_value = any(d.value == dim_val for d in mql.dimensions)
            if already_dim_value:
                continue

            # 从指标名中剔除维度值，生成 filter
            new_metric_name = metric_name.replace(dim_val, "").strip()
            if new_metric_name and new_metric_name != metric_name:
                logger.warning(f"[_correct_dimension_value_in_metric_name] "
                             f"从指标名'{metric_name}'中剔除维度值'{dim_val}', "
                             f"新指标名'{new_metric_name}', 生成 filter {dim_field}='{dim_val}'")
                mql.metric.name = new_metric_name
                mql.filters.append(MQLFilter(
                    field=dim_field,
                    operator=OperatorType.EQ,
                    value=dim_val,
                    source="corrected",
                ))

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
- FSITE: 店铺
- FSITECODE: 站点
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

【Filter 生成规则】（重要！）
1. 只在用户**明确指定**维度过滤时才生成 filter
2. "明确指定"定义：用户问题中出现了"维度关键词+具体值"模式
   - ✓ 正确："自然渠道的转化率" → 生成 filter {"field": "FCHANNEL", "value": "自然"}
   - ✗ 错误："自然订单量是多少" → 不生成 filter（"自然"是指标名一部分，不是渠道值）
   - ✗ 错误："广告花费多少" → 不生成 filter（"广告"是指标名，不是过滤值）
3. filter 值不能是指标名的一部分
4. 维度关键词：{dimension_keywords}

【反面示例】
- 问题："自然订单量是多少" → filters: []（不生成！自然是指标名"自然订单量"的一部分）
- 问题："广告花费多少" → filters: []（不生成！广告是指标名，不是过滤值）
- 问题："自然渠道的转化率" → filters: [{"field": "FCHANNEL", "value": "自然"}]

【上下文】
{context}

【用户问题】
{question}

请输出 JSON："""
