from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://linkedin_user:changeme@localhost:5432/linkedin_intelligence"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str = "dev-secret-change-in-production"
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    # Email (SMTP) — optional, required for weekly digest
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    ENVIRONMENT: str = "development"
    UPLOAD_DIR: str = "/tmp/cv_uploads"

    # JWT settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"


settings = Settings()
