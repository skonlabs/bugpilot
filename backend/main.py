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

import psycopg2  # noqa: E402

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from backend.auth import AuthMiddleware  # noqa: E402
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


# ── Startup connectivity probes (non-fatal — warn but don't block) ────────────

def _warn_if_db_unreachable() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    try:
        import psycopg2
        conn = psycopg2.connect(
            dsn=db_url,
            sslmode="require",
            connect_timeout=5,
        )
        conn.close()
        log.info("Database connection OK")
    except Exception as e:
        msg = str(e)
        log.warning(f"Database unreachable at startup: {msg}")
        if "db." in db_url and ".supabase.co" in db_url:
            log.warning(
                "Your DATABASE_URL uses the direct connection format (db.xxx.supabase.co). "
                "If your Supabase project is on the free tier it may be paused — "
                "visit https://supabase.com to restore it. "
                "Alternatively, use the Transaction Pooler URL "
                "(postgres://postgres.[ref]:[pw]@aws-0-[region].pooler.supabase.com:6543/postgres) "
                "from the 'Connect' button in your project dashboard."
            )
        log.warning("All database-dependent endpoints will return 503 until the DB is reachable.")


def _warn_if_redis_unreachable() -> None:
    redis_url = os.environ.get("REDIS_URL", "")
    try:
        import redis as redis_lib
        r = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=3)
        r.ping()
        r.close()
        log.info("Redis connection OK")
    except Exception as e:
        log.warning(
            f"Redis unreachable at startup: {e}. "
            "Rate limiting and caching will be unavailable. "
            "Start Redis with: redis-server"
        )


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
    # Using a pure ASGI class (not BaseHTTPMiddleware) to avoid Python 3.11+
    # anyio ExceptionGroup wrapping which prevented try/except from catching
    # psycopg2 errors in the dispatch function.
    app.add_middleware(AuthMiddleware)

    # Global handler: DB errors from route handlers return 503 before the
    # exception can escape ExceptionMiddleware and become a BaseExceptionGroup
    # (which `except Exception` in AuthMiddleware cannot catch on Python 3.14).
    @app.exception_handler(psycopg2.OperationalError)
    async def _db_error_handler(request: Request, exc: psycopg2.OperationalError) -> JSONResponse:
        log.error(f"Database unavailable (route handler): {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "database_unavailable",
                "detail": (
                    "Database connection failed. "
                    "Check DATABASE_URL in .env — your Supabase project may be paused "
                    "(visit supabase.com to restore it) or use the Transaction Pooler URL."
                ),
            },
        )

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
        _warn_if_db_unreachable()
        _warn_if_redis_unreachable()

    @app.on_event("shutdown")
    async def shutdown():
        log.info("BugPilot API shutting down")
        from backend.database import _pool
        if _pool:
            _pool.closeall()

    return app


app = create_app()
