"""
步骤 11: 状态更新节点

职责：
- 更新会话状态
- 保存历史记录
- 支持 Checkpoint 回退
- 长会话压缩
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from ai.config.logging_config import get_logger
from ..schema import V2State, MQLSchema

logger = get_logger("ai.llm_v2.state_manager")


class ConversationSummary:
    """对话摘要"""

    def __init__(self):
        self.original_turns: int = 0
        self.key_entities: List[Dict[str, Any]] = []
        self.intent_patterns: List[str] = []
        self.last_metric: Optional[str] = None
        self.last_metric_code: Optional[str] = None
        self.last_time: Optional[str] = None
        self.last_dimensions: List[str] = []
        self.compressed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_turns": self.original_turns,
            "key_entities": self.key_entities,
            "intent_patterns": self.intent_patterns,
            "last_metric": self.last_metric,
            "last_metric_code": self.last_metric_code,
            "last_time": self.last_time,
            "last_dimensions": self.last_dimensions,
            "compressed_at": self.compressed_at,
        }


class SessionCompression:
    """长会话压缩器

    当对话超过20轮时，触发压缩：
    1. 提取关键实体（指标、时间、维度）
    2. 提取意图模式
    3. 生成摘要
    4. 保留最后N轮完整对话 + 摘要
    """

    # 超过此轮数触发压缩
    MAX_TURNS_BEFORE_COMPRESSION = 20

    # 压缩后保留的轮数
    PRESERVED_TURNS = 5

    def compress(self, history_stack: List[str]) -> ConversationSummary:
        """压缩对话历史

        Args:
            history_stack: MQL JSON 字符串列表

        Returns:
            ConversationSummary 对话摘要
        """
        if len(history_stack) <= self.MAX_TURNS_BEFORE_COMPRESSION:
            return None

        summary = ConversationSummary()
        summary.original_turns = len(history_stack)
        summary.compressed_at = datetime.now().isoformat()

        # 提取关键实体
        key_metrics = {}
        key_times = {}
        key_dimensions = set()
        intent_patterns = set()

        for mql_json in history_stack:
            try:
                mql_dict = json.loads(mql_json)

                # 提取指标
                if mql_dict.get("metric"):
                    metric_name = mql_dict["metric"].get("name", "")
                    metric_code = mql_dict["metric"].get("code", "")
                    if metric_name and metric_name not in key_metrics:
                        key_metrics[metric_name] = metric_code

                # 提取时间
                if mql_dict.get("time"):
                    time_original = mql_dict["time"].get("original", "")
                    if time_original and time_original not in key_times:
                        key_times[time_original] = True

                # 提取维度
                for dim in mql_dict.get("dimensions", []):
                    if dim.get("type"):
                        key_dimensions.add(dim["type"])

                # 提取意图
                intent = mql_dict.get("intent", "")
                if intent:
                    intent_patterns.add(intent)

            except (json.JSONDecodeError, KeyError):
                continue

        summary.key_entities = [
            {"name": name, "code": code}
            for name, code in key_metrics.items()
        ]
        summary.last_metric = list(key_metrics.keys())[0] if key_metrics else None
        summary.last_metric_code = list(key_metrics.values())[0] if key_metrics else None
        summary.last_time = list(key_times.keys())[0] if key_times else None
        summary.last_dimensions = list(key_dimensions)
        summary.intent_patterns = list(intent_patterns)

        return summary

    def should_compress(self, history_stack: List[str]) -> bool:
        """判断是否需要压缩"""
        return len(history_stack) > self.MAX_TURNS_BEFORE_COMPRESSION

    def get_compressed_history(
        self,
        history_stack: List[str],
        summary: ConversationSummary,
    ) -> List[str]:
        """获取压缩后的历史

        保留最后N轮完整对话 + 摘要
        """
        preserved = history_stack[-self.PRESERVED_TURNS:]
        compressed = [
            json.dumps({
                "type": "summary",
                "data": summary.to_dict(),
            }, ensure_ascii=False)
        ]
        return compressed + preserved


class StateManager:
    """
    状态管理器

    管理 V2 会话状态，包括：
    - 更新会话状态
    - 保存历史记录
    - 支持 Checkpoint 回退
    - 长会话压缩
    """

    def __init__(self):
        self._session_store: Dict[str, V2State] = {}
        self._compressor = SessionCompression()

    async def update(self, state: V2State) -> None:
        """
        更新状态

        Args:
            state: V2State 实例
        """
        logger.info(f"[StateManager] 更新状态: session_id={state.session_id}")

        # 1. 更新时间戳
        state.updated_at = datetime.now().isoformat()

        # 2. 保存到会话存储
        self._session_store[state.session_id] = state

        # 3. 保存 MQL 到历史记录
        if state.mql:
            await self._save_mql_history(state)

        # 4. 检查是否需要压缩
        if self._compressor.should_compress(state.history_stack):
            summary = self._compressor.compress(state.history_stack)
            if summary:
                compressed_history = self._compressor.get_compressed_history(
                    state.history_stack, summary
                )
                state.history_stack = compressed_history
                state.context_cache["conversation_summary"] = summary.to_dict()
                logger.info(
                    f"[StateManager] 会话已压缩: {summary.original_turns}轮 -> 摘要+{self._compressor.PRESERVED_TURNS}轮"
                )

        # 5. 持久化到 Redis（可选）
        # await self._persist_to_redis(state)

    async def _save_mql_history(self, state: V2State) -> None:
        """保存 MQL 到历史记录"""
        if not state.mql:
            return

        try:
            # 将当前 MQL 保存到历史栈
            mql_json = json.dumps(state.mql.to_dict(), ensure_ascii=False)
            state.push_history(mql_json)

            # TODO: 保存到 Redis，支持跨会话查询
            # redis_key = f"v2:history:{state['session_id']}"
            # await redis_client.rpush(redis_key, mql_json)

            logger.debug(f"[StateManager] MQL 历史已保存: {len(state.history_stack)} 条")

        except Exception as e:
            logger.error(f"[StateManager] 保存 MQL 历史失败: {e}")

    async def get_state(self, session_id: str) -> V2State:
        """
        获取会话状态

        Args:
            session_id: 会话 ID

        Returns:
            V2State 或 None
        """
        return self._session_store.get(session_id)

    async def rollback(self, state: V2State, steps: int = 1) -> V2State:
        """
        回退状态

        Args:
            state: 当前状态
            steps: 回退步数

        Returns:
            回退后的状态
        """
        logger.info(f"[StateManager] 回退状态: session_id={state.session_id}, steps={steps}")

        # 从历史栈回退
        for _ in range(steps):
            previous_mql_json = state.pop_history()
            if previous_mql_json:
                previous_mql = MQLSchema.from_dict(json.loads(previous_mql_json))
                state.mql = previous_mql
                state.error = ""
                state.retry_count = 0

        return state

    async def clear(self, session_id: str) -> None:
        """
        清除会话状态

        Args:
            session_id: 会话 ID
        """
        if session_id in self._session_store:
            del self._session_store[session_id]

        # TODO: 清除 Redis 中的会话数据
        # redis_key = f"v2:history:{session_id}"
        # await redis_client.delete(redis_key)

        logger.info(f"[StateManager] 会话已清除: {session_id}")

    async def get_history(self, session_id: str) -> list:
        """
        获取会话历史

        Args:
            session_id: 会话 ID

        Returns:
            MQL 历史列表
        """
        state = self._session_store.get(session_id)
        if state:
            return state.history_stack
        return []

    def get_compressed_summary(self, state: V2State) -> Optional[ConversationSummary]:
        """
        获取对话摘要（用于恢复上下文）

        Args:
            state: V2State 实例

        Returns:
            ConversationSummary 或 None
        """
        summary_dict = state.context_cache.get("conversation_summary")
        if not summary_dict:
            return None

        summary = ConversationSummary()
        summary.original_turns = summary_dict.get("original_turns", 0)
        summary.key_entities = summary_dict.get("key_entities", [])
        summary.intent_patterns = summary_dict.get("intent_patterns", [])
        summary.last_metric = summary_dict.get("last_metric")
        summary.last_metric_code = summary_dict.get("last_metric_code")
        summary.last_time = summary_dict.get("last_time")
        summary.last_dimensions = summary_dict.get("last_dimensions", [])
        summary.compressed_at = summary_dict.get("compressed_at", "")
        return summary


def get_state_manager() -> StateManager:
    """获取 StateManager 单例"""
    return StateManager()
