"""
Authentication API - device-based CLI auth with license key activation.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rbac import get_current_user, Role
from app.core.security import (
    TokenPayload,
    create_session_token,
    hash_token,
    verify_session_token,
)
from app.models.all_models import License, LicenseStatus, Organisation, Session, User

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ActivateRequest(BaseModel):
    license_key: str = Field(..., min_length=16, max_length=128)
    email: EmailStr
    device_fp: str = Field(..., min_length=8, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)


class ActivateResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    org_id: str
    user_id: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class WhoAmIResponse(BaseModel):
    user_id: str
    org_id: str
    email: str
    display_name: Optional[str]
    role: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_license_key(key: str) -> str:
    return hashlib.sha256(key.strip().encode()).hexdigest()


async def _get_valid_license(db: AsyncSession, key_hash: str) -> License:
    result = await db.execute(select(License).where(License.license_key_hash == key_hash))
    license_obj = result.scalar_one_or_none()
    if not license_obj:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid license key")
    now = datetime.now(timezone.utc)
    if license_obj.status == LicenseStatus.revoked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="License revoked")
    if license_obj.expires_at and license_obj.expires_at < now:
        if license_obj.grace_until and license_obj.grace_until >= now:
            pass  # Allow grace period
        else:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="License expired")
    return license_obj


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/activate", response_model=ActivateResponse, summary="Activate license and get tokens")
async def activate(
    body: ActivateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a license key for an access + refresh token pair.
    Creates org/user records on first activation.
    """
    key_hash = _hash_license_key(body.license_key)
    license_obj = await _get_valid_license(db, key_hash)

    # Upsert user for this org
    result = await db.execute(
        select(User).where(
            User.org_id == license_obj.org_id,
            User.email == body.email,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        # Check seat limit
        from sqlalchemy import func as sqlfunc
        seat_count_result = await db.execute(
            select(sqlfunc.count(User.id)).where(User.org_id == license_obj.org_id, User.is_active == True)
        )
        seat_count = seat_count_result.scalar_one()
        if seat_count >= license_obj.seat_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Seat limit ({license_obj.seat_limit}) reached for this license",
            )
        user = User(
            org_id=license_obj.org_id,
            email=body.email,
            display_name=body.display_name,
            role=Role.investigator.value,
        )
        db.add(user)
        await db.flush()

    user.last_login_at = datetime.now(timezone.utc)

    jwt_token, refresh_token, token_hash, refresh_hash = create_session_token(
        user_id=str(user.id),
        org_id=str(license_obj.org_id),
        device_fp=body.device_fp,
        role=user.role,
    )

    session = Session(
        user_id=user.id,
        org_id=license_obj.org_id,
        token_hash=token_hash,
        refresh_hash=refresh_hash,
        device_fp=body.device_fp,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )
    db.add(session)
    await db.commit()

    logger.info("user_activated", user_id=str(user.id), org_id=str(license_obj.org_id))
    return ActivateResponse(
        access_token=jwt_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        org_id=str(license_obj.org_id),
        user_id=str(user.id),
        role=user.role,
    )


@router.post("/refresh", response_model=RefreshResponse, summary="Refresh access token")
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    refresh_hash = hash_token(body.refresh_token)
    result = await db.execute(
        select(Session).where(
            Session.refresh_hash == refresh_hash,
            Session.revoked == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = datetime.now(timezone.utc)
    if session.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    # Fetch user
    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Revoke old session
    session.revoked = True

    # Issue new tokens
    new_jwt, new_refresh, new_token_hash, new_refresh_hash = create_session_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        device_fp=session.device_fp or "",
        role=user.role,
    )
    new_session = Session(
        user_id=user.id,
        org_id=user.org_id,
        token_hash=new_token_hash,
        refresh_hash=new_refresh_hash,
        device_fp=session.device_fp,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        expires_at=now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )
    db.add(new_session)
    await db.commit()

    return RefreshResponse(
        access_token=new_jwt,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", summary="Revoke current session")
async def logout(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Revoke all active sessions for this user/device
    result = await db.execute(
        select(Session).where(
            Session.user_id == uuid.UUID(user.sub),
            Session.device_fp == user.device_fp,
            Session.revoked == False,
        )
    )
    sessions = result.scalars().all()
    for s in sessions:
        s.revoked = True
    await db.commit()
    logger.info("user_logged_out", user_id=user.sub)
    return {"detail": "Logged out successfully"}


@router.get("/whoami", response_model=WhoAmIResponse, summary="Current user info")
async def whoami(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(current_user.sub)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return WhoAmIResponse(
        user_id=str(user.id),
        org_id=str(user.org_id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )
