"""
DubaiPulse Analyst — FastAPI application entrypoint.

Wires together: structured logging, CORS, API-key auth, rate limiting, the
health / insights / chat routes, and a lifespan that warms up the DuckDB engine
and the compiled agent graph so the first request is fast.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.routes import chat, health, insights, metrics
from app.config import get_settings
from app.middleware import APIKeyMiddleware
from app.rate_limit import limiter
from app.security import SecurityHeadersMiddleware

# --------------------------------------------------------------------------- #
# Structured logging (console). Every agent step also logs here → audit trail.
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("dubaipulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting DubaiPulse Analyst (env=%s)…", settings.app_env)
    # Warm up the data engine + orchestrator (compiles the LangGraph, registers views).
    try:
        chat.get_orchestrator()
        logger.info("Orchestrator + DuckDB engine ready. LLM configured: %s", settings.llm_enabled)
    except Exception:
        logger.exception("Warm-up failed — check that the data pipeline has been run.")
    yield
    logger.info("Shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DubaiPulse Analyst API",
        description="Agentic market-intelligence copilot for Dubai real estate.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # --- Rate limiting ---
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded: {exc.detail}. Please slow down."},
        )

    # --- Never leak stack traces ---
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # pragma: no cover
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    # --- CORS (before auth so preflight works) ---
    # We authenticate via the X-API-Key header, not cookies, so credentials are
    # not needed. That lets CORS_ORIGINS="*" work (handy for first deploy before
    # the exact frontend URL is known) while staying safe behind the API key.
    origins = settings.cors_origin_list
    allow_all = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- API-key auth for protected routes ---
    app.add_middleware(APIKeyMiddleware)

    # --- Security headers on every response ---
    app.add_middleware(SecurityHeadersMiddleware)

    # --- Routes ---
    app.include_router(health.router)
    app.include_router(insights.router)
    app.include_router(metrics.router)
    app.include_router(chat.router)

    @app.get("/", tags=["health"])
    async def root() -> dict:
        return {
            "service": "DubaiPulse Analyst",
            "docs": "/docs",
            "endpoints": ["/health", "/insights", "POST /chat (SSE)"],
        }

    return app


app = create_app()
