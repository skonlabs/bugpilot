"""
BugPilot Data API - self-hostable CRUD layer.

This service stores investigations, evidence, hypotheses, actions, and connector
configuration in a customer-managed PostgreSQL database.  It does NOT contain
any analysis logic, LLM calls, or connector implementations — those live in the
BugPilot-hosted analysis engine (src/backend).
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging

# API Routers
from app.api.v1 import (
    auth,
    license,
    investigations,
    evidence,
    hypotheses,
    actions,
    service_mappings,
    admin,
)

settings = get_settings()
configure_logging()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("bugpilot_data_api_starting", version="0.1.0")
    yield
    logger.info("bugpilot_data_api_stopped")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="BugPilot Data API",
        description="Self-hostable CRUD layer for investigations, evidence, and connector config",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Health endpoints
    # ---------------------------------------------------------------------------
    @app.get("/health", tags=["ops"], summary="Liveness probe")
    async def health_liveness():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["ops"], summary="Readiness probe")
    async def health_readiness():
        from app.core.db import engine
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"status": "ready", "db": "ok"}
        except Exception as exc:
            logger.error("readiness_check_failed", error=str(exc))
            return JSONResponse(status_code=503, content={"status": "not_ready", "db": "error"})

    # ---------------------------------------------------------------------------
    # API v1 routers
    # ---------------------------------------------------------------------------
    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix + "/auth", tags=["auth"])
    app.include_router(license.router, prefix=api_prefix + "/license", tags=["license"])
    app.include_router(investigations.router, prefix=api_prefix + "/investigations", tags=["investigations"])
    app.include_router(evidence.router, prefix=api_prefix + "/evidence", tags=["evidence"])
    app.include_router(hypotheses.router, prefix=api_prefix + "/hypotheses", tags=["hypotheses"])
    app.include_router(actions.router, prefix=api_prefix + "/actions", tags=["actions"])
    app.include_router(service_mappings.router, prefix=api_prefix + "/service-mappings", tags=["service-mappings"])
    app.include_router(admin.router, prefix=api_prefix + "/admin", tags=["admin"])

    return app


app = create_app()
