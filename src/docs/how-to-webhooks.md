# How to Configure Webhooks

BugPilot can receive webhooks from monitoring platforms to automatically create and triage investigations when alerts fire — eliminating the manual step of opening an investigation.

---

## How It Works

```
Monitoring platform fires alert
        │
        ▼
POST /api/v1/webhooks/{source}
        │
        ▼
BugPilot verifies HMAC-SHA256 signature
        │
        ├── invalid signature → 401, metric incremented, logged
        │
        ▼
Dedup check: is there already an open investigation?
        │
        ├── duplicate found → attach evidence to existing investigation
        │
        ▼
Create new investigation (if no duplicate)
        │
        ▼
Enqueue evidence collection
```

---

## Supported Webhook Sources

| Source | Path | Signature header |
|--------|------|-----------------|
| Datadog | `/api/v1/webhooks/datadog` | `X-Hub-Signature` (hex HMAC) |
| Grafana | `/api/v1/webhooks/grafana` | `X-Grafana-Signature` (`sha256=HMAC`) |
| AWS CloudWatch (SNS) | `/api/v1/webhooks/cloudwatch` | Certificate-based SNS signature |
| PagerDuty | `/api/v1/webhooks/pagerduty` | `X-PagerDuty-Signature` (`v1=HMAC`) |

---

## Registering a Webhook Secret

```bash
# Register a new webhook for Datadog
curl -X POST http://localhost:8000/api/v1/admin/webhooks \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "datadog",
    "secret": "YOUR_SHARED_SECRET_MIN_32_CHARS",
    "description": "Production Datadog webhook"
  }'

# Returns: { "webhook_id": "wh_abc123", "source": "datadog" }
```

---

## Setting Up Each Source

### Datadog

1. In Datadog → Integrations → Webhooks → Add Webhook
2. **URL:** `https://your-bugpilot.example.com/api/v1/webhooks/datadog?org_id=YOUR_ORG_ID`
3. **Payload:** Default (or custom JSON)
4. **Custom Headers:**
   ```
   X-Hub-Signature: sha256=${signature}
   ```
5. In Datadog, set the Webhook secret to match the one you registered with BugPilot

**Sample payload sent by Datadog:**

```json
{
  "title": "High 5xx error rate on payment-service",
  "alert_id": "1234567",
  "severity": "critical",
  "tags": ["service:payment-service", "env:production"],
  "date": 1705330271,
  "org": { "id": "abc123", "name": "ACME Corp" }
}
```

---

### Grafana

1. In Grafana → Alerting → Contact points → Add contact point
2. **Integration:** Webhook
3. **URL:** `https://your-bugpilot.example.com/api/v1/webhooks/grafana?org_id=YOUR_ORG_ID`
4. **Authorization Header:** Leave blank (Grafana uses `X-Grafana-Signature`)
5. Under **Settings** → **Webhook secret**, set the same secret registered in BugPilot

**Sample payload:**

```json
{
  "alerts": [
    {
      "status": "firing",
      "labels": { "alertname": "HighLatency", "service": "checkout-svc" },
      "annotations": { "summary": "p99 latency > 5s" },
      "startsAt": "2024-01-15T14:31:00Z",
      "fingerprint": "abc123def456"
    }
  ],
  "receiver": "bugpilot",
  "externalURL": "https://grafana.example.com"
}
```

The `fingerprint` field is used for deduplication.

---

### AWS CloudWatch (via SNS)

1. In AWS → SNS → Create topic → HTTPS subscription
2. **Endpoint:** `https://your-bugpilot.example.com/api/v1/webhooks/cloudwatch?org_id=YOUR_ORG_ID`
3. Confirm the SNS subscription (BugPilot auto-confirms `SubscriptionConfirmation` messages)
4. Attach the SNS topic to your CloudWatch alarm

BugPilot verifies SNS messages using AWS certificate-based signature validation. The certificate URL must match `*.amazonaws.com` to prevent SSRF attacks.

**Sample alarm notification:**

```json
{
  "Type": "Notification",
  "MessageId": "abc123",
  "Subject": "ALARM: \"payment-service-5xx\" in us-east-1",
  "Message": "{\"AlarmName\":\"payment-service-5xx\",\"NewStateValue\":\"ALARM\",\"NewStateReason\":\"Threshold Crossed: 1 out of the last 1 datapoints (7.8%) was greater than the threshold (5.0%)\"}",
  "Timestamp": "2024-01-15T14:31:00.000Z",
  "Signature": "...",
  "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-..."
}
```

---

### PagerDuty

1. In PagerDuty → Service → Webhooks → Add Webhook
2. **Delivery URL:** `https://your-bugpilot.example.com/api/v1/webhooks/pagerduty?org_id=YOUR_ORG_ID`
3. **Event types:** `incident.triggered`, `incident.acknowledged`, `incident.resolved`
4. Copy the webhook secret from PagerDuty and register it in BugPilot

PagerDuty sends multiple signatures in a comma-separated header for key rotation. BugPilot accepts any valid signature from the list.

**Sample payload:**

```json
{
  "event": {
    "id": "evt_abc",
    "event_type": "incident.triggered",
    "data": {
      "id": "P1ABC12",
      "title": "High 5xx rate - payment-service",
      "urgency": "high",
      "service": { "id": "SVC001", "summary": "payment-service" },
      "created_at": "2024-01-15T14:31:00Z"
    }
  }
}
```

---

## Secret Rotation (Zero-downtime)

BugPilot supports a **dual-secret grace window** for rotating webhook secrets without downtime:

```bash
# 1. Register the new secret as the "previous" secret on your webhook
curl -X PATCH http://localhost:8000/api/v1/admin/webhooks/wh_abc123 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"secret": "NEW_SECRET", "previous_secret": "OLD_SECRET"}'

# 2. Update the secret in your monitoring platform

# 3. After all platforms are updated, clear the previous secret
curl -X PATCH http://localhost:8000/api/v1/admin/webhooks/wh_abc123 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"previous_secret": null}'
```

During the grace window, BugPilot accepts signatures from either the current or previous secret.

---

## Rate Limiting

Webhook endpoints enforce **100 requests per minute per source IP + org combination**. When exceeded, BugPilot returns `429 Too Many Requests` and logs the event.

Legitimate monitoring platforms typically send far fewer webhooks than this limit. If you exceed it, consider consolidating multiple alert rules into fewer webhook calls.

---

## Testing Webhooks Locally

Use the sample payloads in `fixtures/sample_configs/sample_webhook_payloads/`:

```bash
# Test Datadog webhook locally
SIGNATURE=$(echo -n '{"title":"Test Alert"}' | openssl dgst -sha256 -hmac "YOUR_SECRET" | awk '{print $2}')

curl -X POST http://localhost:8000/api/v1/webhooks/datadog?org_id=YOUR_ORG_ID \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature: sha256=$SIGNATURE" \
  -d @fixtures/sample_configs/sample_webhook_payloads/datadog.json
```

---

## Webhook Verification Failures

If a webhook fails signature verification, BugPilot:
1. Returns `401 Unauthorized`
2. Increments `bugpilot_webhook_verification_failures_total{source="datadog"}` Prometheus counter
3. Logs at `warning` level with `event=webhook_verification_failed`

Monitor for verification failures to detect misconfigured secrets or potential replay attacks:

```yaml
# Prometheus alert
- alert: WebhookVerificationFailures
  expr: increase(bugpilot_webhook_verification_failures_total[5m]) > 10
  labels:
    severity: warning
  annotations:
    summary: "Webhook signature verification failures — check secret configuration"
```
