"""Shared slowapi rate limiter (per client IP).

Uses Redis for distributed, multi-instance-safe limiting when REDIS_URL is set;
otherwise falls back to in-process memory storage (fine for single-instance /
local dev).
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()
# limits/slowapi understands redis://… and memory:// storage URIs.
_storage_uri = _settings.redis_url.strip() or "memory://"

limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
