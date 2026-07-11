"""
Thin async wrapper around the Anthropic (Claude) API.

Design goals
------------
* One place that knows how to talk to Claude (model, tokens, temperature, retries).
* An ``LLMProtocol`` so agents depend on an *interface*, not the concrete client.
  This lets tests inject a deterministic stub and exercise the full orchestrator
  (routing, real DuckDB execution, verifier) with **no API key and no network**.
* JSON helpers for the structured NL->SQL step.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol, runtime_checkable

from app.config import Settings, get_settings

logger = logging.getLogger("dubaipulse.llm")


class LLMError(Exception):
    """Raised when the LLM call fails or returns unusable output."""


@runtime_checkable
class LLMProtocol(Protocol):
    """The minimal surface agents rely on."""

    async def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        ...


class LLMClient:
    """Concrete Anthropic-backed client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any | None = None  # lazy — don't require a key at import time

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.llm_enabled:
                raise LLMError(
                    "ANTHROPIC_API_KEY is not set. Configure it in backend/.env to run the agents."
                )
            # Imported lazily so the package imports fine without the key/lib present.
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    async def complete(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        client = self._get_client()
        try:
            resp = await client.messages.create(
                model=model or self.settings.anthropic_model,
                max_tokens=max_tokens or self.settings.llm_max_tokens,
                temperature=self.settings.llm_temperature if temperature is None else temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # anthropic.APIError etc.
            logger.exception("Anthropic call failed")
            raise LLMError(f"LLM request failed: {exc}") from exc

        # Concatenate text blocks.
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        text = "".join(parts).strip()
        if not text:
            raise LLMError("LLM returned an empty response.")
        return text


# --------------------------------------------------------------------------- #
# JSON extraction helpers (models sometimes wrap JSON in prose or code fences).
# --------------------------------------------------------------------------- #
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object from an LLM response."""
    # 1) fenced json
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else None
    # 2) first {...} span
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
    if candidate is None:
        raise LLMError(f"No JSON object found in LLM output: {text[:200]}")
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from LLM: {exc}") from exc


def extract_sql(text: str) -> str:
    """Pull a SQL statement out of an LLM response (fenced or raw)."""
    m = _SQL_FENCE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()
