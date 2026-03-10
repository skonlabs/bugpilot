"""
CLI application context - holds config, API client, and output formatter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx


CONFIG_DIR = Path.home() / ".config" / "bugpilot"
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def _default_api_url() -> str:
    return os.environ.get("BUGPILOT_API_URL", "http://localhost:8000")


@dataclass
class AppContext:
    """Shared application context passed to all commands."""
    api_url: str = field(default_factory=_default_api_url)
    output_format: str = "human"  # "human" | "json" | "verbose"
    no_color: bool = False
    _access_token: Optional[str] = field(default=None, repr=False)
    _refresh_token: Optional[str] = field(default=None, repr=False)
    _org_id: Optional[str] = field(default=None, repr=False)
    _user_id: Optional[str] = field(default=None, repr=False)

    def load_credentials(self) -> bool:
        """Load credentials from disk. Returns True if successful."""
        if not CREDENTIALS_FILE.exists():
            return False
        try:
            import json
            data = json.loads(CREDENTIALS_FILE.read_text())
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            self._org_id = data.get("org_id")
            self._user_id = data.get("user_id")
            return bool(self._access_token)
        except Exception:
            return False

    def save_credentials(
        self,
        access_token: str,
        refresh_token: str,
        org_id: str,
        user_id: str,
    ) -> None:
        """Persist credentials to disk."""
        import json
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(
            json.dumps(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "org_id": org_id,
                    "user_id": user_id,
                },
                indent=2,
            )
        )
        CREDENTIALS_FILE.chmod(0o600)

    def clear_credentials(self) -> None:
        """Remove credentials from disk."""
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
        self._access_token = None
        self._refresh_token = None
        self._org_id = None
        self._user_id = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self._access_token)

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    @property
    def org_id(self) -> Optional[str]:
        return self._org_id

    @property
    def user_id(self) -> Optional[str]:
        return self._user_id

    def make_client(self) -> httpx.AsyncClient:
        headers = {"User-Agent": "bugpilot-cli/0.1.0"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return httpx.AsyncClient(
            base_url=self.api_url,
            headers=headers,
            timeout=30.0,
        )
