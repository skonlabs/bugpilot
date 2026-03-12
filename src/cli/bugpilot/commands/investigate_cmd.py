"""
Investigate commands - create, list, get, and manage investigations.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import (
    print_error,
    print_investigation,
    print_investigation_list,
    print_success,
)
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_delete, api_get, api_patch, api_post

app = typer.Typer(help="Investigation management commands")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.command("list")
def cmd_list(
    ctx: typer.Context,
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity"),
    page: int = typer.Option(1, "--page", "-p"),
    page_size: int = typer.Option(20, "--page-size"),
) -> None:
    """List investigations."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity
        try:
            data = await api_get(app_ctx, "/api/v1/investigations", params=params)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_investigation_list(data["items"], data["total"])
        except APIError as e:
            print_error(f"Failed to list investigations: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("create")
def cmd_create(
    ctx: typer.Context,
    title: str = typer.Argument(..., help="Investigation title"),
    symptom: Optional[str] = typer.Option(None, "--symptom", help="Observed symptom"),
    severity: str = typer.Option("medium", "--severity", help="Severity: low|medium|high|critical"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
) -> None:
    """Create a new investigation."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {
            "title": title,
            "severity": severity,
        }
        if symptom:
            body["symptom"] = symptom
        if description:
            body["description"] = description
        try:
            data = await api_post(app_ctx, "/api/v1/investigations", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Investigation created: {data['id']}")
                print_investigation(data)
        except APIError as e:
            print_error(f"Failed to create investigation: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("get")
def cmd_get(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="Investigation ID"),
) -> None:
    """Get investigation details."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_get(app_ctx, f"/api/v1/investigations/{investigation_id}")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_investigation(data)
        except APIError as e:
            print_error(f"Investigation not found: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("update")
def cmd_update(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(...),
    title: Optional[str] = typer.Option(None),
    status: Optional[str] = typer.Option(None),
    severity: Optional[str] = typer.Option(None),
    description: Optional[str] = typer.Option(None),
) -> None:
    """Update an investigation."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {}
        if title:
            body["title"] = title
        if status:
            body["status"] = status
        if severity:
            body["severity"] = severity
        if description:
            body["description"] = description
        if not body:
            print_error("No fields to update provided.")
            raise typer.Exit(1)
        try:
            data = await api_patch(app_ctx, f"/api/v1/investigations/{investigation_id}", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success("Investigation updated.")
                print_investigation(data)
        except APIError as e:
            print_error(f"Update failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("close")
def cmd_close(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(...),
) -> None:
    """Close an investigation."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/investigations/{investigation_id}/close")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Investigation {investigation_id} closed.")
        except APIError as e:
            print_error(f"Close failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("delete")
def cmd_delete(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(...),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete an investigation (admin only)."""
    app_ctx = _get_ctx(ctx)

    if not confirm:
        typer.confirm(f"Delete investigation {investigation_id}? This cannot be undone.", abort=True)

    async def _run():
        try:
            await api_delete(app_ctx, f"/api/v1/investigations/{investigation_id}")
            print_success(f"Investigation {investigation_id} deleted.")
        except APIError as e:
            print_error(f"Delete failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
