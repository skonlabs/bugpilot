"""Tests for the evidence collector - concurrent collection with graceful degradation."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.base import (
    BaseConnector,
    ConnectorCapability,
    RawEvidenceItem,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Minimal EvidenceCollector implementation for testing
# ---------------------------------------------------------------------------
# This models the expected contract. Replace with actual import when module exists.


class CollectionResult:
    def __init__(
        self,
        connector_id: str,
        capability: ConnectorCapability,
        items: List[RawEvidenceItem],
        error: Optional[str] = None,
        degraded: bool = False,
    ):
        self.connector_id = connector_id
        self.capability = capability
        self.items = items
        self.error = error
        self.degraded = degraded


class EvidenceCollector:
    """
    Collects evidence from multiple connectors concurrently.
    Continues if one connector fails (degraded mode).
    Applies a per-connector timeout.
    """

    def __init__(
        self,
        connectors: dict,  # {connector_id: BaseConnector}
        timeout_seconds: float = 45.0,
    ):
        self.connectors = connectors
        self.timeout_seconds = timeout_seconds

    async def collect(
        self,
        service: str,
        since: datetime,
        until: datetime,
        capabilities: Optional[List[ConnectorCapability]] = None,
    ) -> List[CollectionResult]:
        """Collect evidence from all connectors concurrently."""
        tasks = []
        connector_keys = []

        for connector_id, connector in self.connectors.items():
            caps = capabilities or connector.capabilities()
            for cap in caps:
                if connector.supports(cap):
                    tasks.append(
                        self._collect_one(connector_id, connector, cap, service, since, until)
                    )
                    connector_keys.append((connector_id, cap))

        if not tasks:
            return []

        # Run all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    async def _collect_one(
        self,
        connector_id: str,
        connector: BaseConnector,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
    ) -> CollectionResult:
        """Collect evidence from a single connector with timeout protection."""
        try:
            items = await asyncio.wait_for(
                connector.fetch_evidence(capability, service, since, until),
                timeout=self.timeout_seconds,
            )
            return CollectionResult(
                connector_id=connector_id,
                capability=capability,
                items=items,
            )
        except asyncio.TimeoutError:
            return CollectionResult(
                connector_id=connector_id,
                capability=capability,
                items=[],
                error=f"Timeout after {self.timeout_seconds}s",
                degraded=True,
            )
        except Exception as exc:
            return CollectionResult(
                connector_id=connector_id,
                capability=capability,
                items=[],
                error=str(exc),
                degraded=True,
            )


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

SINCE = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
SERVICE = "payment-service"


def _make_raw_item(service: str = SERVICE, cap: ConnectorCapability = ConnectorCapability.LOGS) -> RawEvidenceItem:
    return RawEvidenceItem(
        capability=cap,
        source_system="test",
        service=service,
        timestamp=SINCE,
        payload={"message": "test"},
    )


class HealthyConnector(BaseConnector):
    def __init__(self, caps=None, items=None):
        self._caps = caps or [ConnectorCapability.LOGS, ConnectorCapability.METRICS]
        self._items = items if items is not None else [_make_raw_item()]

    def capabilities(self) -> list:
        return list(self._caps)

    async def validate(self) -> ValidationResult:
        return ValidationResult(is_valid=True, latency_ms=10.0)

    async def fetch_evidence(self, capability, service, since, until, limit=500):
        return list(self._items)


class FailingConnector(BaseConnector):
    def __init__(self, error_msg="Connection refused"):
        self._error_msg = error_msg

    def capabilities(self) -> list:
        return [ConnectorCapability.LOGS]

    async def validate(self) -> ValidationResult:
        return ValidationResult(is_valid=False, error=self._error_msg)

    async def fetch_evidence(self, capability, service, since, until, limit=500):
        raise RuntimeError(self._error_msg)


class TimeoutConnector(BaseConnector):
    def capabilities(self) -> list:
        return [ConnectorCapability.LOGS]

    async def validate(self) -> ValidationResult:
        return ValidationResult(is_valid=True)

    async def fetch_evidence(self, capability, service, since, until, limit=500):
        await asyncio.sleep(999)  # Simulate hanging connector


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_continues_if_one_connector_fails():
    """Collector returns results from healthy connectors even when one fails."""
    connectors = {
        "healthy": HealthyConnector(
            caps=[ConnectorCapability.LOGS],
            items=[_make_raw_item()],
        ),
        "failing": FailingConnector("DatadogConnector: 503 Service Unavailable"),
    }
    collector = EvidenceCollector(connectors, timeout_seconds=5.0)
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    # Should have 2 results (one healthy, one degraded)
    assert len(results) == 2

    healthy_results = [r for r in results if not r.degraded]
    degraded_results = [r for r in results if r.degraded]

    assert len(healthy_results) == 1
    assert len(degraded_results) == 1
    assert len(healthy_results[0].items) == 1


@pytest.mark.asyncio
async def test_degraded_connector_noted_in_metadata():
    """Degraded connector result has degraded=True and error message set."""
    connectors = {
        "broken": FailingConnector("Connection refused"),
    }
    collector = EvidenceCollector(connectors, timeout_seconds=5.0)
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    assert len(results) == 1
    result = results[0]
    assert result.degraded is True
    assert result.error is not None
    assert "Connection refused" in result.error
    assert result.items == []


@pytest.mark.asyncio
async def test_all_connectors_collected_concurrently():
    """Verify all connectors are invoked, not sequentially skipped."""
    call_log = []

    class TrackedConnector(BaseConnector):
        def __init__(self, connector_id: str):
            self.connector_id = connector_id

        def capabilities(self):
            return [ConnectorCapability.LOGS]

        async def validate(self):
            return ValidationResult(is_valid=True)

        async def fetch_evidence(self, capability, service, since, until, limit=500):
            call_log.append(self.connector_id)
            return [_make_raw_item()]

    connectors = {
        "connector-a": TrackedConnector("connector-a"),
        "connector-b": TrackedConnector("connector-b"),
        "connector-c": TrackedConnector("connector-c"),
    }
    collector = EvidenceCollector(connectors, timeout_seconds=5.0)
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    # All three should have been called
    assert len(results) == 3
    assert set(call_log) == {"connector-a", "connector-b", "connector-c"}


@pytest.mark.asyncio
async def test_timeout_guarded_per_connector():
    """Connector that hangs is terminated after timeout and marked degraded."""
    connectors = {
        "hanging": TimeoutConnector(),
    }
    collector = EvidenceCollector(connectors, timeout_seconds=0.1)  # Very short timeout
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    assert len(results) == 1
    result = results[0]
    assert result.degraded is True
    assert "Timeout" in result.error or "timeout" in result.error.lower()
    assert result.items == []


@pytest.mark.asyncio
async def test_empty_connectors_returns_empty_list():
    """Collector with no connectors returns an empty list."""
    collector = EvidenceCollector({}, timeout_seconds=5.0)
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])
    assert results == []


@pytest.mark.asyncio
async def test_healthy_connector_with_no_items():
    """Connector that returns empty list is not degraded."""
    connectors = {
        "empty": HealthyConnector(caps=[ConnectorCapability.LOGS], items=[]),
    }
    collector = EvidenceCollector(connectors, timeout_seconds=5.0)
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    assert len(results) == 1
    assert results[0].degraded is False
    assert results[0].items == []
    assert results[0].error is None


@pytest.mark.asyncio
async def test_mixed_connectors_all_results_returned():
    """Mix of healthy, failing, and timeout connectors all produce results."""
    connectors = {
        "healthy": HealthyConnector(
            caps=[ConnectorCapability.LOGS],
            items=[_make_raw_item(), _make_raw_item()],
        ),
        "failing": FailingConnector("500 Internal Server Error"),
        "timeout": TimeoutConnector(),
    }
    collector = EvidenceCollector(connectors, timeout_seconds=0.1)
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    assert len(results) == 3

    # Count healthy vs degraded
    healthy = [r for r in results if not r.degraded]
    degraded = [r for r in results if r.degraded]

    assert len(healthy) == 1
    assert len(degraded) == 2
    assert len(healthy[0].items) == 2


@pytest.mark.asyncio
async def test_unsupported_capability_skipped():
    """Connectors are not called for capabilities they don't support."""
    call_log = []

    class MetricsOnlyConnector(BaseConnector):
        def capabilities(self):
            return [ConnectorCapability.METRICS]

        async def validate(self):
            return ValidationResult(is_valid=True)

        async def fetch_evidence(self, capability, service, since, until, limit=500):
            call_log.append(capability)
            return []

    connectors = {"metrics-only": MetricsOnlyConnector()}
    collector = EvidenceCollector(connectors, timeout_seconds=5.0)

    # Request LOGS only - should not call connector
    results = await collector.collect(SERVICE, SINCE, UNTIL, [ConnectorCapability.LOGS])

    assert len(results) == 0
    assert call_log == []
