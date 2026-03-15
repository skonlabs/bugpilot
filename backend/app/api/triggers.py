"""
Trigger management endpoints:

  GET  /v1/triggers/pending            — list pending triggers for org
  POST /v1/triggers/{id}/ack           — acknowledge (start processing) a trigger
  POST /v1/triggers/{id}/skip          — skip a trigger with reason
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.app.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)
router = APIRouter()


class SkipRequest(BaseModel):
    reason: str
    skipped_by: Optional[str] = None


@router.get("/triggers/pending")
async def list_pending_triggers(request: Request, limit: int = 50):
    """List pending triggers for the org (newest first)."""
    org_id = request.state.org_id
    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, source, external_id, summary, service_name,
                          status, created_at
                   FROM triggers
                   WHERE org_id = %s AND status = 'pending'
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (org_id, min(limit, 200)),
            )
            rows = cur.fetchall()
        return [
            {
                "trigger_id": str(r[0]),
                "source": r[1],
                "external_id": r[2],
                "summary": r[3],
                "service_name": r[4],
                "status": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]
    finally:
        release_conn(conn)


@router.post("/triggers/{trigger_id}/ack")
async def ack_trigger(trigger_id: str, request: Request):
    """Acknowledge a trigger — marks it processing and creates an investigation."""
    org_id = request.state.org_id
    conn = get_conn()
    try:
        set_org_context(conn, org_id)

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE triggers
                   SET status = 'processing', updated_at = NOW()
                   WHERE id = %s AND org_id = %s AND status = 'pending'
                   RETURNING source, external_id, summary, service_name, payload""",
                (trigger_id, org_id),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Trigger not found or already processed",
            )

        source, external_id, summary, service_name, payload = row
        conn.commit()

        # Enqueue investigation
        from backend.app.services.queue import enqueue_investigation
        inv_id = enqueue_investigation(
            org_id=org_id,
            trigger_type="webhook",
            trigger_ref=external_id,
            trigger_source=source,
            service_name=service_name,
            window_minutes=30,
            since=None,
            suppress_slack=False,
            text=summary,
        )

        # Link trigger to investigation
        conn2 = get_conn()
        try:
            set_org_context(conn2, org_id)
            with conn2.cursor() as cur:
                cur.execute(
                    "UPDATE triggers SET investigation_id = %s, status = 'done' "
                    "WHERE id = %s",
                    (inv_id, trigger_id),
                )
            conn2.commit()
        finally:
            release_conn(conn2)

        return {"trigger_id": trigger_id, "investigation_id": inv_id}

    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


@router.post("/triggers/{trigger_id}/skip")
async def skip_trigger(trigger_id: str, req: SkipRequest, request: Request):
    """Skip a trigger with a reason."""
    org_id = request.state.org_id
    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE triggers
                   SET status = 'skipped', skip_reason = %s, updated_at = NOW()
                   WHERE id = %s AND org_id = %s AND status = 'pending'""",
                (req.reason, trigger_id, org_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Trigger not found or not pending")
        conn.commit()
        return {"status": "skipped", "trigger_id": trigger_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
