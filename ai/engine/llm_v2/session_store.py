"""
V2 session store shared by router and state manager.

Redis is used when available. If Redis is unavailable, the store falls back
to an in-process dictionary so local development and tests still work.
"""
from __future__ import annotations

import json
import time
import logging
from typing import Optional, Dict, Any, List

import redis
from redis.exceptions import RedisError

from ai.config.runtime import get_redis_settings
from .schema import ContextScope, MQLSchema, V2State, create_v2_state

logger = logging.getLogger("ai.llm_v2.session_store")


class V2SessionStore:
    """Durable session storage for V2 multi-turn conversations."""

    DEFAULT_TTL = 7 * 24 * 3600

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = DEFAULT_TTL,
        redis_client: Optional[Any] = None,
    ):
        self._ttl = ttl_seconds
        self._memory_store: Dict[str, str] = {}
        self._redis = redis_client

        if self._redis is None:
            redis_url = redis_url or self._default_redis_url()
            self._redis = redis.from_url(redis_url, decode_responses=True)
            self._redis_url = redis_url
        else:
            self._redis_url = "<injected>"

        logger.info(
            f"[V2SessionStore] initialized, redis={self._redis_url}, ttl={ttl_seconds}s"
        )

    @staticmethod
    def _default_redis_url() -> str:
        host, port, db = get_redis_settings()
        return f"redis://{host}:{port}/{db}"

    def _key(self, session_id: str) -> str:
        return f"v2:session:{session_id}"

    def _read_raw(self, key: str) -> Optional[str]:
        try:
            raw = self._redis.get(key)
            if raw is not None:
                return raw
        except RedisError as exc:
            logger.warning(f"[V2SessionStore] redis read failed, using memory fallback: {exc}")
        return self._memory_store.get(key)

    def _write_raw(self, key: str, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False)
        try:
            self._redis.setex(key, self._ttl, raw)
        except RedisError as exc:
            logger.warning(f"[V2SessionStore] redis write failed, using memory fallback: {exc}")
            self._memory_store[key] = raw

    def _delete_raw(self, key: str) -> None:
        try:
            self._redis.delete(key)
        except RedisError as exc:
            logger.warning(f"[V2SessionStore] redis delete failed, using memory fallback: {exc}")
        self._memory_store.pop(key, None)

    def _load_payload(self, session_id: str) -> Dict[str, Any]:
        raw = self._read_raw(self._key(session_id))
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[V2SessionStore] invalid payload for session={session_id}")
            return {}

    def set(
        self,
        session_id: str,
        mql: Optional[MQLSchema] = None,
        history_stack: Optional[List[str]] = None,
        conversation_summary: Optional[Dict[str, Any]] = None,
        user_id: str = "default",
    ) -> None:
        """Persist the durable portion of a V2 session."""
        existing = self._load_payload(session_id)
        created_at = existing.get("created_at", time.time())

        payload = {
            "mql": mql.to_dict() if mql else existing.get("mql"),
            "history_stack": history_stack if history_stack is not None else existing.get("history_stack", []),
            "conversation_summary": (
                conversation_summary
                if conversation_summary is not None
                else existing.get("conversation_summary")
            ),
            "user_id": user_id or existing.get("user_id") or "default",
            "created_at": created_at,
            "last_accessed": time.time(),
        }
        self._write_raw(self._key(session_id), payload)
        logger.info(
            f"[V2SessionStore] saved session={session_id}, "
            f"user_id={payload['user_id']}, "
            f"metric={(mql.metric.name if mql and mql.metric else None)}, "
            f"history={len(payload['history_stack'])}"
        )

    def set_state(self, state: V2State) -> None:
        """Persist the durable subset of a V2State."""
        summary = state.conversation_summary

        self.set(
            session_id=state.session_id,
            mql=state.mql,
            history_stack=list(state.history_stack),
            conversation_summary=summary,
            user_id=state.user_id,
        )

    def get_context(self, session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load the durable portion of a V2 session."""
        obj = self._load_payload(session_id)
        if not obj:
            logger.info(f"[V2SessionStore] missing session: {session_id}")
            return None

        stored_user_id = obj.get("user_id")
        if user_id and stored_user_id and stored_user_id != user_id:
            logger.warning(
                f"[V2SessionStore] session user mismatch, "
                f"session_id={session_id}, stored={stored_user_id}, requested={user_id}"
            )
            return None

        obj["last_accessed"] = time.time()
        self._write_raw(self._key(session_id), obj)

        mql = None
        mql_dict = obj.get("mql")
        if mql_dict:
            mql = MQLSchema.from_dict(mql_dict)

        return {
            "mql": mql,
            "history_stack": obj.get("history_stack") or [],
            "conversation_summary": obj.get("conversation_summary"),
            "user_id": stored_user_id or "default",
        }

    def get_mql(self, session_id: str) -> Optional[MQLSchema]:
        """Compatibility helper for callers that only need inherited MQL."""
        context = self.get_context(session_id)
        if not context:
            return None

        mql = context.get("mql")
        logger.info(
            f"[V2SessionStore] restored session={session_id}, "
            f"metric={(mql.metric.name if mql and mql.metric else None)}, "
            f"time={(mql.time.original if mql and mql.time else None)}"
        )
        return mql

    def get_state(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        question: str = "",
    ) -> Optional[V2State]:
        """Rebuild a lightweight V2State from durable session data."""
        context = self.get_context(session_id, user_id=user_id)
        if not context:
            return None

        state = create_v2_state(
            session_id=session_id,
            user_id=context.get("user_id") or user_id or "default",
            question=question,
        )
        state.mql = context.get("mql")
        state.history_stack = list(context.get("history_stack") or [])
        state.conversation_summary = context.get("conversation_summary")
        state.context_cache = ContextScope()
        return state

    def delete(self, session_id: str) -> None:
        self._delete_raw(self._key(session_id))
        logger.info(f"[V2SessionStore] deleted session: {session_id}")

    def clear_all(self) -> None:
        try:
            keys = self._redis.keys("v2:session:*")
        except RedisError as exc:
            logger.warning(f"[V2SessionStore] redis key scan failed, using memory fallback: {exc}")
            keys = list(self._memory_store.keys())

        for key in keys:
            self._delete_raw(key)

        if keys:
            logger.info(f"[V2SessionStore] cleared {len(keys)} sessions")


_store: Optional[V2SessionStore] = None


def get_session_store() -> V2SessionStore:
    global _store
    if _store is None:
        _store = V2SessionStore()
    return _store
