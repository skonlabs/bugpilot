"""
Export commands - export investigation data in various formats.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import print_error, print_success
from bugpilot.session import APIError
from bugpilot.commands.export_helpers import collect_investigation_bundle, render_markdown

app = typer.Typer(help="Export investigation data")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.command("json")
def cmd_json(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="Investigation ID to export"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
) -> None:
    """Export investigation as JSON bundle."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            bundle = await collect_investigation_bundle(app_ctx, investigation_id)
            serialized = json.dumps(bundle, indent=2, default=str)
            if output:
                output.write_text(serialized)
                print_success(f"Exported to {output}")
            else:
                print(serialized)
        except APIError as e:
            print_error(f"Export failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("markdown")
def cmd_markdown(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="Investigation ID to export"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
) -> None:
    """Export investigation as Markdown incident report."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            bundle = await collect_investigation_bundle(app_ctx, investigation_id)
            md = render_markdown(bundle)
            if output:
                output.write_text(md)
                print_success(f"Markdown report saved to {output}")
            else:
                print(md)
        except APIError as e:
            print_error(f"Export failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
