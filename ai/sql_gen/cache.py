"""
SQL 结果缓存
基于 SQL 哈希的 TTL 缓存，自动管理容量上界，防止内存泄漏。
"""
import hashlib
from typing import Any, Optional
from cachetools import TTLCache


class SQLCache:
    """SQL 结果缓存，有界 TTL，最多 max_size 条"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl_seconds)

    def _hash_sql(self, sql: str) -> str:
        return hashlib.sha256(sql.strip().encode()).hexdigest()

    def get(self, sql: str) -> Optional[Any]:
        return self._cache.get(self._hash_sql(sql))

    def set(self, sql: str, result: Any) -> None:
        self._cache[self._hash_sql(sql)] = result

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


# 全局缓存实例
_sql_cache = SQLCache(max_size=1000, ttl_seconds=300)


def get_sql_cache() -> SQLCache:
    """获取全局 SQL 缓存实例"""
    return _sql_cache
