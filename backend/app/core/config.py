from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Conflux HQ"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Supabase Session pooler; replace placeholders in .env before connecting.
    # SQLite is an explicit offline/test option, never a silent fallback.
    database_url: str = "postgresql+psycopg://postgres.PROJECT_REF:DB_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require"
    demo_mode: bool = True
    demo_username: str = "Zymic Bank"
    demo_password: str = "123"
    demo_token_secret: str = ""  # required: set a random secret of at least 32 characters
    demo_token_minutes: int = Field(default=120, ge=1, le=1440)
    social_adapter_token: str = ""  # simulator/webhook bearer credential, not the Supabase service key
    auto_create_tables: bool = False  # use Alembic migrations; True only for throwaway SQLite
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""  # server only, never expose to the browser
    supabase_jwt_secret: str = ""  # legacy HS256 projects; leave empty to verify via JWKS
    supabase_jwt_audience: str = "authenticated"
    site_url: str = "http://localhost:5173"  # where invite emails send people

    ai_provider: str = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_timeout_seconds: float = 15.0
    anthropic_max_retries: int = 1
    anthropic_max_attempts: int = 2

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 15.0
    gemini_max_retries: int = 1
    gemini_max_attempts: int = 2

    spike_bucket_minutes: int = 15
    spike_baseline_hours: int = 24
    spike_mad_multiplier: float = 3.0
    spike_min_volume: int = 10

    @model_validator(mode="after")
    def _demo_is_not_production(self):
        if self.demo_mode and self.environment.lower() in {"production", "prod"}:
            raise ValueError("DEMO_MODE must be disabled in production")
        return self

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        """Accept the plain URL Supabase shows and use the psycopg 3 driver."""
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
