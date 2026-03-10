"""
Hypotheses API - generate, list, and manage investigation hypotheses.
"""
import uuid
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Permission, TokenPayload, require_permission
from app.models.all_models import Hypothesis, HypothesisStatus, Investigation

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class HypothesisCreate(BaseModel):
    investigation_id: str
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    supporting_evidence: Optional[List[str]] = Field(default_factory=list)
    reasoning: Optional[str] = None
    generated_by_llm: bool = False
    llm_model: Optional[str] = None


class HypothesisUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[HypothesisStatus] = None
    supporting_evidence: Optional[List[str]] = None
    reasoning: Optional[str] = None


class HypothesisOut(BaseModel):
    id: str
    investigation_id: str
    org_id: str
    title: str
    description: Optional[str]
    confidence_score: Optional[float]
    status: str
    supporting_evidence: List[str]
    reasoning: Optional[str]
    generated_by_llm: bool
    llm_model: Optional[str]
    created_at: datetime
    updated_at: datetime


class HypothesisListResponse(BaseModel):
    items: List[HypothesisOut]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize(h: Hypothesis) -> HypothesisOut:
    return HypothesisOut(
        id=str(h.id),
        investigation_id=str(h.investigation_id),
        org_id=str(h.org_id),
        title=h.title,
        description=h.description,
        confidence_score=h.confidence_score,
        status=h.status.value,
        supporting_evidence=h.supporting_evidence or [],
        reasoning=h.reasoning,
        generated_by_llm=h.generated_by_llm,
        llm_model=h.llm_model,
        created_at=h.created_at,
        updated_at=h.updated_at,
    )


async def _assert_investigation_access(investigation_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id, Investigation.org_id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")


async def _get_hypothesis_or_404(hypothesis_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Hypothesis:
    result = await db.execute(
        select(Hypothesis).where(Hypothesis.id == hypothesis_id, Hypothesis.org_id == org_id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hypothesis not found")
    return h


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=HypothesisListResponse, summary="List hypotheses for an investigation")
async def list_hypotheses(
    investigation_id: uuid.UUID = Query(...),
    status_filter: Optional[HypothesisStatus] = Query(None, alias="status"),
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    query = select(Hypothesis).where(
        Hypothesis.investigation_id == investigation_id,
        Hypothesis.org_id == org_id,
    )
    if status_filter:
        query = query.where(Hypothesis.status == status_filter)

    from sqlalchemy import func as sqlfunc
    count_result = await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Hypothesis.confidence_score.desc().nullslast(), Hypothesis.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return HypothesisListResponse(items=[_serialize(h) for h in items], total=total)


@router.post("", response_model=HypothesisOut, status_code=status.HTTP_201_CREATED, summary="Create hypothesis")
async def create_hypothesis(
    body: HypothesisCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.generate_hypothesis)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    investigation_id = uuid.UUID(body.investigation_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    h = Hypothesis(
        investigation_id=investigation_id,
        org_id=org_id,
        title=body.title,
        description=body.description,
        confidence_score=body.confidence_score,
        supporting_evidence=body.supporting_evidence or [],
        reasoning=body.reasoning,
        generated_by_llm=body.generated_by_llm,
        llm_model=body.llm_model,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)

    logger.info("hypothesis_created", hypothesis_id=str(h.id), investigation_id=str(investigation_id))
    return _serialize(h)


@router.get("/{hypothesis_id}", response_model=HypothesisOut, summary="Get hypothesis by ID")
async def get_hypothesis(
    hypothesis_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    return _serialize(await _get_hypothesis_or_404(hypothesis_id, uuid.UUID(current_user.org_id), db))


@router.patch("/{hypothesis_id}", response_model=HypothesisOut, summary="Update hypothesis")
async def update_hypothesis(
    hypothesis_id: uuid.UUID,
    body: HypothesisUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.generate_hypothesis)),
    db: AsyncSession = Depends(get_db),
):
    h = await _get_hypothesis_or_404(hypothesis_id, uuid.UUID(current_user.org_id), db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(h, field, value)
    await db.commit()
    await db.refresh(h)
    return _serialize(h)


@router.post("/{hypothesis_id}/confirm", response_model=HypothesisOut, summary="Mark hypothesis confirmed")
async def confirm_hypothesis(
    hypothesis_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.generate_hypothesis)),
    db: AsyncSession = Depends(get_db),
):
    h = await _get_hypothesis_or_404(hypothesis_id, uuid.UUID(current_user.org_id), db)
    h.status = HypothesisStatus.confirmed
    await db.commit()
    await db.refresh(h)
    logger.info("hypothesis_confirmed", hypothesis_id=str(hypothesis_id))
    return _serialize(h)


@router.post("/{hypothesis_id}/reject", response_model=HypothesisOut, summary="Mark hypothesis rejected")
async def reject_hypothesis(
    hypothesis_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.generate_hypothesis)),
    db: AsyncSession = Depends(get_db),
):
    h = await _get_hypothesis_or_404(hypothesis_id, uuid.UUID(current_user.org_id), db)
    h.status = HypothesisStatus.rejected
    await db.commit()
    await db.refresh(h)
    return _serialize(h)


@router.delete("/{hypothesis_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete hypothesis")
async def delete_hypothesis(
    hypothesis_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.generate_hypothesis)),
    db: AsyncSession = Depends(get_db),
):
    h = await _get_hypothesis_or_404(hypothesis_id, uuid.UUID(current_user.org_id), db)
    await db.delete(h)
    await db.commit()
