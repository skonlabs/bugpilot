"""
Settings loaded from environment variables.
All configuration comes from the environment — no defaults for secrets.
"""
from __future__ import annotations

import os


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Required environment variable {key!r} is not set")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class Settings:
    # ── Supabase ──────────────────────────────────────────────
    SUPABASE_URL: str = _require("SUPABASE_URL")
    SUPABASE_SERVICE_KEY: str = _require("SUPABASE_SERVICE_KEY")
    SUPABASE_ANON_KEY: str = _optional("SUPABASE_ANON_KEY")
    DATABASE_URL: str = _require("DATABASE_URL")
    DATABASE_POOL_SIZE: int = int(_optional("DATABASE_POOL_SIZE", "20"))
    DATABASE_MIN_POOL: int = int(_optional("DATABASE_MIN_POOL", "2"))

    # ── Redis ──────────────────────────────────────────────────
    REDIS_URL: str = _require("REDIS_URL")

    # ── AWS ───────────────────────────────────────────────────
    AWS_REGION: str = _optional("AWS_REGION", "us-east-1")
    AWS_SQS_P1_URL: str = _optional("AWS_SQS_P1_URL")
    AWS_SQS_P2_URL: str = _optional("AWS_SQS_P2_URL")
    AWS_SQS_RETRO_URL: str = _optional("AWS_SQS_RETRO_URL")
    AWS_SNS_TOPIC_ARN: str = _optional("AWS_SNS_TOPIC_ARN")

    # ── LLM ───────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = _optional("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str = _optional("OPENAI_API_KEY")

    # ── Connector config encryption ───────────────────────────
    CONNECTOR_ENCRYPTION_KEY: str = _optional("CONNECTOR_ENCRYPTION_KEY")

    # ── Slack ─────────────────────────────────────────────────
    SLACK_SIGNING_SECRET: str = _optional("SLACK_SIGNING_SECRET")

    # ── App ───────────────────────────────────────────────────
    BUGPILOT_ENV: str = _optional("BUGPILOT_ENV", "development")
    BUGPILOT_BASE_URL: str = _optional("BUGPILOT_BASE_URL", "https://api.bugpilot.io")
    LOG_LEVEL: str = _optional("LOG_LEVEL", "info")
    LOG_FORMAT: str = _optional("LOG_FORMAT", "text")

    # ── Terms of Service ──────────────────────────────────────
    CURRENT_TERMS_VERSION: str = "1.0"
    REQUIRED_TERMS_VERSION: str = "1.0"

    # ── Rate limits ───────────────────────────────────────────
    RATE_LIMIT_INVESTIGATIONS: tuple[int, int] = (100, 3600)   # 100/hour
    RATE_LIMIT_HISTORY: tuple[int, int] = (500, 3600)          # 500/hour
    RATE_LIMIT_DEFAULT: tuple[int, int] = (1000, 3600)         # 1000/hour

    # ── Investigation ─────────────────────────────────────────
    INVESTIGATION_TIMEOUT_SECONDS: int = 900   # 15 minutes


settings = Settings()
