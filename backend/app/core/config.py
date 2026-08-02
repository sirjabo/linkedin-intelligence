from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://linkedin_user:changeme@localhost:5432/linkedin_intelligence"
    ANTHROPIC_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    ENVIRONMENT: str = "development"
    UPLOAD_DIR: str = "/tmp/cv_uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
