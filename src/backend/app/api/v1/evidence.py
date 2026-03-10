"""
Evidence API - collect, list, and manage evidence items for investigations.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rbac import Permission, TokenPayload, require_permission
from app.models.all_models import Evidence, EvidenceKind, Investigation

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class EvidenceCollectRequest(BaseModel):
    investigation_id: str
    connector_id: Optional[str] = None
    kind: EvidenceKind
    label: str = Field(..., min_length=1, max_length=512)
    source_uri: Optional[str] = Field(None, max_length=2048)
    raw_payload: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)


class EvidenceOut(BaseModel):
    id: str
    investigation_id: str
    org_id: str
    connector_id: Optional[str]
    kind: str
    label: str
    source_uri: Optional[str]
    summary: Optional[str]
    tags: List[str]
    collected_at: datetime
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceListResponse(BaseModel):
    items: List[EvidenceOut]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize(ev: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=str(ev.id),
        investigation_id=str(ev.investigation_id),
        org_id=str(ev.org_id),
        connector_id=str(ev.connector_id) if ev.connector_id else None,
        kind=ev.kind.value,
        label=ev.label,
        source_uri=ev.source_uri,
        summary=ev.summary,
        tags=ev.tags or [],
        collected_at=ev.collected_at,
        expires_at=ev.expires_at,
        created_at=ev.created_at,
    )


async def _assert_investigation_access(
    investigation_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(Investigation).where(
            Investigation.id == investigation_id,
            Investigation.org_id == org_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED, summary="Collect evidence")
async def collect_evidence(
    body: EvidenceCollectRequest,
    current_user: TokenPayload = Depends(require_permission(Permission.collect_evidence)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    investigation_id = uuid.UUID(body.investigation_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    expires_at = None
    if settings.EVIDENCE_TTL_MINUTES > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.EVIDENCE_TTL_MINUTES)

    ev = Evidence(
        investigation_id=investigation_id,
        org_id=org_id,
        connector_id=uuid.UUID(body.connector_id) if body.connector_id else None,
        kind=body.kind,
        label=body.label,
        source_uri=body.source_uri,
        raw_payload=body.raw_payload,
        summary=body.summary,
        tags=body.tags or [],
        expires_at=expires_at,
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)

    logger.info("evidence_collected", evidence_id=str(ev.id), investigation_id=str(investigation_id))
    return _serialize(ev)


@router.get("", response_model=EvidenceListResponse, summary="List evidence for an investigation")
async def list_evidence(
    investigation_id: uuid.UUID = Query(...),
    kind: Optional[EvidenceKind] = Query(None),
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    query = select(Evidence).where(
        Evidence.investigation_id == investigation_id,
        Evidence.org_id == org_id,
    )
    if kind:
        query = query.where(Evidence.kind == kind)

    from sqlalchemy import func as sqlfunc
    count_result = await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Evidence.collected_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return EvidenceListResponse(items=[_serialize(e) for e in items], total=total)


@router.get("/{evidence_id}", response_model=EvidenceOut, summary="Get evidence by ID")
async def get_evidence(
    evidence_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    result = await db.execute(
        select(Evidence).where(Evidence.id == evidence_id, Evidence.org_id == org_id)
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return _serialize(ev)


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete evidence item")
async def delete_evidence(
    evidence_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.collect_evidence)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    result = await db.execute(
        select(Evidence).where(Evidence.id == evidence_id, Evidence.org_id == org_id)
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    await db.delete(ev)
    await db.commit()
    logger.info("evidence_deleted", evidence_id=str(evidence_id))
