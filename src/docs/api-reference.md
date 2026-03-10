# API Reference

The BugPilot REST API follows standard HTTP conventions. All endpoints are versioned under `/api/v1/`. Request and response bodies use JSON (`Content-Type: application/json`).

---

## Authentication

All endpoints except `/auth/activate` require a valid JWT in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

JWTs expire after 1 hour. Use `POST /auth/refresh` with a valid refresh token to obtain a new pair.

---

## Authentication Endpoints

### `POST /api/v1/auth/activate`

Activate a license on a device and create a session.

**Request body:**

```json
{
  "license_key": "bp_T7zK9mNvXqAbCdEfGhIjKlMnOpQrStUvWxYz",
  "device_fingerprint": "sha256-of-mac-hostname-machine"
}
```

**Response `200`:**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "opaque-64-byte-hex",
  "token_type": "bearer",
  "org_id": "3f8a...",
  "user_id": "9c1b..."
}
```

---

### `POST /api/v1/auth/refresh`

Rotate the access and refresh tokens.

**Request body:**

```json
{
  "refresh_token": "opaque-64-byte-hex"
}
```

**Response `200`:** Same structure as `/activate`.

---

### `POST /api/v1/auth/logout`

Revoke the current session.

**Response `204`:** No body.

---

### `GET /api/v1/auth/whoami`

Return the authenticated user's details.

**Response `200`:**

```json
{
  "user_id": "9c1b...",
  "email": "alice@acme.com",
  "role": "investigator",
  "org_id": "3f8a...",
  "org_slug": "acme-corp"
}
```

---

## Investigation Endpoints

### `GET /api/v1/investigations`

List investigations for the authenticated org.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | — | `open` \| `in_progress` \| `resolved` \| `closed` |
| `service` | string | — | Filter by linked service name |
| `limit` | int | 20 | Max results |
| `offset` | int | 0 | Pagination offset |

**Response `200`:**

```json
[
  {
    "id": "inv_7f3a2b",
    "title": "High error rate on payment-service",
    "status": "open",
    "linked_services": ["payment-service"],
    "started_at": "2024-01-15T14:35:00Z",
    "resolved_at": null,
    "hypothesis_count": 3,
    "evidence_count": 65
  }
]
```

---

### `POST /api/v1/investigations`

Create a new investigation.

**Request body:**

```json
{
  "title": "High error rate on payment-service",
  "linked_services": ["payment-service"],
  "context": {
    "alert_name": "HTTP 5xx rate > 5%",
    "severity": "critical"
  }
}
```

**Response `201`:**

```json
{
  "id": "inv_7f3a2b",
  "title": "High error rate on payment-service",
  "status": "open",
  "branch_id": "branch_main",
  "linked_services": ["payment-service"],
  "started_at": "2024-01-15T14:35:00Z"
}
```

---

### `GET /api/v1/investigations/{investigation_id}`

Fetch a single investigation with full detail.

---

### `PATCH /api/v1/investigations/{investigation_id}`

Update investigation fields.

**Request body (all fields optional):**

```json
{
  "title": "Updated title",
  "status": "in_progress",
  "linked_services": ["payment-service", "stripe-gateway"]
}
```

---

### `DELETE /api/v1/investigations/{investigation_id}`

Delete an investigation and all associated data. Requires `admin` role.

---

## Evidence Endpoints

### `POST /api/v1/evidence/collect`

Trigger evidence collection from all configured connectors.

**Request body:**

```json
{
  "investigation_id": "inv_7f3a2b",
  "since": "2024-01-15T12:00:00Z",
  "until": "2024-01-15T15:00:00Z",
  "capabilities": ["LOGS", "METRICS", "DEPLOYMENTS"]
}
```

**Response `200`:**

```json
{
  "collected": 65,
  "degraded_connectors": ["grafana"],
  "duration_seconds": 3.2,
  "evidence_ids": ["ev_a1b2...", "..."]
}
```

---

### `GET /api/v1/evidence`

List evidence for an investigation.

**Query parameters:** `investigation_id` (required), `capability`, `limit`, `offset`.

---

### `GET /api/v1/evidence/{evidence_id}`

Fetch a single evidence item.

**Response `200`:**

```json
{
  "id": "ev_a1b2",
  "investigation_id": "inv_7f3a2b",
  "source_system": "datadog",
  "capability": "LOGS",
  "normalized_summary": "ERROR: NullPointerException in PaymentProcessor.charge() at 14:31:42",
  "reliability_score": 0.92,
  "is_redacted": true,
  "fetched_at": "2024-01-15T14:36:10Z",
  "ttl_expires_at": "2024-01-22T14:36:10Z"
}
```

---

## Hypothesis Endpoints

### `GET /api/v1/hypotheses`

List hypotheses for an investigation.

**Query parameters:** `investigation_id` (required), `status` (`active` \| `confirmed` \| `rejected`).

**Response `200`:**

```json
[
  {
    "id": "hyp_c9e1",
    "investigation_id": "inv_7f3a2b",
    "title": "Bad Deployment Introduced Regression",
    "description": "A deployment at 14:23 UTC correlates with 5xx onset...",
    "confidence_score": 0.72,
    "rank": 1,
    "status": "active",
    "generated_by": "rule",
    "is_single_lane": false,
    "evidence_ids": ["ev_a1b2", "ev_c3d4"]
  }
]
```

---

### `POST /api/v1/hypotheses/{hypothesis_id}/confirm`

Mark a hypothesis as confirmed (the root cause).

**Response `200`:** Updated hypothesis object.

---

### `POST /api/v1/hypotheses/{hypothesis_id}/reject`

Mark a hypothesis as rejected.

**Request body (optional):**

```json
{ "reason": "Deployment was rolled back before the spike started" }
```

---

## Action Endpoints

### `POST /api/v1/actions/suggest`

Generate remediation action candidates for an investigation.

**Request body:**

```json
{
  "investigation_id": "inv_7f3a2b",
  "hypothesis_id": "hyp_c9e1"
}
```

**Response `200`:**

```json
[
  {
    "id": "act_d2f4",
    "description": "Rollback deployment a3f8c2d",
    "rationale": "Deployment correlates with 5xx onset",
    "risk_level": "low",
    "expected_effect": "Restore previous stable version",
    "rollback_path": "git revert a3f8c2d && redeploy",
    "status": "pending"
  }
]
```

---

### `POST /api/v1/actions/{action_id}/approve`

Approve a medium/high/critical risk action. Requires `approver` role.

**Request body:**

```json
{ "note": "Approved after verifying rollback path with infra team" }
```

---

### `POST /api/v1/actions/{action_id}/run`

Execute an action. For `--dry-run`, pass `"dry_run": true`.

**Request body:**

```json
{ "dry_run": false }
```

**Response `200`:**

```json
{
  "action_id": "act_d2f4",
  "status": "completed",
  "dry_run": false,
  "output": "Deployment rolled back successfully. Pod restarts: 3/3 ready."
}
```

---

## Graph Endpoints

### `GET /api/v1/graph/timeline/{investigation_id}`

Return the investigation timeline as a list of events sorted by time.

**Response `200`:**

```json
[
  {
    "id": "node_1a2b",
    "node_type": "deployment",
    "label": "Deploy a3f8c2d",
    "timestamp": "2024-01-15T14:23:00Z",
    "properties": { "commit": "a3f8c2d", "author": "alice@acme.com" }
  },
  {
    "id": "node_3c4d",
    "node_type": "symptom",
    "label": "HTTP 5xx rate spike",
    "timestamp": "2024-01-15T14:31:00Z"
  }
]
```

---

### `GET /api/v1/graph/causal/{investigation_id}`

Return the full causal graph as nodes + edges.

**Response `200`:**

```json
{
  "nodes": [...],
  "edges": [
    {
      "id": "edge_e5f6",
      "from_node_id": "node_3c4d",
      "to_node_id": "node_1a2b",
      "edge_type": "caused_by"
    }
  ]
}
```

---

## Webhook Endpoints

### `POST /api/v1/webhooks/datadog`

Receive a Datadog webhook. Requires `X-Datadog-Webhook-ID` and `X-Hub-Signature` headers.

### `POST /api/v1/webhooks/grafana`

Receive a Grafana alerting webhook. Requires `X-Grafana-Signature` header (format: `sha256=HMAC`).

### `POST /api/v1/webhooks/cloudwatch`

Receive an AWS SNS/CloudWatch notification. Signature verified against SNS certificate.

### `POST /api/v1/webhooks/pagerduty`

Receive a PagerDuty webhook. Requires `X-PagerDuty-Signature` header (format: `v1=HMAC`). Supports multiple signatures for key rotation.

All webhook handlers:
- Verify the HMAC-SHA256 signature
- Support a dual-secret grace window for key rotation
- Apply per-IP+org rate limiting (100 requests/minute)
- Log verification failures to Prometheus and structlog

---

## Admin Endpoints

Admin endpoints require the `admin` role.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/connectors` | List configured connectors |
| `POST` | `/api/v1/admin/connectors` | Add a new connector |
| `DELETE` | `/api/v1/admin/connectors/{id}` | Remove a connector |
| `GET` | `/api/v1/admin/connectors/validate` | Test all connector connections |
| `GET` | `/api/v1/admin/users` | List org users |
| `PATCH` | `/api/v1/admin/users/{id}` | Update user role |
| `DELETE` | `/api/v1/admin/users/{id}` | Deactivate user |
| `GET` | `/api/v1/admin/audit-logs` | Query audit log |
| `GET` | `/api/v1/admin/org/settings` | Get org settings |
| `PATCH` | `/api/v1/admin/org/settings` | Update org settings (retention, etc.) |
| `GET` | `/api/v1/admin/webhooks` | List configured webhooks |
| `POST` | `/api/v1/admin/webhooks` | Register a new webhook secret |
| `DELETE` | `/api/v1/admin/webhooks/{id}` | Revoke a webhook |

---

## Health Endpoints

### `GET /health`

Liveness probe. Always returns `200` if the process is running.

```json
{ "status": "ok" }
```

### `GET /health/ready`

Readiness probe. Returns `200` if the database is reachable.

```json
{ "status": "ready", "db": "ok" }
```

Returns `503` with `{ "status": "not_ready", "db": "error: ..." }` if the DB is unavailable.

### `GET /metrics`

Prometheus metrics in text/plain exposition format.

---

## Error Responses

All errors follow a consistent structure:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request / validation error |
| `401` | Missing or invalid JWT |
| `403` | Insufficient role/permission |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate org slug) |
| `422` | Request body validation failed |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## Rate Limiting

Webhook endpoints are rate-limited to **100 requests per minute per source IP + org combination**. Other API endpoints do not currently enforce client-side rate limits but rely on the database connection pool as a natural backpressure mechanism.

---

## OpenAPI Specification

The full OpenAPI 3.1 spec is served at:

```
GET /openapi.json
GET /docs           (Swagger UI)
GET /redoc          (ReDoc)
```

To export the spec to a file:

```bash
curl http://localhost:8000/openapi.json > openapi/bugpilot_v1.json
```
