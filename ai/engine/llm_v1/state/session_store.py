"""
SessionStore - LLM.V1 Redis 状态管理
基于 Redis TTL 的多轮对话状态存储
Key: llm_v1:session:{session_id}
TTL: 30分钟
"""
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

import redis

logger = logging.getLogger("ai.llm_v1.session_store")


@dataclass
class ConversationMessage:
    """对话消息"""
    role: str  # user / assistant
    content: str
    slots: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None
    node: Optional[str] = None  # LU/SF/SQL/CK/EX/RV/CHART/RS
    answer: Optional[str] = None
    chart_config: Optional[Dict] = None
    thinking_steps: Optional[List[Dict]] = None
    result_data: Optional[List[Dict]] = None
    suggestions: Optional[List[str]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConversationContext:
    """对话上下文（用于多轮继承）"""
    current_metric: Optional[str] = None
    current_metric_code: Optional[str] = None
    current_time: Optional[str] = None
    current_dimensions: List[str] = field(default_factory=list)
    current_filters: List[Dict] = field(default_factory=list)


@dataclass
class SessionState:
    """完整会话状态"""
    session_id: str
    history: List[ConversationMessage] = field(default_factory=list)
    context: ConversationContext = field(default_factory=ConversationContext)
    last_node: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None


class SessionStore:
    """
    Redis 会话状态管理器
    - 30分钟 TTL 自动过期
    - 存储对话历史和上下文
    - 当 Redis 不可用时，使用内存存储作为 fallback
    """

    _instance: Optional['SessionStore'] = None
    _redis: Optional[redis.Redis] = None
    _memory_store: Dict[str, SessionState] = {}  # 内存 fallback 存储

    # Redis Key 前缀
    KEY_PREFIX = "llm_v1:session:"
    DEFAULT_TTL = 1800  # 30分钟

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._init_redis()

    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            import os
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))

            self._redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # 测试连接
            self._redis.ping()
            logger.info(f"[SessionStore] Redis 连接成功 ({redis_host}:{redis_port})")
        except redis.ConnectionError as e:
            logger.warning(f"[SessionStore] Redis 连接失败: {e}，将使用内存存储")
            self._redis = None
        except Exception as e:
            logger.warning(f"[SessionStore] Redis 初始化失败: {e}，将使用内存存储")
            self._redis = None

    def _get_key(self, session_id: str) -> str:
        """生成 Redis Key"""
        return f"{self.KEY_PREFIX}{session_id}"

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        获取会话状态
        返回 None 表示会话不存在或已过期
        """
        # 先尝试从 Redis 获取
        if self._redis is not None:
            try:
                key = self._get_key(session_id)
                data = self._redis.get(key)
                if data is None:
                    return None

                state_dict = json.loads(data)
                # 反序列化
                history = [ConversationMessage(**m) for m in state_dict.get("history", [])]
                context = ConversationContext(**state_dict.get("context", {}))

                return SessionState(
                    session_id=session_id,
                    history=history,
                    context=context,
                    last_node=state_dict.get("last_node"),
                    last_result=state_dict.get("last_result"),
                )
            except Exception as e:
                logger.warning(f"[SessionStore] Redis 获取会话失败: {e}，尝试内存存储")

        # Redis 不可用时，使用内存存储
        if session_id in self._memory_store:
            logger.info(f"[SessionStore] 从内存存储获取 session: {session_id}")
            return self._memory_store[session_id]

        return None

    def save_session(self, session_id: str, state: SessionState, ttl: int = None) -> bool:
        """
        保存会话状态
        ttl: 过期时间（秒），默认30分钟
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL

        # 同时保存到内存存储（作为 fallback）
        self._memory_store[session_id] = state
        logger.info(f"[SessionStore] 保存到内存存储: session_id={session_id}")

        # 尝试保存到 Redis
        if self._redis is None:
            logger.warning(f"[SessionStore] Redis 不可用，仅保存到内存存储")
            return True

        try:
            key = self._get_key(session_id)
            # 序列化
            state_dict = {
                "session_id": state.session_id,
                "history": [asdict(m) for m in state.history],
                "context": asdict(state.context),
                "last_node": state.last_node,
                "last_result": state.last_result,
            }
            data = json.dumps(state_dict, ensure_ascii=False)
            self._redis.setex(key, ttl, data)
            return True
        except Exception as e:
            logger.error(f"[SessionStore] 保存会话失败: {e}")
            return True  # 内存存储已保存，返回成功

    def append_history(
        self,
        session_id: str,
        message: ConversationMessage,
        ttl: int = None
    ) -> bool:
        """
        追加对话历史
        自动刷新 TTL
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL

        # 获取当前会话
        state = self.get_session(session_id)
        if state is None:
            # 新建会话
            state = SessionState(session_id=session_id)

        # 追加消息
        state.history.append(message)
        state.last_node = message.node
        state.last_result = {
            "content": message.content,
            "sql": message.sql,
            "answer": message.answer,
            "chart_config": message.chart_config,
        }

        # 更新上下文（如果有 slots）
        if message.slots:
            self._update_context_from_slots(state, message.slots)

        return self.save_session(session_id, state, ttl)

    def _update_context_from_slots(self, state: SessionState, slots: Dict[str, Any]):
        """从 slots 更新对话上下文"""
        if slots.get("metric"):
            state.context.current_metric = slots["metric"]
        if slots.get("metric_code"):
            state.context.current_metric_code = slots["metric_code"]
        if slots.get("time_range"):
            time_expr = slots["time_range"].get("original") if isinstance(slots["time_range"], dict) else str(slots["time_range"])
            state.context.current_time = time_expr
        if slots.get("dimensions"):
            state.context.current_dimensions = slots["dimensions"]
        if slots.get("filters"):
            state.context.current_filters = slots["filters"]

    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """获取对话上下文（用于多轮继承）"""
        state = self.get_session(session_id)
        return state.context if state else None

    def clear_session(self, session_id: str) -> bool:
        """清除会话"""
        if self._redis is None:
            return False

        try:
            key = self._get_key(session_id)
            self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"[SessionStore] 清除会话失败: {e}")
            return False

    def refresh_ttl(self, session_id: str, ttl: int = None) -> bool:
        """刷新 TTL"""
        if ttl is None:
            ttl = self.DEFAULT_TTL

        if self._redis is None:
            return False

        try:
            key = self._get_key(session_id)
            return self._redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"[SessionStore] 刷新TTL失败: {e}")
            return False


# 全局单例
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """获取会话存储单例"""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
