"""
Datadog connector for BugPilot.
Supports LOGS, METRICS, TRACES, and ALERTS capabilities.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

from app.connectors.base import (
    BaseConnector,
    ConnectorCapability,
    RawEvidenceItem,
    ValidationResult,
)
from app.connectors.retry import async_retry

logger = structlog.get_logger(__name__)

_SUPPORTED_CAPABILITIES = [
    ConnectorCapability.LOGS,
    ConnectorCapability.METRICS,
    ConnectorCapability.TRACES,
    ConnectorCapability.ALERTS,
]

_REQUEST_TIMEOUT = 30.0


def _to_epoch(dt: datetime) -> int:
    """Convert a datetime to a Unix epoch integer."""
    return int(dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp())


def _to_iso8601(dt: datetime) -> str:
    """Return ISO-8601 string with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class DatadogConnector(BaseConnector):
    """
    Connector for the Datadog observability platform.

    Supports:
    - LOGS   via POST /api/v2/logs/events/search
    - METRICS via GET  /api/v1/query
    - TRACES  via GET  /api/v2/spans/events
    - ALERTS  via GET  /api/v1/monitor (filtered by service tag)
    """

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
    ) -> None:
        self._api_key = api_key
        self._app_key = app_key
        self._base_url = f"https://api.{site}"
        self._headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[ConnectorCapability]:
        return list(_SUPPORTED_CAPABILITIES)

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        """Validate API credentials via GET /api/v1/validate."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/validate",
                    headers=self._headers,
                )
            latency_ms = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return ValidationResult(is_valid=True, latency_ms=latency_ms)
            return ValidationResult(
                is_valid=False,
                error=f"Validation failed: HTTP {resp.status_code} - {resp.text[:200]}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            logger.error("datadog_validate_error", error=str(exc))
            return ValidationResult(is_valid=False, error=str(exc), latency_ms=latency_ms)

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        """Dispatch fetch to the appropriate method based on capability."""
        if capability == ConnectorCapability.LOGS:
            return await self._fetch_logs(service, since, until, limit)
        elif capability == ConnectorCapability.METRICS:
            return await self._fetch_metrics(service, since, until, limit)
        elif capability == ConnectorCapability.TRACES:
            return await self._fetch_traces(service, since, until, limit)
        elif capability == ConnectorCapability.ALERTS:
            return await self._fetch_alerts(service, since, until, limit)
        else:
            logger.warning(
                "datadog_unsupported_capability",
                capability=capability.value,
            )
            return []

    # ------------------------------------------------------------------
    # Private fetch methods
    # ------------------------------------------------------------------

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_logs(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch logs via POST /api/v2/logs/events/search."""
        body = {
            "filter": {
                "query": f"service:{service}",
                "from": _to_iso8601(since),
                "to": _to_iso8601(until),
                "indexes": ["*"],
            },
            "sort": "timestamp",
            "page": {"limit": min(limit, 1000)},
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/api/v2/logs/events/search",
                    headers=self._headers,
                    json=body,
                )
            resp.raise_for_status()
            data = resp.json()
            items: list[RawEvidenceItem] = []
            for log in data.get("data", []):
                attrs = log.get("attributes", {})
                ts_str = attrs.get("timestamp") or attrs.get("@timestamp") or since.isoformat()
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.LOGS,
                        source_system="datadog",
                        service=service,
                        timestamp=ts,
                        payload=log,
                        severity=attrs.get("status"),
                        message=attrs.get("message"),
                        raw_ref=log.get("id"),
                    )
                )
            logger.info("datadog_logs_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "datadog_logs_http_error",
                service=service,
                status=exc.response.status_code,
                body=exc.response.text[:200],
            )
            raise
        except Exception as exc:
            logger.error("datadog_logs_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_metrics(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch metrics via GET /api/v1/query."""
        params = {
            "from": _to_epoch(since),
            "to": _to_epoch(until),
            "query": f"avg:system.cpu.user{{service:{service}}}",
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/query",
                    headers=self._headers,
                    params=params,
                )
            resp.raise_for_status()
            data = resp.json()
            items: list[RawEvidenceItem] = []
            for series in data.get("series", []):
                metric_name = series.get("metric", "unknown")
                for point in series.get("pointlist", [])[:limit]:
                    epoch_ms, value = point[0], point[1]
                    ts = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
                    items.append(
                        RawEvidenceItem(
                            capability=ConnectorCapability.METRICS,
                            source_system="datadog",
                            service=service,
                            timestamp=ts,
                            payload={"metric": metric_name, "value": value, "series": series},
                            message=f"{metric_name}={value}",
                        )
                    )
            logger.info("datadog_metrics_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "datadog_metrics_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("datadog_metrics_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_traces(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch traces via GET /api/v2/spans/events."""
        params = {
            "filter[query]": f"service:{service}",
            "filter[from]": _to_iso8601(since),
            "filter[to]": _to_iso8601(until),
            "page[limit]": min(limit, 1000),
            "sort": "timestamp",
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v2/spans/events",
                    headers=self._headers,
                    params=params,
                )
            resp.raise_for_status()
            data = resp.json()
            items: list[RawEvidenceItem] = []
            for span in data.get("data", []):
                attrs = span.get("attributes", {})
                ts_str = attrs.get("timestamp") or since.isoformat()
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.TRACES,
                        source_system="datadog",
                        service=service,
                        timestamp=ts,
                        payload=span,
                        raw_ref=span.get("id"),
                        message=f"span:{attrs.get('resource_name', '')}",
                    )
                )
            logger.info("datadog_traces_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "datadog_traces_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("datadog_traces_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_alerts(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch monitors/alerts via GET /api/v1/monitor (filtered by service tag)."""
        params = {
            "monitor_tags": f"service:{service}",
            "with_downtimes": "false",
            "page_size": min(limit, 1000),
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/monitor",
                    headers=self._headers,
                    params=params,
                )
            resp.raise_for_status()
            monitors = resp.json()
            items: list[RawEvidenceItem] = []
            since_ts = _to_epoch(since)
            until_ts = _to_epoch(until)
            for monitor in monitors:
                # Filter by state changed time if available
                overall_state_modified = monitor.get("overall_state_modified")
                if overall_state_modified is not None:
                    try:
                        mod_ts = int(overall_state_modified)
                        if mod_ts < since_ts or mod_ts > until_ts:
                            continue
                    except (ValueError, TypeError):
                        pass

                ts_epoch = overall_state_modified or _to_epoch(since)
                try:
                    ts = datetime.fromtimestamp(float(ts_epoch), tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    ts = since

                severity = _datadog_monitor_severity(monitor.get("overall_state", ""))
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.ALERTS,
                        source_system="datadog",
                        service=service,
                        timestamp=ts,
                        payload=monitor,
                        severity=severity,
                        message=monitor.get("name"),
                        raw_ref=str(monitor.get("id", "")),
                    )
                )
            logger.info("datadog_alerts_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "datadog_alerts_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("datadog_alerts_error", service=service, error=str(exc))
            return []


def _datadog_monitor_severity(state: str) -> str:
    """Map Datadog monitor state to a normalized severity string."""
    mapping = {
        "Alert": "critical",
        "Warn": "warning",
        "No Data": "unknown",
        "OK": "ok",
        "Ignored": "info",
        "Skipped": "info",
        "Triggered": "critical",
    }
    return mapping.get(state, "unknown")


__all__ = ["DatadogConnector"]
