"""
Config commands - manage ~/.config/bugpilot/config.yaml
"""
from __future__ import annotations

import typer

from bugpilot.config_loader import (
    CONFIG_DIR,
    CONFIG_YAML,
    BugPilotConfig,
)
from bugpilot.context import AppContext
from bugpilot.output.human import console, print_info, print_success, print_warning
from bugpilot.output.json_out import print_json

app = typer.Typer(help="Manage BugPilot configuration")

_SAMPLE_CONFIG = """\
# BugPilot Configuration
#
# Each connector entry has a unique NAME (the key) and a "kind" field that
# sets the connector type. This lets you configure multiple instances of the
# same type, e.g. two Grafana installations or two GitHub organisations.
#
# Example with two Grafana instances:
#
#   grafana-prod:
#     kind: grafana
#     url: https://grafana.prod.example.com
#     api_token: ${GRAFANA_PROD_TOKEN}
#   grafana-staging:
#     kind: grafana
#     url: https://grafana.staging.example.com
#     api_token: ${GRAFANA_STAGING_TOKEN}
#
# Uncomment and fill in the connector(s) you need.

connectors:

  # ── Datadog ──────────────────────────────────────────────────────────────
  # datadog:
  #   kind: datadog
  #   api_key: ${DD_API_KEY}
  #   app_key: ${DD_APP_KEY}
  #   site: datadoghq.com       # e.g. datadoghq.eu, us3.datadoghq.com

  # ── Grafana ──────────────────────────────────────────────────────────────
  # grafana:
  #   kind: grafana
  #   url: https://grafana.example.com
  #   api_token: ${GRAFANA_TOKEN}
  #   org_id: "1"
  #   prometheus_datasource_uid:  # optional

  # ── AWS CloudWatch ────────────────────────────────────────────────────────
  # cloudwatch:
  #   kind: cloudwatch
  #   aws_access_key_id: ${AWS_ACCESS_KEY_ID}
  #   aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
  #   region: us-east-1
  #   log_group_names:           # optional
  #     - /aws/lambda/my-function

  # ── GitHub ────────────────────────────────────────────────────────────────
  # github:
  #   kind: github
  #   token: ${GITHUB_TOKEN}
  #   org: mycompany
  #   repos:                     # optional – omit to include all
  #     - my-repo

  # ── Kubernetes ────────────────────────────────────────────────────────────
  # kubernetes:
  #   kind: kubernetes
  #   api_server: https://k8s.example.com:6443
  #   token: ${K8S_TOKEN}
  #   namespace: production
  #   extra_namespaces:          # optional
  #     - staging
  #   ca_cert_path:              # optional

  # ── PagerDuty ─────────────────────────────────────────────────────────────
  # pagerduty:
  #   kind: pagerduty
  #   api_key: ${PD_API_KEY}
  #   from_email: oncall@example.com
  #   service_ids:               # optional
  #     - P1234567

webhooks:
  # Set secrets that match what you configure in your monitoring platform
  # datadog:
  #   secret: ${DD_WEBHOOK_SECRET}
  # grafana:
  #   secret: ${GRAFANA_WEBHOOK_SECRET}
  # cloudwatch:
  #   secret: ${CW_WEBHOOK_SECRET}
  # pagerduty:
  #   secret: ${PD_WEBHOOK_SECRET}

global:
  connector_timeout_seconds: 30
  connector_max_retries: 3
  evidence_collection_timeout_seconds: 45
"""


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    return typer_ctx.obj


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@app.command("init")
def cmd_init(
    ctx: typer.Context,
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing config"),
) -> None:
    """Create a starter config.yaml with all connector templates."""
    if CONFIG_YAML.exists() and not overwrite:
        print_warning(f"Config already exists at {CONFIG_YAML}")
        print_info("Use --overwrite to replace it, or edit it directly.")
        raise typer.Exit(0)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_YAML.write_text(_SAMPLE_CONFIG)
    CONFIG_YAML.chmod(0o600)
    print_success(f"Config created at {CONFIG_YAML}")
    console.print(
        "\n[dim]Edit the file to fill in your credentials, or use:[/dim]\n"
        "  [bold]bugpilot connector add <type>[/bold]   — interactive setup\n"
        "  [bold]bugpilot config show[/bold]             — view current settings\n"
        "  [bold]bugpilot config validate[/bold]         — check for missing fields\n"
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

@app.command("show")
def cmd_show(ctx: typer.Context) -> None:
    """Show current configuration (secrets masked)."""
    app_ctx = _get_ctx(ctx)
    cfg = BugPilotConfig.load()

    if app_ctx.output_format == "json":
        out = {
            "connectors": {k: v.masked() for k, v in cfg.connectors.items()},
            "webhooks": {
                k: {ck: ("****" if ck == "secret" and cv else cv) for ck, cv in v.items()}
                for k, v in cfg.webhooks.items()
            },
            "global": cfg.global_settings,
        }
        print_json(out)
        return

    if not cfg.connectors and not cfg.webhooks and not cfg.global_settings:
        print_info(f"No config found at {CONFIG_YAML}")
        print_info("Run 'bugpilot config init' to create a starter config.")
        return

    console.print(f"\n[bold]Config:[/bold] {CONFIG_YAML}\n")

    if cfg.connectors:
        console.print("[bold]Connectors:[/bold]")
        for kind, entry in cfg.connectors.items():
            masked = entry.masked()
            console.print(f"  [cyan]{kind}[/cyan]")
            for k, v in masked.items():
                if isinstance(v, list):
                    console.print(f"    {k}: {', '.join(str(i) for i in v) or '(empty)'}")
                else:
                    console.print(f"    {k}: {v or '(empty)'}")
    else:
        console.print("[dim]  No connectors configured.[/dim]")

    if cfg.webhooks:
        console.print("\n[bold]Webhooks:[/bold]")
        for kind, wcfg in cfg.webhooks.items():
            secret = wcfg.get("secret", "")
            masked_secret = "****" if secret else "(not set)"
            console.print(f"  [cyan]{kind}[/cyan]  secret: {masked_secret}")

    if cfg.global_settings:
        console.print("\n[bold]Global settings:[/bold]")
        for k, v in cfg.global_settings.items():
            console.print(f"  {k}: {v}")

    console.print()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@app.command("validate")
def cmd_validate(ctx: typer.Context) -> None:
    """Validate config.yaml for missing required fields."""
    app_ctx = _get_ctx(ctx)
    cfg = BugPilotConfig.load()
    errors = cfg.validate()

    if app_ctx.output_format == "json":
        print_json({"valid": not errors, "errors": errors})
        return

    if errors:
        print_warning(f"Found {len(errors)} validation error(s):")
        for err in errors:
            console.print(f"  [red]•[/red] {err}")
        raise typer.Exit(1)
    else:
        print_success("Config is valid.")
        console.print(f"  [dim]{len(cfg.connectors)} connector(s) configured[/dim]")
