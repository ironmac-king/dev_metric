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

        Args:
            mql: MQLSchema 实例

        Returns:
            (is_valid, error_message)
        """
        if not mql:
            return False, "MQL 为空"

        # 寒暄不需要验证
        if mql.intent in [MQLIntent.GREETING, MQLIntent.THANKS, MQLIntent.BYE]:
            return True, ""

        # 验证指标
        if mql.metric:
            is_valid, error = await self._validate_metric(mql.metric)
            if not is_valid:
                return False, f"指标验证失败: {error}"

        # 验证占比分子指标
        if mql.molecule_metric:
            is_valid, error = await self._validate_metric(mql.molecule_metric)
            if not is_valid:
                logger.warning(f"molecule_metric 验证失败，尝试用 name 查找: {error}")
                # 继续，不阻断流程

        # 验证占比分母指标
        if mql.denominator_metric:
            is_valid, error = await self._validate_metric(mql.denominator_metric)
            if not is_valid:
                logger.warning(f"denominator_metric 验证失败，尝试用 name 查找: {error}")
                # 继续，不阻断流程

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

        return True, ""

    async def _validate_metric(self, metric: MQLMetric) -> Tuple[bool, str]:
        """验证指标并填充 starrocks_sql"""
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
            metric_info = await self._get_metric_info_by_name(metric.name)
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
