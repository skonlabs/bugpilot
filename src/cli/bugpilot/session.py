"""
Session management - token refresh and API call helpers.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx
import typer

from .context import AppContext


class APIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


class BackendUnavailableError(Exception):
    """Raised when the backend cannot be reached."""


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise APIError(status_code=response.status_code, detail=str(detail))


def _handle_connect_error(exc: Exception) -> None:
    """Print backend unavailable message and exit with code 2."""
    from bugpilot.output.human import error_console
    error_console.print("[bold red][BugPilot] Backend unavailable.[/bold red] "
                        "Check your network connection and API URL.")
    raise typer.Exit(2)


async def api_get(ctx: AppContext, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    try:
        async with ctx.make_client() as client:
            r = await client.get(path, params=params)
            _raise_for_status(r)
            return r.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        _handle_connect_error(exc)


async def api_post(ctx: AppContext, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    try:
        async with ctx.make_client() as client:
            r = await client.post(path, json=body)
            _raise_for_status(r)
            return r.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        _handle_connect_error(exc)


async def api_patch(ctx: AppContext, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    try:
        async with ctx.make_client() as client:
            r = await client.patch(path, json=body)
            _raise_for_status(r)
            return r.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        _handle_connect_error(exc)


async def api_delete(ctx: AppContext, path: str) -> None:
    try:
        async with ctx.make_client() as client:
            r = await client.delete(path)
            _raise_for_status(r)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        _handle_connect_error(exc)


async def refresh_token_if_needed(ctx: AppContext) -> bool:
    """
    Attempt to refresh the access token using the stored refresh token.
    Returns True on success, False on failure.
    """
    from .context import CREDENTIALS_FILE
    if not CREDENTIALS_FILE.exists():
        return False
    try:
        data = json.loads(CREDENTIALS_FILE.read_text())
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            return False

        async with httpx.AsyncClient(base_url=ctx.api_url, timeout=15.0) as client:
            r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
            if r.is_error:
                return False
            resp = r.json()
            ctx.save_credentials(
                access_token=resp["access_token"],
                refresh_token=resp["refresh_token"],
                org_id=data.get("org_id", ""),
                user_id=data.get("user_id", ""),
            )
            ctx._access_token = resp["access_token"]
            ctx._refresh_token = resp["refresh_token"]
            return True
    except Exception:
        return False
