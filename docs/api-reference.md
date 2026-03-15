# API Reference

The BugPilot REST API follows standard HTTP conventions. All endpoints are versioned under `/api/v1/`. Request and response bodies use JSON (`Content-Type: application/json`).

---

## Authentication

All endpoints except `/auth/activate` require a valid JWT in the Authorization header:

```
Authorization: Bearer <access_token>
```

Tokens expire after **1 hour**. Use the refresh endpoint to get a new token without re-activating.

---

## Auth Endpoints

### `POST /api/v1/auth/activate`

Exchange a license key for access and refresh tokens.

**Request:**
```json
{
  "license_key": "bp_T7zK9mNvXq...",
  "email": "alice@acme.com",
  "device_fp": "sha256_of_mac_address_os_arch",
  "display_name": "Alice Smith"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "org_id": "org_acme",
  "user_id": "usr_a3f8c2",
  "role": "investigator"
}
```

---

### `POST /api/v1/auth/refresh`

Exchange a refresh token for a new access token.

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response `200`:** Same structure as `/auth/activate`.

---

### `POST /api/v1/auth/logout`

Revoke the current session. Returns `204 No Content`.

---

### `GET /api/v1/auth/whoami`

Return the current user's identity.

**Response `200`:**
```json
{
  "user_id": "usr_a3f8c2",
  "email": "alice@acme.com",
  "display_name": "Alice Smith",
  "role": "investigator",
  "org_id": "org_acme",
  "org_slug": "acme-corp"
}
```

---

## Investigation Endpoints

### `GET /api/v1/investigations`

List investigations.

**Query params:** `status`, `severity`, `page` (default: 1), `page_size` (default: 20)

**Response `200`:** Array of investigation objects.

---

### `POST /api/v1/investigations`

Create a new investigation.

**Request:**
```json
{
  "title": "High error rate on payment-service",
  "symptom": "HTTP 5xx rate above 5%",
  "severity": "critical",
  "linked_services": ["payment-service"],
  "description": "Optional longer context"
}
```

**Response `201`:** Investigation object with `id`.

---

### `GET /api/v1/investigations/{investigation_id}`

Fetch a single investigation with full details.

---

### `PATCH /api/v1/investigations/{investigation_id}`

Update investigation fields.

**Request (all fields optional):**
```json
{
  "title": "Updated title",
  "status": "in_progress",
  "severity": "high",
  "description": "Updated notes"
}
```

---

### `DELETE /api/v1/investigations/{investigation_id}`

Permanently delete an investigation and all its evidence. Returns `204`.

---

## Evidence Endpoints

### `GET /api/v1/evidence`

List evidence items for an investigation.

**Query params:** `investigation_id` (required), `kind`, `limit`, `offset`

---

### `POST /api/v1/evidence`

Add an evidence item.

**Request:**
```json
{
  "investigation_id": "inv_7f3a2b",
  "label": "payment-service error logs",
  "kind": "log_snapshot",
  "source": "datadog",
  "summary": "47 NullPointerException at UserService.java:142",
  "connector_id": "conn_dd_prod"
}
```

**Response `201`:** Evidence object with `id`.

---

### `GET /api/v1/evidence/{evidence_id}`

Fetch a single evidence item.

---

### `DELETE /api/v1/evidence/{evidence_id}`

Delete an evidence item. Returns `204`.

---

## Hypothesis Endpoints

### `GET /api/v1/hypotheses`

List hypotheses for an investigation.

**Query params:** `investigation_id` (required), `status` (`active` / `confirmed` / `rejected`)

**Response `200`:** Array of hypothesis objects, sorted by `rank`.

---

### `POST /api/v1/hypotheses`

Create a hypothesis manually.

**Request:**
```json
{
  "investigation_id": "inv_7f3a2b",
  "title": "Bad deployment introduced regression",
  "description": "Stripe SDK v4 changed preferences API contract",
  "confidence_score": 0.72,
  "reasoning": "Deployment at 14:23 correlates with error onset at 14:31",
  "supporting_evidence": ["ev_9c1d3e", "ev_a2b4f1"]
}
```

---

### `POST /api/v1/hypotheses/{hypothesis_id}/confirm`

Mark a hypothesis as the confirmed root cause. Returns `200`.

---

### `POST /api/v1/hypotheses/{hypothesis_id}/reject`

Mark a hypothesis as rejected.

**Request (optional):**
```json
{ "reason": "Ruled out — memory was stable during the incident" }
```

---

### `PATCH /api/v1/hypotheses/{hypothesis_id}`

Update hypothesis fields.

---

## Action Endpoints

### `GET /api/v1/actions`

List actions for an investigation.

**Query params:** `investigation_id` (required), `status`

---

### `POST /api/v1/actions`

Create an action.

**Request:**
```json
{
  "investigation_id": "inv_7f3a2b",
  "title": "Rollback deployment a3f8c2d",
  "action_type": "rollback",
  "risk_level": "low",
  "description": "Revert Stripe SDK v4 update",
  "hypothesis_id": "hyp_f3a1d2",
  "rollback_plan": "git revert a3f8c2d && redeploy"
}
```

**Response `201`:** Action object with `id` and `status: pending`.

---

### `POST /api/v1/actions/{action_id}/approve`

Approve an action (requires `approver` or `admin` role). Returns `200`.

---

### `POST /api/v1/actions/{action_id}/run`

Execute an action. Returns `200` with the updated action object.

---

### `POST /api/v1/actions/{action_id}/dry-run`

Simulate an action without making any changes. Returns the same response shape as `/run` but no side effects are applied.

---

### `POST /api/v1/actions/{action_id}/cancel`

Cancel a pending or approved action. Returns `200`.

---

## Graph Endpoints

### `GET /api/v1/graph/timeline`

Return the investigation timeline as an ordered list of events.

**Query params:** `investigation_id` (required)

### `GET /api/v1/graph/causal/{investigation_id}`

Return the causal graph as nodes and weighted edges.

---

## Export Endpoints

### `GET /api/v1/export/json/{investigation_id}`

Export the full investigation bundle as JSON.

### `GET /api/v1/export/markdown/{investigation_id}`

Export a Markdown incident report.

---

## Webhook Endpoints

These endpoints receive alerts from monitoring platforms. Requests must include a valid HMAC signature.

| Method | Path | Source |
|--------|------|--------|
| POST | `/api/v1/webhooks/datadog` | Datadog |
| POST | `/api/v1/webhooks/grafana` | Grafana |
| POST | `/api/v1/webhooks/cloudwatch` | AWS CloudWatch (SNS) |
| POST | `/api/v1/webhooks/pagerduty` | PagerDuty |

All webhook endpoints return `200` on success or `401` on signature failure. Rate limit: 100 requests/min per IP + org.

---

## Admin Endpoints

All admin endpoints require the `admin` role.

### Connectors

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/connectors` | List configured connectors |
| POST | `/api/v1/admin/connectors` | Add a connector |
| DELETE | `/api/v1/admin/connectors/{id}` | Remove a connector |
| GET | `/api/v1/admin/connectors/validate` | Validate all connectors |

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/users` | List users |
| PATCH | `/api/v1/admin/users/{id}` | Update role |
| DELETE | `/api/v1/admin/users/{id}` | Deactivate user |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/webhooks` | List webhook configs |
| POST | `/api/v1/admin/webhooks` | Register webhook |
| DELETE | `/api/v1/admin/webhooks/{id}` | Remove webhook |

### Org Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/org/settings` | Get org settings |
| PATCH | `/api/v1/admin/org/settings` | Update settings (retention, etc.) |

### Audit Log

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/audit-logs` | Query audit log |

---

## Health Endpoints

| Path | Description |
|------|-------------|
| `GET /health` | Liveness — returns `{"status": "ok"}` |
| `GET /health/ready` | Readiness — checks database connectivity |
| `GET /metrics` | Prometheus metrics |
| `GET /openapi.json` | OpenAPI specification |
| `GET /docs` | Swagger UI |

---

## Error Responses

All errors use standard HTTP status codes with a JSON body:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request — invalid input |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — insufficient role |
| `404` | Not found |
| `422` | Validation error — request body failed schema validation |
| `429` | Rate limit exceeded |
| `500` | Internal server error |
