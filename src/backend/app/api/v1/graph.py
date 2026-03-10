"""
Graph API - timeline events and causal graph for investigations.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Permission, TokenPayload, require_permission
from app.models.all_models import Investigation, TimelineEvent

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class TimelineEventCreate(BaseModel):
    investigation_id: str
    occurred_at: datetime
    event_type: str = Field(..., min_length=1, max_length=100)
    source: Optional[str] = Field(None, max_length=255)
    description: str = Field(..., min_length=1)
    payload: Optional[Dict[str, Any]] = None
    clock_skew_warning: bool = False


class TimelineEventOut(BaseModel):
    id: str
    investigation_id: str
    org_id: str
    occurred_at: datetime
    event_type: str
    source: Optional[str]
    description: str
    payload: Optional[Dict[str, Any]]
    clock_skew_warning: bool
    created_at: datetime


class TimelineResponse(BaseModel):
    events: List[TimelineEventOut]
    total: int


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str
    occurred_at: Optional[datetime]
    event_type: Optional[str]
    metadata: Dict[str, Any]


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    weight: float = 1.0


class CausalGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    investigation_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_event(e: TimelineEvent) -> TimelineEventOut:
    return TimelineEventOut(
        id=str(e.id),
        investigation_id=str(e.investigation_id),
        org_id=str(e.org_id),
        occurred_at=e.occurred_at,
        event_type=e.event_type,
        source=e.source,
        description=e.summary,           # model field is 'summary'
        payload=e.timeline_metadata,     # model field is 'timeline_metadata'
        clock_skew_warning=e.clock_skew_warning,
        created_at=e.created_at,
    )


async def _assert_investigation_access(investigation_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id, Investigation.org_id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/timeline", response_model=TimelineResponse, summary="Get timeline events for an investigation")
async def get_timeline(
    investigation_id: uuid.UUID = Query(...),
    event_type: Optional[str] = Query(None),
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    query = select(TimelineEvent).where(
        TimelineEvent.investigation_id == investigation_id,
        TimelineEvent.org_id == org_id,
    )
    if event_type:
        query = query.where(TimelineEvent.event_type == event_type)

    from sqlalchemy import func as sqlfunc
    count_result = await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(TimelineEvent.occurred_at.asc())
    result = await db.execute(query)
    events = result.scalars().all()

    return TimelineResponse(events=[_serialize_event(e) for e in events], total=total)


@router.post("/timeline", response_model=TimelineEventOut, status_code=status.HTTP_201_CREATED, summary="Add timeline event")
async def add_timeline_event(
    body: TimelineEventCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.collect_evidence)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    investigation_id = uuid.UUID(body.investigation_id)
    await _assert_investigation_access(investigation_id, org_id, db)

    event = TimelineEvent(
        investigation_id=investigation_id,
        org_id=org_id,
        occurred_at=body.occurred_at,
        event_type=body.event_type,
        source=body.source,
        summary=body.description,              # model field is 'summary'
        timeline_metadata=body.payload,        # model field is 'timeline_metadata'
        clock_skew_warning=body.clock_skew_warning,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    logger.info("timeline_event_added", event_id=str(event.id), investigation_id=str(investigation_id))
    return _serialize_event(event)


@router.get("/causal/{investigation_id}", response_model=CausalGraphResponse, summary="Get causal graph for investigation")
async def get_causal_graph(
    investigation_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    """
    Builds a lightweight causal graph from timeline events and evidence.
    Nodes represent events/evidence, edges represent temporal/causal relationships.
    """
    org_id = uuid.UUID(current_user.org_id)
    inv_result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id, Investigation.org_id == org_id)
    )
    inv = inv_result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    # Fetch timeline events
    events_result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.investigation_id == investigation_id)
        .order_by(TimelineEvent.occurred_at.asc())
    )
    events = events_result.scalars().all()

    # Build nodes from events
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    # Add investigation root node
    nodes.append(GraphNode(
        id=f"inv_{str(investigation_id)}",
        label=inv.title,
        kind="investigation",
        occurred_at=inv.created_at,
        event_type="symptom",
        metadata={"severity": inv.severity, "status": inv.status},
    ))

    prev_node_id = f"inv_{str(investigation_id)}"
    for event in events:
        node_id = f"event_{str(event.id)}"
        nodes.append(GraphNode(
            id=node_id,
            label=event.description[:80],
            kind="timeline_event",
            occurred_at=event.occurred_at,
            event_type=event.event_type,
            metadata={"source": event.source or "", "payload": event.payload or {}},
        ))
        # Link sequentially
        edges.append(GraphEdge(
            source=prev_node_id,
            target=node_id,
            label="followed_by",
            weight=1.0,
        ))
        prev_node_id = node_id

    return CausalGraphResponse(
        nodes=nodes,
        edges=edges,
        investigation_id=str(investigation_id),
    )


@router.delete("/timeline/{event_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete timeline event")
async def delete_timeline_event(
    event_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.collect_evidence)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.id == event_id, TimelineEvent.org_id == org_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline event not found")
    await db.delete(event)
    await db.commit()
