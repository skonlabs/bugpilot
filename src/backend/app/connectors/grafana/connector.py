"""
Grafana connector for BugPilot.
Supports METRICS (via Prometheus datasource proxy) and ALERTS capabilities.
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
    ConnectorCapability.METRICS,
    ConnectorCapability.ALERTS,
]

_REQUEST_TIMEOUT = 30.0


def _to_epoch(dt: datetime) -> float:
    """Return Unix epoch seconds as float."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class GrafanaConnector(BaseConnector):
    """
    Connector for Grafana.

    Supports:
    - METRICS via GET /api/datasources/proxy/:uid/api/v1/query_range (Prometheus proxy)
    - ALERTS  via GET /api/v1/provisioning/alert-rules

    Notes:
    - Grafana's alert-rules endpoint does not filter by time range directly.
      The connector fetches all alert rules and annotates evidence with an
      adaptation note in the metadata field.
    - Metrics require a known Prometheus datasource UID. If none is configured,
      the connector falls back to listing datasources and using the first
      Prometheus type found.
    """

    def __init__(
        self,
        url: str,
        api_token: str,
        org_id: int = 1,
        prometheus_datasource_uid: Optional[str] = None,
    ) -> None:
        self._base_url = url.rstrip("/")
        self._api_token = api_token
        self._org_id = org_id
        self._prometheus_datasource_uid = prometheus_datasource_uid
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "X-Grafana-Org-Id": str(org_id),
        }

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[ConnectorCapability]:
        return list(_SUPPORTED_CAPABILITIES)

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        """Validate connectivity via GET /api/health."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/health",
                    headers=self._headers,
                )
            latency_ms = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return ValidationResult(is_valid=True, latency_ms=latency_ms)
            return ValidationResult(
                is_valid=False,
                error=f"Health check failed: HTTP {resp.status_code} - {resp.text[:200]}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            logger.error("grafana_validate_error", error=str(exc))
            return ValidationResult(is_valid=False, error=str(exc), latency_ms=latency_ms)

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        if capability == ConnectorCapability.METRICS:
            return await self._fetch_metrics(service, since, until, limit)
        elif capability == ConnectorCapability.ALERTS:
            return await self._fetch_alerts(service, since, until, limit)
        else:
            logger.warning("grafana_unsupported_capability", capability=capability.value)
            return []

    # ------------------------------------------------------------------
    # Private fetch methods
    # ------------------------------------------------------------------

    async def _resolve_prometheus_uid(self) -> Optional[str]:
        """Resolve a Prometheus datasource UID if not already configured."""
        if self._prometheus_datasource_uid:
            return self._prometheus_datasource_uid
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/datasources",
                    headers=self._headers,
                )
            if resp.status_code != 200:
                return None
            datasources = resp.json()
            for ds in datasources:
                if ds.get("type") in ("prometheus", "loki"):
                    uid = ds.get("uid")
                    logger.info("grafana_resolved_datasource_uid", uid=uid, type=ds.get("type"))
                    self._prometheus_datasource_uid = uid
                    return uid
        except Exception as exc:
            logger.warning("grafana_resolve_uid_error", error=str(exc))
        return None

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_metrics(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """
        Fetch metrics via Prometheus proxy at
        GET /api/datasources/proxy/:uid/api/v1/query_range.

        Adaptation note: Grafana proxies Prometheus query_range; the time range
        is passed as Unix epoch seconds (start/end), which Grafana respects fully.
        """
        uid = await self._resolve_prometheus_uid()
        if not uid:
            logger.warning(
                "grafana_no_prometheus_datasource",
                service=service,
            )
            return []

        query = f'{{service="{service}"}}'
        params = {
            "query": query,
            "start": _to_epoch(since),
            "end": _to_epoch(until),
            "step": "60s",
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/datasources/proxy/{uid}/api/v1/query_range",
                    headers=self._headers,
                    params=params,
                )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("data", {}).get("result", [])
            items: list[RawEvidenceItem] = []
            for series in result:
                metric_labels = series.get("metric", {})
                metric_name = metric_labels.get("__name__", "unknown")
                for ts_epoch, value in series.get("values", [])[:limit]:
                    ts = datetime.fromtimestamp(float(ts_epoch), tz=timezone.utc)
                    items.append(
                        RawEvidenceItem(
                            capability=ConnectorCapability.METRICS,
                            source_system="grafana",
                            service=service,
                            timestamp=ts,
                            payload={"metric": metric_name, "labels": metric_labels, "value": value},
                            message=f"{metric_name}={value}",
                            metadata={
                                "datasource_uid": uid,
                                "adaptation_note": (
                                    "Time range passed as Prometheus start/end epoch seconds "
                                    "via Grafana datasource proxy."
                                ),
                            },
                        )
                    )
            logger.info("grafana_metrics_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "grafana_metrics_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("grafana_metrics_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_alerts(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """
        Fetch alert rules via GET /api/v1/provisioning/alert-rules.

        Adaptation note: The Grafana provisioning API does not support time range
        filtering for alert rules. All active rules are returned and annotated
        with the adaptation note. Callers should apply their own time filtering
        based on the returned evidence timestamps if needed.
        """
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/provisioning/alert-rules",
                    headers=self._headers,
                )
            resp.raise_for_status()
            rules = resp.json()
            if isinstance(rules, dict):
                rules = rules.get("items", [rules])

            items: list[RawEvidenceItem] = []
            for rule in rules[:limit]:
                # Use 'updated' field when present; otherwise fall back to 'since'
                updated_str = rule.get("updated") or rule.get("created")
                if updated_str:
                    try:
                        ts = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        ts = since
                else:
                    ts = since

                # Best-effort service match via labels/annotations
                labels = rule.get("labels", {})
                annotations = rule.get("annotations", {})
                rule_service = labels.get("service") or annotations.get("service") or service

                # Filter to rules matching the requested service (or include all if no label)
                if rule_service != service and labels.get("service") is not None:
                    continue

                severity = labels.get("severity") or "unknown"
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.ALERTS,
                        source_system="grafana",
                        service=service,
                        timestamp=ts,
                        payload=rule,
                        severity=severity,
                        message=rule.get("title") or rule.get("name"),
                        raw_ref=str(rule.get("uid", rule.get("id", ""))),
                        metadata={
                            "adaptation_note": (
                                "Grafana provisioning alert-rules API does not support "
                                "time range filtering. All active rules are returned. "
                                "Apply time filtering on `timestamp` field as needed."
                            ),
                        },
                    )
                )
            logger.info("grafana_alerts_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "grafana_alerts_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("grafana_alerts_error", service=service, error=str(exc))
            return []


__all__ = ["GrafanaConnector"]
