"""
History command - list past (resolved/closed) investigations.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get

app = typer.Typer(help="List past investigations")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.callback(invoke_without_command=True)
def cmd_history(
    ctx: typer.Context,
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", help="Results per page"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity"),
    service: Optional[str] = typer.Option(None, "--service", help="Filter by affected service"),
) -> None:
    """List past resolved and closed investigations."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        params: dict = {"page": page, "page_size": page_size, "status": ["resolved", "closed"]}
        if severity:
            params["severity"] = severity
        try:
            data = await api_get(app_ctx, "/api/v1/investigations", params=params)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                from bugpilot.output.human import print_investigation_list
                items = data.get("items", [])
                total = data.get("total", 0)
                if not items:
                    console.print("[dim]No past investigations found.[/dim]")
                    return
                print_investigation_list(items, total)
                console.print(f"[dim]Page {page} — showing {len(items)} of {total}[/dim]")
        except APIError as e:
            print_error(f"Failed to fetch history: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
