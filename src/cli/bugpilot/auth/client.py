"""
Auth client - handles activation, refresh, and logout against the API.
"""
from __future__ import annotations

import hashlib
import platform
import uuid
from typing import Optional

import httpx

from bugpilot.context import AppContext
from bugpilot.session import APIError, _raise_for_status


def _generate_device_fingerprint() -> str:
    """Generate a stable device fingerprint from machine characteristics."""
    node = str(uuid.getnode())
    system = platform.system()
    machine = platform.machine()
    raw = f"{node}-{system}-{machine}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def activate(
    ctx: AppContext,
    license_key: str,
    email: str,
    api_secret: Optional[str] = None,
    display_name: Optional[str] = None,
) -> dict:
    """
    Activate license and store credentials.
    Returns the activation response dict.
    """
    device_fp = _generate_device_fingerprint()

    async with httpx.AsyncClient(base_url=ctx.api_url, timeout=30.0) as client:
        r = await client.post(
            "/api/v1/auth/activate",
            json={
                "license_key": license_key,
                "api_secret": api_secret,
                "email": email,
                "device_fingerprint": device_fp,
                "display_name": display_name,
            },
        )
        _raise_for_status(r)
        resp = r.json()

    ctx.save_credentials(
        access_token=resp["access_token"],
        refresh_token=resp["refresh_token"],
        org_id=resp["org_id"],
        user_id=resp["user_id"],
    )
    ctx._access_token = resp["access_token"]
    ctx._refresh_token = resp["refresh_token"]
    ctx._org_id = resp["org_id"]
    ctx._user_id = resp["user_id"]
    return resp


async def logout(ctx: AppContext) -> None:
    """Revoke current session and clear local credentials."""
    if not ctx.is_authenticated:
        ctx.clear_credentials()
        return

    try:
        async with ctx.make_client() as client:
            await client.post("/api/v1/auth/logout")
    except Exception:
        pass  # Best-effort logout
    finally:
        ctx.clear_credentials()


async def whoami(ctx: AppContext) -> dict:
    """Return current user information from the API."""
    async with ctx.make_client() as client:
        r = await client.get("/api/v1/auth/whoami")
        _raise_for_status(r)
        return r.json()
