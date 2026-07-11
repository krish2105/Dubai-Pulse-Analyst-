"""
Chat endpoint — streams the multi-agent investigation over Server-Sent Events.

POST /chat  { "question": "..." }  ->  text/event-stream

Event types (SSE ``event:`` field):
  * ``agent_step`` — one per agent transition (running / complete / error). The
    frontend renders these live in the Reasoning Trace panel.
  * ``final``      — the finished answer + citations + verification/confidence.
  * ``error``      — an unrecoverable error (surfaced cleanly, no stack traces).
  * ``done``       — terminal marker so the client can close the stream.
"""

# NOTE: intentionally NOT using `from __future__ import annotations` here.
# The slowapi @limiter.limit wrapper has different __globals__, so stringized
# annotations (ChatRequest) would fail FastAPI's forward-ref resolution and the
# request body would be mis-read as a query param.

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agents.events import AgentEvent, AgentEventStream
from app.agents.orchestrator import Orchestrator
from app.config import get_settings
from app.rate_limit import limiter

logger = logging.getLogger("dubaipulse.chat")

router = APIRouter(tags=["chat"])

# Single compiled orchestrator (graph + DuckDB views) reused across requests.
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    history: list[Turn] = Field(default_factory=list, max_length=20)
    language: str = Field(default="auto")  # 'auto' | 'en' | 'ar'


def _sse(event: AgentEvent) -> dict:
    return {"event": event.type, "data": json.dumps(event.to_dict(), default=str)}


@router.post("/chat")
@limiter.limit(get_settings().rate_limit)
async def chat(request: Request, body: ChatRequest):
    question = body.question.strip()
    history = [t.model_dump() for t in body.history]
    language = body.language
    logger.info("Chat question (lang=%s, %d prior turns): %s", language, len(history), question)
    orchestrator = get_orchestrator()

    async def event_generator():
        stream = AgentEventStream()

        async def run_and_close():
            try:
                await orchestrator.run(question, stream, history=history, language=language)
            except Exception as exc:  # never leak a stack trace to the client
                logger.exception("Orchestrator failed")
                await stream.emit(
                    AgentEvent(
                        type="error", agent="orchestrator", status="error",
                        detail="The analysis engine hit an unexpected error. Please try again.",
                        data={"error_class": exc.__class__.__name__},
                    )
                )
            finally:
                await stream.close()

        task = asyncio.create_task(run_and_close())
        try:
            async for event in stream:
                # Stop early if the client disconnected.
                if await request.is_disconnected():
                    break
                yield _sse(event)
            yield {"event": "done", "data": "{}"}
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

    return EventSourceResponse(event_generator())
