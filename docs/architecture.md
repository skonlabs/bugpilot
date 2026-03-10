# BugPilot Architecture

## Overview

BugPilot is a CLI-first debugging and investigation platform with a REST API backend.

**Core user journey:**
```
symptom → evidence collection → timeline reconstruction → hypothesis generation → safest next action
```

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                       User (Terminal)                        │
└────────────────────────┬────────────────────────────────────┘
                         │ CLI (bugpilot)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Auth    │  │Investig. │  │Evidence  │  │Hypotheses│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Actions  │  │  Graph   │  │ServiceMap│  │  Admin   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Webhook Intake                          │   │
│  │  /v1/webhooks/{datadog,grafana,cloudwatch,pagerduty} │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Core Services                           │   │
│  │  Config | DB | Security | RBAC | Logging             │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ asyncpg
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL 16                               │
│   21 tables: orgs, licenses, users, sessions,                │
│   investigations, evidence, hypotheses, actions,             │
│   connectors, timeline_events, service_maps, nodes,         │
│   edges, webhooks, webhook_deliveries, audit_logs,          │
│   api_keys, investigation_members, comments,                │
│   notification_subscriptions, llm_request_logs             │
└─────────────────────────────────────────────────────────────┘
```

---

## Investigation Graph Model

The investigation graph is the central data structure in BugPilot. It represents all known facts about an incident as a directed property graph.

### Node Types

| Node Type | Description |
|-----------|-------------|
| `investigation` | Root node; represents the investigation itself |
| `symptom` | Observed anomaly (e.g., "15% HTTP 500 error rate") |
| `business_operation` | Affected business process (e.g., "checkout flow") |
| `service_or_component` | Software service or infrastructure component |
| `event` | A discrete occurrence (deployment, config change, etc.) |
| `evidence` | A collected evidence artifact (log snapshot, metric, trace) |
| `hypothesis` | A proposed root cause explanation |
| `action` | A proposed or executed remediation action |
| `outcome` | Result of an action |
| `deployment` | A code deployment event |
| `code_change` | A commit or pull request |
| `user_report` | Report from an end user |
| `environment` | Infrastructure environment (Kubernetes cluster, AWS region) |

### Edge Types

| Edge Type | Meaning |
|-----------|---------|
| `contains` | Investigation contains a symptom or sub-node |
| `affects` | Symptom affects a service |
| `depends_on` | Service depends on another service |
| `precedes` | Event preceded another event (temporal) |
| `supports` | Evidence supports a hypothesis |
| `contradicts` | Evidence contradicts a hypothesis |
| `confirms` | Action confirmed a hypothesis |
| `rejects` | Evidence/action rejected a hypothesis |
| `branch_lineage` | Connects branches of the investigation graph |

### GraphSlice

A `GraphSlice` is a serializable, immutable view of a subgraph. It is the **only** structure passed between the graph engine and the LLM layer. It carries a `is_redacted: bool` flag that must be `True` before being passed to any LLM provider.

```python
@dataclass
class GraphSlice:
    investigation_id: str
    branch_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: dict[str, Any]
    is_redacted: bool = False  # Must be True before passing to LLM
```

---

## Connector Interface

All connectors implement the `BaseConnector` abstract base class from `app/connectors/base.py`.

### Required Methods

```python
class BaseConnector(ABC):
    def capabilities(self) -> list[ConnectorCapability]: ...
    async def validate(self) -> ValidationResult: ...
    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]: ...
```

### ConnectorCapability Enum

```
LOGS | METRICS | TRACES | ALERTS | INCIDENTS |
DEPLOYMENTS | CODE_CHANGES | INFRASTRUCTURE_STATE
```

### How to Add a New Connector

1. Create `app/connectors/{name}/` directory with `__init__.py` and `connector.py`.
2. Implement `BaseConnector` in `connector.py`.
3. Declare `_SUPPORTED_CAPABILITIES` as a module-level constant.
4. Wrap all HTTP calls with `@async_retry(max_attempts=3, base_delay=1.0, jitter=True)`.
5. Catch `httpx.HTTPStatusError` and check for 429 (rate limit) - the retry decorator handles the `Retry-After` header automatically.
6. Return `[]` (not raise) when `capability` is not in `self.capabilities()`.
7. Add the connector to `ConnectorKind` enum in `app/models/all_models.py`.
8. Register the connector in the connector factory (when implemented).
9. Add connector tests to `backend/tests/test_connectors.py`.
10. Document the connector in `docs/connectors.md`.

---

## Hypothesis Pipeline

The hypothesis engine runs up to 6 sequential passes over the evidence graph. Each pass can add, filter, or re-score hypothesis candidates.

```
Pass 1: Rule-based heuristics
  - Pattern match evidence kinds against known failure modes
  - Config diff → "recent change caused regression"
  - Metric spike → "resource saturation"
  - Log errors → "application error"

Pass 2: Graph-based reasoning
  - Traverse service dependency edges to identify upstream causes
  - Correlate evidence timestamps with event nodes
  - Weight hypotheses by temporal proximity to symptom onset

Pass 3: Historical similarity
  - Query past resolved investigations with similar symptoms+service
  - Boost confidence of hypotheses that were confirmed in similar past cases

Pass 4: LLM generation
  - Build a GraphSlice (MUST be redacted before this step)
  - Send to configured LLM provider with versioned prompt template
  - Parse and normalize LLM-generated hypothesis candidates

Pass 5: Deduplication
  - Compute pairwise similarity between candidates
  - Merge candidates above the dedup threshold (default: 0.75)
  - Weighted scoring: service (40%) + symptoms (30%) + timewindow (20%) + description (10%)

Pass 6: Ranking
  - Sort all candidates by confidence_score descending
  - Apply user-configurable max_hypotheses limit
  - Return final ranked list
```

---

## LLM Abstraction

BugPilot supports 4 LLM providers via a common interface.

### Provider Interface

```python
class LLMProvider(ABC):
    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse: ...
    def model_name(self) -> str: ...
    def provider_name(self) -> str: ...
```

### Supported Providers

| Provider | Module | Model examples |
|----------|--------|---------------|
| Anthropic Claude | `anthropic_provider.py` | claude-3-5-sonnet, claude-opus-4 |
| OpenAI | `openai_provider.py` | gpt-4o, gpt-4-turbo |
| Azure OpenAI | `azure_openai_provider.py` | azure-gpt-4o |
| Ollama (local) | `ollama_provider.py` | llama3, mistral |

### Prompt Building from GraphSlice

1. Assert `graph_slice.is_redacted is True` - raise `ValueError` otherwise.
2. Serialize nodes and edges to a concise text or JSON representation.
3. Inject the serialized graph into the versioned prompt template.
4. Include investigation metadata: service name, severity, symptoms.
5. Send to provider via `complete()`.

### Cache Invalidation

LLM responses are cached by a composite key:
```
cache_key = SHA256(graph_checksum + ":" + prompt_version + ":" + SHA256(prompt_template))
```

Cache is invalidated when:
- The graph changes (new evidence, new edges, node property updates)
- The prompt version is bumped (e.g., from `v1.0.0` to `v2.0.0`)
- `bypass_cache=True` is passed (forces a fresh request without deleting the cached entry)

---

## RBAC Model

### Roles

| Role | Level | Description |
|------|-------|-------------|
| `viewer` | 0 | Read-only access to investigations |
| `investigator` | 1 | Can create investigations and collect evidence |
| `approver` | 2 | Can approve and run actions |
| `admin` | 3 | Full access including connector and org management |

### Permission Matrix

| Permission | viewer | investigator | approver | admin |
|-----------|--------|-------------|---------|-------|
| `read_investigation` | Y | Y | Y | Y |
| `create_investigation` | - | Y | Y | Y |
| `collect_evidence` | - | Y | Y | Y |
| `generate_hypothesis` | - | Y | Y | Y |
| `suggest_action` | - | Y | Y | Y |
| `approve_action` | - | - | Y | Y |
| `run_action` | - | - | Y | Y |
| `manage_connectors` | - | - | - | Y |
| `manage_roles` | - | - | - | Y |
| `manage_org_settings` | - | - | - | Y |
| `manage_webhooks` | - | - | - | Y |

Role hierarchy is strictly additive: each higher role includes all permissions of lower roles.

---

## Session and Activation Flow

```
1. User runs: bugpilot auth activate --license-key <key>
2. CLI sends: POST /api/v1/auth/activate
   Body: { license_key, email, device_fp, display_name }

3. Backend:
   a. Hash license_key with SHA-256
   b. Look up License by hash → validate status, expiry, seat limit
   c. Upsert User record for (org_id, email)
   d. Create JWT access token (1-hour TTL, HS256, claims: sub, org_id, device_fp, role, jti)
   e. Create opaque refresh token (64-byte random, SHA-256 hashed in DB)
   f. Store Session row with token_hash, refresh_hash, device_fp, ip_address
   g. Return { access_token, refresh_token, expires_in, org_id, user_id, role }

4. CLI stores tokens in ~/.config/bugpilot/session.json

5. Token refresh:
   POST /api/v1/auth/refresh { refresh_token }
   → Revoke old session → Issue new access + refresh token pair (rotation)
   → Old refresh token is immediately invalidated

6. Logout:
   POST /api/v1/auth/logout (Bearer token required)
   → Revokes all sessions for this (user_id, device_fp) pair
```

### Device Fingerprint

The device fingerprint (`device_fp`) is a hash derived from the CLI host machine. It is embedded in the JWT and stored in the Session row. This enables per-device session revocation.

---

## Privacy and Redaction Boundary

**Rule: No raw PII or secrets may ever be sent to an LLM provider.**

### How it works

1. All evidence payloads are stored with their raw content only during the `raw_payload_days` window (default: 7 days). After that, `raw_payload` is nulled; only `summary` is retained.

2. Before building a `GraphSlice` for LLM consumption, the graph service calls `redact_dict()` on all node `properties` fields.

3. `redact_dict()` applies these redaction patterns:
   - Email addresses (`user@domain.com`)
   - IPv4 addresses
   - AWS access key IDs (`AKIA...`)
   - JWT tokens (`eyJ...`)
   - Generic API keys / tokens / passwords (key=value pattern)
   - Credit/debit card numbers (13-16 digit sequences)

4. The `GraphSlice.is_redacted` flag is set to `True` only after the redaction step is complete.

5. LLM provider wrappers MUST assert `slice.is_redacted is True` and raise `ValueError` if not.

### Adding New Redaction Patterns

Add new regex patterns to `_PATTERNS` dict in `app/privacy/__init__.py`:

```python
_PATTERNS["my_pattern"] = re.compile(r"YOUR_REGEX_HERE")
```

All tests in `test_privacy.py` must pass after any pattern changes.

---

## Webhook Intake

BugPilot receives webhooks from external monitoring systems at:
- `POST /v1/webhooks/datadog` — HMAC-SHA256 via `X-Datadog-Signature`
- `POST /v1/webhooks/grafana` — HMAC-SHA256 via `X-Grafana-Signature` (sha256= prefix)
- `POST /v1/webhooks/cloudwatch` — AWS SNS certificate-based verification
- `POST /v1/webhooks/pagerduty` — HMAC-SHA256 via `X-PagerDuty-Signature` (v1= prefix, multi-sig)

All endpoints support a dual-secret grace window for zero-downtime key rotation.

Rate limiting: 100 requests per 60-second window per source IP + org combination.

Intake records are normalized into `WebhookIntakeRecord` with fields: `source`, `org_id`, `event_type`, `timestamp`, `payload`, `signature_valid`, `metadata`.
