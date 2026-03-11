"""Initial schema — creates all 21 BugPilot tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-10 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Alembic metadata
# ---------------------------------------------------------------------------

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enum(*values, name: str):
    """Create a reusable SA Enum type (PostgreSQL native ENUM)."""
    return sa.Enum(*values, name=name)


# ---------------------------------------------------------------------------
# upgrade — create all tables
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. PostgreSQL enum types (must be created before tables that use them)
    # ------------------------------------------------------------------
    license_tier = _enum("solo", "team", "enterprise", name="license_tier")
    license_status = _enum("active", "expired", "revoked", "grace", name="license_status")
    investigation_status = _enum("open", "in_progress", "resolved", "closed", "archived", name="investigation_status")
    severity = _enum("low", "medium", "high", "critical", name="severity")
    evidence_kind = _enum(
        "log_snapshot", "metric_snapshot", "trace", "event",
        "config_diff", "topology", "custom",
        name="evidence_kind",
    )
    hypothesis_status = _enum(
        "proposed", "testing", "confirmed", "rejected",
        name="hypothesis_status",
    )
    action_status = _enum(
        "pending", "approved", "running", "completed", "failed", "cancelled",
        name="action_status",
    )
    action_risk_level = _enum(
        "safe", "low", "medium", "high", "critical",
        name="action_risk_level",
    )
    connector_kind = _enum(
        "datadog", "newrelic", "prometheus", "grafana", "loki",
        "elasticsearch", "cloudwatch", "pagerduty", "opsgenie",
        "github", "gitlab", "jira", "linear", "slack",
        "kubernetes", "aws", "gcp", "azure", "custom",
        name="connector_kind",
    )
    node_kind = _enum(
        "service", "database", "queue", "cache", "external",
        "lambda", "container",
        name="node_kind",
    )

    # ------------------------------------------------------------------
    # Table 1: organisations
    # ------------------------------------------------------------------
    op.create_table(
        "organisations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("settings", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_organisations_slug", "organisations", ["slug"], unique=True)

    # ------------------------------------------------------------------
    # Table 2: licenses
    # ------------------------------------------------------------------
    op.create_table(
        "licenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("license_key_hash", sa.String(128), nullable=False),
        sa.Column("tier", license_tier, nullable=False),
        sa.Column("status", license_status, nullable=False, server_default="active"),
        sa.Column("seat_limit", sa.Integer, nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_licenses_org_id", "licenses", ["org_id"])
    op.create_unique_constraint("uq_licenses_key_hash", "licenses", ["license_key_hash"])

    # ------------------------------------------------------------------
    # Table 3: users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="investigator"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # ------------------------------------------------------------------
    # Table 4: sessions
    # ------------------------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("refresh_hash", sa.String(128), nullable=False),
        sa.Column("device_fp", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_org_id", "sessions", ["org_id"])
    op.create_unique_constraint("uq_sessions_token_hash", "sessions", ["token_hash"])
    op.create_unique_constraint("uq_sessions_refresh_hash", "sessions", ["refresh_hash"])

    # ------------------------------------------------------------------
    # Table 5: investigations
    # ------------------------------------------------------------------
    op.create_table(
        "investigations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("symptom", sa.Text, nullable=True),
        sa.Column("severity", severity, nullable=False, server_default="medium"),
        sa.Column("status", investigation_status, nullable=False, server_default="open"),
        sa.Column("tags", postgresql.JSONB, nullable=True, server_default="'[]'::jsonb"),
        sa.Column("context", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_investigations_org_id", "investigations", ["org_id"])
    op.create_index("ix_investigations_status", "investigations", ["status"])
    op.create_index("ix_investigations_created_at", "investigations", ["created_at"])

    # ------------------------------------------------------------------
    # Table 6: connectors  (must precede evidence which FKs to it)
    # ------------------------------------------------------------------
    op.create_table(
        "connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", connector_kind, nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("credentials_enc", sa.LargeBinary, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_success", sa.Boolean, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "name", name="uq_connectors_org_name"),
    )
    op.create_index("ix_connectors_org_id", "connectors", ["org_id"])

    # ------------------------------------------------------------------
    # Table 7: evidence
    # ------------------------------------------------------------------
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connector_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connectors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", evidence_kind, nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("source_uri", sa.String(2048), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True, server_default="'[]'::jsonb"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_evidence_investigation_id", "evidence", ["investigation_id"])
    op.create_index("ix_evidence_org_id", "evidence", ["org_id"])
    op.create_index("ix_evidence_collected_at", "evidence", ["collected_at"])

    # ------------------------------------------------------------------
    # Table 8: hypotheses
    # ------------------------------------------------------------------
    op.create_table(
        "hypotheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("status", hypothesis_status, nullable=False, server_default="proposed"),
        sa.Column("supporting_evidence", postgresql.JSONB, nullable=True, server_default="'[]'::jsonb"),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("generated_by_llm", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_hypotheses_investigation_id", "hypotheses", ["investigation_id"])
    op.create_index("ix_hypotheses_org_id", "hypotheses", ["org_id"])

    # ------------------------------------------------------------------
    # Table 9: actions
    # ------------------------------------------------------------------
    op.create_table(
        "actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "hypothesis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hypotheses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("parameters", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column("risk_level", action_risk_level, nullable=False, server_default="medium"),
        sa.Column("status", action_status, nullable=False, server_default="pending"),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "executed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("rollback_plan", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_actions_investigation_id", "actions", ["investigation_id"])
    op.create_index("ix_actions_org_id", "actions", ["org_id"])
    op.create_index("ix_actions_status", "actions", ["status"])

    # ------------------------------------------------------------------
    # Table 10: timeline_events
    # ------------------------------------------------------------------
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_timeline_events_investigation_id", "timeline_events", ["investigation_id"])
    op.create_index("ix_timeline_events_occurred_at", "timeline_events", ["occurred_at"])

    # ------------------------------------------------------------------
    # Table 11: service_maps
    # ------------------------------------------------------------------
    op.create_table(
        "service_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "name", name="uq_service_maps_org_name"),
    )
    op.create_index("ix_service_maps_org_id", "service_maps", ["org_id"])

    # ------------------------------------------------------------------
    # Table 12: service_nodes
    # ------------------------------------------------------------------
    op.create_table(
        "service_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "service_map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", node_kind, nullable=False, server_default="service"),
        sa.Column("namespace", sa.String(255), nullable=True),
        sa.Column("team", sa.String(255), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True, server_default="'[]'::jsonb"),
        sa.Column("metadata", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("service_map_id", "name", name="uq_service_nodes_map_name"),
    )
    op.create_index("ix_service_nodes_service_map_id", "service_nodes", ["service_map_id"])

    # ------------------------------------------------------------------
    # Table 13: service_edges
    # ------------------------------------------------------------------
    op.create_table(
        "service_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "service_map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("protocol", sa.String(50), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_service_edges_service_map_id", "service_edges", ["service_map_id"])
    op.create_index("ix_service_edges_source_node_id", "service_edges", ["source_node_id"])
    op.create_index("ix_service_edges_target_node_id", "service_edges", ["target_node_id"])

    # ------------------------------------------------------------------
    # Table 14: webhooks
    # ------------------------------------------------------------------
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret_hash", sa.String(128), nullable=True),
        sa.Column("events", postgresql.JSONB, nullable=False, server_default="'[]'::jsonb"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("headers", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_webhooks_org_id", "webhooks", ["org_id"])

    # ------------------------------------------------------------------
    # Table 15: webhook_deliveries
    # ------------------------------------------------------------------
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_kind", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
    op.create_index("ix_webhook_deliveries_org_id", "webhook_deliveries", ["org_id"])

    # ------------------------------------------------------------------
    # Table 16: audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("before_state", postgresql.JSONB, nullable=True),
        sa.Column("after_state", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ------------------------------------------------------------------
    # Table 17: api_keys
    # ------------------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("scopes", postgresql.JSONB, nullable=False, server_default="'[]'::jsonb"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "name", name="uq_api_keys_org_name"),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    op.create_unique_constraint("uq_api_keys_key_hash", "api_keys", ["key_hash"])

    # ------------------------------------------------------------------
    # Table 18: investigation_members
    # ------------------------------------------------------------------
    op.create_table(
        "investigation_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role_override", sa.String(50), nullable=True),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "investigation_id", "user_id", name="uq_investigation_members"
        ),
    )
    op.create_index(
        "ix_investigation_members_investigation_id",
        "investigation_members",
        ["investigation_id"],
    )

    # ------------------------------------------------------------------
    # Table 19: comments
    # ------------------------------------------------------------------
    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_comments_investigation_id", "comments", ["investigation_id"])

    # ------------------------------------------------------------------
    # Table 20: notification_subscriptions
    # ------------------------------------------------------------------
    op.create_table(
        "notification_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_types", postgresql.JSONB, nullable=False, server_default="'[]'::jsonb"),
        sa.Column("channel", sa.String(50), nullable=False, server_default="email"),
        sa.Column("channel_config", postgresql.JSONB, nullable=True, server_default="'{}'::jsonb"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "channel", name="uq_notification_subs_user_channel"
        ),
    )
    op.create_index("ix_notification_subscriptions_user_id", "notification_subscriptions", ["user_id"])

    # ------------------------------------------------------------------
    # Table 21: llm_request_logs
    # ------------------------------------------------------------------
    op.create_table(
        "llm_request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investigations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_request_logs_org_id", "llm_request_logs", ["org_id"])
    op.create_index("ix_llm_request_logs_created_at", "llm_request_logs", ["created_at"])


# ---------------------------------------------------------------------------
# downgrade — drop all tables in reverse dependency order
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Dependent tables first
    op.drop_table("llm_request_logs")
    op.drop_table("notification_subscriptions")
    op.drop_table("comments")
    op.drop_table("investigation_members")
    op.drop_table("api_keys")
    op.drop_table("audit_logs")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("service_edges")
    op.drop_table("service_nodes")
    op.drop_table("service_maps")
    op.drop_table("timeline_events")
    op.drop_table("actions")
    op.drop_table("hypotheses")
    op.drop_table("evidence")
    op.drop_table("connectors")
    op.drop_table("investigations")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("licenses")
    op.drop_table("organisations")

    # Drop enum types
    for name in [
        "node_kind",
        "connector_kind",
        "action_risk_level",
        "action_status",
        "hypothesis_status",
        "evidence_kind",
        "severity",
        "investigation_status",
        "license_status",
        "license_tier",
    ]:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
