"""Shared slowapi rate limiter (per client IP)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Keyed by client IP. Per-route limits are applied via @limiter.limit(...).
limiter = Limiter(key_func=get_remote_address)
