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

| Provider key | Models | Notes |
|---|---|---|
| `openai` | `gpt-4o` (default) | Requires `LLM_API_KEY` |
| `anthropic` | `claude-sonnet-4-6` (default) | Requires `LLM_API_KEY`. Supports prompt caching. |
| `azure_openai` | Any deployed model | Requires `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_AZURE_DEPLOYMENT` |
| `gemini` | `gemini-1.5-pro` (default) | Requires `LLM_API_KEY` |
| `ollama` | Any locally hosted model | Requires `LLM_BASE_URL`. No external API calls — fully on-premise. |
| `openai_compatible` | Any model | For OpenAI-compatible APIs (e.g. vLLM, LM Studio). Requires `LLM_BASE_URL` and `LLM_API_KEY`. |

---

## Configuration

LLM providers are configured via environment variables on the BugPilot analysis engine server. All providers share the same variable names — only the values differ.

### Common Variables

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | Provider key (see table above) |
| `LLM_API_KEY` | API key for the selected provider |
| `LLM_MODEL` | Model name override (uses provider default if unset) |
| `LLM_BASE_URL` | Base URL for Azure OpenAI, Ollama, or OpenAI-compatible providers |
| `LLM_AZURE_DEPLOYMENT` | Azure OpenAI deployment name (Azure only) |
| `LLM_AZURE_API_VERSION` | Azure OpenAI API version (Azure only) |

### OpenAI

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
# Optional: override the default model
LLM_MODEL=gpt-4o
```

### Anthropic

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
# Optional: override the default model
LLM_MODEL=claude-sonnet-4-6
```

### Azure OpenAI

```bash
LLM_PROVIDER=azure_openai
LLM_BASE_URL=https://your-resource.openai.azure.com
LLM_API_KEY=your-azure-key
LLM_AZURE_DEPLOYMENT=your-deployment-name
LLM_AZURE_API_VERSION=2024-02-01
```

### Google Gemini

```bash
LLM_PROVIDER=gemini
LLM_API_KEY=AIzaSy...
# Optional: override the default model
LLM_MODEL=gemini-1.5-pro
```

### Ollama (on-premise, no external calls)

```bash
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3                        # or any model you have pulled
```

### OpenAI-Compatible (vLLM, LM Studio, etc.)

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:8080/v1
LLM_API_KEY=your-api-key               # use "none" if auth is not required
LLM_MODEL=your-model-name
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
