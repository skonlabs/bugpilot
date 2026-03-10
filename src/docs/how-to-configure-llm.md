# How to Configure LLM Providers

BugPilot uses LLMs to synthesize additional hypotheses when evidence is complex or when rule-based patterns don't fully explain an incident. LLM usage is **optional** — BugPilot works without one using its rule-based and graph correlation engines.

---

## Overview

When an LLM is configured, it runs as the 4th pass of the hypothesis pipeline:

```
Pass 1: Rule-based pattern matching     (always runs)
Pass 2: Graph correlation               (always runs)
Pass 3: Historical reranking            (always runs)
Pass 4: LLM synthesis                  (runs only when LLM_PROVIDER is set)
Pass 5: Deduplication
Pass 6: Final ranking
```

The LLM receives a **redacted** evidence summary — all PII, credentials, tokens, and keys are stripped before anything is sent. This is enforced in code; a safety check raises an error if non-redacted data reaches the LLM boundary.

---

## Supported Providers

| Provider | Models | Notes |
|----------|--------|-------|
| OpenAI | `gpt-4o` (default) | Requires `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-6` (default) | Requires `ANTHROPIC_API_KEY`. Supports prompt caching. |
| Azure OpenAI | Any deployed model | Requires endpoint, key, and deployment name |
| Ollama | Any locally hosted model | No external API calls — fully on-premise |

---

## Configuration

LLM providers are configured via environment variables on the BugPilot backend server. If you are using the hosted BugPilot service, contact your account team to enable LLM synthesis for your organisation.

### OpenAI

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Anthropic

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Azure OpenAI

```bash
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

### Ollama (on-premise, no external calls)

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3                        # or any model you have pulled
```

### No LLM (rule-based only)

Simply leave `LLM_PROVIDER` unset. BugPilot will use rule-based and graph correlation only. This is the default.

---

## Privacy Guarantee

Before any evidence is sent to an LLM, BugPilot's privacy redactor strips:

- Email addresses
- Phone numbers
- JWT and Bearer tokens
- Payment card numbers
- AWS access keys and secrets
- PEM private keys
- IP addresses (configurable)
- Custom regex patterns (configurable per org)

This redaction happens in code before the LLM boundary. A safety check in the hypothesis engine raises a `ValueError` if it detects non-redacted content about to be sent — this is a hard stop, not a warning.

---

## Token Budget

| Limit | Value |
|-------|-------|
| Max prompt tokens | 8,000 |
| Max completion tokens | 2,000 |
| Max tokens per investigation | 40,000 |

When the investigation token budget is exhausted, LLM synthesis is skipped for subsequent hypothesis passes. Rule-based and graph results are still produced.

---

## Caching

LLM responses are cached in-memory keyed by SHA-256 hash of the graph content. The cache is invalidated when new evidence is added to the investigation.

---

## Usage Tracking

LLM usage is logged and exposed via Prometheus metrics:

| Metric | Description |
|--------|-------------|
| `bugpilot_llm_requests_total` | Total LLM requests, labelled by provider |
| `bugpilot_llm_tokens_total` | Prompt and completion token counts |
