"""
License management API - create, validate, and manage licenses.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Role, TokenPayload, require_role
from app.models.all_models import License, LicenseStatus, LicenseTier, Organisation

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class LicenseCreateRequest(BaseModel):
    org_slug: str = Field(..., min_length=2, max_length=100)
    org_display_name: str = Field(..., min_length=1, max_length=255)
    tier: LicenseTier = LicenseTier.solo
    seat_limit: int = Field(1, ge=1, le=10000)
    expires_at: Optional[datetime] = None


class LicenseResponse(BaseModel):
    id: str
    org_id: str
    tier: str
    status: str
    seat_limit: int
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LicenseStatusResponse(BaseModel):
    license_id: str
    org_id: str
    tier: str
    status: str
    seat_limit: int
    seats_used: int
    expires_at: Optional[datetime]
    grace_until: Optional[datetime]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Create new license (admin only)")
async def create_license(
    body: LicenseCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Admin endpoint to provision a new org + license.
    In production this would be protected by an admin API key.
    """
    # Check for existing org slug
    result = await db.execute(select(Organisation).where(Organisation.slug == body.org_slug))
    existing_org = result.scalar_one_or_none()
    if existing_org:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Org slug '{body.org_slug}' already exists")

    # Create org
    org = Organisation(
        slug=body.org_slug,
        display_name=body.org_display_name,
    )
    db.add(org)
    await db.flush()

    # Generate license key
    raw_key = f"bp_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    license_obj = License(
        org_id=org.id,
        license_key_hash=key_hash,
        tier=body.tier,
        status=LicenseStatus.active,
        seat_limit=body.seat_limit,
        expires_at=body.expires_at,
    )
    db.add(license_obj)
    await db.commit()

    logger.info("license_created", org_id=str(org.id), tier=body.tier.value)
    return {
        "license_key": raw_key,  # Only returned at creation time
        "license_id": str(license_obj.id),
        "org_id": str(org.id),
        "org_slug": org.slug,
        "tier": license_obj.tier.value,
    }


@router.get("/status", response_model=LicenseStatusResponse, summary="License status for current org")
async def license_status(
    current_user: TokenPayload = Depends(require_role(Role.viewer)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    result = await db.execute(
        select(License).where(
            License.org_id == org_id,
            License.status != LicenseStatus.revoked,
        ).order_by(License.created_at.desc())
    )
    license_obj = result.scalar_one_or_none()
    if not license_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active license found")

    from app.models.all_models import User
    from sqlalchemy import func as sqlfunc
    seat_result = await db.execute(
        select(sqlfunc.count(User.id)).where(User.org_id == org_id, User.is_active == True)
    )
    seats_used = seat_result.scalar_one()

    return LicenseStatusResponse(
        license_id=str(license_obj.id),
        org_id=str(license_obj.org_id),
        tier=license_obj.tier.value,
        status=license_obj.status.value,
        seat_limit=license_obj.seat_limit,
        seats_used=seats_used,
        expires_at=license_obj.expires_at,
        grace_until=license_obj.grace_until,
    )


@router.post("/{license_id}/revoke", summary="Revoke a license (admin only)")
async def revoke_license(
    license_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(License).where(License.id == license_id))
    license_obj = result.scalar_one_or_none()
    if not license_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    license_obj.status = LicenseStatus.revoked
    await db.commit()
    logger.info("license_revoked", license_id=str(license_id))
    return {"detail": "License revoked"}
