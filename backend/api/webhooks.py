"""
Webhook ingestion endpoints (bypass Bearer auth — use secret params or HMAC).

  POST /v1/webhooks/jira
  POST /v1/webhooks/freshdesk
  POST /v1/webhooks/sentry
  POST /v1/webhooks/slack

Each webhook:
1. Validates the request signature / secret param
2. Upserts a trigger row (status=pending)
3. Returns 200 immediately

The worker picks up pending triggers and converts them to investigations.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.database import get_conn, release_conn

log = logging.getLogger(__name__)
router = APIRouter()


def _upsert_trigger(
    conn,
    org_id: str,
    source: str,
    external_id: str,
    payload: dict,
    summary: str,
    service_name: Optional[str] = None,
) -> str:
    """Insert trigger if not already present. Returns trigger id."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO triggers
               (org_id, source, external_id, payload, summary, service_name, status)
               VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'pending')
               ON CONFLICT (org_id, source, external_id) DO NOTHING
               RETURNING id""",
            (org_id, source, external_id, json.dumps(payload), summary, service_name),
        )
        row = cur.fetchone()
    return str(row[0]) if row else "duplicate"


def _lookup_org_by_webhook_secret(conn, source: str, secret: str) -> Optional[str]:
    """Find org_id matching webhook secret stored in connector config."""
    # Webhook secrets are stored in connector rows' health_details or config
    # For now we look up the connector by source type and match secret from env
    # In production this would validate against the connector's stored secret.
    # Simple approach: secret must match env var WEBHOOK_SECRET_{SOURCE.upper()}
    expected = os.environ.get(f"WEBHOOK_SECRET_{source.upper()}", "")
    if expected and hmac.compare_digest(secret, expected):
        # Return a known org_id from env for single-tenant dev; real impl queries DB
        return os.environ.get("WEBHOOK_ORG_ID")
    return None


# ── Jira ──────────────────────────────────────────────────────────────────────

@router.post("/webhooks/jira")
async def jira_webhook(request: Request):
    secret = request.query_params.get("secret", "")
    body = await request.json()

    event = body.get("webhookEvent", "")
    issue = body.get("issue", {})
    issue_key = issue.get("key", str(uuid.uuid4()))
    summary = issue.get("fields", {}).get("summary", "Jira issue")
    service_name = None
    labels = issue.get("fields", {}).get("labels", [])
    if labels:
        service_name = labels[0]

    conn = get_conn()
    try:
        org_id = _lookup_org_by_webhook_secret(conn, "jira", secret)
        if not org_id:
            return JSONResponse({"error": "invalid_secret"}, status_code=401)

        trigger_id = _upsert_trigger(
            conn, org_id, "jira", issue_key, body, summary, service_name
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)

    return {"status": "accepted", "trigger_id": trigger_id}


# ── Freshdesk ─────────────────────────────────────────────────────────────────

@router.post("/webhooks/freshdesk")
async def freshdesk_webhook(request: Request):
    secret = request.query_params.get("secret", "")
    body = await request.json()

    ticket = body.get("ticket", {})
    ticket_id = str(ticket.get("id", uuid.uuid4()))
    subject = ticket.get("subject", "Freshdesk ticket")
    tags = ticket.get("tags", [])
    service_name = tags[0] if tags else None

    conn = get_conn()
    try:
        org_id = _lookup_org_by_webhook_secret(conn, "freshdesk", secret)
        if not org_id:
            return JSONResponse({"error": "invalid_secret"}, status_code=401)

        trigger_id = _upsert_trigger(
            conn, org_id, "freshdesk", ticket_id, body, subject, service_name
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)

    return {"status": "accepted", "trigger_id": trigger_id}


# ── Sentry ────────────────────────────────────────────────────────────────────

@router.post("/webhooks/sentry")
async def sentry_webhook(request: Request):
    # Sentry uses a shared secret in Authorization header
    auth = request.headers.get("Authorization", "")
    secret = auth.removeprefix("Bearer ").strip()

    body = await request.json()
    event = body.get("data", {}).get("event", {})
    event_id = event.get("event_id", str(uuid.uuid4()))
    title = event.get("title", "Sentry issue")
    project = event.get("project", None)

    conn = get_conn()
    try:
        org_id = _lookup_org_by_webhook_secret(conn, "sentry", secret)
        if not org_id:
            return JSONResponse({"error": "invalid_secret"}, status_code=401)

        trigger_id = _upsert_trigger(
            conn, org_id, "sentry", event_id, body, title, project
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)

    return {"status": "accepted", "trigger_id": trigger_id}


# ── Slack ─────────────────────────────────────────────────────────────────────

def _verify_slack_signature(body_bytes: bytes, timestamp: str, signature: str) -> bool:
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        return False
    base = f"v0:{timestamp}:{body_bytes.decode()}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/slack")
async def slack_webhook(request: Request):
    body_bytes = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_signature(body_bytes, timestamp, signature):
        return JSONResponse({"error": "invalid_signature"}, status_code=401)

    body = json.loads(body_bytes)

    # Handle Slack URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    event = body.get("event", {})
    event_id = body.get("event_id", str(uuid.uuid4()))
    text = event.get("text", "")

    # Only process messages that mention the bot with a bug keyword
    if "bug" not in text.lower() and "error" not in text.lower():
        return {"status": "ignored"}

    conn = get_conn()
    try:
        # For Slack, org lookup is by team_id
        team_id = body.get("team_id", "")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT org_id FROM connectors WHERE type = 'slack' AND "
                "config->'team_id' = %s::jsonb LIMIT 1",
                (json.dumps(team_id),),
            )
            row = cur.fetchone()

        if not row:
            return {"status": "ignored"}

        org_id = str(row[0])
        trigger_id = _upsert_trigger(
            conn, org_id, "slack", event_id, body, text[:200], None
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)

    return {"status": "accepted", "trigger_id": trigger_id}
