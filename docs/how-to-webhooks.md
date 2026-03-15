# How to Configure Webhooks (Automatic Mode)

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
Evidence collection begins
          │
          ▼
Open terminal → bugpilot investigate list --status open
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

## Step 1: Add a Webhook Secret to Your Config

Each webhook source requires a secret (minimum 32 characters) used to verify incoming request signatures. Add the secret to the `webhooks` section of `~/.config/bugpilot/config.yaml`:

```bash
# Generate a starter config if you haven't already
bugpilot config init
```

Then edit `~/.config/bugpilot/config.yaml` and fill in the `webhooks` section:

```yaml
webhooks:
  datadog:
    secret: "${DD_WEBHOOK_SECRET}"
  grafana:
    secret: "${GRAFANA_WEBHOOK_SECRET}"
  cloudwatch:
    secret: "${CW_WEBHOOK_SECRET}"
  pagerduty:
    secret: "${PD_WEBHOOK_SECRET}"
```

Use a different secret for each source. Secrets must be at least 32 characters.

---

## Step 2: Configure Your Monitoring Platform

Point your monitoring platform's webhook/notification settings at the BugPilot endpoint and set the shared secret.

### Datadog

1. Go to **Integrations → Webhooks**
2. Add a new webhook:
   - **URL:** `https://api.bugpilot.io/api/v1/webhooks/datadog`
   - **Payload:** Leave as default (standard Datadog format)
   - **Secret:** The value you set for `webhooks.datadog.secret` in config.yaml
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
4. Set the webhook secret to match what you set in config.yaml

---

## Step 3: Verify the Config

```bash
bugpilot config validate
```

```
✓ Config is valid.
  2 connector(s) configured
```

---

## Using Automatic Mode

After webhooks are configured, alerts create investigations automatically. In the terminal:

```bash
# See what investigations have been auto-created
bugpilot investigate list --status open

# Check the status of an auto-created investigation
bugpilot incident status inv_7f3a2b

# Continue from where BugPilot left off — add more evidence, review hypotheses
bugpilot evidence collect --investigation-id inv_7f3a2b ...
bugpilot hypotheses list --investigation-id inv_7f3a2b
```

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

To rotate a webhook secret without downtime:

1. Update the secret in `~/.config/bugpilot/config.yaml`
2. Update the secret in your monitoring platform
3. BugPilot supports a 1-hour grace window where both the old and new secret are accepted

---

## Rate Limiting

Webhook endpoints are rate-limited to **100 requests per minute** per IP + org combination. Requests exceeding this return `429 Too Many Requests`.

---

## Troubleshooting

**401 Unauthorized on delivery**
- The signature header is missing or the secret doesn't match
- Verify the secret in your monitoring platform matches `webhooks.<source>.secret` in config.yaml exactly (no extra spaces or encoding differences)
- Check for encoding differences (URL-encoding, extra whitespace)

**Webhook received but no investigation created**
- Verify the webhook payload format matches the expected schema for your source
- If a dedup check matched an existing open investigation, the webhook updated it — check `bugpilot investigate list --status open`
