"""
Fix commands - suggest, approve, and run remediation actions.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, print_action_list, print_error, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get, api_patch, api_post

app = typer.Typer(help="Remediation action commands")

RISK_LEVELS = ["safe", "low", "medium", "high", "critical"]


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


@app.command("list")
def cmd_list(
    ctx: typer.Context,
    investigation_id: str = typer.Option(..., "--investigation-id", "-i"),
    status: Optional[str] = typer.Option(None, "--status"),
) -> None:
    """List actions for an investigation."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        params = {"investigation_id": investigation_id}
        if status:
            params["status"] = status
        try:
            data = await api_get(app_ctx, "/api/v1/actions", params=params)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_action_list(data["items"], data["total"])
        except APIError as e:
            print_error(f"Failed to list actions: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("suggest")
def cmd_suggest(
    ctx: typer.Context,
    investigation_id: str = typer.Option(..., "--investigation-id", "-i"),
    title: str = typer.Argument(..., help="Action title"),
    action_type: str = typer.Option(..., "--type", "-t", help="Action type, e.g. kubectl_rollback"),
    risk_level: str = typer.Option("medium", "--risk", help=f"Risk level: {', '.join(RISK_LEVELS)}"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    hypothesis_id: Optional[str] = typer.Option(None, "--hypothesis-id"),
    rollback_plan: Optional[str] = typer.Option(None, "--rollback-plan"),
) -> None:
    """Suggest a remediation action."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {
            "investigation_id": investigation_id,
            "title": title,
            "action_type": action_type,
            "risk_level": risk_level,
        }
        if description:
            body["description"] = description
        if hypothesis_id:
            body["hypothesis_id"] = hypothesis_id
        if rollback_plan:
            body["rollback_plan"] = rollback_plan

        try:
            data = await api_post(app_ctx, "/api/v1/actions", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Action suggested: {data['id']}")
                console.print(f"[dim]Title:[/dim] {data['title']}")
                console.print(f"[dim]Risk:[/dim] {data['risk_level'].upper()}")
                console.print(f"[dim]Status:[/dim] {data['status'].upper()}")
                console.print(f"\n[dim]To approve:[/dim] bugpilot fix approve {data['id']}")
        except APIError as e:
            print_error(f"Failed to suggest action: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("approve")
def cmd_approve(
    ctx: typer.Context,
    action_id: str = typer.Argument(..., help="Action ID to approve"),
) -> None:
    """Approve an action for execution (requires approver role)."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/actions/{action_id}/approve")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Action approved: {action_id}")
                console.print(f"[dim]To execute:[/dim] bugpilot fix run {action_id}")
        except APIError as e:
            print_error(f"Approve failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("run")
def cmd_run(
    ctx: typer.Context,
    action_id: str = typer.Argument(..., help="Action ID to execute"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Execute an approved action."""
    app_ctx = _get_ctx(ctx)

    async def _run_fetch():
        return await api_get(app_ctx, f"/api/v1/actions/{action_id}")

    if not confirm:
        try:
            action_data = anyio.run(_run_fetch)
            risk = action_data.get("risk_level", "unknown").upper()
            console.print(f"[bold yellow]Action:[/bold yellow] {action_data.get('title')}")
            console.print(f"[bold yellow]Risk level:[/bold yellow] {risk}")
            typer.confirm("Execute this action?", abort=True)
        except APIError as e:
            print_error(f"Failed to fetch action: {e.detail}")
            raise typer.Exit(1)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/actions/{action_id}/run")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Action executed: {action_id}")
                if data.get("result"):
                    console.print(f"[dim]Result:[/dim] {data['result']}")
        except APIError as e:
            print_error(f"Execution failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("dry-run")
def cmd_dry_run(
    ctx: typer.Context,
    action_id: str = typer.Argument(..., help="Action ID to simulate"),
) -> None:
    """Simulate an action without executing it — show predicted changes."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/actions/{action_id}/dry-run")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                console.print(f"[bold]Dry-run result for:[/bold] {action_id}")
                console.print(f"[dim]Predicted changes:[/dim]")
                changes = data.get("predicted_changes") or data.get("dry_run_output") or str(data)
                console.print(changes)
        except APIError as e:
            print_error(f"Dry-run failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("cancel")
def cmd_cancel(
    ctx: typer.Context,
    action_id: str = typer.Argument(...),
) -> None:
    """Cancel a pending or approved action."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/actions/{action_id}/cancel")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Action cancelled: {action_id}")
        except APIError as e:
            print_error(f"Cancel failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
