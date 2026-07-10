"""
app/services/cache_service.py
──────────────────────────────
Redis-backed cache with a transparent in-memory fallback.
Product search results are cached to reduce API costs and latency.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from cachetools import TTLCache

from app.config import get_settings

settings = get_settings()

# In-memory fallback: up to 2 000 items, each lives for cache_ttl_seconds
_local: TTLCache = TTLCache(maxsize=2000, ttl=settings.cache_ttl_seconds)

try:
    import redis.asyncio as aioredis
    _USE_REDIS = bool(settings.redis_url)
except ImportError:
    _USE_REDIS = False


class CacheService:
    def __init__(self) -> None:
        self._redis: Any = None
        if _USE_REDIS:
            self._redis = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )

    async def get(self, key: str) -> Optional[Any]:
        if self._redis:
            try:
                val = await self._redis.get(key)
                return json.loads(val) if val else None
            except Exception:
                pass  # fall through to local
        return _local.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or settings.cache_ttl_seconds
        if self._redis:
            try:
                await self._redis.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass
        _local[key] = value  # TTLCache handles expiry automatically

    async def delete(self, key: str) -> None:
        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
        _local.pop(key, None)

    async def is_connected(self) -> bool:
        if self._redis:
            try:
                await self._redis.ping()
                return True
            except Exception:
                return False
        return False   # using local cache — not "connected" in the Redis sense


_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
