"""
LLM Service - orchestrates prompt building, caching, and LLM provider calls.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
import structlog

from app.llm.base import LLMProvider
from app.llm.types import Message, LLMResponse
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.graph.types import GraphSlice
    from app.privacy.redactor import RedactedGraphSlice

logger = get_logger(__name__)

PROMPT_VERSION = "1.0.0"


class LLMService:
    def __init__(self, provider: LLMProvider, db=None):
        self.provider = provider
        self.db = db
        self._cache: dict[str, LLMResponse] = {}  # in-memory cache for MVP

    def _cache_key(self, slice_hash: str, task: str, bypass_cache: bool = False) -> str:
        if bypass_cache:
            return f"bypass-{datetime.now(timezone.utc).timestamp()}"
        return hashlib.sha256(
            f"{slice_hash}:{task}:{PROMPT_VERSION}:{self.provider.model_name()}".encode()
        ).hexdigest()

    def _graph_slice_hash(self, slice: "GraphSlice") -> str:
        """Deterministic hash of graph slice content."""
        content = {
            "nodes": [(n.id, n.node_type.value, n.label) for n in sorted(slice.nodes, key=lambda x: x.id)],
            "edges": [(e.id, e.edge_type.value) for e in sorted(slice.edges, key=lambda x: x.id)],
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

    def graph_slice_to_prompt(self, slice: "GraphSlice", task: str) -> list[Message]:
        """
        Build a structured prompt from a GraphSlice.
        CRITICAL: Only accepts redacted slices.
        """
        # Enforce redaction at the boundary
        if not getattr(slice, 'is_redacted', False):
            raise ValueError(
                "SECURITY: Attempted to send non-redacted GraphSlice to LLM provider. "
                "Call redact_graph_slice() first."
            )

        # Build context summary
        nodes_by_type = {}
        for node in slice.nodes:
            nt = node.node_type.value
            nodes_by_type.setdefault(nt, []).append(node)

        context_parts = [
            f"Investigation ID: {slice.investigation_id}",
            f"Branch: {slice.branch_id}",
            "",
        ]

        for node_type, nodes in nodes_by_type.items():
            context_parts.append(f"## {node_type.replace('_', ' ').title()} ({len(nodes)} items)")
            for n in nodes[:20]:  # Limit per type
                props_summary = ", ".join(f"{k}={v}" for k, v in list(n.properties.items())[:3])
                context_parts.append(
                    f"- [{n.id[:8]}] {n.label}" + (f" ({props_summary})" if props_summary else "")
                )
            context_parts.append("")

        if slice.edges:
            context_parts.append(f"## Relationships ({len(slice.edges)} edges)")
            for e in slice.edges[:50]:  # Limit edges
                context_parts.append(
                    f"- {e.from_node_id[:8]} --[{e.edge_type.value}]--> {e.to_node_id[:8]}"
                )

        context = "\n".join(context_parts)

        return [
            Message(
                role="system",
                content=(
                    "You are BugPilot, an expert debugging assistant. "
                    "Analyze investigation graphs and provide structured analysis. "
                    "Be concise, specific, and actionable. "
                    "All data has been pre-sanitized - do not add sensitive information."
                ),
            ),
            Message(
                role="user",
                content=f"## Investigation Context\n\n{context}\n\n## Task\n\n{task}",
            ),
        ]

    async def complete(
        self,
        slice: "GraphSlice",
        task: str,
        max_tokens: int = 2000,
        bypass_cache: bool = False,
        investigation_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> LLMResponse:
        """Complete a task using LLM with caching."""
        slice_hash = self._graph_slice_hash(slice)
        cache_key = self._cache_key(slice_hash, task, bypass_cache)

        if not bypass_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.debug("llm_cache_hit", cache_key=cache_key[:16])
            return cached

        messages = self.graph_slice_to_prompt(slice, task)

        try:
            response = await self.provider.complete(messages, max_tokens=max_tokens)
            if not bypass_cache:
                self._cache[cache_key] = response

            # Log usage
            await self._log_usage(response, investigation_id, org_id)
            return response

        except Exception as e:
            logger.error("llm_error", error=str(e), provider=self.provider.provider_name())
            # Return deterministic fallback
            return LLMResponse(
                content=self._fallback_response(task),
                model=self.provider.model_name(),
                provider=self.provider.provider_name(),
                prompt_tokens=0,
                completion_tokens=0,
                cached=False,
                cost_usd=0.0,
            )

    def _fallback_response(self, task: str) -> str:
        return (
            f"[LLM unavailable - rule-based fallback]\n\n"
            f"Unable to complete task: {task}\n\n"
            f"Please check your LLM provider configuration and try again."
        )

    async def _log_usage(
        self,
        response: LLMResponse,
        investigation_id: Optional[str],
        org_id: Optional[str],
    ) -> None:
        if not self.db:
            return
        try:
            from app.models.all_models import LLMUsageLog
            import uuid
            log = LLMUsageLog(
                id=str(uuid.uuid4()),
                org_id=org_id,
                investigation_id=investigation_id,
                provider=response.provider,
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cached=response.cached,
                cost_usd=response.cost_usd,
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            logger.warning("llm_usage_log_failed", error=str(e))

    def invalidate_cache_for_investigation(self, investigation_id: str) -> None:
        """Invalidate all cached responses for an investigation."""
        # In production, this would target specific cache entries
        # For MVP, clear all cache entries containing this investigation
        self._cache.clear()
        logger.info("cache_invalidated", investigation_id=investigation_id)
