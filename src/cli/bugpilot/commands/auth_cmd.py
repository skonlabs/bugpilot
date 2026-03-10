"""
Auth commands - activate license, logout, whoami.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from bugpilot.auth.client import activate, logout, whoami
from bugpilot.config_loader import TOS_FILE, CONFIG_DIR
from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error, print_info, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError

app = typer.Typer(help="Authentication commands")

_TOS_TEXT = """\
[bold]BugPilot Terms of Service[/bold]

By activating BugPilot you agree to the following:

  1. BugPilot accesses your monitoring and infrastructure data
     only with the credentials you explicitly provide.

  2. Evidence summaries may be sent to an AI/LLM provider when
     the LLM synthesis feature is enabled. PII is redacted
     automatically before transmission.

  3. You are responsible for ensuring you have authorization to
     connect BugPilot to your organisation's systems.

  4. BugPilot stores credentials locally at
     ~/.config/bugpilot/credentials.json (permissions 600) and
     connector config at ~/.config/bugpilot/config.yaml (600).

Full Terms of Service: https://bugpilot.io/terms
Privacy Policy:        https://bugpilot.io/privacy
"""

_NEXT_STEPS = """\
[bold green]✓ BugPilot activated![/bold green]

[bold]Next steps:[/bold]

  1. [bold]Set up a connector[/bold] (connect to your data sources)
       bugpilot connector add datadog
       bugpilot connector add grafana
       bugpilot connector add cloudwatch
       bugpilot connector add github
       bugpilot connector add kubernetes
       bugpilot connector add pagerduty

     Or initialise the config file and edit manually:
       bugpilot config init

  2. [bold]Test connectivity[/bold]
       bugpilot connector test

  3. [bold]Start your first investigation[/bold]  (on-demand mode)
       bugpilot investigate create --title "High error rate on payment-service" \\
         --symptom "HTTP 5xx above 5%" --severity high

  4. [bold]Set up webhooks[/bold]  (automatic mode)
     Configure your monitoring platform to POST alerts to:
       https://api.bugpilot.io/api/v1/webhooks/<source>
     Then add the webhook secret to your config:
       bugpilot config init   # edit the webhooks section

  Run [bold]bugpilot --help[/bold] at any time to see all commands.
"""


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    return typer_ctx.obj


def _ensure_tos_accepted() -> None:
    """Display T&C and require acceptance. Exits if declined."""
    if TOS_FILE.exists():
        return  # Already accepted

    console.print(Panel(_TOS_TEXT, title="Terms of Service", border_style="yellow"))

    accepted = Confirm.ask("\nDo you accept the Terms of Service?", default=False)
    if not accepted:
        console.print("[red]Terms of Service declined. BugPilot will not be activated.[/red]")
        raise typer.Exit(1)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOS_FILE.write_text("accepted\n")
    TOS_FILE.chmod(0o600)
    print_success("Terms of Service accepted.")
    console.print()


@app.command("activate")
def cmd_activate(
    ctx: typer.Context,
    license_key: Optional[str] = typer.Option(
        None, "--key", "-k", help="License key", envvar="BUGPILOT_LICENSE_KEY"
    ),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Your email address"),
    display_name: Optional[str] = typer.Option(None, "--name", help="Your display name"),
) -> None:
    """Activate a BugPilot license and store credentials."""
    app_ctx = _get_ctx(ctx)

    # Terms of Service must be accepted before activation
    _ensure_tos_accepted()

    if not license_key:
        license_key = Prompt.ask("[bold]Enter your license key[/bold]", password=True)
    if not email:
        email = Prompt.ask("[bold]Enter your email address[/bold]")

    async def _run():
        try:
            resp = await activate(
                app_ctx,
                license_key=license_key,
                email=email,
                display_name=display_name,
            )
            if app_ctx.output_format == "json":
                print_json(
                    {
                        "status": "activated",
                        "org_id": resp["org_id"],
                        "user_id": resp["user_id"],
                        "role": resp["role"],
                    }
                )
            else:
                console.print(Panel(_NEXT_STEPS, border_style="green"))
        except APIError as e:
            print_error(f"Activation failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("logout")
def cmd_logout(ctx: typer.Context) -> None:
    """Revoke the current session and clear stored credentials."""
    app_ctx = _get_ctx(ctx)

    async def _run():
        await logout(app_ctx)
        if app_ctx.output_format == "json":
            print_json({"status": "logged_out"})
        else:
            print_success("Logged out successfully.")

    anyio.run(_run)


@app.command("whoami")
def cmd_whoami(ctx: typer.Context) -> None:
    """Show current authenticated user info."""
    app_ctx = _get_ctx(ctx)
    if not app_ctx.load_credentials():
        print_error("Not authenticated. Run: bugpilot auth activate")
        raise typer.Exit(1)

    async def _run():
        try:
            data = await whoami(app_ctx)
            if app_ctx.output_format == "json":
                print_json(data)
            else:
                console.print(f"[bold]User:[/bold] {data.get('email')}")
                console.print(f"[bold]Display name:[/bold] {data.get('display_name') or '-'}")
                console.print(f"[bold]Role:[/bold] {data.get('role')}")
                console.print(f"[bold]Org ID:[/bold] {data.get('org_id')}")
                console.print(f"[bold]User ID:[/bold] {data.get('user_id')}")
        except APIError as e:
            print_error(f"Failed to get user info: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)


@app.command("status")
def cmd_status(ctx: typer.Context) -> None:
    """Show current session status (validity, expiry, role)."""
    app_ctx = _get_ctx(ctx)
    if not app_ctx.load_credentials():
        if app_ctx.output_format == "json":
            print_json({"authenticated": False})
        else:
            print_info("Not authenticated. Run: bugpilot auth activate")
        return

    async def _run():
        try:
            data = await whoami(app_ctx)
            if app_ctx.output_format == "json":
                print_json({"authenticated": True, **data})
            else:
                console.print(f"[green]✓[/green] Authenticated")
                console.print(f"[bold]User:[/bold] {data.get('email')}")
                console.print(f"[bold]Role:[/bold] {data.get('role')}")
                console.print(f"[bold]Org:[/bold] {data.get('org_id')}")
        except APIError as e:
            print_error(f"Session check failed: {e.detail}")
            raise typer.Exit(1)

    anyio.run(_run)
