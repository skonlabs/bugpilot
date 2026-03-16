"""
GET /v1/keys/validate — validate an API key and record T&C acceptance.

Called by:
  - bugpilot init (Step 1/5 — API key validation)
  - Any CLI command that needs to verify key before first use

Request body (JSON):
{
  "api_key": "bp_live_...",
  "terms_accepted": true,
  "terms_version": "1.0",
  "terms_accepted_at": "2026-03-14T11:00:00Z",
  "cli_version": "v1.0.0",
  "platform": "darwin/arm64"
}

Response 200:
{
  "valid": true,
  "org_name": "Acme Corp",
  "org_id": "uuid",
  "plan": "starter"
}

Response 401: invalid or revoked key
Response 422: validation error in body
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from backend.database import get_conn, release_conn

log = logging.getLogger(__name__)
router = APIRouter()


class ValidateKeyRequest(BaseModel):
    api_key: str
    terms_accepted: bool
    terms_version: str
    terms_accepted_at: str      # ISO8601 UTC
    cli_version: str
    platform: str

    @field_validator("api_key")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        if not (v.startswith("bp_live_") or v.startswith("bp_test_")):
            raise ValueError("API key must start with bp_live_ or bp_test_")
        prefix = "bp_live_" if v.startswith("bp_live_") else "bp_test_"
        if len(v) - len(prefix) < 24:
            raise ValueError("API key suffix must be at least 24 characters")
        return v


@router.get("/keys/validate")
async def validate_key(request: Request):
    """
    Validate API key and record T&C acceptance.
    This endpoint uses Bearer auth from the auth middleware.
    The request body carries T&C acceptance details.
    """
    # The key has already been validated by auth middleware at this point.
    # We just need to record the T&C acceptance and return org info.
    org_id = request.state.org_id

    # Parse the T&C body if present
    try:
        body = await request.json()
    except Exception:
        body = {}

    terms_accepted = body.get("terms_accepted", False)
    terms_version = body.get("terms_version", "")
    terms_accepted_at = body.get("terms_accepted_at", "")
    cli_version = body.get("cli_version", "")
    platform = body.get("platform", "")

    conn = get_conn()
    try:
        # Record T&C acceptance on the org
        if terms_accepted and terms_version:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE orgs
                       SET terms_accepted = TRUE,
                           terms_accepted_at = %s::timestamptz,
                           terms_version = %s,
                           terms_cli_version = %s,
                           terms_platform = %s
                       WHERE id = %s""",
                    (
                        terms_accepted_at or None,
                        terms_version,
                        cli_version,
                        platform,
                        org_id,
                    ),
                )

        # Fetch org info
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, plan FROM orgs WHERE id = %s",
                (org_id,),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Organisation not found")

        org_name, plan = row
        conn.commit()

        return {
            "valid": True,
            "org_name": org_name,
            "org_id": org_id,
            "plan": plan,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        log.error(f"Key validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        release_conn(conn)
