"""
BugPilot Backend - FastAPI Application Entry Point
"""
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

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
    graph,
    service_mappings,
    admin,
    webhooks,
)

settings = get_settings()
configure_logging()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP request count",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

# BugPilot domain metrics
bugpilot_activations_total = Counter(
    "bugpilot_activations_total",
    "Total number of license activations",
    ["tier", "status"],
)

bugpilot_active_investigations = Gauge(
    "bugpilot_active_investigations",
    "Number of currently open/in-progress investigations",
    ["org_id"],
)

bugpilot_investigation_duration_seconds = Histogram(
    "bugpilot_investigation_duration_seconds",
    "Time from investigation open to resolved/closed in seconds",
    buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400],
)

bugpilot_time_to_first_hypothesis_seconds = Histogram(
    "bugpilot_time_to_first_hypothesis_seconds",
    "Time from investigation creation to first hypothesis generation in seconds",
    buckets=[5, 15, 30, 60, 120, 300, 600],
)

bugpilot_connector_errors_total = Counter(
    "bugpilot_connector_errors_total",
    "Total connector errors by connector type and error kind",
    ["connector", "error_type"],
)

bugpilot_connector_rate_limits_total = Counter(
    "bugpilot_connector_rate_limits_total",
    "Total number of connector rate limit (429) responses",
    ["connector"],
)

bugpilot_webhook_verification_failures_total = Counter(
    "bugpilot_webhook_verification_failures_total",
    "Total number of webhook signature verification failures",
    ["source"],
)

bugpilot_llm_requests_total = Counter(
    "bugpilot_llm_requests_total",
    "Total number of LLM completion requests",
    ["provider", "model", "status"],
)

bugpilot_llm_tokens_total = Counter(
    "bugpilot_llm_tokens_total",
    "Total number of LLM tokens consumed",
    ["provider", "model", "token_type"],
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("bugpilot_backend_starting", version="0.1.0")
    yield
    logger.info("bugpilot_backend_stopped")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="BugPilot API",
        description="CLI-first debugging and investigation platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Request instrumentation middleware
    # ---------------------------------------------------------------------------
    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        latency = time.perf_counter() - start

        # Normalise path (replace UUIDs / numeric IDs with {id})
        import re
        path = request.url.path
        path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{id}", path)
        path = re.sub(r"/\d+", "/{id}", path)

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=path,
            status_code=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=path).observe(latency)
        return response

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
    # Metrics endpoint
    # ---------------------------------------------------------------------------
    @app.get("/metrics", tags=["ops"], summary="Prometheus metrics")
    async def metrics():
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

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
    app.include_router(graph.router, prefix=api_prefix + "/graph", tags=["graph"])
    app.include_router(service_mappings.router, prefix=api_prefix + "/service-mappings", tags=["service-mappings"])
    app.include_router(admin.router, prefix=api_prefix + "/admin", tags=["admin"])

    # Webhook intake router (has its own /v1/webhooks prefix defined in the router)
    app.include_router(webhooks.router, tags=["webhooks"])

    return app


app = create_app()
