from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    PROJECT_NAME: str = "IncidentAI Backend"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "*"
    ]

    # Database (Defaults to SQLite for instant local execution)
    DATABASE_URL: str = "sqlite+aiosqlite:///./incidentai.db"

    # Redis (Fallback to in-memory event bus if unavailable)
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI / LLM Configuration
    DEFAULT_LLM_PROVIDER: str = "mock"  # "mock", "openai", "gemini", "anthropic"
    DEFAULT_LLM_MODEL: str = "mock-incident-gpt"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Telemetry
    TELEMETRY_MODE: str = "synthetic"  # "synthetic" or "live"
    PROMETHEUS_URL: str = "http://localhost:9090"
    LOKI_URL: str = "http://localhost:3100"
    JAEGER_URL: str = "http://localhost:16686"


settings = Settings()
