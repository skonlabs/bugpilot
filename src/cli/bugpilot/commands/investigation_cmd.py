"""
Investigation export command - export investigation data (JSON or Markdown).
Implements: bugpilot investigation export --format [json|markdown]
"""
from __future__ import annotations

import json as json_mod
from pathlib import Path
from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import debug_exc, print_error, print_success
from bugpilot.session import APIError
from bugpilot.commands.export_helpers import collect_investigation_bundle, render_markdown

app = typer.Typer(help="Investigation export and management")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.command("export")
def cmd_export(
    ctx: typer.Context,
    investigation_id: Optional[str] = typer.Option(
        None, "--investigation", "-i", help="Investigation ID (uses stored context if omitted)"
    ),
    fmt: str = typer.Option("json", "--format", "-f", help="Export format: json|markdown"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
) -> None:
    """Export a full investigation report as JSON or Markdown."""
    app_ctx = _get_ctx(ctx)

    inv_id = app_ctx.resolve_investigation_id(investigation_id)
    if not inv_id:
        print_error(
            "No investigation context set. Use --investigation <id> or run: bugpilot incident open <id>"
        )
        raise typer.Exit(1)

    if fmt not in ("json", "markdown"):
        print_error("--format must be json or markdown")
        raise typer.Exit(1)

    async def _run():
        try:
            bundle = await collect_investigation_bundle(app_ctx, inv_id)
            if fmt == "json":
                content = json_mod.dumps(bundle, indent=2, default=str)
            else:
                content = render_markdown(bundle)

            if output:
                output.write_text(content)
                print_success(f"Exported to {output}")
            else:
                print(content)
        except APIError as e:
            print_error(f"Export failed: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)
