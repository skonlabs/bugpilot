"""
Org/tenant helper utilities.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)


def get_org(org_id: str) -> Optional[dict]:
    """Return org row as dict or None."""
    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, plan, terms_accepted, settings FROM orgs WHERE id = %s",
                (org_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "name": row[1],
            "plan": row[2],
            "terms_accepted": row[3],
            "settings": row[4] or {},
        }
    finally:
        release_conn(conn)


def is_plan_allowed(org_id: str, min_plan: str) -> bool:
    """Check if org's plan meets the minimum required plan tier."""
    PLAN_ORDER = ["free", "starter", "growth", "enterprise"]
    org = get_org(org_id)
    if not org:
        return False
    try:
        return PLAN_ORDER.index(org["plan"]) >= PLAN_ORDER.index(min_plan)
    except ValueError:
        return False
