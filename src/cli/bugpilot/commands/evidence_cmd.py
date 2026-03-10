"""
Evidence commands - collect, list, and view evidence items.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error, print_evidence_list, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_delete, api_get, api_post

app = typer.Typer(help="Evidence management commands")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


EVIDENCE_KINDS = ["log_snapshot", "metric_snapshot", "trace", "event", "config_diff", "topology", "custom"]


@app.command("list")
def cmd_list(
    ctx: typer.Context,
    investigation_id: str = typer.Option(..., "--investigation-id", "-i", help="Investigation ID"),
    kind: Optional[str] = typer.Option(None, "--kind", help=f"Filter by kind: {', '.join(EVIDENCE_KINDS)}"),
) -> None:
    """List evidence items for an investigation."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        params = {"investigation_id": investigation_id}
        if kind:
            params["kind"] = kind
        try:
            data = await api_get(app_ctx, "/api/v1/evidence", params=params)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_evidence_list(data["items"], data["total"])
        except APIError as e:
            print_error(f"Failed to list evidence: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("collect")
def cmd_collect(
    ctx: typer.Context,
    investigation_id: str = typer.Option(..., "--investigation-id", "-i"),
    label: str = typer.Option(..., "--label", "-l", help="Short label for the evidence"),
    kind: str = typer.Option("custom", "--kind", "-k", help=f"Evidence kind: {', '.join(EVIDENCE_KINDS)}"),
    source_uri: Optional[str] = typer.Option(None, "--source", help="Source URI (URL, file path, etc.)"),
    summary: Optional[str] = typer.Option(None, "--summary", "-s", help="Short summary of findings"),
    connector_id: Optional[str] = typer.Option(None, "--connector-id"),
) -> None:
    """Manually collect a piece of evidence."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {
            "investigation_id": investigation_id,
            "kind": kind,
            "label": label,
        }
        if source_uri:
            body["source_uri"] = source_uri
        if summary:
            body["summary"] = summary
        if connector_id:
            body["connector_id"] = connector_id

        try:
            data = await api_post(app_ctx, "/api/v1/evidence", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Evidence collected: {data['id']}")
                console.print(f"[dim]Label:[/dim] {data['label']}")
                console.print(f"[dim]Kind:[/dim] {data['kind']}")
                if data.get("expires_at"):
                    console.print(f"[dim]Expires:[/dim] {data['expires_at']}")
        except APIError as e:
            print_error(f"Failed to collect evidence: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("get")
def cmd_get(
    ctx: typer.Context,
    evidence_id: str = typer.Argument(..., help="Evidence ID"),
) -> None:
    """Get evidence details."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_get(app_ctx, f"/api/v1/evidence/{evidence_id}")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                from bugpilot.output.human import print_json_data
                print_json_data(data)
        except APIError as e:
            print_error(f"Evidence not found: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("delete")
def cmd_delete(
    ctx: typer.Context,
    evidence_id: str = typer.Argument(...),
    confirm: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete an evidence item."""
    app_ctx = _get_ctx(ctx)
    if not confirm:
        typer.confirm(f"Delete evidence {evidence_id}?", abort=True)

    async def _run():
        try:
            await api_delete(app_ctx, f"/api/v1/evidence/{evidence_id}")
            print_success(f"Evidence {evidence_id} deleted.")
        except APIError as e:
            print_error(f"Delete failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
