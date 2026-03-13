"""
Timeline command - chronological evidence with clock skew warnings.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer
from rich.table import Table
from rich import box

from bugpilot.context import AppContext
from bugpilot.output.human import console, debug_exc, print_error
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get

app = typer.Typer(help="Show chronological evidence timeline with clock skew warnings")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.callback(invoke_without_command=True)
def cmd_timeline(
    ctx: typer.Context,
    investigation_id: Optional[str] = typer.Option(
        None, "--investigation", "-i", help="Investigation ID (uses stored context if omitted)"
    ),
) -> None:
    """Show a chronological timeline of evidence events, with clock skew warnings."""
    app_ctx = _get_ctx(ctx)

    inv_id = app_ctx.resolve_investigation_id(investigation_id)
    if not inv_id:
        print_error(
            "No investigation context set. Use --investigation <id> or run: bugpilot incident open <id>"
        )
        raise typer.Exit(1)

    async def _run():
        try:
            data = await api_get(app_ctx, "/api/v1/graph/timeline", params={"investigation_id": inv_id})
            if app_ctx.output_format == "json":
                print_json(data)
                return

            events = data.get("events", [])
            if not events:
                console.print("[dim]No timeline events recorded.[/dim]")
                return

            table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
            table.add_column("Time (UTC)", min_width=19)
            table.add_column("Type")
            table.add_column("Source", style="dim")
            table.add_column("Description", max_width=60)
            table.add_column("⚠", justify="center", style="yellow")

            for event in events:
                skew_flag = "⚠" if event.get("clock_skew_warning") else ""
                table.add_row(
                    (event.get("occurred_at") or "-")[:19].replace("T", " "),
                    event.get("event_type", "-"),
                    event.get("source", "-"),
                    event.get("description", "-"),
                    skew_flag,
                )

            console.print(table)

            skew_count = sum(1 for e in events if e.get("clock_skew_warning"))
            if skew_count:
                console.print(
                    f"\n[yellow]⚠ {skew_count} clock skew warning(s) detected.[/yellow] "
                    "Events from different sources may be out of sync by more than 60 seconds."
                )
        except APIError as e:
            print_error(f"Failed to get timeline: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)
