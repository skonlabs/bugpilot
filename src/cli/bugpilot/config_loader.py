"""
BugPilot config file loader.

Reads ~/.config/bugpilot/config.yaml and exposes connector / webhook settings.
Supports ${VAR_NAME} substitution from environment variables.

Connector config format (named — supports multiple instances of the same type):

    connectors:
      grafana-prod:
        kind: grafana
        url: https://grafana.prod.example.com
        api_token: ${GRAFANA_PROD_TOKEN}
      grafana-staging:
        kind: grafana
        url: https://grafana.staging.example.com
        api_token: ${GRAFANA_STAGING_TOKEN}

Backward-compatible: old configs where the key equals the connector type
(e.g. "grafana:") and no explicit "kind:" field are loaded transparently.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Shared with context.py
CONFIG_DIR = Path.home() / ".config" / "bugpilot"
CONFIG_YAML = CONFIG_DIR / "config.yaml"
TOS_FILE = CONFIG_DIR / "tos_accepted"

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")

# Required / optional fields for each connector type, in prompt order.
CONNECTOR_FIELDS: Dict[str, List[Dict[str, Any]]] = {
    "datadog": [
        {"key": "api_key",  "label": "API Key",                         "secret": True},
        {"key": "app_key",  "label": "Application Key",                 "secret": True},
        {"key": "site",     "label": "Site (e.g. datadoghq.com)",       "secret": False, "default": "datadoghq.com"},
    ],
    "grafana": [
        {"key": "url",       "label": "Grafana URL (https://…)",         "secret": False},
        {"key": "api_token", "label": "Service Account Token",           "secret": True},
        {"key": "org_id",    "label": "Org ID",                          "secret": False, "default": "1"},
        {"key": "prometheus_datasource_uid",
                             "label": "Prometheus datasource UID (optional)",
                                                                          "secret": False, "optional": True},
    ],
    "cloudwatch": [
        {"key": "aws_access_key_id",     "label": "AWS Access Key ID",      "secret": False},
        {"key": "aws_secret_access_key", "label": "AWS Secret Access Key",   "secret": True},
        {"key": "region",                "label": "AWS Region (e.g. us-east-1)", "secret": False},
        {"key": "log_group_names",       "label": "Log group names, comma-separated (optional)",
                                                                              "secret": False, "optional": True, "list_field": True},
    ],
    "github": [
        {"key": "token", "label": "Personal Access Token or GitHub App Token", "secret": True},
        {"key": "org",   "label": "GitHub Organisation name",                  "secret": False},
        {"key": "repos", "label": "Repository names, comma-separated (optional)",
                                                                                "secret": False, "optional": True, "list_field": True},
    ],
    "kubernetes": [
        {"key": "api_server", "label": "API Server URL (https://k8s.example.com:6443)", "secret": False},
        {"key": "token",      "label": "Service Account Bearer Token",                  "secret": True},
        {"key": "namespace",  "label": "Primary namespace",                             "secret": False, "default": "production"},
        {"key": "extra_namespaces", "label": "Extra namespaces, comma-separated (optional)",
                                                                                          "secret": False, "optional": True, "list_field": True},
        {"key": "ca_cert_path", "label": "CA certificate path (optional)",              "secret": False, "optional": True},
    ],
    "pagerduty": [
        {"key": "api_key",     "label": "REST API Key",                           "secret": True},
        {"key": "from_email",  "label": "From email address",                     "secret": False},
        {"key": "service_ids", "label": "Service IDs, comma-separated (optional)", "secret": False, "optional": True, "list_field": True},
    ],
}

CONNECTOR_TYPES = list(CONNECTOR_FIELDS.keys())


def _substitute_env_vars(value: Any) -> Any:
    """Recursively substitute ${VAR} patterns with environment variable values."""
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            return os.environ.get(m.group(1), "")
        return _ENV_VAR_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env_vars(i) for i in value]
    return value


@dataclass
class ConnectorEntry:
    name: str
    kind: str
    config: Dict[str, Any]

    def masked(self) -> Dict[str, Any]:
        """Return config with secret fields replaced by ****."""
        secret_keys = {
            "api_key", "app_key", "api_token", "token",
            "aws_secret_access_key", "webhook_secret", "secret", "password",
        }
        return {
            k: ("****" if k in secret_keys and v else v)
            for k, v in self.config.items()
        }


@dataclass
class BugPilotConfig:
    # Keyed by connector name (user-defined), not by kind.
    connectors: Dict[str, ConnectorEntry] = field(default_factory=dict)
    webhooks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    global_settings: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "BugPilotConfig":
        """Load the YAML config file. Returns an empty config if the file does not exist."""
        if not CONFIG_YAML.exists():
            return cls()
        try:
            import yaml
        except ImportError:
            raise RuntimeError("PyYAML is required. Run: pip install pyyaml")

        raw = yaml.safe_load(CONFIG_YAML.read_text()) or {}
        raw = _substitute_env_vars(raw)

        connectors: Dict[str, ConnectorEntry] = {}
        for name, cfg in (raw.get("connectors") or {}).items():
            cfg = cfg or {}
            # Explicit "kind:" field takes precedence.
            # Backward compat: if missing and the key matches a known type, use the key.
            kind = cfg.pop("kind", None)
            if kind is None:
                if name in CONNECTOR_FIELDS:
                    kind = name
                else:
                    # Unknown name with no kind field — skip with warning handled at validate()
                    kind = name
            connectors[name] = ConnectorEntry(name=name, kind=kind, config=cfg)

        return cls(
            connectors=connectors,
            webhooks=raw.get("webhooks") or {},
            global_settings=raw.get("global") or {},
        )

    def save(self) -> None:
        """Write the current config back to disk (permissions 600)."""
        try:
            import yaml
        except ImportError:
            raise RuntimeError("PyYAML is required. Run: pip install pyyaml")

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if self.connectors:
            out: Dict[str, Any] = {}
            for name, entry in self.connectors.items():
                # Always write kind: explicitly so the file is unambiguous.
                out[name] = {"kind": entry.kind, **entry.config}
            data["connectors"] = out
        if self.webhooks:
            data["webhooks"] = self.webhooks
        if self.global_settings:
            data["global"] = self.global_settings

        CONFIG_YAML.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True)
        )
        CONFIG_YAML.chmod(0o600)

    def validate(self) -> List[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: List[str] = []
        for name, entry in self.connectors.items():
            if entry.kind not in CONNECTOR_FIELDS:
                errors.append(f"{name}: unknown connector type '{entry.kind}'")
                continue
            for fdef in CONNECTOR_FIELDS[entry.kind]:
                if fdef.get("optional"):
                    continue
                if not entry.config.get(fdef["key"]):
                    errors.append(f"{name}.{fdef['key']}: required field is missing or empty")
        return errors
