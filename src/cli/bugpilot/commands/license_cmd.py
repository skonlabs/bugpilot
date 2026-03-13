"""
License commands - show license tier, device count, and expiry.
"""
from __future__ import annotations

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, debug_exc, print_error
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get

app = typer.Typer(help="License management commands")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.command("status")
def cmd_status(ctx: typer.Context) -> None:
    """Show license tier, device count, expiry, and entitlements."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_get(app_ctx, "/api/v1/license/status")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                status = data.get("status", "-")
                color = "green" if status == "active" else "red"
                console.print(f"[bold]License status:[/bold] [{color}]{status.upper()}[/{color}]")
                console.print(f"[bold]Tier:[/bold] {data.get('tier', '-')}")
                console.print(f"[bold]Org:[/bold] {data.get('org_id', '-')}")
                console.print(f"[bold]Devices:[/bold] {data.get('device_count', '-')} / {data.get('max_devices', '-')}")
                console.print(f"[bold]Expires:[/bold] {data.get('expires_at') or 'Never'}")
                entitlements = data.get("entitlements")
                if entitlements:
                    console.print(f"[bold]Entitlements:[/bold] {', '.join(entitlements)}")
        except APIError as e:
            print_error(f"Failed to get license status: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)
