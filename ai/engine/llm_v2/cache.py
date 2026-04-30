"""
V2 多级缓存体系

提供三级缓存：
1. L1 内存缓存 - LRU，最近 1000 条，5 分钟过期
2. L2 Redis 缓存 - 最近 7 天查询，1 小时过期
3. 历史查询复用 - 相似度 > 70% 复用 MQL

性能目标：
- L1 命中 < 1ms，命中率 30-40%
- L2 命中 < 10ms，命中率 40-50%
- 历史查询复用跳过 MQL 生成，耗时减少 70%
"""
import time
import hashlib
import json
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from datetime import datetime, timedelta
import threading

from ai.config.logging_config import get_logger
from ai.config.runtime import get_redis_settings

logger = get_logger("ai.llm_v2.cache")

# ==================== L1 内存缓存 ====================

class L1MemoryCache:
    """
    L1 内存缓存

    特性：
    - LRU 淘汰策略
    - 最大 1000 条
    - 5 分钟过期
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._expiry: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            # 检查是否存在
            if key not in self._cache:
                return None

            # 检查是否过期
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._cache[key]
                del self._expiry[key]
                return None

            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """设置缓存"""
        with self._lock:
            # 如果已存在，移到末尾
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
                self._expiry[key] = time.time() + self._ttl
                return

            # 如果达到最大容量，淘汰最旧的
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                if oldest_key in self._expiry:
                    del self._expiry[oldest_key]

            # 添加新条目
            self._cache[key] = value
            self._expiry[key] = time.time() + self._ttl

    def delete(self, key: str) -> None:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            if key in self._expiry:
                del self._expiry[key]

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._expiry.clear()

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
            }


# ==================== L2 Redis 缓存 ====================

class L2RedisCache:
    """
    L2 Redis 缓存

    特性：
    - 最近 7 天查询
    - 1 小时过期
    """

    KEY_PREFIX = "v2:cache:"
    TTL_SECONDS = 3600  # 1 小时

    def __init__(self):
        self._redis = None
        self._redis_host = ""
        self._redis_port = 0
        self._redis_db = 0
        self._init_redis()

    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            import redis
            self._redis_host, self._redis_port, self._redis_db = get_redis_settings()
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                db=self._redis_db,
                decode_responses=True,
                socket_connect_timeout=2
            )
            self._redis.ping()
            logger.info(f"[L2Cache] Redis 连接成功: {self._redis_host}:{self._redis_port}/{self._redis_db}")
        except Exception as e:
            logger.warning(f"[L2Cache] Redis 连接失败: {e}，L2 缓存将不可用")
            self._redis = None

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存"""
        if not self._redis:
            return None

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
            data = self._redis.get(full_key)
            if data:
                logger.debug(f"[L2Cache] 命中: {key}")
                return json.loads(data)
            logger.debug(f"[L2Cache] 未命中: {key}")
            return None
        except Exception as e:
            logger.warning(f"[L2Cache] 获取失败: {key}, error={e}")
            return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        """设置缓存"""
        if not self._redis:
            return

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
            self._redis.setex(
                full_key,
                self.TTL_SECONDS,
                json.dumps(value, ensure_ascii=False, default=str)
            )
            logger.debug(f"[L2Cache] 写入: {key}, TTL={self.TTL_SECONDS}s")
        except Exception as e:
            logger.warning(f"[L2Cache] 写入失败: {key}, error={e}")

    def delete(self, key: str) -> None:
        """删除缓存"""
        if not self._redis:
            return

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
            self._redis.delete(full_key)
        except Exception as e:
            logger.warning(f"[L2Cache] 删除失败: {key}, error={e}")

    def clear(self) -> None:
        """清空缓存"""
        if not self._redis:
            return

        try:
            pattern = f"{self.KEY_PREFIX}*"
            keys = self._redis.keys(pattern)
            if keys:
                self._redis.delete(*keys)
            logger.info(f"[L2Cache] 已清空 {len(keys)} 条缓存")
        except Exception as e:
            logger.warning(f"[L2Cache] 清空失败: {e}")


# ==================== MQL SQL 缓存 ====================

class MQLSQLCache:
    """
    MQL → SQL 缓存

    Key: MQL 的 SHA256 哈希
    Value: 生成的 SQL
    """

    def __init__(self):
        self._l1 = L1MemoryCache(max_size=1000, ttl_seconds=300)
        self._l2 = L2RedisCache()

    def _make_key(self, mql_dict: Dict[str, Any]) -> str:
        """生成缓存 Key"""
        # 按固定顺序序列化， 保证一致性
        def serialize(obj):
            if isinstance(obj, dict):
                return sorted((k, serialize(v)) for k, v in obj.items())
            elif isinstance(obj, list):
                return [serialize(item) for item in obj]
            else:
                return str(obj) if obj is not None else ""

        serialized = json.dumps(serialize(mql_dict), ensure_ascii=False)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def get(self, mql_dict: Dict[str, Any]) -> Optional[str]:
        """
        获取缓存的 SQL

        Args:
            mql_dict: MQL 字典

        Returns:
            SQL 或 None
        """
        key = self._make_key(mql_dict)

        # L1 查找
        cached = self._l1.get(key)
        if cached:
            logger.debug("[MQLSQLCache] L1 命中")
            return cached.get("sql")

        # L2 查找
        cached = self._l2.get(key)
        if cached:
            # 回填 L1
            self._l1.set(key, cached)
            logger.debug("[MQLSQLCache] L2 命中，回填 L1")
            return cached.get("sql")

        return None

    def set(self, mql_dict: Dict[str, Any], sql: str, sql_result: Dict[str, Any] = None) -> None:
        """
        设置缓存

        Args:
            mql_dict: MQL 字典
            sql: 生成的 SQL
            sql_result: SQL 执行结果（可选）
        """
        key = self._make_key(mql_dict)
        value = {
            "sql": sql,
            "result": sql_result,
            "created_at": datetime.now().isoformat(),
        }

        # 同时写入 L1 和 L2
        self._l1.set(key, value)
        self._l2.set(key, value)

    def invalidate(self, mql_dict: Dict[str, Any]) -> None:
        """使缓存失效"""
        key = self._make_key(mql_dict)
        self._l1.delete(key)
        self._l2.delete(key)


# ==================== 历史查询复用 ====================

class HistoryReuseCache:
    """
    历史查询复用

    特性：
    - 存储历史 MQL
    - 计算相似度
    - 相似度 > 70% 复用
    """

    def __init__(self):
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100  # 最多保存 100 条

    def add(self, question: str, mql_dict: Dict[str, Any]) -> None:
        """添加历史记录"""
        self._history.append({
            "question": question,
            "mql": mql_dict,
            "timestamp": datetime.now().isoformat(),
        })

        # 限制历史条数
        while len(self._history) > self._max_history:
            self._history.pop(0)

    def find_similar(self, question: str, threshold: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        查找相似查询

        Args:
            question: 当前问题
            threshold: 相似度阈值

        Returns:
            相似历史记录或 None
        """
        if not self._history:
            return None

        # TODO: 使用 embedding 计算相似度
        # 目前使用简单的关键词匹配

        # 提取关键词
        current_keywords = self._extract_keywords(question)

        best_match = None
        best_score = 0.0

        for item in reversed(self._history):
            history_keywords = self._extract_keywords(item["question"])
            score = self._calculate_similarity(current_keywords, history_keywords)

            if score >= threshold and score > best_score:
                best_score = score
                best_match = item

        if best_match:
            logger.info(f"[HistoryReuse] 找到相似查询: score={best_score:.2f}, question={best_match['question'][:30]}...")

        return best_match

    def _extract_keywords(self, text: str) -> set:
        """提取关键词"""
        # 简单分词
        import re
        words = re.findall(r'[\w]+', text.lower())
        # 过滤停用词
        stopwords = {"的", "是", "在", "了", "和", "与", "或", "各", "有", "多少", "什么", "哪个", "怎"}
        return {w for w in words if w not in stopwords and len(w) > 1}

    def _calculate_similarity(self, keywords1: set, keywords2: set) -> float:
        """计算相似度"""
        if not keywords1 or not keywords2:
            return 0.0

        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)

        return intersection / union if union > 0 else 0.0


# ==================== 全局缓存实例 ====================

_mql_sql_cache: Optional[MQLSQLCache] = None
_history_reuse_cache: Optional[HistoryReuseCache] = None


def get_mql_sql_cache() -> MQLSQLCache:
    """获取 MQLSQLCache 单例"""
    global _mql_sql_cache
    if _mql_sql_cache is None:
        _mql_sql_cache = MQLSQLCache()
    return _mql_sql_cache


def get_history_reuse_cache() -> HistoryReuseCache:
    """获取 HistoryReuseCache 单例"""
    global _history_reuse_cache
    if _history_reuse_cache is None:
        _history_reuse_cache = HistoryReuseCache()
    return _history_reuse_cache
