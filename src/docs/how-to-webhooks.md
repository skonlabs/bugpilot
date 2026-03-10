# How to Configure Webhooks

BugPilot can receive webhooks from your monitoring platforms to automatically create and triage investigations when alerts fire — eliminating the manual step of opening an investigation.

---

## How It Works

```
Monitoring platform fires alert
          │
          ▼
BugPilot receives webhook POST
          │
          ▼
Signature verified (HMAC-SHA256)
          │
          ▼
Dedup check — does a similar open investigation already exist?
          │
    ┌─────┴──────┐
  New alert    Duplicate
    │              │
    ▼              ▼
Create new     Update existing
investigation  investigation
          │
          ▼
Evidence collection enqueued
```

---

## Supported Sources

| Source | Webhook path | Signature header |
|--------|-------------|-----------------|
| Datadog | `/api/v1/webhooks/datadog` | `X-Hub-Signature` (hex HMAC) |
| Grafana | `/api/v1/webhooks/grafana` | `X-Grafana-Signature` (`sha256=` prefix) |
| AWS CloudWatch (SNS) | `/api/v1/webhooks/cloudwatch` | SNS certificate verification |
| PagerDuty | `/api/v1/webhooks/pagerduty` | `X-PagerDuty-Signature` (`v1=` prefix) |

---

## Step 1: Register a Webhook Secret

Each webhook source requires a secret (minimum 32 characters) used to verify incoming request signatures.

Via the dashboard: **Settings → Webhooks → Add Webhook**

Via the API:

```bash
curl -X POST https://api.bugpilot.io/api/v1/admin/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "datadog",
    "secret": "your-webhook-secret-min-32-chars-long",
    "description": "Production Datadog alerts"
  }'
```

---

## Step 2: Configure Your Monitoring Platform

### Datadog

1. Go to **Integrations → Webhooks**
2. Add a new webhook:
   - **URL:** `https://api.bugpilot.io/api/v1/webhooks/datadog`
   - **Payload:** Leave as default (standard Datadog format)
   - **Secret:** Use the secret you registered in Step 1
3. Add the webhook to any monitor under **Notify your team**

### Grafana

1. Go to **Alerting → Contact points → New contact point**
2. Select type **Webhook**
3. Set URL to `https://api.bugpilot.io/api/v1/webhooks/grafana`
4. Under **Optional Webhook settings**, set the Authorization header using your secret
5. Save and assign to an alert rule via a notification policy

### AWS CloudWatch (via SNS)

1. Create an SNS topic
2. Add an HTTPS subscription pointing to `https://api.bugpilot.io/api/v1/webhooks/cloudwatch`
3. BugPilot will automatically confirm the subscription on first delivery
4. Configure your CloudWatch alarms to send to the SNS topic

### PagerDuty

1. Go to **Integrations → Generic Webhooks (v3)**
2. Add endpoint: `https://api.bugpilot.io/api/v1/webhooks/pagerduty`
3. Select events: **incident.triggered**, **incident.acknowledged**, **incident.resolved**
4. Set the webhook secret to match what you registered in Step 1

---

## Deduplication

When a webhook arrives, BugPilot checks for existing open investigations using a weighted similarity score:

| Signal | Weight |
|--------|--------|
| Service name match | 40% |
| Time proximity (within 30 min) | 30% |
| Alert signature match | 20% |
| Symptom text similarity | 10% |

If similarity exceeds the threshold, the webhook updates the existing investigation rather than creating a new one.

---

## Secret Rotation

BugPilot supports dual-secret rotation — both the current and previous secret are valid during a grace window, so you can rotate without downtime.

```bash
# Update with new secret (old secret remains valid for 1 hour)
curl -X PATCH https://api.bugpilot.io/api/v1/admin/webhooks/{webhook_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"secret": "your-new-secret-min-32-chars-long"}'
```

---

## Rate Limiting

Webhook endpoints are rate-limited to **100 requests per minute** per IP + org combination. Requests exceeding this return `429 Too Many Requests`.

---

## Troubleshooting

**401 Unauthorized on delivery**
- The signature header is missing or the secret doesn't match
- Verify the secret in your monitoring platform matches the registered secret exactly
- Check for encoding differences (URL-encoding, extra whitespace)

**Webhook received but no investigation created**
- Check the structured logs: `bugpilot_webhook_verification_failures_total` Prometheus metric
- Verify the webhook payload format matches the expected schema for your source

**Testing with sample payloads**

Use the sample webhook payloads to test your setup:

```bash
# Datadog sample
curl -X POST https://api.bugpilot.io/api/v1/webhooks/datadog \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature: sha256=<computed_hmac>" \
  -d @sample_webhook_payloads/datadog.json
```
