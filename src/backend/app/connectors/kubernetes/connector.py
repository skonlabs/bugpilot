"""
Kubernetes connector for BugPilot.
Supports INFRASTRUCTURE_STATE (pods, nodes, events) and DEPLOYMENTS capabilities.
"""
from __future__ import annotations

import ssl
import tempfile
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
    ConnectorCapability.INFRASTRUCTURE_STATE,
    ConnectorCapability.DEPLOYMENTS,
]

_REQUEST_TIMEOUT = 30.0


def _parse_k8s_time(ts_str: Optional[str], fallback: datetime) -> datetime:
    """Parse a Kubernetes ISO timestamp (e.g. '2024-01-02T15:04:05Z')."""
    if not ts_str:
        return fallback
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return fallback


def _condition_severity(conditions: list[dict]) -> str:
    """Derive a severity from a list of Kubernetes condition objects."""
    for cond in conditions:
        ctype = cond.get("type", "")
        status = cond.get("status", "True")
        if ctype in ("Ready", "Available") and status != "True":
            return "critical"
        if ctype == "MemoryPressure" and status == "True":
            return "warning"
        if ctype == "DiskPressure" and status == "True":
            return "warning"
    return "ok"


class KubernetesConnector(BaseConnector):
    """
    Connector for Kubernetes API server.

    Supports:
    - INFRASTRUCTURE_STATE via GET /api/v1/pods, /api/v1/nodes, /api/v1/events
    - DEPLOYMENTS          via GET /apis/apps/v1/deployments

    Authentication: Bearer token.
    TLS: uses ca_cert if provided, otherwise accepts the server certificate
         (suitable for in-cluster access or controlled environments).
    """

    def __init__(
        self,
        api_server: str,
        token: str,
        ca_cert: Optional[str] = None,
        namespace: str = "default",
    ) -> None:
        self._api_server = api_server.rstrip("/")
        self._token = token
        self._ca_cert = ca_cert  # PEM string or path
        self._namespace = namespace
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[ConnectorCapability]:
        return list(_SUPPORTED_CAPABILITIES)

    def _build_client(self) -> httpx.AsyncClient:
        """Build an AsyncClient with appropriate TLS settings."""
        if self._ca_cert:
            # Write PEM to a temp file if it looks like PEM content
            if self._ca_cert.strip().startswith("-----BEGIN"):
                import os
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".pem", delete=False
                )
                tmp.write(self._ca_cert)
                tmp.close()
                verify: Any = tmp.name
            else:
                # Assume it's already a file path
                verify = self._ca_cert
        else:
            # No CA cert provided - skip verification (OK for in-cluster with projected token)
            verify = False
        return httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, verify=verify)

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        """Validate connectivity via GET /api/v1/namespaces."""
        start = time.monotonic()
        try:
            async with self._build_client() as client:
                resp = await client.get(
                    f"{self._api_server}/api/v1/namespaces",
                    headers=self._headers,
                    params={"limit": 1},
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
            logger.error("kubernetes_validate_error", error=str(exc))
            return ValidationResult(is_valid=False, error=str(exc), latency_ms=latency_ms)

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        if capability == ConnectorCapability.INFRASTRUCTURE_STATE:
            return await self._fetch_infrastructure_state(service, since, until, limit)
        elif capability == ConnectorCapability.DEPLOYMENTS:
            return await self._fetch_deployments(service, since, until, limit)
        else:
            logger.warning("kubernetes_unsupported_capability", capability=capability.value)
            return []

    # ------------------------------------------------------------------
    # Private fetch methods
    # ------------------------------------------------------------------

    async def _k8s_get(
        self, path: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Perform a signed GET request to the Kubernetes API."""
        async with self._build_client() as client:
            resp = await client.get(
                f"{self._api_server}{path}",
                headers=self._headers,
                params=params,
            )
        resp.raise_for_status()
        return resp.json()

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_infrastructure_state(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch pods, nodes, and events for the given service/namespace."""
        items: list[RawEvidenceItem] = []
        try:
            # --- Pods ---
            ns = self._namespace
            pods_data = await self._k8s_get(
                f"/api/v1/namespaces/{ns}/pods",
                params={"labelSelector": f"app={service}", "limit": min(limit, 500)},
            )
            for pod in pods_data.get("items", []):
                meta = pod.get("metadata", {})
                status = pod.get("status", {})
                conditions = status.get("conditions", [])
                ts = _parse_k8s_time(
                    meta.get("creationTimestamp"), since
                )
                severity = _condition_severity(conditions)
                # Map pod phase to severity
                phase = status.get("phase", "Unknown")
                if phase in ("Failed", "CrashLoopBackOff"):
                    severity = "critical"
                elif phase == "Pending":
                    severity = "warning"

                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.INFRASTRUCTURE_STATE,
                        source_system="kubernetes",
                        service=service,
                        timestamp=ts,
                        payload=pod,
                        severity=severity,
                        message=f"Pod {meta.get('name')} phase={phase}",
                        raw_ref=meta.get("uid"),
                        metadata={"kind": "Pod", "namespace": ns, "phase": phase},
                    )
                )

            # --- Nodes ---
            nodes_data = await self._k8s_get("/api/v1/nodes", params={"limit": 100})
            for node in nodes_data.get("items", []):
                meta = node.get("metadata", {})
                status = node.get("status", {})
                conditions = status.get("conditions", [])
                ts = _parse_k8s_time(meta.get("creationTimestamp"), since)
                severity = _condition_severity(conditions)
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.INFRASTRUCTURE_STATE,
                        source_system="kubernetes",
                        service=service,
                        timestamp=ts,
                        payload={"metadata": meta, "status": {"conditions": conditions}},
                        severity=severity,
                        message=f"Node {meta.get('name')} severity={severity}",
                        raw_ref=meta.get("uid"),
                        metadata={"kind": "Node"},
                    )
                )

            # --- Events ---
            events_data = await self._k8s_get(
                f"/api/v1/namespaces/{ns}/events",
                params={
                    "fieldSelector": f"involvedObject.labels.app={service}",
                    "limit": min(limit, 500),
                },
            )
            for event in events_data.get("items", []):
                meta = event.get("metadata", {})
                ts_str = event.get("lastTimestamp") or event.get("firstTimestamp")
                ts = _parse_k8s_time(ts_str, since)
                event_type = event.get("type", "Normal")
                severity = "critical" if event_type == "Warning" else "info"

                # Time range filter
                if ts.replace(tzinfo=timezone.utc) < since.replace(tzinfo=timezone.utc):
                    continue
                if ts.replace(tzinfo=timezone.utc) > until.replace(tzinfo=timezone.utc):
                    continue

                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.INFRASTRUCTURE_STATE,
                        source_system="kubernetes",
                        service=service,
                        timestamp=ts,
                        payload=event,
                        severity=severity,
                        message=event.get("message"),
                        raw_ref=meta.get("uid"),
                        metadata={
                            "kind": "Event",
                            "reason": event.get("reason"),
                            "namespace": ns,
                        },
                    )
                )

            logger.info("kubernetes_infra_fetched", service=service, count=len(items))
            return items[:limit]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "kubernetes_infra_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("kubernetes_infra_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_deployments(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """
        Fetch deployments via GET /apis/apps/v1/deployments.

        Filters by label selector 'app=<service>' and by creationTimestamp
        (the K8s API does not support time range filtering natively; we apply
        client-side filtering and annotate evidence accordingly).
        """
        ns = self._namespace
        try:
            deployments_data = await self._k8s_get(
                f"/apis/apps/v1/namespaces/{ns}/deployments",
                params={
                    "labelSelector": f"app={service}",
                    "limit": min(limit, 500),
                },
            )
            items: list[RawEvidenceItem] = []
            for deployment in deployments_data.get("items", []):
                meta = deployment.get("metadata", {})
                spec = deployment.get("spec", {})
                status = deployment.get("status", {})
                ts = _parse_k8s_time(meta.get("creationTimestamp"), since)

                # Client-side time range filter
                ts_aware = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
                since_aware = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
                until_aware = until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until
                if ts_aware < since_aware or ts_aware > until_aware:
                    # Also check annotations for deploy time
                    deploy_time_str = meta.get("annotations", {}).get(
                        "deployment.kubernetes.io/revision-history-limit"
                    )
                    if not deploy_time_str:
                        continue

                available = status.get("availableReplicas", 0)
                desired = spec.get("replicas", 0)
                severity = "ok" if available >= desired else "warning"

                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.DEPLOYMENTS,
                        source_system="kubernetes",
                        service=service,
                        timestamp=ts,
                        payload=deployment,
                        severity=severity,
                        message=(
                            f"Deployment {meta.get('name')} "
                            f"{available}/{desired} replicas available"
                        ),
                        raw_ref=meta.get("uid"),
                        metadata={
                            "namespace": ns,
                            "available_replicas": available,
                            "desired_replicas": desired,
                            "revision": meta.get("annotations", {}).get(
                                "deployment.kubernetes.io/revision", "unknown"
                            ),
                        },
                    )
                )

            logger.info("kubernetes_deployments_fetched", service=service, count=len(items))
            return items[:limit]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "kubernetes_deployments_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("kubernetes_deployments_error", service=service, error=str(exc))
            return []


__all__ = ["KubernetesConnector"]
