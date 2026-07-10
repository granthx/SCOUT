"""
app/services/session_service.py
────────────────────────────────
Per-user session management.

Fixes ShoppingGPT's #1 architecture flaw:
  ❌ SHARED_MEMORY = ConversationBufferMemory()   ← one object for ALL users
  ✅ Each session_id maps to its own Session object

Sessions are stored in Redis (with JSON serialisation) if available,
otherwise in a local TTL-cache dictionary.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from cachetools import TTLCache

from app.config import get_settings
from app.models.session import Session

settings = get_settings()

# Local fallback store: 10 000 sessions, each expires after session_ttl_seconds
_local_store: TTLCache = TTLCache(
    maxsize=10_000, ttl=settings.session_ttl_seconds
)

try:
    import redis.asyncio as aioredis
    _USE_REDIS = bool(settings.redis_url)
except ImportError:
    _USE_REDIS = False


class SessionService:
    def __init__(self) -> None:
        self._redis: object = None
        if _USE_REDIS:
            self._redis = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )

    # ── public API ────────────────────────────────────────────────────────────

    async def get_or_create(self, session_id: Optional[str]) -> Session:
        """Return an existing session or create a fresh one."""
        if session_id:
            existing = await self._load(session_id)
            if existing:
                return existing
        # Create new
        new_id = session_id or str(uuid.uuid4())
        session = Session(session_id=new_id)
        await self._save(session)
        return session

    async def save(self, session: Session) -> None:
        session.last_active = datetime.now(timezone.utc)
        await self._save(session)

    async def delete(self, session_id: str) -> None:
        key = self._key(session_id)
        if self._redis:
            try:
                await self._redis.delete(key)  # type: ignore[attr-defined]
            except Exception:
                pass
        _local_store.pop(key, None)

    # ── internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

    async def _load(self, session_id: str) -> Optional[Session]:
        key = self._key(session_id)
        raw: Optional[str] = None
        if self._redis:
            try:
                raw = await self._redis.get(key)  # type: ignore[attr-defined]
            except Exception:
                pass
        if raw is None:
            raw = _local_store.get(key)
        if raw is None:
            return None
        data = json.loads(raw) if isinstance(raw, str) else raw
        return Session.model_validate(data)

    async def _save(self, session: Session) -> None:
        key = self._key(session.session_id)
        payload = session.model_dump_json()
        if self._redis:
            try:
                await self._redis.setex(  # type: ignore[attr-defined]
                    key, settings.session_ttl_seconds, payload
                )
                return
            except Exception:
                pass
        _local_store[key] = json.loads(payload)


_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
