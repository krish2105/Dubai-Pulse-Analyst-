"""
Security middleware & concurrency control.

* ``SecurityHeadersMiddleware`` — adds standard hardening headers
  (nosniff, anti-clickjacking, referrer policy, permissions policy, and HSTS in
  production). See the OWASP secure-headers guidance.
* ``ConcurrencyLimiter`` — a global bound on in-flight expensive (LLM) requests
  so a burst can't exhaust the box (OWASP LLM10: Unbounded Consumption).
"""

from __future__ import annotations

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        settings = get_settings()
        if settings.security_headers_enabled:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            # frame-ancestors 'none' hardens against clickjacking without
            # breaking the Swagger UI at /docs (which needs script/style).
            response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
            if settings.app_env == "production":
                response.headers.setdefault(
                    "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                )
        return response


class ConcurrencyLimiter:
    """Bounds concurrent expensive requests. `acquire()` returns False if full."""

    def __init__(self, limit: int) -> None:
        self.limit = max(1, limit)
        self._active = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            if self._active >= self.limit:
                return False
            self._active += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)

    @property
    def active(self) -> int:
        return self._active


_limiter: ConcurrencyLimiter | None = None


def get_concurrency_limiter() -> ConcurrencyLimiter:
    global _limiter
    if _limiter is None:
        _limiter = ConcurrencyLimiter(get_settings().max_concurrent_requests)
    return _limiter
