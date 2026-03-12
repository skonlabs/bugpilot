"""Basic smoke tests — ensure the CLI loads and core modules import correctly."""
from typer.testing import CliRunner

from bugpilot.main import app


runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "bugpilot" in result.output.lower()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "bugpilot" in result.output


def test_auth_help():
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


def test_context_instantiation():
    from bugpilot.context import AppContext
    ctx = AppContext(api_url="http://localhost")
    assert ctx.api_url == "http://localhost"
