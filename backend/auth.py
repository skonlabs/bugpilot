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

import redis as redis_lib
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)

# ── Redis client (lazy init) ───────────────────────────────────────────────────
_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        import os
        _redis = redis_lib.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _redis


# ── Rate limit config ──────────────────────────────────────────────────────────
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "investigations": (100, 3600),   # 100 per hour
    "history":        (500, 3600),   # 500 per hour
    "default":        (1000, 3600),  # 1000 per hour
}


def check_rate_limit(org_id: str, endpoint_type: str) -> None:
    """Raise 429 if rate limit exceeded."""
    limit, window = RATE_LIMITS.get(endpoint_type, RATE_LIMITS["default"])
    key = f"rl:{org_id}:{endpoint_type}"
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


async def auth_middleware(request: Request, call_next):
    """
    Validate API key and set org context on every request.
    Skip auth for /health and /v1/webhooks/* (webhooks use secret params).
    Return HTTP 451 if terms not accepted.
    """
    path = request.url.path

    # Skip auth for health check and webhooks
    if path == "/health" or path.startswith("/v1/webhooks/"):
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "missing_auth", "detail": "Missing Authorization header"},
        )

    raw_key = auth.removeprefix("Bearer ").strip()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    conn = get_conn()
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
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_key", "detail": "Invalid or revoked API key"},
            )

        org_id, scope = row

        # Check terms acceptance
        with conn.cursor() as cur:
            cur.execute(
                "SELECT terms_accepted, terms_version FROM orgs WHERE id = %s",
                (str(org_id),),
            )
            org_row = cur.fetchone()

        if not org_row:
            return JSONResponse(
                status_code=401,
                content={"error": "org_not_found", "detail": "Organisation not found"},
            )

        terms_accepted, terms_version = org_row

        if not terms_accepted:
            return JSONResponse(
                status_code=451,
                content={
                    "error": "terms_not_accepted",
                    "message": "Please run 'bugpilot init' to accept the Terms of Service.",
                    "terms_url": "https://ekonomical.com/terms",
                },
            )

        # Check if terms version is outdated (current required: "1.0")
        from backend.config import settings
        if terms_version is not None and terms_version < settings.REQUIRED_TERMS_VERSION:
            return JSONResponse(
                status_code=451,
                content={
                    "error": "terms_update_required",
                    "new_version": settings.REQUIRED_TERMS_VERSION,
                    "terms_url": "https://ekonomical.com/terms",
                    "message": "Terms of Service updated. Please re-accept.",
                },
            )

        # Set RLS context
        set_org_context(conn, str(org_id))

        # Attach to request state
        request.state.org_id = str(org_id)
        request.state.scope = scope
        request.state.db_conn = conn

        # Update last_used_at asynchronously
        _update_key_last_used(key_hash)

        response = await call_next(request)
        conn.commit()
        return response

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        log.error(f"Auth middleware error: {e}", exc_info=True)
        raise
    finally:
        release_conn(conn)
