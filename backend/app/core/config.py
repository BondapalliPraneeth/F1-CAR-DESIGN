from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ApexVision 3D API"
    environment: str = "development"
    # PostgreSQL in production (Neon), e.g. postgresql+psycopg://user:pass@host/db?sslmode=require
    # Falls back to a local SQLite file so the API runs with zero setup.
    database_url: str = "sqlite:///./apexvision.db"
    # Neon's direct (non-pooled) connection. Used only for Alembic migrations (DDL); the app uses the pooled DATABASE_URL.
    database_url_unpooled: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # AI assistant. provider: auto | gemini | openai | neon | offline
    ai_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Neon AI Gateway (OpenAI-compatible chat completions); vars are written by `neon deploy` / `neon env pull`.
    neon_ai_gateway_base_url: str | None = None
    neon_ai_gateway_token: str | None = None
    neon_ai_model: str = "claude-haiku-4-5"
    ai_rate_limit_per_minute: int = 12
    ai_global_rate_limit_per_minute: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        return _with_driver(self.database_url)

    @property
    def migration_url(self) -> str:
        return _with_driver(self.database_url_unpooled or self.database_url)


def _with_driver(url: str) -> str:
    # Neon / Render hand out postgres:// URLs; SQLAlchemy needs an explicit driver.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
