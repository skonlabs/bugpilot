"""
Admin API - organization management, user management, audit logs, connectors.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Permission, Role, TokenPayload, require_permission, require_role
from app.core.security import encrypt_credentials, decrypt_credentials
from app.models.all_models import (
    AuditLog,
    Connector,
    ConnectorKind,
    Organisation,
    User,
    Webhook,
    WebhookDelivery,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class OrgSettingsUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    settings: Optional[Dict[str, Any]] = None


class OrgOut(BaseModel):
    id: str
    slug: str
    display_name: str
    settings: Dict[str, Any]
    created_at: datetime


class UserOut(BaseModel):
    id: str
    org_id: str
    email: str
    display_name: Optional[str]
    role: str
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: Role


class ConnectorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: ConnectorKind
    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ConnectorOut(BaseModel):
    id: str
    org_id: str
    name: str
    kind: str
    is_enabled: bool
    config: Dict[str, Any]
    last_tested_at: Optional[datetime]
    last_test_success: Optional[bool]
    created_at: datetime
    updated_at: datetime


class ConnectorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., max_length=2048)
    secret: Optional[str] = None
    events: List[str] = Field(..., min_length=1)
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)


class WebhookOut(BaseModel):
    id: str
    org_id: str
    name: str
    url: str
    events: List[str]
    is_enabled: bool
    headers: Dict[str, str]
    created_at: datetime


class AuditLogOut(BaseModel):
    id: str
    org_id: str
    actor_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ser_org(o: Organisation) -> OrgOut:
    return OrgOut(
        id=str(o.id),
        slug=o.slug,
        display_name=o.display_name,
        settings=o.settings or {},
        created_at=o.created_at,
    )


def _ser_user(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        org_id=str(u.org_id),
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        is_active=u.is_active,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


def _ser_connector(c: Connector) -> ConnectorOut:
    return ConnectorOut(
        id=str(c.id),
        org_id=str(c.org_id),
        name=c.name,
        kind=c.kind.value,
        is_enabled=c.is_enabled,
        config=c.config or {},
        last_tested_at=c.last_tested_at,
        last_test_success=c.last_test_success,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _ser_webhook(w: Webhook) -> WebhookOut:
    return WebhookOut(
        id=str(w.id),
        org_id=str(w.org_id),
        name=w.name,
        url=w.url,
        events=w.events or [],
        is_enabled=w.is_enabled,
        headers=w.headers or {},
        created_at=w.created_at,
    )


# ---------------------------------------------------------------------------
# Org routes
# ---------------------------------------------------------------------------
@router.get("/org", response_model=OrgOut, summary="Get current org")
async def get_org(
    current_user: TokenPayload = Depends(require_role(Role.viewer)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Organisation).where(Organisation.id == uuid.UUID(current_user.org_id))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return _ser_org(org)


@router.patch("/org", response_model=OrgOut, summary="Update org settings")
async def update_org(
    body: OrgSettingsUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_org_settings)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Organisation).where(Organisation.id == uuid.UUID(current_user.org_id))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    if body.display_name:
        org.display_name = body.display_name
    if body.settings is not None:
        org.settings = {**(org.settings or {}), **body.settings}
    await db.commit()
    await db.refresh(org)
    return _ser_org(org)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
@router.get("/users", response_model=List[UserOut], summary="List users in org")
async def list_users(
    current_user: TokenPayload = Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.org_id == uuid.UUID(current_user.org_id)).order_by(User.email)
    )
    return [_ser_user(u) for u in result.scalars().all()]


@router.patch("/users/{user_id}/role", response_model=UserOut, summary="Update user role")
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_roles)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.org_id == uuid.UUID(current_user.org_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = body.role.value
    await db.commit()
    await db.refresh(user)
    logger.info("user_role_updated", target_user_id=str(user_id), new_role=body.role.value)
    return _ser_user(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate user")
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.org_id == uuid.UUID(current_user.org_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if str(user.id) == current_user.sub:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")
    user.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------
@router.get("/connectors", response_model=List[ConnectorOut], summary="List connectors")
async def list_connectors(
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(Connector.org_id == uuid.UUID(current_user.org_id)).order_by(Connector.name)
    )
    return [_ser_connector(c) for c in result.scalars().all()]


@router.post("/connectors", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED, summary="Add connector")
async def create_connector(
    body: ConnectorCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    creds_enc = None
    if body.credentials:
        creds_enc = encrypt_credentials(body.credentials)

    connector = Connector(
        org_id=org_id,
        name=body.name,
        kind=body.kind,
        credentials_enc=creds_enc,
        config=body.config or {},
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    logger.info("connector_created", connector_id=str(connector.id), kind=body.kind.value)
    return _ser_connector(connector)


@router.get("/connectors/{connector_id}", response_model=ConnectorOut, summary="Get connector")
async def get_connector(
    connector_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id, Connector.org_id == uuid.UUID(current_user.org_id))
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    return _ser_connector(c)


@router.patch("/connectors/{connector_id}", response_model=ConnectorOut, summary="Update connector")
async def update_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id, Connector.org_id == uuid.UUID(current_user.org_id))
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    if body.name is not None:
        c.name = body.name
    if body.is_enabled is not None:
        c.is_enabled = body.is_enabled
    if body.config is not None:
        c.config = {**(c.config or {}), **body.config}
    if body.credentials is not None:
        c.credentials_enc = encrypt_credentials(body.credentials)

    await db.commit()
    await db.refresh(c)
    return _ser_connector(c)


@router.delete("/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete connector")
async def delete_connector(
    connector_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id, Connector.org_id == uuid.UUID(current_user.org_id))
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    await db.delete(c)
    await db.commit()


@router.post("/connectors/{connector_id}/test", summary="Test connector connectivity")
async def test_connector(
    connector_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    result = await db.execute(
        select(Connector).where(Connector.id == connector_id, Connector.org_id == uuid.UUID(current_user.org_id))
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    # Placeholder connectivity test - in production this would dispatch to connector-specific logic
    c.last_tested_at = datetime.now(timezone.utc)
    c.last_test_success = True
    await db.commit()
    return {"status": "ok", "connector_id": str(connector_id), "kind": c.kind.value}


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------
@router.get("/webhooks", response_model=List[WebhookOut], summary="List webhooks")
async def list_webhooks(
    current_user: TokenPayload = Depends(require_permission(Permission.manage_webhooks)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.org_id == uuid.UUID(current_user.org_id))
    )
    return [_ser_webhook(w) for w in result.scalars().all()]


@router.post("/webhooks", response_model=WebhookOut, status_code=status.HTTP_201_CREATED, summary="Create webhook")
async def create_webhook(
    body: WebhookCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_webhooks)),
    db: AsyncSession = Depends(get_db),
):
    import hashlib
    org_id = uuid.UUID(current_user.org_id)
    secret_hash = None
    if body.secret:
        secret_hash = hashlib.sha256(body.secret.encode()).hexdigest()

    w = Webhook(
        org_id=org_id,
        name=body.name,
        url=body.url,
        secret_hash=secret_hash,
        events=body.events,
        headers=body.headers or {},
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return _ser_webhook(w)


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete webhook")
async def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_webhooks)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.org_id == uuid.UUID(current_user.org_id))
    )
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await db.delete(w)
    await db.commit()


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------
@router.get("/audit-logs", response_model=List[AuditLogOut], summary="List audit logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: TokenPayload = Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    query = (
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    logs = result.scalars().all()
    return [
        AuditLogOut(
            id=str(al.id),
            org_id=str(al.org_id),
            actor_id=str(al.actor_id) if al.actor_id else None,
            action=al.action,
            resource_type=al.resource_type,
            resource_id=al.resource_id,
            ip_address=al.ip_address,
            created_at=al.created_at,
        )
        for al in logs
    ]
