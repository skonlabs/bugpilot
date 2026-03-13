"""
Hypotheses commands - list, create, confirm, and reject hypotheses.
"""
from __future__ import annotations

from typing import List, Optional

import anyio
import typer

from bugpilot.context import AppContext
from bugpilot.output.human import console, debug_exc, print_error, print_hypothesis_list, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get, api_patch, api_post, api_post_analysis

app = typer.Typer(help="Hypothesis management commands")


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
    status: Optional[str] = typer.Option(None, "--status", "-s"),
    refresh: bool = typer.Option(False, "--refresh", help="Trigger hypothesis regeneration before listing"),
) -> None:
    """List hypotheses for an investigation. Use --refresh to trigger regeneration."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        if refresh:
            try:
                await api_post_analysis(
                    app_ctx,
                    f"/api/v1/investigations/{investigation_id}/hypotheses/refresh",
                )
                console.print("[dim]Hypothesis regeneration triggered...[/dim]")
            except APIError as e:
                print_error(f"Failed to trigger refresh: {e.detail}")
                debug_exc(app_ctx.debug)
                raise typer.Exit(1)

        params: dict = {"investigation_id": investigation_id}
        if status:
            params["status"] = status
        try:
            data = await api_get(app_ctx, "/api/v1/hypotheses", params=params)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_hypothesis_list(data["items"], data["total"])
        except APIError as e:
            print_error(f"Failed to list hypotheses: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("create")
def cmd_create(
    ctx: typer.Context,
    investigation_id: str = typer.Option(..., "--investigation-id", "-i"),
    title: str = typer.Argument(..., help="Hypothesis title"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    confidence: Optional[float] = typer.Option(None, "--confidence", "-c", min=0.0, max=1.0),
    reasoning: Optional[str] = typer.Option(None, "--reasoning"),
    evidence_ids: Optional[List[str]] = typer.Option(None, "--evidence", help="Supporting evidence IDs"),
) -> None:
    """Create a new hypothesis."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {
            "investigation_id": investigation_id,
            "title": title,
            "generated_by_llm": False,
        }
        if description:
            body["description"] = description
        if confidence is not None:
            body["confidence_score"] = confidence
        if reasoning:
            body["reasoning"] = reasoning
        if evidence_ids:
            body["supporting_evidence"] = list(evidence_ids)

        try:
            data = await api_post(app_ctx, "/api/v1/hypotheses", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Hypothesis created: {data['id']}")
                console.print(f"[dim]Title:[/dim] {data['title']}")
                conf = data.get("confidence_score")
                if conf is not None:
                    console.print(f"[dim]Confidence:[/dim] {conf:.0%}")
        except APIError as e:
            print_error(f"Failed to create hypothesis: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("confirm")
def cmd_confirm(
    ctx: typer.Context,
    hypothesis_id: str = typer.Argument(..., help="Hypothesis ID"),
) -> None:
    """Mark a hypothesis as confirmed (root cause identified)."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/hypotheses/{hypothesis_id}/confirm")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Hypothesis confirmed: {hypothesis_id}")
        except APIError as e:
            print_error(f"Confirm failed: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("reject")
def cmd_reject(
    ctx: typer.Context,
    hypothesis_id: str = typer.Argument(...),
) -> None:
    """Mark a hypothesis as rejected."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        try:
            data = await api_post(app_ctx, f"/api/v1/hypotheses/{hypothesis_id}/reject")
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success(f"Hypothesis rejected: {hypothesis_id}")
        except APIError as e:
            print_error(f"Reject failed: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("update")
def cmd_update(
    ctx: typer.Context,
    hypothesis_id: str = typer.Argument(...),
    title: Optional[str] = typer.Option(None),
    confidence: Optional[float] = typer.Option(None, min=0.0, max=1.0),
    reasoning: Optional[str] = typer.Option(None),
) -> None:
    """Update a hypothesis."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        body = {}
        if title:
            body["title"] = title
        if confidence is not None:
            body["confidence_score"] = confidence
        if reasoning:
            body["reasoning"] = reasoning
        if not body:
            print_error("No fields to update.")
            raise typer.Exit(1)

        try:
            data = await api_patch(app_ctx, f"/api/v1/hypotheses/{hypothesis_id}", body=body)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                print_success("Hypothesis updated.")
        except APIError as e:
            print_error(f"Update failed: {e.detail}")
            debug_exc(app_ctx.debug)
            raise typer.Exit(1)

    anyio.run(_run)
