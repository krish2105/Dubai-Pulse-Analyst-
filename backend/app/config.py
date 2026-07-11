"""
Central configuration for the DubaiPulse Analyst backend.

All settings come from environment variables (12-factor style). Nothing secret
is ever hard-coded. Values are loaded from the process environment and, for
local development, from a ``.env`` file (see ``.env.example``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- LLM ----
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")
    # A smaller/faster model can be used for the mechanical NL->SQL step.
    anthropic_sql_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_SQL_MODEL")
    llm_max_tokens: int = Field(default=1500, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    # ---- API auth ----
    # If empty, the API-key middleware is disabled (handy for local dev / CI).
    backend_api_key: str = Field(default="", alias="BACKEND_API_KEY")

    # ---- CORS (comma-separated origins) ----
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS")

    # ---- Rate limiting ----
    rate_limit: str = Field(default="20/minute", alias="RATE_LIMIT")

    # ---- Data ----
    processed_dir: Path = Field(default=BACKEND_DIR / "data" / "processed")

    # ---- Query engine safety ----
    max_result_rows: int = Field(default=2000, alias="MAX_RESULT_ROWS")

    # ---- App ----
    app_env: str = Field(default="development", alias="APP_ENV")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        """True when a real Anthropic key is configured."""
        return bool(self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
