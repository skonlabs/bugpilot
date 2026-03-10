"""
Actions API - suggest, approve, and execute remediation actions.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Permission, TokenPayload, require_permission
from app.models.all_models import Action, ActionRiskLevel, ActionStatus, Investigation

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ActionCreate(BaseModel):
    investigation_id: str
    hypothesis_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    action_type: str = Field(..., min_length=1, max_length=100)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    risk_level: ActionRiskLevel = ActionRiskLevel.medium
    rollback_plan: Optional[str] = None


class ActionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    risk_level: Optional[ActionRiskLevel] = None
    rollback_plan: Optional[str] = None


class ActionOut(BaseModel):
    id: str
    investigation_id: str
    hypothesis_id: Optional[str]
    org_id: str
    title: str
    description: Optional[str]
    action_type: str
    parameters: Dict[str, Any]
    risk_level: str
    status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    executed_by: Optional[str]
    executed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    rollback_plan: Optional[str]
    created_at: datetime
    updated_at: datetime


class ActionListResponse(BaseModel):
    items: List[ActionOut]
    total: int


class DryRunOut(BaseModel):
    action_id: str
    action_type: str
    title: str
    parameters: Dict[str, Any]
    risk_level: str
    predicted_changes: str
    dry_run: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize(a: Action) -> ActionOut:
    return ActionOut(
        id=str(a.id),
        investigation_id=str(a.investigation_id),
        hypothesis_id=str(a.hypothesis_id) if a.hypothesis_id else None,
        org_id=str(a.org_id),
        title=a.title,
        description=a.description,
        action_type=a.action_type,
        parameters=a.parameters or {},
        risk_level=a.risk_level,
        status=a.status,
        approved_by=str(a.approved_by) if a.approved_by else None,
        approved_at=a.approved_at,
        executed_by=str(a.executed_by) if a.executed_by else None,
        executed_at=a.executed_at,
        result=a.result,
        rollback_plan=a.rollback_plan,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


async def _assert_investigation_access(investigation_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id, Investigation.org_id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")


async def _get_action_or_404(action_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Action:
    result = await db.execute(
        select(Action).where(Action.id == action_id, Action.org_id == org_id)
    )
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return a


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=ActionListResponse, summary="List actions for an investigation")
async def list_actions(
    investigation_id: uuid.UUID = Query(...),
    status_filter: Optional[ActionStatus] = Query(None, alias="status"),
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    query = select(Action).where(
        Action.investigation_id == investigation_id,
        Action.org_id == org_id,
    )
    if status_filter:
        query = query.where(Action.status == status_filter)

    from sqlalchemy import func as sqlfunc
    count_result = await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Action.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return ActionListResponse(items=[_serialize(a) for a in items], total=total)


@router.post("", response_model=ActionOut, status_code=status.HTTP_201_CREATED, summary="Suggest an action")
async def create_action(
    body: ActionCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.suggest_action)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    investigation_id = uuid.UUID(body.investigation_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    a = Action(
        investigation_id=investigation_id,
        hypothesis_id=uuid.UUID(body.hypothesis_id) if body.hypothesis_id else None,
        org_id=org_id,
        title=body.title,
        description=body.description,
        action_type=body.action_type,
        parameters=body.parameters or {},
        risk_level=body.risk_level,
        rollback_plan=body.rollback_plan,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)

    logger.info("action_created", action_id=str(a.id), investigation_id=str(investigation_id))
    return _serialize(a)


@router.get("/{action_id}", response_model=ActionOut, summary="Get action by ID")
async def get_action(
    action_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    return _serialize(await _get_action_or_404(action_id, uuid.UUID(current_user.org_id), db))


@router.patch("/{action_id}", response_model=ActionOut, summary="Update action")
async def update_action(
    action_id: uuid.UUID,
    body: ActionUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.suggest_action)),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_action_or_404(action_id, uuid.UUID(current_user.org_id), db)
    if a.status not in (ActionStatus.pending,):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update action in status '{a.status}'",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(a, field, value)
    await db.commit()
    await db.refresh(a)
    return _serialize(a)


@router.post("/{action_id}/approve", response_model=ActionOut, summary="Approve action for execution")
async def approve_action(
    action_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.approve_action)),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_action_or_404(action_id, uuid.UUID(current_user.org_id), db)
    if a.status != ActionStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action must be in 'pending' status to approve, got '{a.status}'",
        )
    a.status = ActionStatus.approved
    a.approved_by = uuid.UUID(current_user.sub)
    a.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(a)
    logger.info("action_approved", action_id=str(action_id), approver=current_user.sub)
    return _serialize(a)


@router.post("/{action_id}/dry-run", response_model=DryRunOut, summary="Simulate action without executing")
async def dry_run_action(
    action_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    """Simulate an action and return predicted changes without executing anything."""
    a = await _get_action_or_404(action_id, uuid.UUID(current_user.org_id), db)

    predicted = (
        a.dry_run_output
        or f"[Simulation] Would execute '{a.title}' (type: {a.action_type}) "
           f"with parameters: {a.parameters or {}}"
    )

    # Persist the simulated output so subsequent dry-runs are consistent
    if not a.dry_run_output:
        a.dry_run_output = predicted
        await db.commit()

    logger.info("action_dry_run", action_id=str(action_id), user=current_user.sub)
    return DryRunOut(
        action_id=str(a.id),
        action_type=a.action_type,
        title=a.title,
        parameters=a.parameters or {},
        risk_level=a.risk_level,
        predicted_changes=predicted,
    )


@router.post("/{action_id}/run", response_model=ActionOut, summary="Execute an approved action")
async def run_action(
    action_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.run_action)),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_action_or_404(action_id, uuid.UUID(current_user.org_id), db)
    if a.status != ActionStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action must be approved before running, got '{a.status}'",
        )
    a.status = ActionStatus.running
    a.executed_by = uuid.UUID(current_user.sub)
    a.executed_at = datetime.now(timezone.utc)
    await db.commit()

    # TODO: dispatch to async worker for actual execution
    # For now mark as completed with placeholder result
    a.status = ActionStatus.completed
    a.result = {"message": "Action dispatched for execution", "queued_at": datetime.now(timezone.utc).isoformat()}
    await db.commit()
    await db.refresh(a)
    logger.info("action_executed", action_id=str(action_id), executor=current_user.sub)
    return _serialize(a)


@router.post("/{action_id}/cancel", response_model=ActionOut, summary="Cancel a pending or approved action")
async def cancel_action(
    action_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.approve_action)),
    db: AsyncSession = Depends(get_db),
):
    a = await _get_action_or_404(action_id, uuid.UUID(current_user.org_id), db)
    if a.status not in (ActionStatus.pending, ActionStatus.approved):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel action in status '{a.status}'",
        )
    a.status = ActionStatus.cancelled
    await db.commit()
    await db.refresh(a)
    return _serialize(a)
