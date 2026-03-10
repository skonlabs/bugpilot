"""
Supabase client for BugPilot backend.

The service-role client is used server-side and bypasses Row Level Security (RLS).
The anon client uses the public key and respects RLS policies.

Usage:
    from app.core.supabase import get_supabase, get_supabase_anon

    client = get_supabase()
    if client:
        # Storage: upload evidence payloads
        client.storage.from_("evidence").upload(path, data)

        # Realtime: broadcast investigation updates (via REST)
        client.table("investigations").select("*").execute()

Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env to enable.
"""

from functools import lru_cache
from typing import Optional

from .config import get_settings


def _make_client(url: str, key: str):
    """Create a Supabase client; returns None if supabase package unavailable."""
    try:
        from supabase import create_client, Client  # type: ignore
        return create_client(url, key)
    except ImportError:
        return None


@lru_cache(maxsize=1)
def get_supabase():
    """
    Return a service-role Supabase client (bypasses RLS).
    Returns None when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured.
    """
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        return None
    return _make_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


@lru_cache(maxsize=1)
def get_supabase_anon():
    """
    Return an anon Supabase client (respects RLS).
    Returns None when SUPABASE_URL / SUPABASE_ANON_KEY are not configured.
    """
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None
    return _make_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
