"""Tests for connector implementations."""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from app.connectors.base import ConnectorCapability, ValidationResult
from app.connectors.datadog.connector import DatadogConnector
from app.connectors.grafana.connector import GrafanaConnector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SINCE = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
SERVICE = "payment-service"

DD_API_KEY = "test-dd-api-key"
DD_APP_KEY = "test-dd-app-key"
DD_SITE = "datadoghq.com"
DD_BASE = f"https://api.{DD_SITE}"

GRAFANA_URL = "https://grafana.example.com"
GRAFANA_TOKEN = "glsa_test_token"


# ---------------------------------------------------------------------------
# DatadogConnector tests
# ---------------------------------------------------------------------------


class TestDatadogConnectorCapabilities:
    def test_returns_correct_capabilities(self):
        """DatadogConnector supports LOGS, METRICS, TRACES, ALERTS."""
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        caps = connector.capabilities()
        assert ConnectorCapability.LOGS in caps
        assert ConnectorCapability.METRICS in caps
        assert ConnectorCapability.TRACES in caps
        assert ConnectorCapability.ALERTS in caps

    def test_does_not_support_incidents(self):
        """DatadogConnector does not claim INCIDENTS capability."""
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        assert ConnectorCapability.INCIDENTS not in connector.capabilities()

    def test_supports_method(self):
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        assert connector.supports(ConnectorCapability.LOGS)
        assert not connector.supports(ConnectorCapability.INCIDENTS)


class TestDatadogConnectorValidate:
    @respx.mock
    @pytest.mark.asyncio
    async def test_validate_success(self):
        """Validate returns is_valid=True on 200."""
        respx.get(f"{DD_BASE}/api/v1/validate").respond(200, json={"valid": True})
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        result = await connector.validate()
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.latency_ms is not None

    @respx.mock
    @pytest.mark.asyncio
    async def test_validate_failure_403(self):
        """Validate returns is_valid=False on 403."""
        respx.get(f"{DD_BASE}/api/v1/validate").respond(403, json={"errors": ["Forbidden"]})
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        result = await connector.validate()
        assert result.is_valid is False
        assert "403" in str(result.error)


class TestDatadogConnectorRateLimit:
    @respx.mock
    @pytest.mark.asyncio
    async def test_handles_429_with_retry_after(self):
        """DatadogConnector handles 429 with Retry-After header."""
        call_count = 0

        def respond(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"errors": ["Rate limit exceeded"]},
                )
            return httpx.Response(200, json={"data": []})

        respx.post(f"{DD_BASE}/api/v2/logs/events/search").mock(side_effect=respond)
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)

        # Patch asyncio.sleep to avoid actual waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            items = await connector.fetch_evidence(
                ConnectorCapability.LOGS, SERVICE, SINCE, UNTIL
            )
        assert isinstance(items, list)
        assert call_count >= 2  # retried at least once


class TestDatadogConnectorTimeout:
    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        """DatadogConnector handles timeout - eventually raises or returns empty."""
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)

        with respx.mock:
            respx.post(f"{DD_BASE}/api/v2/logs/events/search").mock(
                side_effect=httpx.TimeoutException("timed out")
            )
            # The connector catches generic exceptions and returns []
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await connector.fetch_evidence(
                    ConnectorCapability.LOGS, SERVICE, SINCE, UNTIL
                )
        # Connector should not raise; returns empty list on exhausted retries
        assert isinstance(result, list)


class TestDatadogConnectorUnsupportedCapability:
    @pytest.mark.asyncio
    async def test_unsupported_capability_returns_empty_list(self):
        """Fetching an unsupported capability returns [] not an exception."""
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        result = await connector.fetch_evidence(
            ConnectorCapability.INCIDENTS, SERVICE, SINCE, UNTIL
        )
        assert result == []


class TestDatadogConnectorFetchLogs:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_logs_parses_correctly(self):
        """Fetch logs returns correctly parsed RawEvidenceItem list."""
        response_data = {
            "data": [
                {
                    "id": "log-001",
                    "attributes": {
                        "timestamp": "2024-01-15T14:30:00Z",
                        "status": "error",
                        "message": "NullPointerException in PaymentService",
                        "service": "payment-service",
                    },
                }
            ]
        }
        respx.post(f"{DD_BASE}/api/v2/logs/events/search").respond(200, json=response_data)
        connector = DatadogConnector(DD_API_KEY, DD_APP_KEY, DD_SITE)
        items = await connector.fetch_evidence(ConnectorCapability.LOGS, SERVICE, SINCE, UNTIL)
        assert len(items) == 1
        assert items[0].capability == ConnectorCapability.LOGS
        assert items[0].source_system == "datadog"
        assert items[0].message == "NullPointerException in PaymentService"
        assert items[0].severity == "error"


# ---------------------------------------------------------------------------
# GrafanaConnector tests
# ---------------------------------------------------------------------------


class TestGrafanaConnectorCapabilities:
    def test_returns_correct_capabilities(self):
        """GrafanaConnector supports METRICS and ALERTS only."""
        connector = GrafanaConnector(GRAFANA_URL, GRAFANA_TOKEN)
        caps = connector.capabilities()
        assert ConnectorCapability.METRICS in caps
        assert ConnectorCapability.ALERTS in caps
        assert ConnectorCapability.LOGS not in caps
        assert ConnectorCapability.TRACES not in caps

    def test_unsupported_capability_returns_empty(self):
        connector = GrafanaConnector(GRAFANA_URL, GRAFANA_TOKEN)
        # Logs is not supported by Grafana connector
        assert not connector.supports(ConnectorCapability.LOGS)


class TestGrafanaConnectorValidate:
    @respx.mock
    @pytest.mark.asyncio
    async def test_validate_success(self):
        respx.get(f"{GRAFANA_URL}/api/health").respond(200, json={"database": "ok"})
        connector = GrafanaConnector(GRAFANA_URL, GRAFANA_TOKEN)
        result = await connector.validate()
        assert result.is_valid is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_validate_failure(self):
        respx.get(f"{GRAFANA_URL}/api/health").respond(503, json={"message": "down"})
        connector = GrafanaConnector(GRAFANA_URL, GRAFANA_TOKEN)
        result = await connector.validate()
        assert result.is_valid is False


class TestGrafanaConnectorFetchAlerts:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_alerts_returns_items(self):
        """GrafanaConnector fetches alert rules and wraps them as evidence."""
        rules = [
            {
                "uid": "rule-001",
                "title": "High error rate",
                "updated": "2024-01-15T14:00:00Z",
                "labels": {"severity": "critical", "service": SERVICE},
                "annotations": {},
            }
        ]
        respx.get(f"{GRAFANA_URL}/api/v1/provisioning/alert-rules").respond(200, json=rules)
        connector = GrafanaConnector(GRAFANA_URL, GRAFANA_TOKEN)
        items = await connector.fetch_evidence(ConnectorCapability.ALERTS, SERVICE, SINCE, UNTIL)
        assert len(items) >= 1
        assert items[0].capability == ConnectorCapability.ALERTS
        assert items[0].source_system == "grafana"

    @respx.mock
    @pytest.mark.asyncio
    async def test_unsupported_capability_returns_empty(self):
        """Grafana connector returns [] for unsupported capabilities."""
        connector = GrafanaConnector(GRAFANA_URL, GRAFANA_TOKEN)
        result = await connector.fetch_evidence(
            ConnectorCapability.LOGS, SERVICE, SINCE, UNTIL
        )
        assert result == []


# ---------------------------------------------------------------------------
# Validation result tests
# ---------------------------------------------------------------------------


def test_validation_result_valid():
    result = ValidationResult(is_valid=True, latency_ms=42.0)
    assert result.is_valid
    assert result.error is None
    assert result.latency_ms == 42.0


def test_validation_result_invalid():
    result = ValidationResult(is_valid=False, error="Connection refused", latency_ms=5000.0)
    assert not result.is_valid
    assert "Connection refused" in result.error
