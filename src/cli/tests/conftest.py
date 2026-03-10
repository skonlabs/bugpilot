"""
CLI test configuration and fixtures.
"""
import pytest
import respx
import httpx

from bugpilot.context import AppContext


@pytest.fixture
def app_ctx(tmp_path, monkeypatch) -> AppContext:
    """Provide an AppContext with isolated config directory."""
    monkeypatch.setenv("BUGPILOT_API_URL", "http://test-api")
    # Redirect credentials to temp dir
    import bugpilot.context as ctx_module
    monkeypatch.setattr(ctx_module, "CONFIG_DIR", tmp_path / ".config" / "bugpilot")
    monkeypatch.setattr(ctx_module, "CREDENTIALS_FILE", tmp_path / ".config" / "bugpilot" / "credentials.json")
    return AppContext(api_url="http://test-api")


@pytest.fixture
def mock_api():
    """Provide a respx mock for API calls."""
    with respx.mock(base_url="http://test-api", assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def authenticated_ctx(app_ctx: AppContext, tmp_path, monkeypatch) -> AppContext:
    """AppContext with pre-loaded credentials."""
    import bugpilot.context as ctx_module
    cred_file = tmp_path / ".config" / "bugpilot" / "credentials.json"
    cred_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ctx_module, "CREDENTIALS_FILE", cred_file)

    app_ctx.save_credentials(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        org_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
    )
    app_ctx.load_credentials()
    return app_ctx
