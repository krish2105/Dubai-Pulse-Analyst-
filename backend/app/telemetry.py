"""
Lightweight, dependency-free observability for the agent pipeline.

Captures per-request metrics — latency, LLM call count, (estimated) token usage
and cost, plus routing/verification outcome — using a context-local record, an
in-memory ring buffer (for the /metrics endpoint), and an append-only JSONL
audit log (the audit trail the README promises).

Tokens are *estimated* from text length (≈ 4 chars/token) so the numbers are
provider-agnostic and require no changes to the LLM interface. Cost is derived
from a configurable per-1K-token rate (0 for local Ollama).
"""

from __future__ import annotations

import contextvars
import json
import statistics
import threading
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

from app.config import BACKEND_DIR, get_settings

# Rough USD cost per 1K tokens by provider (local is free).
_COST_PER_1K = {"ollama": 0.0, "groq": 0.0, "gemini": 0.0, "openai": 0.0015, "anthropic": 0.003}

_LOG_DIR = BACKEND_DIR / "logs"
_TELEMETRY_LOG = _LOG_DIR / "telemetry.jsonl"

_ring: deque[dict[str, Any]] = deque(maxlen=500)
_lock = threading.Lock()
_current: contextvars.ContextVar[RequestMetrics | None] = contextvars.ContextVar(
    "request_metrics", default=None
)


@dataclass
class RequestMetrics:
    request_id: str
    question: str
    t0: float
    llm_calls: int = 0
    prompt_chars: int = 0
    completion_chars: int = 0
    route: str | None = None
    confidence: str | None = None
    verified: bool | None = None
    blocked: bool = False
    retries: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _est_tokens(chars: int) -> int:
    return max(0, chars // 4)


def start_request(question: str) -> RequestMetrics:
    m = RequestMetrics(request_id=uuid.uuid4().hex[:12], question=question, t0=time.time())
    _current.set(m)
    return m


def record_llm(prompt_chars: int, completion_chars: int) -> None:
    m = _current.get()
    if m is not None:
        m.llm_calls += 1
        m.prompt_chars += max(0, prompt_chars)
        m.completion_chars += max(0, completion_chars)


def snapshot() -> dict[str, Any]:
    """Current metrics (for embedding in the final SSE event)."""
    m = _current.get()
    if m is None:
        return {}
    pt, ct = _est_tokens(m.prompt_chars), _est_tokens(m.completion_chars)
    rate = _COST_PER_1K.get(get_settings().provider, 0.0)
    cost = round((pt + ct) / 1000 * rate, 6)
    return {
        "request_id": m.request_id,
        "latency_ms": int((time.time() - m.t0) * 1000),
        "llm_calls": m.llm_calls,
        "est_prompt_tokens": pt,
        "est_completion_tokens": ct,
        "est_total_tokens": pt + ct,
        "est_cost_usd": cost,
        "provider": get_settings().provider,
        "model": get_settings().resolved_model,
    }


def finish_request(final: dict[str, Any]) -> dict[str, Any]:
    """Fill in the outcome, persist to ring buffer + JSONL, return the record."""
    m = _current.get()
    snap = snapshot()
    if m is None:
        return snap
    m.route = final.get("route")
    m.confidence = final.get("confidence")
    m.verified = final.get("verification", {}).get("verified")
    m.blocked = final.get("blocked", False)
    m.retries = final.get("retries", 0)
    record = {
        **snap,
        "ts": round(time.time(), 3),
        "route": m.route,
        "confidence": m.confidence,
        "verified": m.verified,
        "blocked": m.blocked,
        "retries": m.retries,
        "question": m.question[:200],
    }
    with _lock:
        _ring.append(record)
    if get_settings().telemetry_enabled:
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            with _TELEMETRY_LOG.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass
    return record


def aggregate() -> dict[str, Any]:
    """Aggregate metrics for the /metrics endpoint."""
    with _lock:
        items = list(_ring)
    if not items:
        return {"requests": 0}
    lats = sorted(r["latency_ms"] for r in items)
    toks = [r.get("est_total_tokens", 0) for r in items]
    conf = Counter(r.get("confidence") for r in items)

    def pct(p: float) -> int:
        if not lats:
            return 0
        k = min(len(lats) - 1, int(round(p / 100 * (len(lats) - 1))))
        return lats[k]

    return {
        "requests": len(items),
        "blocked": sum(1 for r in items if r.get("blocked")),
        "latency_ms": {
            "p50": pct(50), "p95": pct(95), "max": lats[-1],
            "mean": int(statistics.mean(lats)),
        },
        "tokens": {"total": sum(toks), "mean_per_request": int(statistics.mean(toks)) if toks else 0},
        "est_cost_usd_total": round(sum(r.get("est_cost_usd", 0) for r in items), 6),
        "confidence_distribution": dict(conf),
        "verified_rate": round(sum(1 for r in items if r.get("verified")) / len(items) * 100, 1),
        "recent": items[-10:][::-1],
    }


# --- Feedback (thumbs up/down) ------------------------------------------------ #
_FEEDBACK_LOG = _LOG_DIR / "feedback.jsonl"


def record_feedback(request_id: str, rating: str, comment: str = "") -> None:
    rec = {"request_id": request_id, "rating": rating, "comment": comment[:500], "ts": round(time.time(), 3)}
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _FEEDBACK_LOG.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass
