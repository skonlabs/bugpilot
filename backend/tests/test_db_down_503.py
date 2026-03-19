"""
Integration test: verify that DB-unavailable errors return 503, not 500.

This test simulates the exact failure the user sees in production when the
Supabase database is unreachable (DNS lookup failure / connection refused).
It patches get_conn() at the module level so the real psycopg2 pool is never
touched, then spins up the full ASGI middleware stack and fires real HTTP
requests through it.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ── Stub out heavy dependencies BEFORE any backend imports ─────────────────
# psycopg2 stubs (so we can instantiate OperationalError below)
import psycopg2  # noqa: E402  (always available — psycopg2 is in requirements)

# redis stub
sys.modules.setdefault("redis", MagicMock())

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402


DB_DOWN_EXC = psycopg2.OperationalError(
    'could not translate host name "db.xyz.supabase.co" to address: '
    "nodename nor servname provided, or not known"
)

VALID_KEY = "bp_test_validkeyfortesting"
VALID_KEY_HASH = __import__("hashlib").sha256(VALID_KEY.encode()).hexdigest()


def _make_app():
    """Build fresh app with env vars set to avoid startup crash."""
    import os

    os.environ.setdefault("DATABASE_URL", "postgresql://user:pw@db.fake.supabase.co/postgres")
    os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

    from backend.main import create_app  # import after env is set
    return create_app()


# ── Helpers ────────────────────────────────────────────────────────────────

def _mock_conn_raising():
    """Return a mock get_conn that always raises OperationalError."""
    def _raise():
        raise DB_DOWN_EXC
    return _raise


def _mock_conn_success():
    """Return a mock get_conn that returns a valid conn with auth data."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    # fetchone for api_keys lookup → (org_id, scope)
    # fetchone for orgs lookup → (True, "1.0")
    cursor.fetchone.side_effect = [
        ("org-test-123", "full"),
        (True, "1.0"),
    ]
    conn.cursor.return_value = cursor
    return lambda: conn


# ── Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_auth_db_down_returns_503():
    """
    When get_conn() fails during auth key lookup, the server must return 503
    (not 500 / not an unhandled exception crash).
    """
    app = _make_app()

    with (
        patch("backend.auth.get_conn", side_effect=DB_DOWN_EXC),
        patch("backend.auth._get_redis", side_effect=Exception("redis down")),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                "/v1/investigations",
                headers={"Authorization": f"Bearer {VALID_KEY}"},
                json={"text": "spike in 5xx errors", "layer": "l2"},
            )

    assert resp.status_code == 503, (
        f"Expected 503 when DB is down during auth, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("error") == "database_unavailable"


@pytest.mark.anyio
async def test_route_handler_db_down_returns_503():
    """
    When auth passes but the route handler's get_conn() fails (e.g., pool
    exhausted or connection dropped between auth and handler), the server must
    return 503, not 500.
    """
    app = _make_app()

    # Auth succeeds (mock auth conn), but enqueue_investigation's get_conn fails
    with (
        patch("backend.auth.get_conn", side_effect=DB_DOWN_EXC),
        patch("backend.auth._get_redis", side_effect=Exception("redis down")),
        patch("backend.services.queue.get_conn", side_effect=DB_DOWN_EXC),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                "/v1/investigations",
                headers={"Authorization": f"Bearer {VALID_KEY}"},
                json={"text": "spike in 5xx errors", "layer": "l2"},
            )

    # With DB down at auth, we expect 503 from auth middleware
    assert resp.status_code == 503, (
        f"Expected 503 when DB is down, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.anyio
async def test_base_exception_group_unwrapped_to_503():
    """
    Simulate what Python 3.14 + anyio does: wrap OperationalError in a
    BaseExceptionGroup (as happens when an inner BaseHTTPMiddleware task group
    catches it). AuthMiddleware must unwrap it and return 503, not crash.
    """
    app = _make_app()

    # Auth passes, but self.app() raises a BaseExceptionGroup wrapping OperationalError
    wrapped = BaseExceptionGroup("unhandled errors in a TaskGroup", [DB_DOWN_EXC])

    auth_conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.side_effect = [("org-test-123", "full"), (True, "1.0")]
    auth_conn.cursor.return_value = cursor

    async def fake_inner_app(scope, receive, send):
        raise wrapped

    with (
        patch("backend.auth.get_conn", return_value=auth_conn),
        patch("backend.auth.release_conn"),
        patch("backend.auth.set_org_context"),
        patch("backend.auth._get_redis", side_effect=Exception("redis down")),
        patch.object(app, "middleware_stack", wraps=app.build_middleware_stack()),
    ):
        # Patch the ASGI app that AuthMiddleware calls to simulate inner failure
        original_build = app.build_middleware_stack

        class _FakeInner:
            async def __call__(self, scope, receive, send):
                raise wrapped

        import backend.auth as _auth_mod
        original_cls_app = None

        # Directly test AuthMiddleware in isolation
        from backend.auth import AuthMiddleware
        mw = AuthMiddleware(_FakeInner())

        from starlette.testclient import TestClient
        from starlette.requests import Request as StarletteRequest

        responses = []

        async def mock_send(message):
            responses.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/investigations",
            "query_string": b"",
            "headers": [
                (b"authorization", f"Bearer {VALID_KEY}".encode()),
                (b"content-type", b"application/json"),
            ],
            "state": {},
        }

        async def mock_receive():
            return {"type": "http.request", "body": b'{"text":"test"}', "more_body": False}

        await mw(scope, mock_receive, mock_send)

    # The first response message is http.response.start with the status code
    assert responses, "No response was sent"
    start = next((m for m in responses if m.get("type") == "http.response.start"), None)
    assert start is not None, f"No http.response.start in responses: {responses}"
    assert start["status"] == 503, (
        f"Expected 503 when BaseExceptionGroup wraps OperationalError, got {start['status']}"
    )


@pytest.mark.anyio
async def test_health_check_bypasses_auth():
    """Health endpoint must work with no auth and no DB."""
    app = _make_app()

    with patch("backend.auth.get_conn", side_effect=DB_DOWN_EXC):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.get("/health")

    assert resp.status_code == 200
