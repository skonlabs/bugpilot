"""
Compare command - show baseline comparison (last-healthy, last-stable-post-deploy, user-pinned).
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer
from rich.table import Table
from rich import box

from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get_analysis

app = typer.Typer(help="Compare current investigation state against a healthy baseline")

STRATEGIES = ["last_healthy", "last_stable_post_deploy", "user_pinned"]


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.callback(invoke_without_command=True)
def cmd_compare(
    ctx: typer.Context,
    last_healthy: bool = typer.Option(False, "--last-healthy", help="Compare against the last healthy window"),
    last_stable: bool = typer.Option(False, "--last-stable-post-deploy", help="Compare against last stable post-deploy window"),
    user_pinned: bool = typer.Option(False, "--user-pinned", help="Compare against user-pinned baseline"),
    investigation_id: Optional[str] = typer.Option(
        None, "--investigation", "-i", help="Investigation ID (uses stored context if omitted)"
    ),
) -> None:
    """Compare current metrics/state against a healthy baseline to spot regressions."""
    app_ctx = _get_ctx(ctx)

    inv_id = app_ctx.resolve_investigation_id(investigation_id)
    if not inv_id:
        print_error(
            "No investigation context set. Use --investigation <id> or run: bugpilot incident open <id>"
        )
        raise typer.Exit(1)

    if last_stable:
        strategy = "last_stable_post_deploy"
    elif user_pinned:
        strategy = "user_pinned"
    else:
        strategy = "last_healthy"  # default

    async def _run():
        try:
            data = await api_get_analysis(
                app_ctx,
                f"/api/v1/investigations/{inv_id}/baseline-comparison",
                params={"strategy": strategy},
            )
            if app_ctx.output_format == "json":
                print_json(data)
                return

            baseline_desc = data.get("baseline_description", strategy)
            console.print(f"[bold]Baseline:[/bold] {baseline_desc}\n")

            deltas = data.get("metric_deltas", [])
            if deltas:
                table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
                table.add_column("Metric")
                table.add_column("Baseline", justify="right")
                table.add_column("Current", justify="right")
                table.add_column("Delta", justify="right")
                for d in deltas:
                    delta_str = d.get("delta", "-")
                    delta_color = "red" if str(delta_str).startswith("+") else "green"
                    table.add_row(
                        d.get("metric", "-"),
                        str(d.get("baseline_value", "-")),
                        str(d.get("current_value", "-")),
                        f"[{delta_color}]{delta_str}[/{delta_color}]",
                    )
                console.print(table)

            degraded = data.get("degraded_services", [])
            if degraded:
                console.print(f"\n[red]Degraded services:[/red] {', '.join(degraded)}")
        except APIError as e:
            print_error(f"Comparison failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
