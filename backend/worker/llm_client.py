"""
LLM client — generates investigation narratives.

Primary:  Anthropic claude-sonnet-4-6
Fallback: OpenAI gpt-4o

Features:
- Redis prompt cache (SHA256 key, 24h TTL)
- Circuit breaker (3 failures → 300s open)
- Structured output via prompt engineering
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

from backend.connectors._base.circuit_breaker import CircuitBreaker

log = logging.getLogger(__name__)

_ANTHROPIC_CB = CircuitBreaker(name="anthropic", threshold=3, timeout=300)
_OPENAI_CB = CircuitBreaker(name="openai", threshold=3, timeout=300)

SYSTEM_PROMPT = """You are BugPilot, an expert software debugging assistant.
Your job is to analyze a bug report and a list of code changes (PRs) to produce
a concise, technical root-cause narrative.

Output format:
- 2-4 sentences explaining what changed and how it caused the bug
- Mention the specific file/function if identifiable
- Reference the PR number and merge date
- Be precise and actionable; avoid filler phrases
- Do not invent details not present in the evidence"""


def _cache_key(prompt: str) -> str:
    return "llm:cache:" + hashlib.sha256(prompt.encode()).hexdigest()


def _get_cached(redis_client, prompt: str) -> Optional[str]:
    try:
        val = redis_client.get(_cache_key(prompt))
        return val if isinstance(val, str) else (val.decode() if val else None)
    except Exception:
        return None


def _set_cached(redis_client, prompt: str, response: str) -> None:
    try:
        redis_client.setex(_cache_key(prompt), 86400, response)
    except Exception:
        pass


def _build_prompt(
    investigation_id: str,
    ticket_summary: str,
    hypotheses: list[dict],
    sentry_events: list[dict],
) -> str:
    hyp_text = []
    for h in hypotheses[:3]:
        hyp_text.append(
            f"- PR #{h.get('pr_id')}: \"{h.get('pr_title','')}\" "
            f"by {h.get('pr_author','')} merged {h.get('pr_merged_at','')}\n"
            f"  File: {h.get('file_path','')} | Confidence: {h.get('confidence',0):.1%}\n"
            f"  Diff snippet: {str(h.get('evidence',{}).get('diff_snippet',''))[:300]}"
        )

    sentry_text = ""
    if sentry_events:
        sentry_text = f"\nSentry errors:\n- {sentry_events[0].get('title','')}"
        if len(sentry_events) > 1:
            sentry_text += f" (+{len(sentry_events)-1} more)"

    return (
        f"Investigation ID: {investigation_id}\n"
        f"Bug report: {ticket_summary[:500]}\n"
        f"{sentry_text}\n\n"
        f"Top hypotheses:\n" + "\n".join(hyp_text)
    )


def generate_narrative(
    investigation_id: str,
    ticket_summary: str,
    hypotheses: list[dict],
    sentry_events: list[dict],
    redis_client,
) -> str:
    """
    Generate LLM narrative for the top hypothesis.
    Returns the narrative string.
    """
    if not hypotheses:
        return "No hypotheses generated — insufficient signal in the investigation window."

    user_prompt = _build_prompt(
        investigation_id, ticket_summary, hypotheses, sentry_events
    )

    # Check cache
    cached = _get_cached(redis_client, user_prompt)
    if cached:
        log.debug(f"LLM cache hit for {investigation_id}")
        return cached

    # Try Anthropic first
    if not _ANTHROPIC_CB.is_open():
        try:
            narrative = _call_anthropic(user_prompt)
            _ANTHROPIC_CB.record_success()
            _set_cached(redis_client, user_prompt, narrative)
            return narrative
        except Exception as e:
            log.warning(f"Anthropic failed: {e}")
            _ANTHROPIC_CB.record_failure()

    # Fallback to OpenAI
    if not _OPENAI_CB.is_open():
        try:
            narrative = _call_openai(user_prompt)
            _OPENAI_CB.record_success()
            _set_cached(redis_client, user_prompt, narrative)
            return narrative
        except Exception as e:
            log.warning(f"OpenAI failed: {e}")
            _OPENAI_CB.record_failure()

    log.error("Both LLM providers unavailable")
    return (
        f"Unable to generate narrative — LLM providers unavailable. "
        f"Top candidate: PR #{hypotheses[0].get('pr_id')} "
        f"\"{hypotheses[0].get('pr_title','')}\" "
        f"({hypotheses[0].get('confidence',0):.1%} confidence)"
    )


def _call_anthropic(user_prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


def _call_openai(user_prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
