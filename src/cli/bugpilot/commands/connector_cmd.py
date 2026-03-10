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
from bugpilot.output.human import console, print_error, print_info, print_success, print_warning
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError

app = typer.Typer(help="Manage data source connectors")

_CONNECTOR_TEMPLATE = """\
# BugPilot Connector Configuration
# ──────────────────────────────────────────────────────────────────────────────
# Uncomment and fill in the connector(s) you want to use.
# Secrets can be stored as environment variables:  api_key: ${MY_ENV_VAR}
#
# Apply after editing:  bugpilot connector test
# ──────────────────────────────────────────────────────────────────────────────

connectors:

  # ── Datadog ───────────────────────────────────────────────────────────────
  # datadog:
  #   api_key: ${DATADOG_API_KEY}          # required, secret
  #   app_key: ${DATADOG_APP_KEY}          # required, secret
  #   site: datadoghq.com                  # e.g. datadoghq.eu, us3.datadoghq.com

  # ── Grafana ───────────────────────────────────────────────────────────────
  # grafana:
  #   url: https://grafana.example.com     # required
  #   api_token: ${GRAFANA_TOKEN}          # required, service-account token
  #   org_id: "1"                          # default: 1
  #   prometheus_datasource_uid:           # optional

  # ── AWS CloudWatch ────────────────────────────────────────────────────────
  # cloudwatch:
  #   aws_access_key_id: AKIAIOSFODNN7EXAMPLE
  #   aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
  #   region: us-east-1
  #   log_group_names:                     # optional
  #     - /aws/lambda/my-function

  # ── GitHub ────────────────────────────────────────────────────────────────
  # github:
  #   token: ${GITHUB_TOKEN}               # PAT or GitHub App token
  #   org: my-org
  #   repos:                               # optional – omit to include all
  #     - my-repo

  # ── Kubernetes ────────────────────────────────────────────────────────────
  # kubernetes:
  #   api_server: https://k8s.example.com:6443
  #   token: ${K8S_SERVICE_ACCOUNT_TOKEN}
  #   namespace: production
  #   extra_namespaces:                    # optional
  #     - staging
  #   ca_cert_path:                        # optional, e.g. /etc/ssl/certs/ca.crt

  # ── PagerDuty ─────────────────────────────────────────────────────────────
  # pagerduty:
  #   api_key: ${PAGERDUTY_API_KEY}
  #   from_email: oncall@example.com
  #   service_ids:                         # optional
  #     - P1234567
"""


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    return typer_ctx.obj


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@app.command("init")
def cmd_init(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Write a template config.yaml to ~/.config/bugpilot/config.yaml."""
    from bugpilot.config_loader import CONFIG_DIR, CONFIG_YAML

    if CONFIG_YAML.exists() and not force:
        print_warning(f"Config already exists: {CONFIG_YAML}")
        print_info("Use --force to overwrite, or edit it directly.")
        raise typer.Exit(0)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_YAML.write_text(_CONNECTOR_TEMPLATE)
    CONFIG_YAML.chmod(0o600)

    print_success(f"Template written to {CONFIG_YAML}")
    console.print(
        "\n[dim]Uncomment the connector(s) you want, fill in your credentials,\n"
        "then run:[/dim]  bugpilot connector test\n"
    )


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
        print_json({k: v.masked() for k, v in cfg.connectors.items()})
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Type")
    table.add_column("Key Fields")

    for kind, entry in cfg.connectors.items():
        masked = entry.masked()
        # Show a few key fields (non-secret first)
        fields_preview = []
        for fdef in CONNECTOR_FIELDS.get(kind, []):
            val = masked.get(fdef["key"])
            if val:
                fields_preview.append(f"{fdef['key']}={val}")
            if len(fields_preview) >= 3:
                break
        table.add_row(kind, ", ".join(fields_preview) or "-")

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
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if already configured"),
) -> None:
    """Add or update a connector interactively."""
    connector_type = connector_type.lower()
    if connector_type not in CONNECTOR_FIELDS:
        print_error(f"Unknown connector type: {connector_type!r}")
        print_info(f"Supported types: {', '.join(CONNECTOR_TYPES)}")
        raise typer.Exit(1)

    cfg = BugPilotConfig.load()

    if connector_type in cfg.connectors and not overwrite:
        if not Confirm.ask(
            f"[yellow]Connector '{connector_type}' is already configured. Overwrite?[/yellow]"
        ):
            raise typer.Exit(0)

    console.print(f"\n[bold]Configure {connector_type} connector[/bold]\n")
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
            # Convert comma-separated string to list
            items = [item.strip() for item in value.split(",") if item.strip()]
            config[key] = items
        else:
            config[key] = value

    cfg.connectors[connector_type] = ConnectorEntry(kind=connector_type, config=config)
    cfg.save()
    print_success(f"Connector '{connector_type}' saved to ~/.config/bugpilot/config.yaml")
    print_info("Run 'bugpilot connector test' to verify connectivity.")


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

@app.command("remove")
def cmd_remove(
    ctx: typer.Context,
    connector_type: str = typer.Argument(..., help="Connector type to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove a connector from config."""
    connector_type = connector_type.lower()
    cfg = BugPilotConfig.load()

    if connector_type not in cfg.connectors:
        print_error(f"Connector '{connector_type}' is not configured.")
        raise typer.Exit(1)

    if not yes:
        if not Confirm.ask(f"Remove connector '[bold]{connector_type}[/bold]'?"):
            raise typer.Exit(0)

    del cfg.connectors[connector_type]
    cfg.save()
    print_success(f"Connector '{connector_type}' removed.")


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

@app.command("test")
def cmd_test(
    ctx: typer.Context,
    connector_type: Optional[str] = typer.Argument(
        None, help="Connector type to test (omit to test all)"
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
    if connector_type:
        connector_type = connector_type.lower()
        if connector_type not in cfg.connectors:
            print_error(f"Connector '{connector_type}' is not configured.")
            raise typer.Exit(1)
        to_test[connector_type] = cfg.connectors[connector_type]
    else:
        to_test = dict(cfg.connectors)

    async def _run():
        results = {}
        async with app_ctx.make_client() as client:
            for kind, entry in to_test.items():
                console.print(f"  Testing [bold]{kind}[/bold]...", end=" ")
                try:
                    r = await client.post(
                        "/api/v1/admin/connectors/test",
                        json={"kind": kind, "config": entry.config},
                    )
                    if r.status_code == 200:
                        console.print("[green]✓ OK[/green]")
                        results[kind] = {"status": "ok"}
                    else:
                        detail = r.json().get("detail", r.text)
                        console.print(f"[red]✗ FAILED[/red] — {detail}")
                        results[kind] = {"status": "failed", "detail": detail}
                except Exception as exc:
                    console.print(f"[red]✗ ERROR[/red] — {exc}")
                    results[kind] = {"status": "error", "detail": str(exc)}

        if app_ctx.output_format == "json":
            print_json(results)

    anyio.run(_run)
