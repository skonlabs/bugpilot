from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://bugpilot:bugpilot@localhost:5432/bugpilot"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    FERNET_KEY: str = ""  # Auto-generated if empty

    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    ACTIVATION_RATE_LIMIT_PER_HOUR: int = 10
    SECRET_GRACE_PERIOD_HOURS: int = 24

    # Connector timeouts
    CONNECTOR_TIMEOUT_SECONDS: int = 30
    CONNECTOR_MAX_RETRIES: int = 3

    # Evidence TTL
    EVIDENCE_TTL_MINUTES: int = 10


@lru_cache()
def get_settings() -> Settings:
    return Settings()
