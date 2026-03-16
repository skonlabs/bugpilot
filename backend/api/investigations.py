"""
Investigation endpoints:
  POST   /v1/investigations
  GET    /v1/investigations/{id}
  GET    /v1/investigations/{id}/status
  POST   /v1/investigations/{id}/feedback
  GET    /v1/investigations/{id}/blast-radius
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.auth import check_rate_limit
from backend.database import get_conn, release_conn, set_org_context
from backend.services.queue import enqueue_investigation

log = logging.getLogger(__name__)
router = APIRouter()


class InvestigationRequest(BaseModel):
    ticket_id: Optional[str] = None
    ticket_source: Optional[str] = None       # jira | freshdesk | email | sentry | slack | cli
    service_name: Optional[str] = None
    text: Optional[str] = None                 # freeform description
    since: Optional[str] = None               # ISO8601 or relative: "2h", "30m"
    layer: str = "l2"
    window_minutes: int = 30
    suppress_slack: bool = False
    dry_run: bool = False


class FeedbackRequest(BaseModel):
    feedback: str                              # confirmed | refuted
    hypothesis_rank: int = 1
    cause: Optional[str] = None               # if refuted: actual cause
    submitted_by: Optional[str] = None


@router.post("/investigations")
async def create_investigation(req: InvestigationRequest, request: Request):
    """Trigger a new investigation. Returns 202 with investigation_id."""
    org_id = request.state.org_id
    check_rate_limit(org_id, "investigations")

    # Phase guards
    if req.layer == "l1":
        raise HTTPException(status_code=400, detail="Infrastructure investigation is Phase 2.")
    if req.layer == "l3":
        raise HTTPException(status_code=400, detail="AI agent investigation is Phase 3.")

    if req.dry_run:
        # Return what would happen without executing
        return {
            "dry_run": True,
            "ticket": req.ticket_id,
            "ticket_source": req.ticket_source,
            "text": req.text,
            "layer": req.layer,
            "window_minutes": req.window_minutes,
            "estimated_seconds": 90,
        }

    # Determine trigger_type and trigger_ref
    trigger_type = "cli_manual"
    trigger_ref = req.ticket_id
    trigger_source = req.ticket_source or "cli"

    if req.text and not req.ticket_id:
        trigger_type = "cli_manual"
        trigger_ref = f"FREEFORM-{str(uuid.uuid4())[:8].upper()}"
        trigger_source = "cli"

    # Enqueue investigation job
    inv_id = enqueue_investigation(
        org_id=org_id,
        trigger_type=trigger_type,
        trigger_ref=trigger_ref,
        trigger_source=trigger_source,
        service_name=req.service_name,
        window_minutes=req.window_minutes,
        since=req.since,
        suppress_slack=req.suppress_slack,
        text=req.text,
    )

    return {"investigation_id": inv_id, "status": "queued", "estimated_seconds": 90}


@router.get("/investigations/{investigation_id}/status")
async def get_investigation_status(investigation_id: str, request: Request):
    """Poll investigation progress. Called by CLI every 2 seconds."""
    org_id = request.state.org_id
    conn = get_conn()
    try:
        set_org_context(conn, org_id)

        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, queued_at, started_at,
                          EXTRACT(EPOCH FROM (NOW() - COALESCE(started_at, queued_at)))::int
                          AS elapsed_seconds
                   FROM investigations WHERE id = %s AND org_id = %s""",
                (investigation_id, org_id),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")

        status, queued_at, started_at, elapsed = row

        with conn.cursor() as cur:
            cur.execute(
                """SELECT step, status, duration_ms
                   FROM investigation_progress
                   WHERE investigation_id = %s
                   ORDER BY started_at NULLS LAST""",
                (investigation_id,),
            )
            steps = [
                {"step": r[0], "status": r[1], "duration_ms": r[2]}
                for r in cur.fetchall()
            ]

        return {
            "investigation_id": investigation_id,
            "status": status,
            "elapsed_seconds": elapsed or 0,
            "progress": steps,
        }
    finally:
        release_conn(conn)


@router.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str, request: Request):
    """Get full investigation result."""
    org_id = request.state.org_id
    conn = get_conn()
    try:
        set_org_context(conn, org_id)

        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, status, trigger_ref, trigger_source, service_name,
                          failure_class, duration_ms, llm_narrative,
                          top_pr_id, top_pr_url, top_file, top_line,
                          top_confidence, top_diff_type,
                          blast_count, blast_value_usd, blast_cohort, blast_status,
                          window_start, window_end,
                          connectors_used, connectors_missing,
                          feedback, feedback_at, feedback_by, feedback_cause,
                          error_message, error_code
                   FROM investigations
                   WHERE id = %s AND org_id = %s""",
                (investigation_id, org_id),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")

        cols = [
            "id", "status", "trigger_ref", "trigger_source", "service_name",
            "failure_class", "duration_ms", "llm_narrative",
            "top_pr_id", "top_pr_url", "top_file", "top_line",
            "top_confidence", "top_diff_type",
            "blast_count", "blast_value_usd", "blast_cohort", "blast_status",
            "window_start", "window_end",
            "connectors_used", "connectors_missing",
            "feedback", "feedback_at", "feedback_by", "feedback_cause",
            "error_message", "error_code",
        ]
        inv = dict(zip(cols, row))

        # Fetch all hypotheses
        with conn.cursor() as cur:
            cur.execute(
                """SELECT rank, pr_id, pr_url, pr_title, pr_author, pr_merged_at,
                          file_path, line_number, diff_type, confidence,
                          feature_scores, evidence, conflict_note
                   FROM investigation_hypotheses
                   WHERE investigation_id = %s
                   ORDER BY rank""",
                (investigation_id,),
            )
            hyp_rows = cur.fetchall()

        hypotheses = []
        for h in hyp_rows:
            hypotheses.append({
                "rank": h[0], "pr_id": h[1], "pr_url": h[2],
                "pr_title": h[3], "pr_author": h[4],
                "pr_merged_at": h[5].isoformat() if h[5] else None,
                "file_path": h[6], "line_number": h[7],
                "diff_type": h[8],
                "confidence": float(h[9]) if h[9] is not None else None,
                "narrative": inv.get("llm_narrative") if h[0] == 1 else None,
                "feature_scores": h[10],
                "evidence": h[11],
                "conflict_note": h[12],
            })

        result = {
            "investigation_id": inv["id"],
            "status": inv["status"],
            "trigger_ref": inv["trigger_ref"],
            "trigger_source": inv["trigger_source"],
            "service_name": inv["service_name"],
            "failure_class": inv["failure_class"],
            "duration_ms": inv["duration_ms"],
            "hypotheses": hypotheses,
        }

        if inv["blast_count"] is not None:
            result["blast_radius"] = {
                "count": inv["blast_count"],
                "value_usd": float(inv["blast_value_usd"]) if inv["blast_value_usd"] else None,
                "cohort": inv["blast_cohort"],
                "window_start": inv["window_start"].isoformat() if inv["window_start"] else None,
                "window_end": inv["window_end"].isoformat() if inv["window_end"] else None,
                "status": inv["blast_status"],
                "method": "database_query",
            }

        result["connectors_used"] = inv["connectors_used"] or []
        result["connectors_missing"] = inv["connectors_missing"] or []
        result["connector_warnings"] = []

        if inv["error_message"]:
            result["error_message"] = inv["error_message"]
            result["error_code"] = inv["error_code"]

        return result
    finally:
        release_conn(conn)


@router.post("/investigations/{investigation_id}/feedback")
async def submit_feedback(
    investigation_id: str, req: FeedbackRequest, request: Request
):
    """Submit confirm or refute feedback. Triggers model update."""
    org_id = request.state.org_id

    if req.feedback not in ("confirmed", "refuted"):
        raise HTTPException(status_code=422, detail="feedback must be 'confirmed' or 'refuted'")

    conn = get_conn()
    try:
        set_org_context(conn, org_id)

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE investigations
                   SET feedback = %s,
                       feedback_at = NOW(),
                       feedback_by = %s,
                       feedback_cause = %s
                   WHERE id = %s AND org_id = %s""",
                (req.feedback, req.submitted_by, req.cause, investigation_id, org_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Investigation not found")

        # Fetch the top hypothesis feature_scores to save as training data
        with conn.cursor() as cur:
            cur.execute(
                """SELECT h.feature_scores, h.pr_id, h.rank
                   FROM investigation_hypotheses h
                   WHERE h.investigation_id = %s AND h.rank = %s""",
                (investigation_id, req.hypothesis_rank),
            )
            hyp_row = cur.fetchone()

        if hyp_row:
            feature_scores, top_pr_id, hyp_rank = hyp_row
            label = 1 if req.feedback == "confirmed" else 0
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO training_data
                       (org_id, investigation_id, feature_vector, label, hypothesis_rank)
                       VALUES (%s, %s, %s::jsonb, %s, %s)
                       ON CONFLICT DO NOTHING""",
                    (
                        org_id,
                        investigation_id,
                        json.dumps(feature_scores or {}),
                        label,
                        hyp_rank,
                    ),
                )

            # Update AGE graph: mark PR as confirmed/refuted for author risk scoring
            if top_pr_id:
                try:
                    from worker.app.graph_builder import set_pr_confirmed
                    set_pr_confirmed(
                        conn, org_id, top_pr_id,
                        confirmed=(req.feedback == "confirmed"),
                    )
                except Exception as e:
                    log.warning(f"AGE graph update error on feedback: {e}")

        conn.commit()

        # Trigger async model retraining (best-effort, non-blocking)
        if hyp_row:
            def _retrain(org: str) -> None:
                import os
                import redis as redis_lib
                from worker.app.hypothesis_ranker import train_model
                train_conn = get_conn()
                try:
                    redis_client = redis_lib.Redis.from_url(
                        os.environ["REDIS_URL"], decode_responses=True
                    )
                    train_model(org, train_conn, redis_client)
                except Exception as exc:
                    log.warning(f"Background model retrain error: {exc}")
                finally:
                    release_conn(train_conn)

            try:
                t = threading.Thread(target=_retrain, args=(org_id,), daemon=True)
                t.start()
            except Exception as e:
                log.warning(f"Model retrain trigger error: {e}")

        return {"status": "recorded", "investigation_id": investigation_id}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


@router.get("/investigations/{investigation_id}/blast-radius")
async def get_blast_radius(investigation_id: str, request: Request):
    """
    Return blast radius as CSV stream.
    Columns: record_id_hash, entity_type, affected_field, expected_value, actual_value, created_at
    record_id_hash = SHA256 of raw record ID (privacy).
    """
    org_id = request.state.org_id

    def generate_csv():
        yield "record_id_hash,entity_type,affected_field,expected_value,actual_value,created_at\n"
        # Actual rows come from the database connector blast radius data
        # stored during investigation. This is a placeholder that returns
        # the summary row for now — full implementation in database connector.
        conn = get_conn()
        try:
            set_org_context(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT blast_count, blast_cohort, blast_value_usd "
                    "FROM investigations WHERE id = %s AND org_id = %s",
                    (investigation_id, org_id),
                )
                row = cur.fetchone()
            if row and row[0]:
                count, cohort, value_usd = row
                yield (
                    f"{hashlib.sha256(investigation_id.encode()).hexdigest()[:16]},"
                    f"investigation,blast_radius_count,{cohort or ''},"
                    f"{count},{value_usd or ''}\n"
                )
        finally:
            release_conn(conn)

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={investigation_id}-blast-radius.csv"},
    )
