"""
Auth commands - activate license, logout, whoami.
"""
from __future__ import annotations

from typing import Optional

import anyio
import typer
from rich.prompt import Prompt

from bugpilot.auth.client import activate, logout, whoami
from bugpilot.context import AppContext
from bugpilot.output.human import console, print_error, print_success
from bugpilot.output.json_out import print_json
from bugpilot.session import APIError

app = typer.Typer(help="Authentication commands")


def _get_ctx(typer_ctx: typer.Context) -> AppContext:
    return typer_ctx.obj


@app.command("activate")
def cmd_activate(
    ctx: typer.Context,
    license_key: Optional[str] = typer.Option(None, "--key", "-k", help="License key", envvar="BUGPILOT_LICENSE_KEY"),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Your email address"),
    display_name: Optional[str] = typer.Option(None, "--name", help="Your display name"),
) -> None:
    """Activate a BugPilot license and store credentials."""
    app_ctx = _get_ctx(ctx)

    if not license_key:
        license_key = Prompt.ask("[bold]Enter your license key[/bold]", password=True)
    if not email:
        email = Prompt.ask("[bold]Enter your email address[/bold]")

    async def _run():
        try:
            resp = await activate(app_ctx, license_key=license_key, email=email, display_name=display_name)
            if app_ctx.output_format == "json":
                print_json({"status": "activated", "org_id": resp["org_id"], "user_id": resp["user_id"], "role": resp["role"]})
            else:
                print_success(f"Activated successfully! Org: {resp['org_id']} | Role: {resp['role']}")
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
