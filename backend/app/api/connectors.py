"""
Connector management endpoints:

  GET    /v1/connectors                    — list all connectors for org
  POST   /v1/connectors/{type}             — add or update connector
  DELETE /v1/connectors/{type}/{name}      — remove connector
  POST   /v1/connectors/github/index       — trigger GitHub PR index
  GET    /v1/connectors/{type}/{name}/health — health check a connector
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import boto3
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.app.database import get_conn, release_conn, set_org_context
from backend.app.services.secrets import delete_secret, put_secret

log = logging.getLogger(__name__)
router = APIRouter()

VALID_CONNECTOR_TYPES = {
    "github", "jira", "freshdesk", "email_imap", "linear",
    "github_issues", "sentry", "database", "log_files",
    "datadog", "pagerduty", "langsmith", "confluence", "slack",
}


class ConnectorRequest(BaseModel):
    name: str = "default"
    config: dict[str, Any]
    service_map: dict[str, Any] = {}
    role: Optional[str] = None          # blast_radius | error_log_table | both


@router.get("/connectors")
async def list_connectors(request: Request):
    """List all connectors registered for the org."""
    org_id = request.state.org_id
    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, type, name, status, service_map, role,
                          last_health_check, health_details
                   FROM connectors
                   WHERE org_id = %s
                   ORDER BY type, name""",
                (org_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "type": r[1],
                "name": r[2],
                "status": r[3],
                "service_map": r[4] or {},
                "role": r[5],
                "last_health_check": r[6].isoformat() if r[6] else None,
                "health_details": r[7] or {},
            }
            for r in rows
        ]
    finally:
        release_conn(conn)


@router.post("/connectors/{connector_type}")
async def upsert_connector(
    connector_type: str, req: ConnectorRequest, request: Request
):
    """Add or update a connector. Config is stored encrypted in Secrets Manager."""
    org_id = request.state.org_id

    if connector_type not in VALID_CONNECTOR_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown connector type: {connector_type}")

    # Store credentials in Secrets Manager
    put_secret(org_id, connector_type, req.name, req.config)

    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO connectors (org_id, type, name, service_map, role, status)
                   VALUES (%s, %s, %s, %s::jsonb, %s, 'pending')
                   ON CONFLICT (org_id, type, name)
                   DO UPDATE SET
                     service_map = EXCLUDED.service_map,
                     role = COALESCE(EXCLUDED.role, connectors.role),
                     status = 'pending',
                     updated_at = NOW()
                   RETURNING id""",
                (org_id, connector_type, req.name,
                 json.dumps(req.service_map),
                 req.role),
            )
            connector_id = cur.fetchone()[0]
        conn.commit()
        return {"connector_id": str(connector_id), "status": "pending"}
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


@router.delete("/connectors/{connector_type}/{name}")
async def delete_connector(connector_type: str, name: str, request: Request):
    """Remove a connector and its stored credentials."""
    org_id = request.state.org_id

    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM connectors WHERE org_id = %s AND type = %s AND name = %s",
                (org_id, connector_type, name),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Connector not found")
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)

    # Remove from Secrets Manager (best-effort)
    try:
        delete_secret(org_id, connector_type, name)
    except Exception as e:
        log.warning(f"Failed to delete secret for {connector_type}/{name}: {e}")

    return {"status": "deleted"}


@router.post("/connectors/github/index")
async def trigger_github_index(request: Request):
    """Trigger a GitHub PR index job for all configured GitHub connectors."""
    org_id = request.state.org_id

    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM connectors WHERE org_id = %s AND type = 'github'",
                (org_id,),
            )
            connectors = cur.fetchall()
    finally:
        release_conn(conn)

    if not connectors:
        raise HTTPException(status_code=404, detail="No GitHub connectors configured")

    sqs_p2_url = os.environ.get("SQS_P2_URL", "")
    if not sqs_p2_url:
        raise HTTPException(status_code=503, detail="SQS queue not configured")

    sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    queued = []
    for cid, cname in connectors:
        msg = {
            "job_type": "github_index",
            "org_id": org_id,
            "connector_id": str(cid),
            "connector_name": cname,
        }
        sqs.send_message(
            QueueUrl=sqs_p2_url,
            MessageBody=json.dumps(msg),
            MessageGroupId=org_id,
            MessageDeduplicationId=f"idx-{cid}",
        )
        queued.append(cname)

    return {"status": "queued", "connectors": queued}


@router.get("/connectors/{connector_type}/{name}/health")
async def connector_health(connector_type: str, name: str, request: Request):
    """Run a live health check against a connector and update its status."""
    org_id = request.state.org_id

    # Load credentials
    from backend.app.services.secrets import get_secret
    try:
        config = get_secret(org_id, connector_type, name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Connector credentials not found")

    # Run live health check
    from connectors.registry import get_connector
    try:
        instance = get_connector(connector_type, config, org_id, name)
        health = instance.health_check()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Health check error for {connector_type}/{name}: {e}")
        health = type("H", (), {"status": "error", "message": str(e), "details": {}})()

    # Persist result to DB
    db_status = health.status if health.status in ("healthy", "degraded") else "error"
    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE connectors
                   SET status = %s,
                       last_health_check = NOW(),
                       health_details = %s::jsonb
                   WHERE org_id = %s AND type = %s AND name = %s""",
                (
                    db_status,
                    json.dumps({"message": health.message, "details": getattr(health, "details", {})}),
                    org_id, connector_type, name,
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning(f"Failed to persist health check result: {e}")
    finally:
        release_conn(conn)

    return {
        "connector_type": connector_type,
        "name": name,
        "status": db_status,
        "message": health.message,
        "details": getattr(health, "details", {}),
    }
