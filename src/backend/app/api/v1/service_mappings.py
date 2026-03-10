"""
Service Mappings API - manage service dependency maps (nodes + edges).
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Permission, Role, TokenPayload, require_permission, require_role
from app.models.all_models import NodeKind, ServiceEdge, ServiceMap, ServiceNode

router = APIRouter()
logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ServiceMapCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ServiceMapUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceMapOut(BaseModel):
    id: str
    org_id: str
    name: str
    description: Optional[str]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ServiceNodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: NodeKind = NodeKind.service
    namespace: Optional[str] = None
    team: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ServiceNodeOut(BaseModel):
    id: str
    service_map_id: str
    name: str
    kind: str
    namespace: Optional[str]
    team: Optional[str]
    tags: List[str]
    metadata: Dict[str, Any]
    created_at: datetime


class ServiceEdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    protocol: Optional[str] = None
    label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ServiceEdgeOut(BaseModel):
    id: str
    service_map_id: str
    source_node_id: str
    target_node_id: str
    protocol: Optional[str]
    label: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime


class ServiceMapDetailOut(BaseModel):
    map: ServiceMapOut
    nodes: List[ServiceNodeOut]
    edges: List[ServiceEdgeOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ser_map(m: ServiceMap) -> ServiceMapOut:
    return ServiceMapOut(
        id=str(m.id),
        org_id=str(m.org_id),
        name=m.name,
        description=m.description,
        version=m.version,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _ser_node(n: ServiceNode) -> ServiceNodeOut:
    return ServiceNodeOut(
        id=str(n.id),
        service_map_id=str(n.service_map_id),
        name=n.name,
        kind=n.kind.value,
        namespace=n.namespace,
        team=n.team,
        tags=n.tags or [],
        metadata=n.metadata or {},
        created_at=n.created_at,
    )


def _ser_edge(e: ServiceEdge) -> ServiceEdgeOut:
    return ServiceEdgeOut(
        id=str(e.id),
        service_map_id=str(e.service_map_id),
        source_node_id=str(e.source_node_id),
        target_node_id=str(e.target_node_id),
        protocol=e.protocol,
        label=e.label,
        metadata=e.metadata or {},
        created_at=e.created_at,
    )


async def _get_map_or_404(map_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> ServiceMap:
    result = await db.execute(
        select(ServiceMap).where(ServiceMap.id == map_id, ServiceMap.org_id == org_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service map not found")
    return m


# ---------------------------------------------------------------------------
# Routes - Maps
# ---------------------------------------------------------------------------
@router.get("", response_model=List[ServiceMapOut], summary="List service maps")
async def list_maps(
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    result = await db.execute(
        select(ServiceMap).where(ServiceMap.org_id == org_id).order_by(ServiceMap.name)
    )
    return [_ser_map(m) for m in result.scalars().all()]


@router.post("", response_model=ServiceMapOut, status_code=status.HTTP_201_CREATED, summary="Create service map")
async def create_map(
    body: ServiceMapCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    m = ServiceMap(org_id=org_id, name=body.name, description=body.description)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    logger.info("service_map_created", map_id=str(m.id))
    return _ser_map(m)


@router.get("/{map_id}", response_model=ServiceMapDetailOut, summary="Get service map with nodes and edges")
async def get_map(
    map_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.read_investigation)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    m = await _get_map_or_404(map_id, org_id, db)

    nodes_result = await db.execute(select(ServiceNode).where(ServiceNode.service_map_id == map_id))
    nodes = nodes_result.scalars().all()

    edges_result = await db.execute(select(ServiceEdge).where(ServiceEdge.service_map_id == map_id))
    edges = edges_result.scalars().all()

    return ServiceMapDetailOut(
        map=_ser_map(m),
        nodes=[_ser_node(n) for n in nodes],
        edges=[_ser_edge(e) for e in edges],
    )


@router.patch("/{map_id}", response_model=ServiceMapOut, summary="Update service map")
async def update_map(
    map_id: uuid.UUID,
    body: ServiceMapUpdate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_map_or_404(map_id, uuid.UUID(current_user.org_id), db)
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        for field, value in update_data.items():
            setattr(m, field, value)
        m.version += 1
    await db.commit()
    await db.refresh(m)
    return _ser_map(m)


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete service map")
async def delete_map(
    map_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_map_or_404(map_id, uuid.UUID(current_user.org_id), db)
    await db.delete(m)
    await db.commit()


# ---------------------------------------------------------------------------
# Routes - Nodes
# ---------------------------------------------------------------------------
@router.post("/{map_id}/nodes", response_model=ServiceNodeOut, status_code=status.HTTP_201_CREATED, summary="Add node to map")
async def add_node(
    map_id: uuid.UUID,
    body: ServiceNodeCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    m = await _get_map_or_404(map_id, org_id, db)
    node = ServiceNode(
        service_map_id=map_id,
        org_id=org_id,
        name=body.name,
        kind=body.kind,
        namespace=body.namespace,
        team=body.team,
        tags=body.tags or [],
        metadata=body.metadata or {},
    )
    db.add(node)
    m.version += 1
    await db.commit()
    await db.refresh(node)
    return _ser_node(node)


@router.delete("/{map_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove node from map")
async def remove_node(
    map_id: uuid.UUID,
    node_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    await _get_map_or_404(map_id, org_id, db)
    result = await db.execute(
        select(ServiceNode).where(ServiceNode.id == node_id, ServiceNode.service_map_id == map_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    await db.delete(node)
    await db.commit()


# ---------------------------------------------------------------------------
# Routes - Edges
# ---------------------------------------------------------------------------
@router.post("/{map_id}/edges", response_model=ServiceEdgeOut, status_code=status.HTTP_201_CREATED, summary="Add edge to map")
async def add_edge(
    map_id: uuid.UUID,
    body: ServiceEdgeCreate,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    m = await _get_map_or_404(map_id, org_id, db)

    # Validate source and target exist in the same map
    for node_id_str in (body.source_node_id, body.target_node_id):
        nid = uuid.UUID(node_id_str)
        nr = await db.execute(
            select(ServiceNode).where(ServiceNode.id == nid, ServiceNode.service_map_id == map_id)
        )
        if not nr.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node {node_id_str} not found in this map",
            )

    edge = ServiceEdge(
        service_map_id=map_id,
        org_id=org_id,
        source_node_id=uuid.UUID(body.source_node_id),
        target_node_id=uuid.UUID(body.target_node_id),
        protocol=body.protocol,
        label=body.label,
        metadata=body.metadata or {},
    )
    db.add(edge)
    m.version += 1
    await db.commit()
    await db.refresh(edge)
    return _ser_edge(edge)


@router.delete("/{map_id}/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove edge from map")
async def remove_edge(
    map_id: uuid.UUID,
    edge_id: uuid.UUID,
    current_user: TokenPayload = Depends(require_permission(Permission.manage_connectors)),
    db: AsyncSession = Depends(get_db),
):
    org_id = uuid.UUID(current_user.org_id)
    await _get_map_or_404(map_id, org_id, db)
    result = await db.execute(
        select(ServiceEdge).where(ServiceEdge.id == edge_id, ServiceEdge.service_map_id == map_id)
    )
    edge = result.scalar_one_or_none()
    if not edge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")
    await db.delete(edge)
    await db.commit()
