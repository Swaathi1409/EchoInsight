"""
Application settings loaded from environment variables.
All settings are validated at startup via Pydantic-settings.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    groq_api_key: str = Field(description="Groq API key")
    llm_primary_model: str = "qwen/qwen3.8-27b"
    llm_verifier_model: str = "openai/gpt-oss-20b"
    llm_daily_token_budget: int = 400_000
    llm_max_concurrency: int = 3
    llm_request_timeout: float = 60.0
    llm_max_retries: int = 3

    # Database
    database_url: str = "sqlite+aiosqlite:///./dev_local.db"

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = Field(description="64-char hex secret for JWT signing")
    access_token_expire_minutes: int = 30

    # Privacy
    store_original_text: bool = False

    # Features
    embeddings_enabled: bool = False
    action_layer_enabled: bool = False

    # CORS
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Observability
    enable_metrics: bool = True

    # Seed users (comma-separated username:password:role)
    seed_users: str = "admin:changeme_admin:admin"

    # Verification thresholds (configurable without code changes)
    qa_confidence_threshold: float = 0.75
    qa_critical_items: list[str] = ["prohibited_promises", "identity_verification", "disclosure"]
    qa_max_verification_items: int = 5

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "production", "test"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings. Call once at startup."""
    return Settings()
