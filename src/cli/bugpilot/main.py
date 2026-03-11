"""
BugPilot CLI - main entry point.
Registers all sub-command groups and sets up shared context.
"""
from __future__ import annotations

import os
from typing import Optional

import typer
from rich.console import Console

from bugpilot.context import AppContext
from bugpilot.commands import (
    ask_cmd,
    auth_cmd,
    compare_cmd,
    config_cmd,
    connector_cmd,
    evidence_cmd,
    export_cmd,
    fix_cmd,
    history_cmd,
    hypotheses_cmd,
    incident_cmd,
    investigate_cmd,
    investigation_cmd,
    license_cmd,
    resolve_cmd,
    summary_cmd,
    timeline_cmd,
)

console = Console()

app = typer.Typer(
    name="bugpilot",
    help="BugPilot - CLI-first debugging and investigation platform",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# ---------------------------------------------------------------------------
# Register command groups
# ---------------------------------------------------------------------------
app.add_typer(auth_cmd.app, name="auth")
app.add_typer(license_cmd.app, name="license")
app.add_typer(connector_cmd.app, name="connector")
app.add_typer(config_cmd.app, name="config")
app.add_typer(investigate_cmd.app, name="investigate")
app.add_typer(investigation_cmd.app, name="investigation")
app.add_typer(incident_cmd.app, name="incident")
app.add_typer(evidence_cmd.app, name="evidence")
app.add_typer(hypotheses_cmd.app, name="hypotheses")
app.add_typer(fix_cmd.app, name="fix")
app.add_typer(export_cmd.app, name="export")

# Top-level single-action commands (no subcommand name needed)
app.add_typer(summary_cmd.app, name="summary")
app.add_typer(timeline_cmd.app, name="timeline")
app.add_typer(ask_cmd.app, name="ask")
app.add_typer(compare_cmd.app, name="compare")
app.add_typer(resolve_cmd.app, name="resolve")
app.add_typer(history_cmd.app, name="history")


# ---------------------------------------------------------------------------
# Global options callback
# ---------------------------------------------------------------------------
@app.callback()
def main(
    ctx: typer.Context,
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="BUGPILOT_API_URL",
        help="BugPilot data API URL (self-hostable)",
    ),
    analysis_url: Optional[str] = typer.Option(
        None,
        "--analysis-url",
        envvar="BUGPILOT_ANALYSIS_URL",
        help="BugPilot analysis engine URL (default: https://api.bugpilot.io)",
        hidden=True,
    ),
    output_format: str = typer.Option(
        "human",
        "--output",
        "-o",
        envvar="BUGPILOT_OUTPUT",
        help="Output format: human|json|verbose",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        envvar="NO_COLOR",
        help="Disable coloured output",
    ),
    investigation: Optional[str] = typer.Option(
        None,
        "--investigation",
        envvar="BUGPILOT_INVESTIGATION",
        help="Override current investigation context",
        is_eager=False,
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """BugPilot: symptom → evidence → timeline → hypotheses → safest next action."""
    if version:
        from bugpilot import __version__
        console.print(f"bugpilot {__version__}")
        raise typer.Exit()

    app_ctx = AppContext(
        output_format=output_format,
        no_color=no_color,
    )
    if api_url:
        app_ctx.api_url = api_url
    if analysis_url:
        app_ctx.analysis_api_url = analysis_url
    if investigation:
        app_ctx.current_investigation_id = investigation

    ctx.ensure_object(dict)
    ctx.obj = app_ctx


def main_entry() -> None:
    app()


if __name__ == "__main__":
    main_entry()
