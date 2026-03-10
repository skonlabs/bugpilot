"""
Service mapping and auto-discovery service.

Manages the ServiceMap / ServiceNode / ServiceEdge graph that represents
an organisation's system topology. Supports:
  - Manual mapping creation
  - On-demand auto-discovery from configured connectors (Kubernetes, GitHub, Datadog)
  - Listing and retrieval of existing mappings
"""
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class MappingConfidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


@dataclass
class DiscoveredService:
    """Lightweight representation of a service found during auto-discovery."""
    name: str
    source: str                        # "kubernetes" | "github" | "datadog"
    namespace: Optional[str] = None
    deployment: Optional[str] = None
    repo: Optional[str] = None
    connector_refs: dict[str, str] = field(default_factory=dict)
    environments: list[str] = field(default_factory=list)
    confidence: MappingConfidence = MappingConfidence.medium
    metadata: dict[str, Any] = field(default_factory=dict)


class MappingService:
    """
    Service mapping registry and auto-discovery engine.

    The service map is persisted as ServiceMap / ServiceNode / ServiceEdge rows.
    Discovery results are returned as DiscoveredService objects for the caller
    to decide whether to persist them.
    """

    def __init__(self, db=None, connectors: Optional[dict] = None):
        self.db = db
        self.connectors: dict = connectors or {}

    # ------------------------------------------------------------------
    # Manual mapping management
    # ------------------------------------------------------------------

    async def get_or_create_service_map(
        self, org_id: str, map_name: str = "default"
    ):
        """Return the named ServiceMap for the org, creating it if absent."""
        if not self.db:
            return None

        from sqlalchemy import select
        from app.models.all_models import ServiceMap

        org_uuid = uuid.UUID(org_id)
        result = await self.db.execute(
            select(ServiceMap).where(
                ServiceMap.org_id == org_uuid,
                ServiceMap.name == map_name,
                ServiceMap.is_active.is_(True),
            )
        )
        service_map = result.scalars().first()

        if not service_map:
            service_map = ServiceMap(
                id=uuid.uuid4(),
                org_id=org_uuid,
                name=map_name,
                description=f"Auto-created service map '{map_name}'",
                version=1,
                is_active=True,
            )
            self.db.add(service_map)
            await self.db.flush()
            logger.info(
                "service_map_created", org_id=org_id, map_name=map_name, id=str(service_map.id)
            )

        return service_map

    async def add_node(
        self,
        org_id: str,
        map_name: str,
        service_name: str,
        kind: str = "service",
        namespace: Optional[str] = None,
        team: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ):
        """Add or update a ServiceNode in the named map."""
        if not self.db:
            logger.warning("add_node_skipped", reason="No DB connection")
            return None

        from sqlalchemy import select
        from app.models.all_models import ServiceNode, NodeKind

        service_map = await self.get_or_create_service_map(org_id, map_name)
        if not service_map:
            return None

        org_uuid = uuid.UUID(org_id)

        # Check for existing node
        result = await self.db.execute(
            select(ServiceNode).where(
                ServiceNode.service_map_id == service_map.id,
                ServiceNode.name == service_name,
            )
        )
        node = result.scalars().first()

        if node:
            # Update in place
            if namespace is not None:
                node.namespace = namespace
            if team is not None:
                node.team = team
            if tags is not None:
                node.tags = tags
            if metadata is not None:
                node.metadata = {**(node.metadata or {}), **metadata}
        else:
            # Map kind string to enum value safely
            try:
                node_kind = NodeKind(kind)
            except ValueError:
                node_kind = NodeKind.service

            node = ServiceNode(
                id=uuid.uuid4(),
                service_map_id=service_map.id,
                org_id=org_uuid,
                name=service_name,
                kind=node_kind,
                namespace=namespace,
                team=team,
                tags=tags or [],
                metadata=metadata or {},
            )
            self.db.add(node)

        await self.db.flush()
        return node

    async def add_edge(
        self,
        org_id: str,
        map_name: str,
        source_service: str,
        target_service: str,
        protocol: Optional[str] = None,
        label: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Add a directed ServiceEdge between two named services."""
        if not self.db:
            return None

        from sqlalchemy import select
        from app.models.all_models import ServiceNode, ServiceEdge

        service_map = await self.get_or_create_service_map(org_id, map_name)
        if not service_map:
            return None

        org_uuid = uuid.UUID(org_id)

        # Resolve source and target nodes (auto-create if missing)
        source_node = await self.add_node(org_id, map_name, source_service)
        target_node = await self.add_node(org_id, map_name, target_service)
        if not source_node or not target_node:
            return None

        # Check for existing edge
        result = await self.db.execute(
            select(ServiceEdge).where(
                ServiceEdge.service_map_id == service_map.id,
                ServiceEdge.source_node_id == source_node.id,
                ServiceEdge.target_node_id == target_node.id,
            )
        )
        edge = result.scalars().first()

        if not edge:
            edge = ServiceEdge(
                id=uuid.uuid4(),
                service_map_id=service_map.id,
                org_id=org_uuid,
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                protocol=protocol,
                label=label,
                metadata=metadata or {},
            )
            self.db.add(edge)
            await self.db.flush()

        return edge

    async def list_nodes(self, org_id: str, map_name: str = "default") -> list:
        """Return all ServiceNode rows for the named map."""
        if not self.db:
            return []

        from sqlalchemy import select
        from app.models.all_models import ServiceMap, ServiceNode

        org_uuid = uuid.UUID(org_id)
        result = await self.db.execute(
            select(ServiceNode)
            .join(ServiceMap, ServiceNode.service_map_id == ServiceMap.id)
            .where(
                ServiceMap.org_id == org_uuid,
                ServiceMap.name == map_name,
                ServiceMap.is_active.is_(True),
            )
        )
        return result.scalars().all()

    async def list_edges(self, org_id: str, map_name: str = "default") -> list:
        """Return all ServiceEdge rows for the named map."""
        if not self.db:
            return []

        from sqlalchemy import select
        from app.models.all_models import ServiceMap, ServiceEdge

        org_uuid = uuid.UUID(org_id)
        result = await self.db.execute(
            select(ServiceEdge)
            .join(ServiceMap, ServiceEdge.service_map_id == ServiceMap.id)
            .where(
                ServiceMap.org_id == org_uuid,
                ServiceMap.name == map_name,
                ServiceMap.is_active.is_(True),
            )
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Auto-discovery
    # ------------------------------------------------------------------

    async def discover(self, org_id: str) -> list[DiscoveredService]:
        """
        Run auto-discovery against all configured connectors for the org.
        Returns discovered services; does NOT automatically persist them.
        Runs on demand — not on a schedule.
        """
        discovered: list[DiscoveredService] = []

        if "kubernetes" in self.connectors:
            try:
                k8s_services = await self._discover_kubernetes(
                    self.connectors["kubernetes"], org_id
                )
                discovered.extend(k8s_services)
                logger.info(
                    "k8s_discovery_done",
                    org_id=org_id,
                    found=len(k8s_services),
                )
            except Exception as exc:
                logger.warning("k8s_discovery_failed", org_id=org_id, error=str(exc))

        if "github" in self.connectors:
            try:
                gh_services = await self._discover_github(
                    self.connectors["github"], org_id
                )
                discovered.extend(gh_services)
                logger.info(
                    "github_discovery_done",
                    org_id=org_id,
                    found=len(gh_services),
                )
            except Exception as exc:
                logger.warning("github_discovery_failed", org_id=org_id, error=str(exc))

        if "datadog" in self.connectors:
            try:
                dd_services = await self._discover_datadog(
                    self.connectors["datadog"], org_id
                )
                discovered.extend(dd_services)
                logger.info(
                    "datadog_discovery_done",
                    org_id=org_id,
                    found=len(dd_services),
                )
            except Exception as exc:
                logger.warning("datadog_discovery_failed", org_id=org_id, error=str(exc))

        logger.info(
            "discovery_complete",
            org_id=org_id,
            total_discovered=len(discovered),
            connectors_used=list(self.connectors.keys()),
        )
        return discovered

    async def discover_and_persist(self, org_id: str, map_name: str = "default") -> dict:
        """
        Run discovery and persist results into the named service map.
        Returns a summary dict with counts.
        """
        services = await self.discover(org_id)
        added = 0
        skipped = 0

        for svc in services:
            try:
                await self.add_node(
                    org_id=org_id,
                    map_name=map_name,
                    service_name=svc.name,
                    kind="service",
                    namespace=svc.namespace,
                    metadata={
                        "source": svc.source,
                        "confidence": svc.confidence.value,
                        "connector_refs": svc.connector_refs,
                        **svc.metadata,
                    },
                )
                added += 1
            except Exception as exc:
                logger.warning(
                    "persist_discovered_service_failed",
                    service=svc.name,
                    error=str(exc),
                )
                skipped += 1

        return {"discovered": len(services), "added": added, "skipped": skipped}

    # ------------------------------------------------------------------
    # Connector-specific discovery implementations
    # ------------------------------------------------------------------

    async def _discover_kubernetes(
        self, connector, org_id: str
    ) -> list[DiscoveredService]:
        """
        Enumerate Kubernetes namespaces and deployments to build service list.
        Requires the connector to expose a `list_deployments()` method.
        """
        services: list[DiscoveredService] = []
        try:
            if hasattr(connector, "list_deployments"):
                deployments = await connector.list_deployments()
                for dep in deployments:
                    name = dep.get("name") or dep.get("metadata", {}).get("name", "")
                    namespace = dep.get("namespace") or dep.get("metadata", {}).get("namespace", "")
                    if not name:
                        continue
                    services.append(
                        DiscoveredService(
                            name=name,
                            source="kubernetes",
                            namespace=namespace,
                            deployment=name,
                            confidence=MappingConfidence.high,
                            metadata={"k8s_labels": dep.get("labels", {})},
                        )
                    )
            else:
                logger.debug(
                    "k8s_discovery_skipped",
                    reason="Connector does not implement list_deployments()",
                )
        except Exception as exc:
            logger.warning("k8s_enumeration_error", error=str(exc))
        return services

    async def _discover_github(
        self, connector, org_id: str
    ) -> list[DiscoveredService]:
        """
        Enumerate GitHub repositories with recent activity as service candidates.
        Requires the connector to expose a `list_repos()` method.
        """
        services: list[DiscoveredService] = []
        try:
            if hasattr(connector, "list_repos"):
                repos = await connector.list_repos()
                for repo in repos:
                    name = repo.get("name", "")
                    if not name:
                        continue
                    # Infer service name from repo name (strip common suffixes)
                    svc_name = (
                        name.removesuffix("-service")
                        .removesuffix("-svc")
                        .removesuffix("-api")
                    )
                    services.append(
                        DiscoveredService(
                            name=svc_name,
                            source="github",
                            repo=repo.get("full_name", name),
                            confidence=MappingConfidence.medium,
                            metadata={
                                "github_repo": repo.get("full_name"),
                                "default_branch": repo.get("default_branch"),
                                "language": repo.get("language"),
                            },
                        )
                    )
            else:
                logger.debug(
                    "github_discovery_skipped",
                    reason="Connector does not implement list_repos()",
                )
        except Exception as exc:
            logger.warning("github_enumeration_error", error=str(exc))
        return services

    async def _discover_datadog(
        self, connector, org_id: str
    ) -> list[DiscoveredService]:
        """
        Enumerate Datadog monitored services via the service catalog or
        active monitors.
        Requires the connector to expose a `list_services()` method.
        """
        services: list[DiscoveredService] = []
        try:
            if hasattr(connector, "list_services"):
                dd_services = await connector.list_services()
                for svc in dd_services:
                    name = svc.get("service") or svc.get("name", "")
                    if not name:
                        continue
                    services.append(
                        DiscoveredService(
                            name=name,
                            source="datadog",
                            connector_refs={"datadog_service": name},
                            confidence=MappingConfidence.high,
                            metadata={
                                "datadog_env": svc.get("env"),
                                "datadog_version": svc.get("version"),
                            },
                        )
                    )
            else:
                logger.debug(
                    "datadog_discovery_skipped",
                    reason="Connector does not implement list_services()",
                )
        except Exception as exc:
            logger.warning("datadog_enumeration_error", error=str(exc))
        return services
