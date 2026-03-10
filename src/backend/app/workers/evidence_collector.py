"""
Evidence collection worker.
Collects evidence from all configured connectors concurrently.
"""
from __future__ import annotations

import asyncio
import textwrap
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog

from app.connectors.base import BaseConnector, ConnectorCapability, RawEvidenceItem
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TTL_MINUTES = 10
COLLECTION_TIMEOUT_SECONDS = 45


# ---------------------------------------------------------------------------
# Collection result
# ---------------------------------------------------------------------------


class EvidenceCollectionResult:
    """Result of a single connector/capability collection."""

    def __init__(self, connector_name: str, capability: ConnectorCapability) -> None:
        self.connector_name = connector_name
        self.capability = capability
        self.items: list[RawEvidenceItem] = []
        self.error: Optional[str] = None
        self.timed_out: bool = False
        self.collected_at: datetime = datetime.now(timezone.utc)
        self.reliability_score: float = 1.0


# ---------------------------------------------------------------------------
# Evidence collector
# ---------------------------------------------------------------------------


class EvidenceCollector:
    """Collects evidence from multiple connectors concurrently."""

    def __init__(self, connectors: list[tuple[str, BaseConnector]]) -> None:
        """
        Args:
            connectors: List of (name, connector_instance) tuples.
        """
        self.connectors = connectors

    async def collect(
        self,
        service: str,
        since: datetime,
        until: datetime,
        capabilities: Optional[list[ConnectorCapability]] = None,
    ) -> list[EvidenceCollectionResult]:
        """
        Collect evidence from all connectors concurrently.

        Each collection is independently timeout-guarded (COLLECTION_TIMEOUT_SECONDS).
        One failing connector does not affect others.

        Args:
            service: The service name to collect evidence for.
            since: Start of the time window.
            until: End of the time window.
            capabilities: Optional whitelist of capabilities to collect.
                          If None, all connector capabilities are used.

        Returns:
            List of EvidenceCollectionResult (one per connector/capability pair).
        """
        tasks: list[asyncio.coroutine] = []
        for name, connector in self.connectors:
            for cap in connector.capabilities():
                if capabilities and cap not in capabilities:
                    continue
                tasks.append(
                    self._collect_with_timeout(name, connector, cap, service, since, until)
                )

        if not tasks:
            logger.warning(
                "evidence_collector_no_tasks",
                service=service,
                capabilities=[c.value for c in (capabilities or [])],
            )
            return []

        results: list[EvidenceCollectionResult] = await asyncio.gather(
            *tasks, return_exceptions=False
        )
        logger.info(
            "evidence_collection_complete",
            service=service,
            total_tasks=len(tasks),
            total_items=sum(len(r.items) for r in results),
            errors=sum(1 for r in results if r.error),
            timeouts=sum(1 for r in results if r.timed_out),
        )
        return results

    async def _collect_with_timeout(
        self,
        name: str,
        connector: BaseConnector,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
    ) -> EvidenceCollectionResult:
        result = EvidenceCollectionResult(name, capability)
        try:
            items = await asyncio.wait_for(
                connector.fetch_evidence(capability, service, since, until),
                timeout=COLLECTION_TIMEOUT_SECONDS,
            )
            result.items = items
            result.reliability_score = 1.0
        except asyncio.TimeoutError:
            result.timed_out = True
            result.error = f"Timed out after {COLLECTION_TIMEOUT_SECONDS}s"
            result.reliability_score = 0.0
            logger.warning(
                "connector_timeout",
                connector=name,
                capability=capability.value,
                service=service,
            )
        except Exception as exc:
            result.error = str(exc)
            result.reliability_score = 0.0
            logger.error(
                "connector_error",
                connector=name,
                capability=capability.value,
                service=service,
                error=str(exc),
            )
        return result

    def compute_reliability_score(
        self, result: EvidenceCollectionResult, staleness_minutes: float = 0
    ) -> float:
        """
        Reliability score 0-1 based on connector health + staleness.

        Args:
            result: The collection result to score.
            staleness_minutes: How many minutes old the result is.

        Returns:
            Float in [0.0, 1.0]. 1.0 = fully reliable, 0.0 = failed/timed out.
        """
        if result.timed_out or result.error:
            return 0.0
        staleness_penalty = min(staleness_minutes / 60.0, 0.5)  # Max 50% penalty
        return max(0.0, 1.0 - staleness_penalty)


# ---------------------------------------------------------------------------
# Normalization pipeline
# ---------------------------------------------------------------------------


class NormalizationPipeline:
    """
    Normalizes RawEvidenceItem instances into structured, redaction-safe records.

    Pipeline steps:
    1. Apply PII/secret redaction to all string fields.
    2. Extract and validate structured fields (timestamp, severity, service, message).
    3. Generate a normalized_summary (plain text, max 500 chars).
    4. Return a normalized evidence dict ready for DB storage.
    """

    def __init__(self) -> None:
        # Import lazily to avoid circular import at module load time
        self._redact_dict = None
        self._redact_string = None

    def _ensure_redactors_loaded(self) -> None:
        if self._redact_dict is None:
            from app.privacy.redactor import redact_dict, redact_string
            self._redact_dict = redact_dict
            self._redact_string = redact_string

    def normalize(self, item: RawEvidenceItem) -> dict[str, Any]:
        """
        Normalize a single RawEvidenceItem.

        Args:
            item: The raw evidence item to normalize.

        Returns:
            A dict with keys: id, capability, source_system, service, timestamp,
            severity, message, normalized_summary, payload, metadata,
            redaction_manifest.
        """
        self._ensure_redactors_loaded()

        # Step 1: Redact payload
        redacted_payload, payload_manifest = self._redact_dict(item.payload)

        # Step 2: Redact message
        redacted_message = item.message
        message_manifest = None
        if item.message:
            redacted_message, message_manifest = self._redact_string(item.message)

        # Step 3: Redact metadata
        redacted_metadata, meta_manifest = self._redact_dict(item.metadata)

        # Step 4: Normalize severity
        severity = _normalize_severity(item.severity)

        # Step 5: Ensure timestamp has timezone info
        ts = item.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Step 6: Build normalized_summary (max 500 chars)
        summary = _build_summary(
            capability=item.capability,
            source_system=item.source_system,
            service=item.service,
            severity=severity,
            message=redacted_message,
            timestamp=ts,
            payload=redacted_payload,
        )

        # Combine manifests
        total_replacements = payload_manifest.total_replacements
        if message_manifest:
            total_replacements += message_manifest.total_replacements
        total_replacements += meta_manifest.total_replacements

        return {
            "id": str(uuid.uuid4()),
            "capability": item.capability.value,
            "source_system": item.source_system,
            "service": item.service,
            "timestamp": ts.isoformat(),
            "severity": severity,
            "message": redacted_message,
            "normalized_summary": summary,
            "payload": redacted_payload,
            "metadata": redacted_metadata,
            "raw_ref": item.raw_ref,
            "redaction_manifest": {
                "total_replacements": total_replacements,
                "pattern_counts": {
                    **payload_manifest.pattern_counts,
                    **(message_manifest.pattern_counts if message_manifest else {}),
                    **meta_manifest.pattern_counts,
                },
            },
        }

    def normalize_batch(
        self, items: list[RawEvidenceItem]
    ) -> list[dict[str, Any]]:
        """Normalize a batch of RawEvidenceItems."""
        results = []
        for item in items:
            try:
                normalized = self.normalize(item)
                results.append(normalized)
            except Exception as exc:
                logger.error(
                    "normalization_error",
                    source=item.source_system,
                    capability=item.capability.value,
                    error=str(exc),
                )
        return results

    def normalize_collection_results(
        self, results: list[EvidenceCollectionResult]
    ) -> list[dict[str, Any]]:
        """Normalize all items from a list of EvidenceCollectionResults."""
        all_normalized: list[dict[str, Any]] = []
        for result in results:
            if result.items:
                batch = self.normalize_batch(result.items)
                # Annotate each item with reliability score
                for item in batch:
                    item["connector_name"] = result.connector_name
                    item["reliability_score"] = result.reliability_score
                    item["collected_at"] = result.collected_at.isoformat()
                all_normalized.extend(batch)
        return all_normalized


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, str] = {
    # Datadog
    "alert": "critical",
    "warn": "warning",
    "warning": "warning",
    "error": "error",
    "info": "info",
    "ok": "ok",
    "critical": "critical",
    # CloudWatch
    "alarm": "critical",
    "insufficient_data": "unknown",
    # Generic
    "high": "critical",
    "medium": "warning",
    "low": "info",
    "unknown": "unknown",
    "none": "info",
}


def _normalize_severity(severity: Optional[str]) -> str:
    if not severity:
        return "unknown"
    normalized = _SEVERITY_MAP.get(severity.lower(), severity.lower())
    return normalized


def _build_summary(
    capability: ConnectorCapability,
    source_system: str,
    service: str,
    severity: str,
    message: Optional[str],
    timestamp: datetime,
    payload: dict[str, Any],
) -> str:
    """
    Build a plain-text normalized summary (max 500 chars).

    The summary is designed to be directly embeddable in LLM prompts.
    """
    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    msg_part = ""
    if message:
        msg_part = f" | {message}"

    # For certain capability types, enrich the summary with extra fields
    extra = ""
    if capability == ConnectorCapability.METRICS:
        value = payload.get("value")
        metric = payload.get("metric", "")
        if value is not None and metric:
            extra = f" | metric={metric} value={value}"
    elif capability == ConnectorCapability.DEPLOYMENTS:
        env = payload.get("environment") or payload.get("env", "")
        ref = payload.get("ref", "")
        if env:
            extra = f" | env={env}"
        if ref:
            extra += f" ref={ref}"
    elif capability == ConnectorCapability.INFRASTRUCTURE_STATE:
        kind = payload.get("kind", "")
        phase = payload.get("phase", "")
        if kind:
            extra = f" | kind={kind}"
        if phase:
            extra += f" phase={phase}"

    summary = (
        f"[{ts_str}] [{source_system.upper()}] [{capability.value.upper()}] "
        f"service={service} severity={severity}{msg_part}{extra}"
    )

    # Truncate to 500 chars
    if len(summary) > 500:
        summary = summary[:497] + "..."

    return summary


__all__ = [
    "EvidenceCollectionResult",
    "EvidenceCollector",
    "NormalizationPipeline",
    "DEFAULT_TTL_MINUTES",
    "COLLECTION_TIMEOUT_SECONDS",
]
