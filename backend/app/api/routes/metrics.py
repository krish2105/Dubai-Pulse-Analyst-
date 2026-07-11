"""Observability endpoints: aggregate metrics + user feedback."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app import telemetry

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def metrics() -> dict:
    """Aggregate request metrics (latency percentiles, tokens, cost, confidence mix)."""
    return telemetry.aggregate()


class Feedback(BaseModel):
    request_id: str = Field(..., max_length=64)
    rating: str = Field(..., pattern="^(up|down)$")
    comment: str = Field(default="", max_length=500)


@router.post("/feedback")
async def feedback(body: Feedback) -> dict:
    """Record a 👍/👎 on an answer (feeds the eval loop)."""
    telemetry.record_feedback(body.request_id, body.rating, body.comment)
    return {"ok": True}
