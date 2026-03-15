"""
NormaliserBase — base class for all connector normalisers.

Each connector extends this to produce Unified Event Schema (UES) events.

UES event types and their required extra fields:

CustomerTicket:
    ticket_id, summary, issue_type, severity, source_system

CodeChangeEvent:
    pr_id, pr_url, pr_title, pr_author, merged_at, deployed_at,
    files_changed[], diff_semantics{type, files, lines},
    ci_status, is_revert, is_hotfix, dependency_bumps[]

FunctionalAnomaly:
    entity_type, field_name, anomaly_pattern, cohort_attrs{}, blast_radius_count

ErrorEvent:
    service, exception_type, stack_trace_hash, count, is_silent, count_delta_pct

JobExecutionEvent:
    job_name, status, duration_ms, error_hash

Every event MUST contain: event_type, source, id, timestamp (ISO8601 UTC), org_id
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

# Valid UES event types
UES_EVENT_TYPES = frozenset(
    [
        "CustomerTicket",
        "CodeChangeEvent",
        "FunctionalAnomaly",
        "ErrorEvent",
        "JobExecutionEvent",
    ]
)

# Required fields on every UES event
UES_REQUIRED_FIELDS = frozenset(["event_type", "source", "id", "timestamp", "org_id"])


def validate_ues_event(event: dict) -> list[str]:
    """Return list of validation errors. Empty = valid UES event."""
    errors = []
    for field in UES_REQUIRED_FIELDS:
        if field not in event:
            errors.append(f"Missing required UES field: '{field}'")
    if "event_type" in event and event["event_type"] not in UES_EVENT_TYPES:
        errors.append(
            f"Invalid event_type '{event['event_type']}'. "
            f"Valid types: {sorted(UES_EVENT_TYPES)}"
        )
    return errors


def utcnow_iso() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


class NormaliserBase(ABC):
    """Base class for all connector normalisers."""

    def __init__(self, config: dict, org_id: str):
        self._config = config
        self.org_id = org_id

    @abstractmethod
    def to_ues(self, raw_event: dict) -> dict:
        """Convert a raw vendor event to a UES event dict."""

    def _base_event(self, event_type: str, source: str, event_id: str) -> dict:
        """Create the base fields every UES event must have."""
        return {
            "event_type": event_type,
            "source": source,
            "id": event_id,
            "timestamp": utcnow_iso(),
            "org_id": self.org_id,
        }
