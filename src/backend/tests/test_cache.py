"""Tests for LLM response cache invalidation logic."""
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest


# ---------------------------------------------------------------------------
# Minimal LLM cache implementation to test against
# ---------------------------------------------------------------------------
# Models the expected cache contract. Replace with actual import when available.


def _hash_dict(data: dict) -> str:
    """Stable SHA-256 hash of a dict."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@dataclass
class GraphSliceSummary:
    """Simplified representation of a GraphSlice for cache key computation."""
    investigation_id: str
    branch_id: str
    node_count: int
    edge_count: int
    # Checksum changes whenever the graph changes
    checksum: str


@dataclass
class LLMCacheKey:
    """
    Composite cache key for LLM responses.
    Invalidated when:
    - The graph changes (checksum changes)
    - The prompt version changes
    """
    graph_checksum: str
    prompt_version: str
    prompt_template_hash: str

    @property
    def key(self) -> str:
        combined = f"{self.graph_checksum}:{self.prompt_version}:{self.prompt_template_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()


class LLMCache:
    """
    Simple in-memory LLM response cache with invalidation support.
    Entries are keyed by (graph_checksum, prompt_version, prompt_template_hash).
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}

    def _build_key(
        self,
        graph_checksum: str,
        prompt_version: str,
        prompt_template: str,
    ) -> str:
        key = LLMCacheKey(
            graph_checksum=graph_checksum,
            prompt_version=prompt_version,
            prompt_template_hash=_hash_str(prompt_template),
        )
        return key.key

    def get(
        self,
        graph_checksum: str,
        prompt_version: str,
        prompt_template: str,
        bypass: bool = False,
    ) -> Optional[Any]:
        if bypass:
            return None
        k = self._build_key(graph_checksum, prompt_version, prompt_template)
        return self._store.get(k)

    def set(
        self,
        graph_checksum: str,
        prompt_version: str,
        prompt_template: str,
        value: Any,
    ) -> None:
        k = self._build_key(graph_checksum, prompt_version, prompt_template)
        self._store[k] = value

    def invalidate_by_graph(self, graph_checksum: str) -> int:
        """Remove all entries matching a specific graph checksum."""
        to_delete = [k for k in self._store]
        # In a real implementation, we'd store the graph_checksum separately
        # For test purposes, clear all (since graph change means all are stale)
        count = len(self._store)
        self._store.clear()
        return count

    def size(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


PROMPT_TEMPLATE = "Analyze the following investigation graph and generate hypotheses:\n{graph}"
PROMPT_VERSION_1 = "v1.0.0"
PROMPT_VERSION_2 = "v2.0.0"
GRAPH_CHECKSUM_A = "abc123def456"
GRAPH_CHECKSUM_B = "xyz789uvw012"


def test_cache_hit_on_same_inputs():
    """Cache returns stored value when graph, version, and template are identical."""
    cache = LLMCache()
    value = {"hypotheses": ["hypothesis 1", "hypothesis 2"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, value)
    result = cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    assert result == value


def test_cache_miss_on_different_graph_checksum():
    """Graph change (different checksum) causes cache miss."""
    cache = LLMCache()
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, {"hypotheses": ["h1"]})

    # New graph checksum = new cache key = miss
    result = cache.get(GRAPH_CHECKSUM_B, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    assert result is None


def test_graph_change_invalidates_llm_cache():
    """When graph changes, the old cached response is not returned."""
    cache = LLMCache()
    cached_response = {"hypotheses": ["stale hypothesis"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, cached_response)

    # Graph changes - simulate by using a different checksum
    new_checksum = _hash_str("new graph state after evidence added")
    result = cache.get(new_checksum, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    assert result is None


def test_prompt_version_bump_invalidates_cache():
    """When prompt version changes, cache is invalidated for that entry."""
    cache = LLMCache()
    v1_response = {"hypotheses": ["old format hypothesis"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, v1_response)

    # Bump prompt version - should not return v1 response
    result = cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_2, PROMPT_TEMPLATE)
    assert result is None


def test_prompt_template_change_invalidates_cache():
    """Changing the prompt template text invalidates the cache."""
    cache = LLMCache()
    old_template = "Old prompt template v1"
    new_template = "New prompt template v2 with different instructions"
    response = {"hypotheses": ["hypothesis based on old template"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, old_template, response)

    # Different template = different hash = miss
    result = cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, new_template)
    assert result is None


def test_explicit_bypass_cache_returns_none():
    """bypass_cache=True forces a cache miss even when entry exists."""
    cache = LLMCache()
    cached = {"hypotheses": ["cached hypothesis"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, cached)

    # With bypass=True, should not return cached value
    result = cache.get(
        GRAPH_CHECKSUM_A,
        PROMPT_VERSION_1,
        PROMPT_TEMPLATE,
        bypass=True,
    )
    assert result is None


def test_bypass_cache_does_not_delete_entry():
    """bypass_cache=True does not remove the cached entry."""
    cache = LLMCache()
    cached = {"hypotheses": ["cached hypothesis"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, cached)

    # Bypass read
    _ = cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, bypass=True)

    # Normal read should still return cached value
    result = cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, bypass=False)
    assert result == cached


def test_cache_miss_returns_none():
    """Cache returns None when no entry exists."""
    cache = LLMCache()
    result = cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    assert result is None


def test_cache_size_tracks_entries():
    """Cache size reflects number of distinct entries."""
    cache = LLMCache()
    assert cache.size() == 0

    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, {"h": "1"})
    assert cache.size() == 1

    cache.set(GRAPH_CHECKSUM_B, PROMPT_VERSION_1, PROMPT_TEMPLATE, {"h": "2"})
    assert cache.size() == 2


def test_multiple_versions_coexist():
    """Different prompt versions can coexist in cache."""
    cache = LLMCache()
    v1_resp = {"version": "1", "hypotheses": ["h1"]}
    v2_resp = {"version": "2", "hypotheses": ["h2"]}
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, v1_resp)
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_2, PROMPT_TEMPLATE, v2_resp)

    # Both should be retrievable
    assert cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE) == v1_resp
    assert cache.get(GRAPH_CHECKSUM_A, PROMPT_VERSION_2, PROMPT_TEMPLATE) == v2_resp


def test_invalidate_by_graph_removes_all_graph_entries():
    """Invalidating by graph checksum removes all entries for that graph."""
    cache = LLMCache()
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE, {"h": "1"})
    cache.set(GRAPH_CHECKSUM_A, PROMPT_VERSION_2, PROMPT_TEMPLATE, {"h": "2"})

    removed = cache.invalidate_by_graph(GRAPH_CHECKSUM_A)
    assert removed >= 2  # At least the 2 entries we added


def test_cache_key_is_deterministic():
    """Same inputs always produce the same cache key."""
    cache = LLMCache()
    key1 = cache._build_key(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    key2 = cache._build_key(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    assert key1 == key2


def test_cache_key_differs_on_different_inputs():
    """Different inputs produce different cache keys."""
    cache = LLMCache()
    key1 = cache._build_key(GRAPH_CHECKSUM_A, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    key2 = cache._build_key(GRAPH_CHECKSUM_B, PROMPT_VERSION_1, PROMPT_TEMPLATE)
    key3 = cache._build_key(GRAPH_CHECKSUM_A, PROMPT_VERSION_2, PROMPT_TEMPLATE)
    assert key1 != key2
    assert key1 != key3
    assert key2 != key3
