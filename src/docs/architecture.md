# Architecture Overview

BugPilot turns a vague symptom — "payment service is slow" — into ranked, evidence-backed debugging hypotheses with suggested safe actions. This document explains the system architecture, data flow, and key design decisions.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User / CI Pipeline                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ CLI (typer + rich)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BugPilot REST API (FastAPI)                     │
│                                                                     │
│  /auth  /investigations  /evidence  /hypotheses  /actions           │
│  /graph  /webhooks  /service-mappings  /admin  /health  /metrics    │
└──────────┬───────────────────────────────────────────────┬──────────┘
           │                                               │
           ▼                                               ▼
┌──────────────────┐                           ┌──────────────────────┐
│   PostgreSQL     │                           │   Evidence Collector  │
│  (async/asyncpg) │◄──────────────────────────│  (asyncio.gather)    │
└──────────────────┘                           └──────┬───────────────┘
                                                      │ concurrent
           ┌──────────────────────────────────────────┼──────────────────┐
           ▼                 ▼                ▼        ▼       ▼         ▼
     ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────┐  ┌────┐  ┌───────┐
     │ Datadog  │  │   Grafana    │  │CloudWatch│  │ K8s│  │ GH │  │  PD   │
     └──────────┘  └──────────────┘  └──────────┘  └────┘  └────┘  └───────┘
```

---

## Core Concepts

### Investigation

An **Investigation** is the top-level container for a debugging session. It is created either manually via CLI/API or automatically when a webhook alert arrives. An investigation tracks:

- The affected service(s)
- A timeline of events
- Evidence collected from connectors
- Hypotheses about the root cause
- Actions taken (with approvals)
- The final outcome

Investigations can be **branched** for parallel hypothesis exploration. Each branch gets its own graph slice without affecting the main investigation.

### Evidence

**Evidence items** are normalised facts collected from connectors. Each item has:

- `source_system` — which connector produced it (e.g. `datadog`, `github`)
- `capability` — what kind of data it is (`LOGS`, `METRICS`, `DEPLOYMENTS`, etc.)
- `normalized_summary` — a ≤500-character human-readable summary (always kept)
- `payload_ref` — reference to the full raw payload in external storage (nulled after TTL)
- `reliability_score` — 0-1 score adjusted for staleness and source quality
- `is_redacted` — whether PII/secrets have been scrubbed
- `redaction_manifest` — a log of what was redacted and why

Evidence is **never sent to an LLM in raw form**. The privacy layer redacts it first.

### Investigation Graph

Every investigation maintains a **graph** (not a simple list) of nodes and edges. Nodes represent symptoms, services, evidence items, and deployment events. Edges represent causal and temporal relationships.

```
[Symptom: 5xx rate spike]
       │
       ├──caused_by──► [Evidence: Datadog alert at 14:31]
       │
       └──correlates_with──► [Deployment: a3f8c2d at 14:23]
                                    │
                                    └──code_change──► [GitHub commit: Update Stripe SDK v4]
```

The graph is stored as `GraphNodeModel` and `GraphEdgeModel` rows, and can be queried as a `GraphSlice` — a lightweight in-memory snapshot used by the hypothesis engine and LLM layer.

### Hypothesis Engine

The hypothesis engine runs a **6-pass pipeline** on each `GraphSlice`:

1. **Rule-based pass** — Pattern matching for known failure modes:
   - OOMKilled / memory spike → Memory Exhaustion hypothesis
   - 5xx errors + recent deployment → Bad Deployment Introduced Regression
   - High latency + multiple services → Upstream Dependency Degradation

2. **Graph correlation pass** — Scores hypotheses by edge density. Symptoms with ≥3 connected edges and related services generate Service Graph Anomaly hypotheses with confidence proportional to edge count.

3. **Historical reranking** — (When DB context is available) Previous investigations with similar evidence patterns adjust confidence scores.

4. **LLM synthesis pass** — If the graph slice is redacted (`is_redacted=True`), the LLM is asked to generate additional hypotheses not already covered by rule-based or graph passes. **The LLM never receives raw evidence.**

5. **Merge and deduplicate** — Jaccard word-overlap similarity. Duplicates above the threshold (0.75) are merged, keeping the higher-confidence version.

6. **Rank** — Sorted by confidence_score descending. In single-lane investigations (evidence from only one capability type), all scores are capped at 0.4 and `is_single_lane=True` is set.

### Privacy and Redaction

BugPilot enforces a strict privacy boundary. Before any data can be sent to an LLM provider, it must pass through the redaction pipeline:

**Patterns scrubbed:**
- Email addresses
- Phone numbers (E.164 and US formats)
- JSON Web Tokens
- Bearer tokens
- Payment card numbers (Luhn)
- AWS secret access keys
- PEM private keys

The `LLMService.complete()` method raises `ValueError` if a non-redacted `GraphSlice` is passed. This is enforced at the code level, not configuration.

### Deduplication

When a new investigation is created (manually or via webhook), BugPilot checks for existing open investigations with overlapping context using a **weighted similarity score**:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Service overlap | 40% | Jaccard overlap of linked service names |
| Time overlap | 30% | Overlap of evidence time windows |
| Alert signature | 20% | Hash match on alert name / monitor name |
| Symptom text | 10% | Word-overlap on title strings |

If the score exceeds 0.85, the new investigation is flagged as a potential duplicate. BugPilot **never silently merges** — it reports the match and lets the user decide.

### Remediation and Approval

Actions suggested by BugPilot are assigned a risk level. The approval requirement depends on role:

| Risk level | Approval required |
|-----------|-------------------|
| `low` | None — any investigator can run |
| `medium` | `approver` role |
| `high` | `approver` role |
| `critical` | `approver` role |

Every action supports a **dry-run mode** that simulates the action and prints what would happen without making any changes.

---

## Database Schema Summary

BugPilot uses 21 PostgreSQL tables:

```
organisations → licenses → users → sessions
organisations → investigations → branches
investigations → graph_nodes
investigations → graph_edges
investigations → evidence_items → hypothesis_evidence_links → hypotheses
hypotheses → actions → approvals
investigations → outcomes
organisations → connector_configs
organisations → service_mapping_models
organisations → retention_policies
organisations → audit_logs
organisations → llm_usage_logs
```

All primary keys are UUIDs. All timestamps are `TIMESTAMPTZ`. JSON columns use PostgreSQL's `JSONB` type for indexability. A cross-dialect `TypeDecorator` ensures the test suite works with SQLite.

---

## Authentication Flow

```
CLI                         API                      DB
 │                           │                        │
 │── POST /auth/activate ───►│                        │
 │   {license_key, device_fp}│                        │
 │                           │── verify license ─────►│
 │                           │── check device count ──►│
 │                           │── create Session ──────►│
 │◄── {jwt_token, refresh} ──│                        │
 │                           │                        │
 │── (on expiry) POST /auth/ │                        │
 │   refresh {refresh_token} │                        │
 │◄── {new_jwt, new_refresh} │                        │
```

- JWT tokens are short-lived (1 hour by default)
- Refresh tokens are opaque (stored as bcrypt hashes)
- Each refresh rotates both tokens
- `logout` revokes the session row

---

## API Versioning

All routes live under `/api/v1/`. The health and metrics endpoints are at the root:

```
GET  /health           Liveness probe
GET  /health/ready     Readiness probe (checks DB)
GET  /metrics          Prometheus metrics (text/plain)
```

---

## Observability

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `bugpilot_activations_total` | Counter | License activations |
| `bugpilot_active_investigations` | Gauge | Open investigations |
| `bugpilot_investigation_duration_seconds` | Histogram | Time from open to resolved |
| `bugpilot_time_to_first_hypothesis_seconds` | Histogram | Time from open to first hypothesis |
| `bugpilot_connector_errors_total` | Counter | Per-connector errors (label: connector) |
| `bugpilot_connector_rate_limits_total` | Counter | Per-connector 429s |
| `bugpilot_webhook_verification_failures_total` | Counter | Webhook HMAC failures |
| `bugpilot_llm_requests_total` | Counter | LLM completions (label: provider) |
| `bugpilot_llm_tokens_total` | Counter | LLM tokens used |
| `bugpilot_http_requests_total` | Counter | HTTP requests (label: method, path, status) |
| `bugpilot_http_request_duration_seconds` | Histogram | HTTP latency |

### Structured Logging

All log output is structured JSON (via structlog) with consistent fields:

```json
{
  "timestamp": "2024-01-15T14:31:00.123Z",
  "level": "info",
  "event": "hypothesis_generated",
  "investigation_id": "inv_7f3a2b",
  "count": 3,
  "is_single_lane": false
}
```

In development (TTY), logs are printed in a human-readable format with colour.

---

## Retention and Data Lifecycle

BugPilot implements a three-phase retention policy configurable per organisation:

| Phase | Default | Action |
|-------|---------|--------|
| Investigation archive | 365 days | Resolved investigations are archived |
| Evidence metadata | 90 days | Evidence rows are deleted |
| Raw payload expiry | 30 days | `payload_ref` is nulled (row kept) |

Each phase writes an `AuditLog` entry before any data mutation, making the operation fully auditable and idempotent. A daily purge job runs `RetentionService.run_daily_purge()` across all organisations.

---

## Security Design Principles

1. **Credentials never stored plaintext.** Connector credentials are Fernet-encrypted before database storage.
2. **Passwords hashed with bcrypt.** All secrets (license keys, tokens) are stored as bcrypt or SHA-256 hashes.
3. **LLM boundary enforced in code.** `LLMService` raises `ValueError` for non-redacted input — not a config flag.
4. **Org isolation at every query.** All database queries filter by `org_id`. No cross-org data access is possible through the API.
5. **Webhook signatures verified.** All four webhook handlers verify HMAC-SHA256 signatures with a dual-secret grace window for rotation.
6. **Role-based access control.** Four roles (viewer, investigator, approver, admin) with a typed permission matrix. Elevation is never implicit.
