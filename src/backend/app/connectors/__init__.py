"""
Connectors - integrations with external monitoring, logging, and ticketing systems.

Each connector implements the BaseConnector interface defined in base.py.
"""
from __future__ import annotations

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
]
