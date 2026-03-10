"""
Verbose output formatter - human-readable with additional debug details.
"""
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.syntax import Syntax
import json

verbose_console = Console()


def print_verbose(label: str, data: Any) -> None:
    """Print a labelled section with syntax-highlighted JSON."""
    verbose_console.print(f"\n[bold cyan]{label}[/bold cyan]")
    verbose_console.print(
        Syntax(
            json.dumps(data, indent=2, default=str),
            "json",
            theme="monokai",
            line_numbers=False,
        )
    )


def print_request(method: str, url: str, body: Any = None) -> None:
    verbose_console.print(f"[dim]→ {method} {url}[/dim]")
    if body:
        print_verbose("Request body", body)


def print_response(status_code: int, data: Any) -> None:
    color = "green" if status_code < 400 else "red"
    verbose_console.print(f"[{color}]← {status_code}[/{color}]")
    print_verbose("Response", data)
