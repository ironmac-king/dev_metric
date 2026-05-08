"""
Prompt 元数据加载器 - 从数据库动态加载实际指标和维度，注入 prompt

职责：
- 加载数据库中实际存在的指标名称（供 LLM 识别）
- 加载数据库中实际存在的维度类型（供 LLM 做维度映射）
- 缓存结果，TTL 5 分钟，支持热修改
"""

import time
from typing import Dict, List, Any, Optional

from ai.config.logging_config import get_logger

logger = get_logger("ai.prompt_metadata_loader")

# 全局单例
_loader: Optional["PromptMetadataLoader"] = None


class PromptMetadataLoader:
    """直接从 PostgreSQL 加载实际指标和维度配置，注入 prompt"""

    CACHE_TTL = 300  # 5分钟

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
        self._pg_conn = None

    def _get_pg_conn(self):
        """获取 PostgreSQL 连接"""
        if self._pg_conn is None:
            import psycopg2
            self._pg_conn = psycopg2.connect(
                host="192.168.1.225",
                port=5432,
                dbname="dev_metric",
                user="postgres",
                password="admin123"
            )
        return self._pg_conn

    def _load_metrics(self) -> List[str]:
        """从 PostgreSQL 加载所有在用指标名称"""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor()
            cur.execute("SELECT name FROM metrics WHERE status = '在用' AND name IS NOT NULL AND name != '' ORDER BY name")
            names = [row[0] for row in cur.fetchall()]
            cur.close()
            logger.info(f"[PromptMetadataLoader] 加载 {len(names)} 个指标")
            return names
        except Exception as e:
            logger.warning(f"[PromptMetadataLoader] 加载指标失败: {e}")
        return []

    def _load_dimensions(self) -> List[Dict[str, str]]:
        """从 PostgreSQL 加载所有维度配置"""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor()
            # 从 dimension_configs 加载维度名称和列名映射（去重，以 column_name 为准）
            seen_codes: set = set()
            dims: list = []
            cur.execute("SELECT dimension_name, column_name FROM dimension_configs ORDER BY dimension_name")
            for row in cur.fetchall():
                name, col = row
                if name and col and col.upper() not in seen_codes:
                    # 排除纯中文的 column_name（来自 dim_value_mapping 的脏数据）
                    if not any('\u4e00' <= c <= '\u9fff' for c in col):
                        dims.append({"name": name, "code": col.upper()})
                        seen_codes.add(col.upper())
            # 从 dim_value_mapping 补充 ASIN/SKU（如果 dimension_configs 没有的话）
            cur.execute("SELECT DISTINCT dimension_type FROM dim_value_mapping WHERE dimension_type IS NOT NULL AND dimension_type != '' ORDER BY dimension_type")
            for row in cur.fetchall():
                dtype = row[0]
                code = dtype.upper()
                if code not in seen_codes and not any('\u4e00' <= c <= '\u9fff' for c in dtype):
                    dims.append({"name": dtype, "code": code})
                    seen_codes.add(code)
            cur.close()
            logger.info(f"[PromptMetadataLoader] 加载 {len(dims)} 个维度")
            return dims
        except Exception as e:
            logger.warning(f"[PromptMetadataLoader] 加载维度失败: {e}")
        return []

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache or key not in self._cache_time:
            return False
        return time.time() - self._cache_time[key] < self.CACHE_TTL

    def get_metric_names(self) -> List[str]:
        """获取所有活跃指标名称（带缓存）"""
        if not self._is_cache_valid("metrics"):
            self._cache["metrics"] = self._load_metrics()
            self._cache_time["metrics"] = time.time()
        return self._cache["metrics"]

    def get_dimension_mappings(self) -> List[Dict[str, str]]:
        """获取维度类型映射（带缓存）"""
        if not self._is_cache_valid("dimensions"):
            self._cache["dimensions"] = self._load_dimensions()
            self._cache_time["dimensions"] = time.time()
        return self._cache["dimensions"]

    def build_metric_names_section(self, max_count: int = 100) -> str:
        """构建指标名称列表段落，供 prompt 使用"""
        names = self.get_metric_names()
        if not names:
            return ""
        selected = names[:max_count]
        name_list = "、".join(selected)
        suffix = f"等（共{len(names)}个）" if len(names) > max_count else f"（共{len(names)}个）"
        return f"{name_list}{suffix}"

    def build_dimension_mappings_section(self) -> str:
        """构建维度映射段落，供 prompt 使用"""
        dims = self.get_dimension_mappings()
        if not dims:
            return ""
        parts = [f"{d['name']}={d['code']}" for d in dims]
        return "、".join(parts)

    def reload(self):
        """强制重新加载（清除缓存）"""
        self._cache.clear()
        self._cache_time.clear()
        logger.info("[PromptMetadataLoader] 已清除缓存")


def get_prompt_metadata_loader() -> PromptMetadataLoader:
    """获取单例"""
    global _loader
    if _loader is None:
        _loader = PromptMetadataLoader()
    return _loader
