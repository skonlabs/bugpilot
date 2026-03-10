"""
Investigations API - core investigation CRUD and lifecycle management.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Permission, Role, TokenPayload, require_permission, require_role
from app.models.all_models import Investigation, InvestigationStatus, InvestigationMember, Severity

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class InvestigationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    symptom: Optional[str] = None
    severity: Severity = Severity.medium
    tags: Optional[List[str]] = Field(default_factory=list)
    context: Optional[dict] = Field(default_factory=dict)


class InvestigationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    symptom: Optional[str] = None
    severity: Optional[Severity] = None
    status: Optional[InvestigationStatus] = None
    tags: Optional[List[str]] = None
    context: Optional[dict] = None


class InvestigationOut(BaseModel):
    id: str
    org_id: str
    created_by: Optional[str]
    title: str
    description: Optional[str]
    symptom: Optional[str]
    severity: str
    status: str
    tags: List[str]
    context: dict
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationListResponse(BaseModel):
    items: List[InvestigationOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_investigation(inv: Investigation) -> InvestigationOut:
    return InvestigationOut(
        id=str(inv.id),
        org_id=str(inv.org_id),
        created_by=str(inv.created_by) if inv.created_by else None,
        title=inv.title,
        description=inv.description,
        symptom=inv.symptom,
        severity=inv.severity,
        status=inv.status,
        tags=inv.tags or [],
        context=inv.context or {},
        resolved_at=inv.resolved_at,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


async def _get_investigation_or_404(
    investigation_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> Investigation:
    result = await db.execute(
        select(Investigation).where(
            Investigation.id == investigation_id,
            Investigation.org_id == org_id,
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    return inv


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=InvestigationListResponse, summary="List investigations")
async def list_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[List[InvestigationStatus]] = Query(None, alias="status"),
    severity_filter: Optional[Severity] = Query(None, alias="severity"),
    service: Optional[str] = Query(None, description="Filter by linked service name"),
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    query = select(Investigation).where(Investigation.org_id == org_id)

    if status_filter:
        query = query.where(Investigation.status.in_(status_filter))
    if severity_filter:
        query = query.where(Investigation.severity == severity_filter)
    if service:
        query = query.where(Investigation.linked_services.contains([service]))

    # Count total
    from sqlalchemy import func as sqlfunc
    count_query = select(sqlfunc.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginate
    query = query.order_by(Investigation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return InvestigationListResponse(
        items=[_serialize_investigation(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=InvestigationOut, status_code=status.HTTP_201_CREATED, summary="Create investigation")
async def create_investigation(
    body: InvestigationCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.create_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    user_id = uuid.UUID(current_user.sub)

    inv = Investigation(
        org_id=org_id,
        created_by=user_id,
        title=body.title,
        description=body.description,
        symptom=body.symptom,
        severity=body.severity,
        tags=body.tags or [],
        context=body.context or {},
    )
    db.add(inv)
    await db.flush()

    # Add creator as member
    member = InvestigationMember(investigation_id=inv.id, user_id=user_id)
    db.add(member)
    await db.commit()
    await db.refresh(inv)

    logger.info("investigation_created", investigation_id=str(inv.id), org_id=str(org_id))
    return _serialize_investigation(inv)


@router.get("/{investigation_id}", response_model=InvestigationOut, summary="Get investigation by ID")
async def get_investigation(
    investigation_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    inv = await _get_investigation_or_404(investigation_id, uuid.UUID(current_user.org_id), db)
    return _serialize_investigation(inv)


@router.patch("/{investigation_id}", response_model=InvestigationOut, summary="Update investigation")
async def update_investigation(
    investigation_id: uuid.UUID,
    body: InvestigationUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.create_investigation)),
    db: AsyncSession = Depends(get_db),
):
    inv = await _get_investigation_or_404(investigation_id, uuid.UUID(current_user.org_id), db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inv, field, value)

    if body.status == InvestigationStatus.resolved and not inv.resolved_at:
        inv.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(inv)
    logger.info("investigation_updated", investigation_id=str(investigation_id))
    return _serialize_investigation(inv)


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete investigation")
async def delete_investigation(
    investigation_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    inv = await _get_investigation_or_404(investigation_id, uuid.UUID(current_user.org_id), db)
    await db.delete(inv)
    await db.commit()
    logger.info("investigation_deleted", investigation_id=str(investigation_id))


@router.post("/{investigation_id}/close", response_model=InvestigationOut, summary="Close investigation")
async def close_investigation(
    investigation_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.create_investigation)),
    db: AsyncSession = Depends(get_db),
):
    inv = await _get_investigation_or_404(investigation_id, uuid.UUID(current_user.org_id), db)
    inv.status = InvestigationStatus.closed
    if not inv.resolved_at:
        inv.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(inv)
    return _serialize_investigation(inv)
