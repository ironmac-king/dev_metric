"""
步骤 4/5: MQL 验证器（语法 + 语义）

职责：
- 语法验证：检查 MQL JSON Schema 是否合法
- 语义验证：检查指标、维度、时间等是否有效
"""
from typing import Dict, Any, List, Tuple, Optional
from ai.config.logging_config import get_logger
from ai.engine.llm import get_llm_engine
from ..schema import MQLSchema, MQLIntent, MQLMetric, MQLDimension

logger = get_logger("ai.llm_v2.mql_validator")


class MQLSyntaxValidator:
    """
    MQL 语法验证器

    检查 MQL JSON Schema 是否合法。
    """

    def validate_syntax(self, mql: MQLSchema) -> Tuple[bool, str]:
        """
        验证 MQL 语法

        Args:
            mql: MQLSchema 实例

        Returns:
            (is_valid, error_message)
        """
        if not mql:
            return False, "MQL 为空"

        # 检查意图
        if not mql.intent:
            return False, "缺少意图"

        # 检查意图是否合法
        try:
            MQLIntent(mql.intent.value)
        except ValueError:
            return False, f"非法的意图类型: {mql.intent}"

        # 寒暄意图不需要验证其他字段
        if mql.intent in [MQLIntent.GREETING, MQLIntent.THANKS, MQLIntent.BYE]:
            return True, ""

        # 检查指标
        if not mql.metric and not mql.metrics:
            return False, "缺少指标信息"

        # 检查时间
        if not mql.time:
            return False, "缺少时间范围"

        # 检查维度格式
        for dim in mql.dimensions:
            if not dim.type and not dim.column:
                return False, f"维度信息不完整: {dim}"

        return True, ""


class MQLSemanticValidator:
    """
    MQL 语义验证器

    检查指标、维度、时间等是否在指标库中存在。
    """

    def __init__(self):
        self._llm_engine = get_llm_engine()
        self._metric_cache: Dict[str, Dict[str, Any]] = {}

    async def validate_semantic(self, mql: MQLSchema) -> Tuple[bool, str]:
        """
        验证 MQL 语义

        快速路径：如果指标和占比分子/分母都已填充 starrocks_sql，
        则跳过 MetricClient HTTP 调用，直接做规则验证。
        仅在 starrocks_sql 为空时才调用 API 获取。
        """
        if not mql:
            return False, "MQL 为空"

        # 寒暄不需要验证
        if mql.intent in [MQLIntent.GREETING, MQLIntent.THANKS, MQLIntent.BYE]:
            return True, ""

        # 快速路径：检查是否需要 API 调用
        # 如果 starrocks_sql 已经填充（来自缓存或继承上下文），跳过 HTTP 调用
        needs_metric_api = True
        if mql.metric and mql.metric.starrocks_sql:
            # starrocks_sql 已填充，跳过 metric API 调用
            logger.info(f"[MQLSemanticValidator] 快速路径: metric.starrocks_sql={repr(mql.metric.starrocks_sql[:50] if mql.metric.starrocks_sql else '')}")
            needs_metric_api = False
            # starrocks_sql 已填充，跳过 metric API 调用
            logger.info(f"[MQLSemanticValidator] 快速路径: metric.starrocks_sql 已填充，跳过 API")
            needs_metric_api = False
            # 仍做基本规则检查
            if not mql.metric.starrocks_sql.strip().upper().startswith("SELECT"):
                return False, "starrocks_sql 必须以 SELECT 开头"

        # 快速路径：检查占比指标
        needs_molecule_api = True
        needs_denominator_api = True
        if mql.molecule_metric and mql.molecule_metric.starrocks_sql:
            needs_molecule_api = False
        if mql.denominator_metric and mql.denominator_metric.starrocks_sql:
            needs_denominator_api = False

        # 需要时再调用 API
        if mql.metric and needs_metric_api:
            is_valid, error = await self._validate_metric(mql.metric)
            if not is_valid:
                return False, f"指标验证失败: {error}"

        # 多指标验证：验证 mql.metrics 中的每个指标
        for i, metric in enumerate(mql.metrics):
            if not metric or not metric.name:
                continue
            # 跳过与主指标相同的项
            if mql.metric and metric.name == mql.metric.name:
                continue
            needs_api = not bool(metric.starrocks_sql)
            if needs_api:
                is_valid, error = await self._validate_metric(metric)
                if not is_valid:
                    logger.warning(f"[MQLValidator] 多指标[{i}] '{metric.name}' 验证失败: {error}")
            # 无论是否调用API，都打印starrocks_sql状态
            sql_preview = metric.starrocks_sql[:80] if metric.starrocks_sql else 'EMPTY'
            logger.info(f"[MQLValidator] 多指标[{i}] '{metric.name}' starrocks_sql={sql_preview}")

        if mql.molecule_metric and needs_molecule_api:
            is_valid, error = await self._validate_metric(mql.molecule_metric)
            if not is_valid:
                logger.warning(f"molecule_metric 验证失败，尝试用 name 查找: {error}")

        if mql.denominator_metric and needs_denominator_api:
            is_valid, error = await self._validate_metric(mql.denominator_metric)
            if not is_valid:
                logger.warning(f"denominator_metric 验证失败，尝试用 name 查找: {error}")

        # 验证维度
        for dim in mql.dimensions:
            is_valid, error = self._validate_dimension(dim)
            if not is_valid:
                return False, f"维度验证失败: {error}"

        # 验证时间
        if mql.time:
            is_valid, error = self._validate_time(mql.time)
            if not is_valid:
                return False, f"时间验证失败: {error}"

        # 验证并清理无效 filters（字段必须是维度配置表中的列）
        self._validate_filters(mql)

        return True, ""

    async def _validate_metric(self, metric: MQLMetric) -> Tuple[bool, str]:
        """验证指标并填充 starrocks_sql"""
        logger.info(f"[_validate_metric] ENTRY: code={metric.code!r}, name={metric.name!r}, starrocks_sql={metric.starrocks_sql!r}")
        # 如果有 code，尝试从指标库获取 starrocks_sql
        if metric.code:
            metric_info = await self._get_metric_info(metric.code)
            if metric_info:
                # 验证：LLM 返回的 code 是否与 metric.name 匹配
                # 如果 LLM 返回了错误的 code（例如用户问"客单价"但返回了 MKI-02-0011 广告转化率），
                # 应该拒绝这个 code，fallback 到 name 查找
                code_metric_name = metric_info.get("name", "") or metric_info.get("metric_name", "")
                if metric.name and code_metric_name:
                    # 检查 name 是否匹配（忽略大小写和空格）
                    if not self._is_metric_name_match(metric.name, code_metric_name):
                        logger.warning(f"[_validate_metric] LLM 返回的 code 与 metric.name 不匹配: code={metric.code}, code_metric_name={code_metric_name}, metric.name={metric.name}，拒绝该 code，fallback 到 name 查找")
                        # 拒绝 code，fallback 到 name 查找
                        if metric.name:
                            metric_info_by_name = await self._get_metric_info_by_name(metric.name)
                            if metric_info_by_name:
                                metric.code = metric_info_by_name.get("metric_code", metric.code)
                                if not metric.starrocks_sql and metric_info_by_name.get("starrocks_sql"):
                                    metric.starrocks_sql = metric_info_by_name.get("starrocks_sql", "")
                                if not metric.table and metric_info_by_name.get("starrocks_table"):
                                    metric.table = metric_info_by_name.get("starrocks_table", "")
                                # 强制用数据库值覆盖 LLM 幻觉的字段
                                if metric_info_by_name.get("starrocks_field"):
                                    metric.field = metric_info_by_name.get("starrocks_field", "")
                                logger.info(f"[_validate_metric] 通过 name 找到指标: name={metric.name}, code={metric.code}, sql={metric.starrocks_sql[:50] if metric.starrocks_sql else 'None'}...")
                        # 继续验证 starrocks_sql
                        if metric.starrocks_sql:
                            sql = metric.starrocks_sql.strip().upper()
                            if not sql.startswith("SELECT"):
                                return False, "starrocks_sql 必须以 SELECT 开头"
                        return True, ""

                # 填充 starrocks_sql（这是最关键的字段）
                if not metric.starrocks_sql and metric_info.get("starrocks_sql"):
                    metric.starrocks_sql = metric_info.get("starrocks_sql", "")
                # 填充 table
                if not metric.table and metric_info.get("starrocks_table"):
                    metric.table = metric_info.get("starrocks_table", "")
                # 强制用数据库值覆盖 LLM 幻觉的字段
                if metric_info.get("starrocks_field"):
                    metric.field = metric_info.get("starrocks_field", "")
                logger.info(f"[_validate_metric] 填充 starrocks_sql: code={metric.code}, sql={metric.starrocks_sql[:80]}...")
            else:
                logger.warning(f"[_validate_metric] 未找到指标，尝试通过名称查找: code={metric.code}")
                # code 不存在时，通过 name 查找
                if metric.name:
                    metric_info = await self._get_metric_info_by_name(metric.name)
                    if metric_info:
                        metric.code = metric_info.get("metric_code", metric.code)
                        if not metric.starrocks_sql and metric_info.get("starrocks_sql"):
                            metric.starrocks_sql = metric_info.get("starrocks_sql", "")
                        if not metric.table and metric_info.get("starrocks_table"):
                            metric.table = metric_info.get("starrocks_table", "")
                        # 强制用数据库值覆盖 LLM 幻觉的字段（LLM 字段名经常是错的）
                        if metric_info.get("starrocks_field"):
                            metric.field = metric_info.get("starrocks_field", "")
                        logger.info(f"[_validate_metric] 通过 name 找到指标: name={metric.name}, code={metric.code}, sql={metric.starrocks_sql[:50] if metric.starrocks_sql else 'None'}...")

        # 如果没有 code 但有 name，尝试通过 name 查找
        if not metric.code and metric.name:
            logger.info(f"[_validate_metric] 通过 name 查找: metric.name={repr(metric.name)}")
            metric_info = await self._get_metric_info_by_name(metric.name)
            logger.info(f"[_validate_metric] name 查找结果: metric_info is None={metric_info is None}")
            if metric_info:
                logger.info(f"[_validate_metric] metric_info keys: {list(metric_info.keys())}")
            if metric_info:
                metric.code = metric_info.get("metric_code", metric.code)
                if not metric.starrocks_sql and metric_info.get("starrocks_sql"):
                    metric.starrocks_sql = metric_info.get("starrocks_sql", "")
                if not metric.table and metric_info.get("starrocks_table"):
                    metric.table = metric_info.get("starrocks_table", "")
                # 强制用数据库值覆盖 LLM 幻觉的字段
                if metric_info.get("starrocks_field"):
                    metric.field = metric_info.get("starrocks_field", "")
                logger.info(f"[_validate_metric] 通过 name 填充: name={metric.name}, code={metric.code}, field={metric.field}")

        # 如果 starrocks_sql 存在，验证 SQL 是否有效
        if metric.starrocks_sql:
            # 基本语法检查
            sql = metric.starrocks_sql.strip().upper()
            if not sql.startswith("SELECT"):
                return False, "starrocks_sql 必须以 SELECT 开头"

        return True, ""

    def _validate_dimension(self, dim: MQLDimension) -> Tuple[bool, str]:
        """验证维度"""
        # TODO: 从维度配置表验证
        # valid_dimensions = self._get_valid_dimensions()
        # if dim.type and dim.type not in valid_dimensions:
        #     return False, f"非法的维度类型: {dim.type}"
        return True, ""

    def _validate_time(self, time_obj) -> Tuple[bool, str]:
        """验证时间"""
        # TODO: 验证时间格式
        if time_obj.original:
            # 基本检查
            if len(time_obj.original) > 50:
                return False, "时间表达式过长"

        if time_obj.start and time_obj.end:
            # 检查日期格式
            import re
            date_pattern = r"^\d{4}-\d{2}-\d{2}$"
            if not re.match(date_pattern, time_obj.start):
                return False, f"开始日期格式错误: {time_obj.start}"
            if not re.match(date_pattern, time_obj.end):
                return False, f"结束日期格式错误: {time_obj.end}"

        return True, ""

    def _is_metric_name_match(self, name1: str, name2: str) -> bool:
        """
        检查两个指标名称是否匹配

        匹配逻辑：
        1. 精确匹配（忽略大小写和空格）
        2. 中文关键词匹配（包含对方则匹配）
        3. 英文别名匹配（通过常见的翻译对）
        """
        if not name1 or not name2:
            return False

        # 标准化：去除空格、转小写
        n1 = name1.strip().lower()
        n2 = name2.strip().lower()

        # 1. 精确匹配
        if n1 == n2:
            return True

        # 2. 包含匹配（用于"客单价"匹配"平均客单价"等场景）
        if n1 in n2 or n2 in n1:
            return True

        # 3. 常见中文-英文指标名映射
        chinese_to_english = {
            "销售额": ["sales", "totalsales", "ordered_product_sales", "product_sales"],
            "订单量": ["order", "total_orders", "orders", "totalorder"],
            "访客数": ["visitor", "visits", "sessions", "traffic"],
            "客单价": ["aov", "average_order_value", "averageordervalue", "per_order"],
            "转化率": ["cvr", "conversion", "conversion_rate", "rate"],
            "广告花费": ["ad_cost", "advertising_cost", "spend", "adspend"],
            "点击率": ["ctr", "click_rate", "clickrate", "click_through"],
            "毛利": ["gross_profit", "profit", "margin"],
            "毛利率": ["gross_margin", "margin_rate", "profit_rate"],
        }

        # 检查是否是同一个指标的不同表达
        for cn_name, en_names in chinese_to_english.items():
            # 如果 name1 是中文，且 name2 是对应的英文
            if cn_name in n1:
                for en_name in en_names:
                    if en_name in n2:
                        return True
            # 如果 name2 是中文，且 name1 是对应的英文
            if cn_name in n2:
                for en_name in en_names:
                    if en_name in n1:
                        return True

        return False

    async def _get_metric_info(self, metric_code: str) -> Optional[Dict[str, Any]]:
        """从指标库获取指标信息"""
        if metric_code in self._metric_cache:
            return self._metric_cache[metric_code]

        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            info = client.get_metric_by_code(metric_code)
            if info:
                self._metric_cache[metric_code] = info
            return info
        except Exception as e:
            logger.warning(f"获取指标信息失败: {e}")
            return None

    async def _get_metric_info_by_name(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """从指标库通过名称获取指标信息"""
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            info = client.get_metric_by_name(metric_name)
            return info
        except Exception as e:
            logger.warning(f"获取指标信息失败: {e}")
            return None

    def _validate_filters(self, mql: MQLSchema):
        """
        验证并清理无效 filters

        规则：
        1. filter 字段必须是维度配置表中的有效列名
        2. filter 值必须在原始问题中明确提到（且前面有维度关键词：渠道/店铺/品牌/平台/国家等）
        3. 如果 filter 的值只是指标名的一部分，不认为是过滤值
        """
        if not mql.filters:
            return

        # 获取原始问题文本
        original_question = mql.original_question or ""

        # 有效字段列表（从维度配置表获取）
        valid_columns = self._get_valid_filter_columns()
        valid_columns_upper = {c.upper() for c in valid_columns}

        # 维度关键词（filter 值必须紧跟这些词后面，才认为用户明确指定了过滤，使用 DimensionService 消除硬编码）
        try:
            from ai.services.dimension_service import DimensionService
            dimension_keywords = DimensionService().get_keywords()
        except Exception:
            dimension_keywords = ["渠道", "店铺", "品牌", "平台", "国家", "地区", "区域", "站点", "品类", "类目", "产品", "商品"]

        original_count = len(mql.filters)
        logger.warning(f"[_validate_filters] ENTRY: {len(mql.filters)} filters, question={original_question[:50]}")
        valid_filters = []
        for f in mql.filters:
            if not f.field:
                continue

            # 规则1：检查字段是否有效（忽略大小写）
            if f.field.upper() not in valid_columns_upper:
                logger.warning(f"[_validate_filters] 过滤字段不在维度配置表中，已丢弃: field={f.field}, value={f.value}")
                continue

            # 规则2：检查 filter 值是否在原始问题中明确提到（且紧跟维度关键词）
            if f.value:
                value_str = str(f.value).strip()
                if value_str:
                    # 如果 filter 是从指标名中校正得到的（source="corrected"），跳过"紧跟维度关键词"检查
                    # 如果 filter 来自 intent_router 本地模型（source="user"），也跳过检查，因为本地模型已验证过
                    if f.source not in ("corrected", "user"):
                        # 检查是否紧跟维度关键词（说明用户明确指定了过滤）
                        # 例如："自然渠道" → 值"自然"前面有"渠道" → 有效
                        # 例如："自然订单量" → 值"自然"前面没有维度关键词 → 无效（是指标名的一部分）
                        is_valid_filter = False
                        for kw in dimension_keywords:
                            # 检查 value_str 是否紧跟在 kw 后面（中间无其他字符）
                            pattern = kw + value_str
                            if pattern in original_question:
                                is_valid_filter = True
                                break

                        if not is_valid_filter:
                            logger.warning(f"[_validate_filters] filter值不是紧跟维度关键词，可能是指标名的一部分，已丢弃: field={f.field}, value={f.value}, question={original_question}")
                            continue

            valid_filters.append(f)

        mql.filters = valid_filters
        logger.warning(f"[_validate_filters] EXIT: {original_count} -> {len(valid_filters)} filters")
        if len(mql.filters) < original_count:
            logger.info(f"[_validate_filters] 过滤条件清理完成: {original_count} -> {len(mql.filters)}")

    def _get_valid_filter_columns(self) -> set:
        """
        获取有效的过滤字段列表

        从 SQLGeneratorNode 的维度映射和维度配置表获取有效列名
        """
        # 从 SQLGeneratorNode 获取基础列名
        from ..nodes.sql_generator import SQLGeneratorNode
        gen = SQLGeneratorNode()
        valid_columns = set(gen.DIMENSION_COLUMN_MAP.values())

        # 补充时间相关列
        valid_columns.update({"FDATE", "MONTHS", "YEARS", "WEEKS", "QUARTERS"})

        # 尝试从维度配置表获取更多有效列
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            configs = client.get_dimension_configs()
            for cfg in configs:
                col = cfg.get("column_name")
                if col:
                    valid_columns.add(col)
        except Exception as e:
            logger.warning(f"[_get_valid_filter_columns] 获取维度配置失败: {e}")

        return valid_columns
