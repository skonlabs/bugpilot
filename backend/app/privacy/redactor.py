"""
Privacy redaction pipeline.
Replaces sensitive patterns with [REDACTED:<type>] placeholders.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.graph import CausalGraph

# ---------------------------------------------------------------------------
# Compiled regexes - defined at module level for performance
# ---------------------------------------------------------------------------

PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone_e164": re.compile(r'\+[1-9]\d{1,14}\b'),
    "phone_us": re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "jwt": re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
    "bearer": re.compile(r'\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b', re.IGNORECASE),
    "payment_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    "aws_secret": re.compile(r'\b[A-Za-z0-9+/]{40}\b'),
    "private_key_pem": re.compile(
        r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?'
        r'-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        re.DOTALL,
    ),
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class RedactionManifest:
    redacted_fields: list[str] = field(default_factory=list)
    pattern_counts: dict[str, int] = field(default_factory=dict)
    total_replacements: int = 0


# ---------------------------------------------------------------------------
# Core redaction functions
# ---------------------------------------------------------------------------


def redact_string(text: str) -> tuple[str, RedactionManifest]:
    """Redact a single string. Returns (redacted_text, manifest)."""
    manifest = RedactionManifest()
    result = text
    for pattern_name, pattern in PATTERNS.items():
        matches = pattern.findall(result)
        if matches:
            result = pattern.sub(f'[REDACTED:{pattern_name.upper()}]', result)
            manifest.pattern_counts[pattern_name] = len(matches)
            manifest.total_replacements += len(matches)
    return result, manifest


def redact_dict(data: dict) -> tuple[dict, RedactionManifest]:
    """Recursively redact a dict. Returns (redacted_dict, manifest)."""
    manifest = RedactionManifest()
    result: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            redacted, sub_manifest = redact_string(value)
            result[key] = redacted
            if sub_manifest.total_replacements > 0:
                manifest.redacted_fields.append(str(key))
                manifest.total_replacements += sub_manifest.total_replacements
                for k, v in sub_manifest.pattern_counts.items():
                    manifest.pattern_counts[k] = manifest.pattern_counts.get(k, 0) + v
        elif isinstance(value, dict):
            redacted_sub, sub_manifest = redact_dict(value)
            result[key] = redacted_sub
            manifest.redacted_fields.extend(
                [f"{key}.{f}" for f in sub_manifest.redacted_fields]
            )
            manifest.total_replacements += sub_manifest.total_replacements
            for k, v in sub_manifest.pattern_counts.items():
                manifest.pattern_counts[k] = manifest.pattern_counts.get(k, 0) + v
        elif isinstance(value, list):
            redacted_list, sub_manifest = redact_list(value)
            result[key] = redacted_list
            manifest.total_replacements += sub_manifest.total_replacements
            for k, v in sub_manifest.pattern_counts.items():
                manifest.pattern_counts[k] = manifest.pattern_counts.get(k, 0) + v
        else:
            result[key] = value
    return result, manifest


def redact_list(data: list) -> tuple[list, RedactionManifest]:
    """Recursively redact a list. Returns (redacted_list, manifest)."""
    manifest = RedactionManifest()
    result: list = []
    for item in data:
        if isinstance(item, str):
            redacted, sub_manifest = redact_string(item)
            result.append(redacted)
            manifest.total_replacements += sub_manifest.total_replacements
            for k, v in sub_manifest.pattern_counts.items():
                manifest.pattern_counts[k] = manifest.pattern_counts.get(k, 0) + v
        elif isinstance(item, dict):
            redacted, sub_manifest = redact_dict(item)
            result.append(redacted)
            manifest.total_replacements += sub_manifest.total_replacements
            for k, v in sub_manifest.pattern_counts.items():
                manifest.pattern_counts[k] = manifest.pattern_counts.get(k, 0) + v
        elif isinstance(item, list):
            redacted, sub_manifest = redact_list(item)
            result.append(redacted)
            manifest.total_replacements += sub_manifest.total_replacements
            for k, v in sub_manifest.pattern_counts.items():
                manifest.pattern_counts[k] = manifest.pattern_counts.get(k, 0) + v
        else:
            result.append(item)
    return result, manifest


# ---------------------------------------------------------------------------
# GraphSlice redaction
# ---------------------------------------------------------------------------


@dataclass
class GraphSlice:
    """
    A subset of the causal graph relevant to a single investigation.
    Carries nodes, edges, and associated evidence payloads.
    """
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RedactedGraphSlice:
    """
    Wrapper around a GraphSlice that has been through the redaction pipeline.

    Only instances of this class may be passed to LLM invocations.
    Attempting to construct one directly with an unredacted slice is intentionally
    impossible from outside this module - use `redact_graph_slice()` instead.
    """

    _SENTINEL = object()  # Module-private construction sentinel

    def __init__(self, slice_: GraphSlice, _sentinel: object = None) -> None:
        if _sentinel is not RedactedGraphSlice._SENTINEL:
            raise TypeError(
                "RedactedGraphSlice must be created via redact_graph_slice(), "
                "not constructed directly."
            )
        self._slice = slice_
        self._manifest: Optional[RedactionManifest] = None

    @property
    def slice(self) -> GraphSlice:
        return self._slice

    @property
    def manifest(self) -> Optional[RedactionManifest]:
        return self._manifest

    def __repr__(self) -> str:
        nodes = len(self._slice.nodes)
        edges = len(self._slice.edges)
        replacements = self._manifest.total_replacements if self._manifest else 0
        return (
            f"RedactedGraphSlice(nodes={nodes}, edges={edges}, "
            f"replacements={replacements})"
        )


def redact_graph_slice(slice_: GraphSlice) -> RedactedGraphSlice:
    """
    Apply the full redaction pipeline to a GraphSlice.

    Returns a RedactedGraphSlice that is safe to pass to LLM calls.
    """
    combined_manifest = RedactionManifest()

    # Deep-copy to avoid mutating the original
    nodes_copy = copy.deepcopy(slice_.nodes)
    edges_copy = copy.deepcopy(slice_.edges)
    evidence_copy = copy.deepcopy(slice_.evidence)
    metadata_copy = copy.deepcopy(slice_.metadata)

    redacted_nodes: list[dict] = []
    for node in nodes_copy:
        if isinstance(node, dict):
            r_node, m = redact_dict(node)
            redacted_nodes.append(r_node)
            _merge_manifests(combined_manifest, m)
        else:
            redacted_nodes.append(node)

    redacted_edges: list[dict] = []
    for edge in edges_copy:
        if isinstance(edge, dict):
            r_edge, m = redact_dict(edge)
            redacted_edges.append(r_edge)
            _merge_manifests(combined_manifest, m)
        else:
            redacted_edges.append(edge)

    redacted_evidence: list[dict] = []
    for ev in evidence_copy:
        if isinstance(ev, dict):
            r_ev, m = redact_dict(ev)
            redacted_evidence.append(r_ev)
            _merge_manifests(combined_manifest, m)
        else:
            redacted_evidence.append(ev)

    redacted_metadata, m = redact_dict(metadata_copy)
    _merge_manifests(combined_manifest, m)

    redacted_slice = GraphSlice(
        nodes=redacted_nodes,
        edges=redacted_edges,
        evidence=redacted_evidence,
        metadata=redacted_metadata,
    )

    result = RedactedGraphSlice(redacted_slice, _sentinel=RedactedGraphSlice._SENTINEL)
    result._manifest = combined_manifest
    return result


def assert_is_redacted(obj: Any) -> None:
    """
    Assert that the given object is a RedactedGraphSlice.

    Raises TypeError if `obj` is a bare GraphSlice or any other type.
    This function should be called at LLM call boundaries to enforce the
    privacy guarantee.
    """
    if isinstance(obj, GraphSlice):
        raise TypeError(
            "Unredacted GraphSlice passed to an LLM boundary. "
            "Call redact_graph_slice() first and pass the resulting "
            "RedactedGraphSlice instead."
        )
    if not isinstance(obj, RedactedGraphSlice):
        raise TypeError(
            f"Expected RedactedGraphSlice at LLM boundary, got {type(obj).__name__}."
        )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _merge_manifests(target: RedactionManifest, source: RedactionManifest) -> None:
    """Merge `source` manifest counts into `target` in-place."""
    target.total_replacements += source.total_replacements
    target.redacted_fields.extend(source.redacted_fields)
    for k, v in source.pattern_counts.items():
        target.pattern_counts[k] = target.pattern_counts.get(k, 0) + v


__all__ = [
    "PATTERNS",
    "RedactionManifest",
    "GraphSlice",
    "RedactedGraphSlice",
    "redact_string",
    "redact_dict",
    "redact_list",
    "redact_graph_slice",
    "assert_is_redacted",
]
