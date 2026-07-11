"""
Central configuration for the DubaiPulse Analyst backend.

All settings come from environment variables (12-factor style). Nothing secret
is ever hard-coded. Values are loaded from the process environment and, for
local development, from a ``.env`` file (see ``.env.example``).

The LLM layer is provider-agnostic: set ``LLM_PROVIDER`` to one of
``ollama`` (free, local, no key) · ``groq`` (free tier) · ``gemini`` (free tier)
· ``openai`` · ``anthropic``. Each provider has a sensible default model.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Default model per provider (used when LLM_MODEL is blank).
_DEFAULT_MODELS = {
    "ollama": "qwen2.5:7b",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5",
}


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- LLM provider selection ----
    # Free & local by default (Ollama needs no API key).
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_model: str = Field(default="", alias="LLM_MODEL")   # blank → provider default
    llm_max_tokens: int = Field(default=1500, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    llm_timeout: int = Field(default=180, alias="LLM_TIMEOUT")

    # ---- Provider credentials / endpoints ----
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434/v1", alias="OLLAMA_BASE_URL")

    # ---- API auth ----
    # If empty, the API-key middleware is disabled (handy for local dev / CI).
    backend_api_key: str = Field(default="", alias="BACKEND_API_KEY")

    # ---- CORS (comma-separated origins, or '*') ----
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS")

    # ---- Rate limiting ----
    rate_limit: str = Field(default="20/minute", alias="RATE_LIMIT")

    # ---- Data ----
    processed_dir: Path = Field(default=BACKEND_DIR / "data" / "processed")

    # ---- Query engine safety ----
    max_result_rows: int = Field(default=2000, alias="MAX_RESULT_ROWS")

    # ---- Security ----
    guardrail_enabled: bool = Field(default=True, alias="GUARDRAIL_ENABLED")
    security_headers_enabled: bool = Field(default=True, alias="SECURITY_HEADERS_ENABLED")
    max_concurrent_requests: int = Field(default=4, alias="MAX_CONCURRENT_REQUESTS")

    # ---- Redis (caching + distributed rate limiting); blank -> in-memory ----
    redis_url: str = Field(default="", alias="REDIS_URL")
    cache_ttl: int = Field(default=3600, alias="CACHE_TTL")

    # ---- Observability ----
    telemetry_enabled: bool = Field(default=True, alias="TELEMETRY_ENABLED")

    # ---- App ----
    app_env: str = Field(default="development", alias="APP_ENV")

    # ------------------------------------------------------------------ #
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider(self) -> str:
        return self.llm_provider.strip().lower()

    @property
    def resolved_model(self) -> str:
        """The model to use: explicit override, else the provider default."""
        return self.llm_model.strip() or _DEFAULT_MODELS.get(self.provider, "")

    @property
    def llm_enabled(self) -> bool:
        """True when the selected provider is usable (local, or key present)."""
        p = self.provider
        if p == "ollama":
            return True  # local, no key required
        if p == "anthropic":
            return bool(self.anthropic_api_key.strip())
        if p == "groq":
            return bool(self.groq_api_key.strip())
        if p == "openai":
            return bool(self.openai_api_key.strip())
        if p == "gemini":
            return bool(self.gemini_api_key.strip())
        return False


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
