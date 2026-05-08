"""
统一维度服务：所有维度数据从 Go 后端 dim_value_mapping 表获取，消除硬编码。
单例模式，类级缓存。
"""
import httpx
import threading
from typing import List, Dict, Any, Optional, Set
from ai.config.logging_config import get_logger
from ai.config.runtime import get_go_api_base

logger = get_logger("ai.dimension_service")

# 全局 HTTP 客户端
_http_client: Optional[httpx.Client] = None


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=15.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    return _http_client


class DimensionService:
    """
    统一维度服务，单例。
    所有维度数据从 Go 后端 /api/v1/dimension-values/* 获取。
    """
    _instance: Optional['DimensionService'] = None
    _lock = threading.Lock()

    # 类级缓存：所有实例共享
    _types_cache: Optional[List[Dict[str, str]]] = None  # [{column_name, dimension_type, table_name}, ...]
    _column_values_cache: Dict[str, List[Dict[str, Any]]] = {}  # column_name -> list of {dimension_value, ...}
    _values_search_cache: Dict[str, List[Dict[str, Any]]] = {}  # "query:column" -> results
    _cache_time: Dict[str, float] = {}
    _cache_ttl = 300.0  # 5分钟缓存

    def __new__(cls, base_url: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._base_url = base_url or get_go_api_base()
        elif base_url:
            cls._instance._base_url = base_url
        return cls._instance

    def __init__(self, base_url: str = None):
        if base_url:
            self._base_url = base_url

    def _api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """调用 Go 后端 API"""
        client = _get_http_client()
        url = f"{self._base_url}{path}"
        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception as e:
            logger.warning(f"[DimensionService] API 调用失败: {url} {e}")
            return None

    def _api_post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """POST 调用 Go 后端 API"""
        client = _get_http_client()
        url = f"{self._base_url}{path}"
        try:
            resp = client.post(url, json=json)
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception as e:
            logger.warning(f"[DimensionService] API POST 失败: {url} {e}")
            return None

    # ==================== 核心查询方法 ====================

    def get_all_types(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """
        获取所有 column_name + dimension_type 对（去重）。
        用于消除 intent_router.py 的 dimension_codes 硬编码。
        返回: [{"column_name": "PLATFORM", "dimension_type": "平台", "table_name": "..."}, ...]
        """
        if use_cache and DimensionService._types_cache is not None:
            return DimensionService._types_cache

        data = self._api_get("/api/v1/dimension-type-mappings")
        if data is not None:
            DimensionService._types_cache = data
        else:
            DimensionService._types_cache = []
        return DimensionService._types_cache

    def get_by_column_name(self, column_name: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        获取某列的所有维度值（非空的 dimension_value 记录）。
        用于 MQL Generator prompt 注入维度值上下文。
        """
        cache_key = column_name
        if use_cache and cache_key in DimensionService._column_values_cache:
            return DimensionService._column_values_cache[cache_key]

        data = self._api_get("/api/v1/dimension-values", params={
            "column_name": column_name,
            "page": 1,
            "page_size": 500,
        })
        items = []
        if data:
            items = data.get("list", []) if isinstance(data, dict) else data
        DimensionService._column_values_cache[cache_key] = items
        return items

    def search_by_value(
        self,
        query: str,
        column_name: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        搜索维度值（模糊匹配 dimension_value）。
        """
        cache_key = f"{query}:{column_name or ''}:{limit}"
        if cache_key in DimensionService._values_search_cache:
            return DimensionService._values_search_cache[cache_key]

        params = {"query": query, "limit": limit}
        if column_name:
            params["column_name"] = column_name

        data = self._api_get("/api/v1/dimension-values/search", params=params)
        items = data if data else []
        DimensionService._values_search_cache[cache_key] = items
        return items

    def find_column_by_value(self, dimension_value: str) -> Optional[str]:
        """
        通过维度值找 column_name（NER 识别 DIM_VALUE 但不知 column 时用）。
        例如："智能云存储" -> "GROUP_2"
        匹配策略：维度值 → 维度类型(fallback) → None
        """
        results = self.search_by_value(dimension_value, limit=5)
        for r in results:
            if str(r.get("dimension_value", "")) == dimension_value:
                return r.get("column_name")
        # 模糊匹配第一个
        if results:
            return results[0].get("column_name")
        # Fallback: 尝试按 dimension_type 匹配（传入的值可能是类型名不是值）
        return self.find_column_by_type(dimension_value)

    def find_column_by_type(self, dimension_type: str) -> Optional[str]:
        """
        通过 dimension_type 找 column_name（NER 识别 DIM 但不知值时用）。
        例如："二级品类" -> "GROUP_2"
        """
        types = self.get_all_types()
        for t in types:
            if t.get("dimension_type") == dimension_type:
                return t.get("column_name")
        return None

    def find_dimension_info(self, dimension_value: str) -> Optional[Dict[str, Any]]:
        """
        通过维度值找维度信息（带泛指类型区分）。

        Returns:
            {
                "column_name": str,       # 如 "GROUP_2"
                "dimension_value": str,   # 原始维度值，如 "智能云存储"
                "is_generic": bool,       # 是否泛指类型（通过 dimension_type fallback 匹配）
                "dimension_type": str     # 维度类型，如 "二级品类"
            }

        匹配策略：
        1. 精确匹配 dimension_value → is_generic=False
        2. 模糊匹配第一个结果 → is_generic=False
        3. Fallback 到 dimension_type 匹配 → is_generic=True（泛指类型）
        4. 仍匹配不上 → None
        """
        results = self.search_by_value(dimension_value, limit=5)

        # 精确匹配
        for r in results:
            if str(r.get("dimension_value", "")) == dimension_value:
                return {
                    "column_name": r.get("column_name"),
                    "dimension_value": r.get("dimension_value"),
                    "is_generic": False,
                    "dimension_type": r.get("dimension_type", ""),
                }

        # 模糊匹配第一个
        if results:
            return {
                "column_name": results[0].get("column_name"),
                "dimension_value": results[0].get("dimension_value"),
                "is_generic": False,
                "dimension_type": results[0].get("dimension_type", ""),
            }

        # Fallback: 尝试按 dimension_type 匹配（传入的是类型名不是值）
        column_name = self.find_column_by_type(dimension_value)
        if column_name:
            return {
                "column_name": column_name,
                "dimension_value": None,
                "is_generic": True,  # 泛指类型
                "dimension_type": dimension_value,
            }

        # Fallback: 查询 business_terms 同义词（用户可能用了"美国站"而不是"美国亚马逊"）
        synonym_result = self._find_by_business_terms_synonym(dimension_value)
        if synonym_result:
            return synonym_result

        return None

    def _find_by_business_terms_synonym(self, dimension_value: str) -> Optional[Dict[str, Any]]:
        """
        通过 business_terms 表的同义词找到维度信息。
        例如："美国站" → "美国亚马逊" → FSITE
        """
        try:
            from ai.client.metric_client import MetricClient
            client = MetricClient()
            terms = client.get_business_terms()
            for t in terms:
                synonyms = t.get("synonyms") or []
                if isinstance(synonyms, str):
                    synonyms = [s.strip().strip('"') for s in synonyms.strip("{}").split(",") if s.strip()]
                dim_field = t.get("dimension_field", "")
                canonical = t.get("dimension_value", "") or t.get("term", "")
                if not canonical or not synonyms:
                    continue
                # 检查传入的值是否匹配同义词
                if dimension_value in synonyms and dim_field:
                    # 将中文维度类型转换为列名
                    col_name = self.find_column_by_type(dim_field)
                    if col_name:
                        return {
                            "column_name": col_name,
                            "dimension_value": canonical,  # 返回标准值
                            "is_generic": False,
                            "dimension_type": dim_field,
                        }
            return None
        except Exception as e:
            logger.warning(f"[_find_by_business_terms_synonym] 查询同义词失败: {e}")
            return None

    def get_values_by_type(self, dimension_type: str) -> List[str]:
        """
        通过 dimension_type 获取所有维度值（用于 GROUP BY 场景）。
        例如："二级品类" -> ["智能云存储", "影音类", ...]
        """
        col = self.find_column_by_type(dimension_type)
        if not col:
            return []
        items = self.get_by_column_name(col)
        return [item.get("dimension_value", "") for item in items if item.get("dimension_value")]

    def get_keywords(self) -> List[str]:
        """
        获取所有 dimension_type 列表（消除 graph.py dim_keywords 硬编码）。
        """
        types = self.get_all_types()
        return list(set(t.get("dimension_type", "") for t in types if t.get("dimension_type")))

    def get_ranking_options(self) -> List[Dict[str, str]]:
        """
        获取排名追问选项（消除 intent_router.py RANKING_DIMENSION_OPTIONS 硬编码）。
        返回 [{"label": "按平台", "value": "PLATFORM"}, ...]
        """
        types = self.get_all_types()
        seen = set()
        options = []
        # 优先添加有实际维度值的列
        for t in types:
            col = t.get("column_name", "")
            dtype = t.get("dimension_type", "")
            if col and dtype and col not in seen:
                seen.add(col)
                options.append({"label": f"按{dtype}", "value": col})
        return options

    def get_default_fields(self) -> List[str]:
        """
        获取默认维度字段（消除 mql_generator 默认回退硬编码）。
        返回所有已知的维度列名。
        """
        types = self.get_all_types()
        result = []
        for t in types:
            col = t.get("column_name", "")
            if col and col not in result:
                result.append(col)
        return result if result else ["PLATFORM", "FCHANNEL", "FADTYPE", "FSITE"]

    def get_prompt_context(self, max_values_per_field: int = 20) -> str:
        """
        生成 prompt 维度上下文（消除 mql_generator prompt 硬编码）。
        格式：列名: 值1, 值2, 值3, ...
        """
        lines = []
        types = self.get_all_types()
        # 按 column_name 分组
        from collections import defaultdict
        by_column = defaultdict(list)
        for t in types:
            col = t.get("column_name", "")
            dtype = t.get("dimension_type", "")
            if col:
                by_column[col].append(dtype)

        for col, type_list in by_column.items():
            values = self.get_by_column_name(col, use_cache=True)
            if values:
                value_strs = [
                    v.get("dimension_value", "") for v in values[:max_values_per_field]
                    if v.get("dimension_value")
                ]
                if value_strs:
                    types_str = "/".join(set(type_list))
                    lines.append(f"  {col}({types_str}): {', '.join(value_strs)}")
        return "\n".join(lines) if lines else ""

    def get_dimension_values_context(self, dimension_fields: Optional[List[str]] = None) -> str:
        """
        获取维度值上下文字符串，用于 MQL Generator prompt。
        消除 mql_generator._get_dimension_values_context 的硬编码字段。
        """
        if dimension_fields is None:
            fields = self.get_default_fields()
        else:
            fields = dimension_fields

        lines = []
        for field in fields:
            values = self.get_by_column_name(field, use_cache=True)
            if values:
                value_list = [v.get("dimension_value", "") for v in values if v.get("dimension_value")]
                if value_list:
                    lines.append(f"  {field}: {', '.join(value_list[:100])}")
        return "\n".join(lines) if lines else ""

    def get_level_keywords(self) -> Dict[str, str]:
        """
        获取品类级别关键词映射（消除 mql_generator level_keywords 硬编码）。
        """
        types = self.get_all_types()
        result = {}
        for t in types:
            col = t.get("column_name", "")
            dtype = t.get("dimension_type", "")
            if col and dtype and "品类" in dtype:
                result[dtype] = col
        # 补充标准映射
        standard = {
            "一级品类": "GROUP_1",
            "二级品类": "GROUP_2",
            "三级品类": "GROUP_3",
            "四级品类": "GROUP_4",
        }
        for k, v in standard.items():
            if k not in result:
                result[k] = v
        return result

    def get_fallback_map(self) -> Dict[str, str]:
        """
        获取中文→列名 fallback 映射（消除 mql_generator fallback_map 硬编码）。
        从 dimension_type_mappings 动态生成。
        """
        types = self.get_all_types()
        result = {}
        for t in types:
            dtype = t.get("dimension_type", "")
            col = t.get("column_name", "")
            if dtype and col:
                result[dtype] = col
        return result

    def clear_cache(self):
        """手动清除所有缓存"""
        with DimensionService._lock:
            DimensionService._types_cache = None
            DimensionService._column_values_cache.clear()
            DimensionService._values_search_cache.clear()
            DimensionService._cache_time.clear()
        logger.info("[DimensionService] 缓存已清除")

    def sync_from_starrocks(self, column_name: str, table_name: str = "ids.IDS_AMZ_COMPREHENSIVE_DI") -> Dict[str, Any]:
        """
        从 StarRocks 同步指定列的维度值到 PostgreSQL。
        返回同步结果统计。
        """
        result = self._api_post("/api/v1/dimension-values/sync", json={
            "column_name": column_name,
            "table_name": table_name,
        })
        # 同步后清除缓存
        if column_name in DimensionService._column_values_cache:
            del DimensionService._column_values_cache[column_name]
        return result if result else {}
