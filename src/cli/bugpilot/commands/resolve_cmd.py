"""
Resolve command - mark the current investigation as resolved.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, debug_exc, print_error, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_patch

app = typer.Typer(help="Mark the current investigation as resolved")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.callback(invoke_without_command=True)
def cmd_resolve(
    ctx: typer.Context,
    investigation_id: Optional[str] = typer.Option(
        None, "--investigation", "-i", help="Investigation ID (uses stored context if omitted)"
    ),
    outcome: Optional[str] = typer.Option(None, "--outcome", "-o", help="Brief description of the resolution"),
) -> None:
    """Mark an investigation as resolved and clear the current context."""
    app_ctx = _get_ctx(ctx)

    inv_id = app_ctx.resolve_investigation_id(investigation_id)
    if not inv_id:
        print_error(
            "No investigation context set. Use --investigation <id> or run: bugpilot incident open <id>"
        )
        raise typer.Exit(1)

    async def _run():
        body: dict = {"status": "resolved"}
        if outcome:
            body["outcome"] = outcome

        try:
            data = await api_patch(app_ctx, f"/api/v1/investigations/{inv_id}", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Investigation {inv_id} marked as resolved.")
                if outcome:
                    console.print(f"[dim]Outcome:[/dim] {outcome}")
            # Clear stored context if it matches the resolved investigation
            stored = app_ctx.load_investigation_context()
            if stored == inv_id:
                app_ctx.clear_investigation_context()
                console.print("[dim]Investigation context cleared.[/dim]")
        except APIError as e:
            print_error(f"Resolve failed: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)
