# Architecture Overview

BugPilot turns a vague symptom — "payment service is returning errors" — into ranked, evidence-backed root cause hypotheses with suggested safe actions. This document explains the system design and data flow.

---

## System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  User's Machine                                                  │
│                                                                  │
│   bugpilot CLI (macOS / Windows binary)                          │
│       │                                                          │
└───────┼──────────────────────────────────────────────────────────┘
        │  HTTPS  (api.bugpilot.io)
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  BugPilot Cloud Service                                          │
│                                                                  │
│   FastAPI REST API  (/api/v1/...)                                 │
│       │                    │                                     │
│       ▼                    ▼                                     │
│   PostgreSQL DB        Evidence Collectors                       │
│                             │                                    │
│                    ┌────────┼────────┐                           │
│                    ▼        ▼        ▼                           │
│               Datadog   Grafana   CloudWatch                     │
│               GitHub    K8s       PagerDuty                      │
│                                                                  │
│   Hypothesis Engine                                              │
│       ├── Pass 1: Rule-based patterns                            │
│       ├── Pass 2: Graph correlation                              │
│       ├── Pass 3: Historical reranking                           │
│       ├── Pass 4: LLM synthesis (optional)                       │
│       ├── Pass 5: Deduplication                                  │
│       └── Pass 6: Final ranking                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### Investigation

The central unit of work. An investigation holds a title, symptom, severity, linked services, timeline of events, and references to all evidence, hypotheses, and actions.

Status lifecycle: `open` → `in_progress` → `resolved` → `closed`

### Evidence

A normalized snapshot of a data point from a monitoring source. Evidence is typed by kind:

| Kind | Description |
|------|-------------|
| `log_snapshot` | Log lines or error summaries |
| `metric_snapshot` | Metric values at a point in time |
| `trace` | Distributed trace data |
| `event` | Deployment, config change, or system event |
| `config_diff` | Before/after config comparison |
| `topology` | Service dependency or infrastructure topology |
| `custom` | Free-form evidence from any source |

Each evidence item has a `reliability_score` (0–1), an `is_redacted` flag, and an optional `connector_id` attributing it to a configured source.

### Investigation Graph

BugPilot builds a directed graph of causal relationships between evidence items. Graph edges are weighted by temporal proximity, service overlap, and signal type correlation. The graph drives the second pass of hypothesis generation.

### Hypothesis Engine — 6-Pass Pipeline

1. **Rule-based:** Matches evidence patterns against a library of known failure signatures (bad deployment, OOMKill, dependency degradation, config error, etc.)
2. **Graph correlation:** Traverses the investigation graph to find causal chains
3. **Historical reranking:** Compares current evidence patterns to resolved past investigations for the same org
4. **LLM synthesis:** (Optional) Sends a redacted evidence summary to the configured LLM provider for open-ended hypothesis generation
5. **Deduplication:** Merges near-duplicate hypotheses using title similarity and evidence overlap
6. **Final ranking:** Sorts by confidence score, assigns ranks

### Actions

Proposed remediation steps. Each action has:
- A **risk level** (`safe` / `low` / `medium` / `high` / `critical`)
- An **approval gate** — medium and above require an `approver` or `admin` before execution
- A **rollback plan** — documented steps to undo the action
- A **dry-run mode** — simulates the action without making changes

---

## Privacy and Security

### PII Redaction

Before evidence summaries are sent to an LLM, BugPilot's privacy redactor strips:

- Email addresses
- Phone numbers
- JWT and Bearer tokens
- Payment card numbers (PAN)
- AWS access keys and secrets
- PEM private keys
- IP addresses (configurable)
- Custom regex patterns (per org)

A hard safety check in the hypothesis engine raises an error if non-redacted content is detected at the LLM boundary — this is enforced in code, not policy.

### Authentication

- License keys activate a device and exchange for a short-lived JWT (1-hour expiry) plus a refresh token
- Device fingerprint (SHA-256 of hardware UUID + system info) is recorded at activation
- Tokens are stored at `~/.config/bugpilot/credentials.json` with `600` permissions
- All API requests use `Authorization: Bearer <token>`

### Org Isolation

Every database query is scoped to `org_id`. Cross-tenant queries are architecturally impossible — the `org_id` is derived from the verified JWT, not from a user-supplied parameter.

### Credential Encryption

Connector credentials are encrypted with Fernet (symmetric AES-128-CBC + HMAC-SHA256) before storage. The Fernet key is a required environment variable and must be managed in a secrets manager in production.

---

## Connectors

Evidence collection is concurrent across all configured connectors. Each connector runs with:
- Request timeout: 30 seconds
- Collection timeout: 45 seconds (connector is marked degraded if exceeded)
- Retry policy: exponential backoff with jitter, max 3 attempts, on 429 / 5xx

Connector failures are graceful — other connectors continue unaffected.

---

## Data Model

Key tables (21 total):

| Table | Description |
|-------|-------------|
| `organisations` | Tenant root, holds settings and retention config |
| `users` | User accounts with role and org membership |
| `license_activations` | Device activations and token refresh history |
| `investigations` | Investigation workspace |
| `investigation_timeline` | Timestamped events within an investigation |
| `evidence_items` | Normalized evidence with metadata and payload reference |
| `hypotheses` | Generated hypotheses with confidence scores and evidence citations |
| `actions` | Proposed remediation actions with risk and approval state |
| `connectors` | Configured monitoring integrations (credentials encrypted) |
| `webhooks` | Registered webhook sources and secrets |
| `audit_logs` | Append-only record of all write operations |
| `llm_usage_logs` | LLM token usage per investigation |

---

## Observability

### Metrics (Prometheus)

Available at `/metrics` on the backend:

| Metric | Description |
|--------|-------------|
| `bugpilot_activations_total` | CLI activations |
| `bugpilot_active_investigations` | Current open investigations |
| `bugpilot_investigation_duration_seconds` | Time from open to resolved |
| `bugpilot_time_to_first_hypothesis_seconds` | Hypothesis generation latency |
| `bugpilot_connector_errors_total` | Connector fetch errors by connector |
| `bugpilot_connector_rate_limits_total` | Rate limit hits by connector |
| `bugpilot_webhook_verification_failures_total` | Failed webhook signature verifications |
| `bugpilot_llm_requests_total` | LLM requests by provider |
| `bugpilot_llm_tokens_total` | LLM token usage (prompt + completion) |
| `bugpilot_http_requests_total` | API request counts |
| `bugpilot_http_request_duration_seconds` | API response latency |

### Structured Logging

All log output is structured JSON via structlog. Log entries include: `timestamp`, `level`, `event`, `investigation_id`, `org_id`, `connector`, `duration_ms`, and other context fields as applicable.
