"""
Connector commands - manage data source integrations in ~/.config/bugpilot/config.yaml
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box

from bugpilot.config_loader import (
    CONNECTOR_FIELDS,
    CONNECTOR_TYPES,
    BugPilotConfig,
    ConnectorEntry,
)
from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error, print_info, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError

app = typer.Typer(help="Manage data source connectors")

def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    return typer_ctx.obj


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command("list")
def cmd_list(ctx: typer.Context) -> None:
    """List configured connectors from ~/.config/bugpilot/config.yaml."""
    app_ctx = _get_ctx(ctx)
    cfg = BugPilotConfig.load()

    if not cfg.connectors:
        print_info("No connectors configured. Run: bugpilot connector add <type>")
        return

    if app_ctx.output_format == "json":
        print_json({
            name: {"kind": entry.kind, **entry.masked()}
            for name, entry in cfg.connectors.items()
        })
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Key Fields")

    for name, entry in cfg.connectors.items():
        masked = entry.masked()
        fields_preview = []
        for fdef in CONNECTOR_FIELDS.get(entry.kind, []):
            val = masked.get(fdef["key"])
            if val:
                fields_preview.append(f"{fdef['key']}={val}")
            if len(fields_preview) >= 3:
                break
        table.add_row(name, entry.kind, ", ".join(fields_preview) or "-")

    console.print(table)
    console.print(f"[dim]{len(cfg.connectors)} connector(s) configured[/dim]")


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

@app.command("add")
def cmd_add(
    ctx: typer.Context,
    connector_type: str = typer.Argument(
        ...,
        help=f"Connector type: {', '.join(CONNECTOR_TYPES)}",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Unique name for this connector instance (default: same as type). "
             "Use a custom name to configure multiple instances of the same type, "
             "e.g. --name grafana-prod",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if already configured"),
) -> None:
    """Add or update a connector interactively.

    To configure multiple instances of the same type use --name:

      bugpilot connector add grafana --name grafana-prod
      bugpilot connector add grafana --name grafana-staging
    """
    connector_type = connector_type.lower()
    if connector_type not in CONNECTOR_FIELDS:
        print_error(f"Unknown connector type: {connector_type!r}")
        print_info(f"Supported types: {', '.join(CONNECTOR_TYPES)}")
        raise typer.Exit(1)

    connector_name = (name or connector_type).strip()

    cfg = BugPilotConfig.load()

    if connector_name in cfg.connectors and not overwrite:
        existing_kind = cfg.connectors[connector_name].kind
        label = f"'{connector_name}' ({existing_kind})"
        if not Confirm.ask(
            f"[yellow]Connector {label} is already configured. Overwrite?[/yellow]"
        ):
            raise typer.Exit(0)

    console.print(f"\n[bold]Configure {connector_type} connector[/bold]"
                  + (f" [dim](name: {connector_name})[/dim]" if connector_name != connector_type else "")
                  + "\n")
    config: dict = {}

    for fdef in CONNECTOR_FIELDS[connector_type]:
        key = fdef["key"]
        label = fdef["label"]
        is_secret = fdef.get("secret", False)
        is_optional = fdef.get("optional", False)
        is_list = fdef.get("list_field", False)
        default = fdef.get("default")

        prompt_label = label
        if is_optional:
            prompt_label += " (leave blank to skip)"

        if is_secret:
            value = Prompt.ask(f"  {prompt_label}", password=True, default="" if is_optional else ...)
        elif default is not None:
            value = Prompt.ask(f"  {prompt_label}", default=str(default))
        else:
            value = Prompt.ask(f"  {prompt_label}", default="" if is_optional else ...)

        if not value:
            if not is_optional:
                print_error(f"{key} is required.")
                raise typer.Exit(1)
            continue

        if is_list:
            items = [item.strip() for item in value.split(",") if item.strip()]
            config[key] = items
        else:
            config[key] = value

    cfg.connectors[connector_name] = ConnectorEntry(name=connector_name, kind=connector_type, config=config)
    cfg.save()
    print_success(f"Connector '{connector_name}' saved to ~/.config/bugpilot/config.yaml")
    print_info("Run 'bugpilot connector test' to verify connectivity.")


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

@app.command("remove")
def cmd_remove(
    ctx: typer.Context,
    connector_name: str = typer.Argument(..., help="Connector name to remove (from 'bugpilot connector list')"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove a connector from config."""
    cfg = BugPilotConfig.load()

    if connector_name not in cfg.connectors:
        print_error(f"Connector '{connector_name}' is not configured.")
        raise typer.Exit(1)

    kind = cfg.connectors[connector_name].kind
    if not yes:
        if not Confirm.ask(f"Remove connector '[bold]{connector_name}[/bold]' ({kind})?"):
            raise typer.Exit(0)

    del cfg.connectors[connector_name]
    cfg.save()
    print_success(f"Connector '{connector_name}' removed.")


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

@app.command("test")
def cmd_test(
    ctx: typer.Context,
    connector_name: Optional[str] = typer.Argument(
        None, help="Connector name to test (omit to test all). Use 'bugpilot connector list' to see names."
    ),
) -> None:
    """Test connector connectivity via the BugPilot API."""
    app_ctx = _get_ctx(ctx)

    if not app_ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)

    cfg = BugPilotConfig.load()

    if not cfg.connectors:
        print_info("No connectors configured. Run: bugpilot connector add <type>")
        return

    to_test: dict = {}
    if connector_name:
        if connector_name not in cfg.connectors:
            print_error(f"Connector '{connector_name}' is not configured.")
            raise typer.Exit(1)
        to_test[connector_name] = cfg.connectors[connector_name]
    else:
        to_test = dict(cfg.connectors)

    async def _run():
        results = {}
        async with app_ctx.make_analysis_client() as client:
            for name, entry in to_test.items():
                label = name if name == entry.kind else f"{name} ({entry.kind})"
                console.print(f"  Testing [bold]{label}[/bold]...", end=" ")
                try:
                    r = await client.post(
                        "/api/v1/admin/connectors/test",
                        json={"kind": entry.kind, "config": entry.config},
                    )
                    if r.status_code == 200:
                        latency = r.json().get("latency_ms")
                        suffix = f" [dim]{latency:.0f}ms[/dim]" if latency else ""
                        console.print(f"[green]✓ OK[/green]{suffix}")
                        results[name] = {"status": "ok"}
                    else:
                        detail = r.json().get("detail", r.text)
                        console.print(f"[red]✗ FAILED[/red] — {detail}")
                        results[name] = {"status": "failed", "detail": detail}
                except Exception as exc:
                    console.print(f"[red]✗ ERROR[/red] — {exc}")
                    results[name] = {"status": "error", "detail": str(exc)}

        if app_ctx.output_format == "json":
            print_json(results)

    anyio.run(_run)
