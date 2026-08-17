"""Application settings via Pydantic Settings v2."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    SECRET_KEY: str = Field(
        default="dev-secret-change-in-production-min-16",
        min_length=16,
    )
    DEBUG: bool = True
    APP_VERSION: str = "0.1.0"

    DATABASE_URL: str = (
        "postgresql+asyncpg://linkedin_user:changeme@localhost:5432/linkedin_intelligence"
    )
    REDIS_URL: str = "memory://"

    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    UPLOAD_DIR: str = "/tmp/cv_uploads"

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://frontend:3000",
        ]
    )

    RATE_LIMIT_ANONYMOUS: str = "30/minute"
    RATE_LIMIT_AUTHENTICATED: str = "60/minute"
    DATA_FRESHNESS_HOURS: int = 24

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
