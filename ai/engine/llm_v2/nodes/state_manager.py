"""
State manager for V2 multi-turn sessions.

Responsibilities:
- keep in-process state snapshots
- maintain deduplicated MQL history
- compress long conversations
- support rollback helpers
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from ai.config.logging_config import get_logger
from ..schema import V2State, MQLSchema
from ..session_store import V2SessionStore, get_session_store

logger = get_logger("ai.llm_v2.state_manager")


class ConversationSummary:
    """Compressed conversation summary."""

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
    """
    Compress long MQL history.

    Keep a summary plus the latest preserved turns.
    """

    MAX_TURNS_BEFORE_COMPRESSION = 12
    PRESERVED_TURNS = 5

    def compress(self, history_stack: List[str]) -> Optional[ConversationSummary]:
        if len(history_stack) <= self.MAX_TURNS_BEFORE_COMPRESSION:
            return None

        summary = ConversationSummary()
        summary.original_turns = len(history_stack)
        summary.compressed_at = datetime.now().isoformat()

        key_metrics: Dict[str, str] = {}
        key_times: Dict[str, bool] = {}
        key_dimensions = set()
        intent_patterns = set()

        for mql_json in history_stack:
            try:
                mql_dict = json.loads(mql_json)
            except (json.JSONDecodeError, TypeError):
                continue

            metric_dict = mql_dict.get("metric") or {}
            metric_name = metric_dict.get("name", "")
            metric_code = metric_dict.get("code", "")
            if metric_name and metric_name not in key_metrics:
                key_metrics[metric_name] = metric_code

            time_dict = mql_dict.get("time") or {}
            time_original = time_dict.get("original", "")
            if time_original and time_original not in key_times:
                key_times[time_original] = True

            for dim in mql_dict.get("dimensions", []) or []:
                dim_type = dim.get("type")
                if dim_type:
                    key_dimensions.add(dim_type)

            intent = mql_dict.get("intent", "")
            if intent:
                intent_patterns.add(intent)

        summary.key_entities = [{"name": name, "code": code} for name, code in key_metrics.items()]
        summary.last_metric = next(iter(key_metrics.keys()), None)
        summary.last_metric_code = next(iter(key_metrics.values()), None)
        summary.last_time = next(iter(key_times.keys()), None)
        summary.last_dimensions = list(key_dimensions)
        summary.intent_patterns = list(intent_patterns)
        return summary

    def should_compress(self, history_stack: List[str]) -> bool:
        return len(history_stack) > self.MAX_TURNS_BEFORE_COMPRESSION

    def get_compressed_history(
        self,
        history_stack: List[str],
        summary: ConversationSummary,
    ) -> List[str]:
        preserved = history_stack[-self.PRESERVED_TURNS:]
        compressed = [json.dumps({"type": "summary", "data": summary.to_dict()}, ensure_ascii=False)]
        return compressed + preserved


class StateManager:
    """In-process V2 state manager."""

    def __init__(self, session_store: Optional[V2SessionStore] = None):
        self._session_store = session_store or get_session_store()
        self._compressor = SessionCompression()

    async def update(self, state: V2State) -> None:
        logger.info(f"[StateManager] update session={state.session_id}")
        state.updated_at = datetime.now().isoformat()

        if state.mql:
            await self._ensure_current_mql_in_history(state)

        if self._compressor.should_compress(state.history_stack):
            summary = self._compressor.compress(state.history_stack)
            if summary:
                state.history_stack = self._compressor.get_compressed_history(state.history_stack, summary)
                state.conversation_summary = summary.to_dict()
                logger.info(
                    f"[StateManager] compressed session={state.session_id}, "
                    f"turns={summary.original_turns}"
                )

        self._session_store.set_state(state)

    async def _ensure_current_mql_in_history(self, state: V2State) -> None:
        if not state.mql:
            return

        try:
            mql_json = json.dumps(state.mql.to_dict(), ensure_ascii=False)
            if not state.history_stack or state.history_stack[-1] != mql_json:
                state.push_history(mql_json)
            logger.debug(f"[StateManager] history size={len(state.history_stack)}")
        except Exception as e:
            logger.error(f"[StateManager] save history failed: {e}")

    async def get_state(self, session_id: str) -> Optional[V2State]:
        return self._session_store.get_state(session_id)

    async def rollback(self, state: V2State, steps: int = 1) -> V2State:
        logger.info(f"[StateManager] rollback session={state.session_id}, steps={steps}")
        for _ in range(steps):
            previous_mql_json = state.pop_history()
            if previous_mql_json:
                state.mql = MQLSchema.from_dict(json.loads(previous_mql_json))
                state.error = ""
                state.retry_count = 0
        return state

    async def clear(self, session_id: str) -> None:
        self._session_store.delete(session_id)
        logger.info(f"[StateManager] cleared session={session_id}")

    async def get_history(self, session_id: str) -> List[str]:
        context = self._session_store.get_context(session_id)
        return list(context.get("history_stack") or []) if context else []

    def get_compressed_summary(self, state: V2State) -> Optional[ConversationSummary]:
        summary_dict = state.conversation_summary
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


_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
