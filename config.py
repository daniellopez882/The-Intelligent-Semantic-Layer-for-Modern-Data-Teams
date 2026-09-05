"""
Settings.

The previous code read the environment in three places with three different
ideas of what was configured: ``agent.py`` wanted ``DEEPSEEK_API_KEY`` and
hardcoded the DeepSeek base URL and model; ``app.py`` chose the database from
``DATABASE_TYPE`` and ``POSTGRES_DB_URL``; nothing validated any of it, so a
missing Postgres URL reached ``SQLDatabase.from_uri(None)``.

One model provider is supported: any OpenAI-compatible endpoint. DeepSeek is
the default because that is what the code was written against; it is not a
requirement.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_DATABASE_URL = "sqlite:///ecommerce.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Model: any OpenAI-compatible endpoint.
    LLM_API_KEY: str = Field(default="", validation_alias="LLM_API_KEY")
    LLM_BASE_URL: str = DEFAULT_BASE_URL
    LLM_MODEL: str = DEFAULT_MODEL
    LLM_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)

    # The database the agent may read. Opened read-only; see db.py.
    DATABASE_URL: str = DEFAULT_DATABASE_URL

    # Rows returned to the model and to the page, per query.
    MAX_ROWS: int = Field(default=100, ge=1, le=10_000)

    # How many prior turns to show the model.
    HISTORY_TURNS: int = Field(default=3, ge=0, le=20)

    # Where "Correct / Incorrect" feedback is appended. Empty disables it.
    FEEDBACK_PATH: str = "evaluations.csv"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def has_llm_key(self) -> bool:
        return bool(self.LLM_API_KEY.strip())

    @model_validator(mode="after")
    def _accept_legacy_key(self) -> Settings:
        # DEEPSEEK_API_KEY was the only name the old code knew.
        if not self.LLM_API_KEY.strip():
            import os

            legacy = os.getenv("DEEPSEEK_API_KEY", "").strip()
            if legacy:
                object.__setattr__(self, "LLM_API_KEY", legacy)
        return self

    def problems(self) -> list[str]:
        found: list[str] = []
        if not self.has_llm_key:
            found.append("LLM_API_KEY is not set (DEEPSEEK_API_KEY is accepted as an alias).")
        if not self.DATABASE_URL.strip():
            found.append("DATABASE_URL is empty.")
        return found


settings = Settings()
