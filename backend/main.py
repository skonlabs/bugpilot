"""
BugPilot API — FastAPI application entry point.

Mounts:
  /health          — no auth
  /v1/keys         — keys router
  /v1/investigations
  /v1/connectors
  /v1/webhooks
  /v1/triggers
  /v1/history
  /v1/reports
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

# ── Load .env before anything else touches os.environ ────────────────────────
# Try several candidate locations so the file is found whether uvicorn's
# reload subprocess inherits the original CWD or resolves paths differently.
from dotenv import load_dotenv  # noqa: E402

def _load_env() -> None:
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",  # <project>/.env
        Path.cwd() / ".env",                              # wherever uvicorn was launched from
    ]
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            load_dotenv(resolved, override=True)
            return
    # File not found — dotenv will silently no-op; startup check below will catch it.

_load_env()
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.auth import auth_middleware  # noqa: E402
from backend.api import health, keys, investigations, connectors, webhooks, triggers, history, reports  # noqa: E402

# ── Logging ───────────────────────────────────────────────────────────────────
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
log_format = os.environ.get("LOG_FORMAT", "text")

if log_format == "json":
    import structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
    )
else:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )

log = logging.getLogger(__name__)

# ── Required environment variables ───────────────────────────────────────────
_REQUIRED = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "REDIS_URL"]


def _check_env() -> None:
    missing = [v for v in _REQUIRED if not os.environ.get(v)]
    if missing:
        msg = (
            f"Missing required environment variables: {', '.join(missing)}\n"
            "  1. Make sure .env exists in the project root (run 'make dev-setup')\n"
            "  2. Start the server with 'make dev-backend' (not bare uvicorn)\n"
            f"  3. Checked paths: {list(dict.fromkeys([str(Path(__file__).resolve().parent.parent / '.env'), str(Path.cwd() / '.env')]))}"
        )
        raise RuntimeError(msg)


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="BugPilot API",
        version="1.0.0",
        description="Functional bug investigation API",
        docs_url="/docs" if os.environ.get("BUGPILOT_ENV") != "production" else None,
        redoc_url=None,
    )

    # CORS — restrict in production
    origins = ["*"] if os.environ.get("BUGPILOT_ENV") != "production" else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth middleware (runs on every request except /health and /v1/webhooks/*)
    app.middleware("http")(auth_middleware)

    # Routers
    app.include_router(health.router)               # /health
    app.include_router(keys.router, prefix="/v1")   # /v1/keys/validate
    app.include_router(investigations.router, prefix="/v1")
    app.include_router(connectors.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")
    app.include_router(triggers.router, prefix="/v1")
    app.include_router(history.router, prefix="/v1")
    app.include_router(reports.router, prefix="/v1")

    @app.on_event("startup")
    async def startup():
        _check_env()
        log.info("BugPilot API starting up")

    @app.on_event("shutdown")
    async def shutdown():
        log.info("BugPilot API shutting down")
        from backend.database import _pool
        if _pool:
            _pool.closeall()

    return app


app = create_app()
