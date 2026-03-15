"""
GET /v1/history — paginated investigation history for org.

Query params:
  limit      int  (default 20, max 100)
  offset     int  (default 0)
  status     str  (filter: completed|failed|queued|running)
  service    str  (filter by service_name)
  since      str  (ISO8601)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request

from backend.app.auth import check_rate_limit
from backend.app.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history")
async def get_history(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    service: Optional[str] = None,
    since: Optional[str] = None,
):
    """Return paginated investigation history."""
    org_id = request.state.org_id
    check_rate_limit(org_id, "history")

    limit = min(limit, 100)
    conn = get_conn()
    try:
        set_org_context(conn, org_id)

        # Build query dynamically
        filters = ["org_id = %s"]
        params: list = [org_id]

        if status:
            filters.append("status = %s")
            params.append(status)
        if service:
            filters.append("service_name = %s")
            params.append(service)
        if since:
            filters.append("queued_at >= %s::timestamptz")
            params.append(since)

        where = " AND ".join(filters)

        with conn.cursor() as cur:
            # Total count
            cur.execute(f"SELECT COUNT(*) FROM investigations WHERE {where}", params)
            total = cur.fetchone()[0]

            # Page
            cur.execute(
                f"""SELECT id, status, trigger_ref, trigger_source, service_name,
                           failure_class, top_confidence, top_pr_url,
                           duration_ms, queued_at, feedback
                    FROM investigations
                    WHERE {where}
                    ORDER BY queued_at DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset],
            )
            rows = cur.fetchall()

        items = [
            {
                "investigation_id": r[0],
                "status": r[1],
                "trigger_ref": r[2],
                "trigger_source": r[3],
                "service_name": r[4],
                "failure_class": r[5],
                "top_confidence": float(r[6]) if r[6] is not None else None,
                "top_pr_url": r[7],
                "duration_ms": r[8],
                "queued_at": r[9].isoformat() if r[9] else None,
                "feedback": r[10],
            }
            for r in rows
        ]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }
    finally:
        release_conn(conn)
