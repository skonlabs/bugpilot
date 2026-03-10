"""
PagerDuty connector for BugPilot.
Supports INCIDENTS and ALERTS capabilities.
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
    ConnectorCapability.INCIDENTS,
    ConnectorCapability.ALERTS,
]

_REQUEST_TIMEOUT = 30.0
_PD_API_BASE = "https://api.pagerduty.com"
_MAX_PAGES = 20
_PAGE_SIZE = 100


def _to_iso8601(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class PagerDutyConnector(BaseConnector):
    """
    Connector for the PagerDuty platform.

    Supports:
    - INCIDENTS via GET /incidents with since/until filter
    - ALERTS    via GET /alerts (filtered by incident IDs collected first)
    """

    def __init__(self, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._headers = {
            "Authorization": f"Token token={api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "From": from_email,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[ConnectorCapability]:
        return list(_SUPPORTED_CAPABILITIES)

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        """Validate credentials via GET /users/me."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{_PD_API_BASE}/users/me",
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
            logger.error("pagerduty_validate_error", error=str(exc))
            return ValidationResult(is_valid=False, error=str(exc), latency_ms=latency_ms)

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        if capability == ConnectorCapability.INCIDENTS:
            return await self._fetch_incidents(service, since, until, limit)
        elif capability == ConnectorCapability.ALERTS:
            return await self._fetch_alerts(service, since, until, limit)
        else:
            logger.warning("pagerduty_unsupported_capability", capability=capability.value)
            return []

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    async def _paginated_get(
        self,
        path: str,
        params: dict[str, Any],
        item_key: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Fetch all pages from a PagerDuty offset-paginated endpoint.
        PagerDuty uses offset + limit pagination with a 'more' boolean.
        """
        results: list[dict[str, Any]] = []
        offset = 0
        page_count = 0

        while len(results) < limit and page_count < _MAX_PAGES:
            page_params = {**params, "limit": _PAGE_SIZE, "offset": offset}
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    f"{_PD_API_BASE}{path}",
                    headers=self._headers,
                    params=page_params,
                )
            resp.raise_for_status()
            data = resp.json()
            page_items = data.get(item_key, [])
            results.extend(page_items)
            if not data.get("more", False) or not page_items:
                break
            offset += len(page_items)
            page_count += 1

        return results[:limit]

    # ------------------------------------------------------------------
    # Private fetch methods
    # ------------------------------------------------------------------

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_incidents(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch incidents via GET /incidents with since/until filter."""
        params: dict[str, Any] = {
            "since": _to_iso8601(since),
            "until": _to_iso8601(until),
            "statuses[]": ["triggered", "acknowledged", "resolved"],
            "sort_by": "created_at:desc",
        }
        try:
            incidents = await self._paginated_get(
                "/incidents", params, "incidents", limit
            )
            items: list[RawEvidenceItem] = []
            for incident in incidents:
                created_at_str = incident.get("created_at", "")
                try:
                    ts = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since

                status = incident.get("status", "unknown")
                urgency = incident.get("urgency", "low")
                severity = _pd_severity(urgency, status)

                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.INCIDENTS,
                        source_system="pagerduty",
                        service=service,
                        timestamp=ts,
                        payload=incident,
                        severity=severity,
                        message=incident.get("title") or incident.get("summary"),
                        raw_ref=incident.get("id"),
                        metadata={
                            "status": status,
                            "urgency": urgency,
                            "incident_number": incident.get("incident_number"),
                            "html_url": incident.get("html_url"),
                        },
                    )
                )
            logger.info("pagerduty_incidents_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pagerduty_incidents_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("pagerduty_incidents_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_alerts(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """
        Fetch alerts via GET /alerts (requires incident IDs).

        Strategy:
        1. Fetch incidents in the time window to get incident IDs.
        2. Fetch alerts for those incident IDs (PagerDuty alerts are always
           associated with incidents).
        """
        try:
            # First get relevant incident IDs
            incident_params: dict[str, Any] = {
                "since": _to_iso8601(since),
                "until": _to_iso8601(until),
                "statuses[]": ["triggered", "acknowledged", "resolved"],
            }
            incidents = await self._paginated_get(
                "/incidents", incident_params, "incidents", min(limit, 100)
            )
            incident_ids = [inc["id"] for inc in incidents if inc.get("id")]

            if not incident_ids:
                logger.info("pagerduty_no_incidents_for_alerts", service=service)
                return []

            items: list[RawEvidenceItem] = []
            # Fetch alerts for each incident (batch up to 10 incident IDs)
            for batch_start in range(0, len(incident_ids), 10):
                batch = incident_ids[batch_start : batch_start + 10]
                for inc_id in batch:
                    try:
                        alerts = await self._paginated_get(
                            f"/incidents/{inc_id}/alerts",
                            {},
                            "alerts",
                            50,
                        )
                        for alert in alerts:
                            created_at_str = alert.get("created_at", "")
                            try:
                                ts = datetime.fromisoformat(
                                    created_at_str.replace("Z", "+00:00")
                                )
                            except (ValueError, AttributeError):
                                ts = since

                            status = alert.get("status", "unknown")
                            severity = alert.get("severity") or "unknown"

                            items.append(
                                RawEvidenceItem(
                                    capability=ConnectorCapability.ALERTS,
                                    source_system="pagerduty",
                                    service=service,
                                    timestamp=ts,
                                    payload=alert,
                                    severity=severity,
                                    message=alert.get("summary"),
                                    raw_ref=alert.get("id"),
                                    metadata={
                                        "status": status,
                                        "incident_id": inc_id,
                                        "html_url": alert.get("html_url"),
                                    },
                                )
                            )
                    except Exception as exc:
                        logger.warning(
                            "pagerduty_alerts_incident_error",
                            incident_id=inc_id,
                            error=str(exc),
                        )

                if len(items) >= limit:
                    break

            logger.info("pagerduty_alerts_fetched", service=service, count=len(items))
            return items[:limit]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pagerduty_alerts_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("pagerduty_alerts_error", service=service, error=str(exc))
            return []


def _pd_severity(urgency: str, status: str) -> str:
    """Derive severity from PagerDuty urgency + status."""
    if status == "triggered":
        return "critical" if urgency == "high" else "warning"
    if status == "acknowledged":
        return "warning"
    if status == "resolved":
        return "ok"
    return "unknown"


__all__ = ["PagerDutyConnector"]
