"""
Investigation Graph engine.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.types import GraphSlice, GraphNode, GraphEdge, NodeType, EdgeType
from app.core.logging import get_logger

logger = get_logger(__name__)


class GraphService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_node(
        self,
        investigation_id: str,
        branch_id: str,
        node_type: NodeType,
        label: str,
        properties: dict[str, Any],
        org_id: str,
    ) -> GraphNode:
        """Add a node to the investigation graph."""
        from app.models.all_models import GraphNodeModel
        node_id = str(uuid.uuid4())
        db_node = GraphNodeModel(
            id=node_id,
            org_id=org_id,
            investigation_id=investigation_id,
            branch_id=branch_id,
            node_type=node_type.value,
            label=label,
            properties=properties,
        )
        self.db.add(db_node)
        await self.db.flush()
        return GraphNode(
            id=node_id,
            org_id=org_id,
            investigation_id=investigation_id,
            branch_id=branch_id,
            node_type=node_type,
            label=label,
            properties=properties,
            created_at=db_node.created_at,
        )

    async def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        edge_type: EdgeType,
        properties: dict[str, Any],
        org_id: str,
        investigation_id: str,
    ) -> GraphEdge:
        """Add an edge between two nodes."""
        from app.models.all_models import GraphEdgeModel
        edge_id = str(uuid.uuid4())
        db_edge = GraphEdgeModel(
            id=edge_id,
            org_id=org_id,
            investigation_id=investigation_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type.value,
            properties=properties,
        )
        self.db.add(db_edge)
        await self.db.flush()
        return GraphEdge(
            id=edge_id,
            org_id=org_id,
            investigation_id=investigation_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type,
            properties=properties,
        )

    async def get_subgraph(
        self,
        investigation_id: str,
        branch_id: str,
        depth: int = 3,
    ) -> GraphSlice:
        """Get a subgraph up to specified depth."""
        from app.models.all_models import GraphNodeModel, GraphEdgeModel

        # Get all nodes for this investigation/branch
        nodes_result = await self.db.execute(
            select(GraphNodeModel).where(
                GraphNodeModel.investigation_id == investigation_id,
                GraphNodeModel.branch_id == branch_id,
            )
        )
        db_nodes = nodes_result.scalars().all()

        # Get all edges for this investigation
        edges_result = await self.db.execute(
            select(GraphEdgeModel).where(
                GraphEdgeModel.investigation_id == investigation_id,
            )
        )
        db_edges = edges_result.scalars().all()

        nodes = [
            GraphNode(
                id=str(n.id),
                org_id=str(n.org_id),
                investigation_id=str(n.investigation_id),
                branch_id=str(n.branch_id),
                node_type=NodeType(n.node_type),
                label=n.label,
                properties=n.properties or {},
                created_at=n.created_at,
            )
            for n in db_nodes
        ]

        node_ids = {n.id for n in nodes}
        edges = [
            GraphEdge(
                id=str(e.id),
                org_id=str(e.org_id),
                investigation_id=str(e.investigation_id),
                from_node_id=str(e.from_node_id),
                to_node_id=str(e.to_node_id),
                edge_type=EdgeType(e.edge_type),
                properties=e.properties or {},
            )
            for e in db_edges
            if str(e.from_node_id) in node_ids or str(e.to_node_id) in node_ids
        ]

        return GraphSlice(
            investigation_id=investigation_id,
            branch_id=branch_id,
            nodes=nodes,
            edges=edges,
        )

    async def get_causal_chain(self, symptom_node_id: str) -> list[GraphNode]:
        """Traverse from a symptom node to find the causal chain."""
        from app.models.all_models import GraphNodeModel, GraphEdgeModel

        visited = set()
        chain = []
        queue = [symptom_node_id]

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            node_result = await self.db.get(GraphNodeModel, node_id)
            if not node_result:
                continue
            chain.append(GraphNode(
                id=str(node_result.id),
                org_id=str(node_result.org_id),
                investigation_id=str(node_result.investigation_id),
                branch_id=str(node_result.branch_id),
                node_type=NodeType(node_result.node_type),
                label=node_result.label,
                properties=node_result.properties or {},
            ))

            # Find causal predecessors (nodes that 'precedes' or 'affects' this node)
            edges_result = await self.db.execute(
                select(GraphEdgeModel).where(
                    GraphEdgeModel.to_node_id == node_id,
                    GraphEdgeModel.edge_type.in_([EdgeType.precedes.value, EdgeType.affects.value]),
                )
            )
            for edge in edges_result.scalars().all():
                if str(edge.from_node_id) not in visited:
                    queue.append(str(edge.from_node_id))

        return chain

    async def find_nodes_by_type(
        self,
        investigation_id: str,
        node_type: NodeType,
    ) -> list[GraphNode]:
        """Find all nodes of a given type in an investigation."""
        from app.models.all_models import GraphNodeModel

        result = await self.db.execute(
            select(GraphNodeModel).where(
                GraphNodeModel.investigation_id == investigation_id,
                GraphNodeModel.node_type == node_type.value,
            )
        )
        return [
            GraphNode(
                id=str(n.id),
                org_id=str(n.org_id),
                investigation_id=str(n.investigation_id),
                branch_id=str(n.branch_id),
                node_type=NodeType(n.node_type),
                label=n.label,
                properties=n.properties or {},
                created_at=n.created_at,
            )
            for n in result.scalars().all()
        ]

    async def merge_branch(
        self,
        source_branch_id: str,
        target_branch_id: str,
        merged_by_user_id: str,
        org_id: str,
    ) -> None:
        """Merge source branch into target branch with full audit trail."""
        from app.models.all_models import GraphNodeModel, AuditLog

        # Copy all nodes from source to target
        nodes_result = await self.db.execute(
            select(GraphNodeModel).where(
                GraphNodeModel.branch_id == source_branch_id,
            )
        )
        nodes = nodes_result.scalars().all()

        for node in nodes:
            node.branch_id = target_branch_id

        # Write audit log
        audit = AuditLog(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=merged_by_user_id,
            event_type="branch.merged",
            entity_type="branch",
            entity_id=source_branch_id,
            metadata={
                "source_branch_id": source_branch_id,
                "target_branch_id": target_branch_id,
            },
        )
        self.db.add(audit)
        await self.db.flush()

        logger.info(
            "branch_merged",
            source_branch_id=source_branch_id,
            target_branch_id=target_branch_id,
            merged_by=merged_by_user_id,
        )
