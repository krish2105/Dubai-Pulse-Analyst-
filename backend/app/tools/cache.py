"""
Small async cache with a Redis backend (when REDIS_URL is set) and an in-memory
TTL fallback otherwise. Used for the deterministic, computation-heavy data
endpoints (insights / geo / analytics) so repeat loads are instant and, in
production, shared across instances.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import get_settings

_mem: dict[str, tuple[Any, float]] = {}
_redis: Any = None
_redis_tried = False


def _get_redis():
    global _redis, _redis_tried
    settings = get_settings()
    if not settings.redis_url:
        return None
    if _redis is None and not _redis_tried:
        _redis_tried = True
        try:
            import redis.asyncio as aioredis

            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            _redis = None
    return _redis


async def cached_json(key: str, compute: Callable[[], Awaitable[Any] | Any], ttl: int | None = None) -> Any:
    """Return cached JSON for ``key`` or compute+store it. ``compute`` may be sync or async."""
    settings = get_settings()
    ttl = ttl if ttl is not None else settings.cache_ttl
    r = _get_redis()

    # 1) read
    if r is not None:
        try:
            hit = await r.get(key)
            if hit is not None:
                return json.loads(hit)
        except Exception:
            pass
    else:
        item = _mem.get(key)
        if item is not None and item[1] > time.time():
            return item[0]

    # 2) compute
    value = compute()
    if hasattr(value, "__await__"):
        value = await value  # type: ignore[assignment]

    # 3) write
    if r is not None:
        try:
            await r.setex(key, ttl, json.dumps(value, default=str))
        except Exception:
            pass
    else:
        _mem[key] = (value, time.time() + ttl)
    return value
