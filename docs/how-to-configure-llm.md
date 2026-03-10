# How to Configure LLM Providers

BugPilot uses LLMs to synthesize additional hypotheses when evidence is complex or when rule-based patterns don't fully explain an incident. LLM usage is **optional** — BugPilot works without one using its rule-based and graph correlation engines.

---

## Overview

When an LLM is configured, BugPilot uses it in the 4th pass of the hypothesis pipeline:

1. Rule-based pass (always runs)
2. Graph correlation pass (always runs)
3. Historical reranking (runs if DB context available)
4. **LLM synthesis** ← only runs if configured and slice is redacted
5. Dedup + rank (always runs)

The LLM is given the redacted investigation graph and asked to suggest hypotheses not already identified by earlier passes. **No raw evidence, no PII, no secrets are ever sent to the LLM.**

---

## Supported Providers

| Provider | Model | Notes |
|----------|-------|-------|
| OpenAI | gpt-4o (default) | Best hypothesis quality |
| Anthropic | claude-sonnet-4-6 (default) | Strong reasoning, supports prompt caching |
| Azure OpenAI | Your deployment | GPT-4 family via your Azure resource |
| Ollama | Any local model | No external API calls; privacy-first |

---

## OpenAI

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

Or in `backend/.env`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...
```

**Supported models:** `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`. Default: `gpt-4o`.

To change the model, set `LLM_MODEL=gpt-4o-mini` in your environment.

---

## Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**Supported models:** `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Default: `claude-sonnet-4-6`.

BugPilot takes advantage of Anthropic's **prompt caching** for repeated investigation context, reducing token costs on follow-up hypothesis refinements.

---

## Azure OpenAI

```env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment
```

Azure OpenAI is recommended for organisations with data residency requirements or enterprise agreements.

---

## Ollama (Local / Air-gapped)

For privacy-sensitive environments where data cannot leave your network:

```bash
# Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2

# Configure BugPilot
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export LLM_MODEL=llama3.2
```

**Recommended models for hypothesis generation:**
- `llama3.2` — Good balance of quality and speed
- `mixtral` — Higher quality, higher resource usage
- `codellama` — Better for code-related incidents

> **Note:** Ollama models are typically less capable at complex reasoning than GPT-4o or Claude. Consider using them for lower-severity incidents or as a complement to rule-based hypotheses.

---

## Privacy Guarantee

Regardless of which LLM provider you use, BugPilot enforces a strict privacy boundary in code:

```python
# In app/llm/llm_service.py — enforced at runtime, not configuration
if not getattr(slice, 'is_redacted', False):
    raise ValueError(
        "SECURITY: Attempted to send non-redacted GraphSlice to LLM provider."
    )
```

Before a `GraphSlice` is sent to any LLM, the privacy pipeline:
1. Scrubs emails, phone numbers, JWTs, bearer tokens, payment cards, AWS keys, PEM keys
2. Sets `is_redacted=True` on the slice
3. Records a `RedactionManifest` with what was removed

The LLM never sees raw log lines, actual error messages with PII, or secrets.

---

## Token Budget and Caching

BugPilot enforces a **token budget** per LLM call to prevent runaway costs:

| Setting | Default |
|---------|---------|
| Max prompt tokens | 8,000 |
| Max completion tokens | 2,000 |
| Max total tokens per investigation | 40,000 |

The LLM service maintains an **in-memory cache** keyed by a SHA-256 hash of the graph content, task description, model name, and prompt version. Identical investigation states return cached results without a new API call.

Cache entries are invalidated when new evidence is added to an investigation via `invalidate_cache_for_investigation(investigation_id)`.

---

## LLM Usage Tracking

All LLM calls are logged to the `llm_usage_logs` table:

```bash
curl http://localhost:8000/api/v1/admin/llm-usage \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# {
#   "total_requests": 142,
#   "total_tokens": 287450,
#   "total_cost_usd": 8.62,
#   "by_provider": {
#     "openai": {"requests": 142, "tokens": 287450, "cost_usd": 8.62}
#   }
# }
```

A Prometheus counter also tracks usage:

```
bugpilot_llm_requests_total{provider="openai"} 142
bugpilot_llm_tokens_total{provider="openai",type="prompt"} 245230
bugpilot_llm_tokens_total{provider="openai",type="completion"} 42220
```

---

## Disabling LLM (Rule-based only mode)

To run BugPilot entirely without an LLM:

```env
# Simply don't set LLM_PROVIDER
# BugPilot will use rule-based + graph correlation only
```

Rule-based and graph correlation hypotheses are available instantly without any API calls, latency, or cost.
