"""
Comprehensive Pydantic v2 schemas for all BugPilot API request/response models.

Conventions:
  - All schemas use ConfigDict(from_attributes=True) for ORM compatibility.
  - Request schemas are suffixed with Request / Create / Update.
  - Response schemas are suffixed with Response.
  - List wrappers are suffixed with List.
  - UUIDs are exposed as str for JSON serialisation simplicity.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Base / shared utilities
# ---------------------------------------------------------------------------


class APIModel(BaseModel):
    """Base model with ORM-mode and common config for all API schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class PaginatedResponse(APIModel, Generic[T]):
    """Generic paginated list wrapper."""

    items: List[T]
    total: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class ErrorResponse(APIModel):
    """Standard API error envelope."""

    detail: str
    code: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class SuccessResponse(APIModel):
    """Standard success envelope for operations that return no domain object."""

    detail: str
    data: Optional[Any] = None


# ---------------------------------------------------------------------------
# Auth — activate / session
# ---------------------------------------------------------------------------


class ActivateRequest(APIModel):
    """POST /v1/auth/activate"""

    license_key: str = Field(
        ...,
        min_length=16,
        max_length=256,
        description="License key to activate. Sent once per installation.",
    )
    device_fingerprint: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional device fingerprint for seat tracking.",
    )
    org_slug: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$",
        description="URL-safe organisation slug.",
    )
    org_display_name: str = Field(..., min_length=1, max_length=255)
    admin_email: str = Field(..., description="Email for the initial admin user.")


class ActivateResponse(APIModel):
    """Response for a successful activation."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token TTL in seconds.")
    org_id: str
    user_id: str
    tier: str


class RefreshRequest(APIModel):
    """POST /v1/auth/refresh"""

    refresh_token: str = Field(..., min_length=32)


class RefreshResponse(APIModel):
    """New token pair after a successful refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SessionStatusResponse(APIModel):
    """GET /v1/auth/session — current session info."""

    session_id: str
    user_id: str
    org_id: str
    email: str
    role: str
    is_active: bool
    expires_at: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------


class LicenseStatusResponse(APIModel):
    """GET /v1/license/status"""

    org_id: str
    license_id: str
    tier: str
    status: str  # active | expired | revoked | grace
    seat_limit: int
    seats_used: int
    expires_at: Optional[datetime] = None
    grace_until: Optional[datetime] = None
    days_until_expiry: Optional[int] = None


# ---------------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------------


class InvestigationCreate(APIModel):
    """POST /v1/investigations"""

    title: str = Field(..., min_length=3, max_length=512)
    description: Optional[str] = Field(default=None, max_length=10_000)
    symptom: Optional[str] = Field(default=None, max_length=5_000)
    severity: str = Field(
        default="medium",
        description="low | medium | high | critical",
    )
    tags: List[str] = Field(default_factory=list, max_length=20)
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Free-form metadata (services affected, deployment SHA, etc.)",
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of {sorted(allowed)}")
        return v.lower()


class InvestigationUpdate(APIModel):
    """PATCH /v1/investigations/{id}"""

    title: Optional[str] = Field(default=None, min_length=3, max_length=512)
    description: Optional[str] = Field(default=None, max_length=10_000)
    symptom: Optional[str] = Field(default=None, max_length=5_000)
    severity: Optional[str] = None
    status: Optional[str] = Field(
        default=None,
        description="open | in_progress | resolved | closed",
    )
    tags: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None


class InvestigationResponse(APIModel):
    """Single investigation."""

    id: str
    org_id: str
    created_by: Optional[str] = None
    title: str
    description: Optional[str] = None
    symptom: Optional[str] = None
    severity: str
    status: str
    tags: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    # Derived / enriched fields added by the API layer
    evidence_count: Optional[int] = None
    hypothesis_count: Optional[int] = None
    action_count: Optional[int] = None
    duplicate_of: Optional[str] = Field(
        default=None,
        description="ID of the canonical investigation if this was merged.",
    )


class InvestigationList(APIModel):
    """GET /v1/investigations — list response."""

    items: List[InvestigationResponse]
    total: int
    page: int = 1
    page_size: int = 20


class InvestigationMergeRequest(APIModel):
    """POST /v1/investigations/{source_id}/merge-into/{target_id}"""

    note: Optional[str] = Field(
        default=None,
        max_length=1_000,
        description="Optional reason for the merge.",
    )


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceItemResponse(APIModel):
    """Single evidence item (raw_payload is never included)."""

    id: str
    investigation_id: str
    org_id: str
    kind: str
    label: str
    source_uri: Optional[str] = None
    # raw_payload intentionally absent
    summary: Optional[str] = None
    collected_at: datetime
    expires_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime


class EvidenceList(APIModel):
    """GET /v1/investigations/{id}/evidence"""

    items: List[EvidenceItemResponse]
    total: int
    page: int = 1
    page_size: int = 50


# ---------------------------------------------------------------------------
# Hypotheses
# ---------------------------------------------------------------------------


class HypothesisResponse(APIModel):
    """Single hypothesis."""

    id: str
    investigation_id: str
    org_id: str
    title: str
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    status: str
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="List of evidence UUIDs that support this hypothesis.",
    )
    reasoning: Optional[str] = None
    generated_by_llm: bool = False
    llm_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class HypothesisList(APIModel):
    """GET /v1/investigations/{id}/hypotheses"""

    items: List[HypothesisResponse]
    total: int


class HypothesisStatusUpdate(APIModel):
    """PATCH /v1/hypotheses/{id}/status"""

    status: str = Field(
        ...,
        description="proposed | testing | confirmed | rejected",
    )
    reasoning: Optional[str] = Field(default=None, max_length=5_000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"proposed", "testing", "confirmed", "rejected"}
        if v.lower() not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v.lower()


# ---------------------------------------------------------------------------
# Actions / Remediation
# ---------------------------------------------------------------------------


class ActionCandidateResponse(APIModel):
    """A proposed remediation action candidate."""

    id: str
    investigation_id: str
    hypothesis_id: Optional[str] = None
    org_id: str
    title: str
    description: Optional[str] = None
    action_type: str
    risk_level: str
    status: str
    rollback_plan: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    requires_approval: bool = False
    created_at: datetime
    updated_at: datetime


class DryRunResponse(APIModel):
    """Result of a dry-run simulation."""

    action_id: str
    predicted_changes: List[str]
    estimated_impact: str
    is_safe: bool
    warnings: List[str] = Field(default_factory=list)


class ActionApproveRequest(APIModel):
    """POST /v1/actions/{id}/approve or /v1/actions/{id}/reject"""

    decision: str = Field(..., description="'approved' or 'rejected'")
    note: Optional[str] = Field(default=None, max_length=2_000)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v.lower() not in {"approved", "rejected"}:
            raise ValueError("decision must be 'approved' or 'rejected'")
        return v.lower()


class ActionRunRequest(APIModel):
    """POST /v1/actions/{id}/run"""

    confirm: bool = Field(
        ...,
        description="Must be True to confirm intentional execution.",
    )

    @field_validator("confirm")
    @classmethod
    def must_confirm(cls, v: bool) -> bool:
        if not v:
            raise ValueError("confirm must be true to execute the action.")
        return v


class ActionResponse(APIModel):
    """Single action result."""

    action_id: str
    status: str
    output: str
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Webhook intake
# ---------------------------------------------------------------------------


class WebhookIntakeRecord(APIModel):
    """
    POST /v1/webhooks/intake/{connector_kind}
    Inbound webhook payload normalised for storage.
    """

    source: str = Field(
        ...,
        description="Connector kind that produced this event (e.g. 'datadog', 'pagerduty').",
    )
    event_kind: str = Field(
        ...,
        description="Event type within the source system.",
    )
    payload: Dict[str, Any] = Field(
        ...,
        description="Raw webhook payload (will be stored; not surfaced in exports).",
    )
    received_at: datetime = Field(
        description="Server-side receipt timestamp.",
    )
    signature_valid: Optional[bool] = Field(
        default=None,
        description="Whether the HMAC signature was verified.",
    )
    investigation_id: Optional[str] = Field(
        default=None,
        description="Investigation auto-linked to this event, if any.",
    )


class WebhookIntakeResponse(APIModel):
    """Acknowledgement returned to the webhook sender."""

    accepted: bool
    investigation_id: Optional[str] = None
    message: str = "Webhook received"


# ---------------------------------------------------------------------------
# Service mappings
# ---------------------------------------------------------------------------


class ServiceNodeCreate(APIModel):
    """A single node in a service map."""

    name: str = Field(..., min_length=1, max_length=255)
    kind: str = Field(
        default="service",
        description="service | database | queue | cache | external | lambda | container",
    )
    namespace: Optional[str] = Field(default=None, max_length=255)
    team: Optional[str] = Field(default=None, max_length=255)
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ServiceEdgeCreate(APIModel):
    """A directed edge between two service nodes."""

    source_service: str = Field(..., min_length=1, max_length=255)
    target_service: str = Field(..., min_length=1, max_length=255)
    protocol: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Transport protocol (HTTP, gRPC, AMQP, etc.)",
    )
    label: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[Dict[str, Any]] = None


class ServiceMappingCreate(APIModel):
    """
    POST /v1/service-mappings
    Create or update a service map with nodes and optional edges.
    """

    map_name: str = Field(
        default="default",
        min_length=1,
        max_length=255,
        description="Name of the service map to create/update.",
    )
    nodes: List[ServiceNodeCreate] = Field(default_factory=list)
    edges: List[ServiceEdgeCreate] = Field(default_factory=list)


class ServiceNodeResponse(APIModel):
    """A persisted service node."""

    id: str
    service_map_id: str
    org_id: str
    name: str
    kind: str
    namespace: Optional[str] = None
    team: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ServiceEdgeResponse(APIModel):
    """A persisted service edge."""

    id: str
    service_map_id: str
    org_id: str
    source_node_id: str
    target_node_id: str
    protocol: Optional[str] = None
    label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ServiceMappingResponse(APIModel):
    """Full service map with nodes and edges."""

    map_id: str
    map_name: str
    org_id: str
    version: int
    is_active: bool
    nodes: List[ServiceNodeResponse] = Field(default_factory=list)
    edges: List[ServiceEdgeResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DiscoveryResponse(APIModel):
    """POST /v1/service-mappings/discover — auto-discovery summary."""

    discovered: int
    added: int
    skipped: int
    services: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Preview of discovered service names and their sources.",
    )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class ExportRequest(APIModel):
    """POST /v1/investigations/{id}/export"""

    format: str = Field(
        ...,
        description="Output format: 'json' or 'markdown'.",
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = {"json", "markdown"}
        if v.lower() not in allowed:
            raise ValueError(f"format must be one of {sorted(allowed)}")
        return v.lower()


class ExportResponse(APIModel):
    """Metadata returned after export generation (content delivered separately)."""

    investigation_id: str
    format: str
    filename: str
    generated_at: datetime
    download_url: Optional[str] = Field(
        default=None,
        description="Pre-signed URL if the export was stored in object storage.",
    )


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


class BaselineSelectRequest(APIModel):
    """POST /v1/investigations/{id}/baseline"""

    strategy: str = Field(
        default="last_healthy_window",
        description=(
            "last_healthy_window | last_stable_post_deploy | user_pinned"
        ),
    )
    pinned_window_start: Optional[datetime] = Field(
        default=None,
        description="Required when strategy='user_pinned'.",
    )
    pinned_window_end: Optional[datetime] = Field(
        default=None,
        description="Required when strategy='user_pinned'.",
    )
    error_rate_threshold: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Maximum acceptable error rate for a window to be 'healthy'.",
    )

    @model_validator(mode="after")
    def validate_pinned_fields(self) -> "BaselineSelectRequest":
        if self.strategy == "user_pinned":
            if not self.pinned_window_start or not self.pinned_window_end:
                raise ValueError(
                    "pinned_window_start and pinned_window_end are required "
                    "when strategy='user_pinned'."
                )
        return self


class BaselineResponse(APIModel):
    """Selected baseline window details."""

    strategy: str
    window_start: datetime
    window_end: datetime
    description: str
    error_rate: float
    alert_count: int


class ComparisonResponse(APIModel):
    """Baseline comparison result."""

    baseline_description: str
    degraded_services: List[str]
    significant_changes: List[str]
    overall_degraded: bool
    metric_deltas: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class DedupCheckResponse(APIModel):
    """Response from a deduplication check."""

    is_duplicate: bool
    candidate_investigation_id: Optional[str] = None
    weighted_score: float
    message: str


# ---------------------------------------------------------------------------
# Admin / org settings
# ---------------------------------------------------------------------------


class RetentionPolicyUpdate(APIModel):
    """PATCH /v1/admin/retention — update org retention settings."""

    investigations_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Days before resolved investigations are archived.",
    )
    evidence_metadata_days: int = Field(
        default=90,
        ge=7,
        le=3650,
        description="Days before evidence metadata records are deleted.",
    )
    raw_payload_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days before raw_payload column is nulled out.",
    )

    @model_validator(mode="after")
    def validate_ordering(self) -> "RetentionPolicyUpdate":
        if self.raw_payload_days > self.evidence_metadata_days:
            raise ValueError(
                "raw_payload_days must be <= evidence_metadata_days."
            )
        if self.evidence_metadata_days > self.investigations_days:
            raise ValueError(
                "evidence_metadata_days must be <= investigations_days."
            )
        return self


class RetentionPolicyResponse(APIModel):
    """Current retention policy for the org."""

    org_id: str
    investigations_days: int
    evidence_metadata_days: int
    raw_payload_days: int


# ---------------------------------------------------------------------------
# Timeline events
# ---------------------------------------------------------------------------


class TimelineEventResponse(APIModel):
    """A single timeline event."""

    id: str
    investigation_id: str
    occurred_at: datetime
    event_type: str
    source: Optional[str] = None
    description: str
    created_at: datetime


class TimelineEventList(APIModel):
    """GET /v1/investigations/{id}/timeline"""

    items: List[TimelineEventResponse]
    total: int


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


class CommentCreate(APIModel):
    """POST /v1/investigations/{id}/comments"""

    body: str = Field(..., min_length=1, max_length=10_000)
    parent_id: Optional[str] = Field(
        default=None,
        description="ID of the comment being replied to.",
    )


class CommentResponse(APIModel):
    """A single comment."""

    id: str
    investigation_id: str
    org_id: str
    author_id: Optional[str] = None
    body: str
    parent_id: Optional[str] = None
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Re-exports for convenience
# ---------------------------------------------------------------------------

__all__ = [
    # Base / utilities
    "APIModel",
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
    # Auth
    "ActivateRequest",
    "ActivateResponse",
    "RefreshRequest",
    "RefreshResponse",
    "SessionStatusResponse",
    # License
    "LicenseStatusResponse",
    # Investigations
    "InvestigationCreate",
    "InvestigationUpdate",
    "InvestigationResponse",
    "InvestigationList",
    "InvestigationMergeRequest",
    # Evidence
    "EvidenceItemResponse",
    "EvidenceList",
    # Hypotheses
    "HypothesisResponse",
    "HypothesisList",
    "HypothesisStatusUpdate",
    # Actions
    "ActionCandidateResponse",
    "DryRunResponse",
    "ActionApproveRequest",
    "ActionRunRequest",
    "ActionResponse",
    # Webhooks
    "WebhookIntakeRecord",
    "WebhookIntakeResponse",
    # Service mappings
    "ServiceNodeCreate",
    "ServiceEdgeCreate",
    "ServiceMappingCreate",
    "ServiceNodeResponse",
    "ServiceEdgeResponse",
    "ServiceMappingResponse",
    "DiscoveryResponse",
    # Export
    "ExportRequest",
    "ExportResponse",
    # Baseline
    "BaselineSelectRequest",
    "BaselineResponse",
    "ComparisonResponse",
    # Dedup
    "DedupCheckResponse",
    # Admin
    "RetentionPolicyUpdate",
    "RetentionPolicyResponse",
    # Timeline
    "TimelineEventResponse",
    "TimelineEventList",
    # Comments
    "CommentCreate",
    "CommentResponse",
]
