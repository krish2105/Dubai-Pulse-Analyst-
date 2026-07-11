"""
Provider-agnostic LLM layer.

Agents depend on ``LLMProtocol`` (a ``complete()`` method), not a concrete SDK.
``build_llm()`` returns the right client for the configured ``LLM_PROVIDER``:

* ``ollama``    — free, local, no API key (default). OpenAI-compatible endpoint.
* ``groq``      — free tier, OpenAI-compatible, very fast.
* ``openai``    — OpenAI or any OpenAI-compatible base URL (OpenRouter, Together…).
* ``gemini``    — Google Gemini free tier (native REST).
* ``anthropic`` — Claude via the Anthropic SDK.

Because it's an interface, tests inject a deterministic stub and exercise the
whole orchestrator with no provider and no network.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol, runtime_checkable

import httpx

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
        json_mode: bool = False,
    ) -> str:
        ...


# --------------------------------------------------------------------------- #
# OpenAI-compatible client (covers Ollama, Groq, OpenAI, OpenRouter, Together…)
# --------------------------------------------------------------------------- #
class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, settings: Settings) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.settings = settings

    async def complete(self, system, user, *, model=None, max_tokens=None,
                       temperature=None, json_mode=False) -> str:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            logger.error("LLM HTTP %s: %s", exc.response.status_code, body)
            raise LLMError(f"LLM request failed ({exc.response.status_code}): {body}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                f"Could not reach LLM provider at {self.base_url}. "
                f"Is it running / reachable? ({exc})"
            ) from exc

        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected LLM response shape: {str(data)[:200]}") from exc
        if not text:
            raise LLMError("LLM returned an empty response.")
        return text


# --------------------------------------------------------------------------- #
# Gemini client (native REST, free tier)
# --------------------------------------------------------------------------- #
class GeminiClient:
    def __init__(self, api_key: str, model: str, settings: Settings) -> None:
        self.api_key = api_key
        self.model = model
        self.settings = settings

    async def complete(self, system, user, *, model=None, max_tokens=None,
                       temperature=None, json_mode=False) -> str:
        mdl = model or self.model
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{mdl}:generateContent?key={self.api_key}")
        gen: dict[str, Any] = {
            "temperature": self.settings.llm_temperature if temperature is None else temperature,
            "maxOutputTokens": max_tokens or self.settings.llm_max_tokens,
        }
        if json_mode:
            gen["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected Gemini response: {str(data)[:200]}") from exc
        if not text:
            raise LLMError("Gemini returned an empty response.")
        return text


# --------------------------------------------------------------------------- #
# Anthropic client (native SDK)
# --------------------------------------------------------------------------- #
class AnthropicClient:
    def __init__(self, api_key: str, model: str, settings: Settings) -> None:
        self.api_key = api_key
        self.model = model
        self.settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(self, system, user, *, model=None, max_tokens=None,
                       temperature=None, json_mode=False) -> str:
        client = self._get_client()
        try:
            resp = await client.messages.create(
                model=model or self.model,
                max_tokens=max_tokens or self.settings.llm_max_tokens,
                temperature=self.settings.llm_temperature if temperature is None else temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            logger.exception("Anthropic call failed")
            raise LLMError(f"LLM request failed: {exc}") from exc
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        text = "".join(parts).strip()
        if not text:
            raise LLMError("LLM returned an empty response.")
        return text


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def build_llm(settings: Settings | None = None) -> LLMProtocol:
    settings = settings or get_settings()
    provider = settings.provider
    model = settings.resolved_model

    if provider == "ollama":
        return OpenAICompatibleClient(settings.ollama_base_url, "", model, settings)
    if provider == "groq":
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not set (LLM_PROVIDER=groq).")
        return OpenAICompatibleClient(
            "https://api.groq.com/openai/v1", settings.groq_api_key, model, settings
        )
    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not set (LLM_PROVIDER=openai).")
        return OpenAICompatibleClient(
            settings.openai_base_url, settings.openai_api_key, model, settings
        )
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set (LLM_PROVIDER=gemini).")
        return GeminiClient(settings.gemini_api_key, model, settings)
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set (LLM_PROVIDER=anthropic).")
        return AnthropicClient(settings.anthropic_api_key, model, settings)

    raise LLMError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")


# Back-compat alias (older imports used LLMClient()).
def LLMClient(settings: Settings | None = None) -> LLMProtocol:  # noqa: N802
    return build_llm(settings)


# --------------------------------------------------------------------------- #
# JSON / SQL extraction helpers (models sometimes wrap output in prose/fences).
# --------------------------------------------------------------------------- #
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object from an LLM response."""
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else None
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
