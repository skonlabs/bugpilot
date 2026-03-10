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

    # LLM provider — controls which provider BugPilot uses by default.
    # Per-org config in Organization.settings["llm"] takes precedence over these.
    #
    # LLM_PROVIDER options:
    #   "anthropic"          — Anthropic Claude (BugPilot default)
    #   "openai"             — OpenAI GPT
    #   "azure_openai"       — Azure-hosted OpenAI deployment
    #   "ollama"             — Local Ollama instance
    #   "openai_compatible"  — Any OpenAI-compatible endpoint (vLLM, Groq, Together, etc.)
    LLM_PROVIDER: str = "anthropic"
    LLM_API_KEY: str = ""           # API key (not needed for Ollama / unauthenticated endpoints)
    LLM_MODEL: str = ""             # Model name; provider default is used when empty
    LLM_BASE_URL: str = ""          # Required for azure_openai, ollama, openai_compatible
    LLM_TIMEOUT_SECONDS: float = 60.0

    # Azure OpenAI extras (only used when LLM_PROVIDER=azure_openai)
    LLM_AZURE_DEPLOYMENT: str = ""
    LLM_AZURE_API_VERSION: str = "2024-02-01"

    # Cost tracking for openai_compatible (USD per million tokens)
    LLM_INPUT_COST_PER_M: float = 0.0
    LLM_OUTPUT_COST_PER_M: float = 0.0

    # Supabase
    # Get these from your Supabase project: Settings → API
    SUPABASE_URL: str = ""           # https://<project-ref>.supabase.co
    SUPABASE_ANON_KEY: str = ""      # public anon key (safe for client-side)
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # service role key (server-side only, bypasses RLS)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
