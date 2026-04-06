"""
SQL 结果缓存
基于 SQL 哈希的缓存，TTL 5分钟
"""
import hashlib
import time
from typing import Dict, Any, Optional


class SQLCache:
    """SQL 结果缓存"""

    def __init__(self, ttl_seconds: int = 300):
        """
        初始化缓存

        Args:
            ttl_seconds: 缓存过期时间，默认5分钟
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def _hash_sql(self, sql: str) -> str:
        """生成 SQL 的哈希值"""
        return hashlib.sha256(sql.strip().encode()).hexdigest()

    def get(self, sql: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            sql: SQL 查询语句

        Returns:
            缓存结果，如果不存在或已过期返回 None
        """
        sql_hash = self._hash_sql(sql)

        if sql_hash not in self._cache:
            return None

        entry = self._cache[sql_hash]
        elapsed = time.time() - entry['timestamp']

        if elapsed >= self._ttl:
            # 缓存过期，删除
            del self._cache[sql_hash]
            return None

        return entry['result']

    def set(self, sql: str, result: Any) -> None:
        """
        设置缓存

        Args:
            sql: SQL 查询语句
            result: 查询结果
        """
        sql_hash = self._hash_sql(sql)

        self._cache[sql_hash] = {
            'result': result,
            'timestamp': time.time()
        }

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def size(self) -> int:
        """返回缓存条目数量"""
        return len(self._cache)


# 全局缓存实例
_sql_cache = SQLCache(ttl_seconds=300)


def get_sql_cache() -> SQLCache:
    """获取全局 SQL 缓存实例"""
    return _sql_cache
