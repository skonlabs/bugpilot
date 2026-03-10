"""
Hypothesis generation engine.
Multi-pass: rule-based -> graph correlation -> historical reranking -> LLM synthesis -> merge/dedup -> rank.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING
import structlog

from app.graph.types import GraphSlice, NodeType, EdgeType
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.llm.llm_service import LLMService

logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.75
MIN_HYPOTHESES = 3
MAX_HYPOTHESES = 7


class HypothesisSource(str, Enum):
    rule = "rule"
    llm = "llm"
    historical = "historical"


class HypothesisStatus(str, Enum):
    active = "active"
    confirmed = "confirmed"
    rejected = "rejected"


@dataclass
class Hypothesis:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    branch_id: str = ""
    title: str = ""
    description: str = ""
    confidence_score: float = 0.5
    rank: int = 0
    status: HypothesisStatus = HypothesisStatus.active
    generated_by: HypothesisSource = HypothesisSource.rule
    evidence_ids: list[str] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    is_single_lane: bool = False
    # Compatibility fields for tests
    reasoning: str = ""
    generated_by_llm: bool = False


class HypothesisEngine:
    """Multi-pass hypothesis generation engine."""

    def __init__(
        self,
        llm_service: Optional["LLMService"] = None,
        db=None,
        # Simple dict-based API for tests / lightweight usage
        use_llm: bool = False,
        llm_client=None,
    ):
        self.llm_service = llm_service
        self.db = db
        self.use_llm = use_llm
        self._llm_client = llm_client

    def _meets_generation_threshold(self, slice: GraphSlice) -> tuple[bool, str]:
        """Check if threshold conditions are met for generation."""
        symptoms = slice.nodes_by_type(NodeType.symptom)
        services = slice.nodes_by_type(NodeType.service_or_component)
        evidence = slice.nodes_by_type(NodeType.evidence)

        if not symptoms:
            return False, "No symptom nodes in graph"
        if not services:
            return False, "No service/component nodes in graph"
        if len(evidence) < 2:
            return False, f"Only {len(evidence)} evidence items (need >=2)"

        return True, "OK"

    def _is_single_evidence_lane(self, slice: GraphSlice) -> bool:
        """Check if evidence comes from only one type/capability."""
        evidence_nodes = slice.nodes_by_type(NodeType.evidence)
        capabilities = set()
        for n in evidence_nodes:
            cap = n.properties.get("capability")
            if cap:
                capabilities.add(cap)
        return len(capabilities) <= 1

    def _rule_based_pass(self, slice: GraphSlice) -> list[Hypothesis]:
        """Deterministic pattern matching for common failure modes."""
        hypotheses = []

        # Pattern: OOMKilled + memory spike -> memory exhaustion
        evidence_nodes = slice.nodes_by_type(NodeType.evidence)
        has_oom = any(
            "OOMKilled" in str(n.properties) or "OutOfMemory" in str(n.properties)
            for n in evidence_nodes
        )
        has_memory_spike = any(
            "memory" in str(n.label).lower() and "spike" in str(n.properties).lower()
            for n in evidence_nodes
        )
        if has_oom or has_memory_spike:
            hypotheses.append(Hypothesis(
                title="Memory Exhaustion",
                description=(
                    "Evidence suggests the service ran out of memory. "
                    "Container was OOMKilled or memory usage spiked to capacity. "
                    "Likely causes: memory leak, large data load, insufficient limits."
                ),
                confidence_score=0.8,
                generated_by=HypothesisSource.rule,
                evidence_ids=[
                    n.id for n in evidence_nodes
                    if "memory" in str(n.properties).lower() or "OOM" in str(n.properties)
                ],
            ))

        # Pattern: 5xx errors + deployment -> bad deployment
        has_5xx = any(
            "5xx" in str(n.properties) or "500" in str(n.label)
            for n in evidence_nodes
        )
        deployments = slice.nodes_by_type(NodeType.deployment)
        if has_5xx and deployments:
            hypotheses.append(Hypothesis(
                title="Bad Deployment Introduced Regression",
                description=(
                    "A recent deployment correlates with the onset of 5xx errors. "
                    "The deployment may have introduced a bug, misconfiguration, or breaking change."
                ),
                confidence_score=0.7,
                generated_by=HypothesisSource.rule,
                evidence_ids=[
                    n.id for n in evidence_nodes
                    if "5xx" in str(n.properties) or "500" in str(n.label)
                ],
            ))

        # Pattern: high latency + dependency -> dependency degradation
        has_latency = any(
            "latency" in str(n.label).lower() or "timeout" in str(n.properties).lower()
            for n in evidence_nodes
        )
        services = slice.nodes_by_type(NodeType.service_or_component)
        if has_latency and len(services) > 1:
            hypotheses.append(Hypothesis(
                title="Upstream Dependency Degradation",
                description=(
                    "High latency evidence suggests a dependency (database, cache, external API) "
                    "is responding slowly, causing cascading delays."
                ),
                confidence_score=0.65,
                generated_by=HypothesisSource.rule,
            ))

        return hypotheses

    def _graph_correlation_pass(self, slice: GraphSlice) -> list[Hypothesis]:
        """Find causal chains in graph and score by edge density."""
        hypotheses = []

        symptoms = slice.nodes_by_type(NodeType.symptom)
        for symptom in symptoms:
            # Find nodes connected to this symptom
            connected_edges = slice.edges_to(symptom.id) + slice.edges_from(symptom.id)
            if len(connected_edges) >= 3:
                related_services = []
                for edge in connected_edges:
                    other_id = (
                        edge.from_node_id if edge.to_node_id == symptom.id
                        else edge.to_node_id
                    )
                    other = slice.node_by_id(other_id)
                    if other and other.node_type == NodeType.service_or_component:
                        related_services.append(other.label)

                if related_services:
                    density_score = min(0.9, 0.5 + len(connected_edges) * 0.1)
                    hypotheses.append(Hypothesis(
                        title=f"Service Graph Anomaly: {symptom.label}",
                        description=(
                            f"Graph analysis shows {len(connected_edges)} connections to symptom '{symptom.label}'. "
                            f"Affected services: {', '.join(related_services[:3])}. "
                            f"High edge density suggests a systemic issue."
                        ),
                        confidence_score=density_score,
                        generated_by=HypothesisSource.rule,
                    ))

        return hypotheses

    async def _llm_synthesis_pass(
        self,
        slice: GraphSlice,
        existing_hypotheses: list[Hypothesis],
    ) -> list[Hypothesis]:
        """Use LLM to synthesize additional hypotheses."""
        if not self.llm_service:
            return []

        existing_titles = [h.title for h in existing_hypotheses]
        task = (
            f"Generate {MIN_HYPOTHESES} to {MAX_HYPOTHESES} ranked debugging hypotheses for this investigation. "
            f"Already identified: {existing_titles}. "
            f"Focus on novel hypotheses not yet covered. "
            f"For each hypothesis provide: title, description (2-3 sentences), confidence_score (0-1). "
            f"Format as JSON array: [{{'title': '...', 'description': '...', 'confidence_score': 0.7}}]"
        )

        try:
            response = await self.llm_service.complete(slice, task)
            return self._parse_llm_hypotheses(response.content)
        except Exception as e:
            logger.warning("llm_hypothesis_failed", error=str(e))
            return []

    def _parse_llm_hypotheses(self, content: str) -> list[Hypothesis]:
        """Parse LLM JSON response into Hypothesis objects."""
        import json
        import re
        hypotheses = []
        # Find JSON array in response
        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group())
            for item in items[:MAX_HYPOTHESES]:
                hypotheses.append(Hypothesis(
                    title=item.get("title", "Unknown"),
                    description=item.get("description", ""),
                    confidence_score=float(item.get("confidence_score", 0.5)),
                    generated_by=HypothesisSource.llm,
                ))
        except (json.JSONDecodeError, ValueError):
            pass
        return hypotheses

    def _semantic_similarity(self, h1: Hypothesis, h2: Hypothesis) -> float:
        """Simple word-overlap similarity."""
        words1 = set(h1.title.lower().split() + h1.description.lower().split())
        words2 = set(h2.title.lower().split() + h2.description.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _deduplicate(self, hypotheses: list[Hypothesis]) -> list[Hypothesis]:
        """Remove duplicates above similarity threshold."""
        unique = []
        for h in hypotheses:
            is_dup = False
            for existing in unique:
                if self._semantic_similarity(h, existing) >= SIMILARITY_THRESHOLD:
                    is_dup = True
                    # Keep the one with higher confidence
                    if h.confidence_score > existing.confidence_score:
                        unique.remove(existing)
                        unique.append(h)
                    break
            if not is_dup:
                unique.append(h)
        return unique

    async def generate(
        self,
        slice_or_evidence,
        investigation_id: str = "",
        branch_id: str = "",
        context: dict = None,
        max_hypotheses: int = MAX_HYPOTHESES,
    ) -> list[Hypothesis]:
        """Full generation pipeline. Accepts either GraphSlice or list[dict] evidence."""
        # Dict-based API for lightweight testing
        if isinstance(slice_or_evidence, list):
            result = await self._generate_from_dicts(slice_or_evidence, context or {}, investigation_id, branch_id)
            return result[:max_hypotheses]
        result = await self._generate_from_graph_slice(slice_or_evidence, investigation_id, branch_id)
        return result[:max_hypotheses]

    async def _generate_from_dicts(
        self,
        evidence: list[dict],
        context: dict,
        investigation_id: str,
        branch_id: str,
    ) -> list[Hypothesis]:
        """Generate hypotheses from plain dict evidence (simpler API for testing)."""
        if self.use_llm:
            raise NotImplementedError(
                "LLM-based hypothesis generation from dict evidence is not yet implemented. "
                "Use GraphSlice-based generation with an LLMService instance."
            )

        hypotheses = []
        service = context.get("service", "unknown-service")

        # Detect evidence kinds
        kinds = set(e.get("kind", "") for e in evidence)
        is_single_lane = len(kinds) <= 1

        all_ev_ids = [e.get("id", "") for e in evidence]

        # Compute base score - lower when no evidence or single lane
        no_evidence = len(evidence) == 0
        base_score = 0.2 if no_evidence else (0.3 if is_single_lane else 0.5)

        # Fallback hypothesis always generated
        hypotheses.append(Hypothesis(
            title=f"Service Degradation: {service}",
            description=f"Evidence indicates degradation in {service}. Review all recent changes.",
            reasoning=f"Multiple evidence items point to degradation in {service}.",
            confidence_score=base_score,
            generated_by=HypothesisSource.rule,
            generated_by_llm=False,
            evidence_ids=all_ev_ids,
            supporting_evidence_ids=all_ev_ids,
            is_single_lane=is_single_lane,
        ))

        # Pattern matching on evidence kinds
        if "log_snapshot" in kinds:
            log_ev_ids = [e.get("id", "") for e in evidence if e.get("kind") == "log_snapshot"]
            hypotheses.append(Hypothesis(
                title="Application Error Spike",
                description="Log evidence shows elevated error rates. Check recent deployments and dependencies.",
                reasoning="Log snapshots contain errors suggesting application-level failure.",
                confidence_score=0.35 if is_single_lane else 0.65,
                generated_by=HypothesisSource.rule,
                generated_by_llm=False,
                evidence_ids=log_ev_ids,
                supporting_evidence_ids=log_ev_ids,
                is_single_lane=is_single_lane,
            ))

        if "metric_snapshot" in kinds:
            metric_ev_ids = [e.get("id", "") for e in evidence if e.get("kind") == "metric_snapshot"]
            hypotheses.append(Hypothesis(
                title="Resource Saturation",
                description="Metric evidence indicates resource saturation (CPU/memory/connections).",
                reasoning="Metric anomalies suggest resource constraints causing service degradation.",
                confidence_score=0.35 if is_single_lane else 0.7,
                generated_by=HypothesisSource.rule,
                generated_by_llm=False,
                evidence_ids=metric_ev_ids,
                supporting_evidence_ids=metric_ev_ids,
                is_single_lane=is_single_lane,
            ))

        if "config_diff" in kinds:
            config_ev_ids = [e.get("id", "") for e in evidence if e.get("kind") == "config_diff"]
            hypotheses.append(Hypothesis(
                title="Configuration Change Regression",
                description="Config diff evidence found. A recent configuration change may have caused this.",
                reasoning="Config diff directly indicates a change that could have caused regression.",
                confidence_score=0.35 if is_single_lane else 0.8,
                generated_by=HypothesisSource.rule,
                generated_by_llm=False,
                evidence_ids=config_ev_ids,
                supporting_evidence_ids=config_ev_ids,
                is_single_lane=is_single_lane,
            ))

        # Deduplicate and rank
        unique = self._deduplicate(hypotheses)
        ranked = sorted(unique, key=lambda h: h.confidence_score, reverse=True)
        for i, h in enumerate(ranked):
            h.rank = i + 1
            h.investigation_id = investigation_id
            h.branch_id = branch_id

        return ranked[:MAX_HYPOTHESES]

    async def _generate_from_graph_slice(
        self,
        slice: GraphSlice,
        investigation_id: str,
        branch_id: str,
    ) -> list[Hypothesis]:
        """Full generation pipeline."""
        meets_threshold, reason = self._meets_generation_threshold(slice)
        if not meets_threshold:
            logger.info("hypothesis_threshold_not_met", reason=reason)
            return []

        is_single_lane = self._is_single_evidence_lane(slice)

        # Pass 1: Rule-based
        rule_hypotheses = self._rule_based_pass(slice)
        logger.debug("rule_hypotheses", count=len(rule_hypotheses))

        # Pass 2: Graph correlation
        graph_hypotheses = self._graph_correlation_pass(slice)
        logger.debug("graph_hypotheses", count=len(graph_hypotheses))

        all_hypotheses = rule_hypotheses + graph_hypotheses

        # Pass 3: LLM synthesis (if slice is redacted)
        if getattr(slice, 'is_redacted', False):
            llm_hypotheses = await self._llm_synthesis_pass(slice, all_hypotheses)
            logger.debug("llm_hypotheses", count=len(llm_hypotheses))
            all_hypotheses.extend(llm_hypotheses)

        # Pass 4: Merge + deduplicate
        unique_hypotheses = self._deduplicate(all_hypotheses)

        # Pass 5: Mark single-lane as low confidence
        if is_single_lane:
            for h in unique_hypotheses:
                h.confidence_score = min(h.confidence_score, 0.4)
                h.is_single_lane = True

        # Pass 6: Rank
        ranked = sorted(unique_hypotheses, key=lambda h: h.confidence_score, reverse=True)
        for i, h in enumerate(ranked):
            h.rank = i + 1
            h.investigation_id = investigation_id
            h.branch_id = branch_id

        # Trim to range
        result = ranked[:MAX_HYPOTHESES]
        if len(result) < MIN_HYPOTHESES and ranked:
            result = ranked  # Keep all if below min

        logger.info(
            "hypotheses_generated",
            count=len(result),
            investigation_id=investigation_id,
            is_single_lane=is_single_lane,
        )
        return result
