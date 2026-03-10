"""
Incident commands - quick triage workflow combining create + evidence collection.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error, print_investigation, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get, api_post

app = typer.Typer(help="Incident triage commands")


@app.command("list")
def cmd_list(
    ctx: typer.Context,
    status: Optional[str] = typer.Option("open", "--status", "-s", help="Filter by status (default: open)"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity"),
    page: int = typer.Option(1, "--page", "-p"),
    page_size: int = typer.Option(20, "--page-size"),
) -> None:
    """List open investigations (active incidents)."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        params: dict = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity
        try:
            data = await api_get(app_ctx, "/api/v1/investigations", params=params)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                from bugpilot.output.human import print_investigation_list
                print_investigation_list(data["items"], data["total"])
        except APIError as e:
            print_error(f"Failed to list incidents: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("open")
def cmd_open(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="Investigation ID to set as current context"),
) -> None:
    """Set an investigation as the current context for subsequent commands."""
    app_ctx = _get_ctx(ctx)
    app_ctx.save_investigation_context(investigation_id)
    if app_ctx.output_format == "json":
        print_json({"current_investigation_id": investigation_id})
    else:
        print_success(f"Current investigation set to: {investigation_id}")
        console.print(f"[dim]You can now run commands without --investigation-id.[/dim]")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.command("triage")
def cmd_triage(
    ctx: typer.Context,
    title: str = typer.Argument(..., help="Incident title / alert name"),
    symptom: Optional[str] = typer.Option(None, "--symptom", "-s", help="Observed symptom or alert description"),
    severity: str = typer.Option("high", "--severity", help="Severity: low|medium|high|critical"),
    service: Optional[str] = typer.Option(None, "--service", help="Affected service name"),
) -> None:
    """
    Rapidly create an investigation from an active incident / alert.
    Shortcut for: investigate create + add timeline event.
    """
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {
            "title": title,
            "severity": severity,
            "status": "in_progress",
        }
        if symptom:
            body["symptom"] = symptom
        if service:
            body["context"] = {"affected_service": service}

        try:
            inv = await api_post(app_ctx, "/api/v1/investigations", body=body)
            investigation_id = inv["id"]

            # Add initial timeline event
            from datetime import datetime, timezone
            event_body = {
                "investigation_id": investigation_id,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "event_type": "incident_reported",
                "description": f"Incident triage started: {title}",
                "source": "bugpilot-cli",
            }
            await api_post(app_ctx, "/api/v1/graph/timeline", body=event_body)

            if app_ctx.output_format == "json":
                print_json(inv)
            else:
                print_success(f"Incident triage started! Investigation: {investigation_id}")
                print_investigation(inv)
                console.print(f"\n[dim]Next steps:[/dim]")
                console.print(f"  bugpilot evidence collect --investigation-id {investigation_id} ...")
                console.print(f"  bugpilot hypotheses list --investigation-id {investigation_id}")
        except APIError as e:
            print_error(f"Triage failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("status")
def cmd_status(
    ctx: typer.Context,
    investigation_id: str = typer.Argument(..., help="Investigation ID"),
) -> None:
    """Show a full status summary of an active incident investigation."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            inv = await api_get(app_ctx, f"/api/v1/investigations/{investigation_id}")
            ev_data = await api_get(
                app_ctx, "/api/v1/evidence", params={"investigation_id": investigation_id}
            )
            hyp_data = await api_get(
                app_ctx, "/api/v1/hypotheses", params={"investigation_id": investigation_id}
            )
            act_data = await api_get(
                app_ctx, "/api/v1/actions", params={"investigation_id": investigation_id}
            )

            if app_ctx.output_format == "json":
                print_json({
                    "investigation": inv,
                    "evidence": ev_data,
                    "hypotheses": hyp_data,
                    "actions": act_data,
                })
            else:
                print_investigation(inv)
                console.print(f"\n[bold]Evidence:[/bold] {ev_data.get('total', 0)} items")
                console.print(f"[bold]Hypotheses:[/bold] {hyp_data.get('total', 0)} items")
                console.print(f"[bold]Actions:[/bold] {act_data.get('total', 0)} items")
        except APIError as e:
            print_error(f"Failed to get status: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
