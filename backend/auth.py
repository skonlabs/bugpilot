"""
API key validation middleware + rate limiting.

Every authenticated request must:
1. Present Authorization: Bearer bp_live_... or bp_test_...
2. Have a valid, non-revoked key in api_keys table
3. Belong to an org where terms_accepted = TRUE
4. Not exceed rate limits

Webhooks (/v1/webhooks/*) bypass Bearer auth — they use secret query params.
/health bypasses all auth.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Callable

import psycopg2
import redis as redis_lib
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)

# ── Redis client (lazy init) ───────────────────────────────────────────────────
_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        import os
        url = os.environ.get("REDIS_URL")
        if not url:
            raise RuntimeError(
                "Environment variable 'REDIS_URL' is not set. "
                "Run 'make dev-setup' to create .env, then restart with 'make dev-backend'."
            )
        _redis = redis_lib.Redis.from_url(url, decode_responses=True)
    return _redis


# ── Rate limit config ──────────────────────────────────────────────────────────
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "investigations": (100, 3600),   # 100 per hour
    "history":        (500, 3600),   # 500 per hour
    "default":        (1000, 3600),  # 1000 per hour
}


def check_rate_limit(org_id: str, endpoint_type: str) -> None:
    """Raise 429 if rate limit exceeded. Skip silently if Redis is unavailable."""
    limit, window = RATE_LIMITS.get(endpoint_type, RATE_LIMITS["default"])
    key = f"rl:{org_id}:{endpoint_type}"
    try:
        r = _get_redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, window)
        if count > limit:
            ttl = r.ttl(key)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} {endpoint_type} per {window}s",
                headers={"Retry-After": str(ttl)},
            )
    except HTTPException:
        raise
    except Exception:
        log.warning("Redis unavailable — skipping rate limit check for %s/%s", org_id, endpoint_type)


def _update_key_last_used(key_hash: str) -> None:
    """Fire-and-forget last_used_at update."""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = %s",
                    (key_hash,),
                )
            conn.commit()
        finally:
            release_conn(conn)
    except Exception as e:
        log.warning(f"Failed to update last_used_at: {e}")


class AuthMiddleware:
    """
    Pure ASGI middleware for API key validation.

    Using a raw ASGI class (not BaseHTTPMiddleware) avoids the anyio
    ExceptionGroup wrapping that occurs in Python 3.11+ with Starlette's
    BaseHTTPMiddleware, which prevented try/except from catching psycopg2
    errors before they became unhandled 500s.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Skip auth for health check and webhooks
        if path == "/health" or path.startswith("/v1/webhooks/"):
            await self.app(scope, receive, send)
            return

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            response = JSONResponse(
                status_code=401,
                content={"error": "missing_auth", "detail": "Missing Authorization header"},
            )
            await response(scope, receive, send)
            return

        raw_key = auth.removeprefix("Bearer ").strip()
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Get DB connection — return 503 immediately if DB is unreachable
        try:
            conn = get_conn()
        except Exception as e:
            log.error(f"Database unavailable during auth: {e}")
            response = JSONResponse(
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
            await response(scope, receive, send)
            return

        try:
            # Look up key
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT org_id, scope FROM api_keys "
                    "WHERE key_hash = %s AND revoked_at IS NULL",
                    (key_hash,),
                )
                row = cur.fetchone()

            if not row:
                response = JSONResponse(
                    status_code=401,
                    content={"error": "invalid_key", "detail": "Invalid or revoked API key"},
                )
                await response(scope, receive, send)
                return

            org_id, scope_val = row

            # Check terms acceptance
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT terms_accepted, terms_version FROM orgs WHERE id = %s",
                    (str(org_id),),
                )
                org_row = cur.fetchone()

            if not org_row:
                response = JSONResponse(
                    status_code=401,
                    content={"error": "org_not_found", "detail": "Organisation not found"},
                )
                await response(scope, receive, send)
                return

            terms_accepted, terms_version = org_row

            if not terms_accepted:
                response = JSONResponse(
                    status_code=451,
                    content={
                        "error": "terms_not_accepted",
                        "message": "Please run 'bugpilot init' to accept the Terms of Service.",
                        "terms_url": "https://bugpilot.io/terms",
                    },
                )
                await response(scope, receive, send)
                return

            # Check if terms version is outdated (current required: "1.0")
            from backend.config import settings
            if terms_version is not None and terms_version < settings.REQUIRED_TERMS_VERSION:
                response = JSONResponse(
                    status_code=451,
                    content={
                        "error": "terms_update_required",
                        "new_version": settings.REQUIRED_TERMS_VERSION,
                        "terms_url": "https://bugpilot.io/terms",
                        "message": "Terms of Service updated. Please re-accept.",
                    },
                )
                await response(scope, receive, send)
                return

            # Set RLS context
            set_org_context(conn, str(org_id))

            # Attach to request state
            scope["state"] = scope.get("state", {})
            request.state.org_id = str(org_id)
            request.state.scope = scope_val
            request.state.db_conn = conn

            # Update last_used_at asynchronously
            _update_key_last_used(key_hash)

            await self.app(scope, receive, send)
            conn.commit()

        except BaseException as e:
            # Catch BaseException (not just Exception) because Python 3.11+
            # anyio task groups inside inner middlewares wrap exceptions in
            # BaseExceptionGroup, which is a BaseException subclass and is
            # silently missed by `except Exception`.
            conn.rollback()

            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise

            # Unwrap single-exception BaseExceptionGroup chains
            actual: BaseException = e
            while hasattr(actual, "exceptions") and len(actual.exceptions) == 1:
                actual = actual.exceptions[0]  # type: ignore[attr-defined]

            if isinstance(actual, psycopg2.OperationalError):
                status_code = 503
                content: dict = {
                    "error": "database_unavailable",
                    "detail": (
                        "Database connection failed. "
                        "Check DATABASE_URL in .env — your Supabase project may be paused "
                        "(visit supabase.com to restore it) or use the Transaction Pooler URL."
                    ),
                }
            else:
                status_code = 500
                content = {"error": "internal_error", "detail": "An unexpected error occurred"}

            log.error(f"Auth middleware error (unwrapped: {actual!r}): {e}", exc_info=True)
            try:
                response = JSONResponse(status_code=status_code, content=content)
                await response(scope, receive, send)
            except Exception:
                pass  # headers already sent — nothing we can do
        finally:
            release_conn(conn)


# Keep the old function name so main.py import still works
async def auth_middleware(request: Request, call_next: Callable):  # type: ignore[misc]
    """Deprecated shim — AuthMiddleware class is used directly in main.py."""
    raise NotImplementedError("Use AuthMiddleware class instead")
