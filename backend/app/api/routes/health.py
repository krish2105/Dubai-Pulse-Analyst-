"""Health & readiness endpoints (unauthenticated)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.tools.duckdb_engine import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness + readiness: confirms the data layer is queryable and reports config."""
    settings = get_settings()
    engine = get_engine()
    try:
        res = engine.run_query("SELECT count(*) AS n FROM transactions")
        rows = res.rows[0]["n"] if res.rows else 0
        data_ok = res.error is None
    except Exception as exc:  # pragma: no cover
        rows, data_ok = 0, False
        _ = exc
    return {
        "status": "ok" if data_ok else "degraded",
        "service": "dubaipulse-analyst",
        "env": settings.app_env,
        "data": {"transactions": rows, "ready": data_ok},
        "llm_configured": settings.llm_enabled,
        "auth_enabled": bool(settings.backend_api_key),
    }
