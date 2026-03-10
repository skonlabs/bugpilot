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
CONTEXT_FILE = CONFIG_DIR / "context.json"


def _default_api_url() -> str:
    return os.environ.get("BUGPILOT_API_URL", "https://api.bugpilot.io")


@dataclass
class AppContext:
    """Shared application context passed to all commands."""
    api_url: str = field(default_factory=_default_api_url)
    output_format: str = "human"  # "human" | "json" | "verbose"
    no_color: bool = False
    current_investigation_id: Optional[str] = field(default=None)
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

    def load_investigation_context(self) -> Optional[str]:
        """Load current investigation ID from disk. Returns None if not set."""
        if not CONTEXT_FILE.exists():
            return None
        try:
            import json
            data = json.loads(CONTEXT_FILE.read_text())
            return data.get("current_investigation_id")
        except Exception:
            return None

    def save_investigation_context(self, investigation_id: str) -> None:
        """Persist current investigation ID to disk."""
        import json
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONTEXT_FILE.write_text(
            json.dumps({"current_investigation_id": investigation_id}, indent=2)
        )
        CONTEXT_FILE.chmod(0o600)
        self.current_investigation_id = investigation_id

    def clear_investigation_context(self) -> None:
        """Remove current investigation ID from disk."""
        if CONTEXT_FILE.exists():
            CONTEXT_FILE.unlink()
        self.current_investigation_id = None

    def resolve_investigation_id(self, explicit_id: Optional[str] = None) -> Optional[str]:
        """Return the investigation ID to use: explicit flag > stored context."""
        if explicit_id:
            return explicit_id
        if self.current_investigation_id:
            return self.current_investigation_id
        return self.load_investigation_context()

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
