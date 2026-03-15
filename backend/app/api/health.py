"""
GET /health — no auth required. Used by load balancer, Supabase, and monitoring.
"""
from __future__ import annotations

import os
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """
    Health check. Returns 200 if database and Redis are reachable, 503 otherwise.
    No authentication required.
    """
    checks: dict[str, str] = {}

    # ── Database check ─────────────────────────────────────────
    try:
        from backend.app.database import get_conn, release_conn
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            release_conn(conn)
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        log.warning(f"Health check: database error: {e}")

    # ── Redis check ────────────────────────────────────────────
    try:
        import redis
        r = redis.Redis.from_url(os.environ["REDIS_URL"])
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        log.warning(f"Health check: Redis error: {e}")

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "ok" else 503
    return JSONResponse({"status": overall, "checks": checks}, status_code=status_code)
