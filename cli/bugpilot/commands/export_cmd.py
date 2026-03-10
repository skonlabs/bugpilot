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
from bugpilot.output.human import console, print_error, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError, api_get

app = typer.Typer(help="Export investigation data")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    ctx: AppContext = typer_ctx.obj
    if not ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)
    return ctx


async def _collect_investigation_bundle(app_ctx: AppContext, investigation_id: str) -> dict:
    """Collect all data for an investigation into a single bundle."""
    inv = await api_get(app_ctx, f"/api/v1/investigations/{investigation_id}")
    evidence = await api_get(app_ctx, "/api/v1/evidence", params={"investigation_id": investigation_id})
    hypotheses = await api_get(app_ctx, "/api/v1/hypotheses", params={"investigation_id": investigation_id})
    actions = await api_get(app_ctx, "/api/v1/actions", params={"investigation_id": investigation_id})
    timeline = await api_get(app_ctx, "/api/v1/graph/timeline", params={"investigation_id": investigation_id})

    return {
        "investigation": inv,
        "evidence": evidence.get("items", []),
        "hypotheses": hypotheses.get("items", []),
        "actions": actions.get("items", []),
        "timeline": timeline.get("events", []),
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "format_version": "1.0",
    }


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
            bundle = await _collect_investigation_bundle(app_ctx, investigation_id)
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
            bundle = await _collect_investigation_bundle(app_ctx, investigation_id)
            md = _render_markdown(bundle)
            if output:
                output.write_text(md)
                print_success(f"Markdown report saved to {output}")
            else:
                print(md)
        except APIError as e:
            print_error(f"Export failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


def _render_markdown(bundle: dict) -> str:
    inv = bundle["investigation"]
    lines = [
        f"# Incident Report: {inv.get('title', 'Unknown')}",
        "",
        f"**Status:** {inv.get('status', '-').upper()}",
        f"**Severity:** {inv.get('severity', '-').upper()}",
        f"**Created:** {inv.get('created_at', '-')}",
        f"**Resolved:** {inv.get('resolved_at') or 'Not resolved'}",
        "",
    ]

    if inv.get("symptom"):
        lines += ["## Symptom", "", inv["symptom"], ""]

    if inv.get("description"):
        lines += ["## Description", "", inv["description"], ""]

    # Timeline
    timeline = bundle.get("timeline", [])
    if timeline:
        lines += ["## Timeline", ""]
        for e in timeline:
            lines.append(f"- **{e.get('occurred_at', '-')[:19]}** [{e.get('event_type', '-')}] {e.get('description', '-')}")
        lines.append("")

    # Evidence
    evidence = bundle.get("evidence", [])
    if evidence:
        lines += ["## Evidence", ""]
        for ev in evidence:
            lines.append(f"- **{ev.get('kind', '-')}** — {ev.get('label', '-')}")
            if ev.get("summary"):
                lines.append(f"  > {ev['summary']}")
        lines.append("")

    # Hypotheses
    hypotheses = bundle.get("hypotheses", [])
    if hypotheses:
        lines += ["## Hypotheses", ""]
        for h in hypotheses:
            conf = h.get("confidence_score")
            conf_str = f" ({conf:.0%} confidence)" if conf is not None else ""
            lines.append(f"- [{h.get('status', '-').upper()}] **{h.get('title', '-')}**{conf_str}")
            if h.get("reasoning"):
                lines.append(f"  > {h['reasoning']}")
        lines.append("")

    # Actions
    actions = bundle.get("actions", [])
    if actions:
        lines += ["## Actions", ""]
        for a in actions:
            lines.append(
                f"- [{a.get('status', '-').upper()}] **{a.get('title', '-')}** "
                f"(risk: {a.get('risk_level', '-')})"
            )
        lines.append("")

    lines += [
        "---",
        f"*Generated by BugPilot at {bundle.get('exported_at', '')}*",
    ]
    return "\n".join(lines)
