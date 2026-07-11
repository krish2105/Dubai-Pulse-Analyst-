"""
API-key authentication middleware.

Lightweight protection for the analysis endpoints: any request to a protected
path must carry the shared secret in the ``X-API-Key`` header. Health and docs
stay open. If ``BACKEND_API_KEY`` is unset (local dev / CI), auth is disabled.
"""

from __future__ import annotations

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger("dubaipulse.auth")

# Paths that require the API key.
_PROTECTED_PREFIXES = ("/chat", "/insights")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path

        # CORS preflight must never be blocked.
        if request.method == "OPTIONS":
            return await call_next(request)

        needs_auth = any(path.startswith(p) for p in _PROTECTED_PREFIXES)
        if needs_auth and settings.backend_api_key:
            provided = request.headers.get("x-api-key", "")
            # Constant-time comparison to avoid timing attacks.
            if not hmac.compare_digest(provided, settings.backend_api_key):
                logger.warning("Rejected unauthenticated request to %s", path)
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid API key (X-API-Key header)."},
                )
        return await call_next(request)
