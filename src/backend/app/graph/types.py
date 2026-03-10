"""
Graph types for the Investigation Graph engine.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class NodeType(str, Enum):
    investigation = "investigation"
    symptom = "symptom"
    business_operation = "business_operation"
    service_or_component = "service_or_component"
    event = "event"
    evidence = "evidence"
    hypothesis = "hypothesis"
    action = "action"
    outcome = "outcome"
    deployment = "deployment"
    code_change = "code_change"
    user_report = "user_report"
    environment = "environment"


class EdgeType(str, Enum):
    contains = "contains"
    affects = "affects"
    depends_on = "depends_on"
    precedes = "precedes"
    supports = "supports"
    contradicts = "contradicts"
    confirms = "confirms"
    rejects = "rejects"
    branch_lineage = "branch_lineage"


@dataclass
class GraphNode:
    id: str
    org_id: str
    investigation_id: str
    branch_id: str
    node_type: NodeType
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None


@dataclass
class GraphEdge:
    id: str
    org_id: str
    investigation_id: str
    from_node_id: str
    to_node_id: str
    edge_type: EdgeType
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None


@dataclass
class GraphSlice:
    """Unit passed between graph and LLM layer - never raw DB rows."""
    investigation_id: str
    branch_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_redacted: bool = False

    def node_by_id(self, node_id: str) -> Optional[GraphNode]:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        return [n for n in self.nodes if n.node_type == node_type]

    def edges_from(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.from_node_id == node_id]

    def edges_to(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.to_node_id == node_id]
