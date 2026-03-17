"""
Database connections:
  - supabase: Supabase client (auth, storage, realtime)
  - psycopg2 pool: direct PostgreSQL for Apache AGE Cypher queries and raw SQL
"""
from __future__ import annotations

import os
import logging

import psycopg2.pool
from supabase import create_client, Client

log = logging.getLogger(__name__)

# ── Supabase client (auth, storage, realtime — not for raw investigation SQL) ──
_supabase: Client | None = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
    return _supabase


# Keep module-level `supabase` name working via a proxy property isn't possible
# for a plain variable, so callers should use get_supabase() directly.
def get_supabase() -> Client:
    return _get_supabase()


# ── Direct psycopg2 pool (AGE Cypher queries + raw investigation SQL) ──────────
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=int(os.environ.get("DATABASE_MIN_POOL", "2")),
            maxconn=int(os.environ.get("DATABASE_POOL_SIZE", "20")),
            dsn=os.environ["DATABASE_URL"],
            sslmode="require",
            connect_timeout=10,
            options="-c search_path=ag_catalog,public",  # Required for AGE
        )
    return _pool


def get_conn():
    """Get a connection from the pool. Call release_conn() when done."""
    conn = _get_pool().getconn()
    conn.autocommit = False
    return conn


def release_conn(conn) -> None:
    """Return connection to the pool."""
    _get_pool().putconn(conn)


def set_org_context(conn, org_id: str) -> None:
    """Set the RLS context for the current request. Call after get_conn()."""
    with conn.cursor() as cur:
        cur.execute("SET LOCAL app.current_org_id = %s", (org_id,))
