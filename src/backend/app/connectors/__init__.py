"""
Connectors - integrations with external monitoring, logging, and ticketing systems.

Each connector implements the BaseConnector interface defined in base.py.
"""
from __future__ import annotations

from typing import Any, Dict

from .base import (
    BaseConnector,
    ConnectorCapability,
    ConnectorError,
    RawEvidenceItem,
    ValidationResult,
)
from .datadog.connector import DatadogConnector
from .grafana.connector import GrafanaConnector
from .cloudwatch.connector import CloudWatchConnector
from .github.connector import GitHubConnector
from .kubernetes.connector import KubernetesConnector
from .pagerduty.connector import PagerDutyConnector


def build_connector(kind: str, config: Dict[str, Any]) -> "BaseConnector":
    """Instantiate the correct connector from a kind string and config dict."""
    if kind == "datadog":
        return DatadogConnector(
            api_key=config["api_key"],
            app_key=config["app_key"],
            site=config.get("site", "datadoghq.com"),
        )
    if kind == "grafana":
        return GrafanaConnector(
            url=config["url"],
            api_token=config["api_token"],
            org_id=int(config.get("org_id", 1)),
            prometheus_datasource_uid=config.get("prometheus_datasource_uid"),
        )
    if kind == "cloudwatch":
        return CloudWatchConnector(
            aws_access_key_id=config["aws_access_key_id"],
            aws_secret_access_key=config["aws_secret_access_key"],
            region=config["region"],
        )
    if kind == "github":
        repos = config.get("repos") or []
        return GitHubConnector(
            token=config["token"],
            org=config.get("org"),
            repo=repos[0] if repos else None,
        )
    if kind == "kubernetes":
        return KubernetesConnector(
            api_server=config["api_server"],
            token=config["token"],
            namespace=config.get("namespace", "default"),
            ca_cert=config.get("ca_cert_path"),
        )
    if kind == "pagerduty":
        return PagerDutyConnector(
            api_key=config["api_key"],
            from_email=config["from_email"],
        )
    raise ValueError(f"Unknown connector kind: {kind!r}")


__all__ = [
    "BaseConnector",
    "ConnectorCapability",
    "ConnectorError",
    "RawEvidenceItem",
    "ValidationResult",
    "DatadogConnector",
    "GrafanaConnector",
    "CloudWatchConnector",
    "GitHubConnector",
    "KubernetesConnector",
    "PagerDutyConnector",
    "build_connector",
]
