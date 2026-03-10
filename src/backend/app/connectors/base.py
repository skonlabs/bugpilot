"""
Base connector interface for BugPilot connectors.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ConnectorCapability(str, Enum):
    LOGS = "logs"
    METRICS = "metrics"
    TRACES = "traces"
    ALERTS = "alerts"
    INCIDENTS = "incidents"
    DEPLOYMENTS = "deployments"
    CODE_CHANGES = "code_changes"
    INFRASTRUCTURE_STATE = "infrastructure_state"


@dataclass
class RawEvidenceItem:
    capability: ConnectorCapability
    source_system: str
    service: str
    timestamp: datetime
    payload: dict[str, Any]
    severity: Optional[str] = None
    message: Optional[str] = None
    raw_ref: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    is_valid: bool
    error: Optional[str] = None
    latency_ms: Optional[float] = None


@dataclass
class ConnectorError:
    connector: str
    capability: ConnectorCapability
    error_type: str
    message: str
    retryable: bool = True


class BaseConnector(ABC):
    """Abstract base class for all BugPilot connectors."""

    @abstractmethod
    def capabilities(self) -> list[ConnectorCapability]:
        """Return list of supported capabilities."""
        ...

    @abstractmethod
    async def validate(self) -> ValidationResult:
        """Validate the connector configuration and connectivity."""
        ...

    @abstractmethod
    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        """Fetch evidence for a service in a time window."""
        ...

    def unsupported_capabilities(self) -> list[ConnectorCapability]:
        all_caps = set(ConnectorCapability)
        supported = set(self.capabilities())
        return list(all_caps - supported)

    def supports(self, capability: ConnectorCapability) -> bool:
        return capability in self.capabilities()


__all__ = [
    "BaseConnector",
    "ConnectorCapability",
    "RawEvidenceItem",
    "ValidationResult",
    "ConnectorError",
]
