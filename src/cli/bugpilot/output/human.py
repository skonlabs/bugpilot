"""
Human-readable output formatter using Rich.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()
error_console = Console(stderr=True)

# Severity colors
SEVERITY_STYLES = {
    "low": "green",
    "medium": "yellow",
    "high": "red",
    "critical": "bold red",
}

STATUS_STYLES = {
    "open": "cyan",
    "in_progress": "yellow",
    "resolved": "green",
    "closed": "dim",
    "proposed": "cyan",
    "testing": "yellow",
    "confirmed": "green",
    "rejected": "red",
    "pending": "yellow",
    "approved": "blue",
    "running": "magenta",
    "completed": "green",
    "failed": "red",
    "cancelled": "dim",
}

RISK_STYLES = {
    "safe": "green",
    "low": "blue",
    "medium": "yellow",
    "high": "red",
    "critical": "bold red",
}


def _fmt_dt(dt: Optional[str]) -> str:
    if not dt:
        return "-"
    try:
        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(dt)


def print_success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    error_console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    console.print(f"[blue]i[/blue] {message}")


def print_investigation(inv: Dict[str, Any]) -> None:
    severity = inv.get("severity", "medium")
    status = inv.get("status", "open")
    severity_style = SEVERITY_STYLES.get(severity, "white")
    status_style = STATUS_STYLES.get(status, "white")

    panel_content = (
        f"[bold]{inv.get('title', 'Unknown')}[/bold]\n\n"
        f"[dim]ID:[/dim] {inv.get('id', '-')}\n"
        f"[dim]Severity:[/dim] [{severity_style}]{severity.upper()}[/{severity_style}]\n"
        f"[dim]Status:[/dim] [{status_style}]{status.upper()}[/{status_style}]\n"
        f"[dim]Created:[/dim] {_fmt_dt(inv.get('created_at'))}\n"
    )
    if inv.get("symptom"):
        panel_content += f"\n[dim]Symptom:[/dim]\n{inv['symptom']}"
    if inv.get("description"):
        panel_content += f"\n\n[dim]Description:[/dim]\n{inv['description']}"

    console.print(Panel(panel_content, title="[bold]Investigation[/bold]", box=box.ROUNDED))


def print_investigation_list(items: List[Dict[str, Any]], total: int) -> None:
    if not items:
        console.print("[dim]No investigations found.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", max_width=36)
    table.add_column("Title", max_width=50)
    table.add_column("Severity", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Created", justify="right")

    for inv in items:
        severity = inv.get("severity", "-")
        st = inv.get("status", "-")
        table.add_row(
            inv.get("id", "-")[:8] + "...",
            inv.get("title", "-"),
            Text(severity.upper(), style=SEVERITY_STYLES.get(severity, "white")),
            Text(st.upper(), style=STATUS_STYLES.get(st, "white")),
            _fmt_dt(inv.get("created_at")),
        )

    console.print(table)
    console.print(f"[dim]Showing {len(items)} of {total} investigations[/dim]")


def print_evidence_list(items: List[Dict[str, Any]], total: int) -> None:
    if not items:
        console.print("[dim]No evidence collected.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Kind")
    table.add_column("Label", max_width=50)
    table.add_column("Summary", max_width=40)
    table.add_column("Collected")

    for ev in items:
        table.add_row(
            ev.get("id", "-")[:8] + "...",
            ev.get("kind", "-"),
            ev.get("label", "-"),
            (ev.get("summary") or "-")[:40],
            _fmt_dt(ev.get("collected_at")),
        )

    console.print(table)
    console.print(f"[dim]{total} evidence items[/dim]")


def print_hypothesis_list(items: List[Dict[str, Any]], total: int) -> None:
    if not items:
        console.print("[dim]No hypotheses.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title", max_width=50)
    table.add_column("Confidence", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("LLM")

    for i, h in enumerate(items, 1):
        conf = h.get("confidence_score")
        conf_str = f"{conf:.0%}" if conf is not None else "-"
        st = h.get("status", "-")
        table.add_row(
            str(i),
            h.get("title", "-"),
            conf_str,
            Text(st.upper(), style=STATUS_STYLES.get(st, "white")),
            "yes" if h.get("generated_by_llm") else "no",
        )

    console.print(table)
    console.print(f"[dim]{total} hypotheses[/dim]")


def print_action_list(items: List[Dict[str, Any]], total: int) -> None:
    if not items:
        console.print("[dim]No actions.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("ID", style="dim")
    table.add_column("Title", max_width=40)
    table.add_column("Type")
    table.add_column("Risk", justify="center")
    table.add_column("Status", justify="center")

    for a in items:
        risk = a.get("risk_level", "-")
        st = a.get("status", "-")
        table.add_row(
            a.get("id", "-")[:8] + "...",
            a.get("title", "-"),
            a.get("action_type", "-"),
            Text(risk.upper(), style=RISK_STYLES.get(risk, "white")),
            Text(st.upper(), style=STATUS_STYLES.get(st, "white")),
        )

    console.print(table)
    console.print(f"[dim]{total} actions[/dim]")


def print_json_data(data: Any) -> None:
    """Pretty-print any data structure."""
    from rich.pretty import pprint
    pprint(data)
