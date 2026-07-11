"""
Agent event streaming.

Every specialist agent emits step events (running / complete / …) so the
frontend can render a *live* reasoning trace — not just a final blob. We use a
context-local emitter so agent nodes can emit without threading a callback
through LangGraph state (which stays clean + serialisable).

The chat route:
  1. creates an ``AgentEventStream``,
  2. installs it via ``use_emitter(...)`` before running the orchestrator,
  3. iterates the stream, forwarding each event to the client as SSE.
"""

from __future__ import annotations

import asyncio
import contextvars
import time
from dataclasses import asdict, dataclass, field
from typing import Any

# Context-local current emitter. Copied into child tasks/coroutines at creation,
# so LangGraph nodes (run within the same async context) can emit transparently.
_current_stream: contextvars.ContextVar[AgentEventStream | None] = contextvars.ContextVar(
    "current_agent_stream", default=None
)


@dataclass
class AgentEvent:
    """A single streamed reasoning-trace event."""

    type: str                      # 'agent_step' | 'final' | 'error'
    agent: str                     # 'orchestrator' | 'query_agent' | ...
    status: str = "running"        # 'running' | 'complete' | 'skipped' | 'error'
    detail: str = ""               # human-readable one-liner
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=lambda: round(time.time(), 3))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentEventStream:
    """An async queue of AgentEvents with a completion sentinel."""

    _SENTINEL = object()

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue()

    async def emit(self, event: AgentEvent) -> None:
        await self._queue.put(event)

    async def close(self) -> None:
        await self._queue.put(self._SENTINEL)

    async def __aiter__(self):
        while True:
            item = await self._queue.get()
            if item is self._SENTINEL:
                return
            yield item


class use_emitter:
    """Context manager that installs an AgentEventStream as the current emitter."""

    def __init__(self, stream: AgentEventStream) -> None:
        self._stream = stream
        self._token: contextvars.Token | None = None

    def __enter__(self) -> AgentEventStream:
        self._token = _current_stream.set(self._stream)
        return self._stream

    def __exit__(self, *exc: object) -> None:
        if self._token is not None:
            _current_stream.reset(self._token)


async def emit_event(
    agent: str,
    status: str = "running",
    detail: str = "",
    *,
    type: str = "agent_step",
    **data: Any,
) -> None:
    """Emit an event to the current stream (no-op if none installed, e.g. tests)."""
    stream = _current_stream.get()
    if stream is None:
        return
    await stream.emit(AgentEvent(type=type, agent=agent, status=status, detail=detail, data=data))
