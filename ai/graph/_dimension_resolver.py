"""
维度解析模块 - 维度识别、提取、校验
"""
import re
import logging
from typing import Dict, Optional, Any, List

logger = logging.getLogger("ai.nodes")


class DimensionResolver:
    """维度解析器"""

    def __init__(self, metric_client=None):
        self.metric_client = metric_client
        self._table_dimensions_cache = {}

    # ==================== 核心维度识别 ====================

    def extract_ranking_dimension(self, text: str, intent: str) -> Optional[str]:
        """
        从文本中提取排名分析的分组维度

        优先级：
        1. 多级维度精确匹配："二级品类" → 直接返回 "二级品类"
        2. 已知维度变体："品类" → "品类"，"品牌" → "品牌"
        3. 模糊匹配变体："类目" → "品类"

        Returns:
            维度字符串（如"二级品类"、"品类"），或者 None
        """
        ranking_intents = ["query_ranking", "query_value"]
        if intent not in ranking_intents:
            return None

        # 定义维度词及其可能的变体
        dimension_words = {
            "品类": ["品类", "类目", "商品类", "产品类", "category"],
            "品牌": ["品牌", "商标", "牌子", "brand"],
            "渠道": ["渠道", "通路", "channel"],
            "地区": ["地区", "区域", "地域", "省份", "城市", "region"],
            "平台": ["平台", "platform"],
            "国家": ["国家", "country", "国度"],
            "客户": ["客户", "顾客", "买家", "用户", "customer"],
            "商品": ["商品", "产品", "货品", "item", "product"],
            "SKU": ["sku", "SKU", "款号"],
            "ASIN": ["asin", "ASIN"],
            "部门": ["部门", "科室", "team", "department"],
            "设备": ["设备", "device"],
            "广告": ["广告", "ad", "广告计划"],
        }

        # 检测"最高的/最好的/最低的/最差的+维度词"模式
        ranking_patterns = [
            r'最高的\s*(\w+)',
            r'最好的\s*(\w+)',
            r'最低的\s*(\w+)',
            r'最差的\s*(\w+)',
            r'销量最高的\s*(\w+)',
            r'销售最高的\s*(\w+)',
            r'卖得最好的\s*(\w+)',
            r'卖得最差的\s*(\w+)',
            r'最受欢迎的\s*(\w+)',
            r'排名第一的\s*(\w+)',
        ]

        for pattern in ranking_patterns:
            match = re.search(pattern, text)
            if match:
                extracted_dim = match.group(1)

                # Step 1: 先检测 extracted_dim 是否本身就是多级维度词（如"二级品类"）
                multi_level_match = re.match(r'^(一|二|三|四)级(品类|品牌|类目)', extracted_dim)
                if multi_level_match:
                    # 直接返回原始词，不简化
                    logger.debug(f"[extract_ranking_dimension] 检测到多级维度: {extracted_dim}")
                    return extracted_dim

                # Step 2: 按长度降序遍历已知变体，找到最长匹配
                all_variants = []
                for dim_type, dim_variants in dimension_words.items():
                    for variant in dim_variants:
                        all_variants.append((len(variant), variant, dim_type))
                all_variants.sort(key=lambda x: -x[0])  # 长度降序

                for _, variant, dim_type in all_variants:
                    if variant in extracted_dim or extracted_dim in variant:
                        logger.debug(f"[extract_ranking_dimension] 检测到维度: {dim_type} (匹配变体: {variant})")
                        return dim_type

        # 备选：检测"X最高的"或"最高的X"
        for dim_type, dim_variants in dimension_words.items():
            for variant in dim_variants:
                if re.search(rf'{variant}.*最高|最高.*{variant}', text):
                    logger.debug(f"[extract_ranking_dimension] 检测到维度(变体): {dim_type}")
                    return dim_type

        return None

    # ==================== SQL 维度提取 ====================

    def extract_sql_dimensions(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 entities 中提取可用于 SQL 的维度参数
        返回: {"platform": "amazon", "GROUP_2": "...", ...}
        """
        dimensions = {}

        if entities.get("platform"):
            dimensions["platform"] = entities.get("platform")
        if entities.get("region"):
            dimensions["region"] = entities.get("region")
        if entities.get("department"):
            dimensions["department"] = entities.get("department")
        if entities.get("site"):
            dimensions["site"] = entities.get("site")
        if entities.get("category"):
            dimensions["category"] = entities.get("category")
        if entities.get("device"):
            dimensions["device"] = entities.get("device")

        # 品类维度 (GROUP_1, GROUP_2, GROUP_3)
        if entities.get("GROUP_1"):
            dimensions["GROUP_1"] = entities.get("GROUP_1")
        if entities.get("GROUP_2"):
            dimensions["GROUP_2"] = entities.get("GROUP_2")
        if entities.get("GROUP_3"):
            dimensions["GROUP_3"] = entities.get("GROUP_3")

        # SKU, ASIN 等
        if entities.get("SKU"):
            dimensions["SKU"] = entities.get("SKU")
        if entities.get("ASIN"):
            dimensions["ASIN"] = entities.get("ASIN")

        # 时间维度
        for dim_key in ["日", "月", "年", "天", "周"]:
            if entities.get(dim_key):
                dimensions[dim_key] = entities.get(dim_key)

        return dimensions

    # ==================== 维度校验 ====================

    def validate_extracted_dimensions(self, state: Any) -> tuple:
        """
        校验提取的维度是否在 dimensions 表配置中
        返回: (is_valid, error_message)
        """
        dimensions = self.extract_sql_dimensions(state.entities)
        if not dimensions:
            return True, None

        # 品类维度（GROUP_1/2/3, SKU, ASIN）跳过校验
        skip_keys = ["GROUP_1", "GROUP_2", "GROUP_3", "SKU", "ASIN", "日", "月", "年", "天", "周"]
        for dim_key, dim_value in dimensions.items():
            if dim_key in skip_keys:
                continue

            if not self.is_dimension_registered(dim_key, dim_value):
                return False, f"不支持的维度值: {dim_key}={dim_value}"

        return True, None

    def is_dimension_registered(self, dim_type: str, dim_value: str) -> bool:
        """检查维度是否在配置表中注册"""
        return True  # 简化，实际需要查配置表

    # ==================== 维度解析 ====================

    def resolve_dimension(self, dimension: str, dim_configs: Dict[str, Any]) -> str:
        """
        将用户说的维度词解析为数据库列名
        例如："二级品类" → "GROUP_2", "品类" → "GROUP_2"(最长匹配)
        """
        # 优先精确匹配
        if dimension in dim_configs:
            return dim_configs[dimension].get("column_name", dimension)

        # 模糊匹配：收集所有候选，选最长的
        candidates = []
        for dim_name in dim_configs:
            if dimension in dim_name or dim_name in dimension:
                candidates.append(dim_name)

        if candidates:
            matched = max(candidates, key=len)  # 选最长的
            return dim_configs[matched].get("column_name", matched)

        # 子串匹配
        for dim_name in dim_configs:
            if dim_name in dimension:
                return dim_configs[dim_name].get("column_name", dim_name)

        return dimension  # fallback

    # ==================== 维度配置缓存 ====================

    def get_table_dimensions_cached(self, table_name: str) -> Dict[str, Any]:
        """获取表的维度配置，带缓存"""
        if table_name in self._table_dimensions_cache:
            return self._table_dimensions_cache[table_name]

        if not self.metric_client:
            return {}

        try:
            configs = self.metric_client.get_dimension_configs(table_name)
            result = {}
            for cfg in configs:
                if cfg.get("status") == 1:
                    result[cfg["dimension_name"]] = {
                        "column_name": cfg["column_name"],
                        "values": [],  # 简化
                    }
            self._table_dimensions_cache[table_name] = result
            return result
        except Exception as e:
            logger.warning(f"获取维度配置失败: {e}")
            return {}
