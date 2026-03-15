"""
ConnectorBase — abstract base class for all BugPilot connectors.

The orchestrator (worker/pipeline/orchestrator.py) calls ONLY:
  - fetch_with_timeout()
  - health_check()

It never imports connector classes directly. Use connectors/registry.py.
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ConnectorHealth:
    status: str     # "healthy" | "degraded" | "error" | "not_configured"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class ConnectorData:
    connector_type: str
    normalised_events: list[dict]   # BugPilot UES format — what orchestrator uses
    raw_event_count: int            # for logging only
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ConnectorBase(ABC):
    """
    All connectors must implement this interface.
    The orchestrator calls only: fetch_with_timeout() and health_check().
    """

    def __init__(self, config: dict, org_id: str):
        self._config = config
        self.org_id = org_id
        self._cb = _CircuitBreaker(name=self.connector_type)
        # Set by registry.get_connectors_for_service():
        self._service_name: Optional[str] = None
        self._service_map: dict = {}
        self._connector_name: str = "default"

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Return: 'github'|'jira'|'freshdesk'|'email_imap'|'sentry'|'database'|'log_files'"""

    @property
    def rate_limit_rpm(self) -> int:
        """Override per-connector. Default 60 req/min."""
        return 60

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Return list of validation error strings. Empty list = valid."""

    @abstractmethod
    def health_check(self) -> ConnectorHealth:
        """
        Test live connectivity and permissions.
        Must complete within 10 seconds.
        MUST NOT raise — catch all exceptions and return ConnectorHealth(status='error').
        """

    @abstractmethod
    def fetch(
        self,
        service_name: Optional[str],
        window_start: datetime,
        window_end: datetime,
        trigger_ref: Optional[str] = None,
        **kwargs,
    ) -> ConnectorData:
        """
        Fetch and return normalised data for this investigation.

        Args:
            service_name: logical service to scope the query (may be None)
            window_start: beginning of investigation time window (UTC)
            window_end: end of investigation time window (UTC)
            trigger_ref: optional external ticket/alert ref (e.g. "ENG-123")

        MUST NOT raise — catch all exceptions, include as warnings, return partial data.
        MUST complete within 30 seconds (enforced externally by fetch_with_timeout).
        """

    def fetch_with_timeout(
        self,
        service_name: Optional[str],
        window_start: datetime,
        window_end: datetime,
        trigger_ref: Optional[str] = None,
        timeout_seconds: int = 30,
    ) -> ConnectorData:
        """
        Wraps fetch() with circuit breaker + hard timeout.
        Called by orchestrator. Do NOT override.
        """
        if self._cb.is_open():
            return ConnectorData(
                connector_type=self.connector_type,
                normalised_events=[],
                raw_event_count=0,
                warnings=[
                    f"{self.connector_type}: circuit breaker open "
                    f"(too many recent failures)"
                ],
            )
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(
                    self.fetch,
                    service_name, window_start, window_end,
                    trigger_ref=trigger_ref,
                )
                result = future.result(timeout=timeout_seconds)
            self._cb.record_success()
            return result
        except concurrent.futures.TimeoutError:
            self._cb.record_failure()
            return ConnectorData(
                connector_type=self.connector_type,
                normalised_events=[],
                raw_event_count=0,
                warnings=[f"{self.connector_type}: timed out after {timeout_seconds}s"],
            )
        except Exception as e:
            self._cb.record_failure()
            log.error(
                f"Connector {self.connector_type} failed unexpectedly: {e}",
                exc_info=True,
            )
            return ConnectorData(
                connector_type=self.connector_type,
                normalised_events=[],
                raw_event_count=0,
                warnings=[f"{self.connector_type}: unexpected error: {str(e)}"],
            )


class _CircuitBreaker:
    """3 failures → open for 300 seconds, then auto-reset."""

    THRESHOLD = 3
    TIMEOUT = 300

    def __init__(self, name: str):
        self.name = name
        self._failures = 0
        self._opened_at: Optional[float] = None

    def is_open(self) -> bool:
        if self._failures >= self.THRESHOLD:
            if self._opened_at and (time.time() - self._opened_at) < self.TIMEOUT:
                return True
            self._failures = 0  # Reset after timeout period
        return False

    def record_success(self) -> None:
        self._failures = 0

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.THRESHOLD:
            self._opened_at = time.time()
